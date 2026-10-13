#!/usr/bin/env python3
"""Fail-closed serial runner for the frozen SRP schedule.

This runner writes evidence only under ignored work/. It does not resume runs,
replace sessions, fetch images, expose credentials to the agent, or print traces.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import tomllib
import uuid


ROOT = Path(__file__).resolve().parents[3]
SRP = ROOT / "experiments" / "srp"
CONFIG = SRP / "config"
COMPOSE = CONFIG / "compose.yaml"
MANIFEST_PATH = CONFIG / "execution-manifest.json"
SCHEDULE_PATH = CONFIG / "schedule.json"
PREPARE = SRP / "tools" / "prepare.py"
VERIFY = SRP / "tools" / "verify.py"
DRIVER = SRP / "tools" / "session-driver.cjs"
TELEMETRY = SRP / "tools" / "telemetry.py"
EVALUATOR = SRP / "evaluator"
READINESS = SRP / "preparation" / "readiness.json"
SEED_NAME = "database_seed"
DEPENDENCY_NAME = "dependencies"
RUNTIME_NAME = "runtime_image"
EXPECTED_SEED_COUNTS = "49|22|0"
AGENT_UID = 1000
AGENT_GID = 1000
DB_START_SECONDS = 180
DB_RETRY_SECONDS = 120
GATEWAY_RETRY_SECONDS = 60
AGENT_HOST_GRACE_SECONDS = 60
POST_BUILD_VERIFY_RESERVE_SECONDS = 120
PREFLIGHT_FILES = (
    "experiments/srp/config/execution-manifest.json",
    "experiments/srp/config/schedule.json",
    "experiments/srp/config/compose.yaml",
    "experiments/srp/config/codex.toml",
    "experiments/srp/config/agent-runtime.env",
    "experiments/srp/config/AGENTS.md",
    "experiments/srp/config/seccomp.json",
    "experiments/srp/tools/prepare.py",
    "experiments/srp/tools/verify.py",
    "experiments/srp/tools/session-driver.cjs",
    "experiments/srp/tools/model-gateway.cjs",
    "experiments/srp/tools/telemetry.py",
    "experiments/srp/evaluator/README.md",
    "experiments/srp/evaluator/jest.config.cjs",
    "experiments/srp/evaluator/maintenance.spec.cjs",
    "experiments/srp/preparation/oracle-freeze.json",
    "experiments/srp/preparation/variant-b.patch",
    "experiments/srp/preparation/README.md",
    "work/dependencies.tar.gz",
    "work/runtime-image.tar",
    "work/database-seed.sql",
)


class AbortRun(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class CommandTimeout(Exception):
    pass


class BudgetExpired(CommandTimeout):
    """The shared external-grading deadline, rather than a local command cap, expired."""


def bounded_timeout(deadline: float | None, maximum: float | None) -> float | None:
    if deadline is None:
        return maximum
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise BudgetExpired
    return remaining if maximum is None else min(maximum, remaining)


def check_deadline(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() >= deadline:
        raise BudgetExpired


def sleep_before_retry(seconds: float, deadline: float | None) -> None:
    if deadline is None:
        time.sleep(seconds)
        return
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise BudgetExpired
    time.sleep(min(seconds, remaining))
    check_deadline(deadline)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_file(path: Path, deadline: float | None = None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            check_deadline(deadline)
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    check_deadline(deadline)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    temp = path.with_name(path.name + ".tmp")
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temp, 0o600)
    os.replace(temp, path)
    try:
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


def append_jsonl(path: Path, value: object) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "ab") as handle:
        handle.write((json.dumps(value, sort_keys=True) + "\n").encode())
        handle.flush()
        os.fsync(handle.fileno())


def private_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(path, mode)
    if hasattr(os, "chown"):
        os.chown(path, AGENT_UID, AGENT_GID)


def capture(
    argv: list[str],
    stdout_path: Path,
    stderr_path: Path,
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    stdin=None,
    timeout: float | None = None,
    deadline: float | None = None,
) -> int:
    """Run a command with private logs and no terminal output."""
    effective_timeout = bounded_timeout(deadline, timeout)
    budget_capped = deadline is not None and (timeout is None or effective_timeout < timeout)
    stdout_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        os.chmod(stdout_path, 0o600)
        os.chmod(stderr_path, 0o600)
        try:
            result = subprocess.run(
                argv,
                cwd=cwd,
                env=env,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                timeout=effective_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            if budget_capped or (deadline is not None and time.monotonic() >= deadline):
                raise BudgetExpired from error
            raise CommandTimeout from error
    return result.returncode


def capture_text(
    argv: list[str], *, env: dict[str, str] | None = None, timeout: float = 30,
    deadline: float | None = None,
) -> str:
    """Return short machine-readable output; callers never print it verbatim."""
    effective_timeout = bounded_timeout(deadline, timeout)
    budget_capped = deadline is not None and effective_timeout < timeout
    try:
        result = subprocess.run(
            argv,
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=effective_timeout,
            check=False,
            text=True,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        if isinstance(error, subprocess.TimeoutExpired) and (
            budget_capped or (deadline is not None and time.monotonic() >= deadline)
        ):
            raise BudgetExpired from error
        raise AbortRun("host_command_failed", "A required local command did not complete.") from error
    if result.returncode:
        raise AbortRun("host_command_failed", "A required local command failed.")
    return result.stdout.strip()


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise AbortRun("frozen_input_invalid", "A frozen JSON input is missing or invalid.") from error
    if not isinstance(value, dict):
        raise AbortRun("frozen_input_invalid", "A frozen JSON input has an unexpected shape.")
    return value


def validate_schedule(schedule: dict, manifest: dict) -> list[dict]:
    sessions = schedule.get("sessions")
    if manifest.get("planned_sessions") != 30 or not isinstance(sessions, list) or len(sessions) != 30:
        raise AbortRun("schedule_mismatch", "The frozen schedule is not the approved 30-session matrix.")
    expected = {(task, rep, variant) for task in ("T01", "T02", "T03", "T04", "T05")
                for rep in (1, 2, 3) for variant in ("A", "B")}
    found = set()
    for position, item in enumerate(sessions, start=1):
        if not isinstance(item, dict):
            raise AbortRun("schedule_mismatch", "A scheduled session entry is invalid.")
        task, repetition, variant = item.get("task"), item.get("repetition"), item.get("variant")
        if item.get("position") != position or task not in {"T01", "T02", "T03", "T04", "T05"}:
            raise AbortRun("schedule_mismatch", "A scheduled session position or task is invalid.")
        if repetition not in (1, 2, 3) or variant not in ("A", "B"):
            raise AbortRun("schedule_mismatch", "A scheduled session variant or repetition is invalid.")
        if item.get("id") != f"{task}-{repetition}-{variant}":
            raise AbortRun("schedule_mismatch", "A scheduled session identifier is invalid.")
        key = (task, repetition, variant)
        if key in found:
            raise AbortRun("schedule_mismatch", "The frozen schedule contains a duplicate session.")
        found.add(key)
    if found != expected:
        raise AbortRun("schedule_mismatch", "The frozen schedule does not contain every task variant.")
    return sessions


def validate_root_output(path_arg: str) -> Path:
    candidate = Path(path_arg).expanduser()
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    if any(part.is_symlink() for part in [candidate, *candidate.parents] if part.exists()):
        raise AbortRun("unsafe_output_path", "The output path cannot contain symlinks.")
    output = candidate.resolve(strict=False)
    work = (ROOT / "work").resolve()
    if output == work or work not in output.parents:
        raise AbortRun("unsafe_output_path", "The output directory must be new and inside ignored work/.")
    if not output.parent.is_dir():
        raise AbortRun("unsafe_output_path", "The output directory's parent must already exist.")
    if output.exists():
        raise AbortRun("unsafe_output_path", "The output directory must be new; this runner never resumes.")
    rel = output.relative_to(ROOT)
    try:
        subprocess.run(
            ["git", "-C", str(ROOT), "check-ignore", "-q", "--", str(rel)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise AbortRun("unsafe_output_path", "The requested output directory is not ignored by Git.") from error
    return output


def validate_auth_file(path_arg: str) -> Path:
    path = Path(path_arg).expanduser()
    try:
        info = path.lstat()
    except OSError as error:
        raise AbortRun("auth_file_missing", "The existing private authentication file is unavailable.") from error
    if path.is_symlink() or not path.is_file() or info.st_mode & 0o077:
        raise AbortRun("auth_file_not_private", "The authentication file must be a regular private file.")
    if not os.access(path, os.R_OK):
        raise AbortRun("auth_file_unreadable", "The existing private authentication file is not readable.")
    return path.resolve()


def validate_attestation(path_arg: str, codex_config_hash: str, manifest: dict) -> tuple[Path, str]:
    path = Path(path_arg).expanduser().resolve()
    if path != READINESS.resolve():
        raise AbortRun("readiness_attestation_invalid", "Use the readiness report frozen with this protocol.")
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise AbortRun("readiness_attestation_missing", "A valid prelaunch readiness attestation is required.") from error
    probe = data.get("successful_probe", {}) if isinstance(data, dict) else {}
    checks = (
        data.get("phase") == "non-benchmark readiness; excluded from measured outcomes",
        probe.get("id") == "readiness-002",
        probe.get("model") == manifest["model"]["id"],
        probe.get("reasoning") == manifest["model"]["reasoning_effort"],
        probe.get("upstream_http_statuses") == [200],
        probe.get("all_provider_models_match") is True,
        probe.get("all_request_efforts_match") is True,
        probe.get("common_instructions_observed") is True,
        probe.get("scratch_write_read_delete") is True,
        probe.get("shell_credentials_absent") is True,
        probe.get("control_and_driver_home_reads_denied") is True,
        probe.get("proc_unavailable") is True,
        probe.get("external_https_blocked") is True,
        probe.get("prisma_select_1") is True,
        probe.get("provider_usage_matches_cli_totals") is True,
        probe.get("codex_configuration_sha256") == codex_config_hash,
        isinstance(probe.get("provider_response_count"), int) and probe["provider_response_count"] > 0,
        isinstance(probe.get("termination"), dict) and probe["termination"].get("code") == 0
        and probe["termination"].get("timed_out") is False,
    )
    if not all(checks):
        raise AbortRun("readiness_attestation_invalid", "The readiness attestation does not match the frozen execution inputs.")
    return path.resolve(), sha256_file(path)


def verify_frozen_artifacts(manifest: dict, log_dir: Path) -> None:
    rc = capture(
        [sys.executable, str(VERIFY)],
        log_dir / "frozen-verify.stdout",
        log_dir / "frozen-verify.stderr",
        timeout=60,
    )
    if rc:
        raise AbortRun("frozen_artifact_mismatch", "Frozen artifact verification failed; inspect the private preflight logs.")
    for name, spec in manifest["local_cache"].items():
        path = ROOT / spec["path"]
        if not path.is_file() or sha256_file(path) != spec["sha256"]:
            raise AbortRun("cache_hash_mismatch", "A private local cache is missing or does not match its frozen hash.")


def validate_code_mode_config(manifest: dict) -> str:
    try:
        raw = (CONFIG / "codex.toml").read_bytes()
        config = tomllib.loads(raw.decode())
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise AbortRun("codex_config_invalid", "The frozen Codex configuration could not be read.") from error
    if config.get("model") != manifest["model"]["id"]:
        raise AbortRun("codex_config_mismatch", "The Codex model does not match the execution manifest.")
    if config.get("model_reasoning_effort") != manifest["model"]["reasoning_effort"]:
        raise AbortRun("codex_config_mismatch", "The Codex reasoning effort does not match the execution manifest.")
    if config.get("features", {}).get("code_mode_host") is not True:
        raise AbortRun(
            "code_mode_host_disabled",
            "code_mode_host is disabled; complete readiness testing, amend, and refreeze before measured sessions.",
        )
    if config.get("features", {}).get("multi_agent") is not False or config.get("features", {}).get("multi_agent_v2") is not False:
        raise AbortRun("multi_agent_enabled", "The frozen configuration must keep multi-agent features disabled.")
    return hashlib.sha256(raw).hexdigest()


def verify_local_images(manifest: dict, logs: Path) -> None:
    runtime_id = manifest["runtime"]["image_id"]
    inspect = subprocess.run(
        ["docker", "image", "inspect", runtime_id],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=30,
        check=False,
        text=True,
    )
    if inspect.returncode:
        load_rc = capture(
            ["docker", "load", "--input", str(ROOT / manifest["local_cache"][RUNTIME_NAME]["path"])],
            logs / "runtime-image-load.stdout",
            logs / "runtime-image-load.stderr",
            timeout=180,
        )
        if load_rc:
            raise AbortRun("runtime_image_unavailable", "The frozen runtime image could not be loaded from its verified cache.")
        inspect = subprocess.run(
            ["docker", "image", "inspect", runtime_id],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
            text=True,
        )
    if inspect.returncode:
        raise AbortRun("runtime_image_mismatch", "The frozen runtime image ID is not available locally.")
    try:
        runtime = json.loads(inspect.stdout)[0]
    except (json.JSONDecodeError, IndexError, TypeError) as error:
        raise AbortRun("runtime_image_mismatch", "The local runtime image inspection result is invalid.") from error
    if runtime.get("Id") != runtime_id or runtime.get("Os") != "linux" or runtime.get("Architecture") != "amd64":
        raise AbortRun("runtime_image_mismatch", "The local runtime image does not match the frozen immutable image ID.")

    postgres_ref = manifest["runtime"]["postgres_image"]
    pg = subprocess.run(
        ["docker", "image", "inspect", postgres_ref],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=30,
        check=False,
        text=True,
    )
    if pg.returncode:
        raise AbortRun("postgres_image_unavailable", "The frozen PostgreSQL image digest is not available locally.")
    try:
        pg_data = json.loads(pg.stdout)[0]
    except (json.JSONDecodeError, IndexError, TypeError) as error:
        raise AbortRun("postgres_image_mismatch", "The local PostgreSQL image inspection result is invalid.") from error
    expected_repo_digest = postgres_ref
    if expected_repo_digest not in (pg_data.get("RepoDigests") or []):
        raise AbortRun("postgres_image_mismatch", "The local PostgreSQL image does not expose the frozen digest.")


def sanitized_env() -> dict[str, str]:
    env = os.environ.copy()
    for name in ("OPENAI_API_KEY", "BENCHMARK_DRIVER_TOKEN", "UPSTREAM_AUTH_FILE"):
        env.pop(name, None)
    return env


def compose_env(manifest: dict, control: Path, workspace: Path, auth: Path) -> dict[str, str]:
    env = sanitized_env()
    env.update({
        "BENCHMARK_RUNTIME_IMAGE": manifest["runtime"]["image_id"],
        "BENCHMARK_CONTROL": str(control),
        "BENCHMARK_AUTH_FILE": str(auth),
        "BENCHMARK_WORKSPACE": str(workspace),
        "BENCHMARK_SECCOMP_FILE": str((CONFIG / "seccomp.json").resolve()),
    })
    return env


def compose_base(project: str) -> list[str]:
    return ["docker", "compose", "--project-name", project, "--file", str(COMPOSE)]


def read_container_state(name: str) -> dict | None:
    result = subprocess.run(
        ["docker", "inspect", name],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=15,
        check=False,
        text=True,
    )
    if result.returncode:
        return None
    try:
        value = json.loads(result.stdout)[0]
        return value.get("State", {})
    except (json.JSONDecodeError, IndexError, TypeError):
        return None


def remove_container(name: str, logs: Path) -> bool:
    if read_container_state(name) is None:
        return True
    rc = capture(
        ["docker", "rm", "--force", name],
        logs / "container-remove.stdout",
        logs / "container-remove.stderr",
        timeout=30,
    )
    return rc == 0


def compose_down(project: str, env: dict[str, str], logs: Path) -> bool:
    rc = capture(
        compose_base(project) + ["down", "--volumes", "--remove-orphans"],
        logs / "compose-down.stdout",
        logs / "compose-down.stderr",
        env=env,
        timeout=90,
    )
    return rc == 0


def wait_database_health(
    project: str, env: dict[str, str], logs: Path, deadline: float | None = None
) -> None:
    phase_deadline = time.monotonic() + DB_START_SECONDS
    if deadline is not None:
        phase_deadline = min(phase_deadline, deadline)
    while time.monotonic() < phase_deadline:
        check_deadline(deadline)
        attempt_timeout = min(15, phase_deadline - time.monotonic())
        try:
            container_id = capture_text(
                compose_base(project) + ["ps", "-q", "database"], env=env,
                timeout=attempt_timeout, deadline=deadline,
            )
        except AbortRun:
            sleep_before_retry(2, deadline)
            continue
        if container_id:
            try:
                result = subprocess.run(
                    ["docker", "inspect", "--format", "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}", container_id],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    timeout=bounded_timeout(deadline, min(15, phase_deadline - time.monotonic())),
                    check=False,
                    text=True,
                )
            except subprocess.TimeoutExpired as error:
                check_deadline(deadline)
                raise CommandTimeout from error
            except OSError as error:
                raise AbortRun("database_health_probe_failed", "The private PostgreSQL health probe failed locally.") from error
            if result.returncode == 0 and result.stdout.strip() == "healthy":
                return
        sleep_before_retry(2, deadline)
    check_deadline(deadline)
    raise AbortRun("database_health_timeout", "The private PostgreSQL service did not become healthy.")


def wait_real_psql(
    project: str, env: dict[str, str], logs: Path, deadline: float | None = None
) -> None:
    """Healthchecks can see PostgreSQL's temporary init server; retry actual SQL."""
    phase_deadline = time.monotonic() + DB_RETRY_SECONDS
    if deadline is not None:
        phase_deadline = min(phase_deadline, deadline)
    attempt = 0
    probe = (
        "SELECT current_database() = 'benchmark' "
        "AND current_user = 'benchmark'"
    )
    try:
        while time.monotonic() < phase_deadline:
            check_deadline(deadline)
            attempt += 1
            try:
                result = subprocess.run(
                    compose_base(project) + [
                        "exec", "--no-TTY", "database", "psql", "-X", "-A", "-t",
                        "-v", "ON_ERROR_STOP=1", "-U", "benchmark", "-d", "benchmark", "-c", probe,
                    ],
                    cwd=ROOT,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    timeout=min(15, phase_deadline - time.monotonic()),
                    check=False,
                    text=True,
                )
            except subprocess.TimeoutExpired:
                check_deadline(deadline)
                sleep_before_retry(2, deadline)
                continue
            except OSError as error:
                raise AbortRun("database_sql_probe_failed", "The private PostgreSQL SQL probe failed locally.") from error
            if result.returncode == 0 and result.stdout.strip() == "t":
                write_json(logs / "database-readiness.json", {"attempts": attempt, "ready": True, "checked_at": utc_now()})
                return
            sleep_before_retry(2, deadline)
    except BudgetExpired:
        write_json(logs / "database-readiness.json", {
            "attempts": attempt, "ready": False, "checked_at": utc_now(),
            "reason": "grading_budget_expired",
        })
        raise
    budget_expired = deadline is not None and time.monotonic() >= deadline
    write_json(logs / "database-readiness.json", {
        "attempts": attempt, "ready": False, "checked_at": utc_now(),
        "reason": "grading_budget_expired" if budget_expired else "database_sql_timeout",
    })
    check_deadline(deadline)
    raise AbortRun("database_sql_timeout", "The database socket did not accept real SQL before the bounded retry expired.")


def restore_seed(
    project: str, env: dict[str, str], manifest: dict, logs: Path,
    deadline: float | None = None,
) -> None:
    rc = capture(
        compose_base(project) + [
            "exec", "--no-TTY", "database", "mkdir", "-p",
            "/var/run/postgresql/.git", "/var/run/postgresql/.codex", "/var/run/postgresql/.agents",
        ],
        logs / "socket-metadata.stdout",
        logs / "socket-metadata.stderr",
        env=env,
        timeout=20,
        deadline=deadline,
    )
    if rc:
        raise AbortRun("database_socket_metadata_failed", "The protected PostgreSQL socket metadata directories could not be created.")
    seed = ROOT / manifest["local_cache"][SEED_NAME]["path"]
    try:
        with seed.open("rb") as stdin:
            rc = capture(
                compose_base(project) + [
                    "exec", "--no-TTY", "database", "psql", "-X", "-v", "ON_ERROR_STOP=1",
                    "-U", "benchmark", "-d", "benchmark",
                ],
                logs / "seed-restore.stdout",
                logs / "seed-restore.stderr",
                env=env,
                stdin=stdin,
                timeout=150,
                deadline=deadline,
            )
    except BudgetExpired:
        raise
    except CommandTimeout as error:
        raise AbortRun("database_seed_timeout", "Restoring the frozen database seed exceeded its bound.") from error
    if rc:
        raise AbortRun("database_seed_failed", "The frozen database seed could not be restored.")
    query = (
        "SELECT (SELECT count(*) FROM public.\"InfraConfig\")::text || '|' || "
        "(SELECT count(*) FROM public._prisma_migrations)::text || '|' || "
        "(SELECT count(*) FROM public.\"Team\")::text"
    )
    try:
        result = subprocess.run(
            compose_base(project) + [
                "exec", "--no-TTY", "database", "psql", "-X", "-A", "-t",
                "-v", "ON_ERROR_STOP=1", "-U", "benchmark", "-d", "benchmark", "-c", query,
            ],
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=bounded_timeout(deadline, 30),
            check=False,
            text=True,
        )
    except subprocess.TimeoutExpired as error:
        check_deadline(deadline)
        raise AbortRun("database_seed_validation_timeout", "Validating the restored database seed exceeded its bound.") from error
    except OSError as error:
        raise AbortRun("database_seed_validation_failed", "The restored database seed could not be checked locally.") from error
    if result.returncode or result.stdout.strip() != EXPECTED_SEED_COUNTS:
        write_json(logs / "seed-counts.json", {"expected": EXPECTED_SEED_COUNTS, "actual": result.stdout.strip() if result.returncode == 0 else None})
        raise AbortRun("database_seed_validation_failed", "The restored database seed did not match the frozen baseline counts.")
    write_json(logs / "seed-counts.json", {"expected": EXPECTED_SEED_COUNTS, "actual": result.stdout.strip(), "validated": True})


def wait_gateway(project: str, env: dict[str, str], logs: Path) -> None:
    deadline = time.monotonic() + GATEWAY_RETRY_SECONDS
    probe = (
        "const h=require('node:http');"
        "const r=h.get('http://127.0.0.1:8080/__health',x=>{x.resume();process.exit(x.statusCode===401?0:1)});"
        "r.setTimeout(2000,()=>process.exit(2));r.on('error',()=>process.exit(3));"
    )
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        rc = capture(
            compose_base(project) + ["exec", "--no-TTY", "model-gateway", "node", "-e", probe],
            logs / "gateway-probe.stdout",
            logs / "gateway-probe.stderr",
            env=env,
            timeout=8,
        )
        if rc == 0:
            write_json(logs / "gateway-readiness.json", {"attempts": attempt, "ready": True, "checked_at": utc_now()})
            return
        time.sleep(1)
    write_json(logs / "gateway-readiness.json", {"attempts": attempt, "ready": False, "checked_at": utc_now()})
    raise AbortRun("gateway_health_timeout", "The isolated model gateway did not become ready.")


def prepare_workspace(variant: str, output: Path, logs: Path) -> str:
    rc = capture(
        [sys.executable, str(PREPARE), "--variant", variant, "--output", str(output)],
        logs / "prepare.stdout",
        logs / "prepare.stderr",
        timeout=900,
    )
    if rc:
        raise AbortRun("workspace_prepare_failed", "Preparing the fresh neutral source snapshot failed.")
    if output.stat().st_uid != AGENT_UID:
        raise AbortRun("workspace_owner_mismatch", "The prepared workspace is not owned by runtime uid 1000.")
    commit = capture_text(["git", "-C", str(output), "rev-parse", "HEAD"], timeout=20)
    if len(commit) != 40:
        raise AbortRun("workspace_prepare_failed", "The prepared neutral commit could not be identified.")
    return commit


def make_baseline_repo(workspace: Path, metadata: Path, logs: Path) -> Path:
    baseline = metadata / "baseline.git"
    rc = capture(
        ["git", "clone", "--quiet", "--bare", str(workspace), str(baseline)],
        logs / "baseline-clone.stdout",
        logs / "baseline-clone.stderr",
        timeout=120,
    )
    if rc:
        raise AbortRun("baseline_snapshot_failed", "A private baseline repository could not be preserved.")
    return baseline


def capture_final_patch(
    workspace: Path, baseline_repo: Path, baseline_commit: str, session_dir: Path, logs: Path
) -> str:
    patch = session_dir / "final.patch"
    index = session_dir / "patch.index"
    env = sanitized_env()
    env.update({
        "GIT_DIR": str(baseline_repo),
        "GIT_WORK_TREE": str(workspace),
        "GIT_INDEX_FILE": str(index),
        "GIT_CONFIG_NOSYSTEM": "1",
    })
    for argv, stem in (
        (["git", "read-tree", baseline_commit], "patch-read-tree"),
        ([
            "git", "add", "-A", "--", ".",
            ":(exclude)node_modules/**", ":(exclude)**/node_modules/**",
            ":(exclude).git/**", ":(exclude)**/.git/**",
            ":(exclude)dist/**", ":(exclude)**/dist/**",
            ":(exclude)coverage/**", ":(exclude)**/coverage/**",
        ], "patch-stage"),
    ):
        rc = capture(argv, logs / f"{stem}.stdout", logs / f"{stem}.stderr", cwd=workspace, env=env, timeout=180)
        if rc:
            raise AbortRun("final_patch_capture_failed", "The final agent patch could not be captured.")
    with patch.open("wb") as stdout, (logs / "patch-export.stderr").open("wb") as stderr:
        os.chmod(patch, 0o600)
        rc = subprocess.run(
            ["git", "diff", "--cached", "--binary", "--full-index", baseline_commit],
            cwd=workspace,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            timeout=180,
            check=False,
        ).returncode
    if rc:
        raise AbortRun("final_patch_capture_failed", "The final agent patch could not be exported.")
    return sha256_file(patch)


def save_final_snapshot(workspace: Path, snapshot: Path, logs: Path) -> str:
    rc = capture(
        [
            "tar", "--create", "--gzip", "--file", str(snapshot), "--directory", str(workspace),
            "--exclude=.git", "--exclude=*/.git", "--exclude=node_modules", "--exclude=*/node_modules",
            "--exclude=dist", "--exclude=*/dist", "--exclude=coverage", "--exclude=*/coverage", ".",
        ],
        logs / "snapshot-archive.stdout",
        logs / "snapshot-archive.stderr",
        timeout=180,
    )
    if rc:
        raise AbortRun("final_snapshot_failed", "The private final source snapshot could not be preserved.")
    os.chmod(snapshot, 0o600)
    return sha256_file(snapshot)


def build_evaluation_workspace(
    baseline_repo: Path, baseline_commit: str, patch: Path, evaluation_workspace: Path,
    manifest: dict, logs: Path, deadline: float | None = None,
) -> None:
    check_deadline(deadline)
    evaluation_workspace.mkdir(mode=0o700)
    archive = logs / "evaluation-baseline.tar"
    with archive.open("wb") as stdout, (logs / "evaluation-archive.stderr").open("wb") as stderr:
        try:
            rc = subprocess.run(
                ["git", "--git-dir", str(baseline_repo), "archive", "--format=tar", baseline_commit],
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                timeout=bounded_timeout(deadline, 180),
                check=False,
            ).returncode
        except subprocess.TimeoutExpired as error:
            check_deadline(deadline)
            raise CommandTimeout from error
    if rc:
        raise AbortRun("evaluation_clone_failed", "Creating the fresh evaluator baseline failed.")
    try:
        with tarfile.open(archive, "r:") as source_tar:
            for member in source_tar:
                check_deadline(deadline)
                source_tar.extract(member, evaluation_workspace, filter="data")
        check_deadline(deadline)
    except (tarfile.TarError, OSError) as error:
        raise AbortRun("evaluation_clone_failed", "Extracting the neutral evaluator baseline failed.") from error
    init_rc = capture(
        ["git", "init", "--quiet", "--initial-branch=master"],
        logs / "evaluation-git-init.stdout",
        logs / "evaluation-git-init.stderr",
        cwd=evaluation_workspace,
        timeout=30,
        deadline=deadline,
    )
    if init_rc:
        raise AbortRun("evaluation_clone_failed", "Initializing the disposable evaluator source failed.")
    add_rc = capture(
        ["git", "add", "-A"],
        logs / "evaluation-git-add.stdout",
        logs / "evaluation-git-add.stderr",
        cwd=evaluation_workspace,
        timeout=120,
        deadline=deadline,
    )
    if add_rc:
        raise AbortRun("evaluation_clone_failed", "Staging the disposable evaluator baseline failed.")
    commit_env = sanitized_env()
    commit_env.update({"GIT_AUTHOR_DATE": "2026-10-12T00:00:00Z", "GIT_COMMITTER_DATE": "2026-10-12T00:00:00Z"})
    commit_rc = capture(
        ["git", "-c", "user.name=Benchmark", "-c", "user.email=benchmark@example.invalid", "commit", "--quiet", "-m", "Prepared neutral evaluation source"],
        logs / "evaluation-git-commit.stdout",
        logs / "evaluation-git-commit.stderr",
        cwd=evaluation_workspace,
        env=commit_env,
        timeout=60,
        deadline=deadline,
    )
    if commit_rc:
        raise AbortRun("evaluation_clone_failed", "Committing the disposable evaluator baseline failed.")
    if patch.stat().st_size:
        apply_rc = capture(
            ["git", "apply", "--binary", "--whitespace=nowarn", str(patch)],
            logs / "evaluation-patch.stdout",
            logs / "evaluation-patch.stderr",
            cwd=evaluation_workspace,
            timeout=120,
            deadline=deadline,
        )
        if apply_rc:
            raise AbortRun("evaluation_patch_apply_failed", "The captured final patch could not be applied to a fresh source clone.")
    # Check protected upstream files before extracting the cached dependencies. Otherwise
    # the cache could overwrite an agent edit and hide it from the protected-file gate.
    protected_rc = capture(
        [sys.executable, str(VERIFY), "--subject", str(evaluation_workspace)],
        logs / "protected-source-verify.stdout",
        logs / "protected-source-verify.stderr",
        timeout=60,
        deadline=deadline,
    )
    if protected_rc:
        raise AbortRun("protected_source_changed", "The final patch changed a protected upstream source or test file.")
    deps = ROOT / manifest["local_cache"][DEPENDENCY_NAME]["path"]
    try:
        with tarfile.open(deps, "r:gz") as dependency_tar:
            for member in dependency_tar:
                check_deadline(deadline)
                dependency_tar.extract(member, evaluation_workspace, filter="data")
        check_deadline(deadline)
    except (tarfile.TarError, OSError) as error:
        raise AbortRun("evaluation_dependencies_failed", "The frozen dependency cache could not be extracted.") from error
    if evaluation_workspace.stat().st_uid != AGENT_UID:
        raise AbortRun("evaluation_owner_mismatch", "The disposable evaluator source is not owned by runtime uid 1000.")
    archive.unlink(missing_ok=True)


def seed_counts_valid(project: str, env: dict[str, str]) -> bool:
    query = (
        "SELECT (SELECT count(*) FROM public.\"InfraConfig\")::text || '|' || "
        "(SELECT count(*) FROM public._prisma_migrations)::text || '|' || "
        "(SELECT count(*) FROM public.\"Team\")::text"
    )
    try:
        result = subprocess.run(
            compose_base(project) + [
                "exec", "--no-TTY", "database", "psql", "-X", "-A", "-t",
                "-v", "ON_ERROR_STOP=1", "-U", "benchmark", "-d", "benchmark", "-c", query,
            ],
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
            text=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.strip() == EXPECTED_SEED_COUNTS


def start_fresh_database(
    project: str, env: dict[str, str], manifest: dict, logs: Path,
    deadline: float | None = None,
) -> None:
    rc = capture(
        compose_base(project) + ["up", "--detach", "--pull", "never", "database"],
        logs / "database-up.stdout",
        logs / "database-up.stderr",
        env=env,
        timeout=DB_START_SECONDS,
        deadline=deadline,
    )
    if rc:
        raise AbortRun("database_start_failed", "A fresh private grading database could not be started.")
    wait_database_health(project, env, logs, deadline)
    wait_real_psql(project, env, logs, deadline)
    restore_seed(project, env, manifest, logs, deadline)


def inspect_result_container(name: str) -> dict | None:
    result = subprocess.run(
        ["docker", "inspect", name],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=15,
        check=False,
        text=True,
    )
    if result.returncode:
        return None
    try:
        return json.loads(result.stdout)[0]
    except (json.JSONDecodeError, IndexError, TypeError):
        return None


def run_grader_command(
    *,
    check_name: str,
    command: list[str],
    runtime_id: str,
    seccomp_path: Path,
    evaluation_workspace: Path,
    result_dir: Path,
    evaluator_path: Path,
    database_volume: str | None,
    logs: Path,
    deadline: float,
    workspace_readonly: bool,
) -> dict:
    if time.monotonic() >= deadline:
        return {
            "started": False, "exit_code": None, "timed_out": True,
            "infrastructure_error": False, "oom_killed": False, "budget_expired_before_start": True,
        }
    container = f"{check_name}-{uuid.uuid4().hex[:8]}"
    workspace_mount = f"type=bind,source={evaluation_workspace},target=/workspace"
    if workspace_readonly:
        workspace_mount += ",readonly"
    argv = [
        "docker", "run", "--name", container, "--pull=never", "--network=none",
        "--user", f"{AGENT_UID}:{AGENT_GID}", "--cpus=2", "--memory=4g", "--memory-swap=4g",
        "--pids-limit=256", "--cap-drop=ALL", "--security-opt", "no-new-privileges:true",
        "--security-opt", f"seccomp={seccomp_path}",
        "--mount", workspace_mount,
        "--workdir", "/workspace/packages/hoppscotch-backend",
        "--env-file", str(CONFIG / "agent-runtime.env"),
        "--env", "BENCHMARK_SUBJECT=/workspace/packages/hoppscotch-backend",
    ]
    if evaluator_path.exists():
        argv += ["--mount", f"type=bind,source={evaluator_path},target=/evaluator,readonly"]
    if database_volume:
        argv += ["--mount", f"type=volume,source={database_volume},target=/db-socket"]
    argv += [runtime_id, *command]
    stdout_path = logs / f"{check_name}.stdout"
    stderr_path = logs / f"{check_name}.stderr"
    try:
        rc = capture(
            argv,
            stdout_path,
            stderr_path,
            env=sanitized_env(),
            deadline=deadline,
        )
        timed_out = False
    except BudgetExpired:
        rc = 124
        timed_out = True
    state = inspect_result_container(container)
    if timed_out:
        state_data = (state or {}).get("State") or {}
        remove_container(container, logs)
        return {
            "started": bool(state),
            "exit_code": None,
            "timed_out": True,
            "infrastructure_error": False,
            "oom_killed": bool(state_data.get("OOMKilled")),
        }
    if state is None:
        remove_container(container, logs)
        return {"started": False, "exit_code": rc, "timed_out": False, "infrastructure_error": True, "oom_killed": False}
    status = state.get("State") or {}
    started = bool(status.get("StartedAt") and status.get("StartedAt") != "0001-01-01T00:00:00Z")
    oom_killed = bool(status.get("OOMKilled"))
    infra = not started or bool(status.get("Error"))
    result = {
        "started": started,
        "exit_code": status.get("ExitCode", rc),
        "timed_out": False,
        "infrastructure_error": infra,
        "oom_killed": oom_killed,
    }
    remove_container(container, logs)
    if check_name in {"oracle", "unit"} and not timed_out:
        persist_jest_report(stdout_path, result_dir / f"{check_name}.json")
    return result


def persist_jest_report(stdout_path: Path, report_path: Path) -> bool:
    """Copy only a complete JSON report; do not guess around stdout noise."""
    try:
        raw = stdout_path.read_bytes()
        report = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(report, dict) or not isinstance(report.get("testResults"), list):
        return False
    private_write(report_path, raw)
    return True


def parse_jest_report(path: Path, expected_total: int | None = None) -> dict:
    try:
        report = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"available": False}
    summary = {
        "available": True,
        "success": report.get("success") is True,
        "num_total_tests": report.get("numTotalTests"),
        "num_passed_tests": report.get("numPassedTests"),
        "num_failed_tests": report.get("numFailedTests"),
        "num_pending_tests": report.get("numPendingTests"),
    }
    if expected_total is not None:
        # Agents may add directly relevant tests. Preserve the frozen 761 upstream
        # tests while allowing additions; the report must still show no skipped tests.
        summary["minimum_expected_tests"] = expected_total
        summary["unit_gate_passed"] = (
            summary["success"]
            and isinstance(summary["num_total_tests"], int)
            and summary["num_total_tests"] >= expected_total
            and summary["num_failed_tests"] == 0
            and summary["num_pending_tests"] == 0
        )
    return summary


def grade_session(
    *,
    item: dict,
    run_id: str,
    session_dir: Path,
    evaluation_workspace: Path,
    manifest: dict,
    auth: Path,
    control: Path,
    output_root: Path,
    started_at: float,
) -> dict:
    budget = manifest["budgets"]["external_grading_seconds"]
    deadline = started_at + budget
    grade_dir = session_dir / "grading"
    grade_dir.mkdir(mode=0o700)
    reports = grade_dir / "reports"
    reports.mkdir(mode=0o700)
    write_json(grade_dir / "status.json", {"status": "grading", "started_at_utc": utc_now(), "budget_seconds": budget})

    # Verification is outside the task workspace and evaluates only this private clone.
    verify_out, verify_err = grade_dir / "verify.stdout", grade_dir / "verify.stderr"
    try:
        verify_rc = capture(
            [sys.executable, str(VERIFY), "--subject", str(evaluation_workspace)],
            verify_out,
            verify_err,
            timeout=60,
            deadline=deadline,
        )
    except BudgetExpired:
        result = {"status": "incomplete", "reason": "grading_budget_expired_during_hash_verification"}
        write_json(grade_dir / "status.json", result | {"finished_at_utc": utc_now()})
        return result
    except CommandTimeout:
        result = {"status": "infrastructure_abort", "reason": "protected_source_verification_timeout"}
        write_json(grade_dir / "status.json", result | {"finished_at_utc": utc_now()})
        return result
    verification = {"exit_code": verify_rc, "passed": verify_rc == 0}

    checks: dict[str, dict] = {}
    seccomp = (CONFIG / "seccomp.json").resolve()
    runtime_id = manifest["runtime"]["image_id"]
    evaluator_runtime = EVALUATOR.resolve()
    for label, command, report in (
        (
            "oracle",
            [
                "/workspace/packages/hoppscotch-backend/node_modules/.bin/jest",
                "--config", "/evaluator/jest.config.cjs", "--runInBand", "--json",
                "--coverage=false", "--cacheDirectory=/tmp/jest-cache",
                "--testNamePattern", f"^(RG|{item['task']}) ",
            ],
            "oracle.json",
        ),
        (
            "unit",
            [
                "/workspace/packages/hoppscotch-backend/node_modules/.bin/jest",
                "--runInBand", "--json", "--coverage=false", "--cacheDirectory=/tmp/jest-cache",
            ],
            "unit.json",
        ),
    ):
        if time.monotonic() >= deadline:
            result = {"status": "incomplete", "reason": "grading_budget_expired", "verification": verification, "checks": checks}
            write_json(grade_dir / "status.json", result | {"finished_at_utc": utc_now()})
            return result
        project = f"srp-g-{run_id[:7]}-{item['position']:02d}-{label}"
        project_env = compose_env(manifest, control, evaluation_workspace, auth)
        db_log = grade_dir / f"{label}-database"
        db_log.mkdir(mode=0o700)
        try:
            start_fresh_database(project, project_env, manifest, db_log, deadline)
        except BudgetExpired:
            try:
                cleanup_ok = compose_down(project, project_env, db_log)
            except Exception:
                cleanup_ok = False
            result = {
                "status": "incomplete" if cleanup_ok else "infrastructure_abort",
                "reason": "grading_budget_expired_during_database_setup" if cleanup_ok else "grader_database_cleanup_failed_after_budget_expiry",
                "verification": verification,
                "checks": checks,
                "database_cleanup_succeeded": cleanup_ok,
            }
            write_json(grade_dir / "status.json", result | {"finished_at_utc": utc_now()})
            return result
        except (AbortRun, CommandTimeout) as error:
            compose_down(project, project_env, db_log)
            result = {
                "status": "infrastructure_abort",
                "reason": error.code if isinstance(error, AbortRun) else "database_setup_timeout",
                "verification": verification,
                "checks": checks,
            }
            write_json(grade_dir / "status.json", result | {"finished_at_utc": utc_now()})
            return result
        except Exception:
            compose_down(project, project_env, db_log)
            raise
        volume = f"{project}_database-socket"
        cleanup_ok = False
        try:
            outcome = run_grader_command(
                check_name=label,
                command=command,
                runtime_id=runtime_id,
                seccomp_path=seccomp,
                evaluation_workspace=evaluation_workspace,
                result_dir=reports,
                evaluator_path=evaluator_runtime if label == "oracle" else Path("/__no_evaluator__"),
                database_volume=volume,
                logs=grade_dir,
                deadline=deadline,
                workspace_readonly=True,
            )
        finally:
            try:
                cleanup_ok = compose_down(project, project_env, db_log)
            except Exception:
                cleanup_ok = False
        checks[label] = {
            **outcome,
            "report": parse_jest_report(
                reports / report,
                761 if label == "unit" else None,
            ),
        }
        if not cleanup_ok:
            result = {
                "status": "infrastructure_abort",
                "reason": "grader_database_cleanup_failed",
                "verification": verification,
                "checks": checks,
            }
            write_json(grade_dir / "status.json", result | {"finished_at_utc": utc_now()})
            return result
        if outcome.get("oom_killed"):
            result = {
                "status": "halt_for_review",
                "reason": f"{label}_grader_oom_killed",
                "verification": verification,
                "checks": checks,
            }
            write_json(grade_dir / "status.json", result | {"finished_at_utc": utc_now()})
            return result
        if outcome["infrastructure_error"]:
            result = {
                "status": "infrastructure_abort",
                "reason": f"{label}_container_failed_to_run",
                "verification": verification,
                "checks": checks,
            }
            write_json(grade_dir / "status.json", result | {"finished_at_utc": utc_now()})
            return result
        if outcome["timed_out"]:
            result = {
                "status": "incomplete",
                "reason": f"grading_budget_expired_during_{label}",
                "verification": verification,
                "checks": checks,
            }
            write_json(grade_dir / "status.json", result | {"finished_at_utc": utc_now()})
            return result
    # Reserve time inside the shared budget for the protected-source check after
    # this writable build. Tests above mount the candidate source read-only.
    build_deadline = deadline - POST_BUILD_VERIFY_RESERVE_SECONDS
    if time.monotonic() >= build_deadline:
        result = {"status": "incomplete", "reason": "grading_budget_expired_before_build", "verification": verification, "checks": checks}
        write_json(grade_dir / "status.json", result | {"finished_at_utc": utc_now()})
        return result
    build = run_grader_command(
        check_name="build",
        command=["pnpm", "run", "build"],
        runtime_id=runtime_id,
        seccomp_path=seccomp,
        evaluation_workspace=evaluation_workspace,
        result_dir=reports,
        evaluator_path=Path("/__no_evaluator__"),
        database_volume=None,
        logs=grade_dir,
        deadline=build_deadline,
        workspace_readonly=False,
    )
    checks["build"] = build
    post_verify_out = grade_dir / "post-build-verify.stdout"
    post_verify_err = grade_dir / "post-build-verify.stderr"
    try:
        post_verify_rc = capture(
            [sys.executable, str(VERIFY), "--subject", str(evaluation_workspace)],
            post_verify_out,
            post_verify_err,
            timeout=60,
            deadline=deadline,
        )
    except BudgetExpired:
        result = {
            "status": "incomplete",
            "reason": "grading_budget_expired_during_post_build_hash_verification",
            "verification": verification,
            "checks": checks,
        }
        write_json(grade_dir / "status.json", result | {"finished_at_utc": utc_now()})
        return result
    except CommandTimeout:
        result = {
            "status": "infrastructure_abort",
            "reason": "post_build_hash_verification_timeout",
            "verification": verification,
            "checks": checks,
        }
        write_json(grade_dir / "status.json", result | {"finished_at_utc": utc_now()})
        return result
    checks["post_build_verification"] = {"exit_code": post_verify_rc, "passed": post_verify_rc == 0}
    if post_verify_rc:
        result = {
            "status": "halt_for_review",
            "reason": "protected_source_changed_during_build",
            "verification": verification,
            "checks": checks,
        }
        write_json(grade_dir / "status.json", result | {"finished_at_utc": utc_now()})
        return result
    if build["infrastructure_error"]:
        result = {
            "status": "infrastructure_abort",
            "reason": "build_container_failed_to_run",
            "verification": verification,
            "checks": checks,
        }
        write_json(grade_dir / "status.json", result | {"finished_at_utc": utc_now()})
        return result
    if build.get("oom_killed"):
        result = {
            "status": "halt_for_review",
            "reason": "build_grader_oom_killed",
            "verification": verification,
            "checks": checks,
        }
        write_json(grade_dir / "status.json", result | {"finished_at_utc": utc_now()})
        return result
    if build["timed_out"]:
        result = {
            "status": "incomplete",
            "reason": "build_exceeded_reserved_window_for_post_build_verification",
            "verification": verification,
            "checks": checks,
        }
        write_json(grade_dir / "status.json", result | {"finished_at_utc": utc_now()})
        return result

    telemetry_path = control / "events.jsonl"
    telemetry = {}
    if telemetry_path.is_file():
        try:
            check_deadline(deadline)
            rc = capture(
                [sys.executable, str(TELEMETRY), str(telemetry_path)],
                grade_dir / "telemetry.stdout",
                grade_dir / "telemetry.stderr",
                timeout=30,
                deadline=deadline,
            )
            if rc == 0:
                telemetry = load_json(grade_dir / "telemetry.stdout")
        except BudgetExpired:
            result = {
                "status": "incomplete",
                "reason": "grading_budget_expired_during_telemetry_summary",
                "verification": verification,
                "checks": checks,
            }
            write_json(grade_dir / "status.json", result | {"finished_at_utc": utc_now()})
            return result
        except (AbortRun, CommandTimeout):
            telemetry = {"available": False}
    result = {
        "status": "graded",
        "verification": verification,
        "checks": checks,
        "telemetry": telemetry,
        "finished_at_utc": utc_now(),
        "elapsed_seconds": round(time.monotonic() - started_at, 3),
        "budget_seconds": budget,
    }
    write_json(grade_dir / "status.json", result)
    return result


def review_provenance(manifest: dict) -> dict:
    # verify_frozen_artifacts() ran immediately before this call. Reuse its
    # checked digests so large cache archives are not read a third time.
    files = dict(manifest.get("artifact_sha256", {}))
    for spec in manifest.get("local_cache", {}).values():
        files[spec["path"]] = spec["sha256"]
    for rel in PREFLIGHT_FILES:
        path = ROOT / rel
        if rel not in files:
            files[rel] = sha256_file(path) if path.is_file() else None
    try:
        head = capture_text(["git", "-C", str(ROOT), "rev-parse", "HEAD"], timeout=15)
        status = capture_text(["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=all"], timeout=15)
        dirty_count = len([line for line in status.splitlines() if line.strip()])
    except AbortRun:
        head, dirty_count = None, None
    return {
        "created_at_utc": utc_now(),
        "script_path": str(Path(__file__).resolve()),
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "repository_head": head,
        "repository_status_entry_count": dirty_count,
        "input_sha256": files,
        "frozen_input_hashes_verified": True,
    }


def validate_preflight(args, manifest: dict, schedule: dict) -> tuple[Path, Path, Path, str, str]:
    if manifest.get("benchmark_execution_authorized") is not True:
        raise AbortRun("execution_not_authorized", "The frozen manifest does not authorize measured execution.")
    if os.getuid() != AGENT_UID or AGENT_GID not in os.getgroups() + [os.getgid()]:
        raise AbortRun("host_owner_mismatch", "Run this script as the host uid/gid 1000 used by the frozen runtime.")
    output = validate_root_output(args.root_output)
    auth = validate_auth_file(args.auth_file)
    codex_hash = validate_code_mode_config(manifest)
    attestation, attestation_hash = validate_attestation(args.prelaunch_attestation, codex_hash, manifest)
    expected_review = args.reviewed_script_sha256.lower().removeprefix("sha256:")
    actual_review = sha256_file(Path(__file__).resolve())
    if len(expected_review) != 64 or not secrets.compare_digest(expected_review, actual_review):
        raise AbortRun("runner_review_hash_mismatch", "The reviewed runner SHA-256 does not match this file.")
    if not Path("/usr/bin/docker").exists() and shutil.which("docker") is None:
        raise AbortRun("docker_unavailable", "Docker is required for isolated sessions.")
    if not Path("/usr/bin/git").exists() and shutil.which("git") is None:
        raise AbortRun("git_unavailable", "Git is required for source snapshots and patch capture.")
    return output, auth, attestation, codex_hash, attestation_hash


def create_run_root(path: Path) -> None:
    try:
        path.mkdir(mode=0o700)
    except FileExistsError as error:
        raise AbortRun("unsafe_output_path", "The output directory must be new; this runner never resumes.") from error
    os.chmod(path, 0o700)
    if path.stat().st_uid != os.getuid():
        raise AbortRun("output_owner_mismatch", "The private output directory has an unexpected owner.")


def compose_preflight(project: str, env: dict[str, str], logs: Path) -> None:
    rc = capture(
        compose_base(project) + ["config", "--quiet"],
        logs / "compose-config.stdout",
        logs / "compose-config.stderr",
        env=env,
        timeout=30,
    )
    if rc:
        raise AbortRun("compose_config_invalid", "The frozen Compose configuration did not validate.")


def ensure_gateway_and_database(
    project: str, env: dict[str, str], manifest: dict, logs: Path
) -> None:
    rc = capture(
        compose_base(project) + ["up", "--detach", "--pull", "never", "database", "model-gateway"],
        logs / "compose-up.stdout",
        logs / "compose-up.stderr",
        env=env,
        timeout=DB_START_SECONDS,
    )
    if rc:
        raise AbortRun("compose_start_failed", "The session's isolated PostgreSQL and gateway services did not start.")
    wait_database_health(project, env, logs)
    wait_real_psql(project, env, logs)
    restore_seed(project, env, manifest, logs)
    wait_gateway(project, env, logs)


def launch_agent(
    project: str, container: str, env: dict[str, str], logs: Path
) -> None:
    rc = capture(
        compose_base(project) + [
            "run", "--detach", "--no-deps", "--name", container, "agent",
            "node", "/control/session-driver.cjs", "--execute-approved-session",
        ],
        logs / "agent-launch.stdout",
        logs / "agent-launch.stderr",
        env=env,
        timeout=60,
    )
    if rc or read_container_state(container) is None:
        raise AbortRun("agent_launcher_failed", "The explicit approved-session driver could not be launched.")


def wait_agent(container: str, manifest: dict, logs: Path) -> tuple[dict, int]:
    budget = manifest["budgets"]["agent_seconds"] + manifest["budgets"]["termination_grace_seconds"] + AGENT_HOST_GRACE_SECONDS
    deadline = time.monotonic() + budget
    while time.monotonic() < deadline:
        state = read_container_state(container)
        if state is None:
            raise AbortRun("agent_container_missing", "The session container disappeared before it stopped.")
        if state.get("Status") not in {"running", "created", "restarting"}:
            result = inspect_result_container(container)
            if result is None:
                raise AbortRun("agent_container_missing", "The stopped session container could not be inspected.")
            return result.get("State") or {}, int((result.get("State") or {}).get("ExitCode", 1))
        time.sleep(2)
    remove_container(container, logs)
    raise AbortRun("agent_host_timeout", "The session driver exceeded its host-side safety bound.")


def read_termination(control: Path) -> dict:
    path = control / "termination.json"
    if not path.is_file():
        raise AbortRun("driver_termination_missing", "The session driver did not record a complete termination result.")
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise AbortRun("driver_termination_invalid", "The session termination record is invalid.") from error
    if not isinstance(value, dict) or value.get("outcome") == "launcher-failure":
        raise AbortRun("driver_launcher_failure", "The Codex CLI launcher failed before a session completed.")
    return value


def validate_trace(control: Path) -> dict:
    events = control / "events.jsonl"
    if not events.is_file() or events.stat().st_size == 0:
        return {"available": False, "reason": "missing_or_empty"}
    starts = 0
    provider_or_cli_errors = 0
    try:
        with events.open() as handle:
            for line in handle:
                if not line.strip():
                    continue
                event = json.loads(line)
                kind = event.get("type")
                if kind == "turn.started":
                    starts += 1
                if kind in {"turn.failed", "response.failed", "error"}:
                    provider_or_cli_errors += 1
    except (OSError, json.JSONDecodeError) as error:
        return {
            "available": False,
            "reason": "invalid_json_or_unreadable",
            "bytes": events.stat().st_size,
            "sha256": sha256_file(events),
        }
    return {
        "available": True,
        "has_started_turn": starts > 0,
        "turns_started": starts,
        "provider_or_cli_error_events": provider_or_cli_errors,
        "bytes": events.stat().st_size,
        "sha256": sha256_file(events),
    }


def harvest_agent_logs(container: str, session_dir: Path, logs: Path) -> None:
    capture(
        ["docker", "logs", "--timestamps", container],
        session_dir / "agent-container.stdout",
        session_dir / "agent-container.stderr",
        timeout=30,
    )
    # The driver's raw events and stderr already live in the private control directory.
    if not (session_dir / "control" / "stderr.log").exists():
        private_write(session_dir / "control" / "stderr.log", b"")


def remove_driver_token(control: Path) -> None:
    token = control / "driver-token"
    try:
        token.unlink()
    except FileNotFoundError:
        pass


def grade_and_record(
    item: dict, run_id: str, session_dir: Path, workspace: Path, manifest: dict,
    auth: Path, control: Path, grade_started: float,
) -> dict:
    clone = session_dir / "evaluation-source"
    baseline = session_dir / "baseline.git"
    patch = session_dir / "final.patch"
    baseline_commit = load_json(session_dir / "session.json")["baseline_commit"]
    grade_log = session_dir / "grading-preparation"
    grade_log.mkdir(mode=0o700)
    deadline = grade_started + manifest["budgets"]["external_grading_seconds"]
    try:
        build_evaluation_workspace(baseline, baseline_commit, patch, clone, manifest, grade_log, deadline)
        patch_hash = sha256_file(patch, deadline)
        snapshot_hash = sha256_file(session_dir / "final-source.tar.gz", deadline)
    except BudgetExpired:
        result = {"status": "incomplete", "reason": "grading_budget_expired_during_preparation"}
        grade_dir = session_dir / "grading"
        grade_dir.mkdir(mode=0o700, exist_ok=True)
        write_json(grade_dir / "status.json", result | {"finished_at_utc": utc_now()})
        return result
    except CommandTimeout:
        result = {"status": "infrastructure_abort", "reason": "grading_preparation_command_timeout"}
        grade_dir = session_dir / "grading"
        grade_dir.mkdir(mode=0o700, exist_ok=True)
        write_json(grade_dir / "status.json", result | {"finished_at_utc": utc_now()})
        return result
    write_json(session_dir / "artifacts.json", {
        "final_patch_sha256": patch_hash,
        "final_patch_bytes": patch.stat().st_size,
        "final_source_snapshot_sha256": snapshot_hash,
        "final_source_snapshot": "final-source.tar.gz",
        "evaluation_source": "fresh git-archive baseline + final.patch + frozen dependency cache",
    })
    # The prepared agent workspace and baseline are removed by run_one's finally
    # block, outside the timed grading interval.
    return grade_session(
        item=item,
        run_id=run_id,
        session_dir=session_dir,
        evaluation_workspace=clone,
        manifest=manifest,
        auth=auth,
        control=control,
        output_root=session_dir.parent.parent,
        started_at=grade_started,
    )


def new_project_name(run_id: str, position: int, purpose: str = "s") -> str:
    return f"srp-{run_id[:7]}-{purpose}-{position:02d}-{uuid.uuid4().hex[:4]}"


def run_one(
    item: dict,
    *,
    run_id: str,
    run_root: Path,
    manifest: dict,
    auth: Path,
    global_started: float,
) -> dict:
    name = item["id"]
    session_dir = run_root / "sessions" / f"{item['position']:02d}-{name}"
    session_dir.mkdir(mode=0o700)
    control = session_dir / "control"
    logs = session_dir / "infrastructure"
    workspace = session_dir / "workspace"
    control.mkdir(mode=0o700)
    logs.mkdir(mode=0o700)
    patch = session_dir / "final.patch"
    private_write(patch, b"")
    project = new_project_name(run_id, item["position"])
    agent_container = f"{project}-agent"
    env = compose_env(manifest, control, workspace, auth)
    baseline_repo = None
    baseline_commit = None
    agent_launched = False
    final_saved = False
    session_started_at = utc_now()
    append_jsonl(run_root / "outcomes.jsonl", {
        "at_utc": session_started_at, "position": item["position"], "session": name, "state": "staging",
    })
    write_json(session_dir / "session.json", {
        "session": name,
        "position": item["position"],
        "task": item["task"],
        "repetition": item["repetition"],
        "variant": item["variant"],
        "compose_project": project,
        "runtime_image_id": manifest["runtime"]["image_id"],
        "started_at_utc": session_started_at,
    })
    result = None
    error: AbortRun | None = None
    try:
        baseline_commit = prepare_workspace(item["variant"], workspace, logs)
        baseline_repo = make_baseline_repo(workspace, session_dir, logs)
        session_meta = load_json(session_dir / "session.json")
        session_meta["baseline_commit"] = baseline_commit
        session_meta["baseline_tree"] = manifest["source_trees"][item["variant"]]
        write_json(session_dir / "session.json", session_meta)
        task_prompt = (SRP / "prompts" / f"{item['task']}.txt").read_bytes()
        private_write(control / "task.txt", task_prompt, 0o400)
        private_write(control / "session-driver.cjs", DRIVER.read_bytes(), 0o400)
        token = secrets.token_urlsafe(48).encode() + b"\n"
        private_write(control / "driver-token", token, 0o400)
        metadata = {
            "task_sha256": sha256_file(SRP / "prompts" / f"{item['task']}.txt"),
            "driver_sha256": sha256_file(DRIVER),
            "driver_token_bytes": len(token.rstrip()),
            "driver_token_retained": False,
            "baseline_commit": baseline_commit,
            "baseline_tree": manifest["source_trees"][item["variant"]],
        }
        write_json(session_dir / "inputs.json", metadata)
        verify_log = logs / "staged-subject-verify"
        rc = capture(
            [sys.executable, str(VERIFY), "--subject", str(workspace)],
            verify_log.with_suffix(".stdout"),
            verify_log.with_suffix(".stderr"),
            timeout=60,
        )
        if rc:
            raise AbortRun("staged_subject_hash_mismatch", "The freshly staged source failed protected-input verification.")
        compose_preflight(project, env, logs)
        ensure_gateway_and_database(project, env, manifest, logs)
        agent_started = time.monotonic()
        launch_agent(project, agent_container, env, logs)
        agent_launched = True
        write_json(session_dir / "session.json", load_json(session_dir / "session.json") | {"agent_started_at_utc": utc_now()})
        append_jsonl(run_root / "outcomes.jsonl", {
            "at_utc": utc_now(), "position": item["position"], "session": name, "state": "agent_started",
        })
        state, exit_code = wait_agent(agent_container, manifest, logs)
        termination = read_termination(control)
        harvest_agent_logs(agent_container, session_dir, logs)
        trace_summary = validate_trace(control)
        termination["container_exit_code"] = exit_code
        termination["container_oom_killed"] = bool(state.get("OOMKilled"))
        write_json(session_dir / "termination.json", termination)
        write_json(session_dir / "trace-summary.json", trace_summary)
        remove_driver_token(control)
        patch_hash = capture_final_patch(workspace, baseline_repo, baseline_commit, session_dir, logs)
        snapshot_hash = save_final_snapshot(workspace, session_dir / "final-source.tar.gz", logs)
        final_saved = True
        write_json(session_dir / "artifacts.json", {
            "final_patch_sha256": patch_hash,
            "final_patch_bytes": patch.stat().st_size,
            "final_source_snapshot_sha256": snapshot_hash,
            "final_source_snapshot": "final-source.tar.gz",
        })
        append_jsonl(run_root / "outcomes.jsonl", {
            "at_utc": utc_now(), "position": item["position"], "session": name,
            "state": "agent_stopped_and_patch_saved",
            "agent_exit_code": exit_code,
            "timed_out": bool(termination.get("timed_out")),
            "patch_sha256": patch_hash,
        })
        grade_started = time.monotonic()
        result = grade_and_record(
            item, run_id, session_dir, workspace, manifest, auth, control, grade_started
        )
        if result.get("status") == "infrastructure_abort":
            raise AbortRun("grading_infrastructure_failure", "External grading failed to start or its isolated database failed.")
        if result.get("status") == "incomplete":
            raise AbortRun("grading_incomplete", "External grading exceeded its cap or did not finish all required checks.")
        if result.get("status") == "halt_for_review":
            reason_code = str(result.get("reason") or "grading_halt_for_review")
            raise AbortRun(reason_code, "External grading flagged this result for review; the schedule stopped.")
        if state.get("OOMKilled"):
            raise AbortRun("agent_oom_killed", "The agent container exceeded the frozen memory limit after its patch was graded.")
        if exit_code != 0:
            raise AbortRun("agent_exit_nonzero", "The agent CLI exited unexpectedly after its final patch was graded.")
        if trace_summary.get("provider_or_cli_error_events", 0):
            raise AbortRun("provider_or_cli_error", "The final patch was graded, but the trace contains provider or CLI error events.")
        if not trace_summary.get("available") or not trace_summary.get("has_started_turn"):
            raise AbortRun("session_trace_unverified", "The final patch was graded, but its CLI trace could not be verified.")
    except AbortRun as caught:
        error = caught
    except KeyboardInterrupt:
        error = AbortRun("interrupted", "The orchestration was interrupted; no later session will start.")
    except Exception as caught:
        # Keep unexpected exception details out of the terminal and private records.
        write_json(session_dir / "unexpected-error.json", {"type": type(caught).__name__, "at_utc": utc_now()})
        error = AbortRun("orchestration_error", "The orchestration encountered an unexpected local error.")
    finally:
        remove_driver_token(control)
        if not final_saved and workspace.exists():
            try:
                if baseline_repo and baseline_commit:
                    patch_hash = capture_final_patch(workspace, baseline_repo, baseline_commit, session_dir, logs)
                    snapshot_hash = save_final_snapshot(workspace, session_dir / "final-source.tar.gz", logs)
                    final_saved = True
                    write_json(session_dir / "artifacts.json", {
                        "final_patch_sha256": patch_hash,
                        "final_patch_bytes": patch.stat().st_size,
                        "final_source_snapshot_sha256": snapshot_hash,
                        "final_source_snapshot": "final-source.tar.gz",
                        "graded": False,
                    })
            except Exception:
                write_json(session_dir / "artifact-capture-error.json", {"at_utc": utc_now()})
        if agent_launched:
            remove_container(agent_container, logs)
        cleaned = compose_down(project, env, logs)
        if not cleaned and error is None:
            error = AbortRun("session_cleanup_failed", "The session's own Compose project did not clean up.")
        if baseline_repo:
            shutil.rmtree(baseline_repo, ignore_errors=True)
        if workspace.exists():
            shutil.rmtree(workspace, ignore_errors=True)
        evaluation_workspace = session_dir / "evaluation-source"
        if error is not None and evaluation_workspace.exists():
            # Partial evaluator clones are evidence only when a complete patch/result record exists.
            shutil.rmtree(evaluation_workspace, ignore_errors=True)
    if error is not None:
        append_jsonl(run_root / "outcomes.jsonl", {
            "at_utc": utc_now(), "position": item["position"], "session": name,
            "state": "aborted_for_review", "reason_code": error.code,
        })
        raise error
    outcome = {
        "session": name,
        "position": item["position"],
        "state": "graded",
        "agent_exit_code": load_json(session_dir / "termination.json").get("container_exit_code"),
        "timed_out": load_json(session_dir / "termination.json").get("timed_out") is True,
        "grading": result,
        "final_patch": str((session_dir / "final.patch").relative_to(run_root)),
    }
    append_jsonl(run_root / "outcomes.jsonl", {"at_utc": utc_now(), **outcome})
    return outcome


def parse_args():
    parser = argparse.ArgumentParser(description="Fail-closed serial runner for the frozen 30-session SRP schedule.")
    parser.add_argument("--execute-approved-schedule", action="store_true", help="Required to run any measured session.")
    parser.add_argument("--auth-file", help="Existing private Codex/OpenAI auth JSON; only mounted into the isolated gateway.")
    parser.add_argument("--root-output", help="New ignored output directory under repository work/. This runner never resumes.")
    parser.add_argument("--prelaunch-attestation", default=str(READINESS), help="Frozen non-benchmark readiness report.")
    parser.add_argument("--reviewed-script-sha256", help="SHA-256 reviewed by the operator before execution.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_json(MANIFEST_PATH)
    schedule = load_json(SCHEDULE_PATH)
    sessions = validate_schedule(schedule, manifest)
    if not args.execute_approved_schedule:
        print(f"Execution disabled. Frozen schedule has {len(sessions)} sessions; no services were started.")
        return 0
    missing = [
        name for name in ("auth_file", "root_output", "reviewed_script_sha256")
        if not getattr(args, name)
    ]
    if missing:
        print("Execution blocked: auth, new work output, prelaunch attestation, and reviewed script hash are required.")
        return 2
    try:
        output, auth, attestation, codex_hash, attestation_hash = validate_preflight(args, manifest, schedule)
        # Record frozen input hashes and the reviewed runner digest before any container is launched.
        create_run_root(output)
        for folder in ("sessions", "preflight"):
            (output / folder).mkdir(mode=0o700)
        verify_frozen_artifacts(manifest, output / "preflight")
        verify_local_images(manifest, output / "preflight")
        provenance = review_provenance(manifest)
        provenance.update({
            "reviewed_script_sha256": sha256_file(Path(__file__).resolve()),
            "codex_config_sha256": codex_hash,
            "prelaunch_attestation_sha256": attestation_hash,
            "prelaunch_attestation_path": str(attestation),
            "schedule_sha256": sha256_file(SCHEDULE_PATH),
            "manifest_sha256": sha256_file(MANIFEST_PATH),
            "runtime_image_id": manifest["runtime"]["image_id"],
            "postgres_image": manifest["runtime"]["postgres_image"],
            "session_order": [item["id"] for item in sessions],
            "execution_authorized_by": "explicit --execute-approved-schedule invocation",
        })
        write_json(output / "provenance.json", provenance)
        run_id = uuid.uuid4().hex
        started_at = utc_now()
        summary = {
            "run_id": run_id,
            "status": "running",
            "started_at_utc": started_at,
            "planned_sessions": 30,
            "completed_sessions": 0,
            "aborted_at_position": None,
            "reason_code": None,
            "provenance_sha256": sha256_file(output / "provenance.json"),
            "runner_sha256": provenance["reviewed_script_sha256"],
        }
        write_json(output / "summary.json", summary)
        print(f"Execution provenance recorded before launch: {provenance['reviewed_script_sha256']}")
        for item in sessions:
            print(f"Starting frozen session {item['position']}/30: {item['id']}")
            try:
                run_one(item, run_id=run_id, run_root=output, manifest=manifest, auth=auth, global_started=time.monotonic())
            except AbortRun as error:
                summary.update({
                    "status": "aborted_for_review",
                    "aborted_at_position": item["position"],
                    "reason_code": error.code,
                    "finished_at_utc": utc_now(),
                })
                write_json(output / "summary.json", summary)
                print(f"Schedule stopped at {item['id']}: {error.message}")
                return 1
            summary["completed_sessions"] += 1
            write_json(output / "summary.json", summary)
            print(f"Completed frozen session {item['position']}/30: {item['id']}")
        summary.update({"status": "complete", "finished_at_utc": utc_now()})
        write_json(output / "summary.json", summary)
        print("All 30 scheduled sessions completed.")
        return 0
    except AbortRun as error:
        print(f"Execution blocked ({error.code}): {error.message}")
        return 2
    except KeyboardInterrupt:
        print("Execution interrupted; no automatic resume or replacement session will occur.")
        return 130
    except Exception as error:
        print(f"Execution stopped ({type(error).__name__}); private output is incomplete and requires review.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
