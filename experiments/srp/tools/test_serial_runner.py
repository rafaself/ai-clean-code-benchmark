"""Regression fixtures for serial-runner artifact and integrity handling."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock


RUNNER_PATH = Path(__file__).with_name("serial-runner.py")
SPEC = importlib.util.spec_from_file_location("srp_serial_runner_under_test", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


class SerialRunnerRegressionTests(unittest.TestCase):
    def git(self, *args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            env.pop(key, None)
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
        )

    def init_git_repo(self, path: Path) -> str:
        path.mkdir(parents=True)
        self.git("init", "-q", cwd=path)
        self.git("config", "user.name", "Runner fixture", cwd=path)
        self.git("config", "user.email", "runner-fixture@example.invalid", cwd=path)
        return self.git("rev-parse", "--show-toplevel", cwd=path).stdout.strip()

    def test_patch_capture_excludes_ignored_dependencies_and_applies_agent_changes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="srp-capture-test-") as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            self.init_git_repo(workspace)
            (workspace / ".gitignore").write_text(
                "node_modules/\n**/node_modules/\ndist/\n**/dist/\ncoverage/\n**/coverage/\n"
            )
            (workspace / "tracked.txt").write_text("baseline\n")
            self.git("add", "-A", cwd=workspace)
            self.git("commit", "-qm", "baseline", cwd=workspace)
            baseline_commit = self.git("rev-parse", "HEAD", cwd=workspace).stdout.strip()

            baseline_repo = root / "baseline.git"
            self.git("clone", "--quiet", "--bare", str(workspace), str(baseline_repo), cwd=root)
            (workspace / "tracked.txt").write_text("agent edit\n")
            (workspace / "new-source.txt").write_text("agent addition\n")
            self.git("add", "-A", cwd=workspace)
            self.git("commit", "-qm", "agent commit", cwd=workspace)

            ignored_paths = (
                "node_modules/root-package/index.js",
                "packages/api/node_modules/nested-package/index.js",
                "dist/generated.js",
                "packages/api/coverage/generated.js",
            )
            for relative in ignored_paths:
                path = workspace / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("must not enter the patch\n")

            session = root / "session"
            logs = root / "logs"
            session.mkdir()
            logs.mkdir()
            runner.capture_final_patch(workspace, baseline_repo, baseline_commit, session, logs)
            patch = session / "final.patch"

            pristine = root / "pristine"
            self.git("clone", "--quiet", str(baseline_repo), str(pristine), cwd=root)
            self.git("apply", "--check", str(patch), cwd=pristine)
            self.git("apply", str(patch), cwd=pristine)

            self.assertEqual((pristine / "tracked.txt").read_text(), "agent edit\n")
            self.assertEqual((pristine / "new-source.txt").read_text(), "agent addition\n")
            for relative in ignored_paths:
                self.assertFalse((pristine / relative).exists(), relative)
            patch_bytes = patch.read_bytes()
            for excluded in (b"node_modules/", b"dist/", b"coverage/"):
                self.assertNotIn(excluded, patch_bytes)

    def test_capture_failure_retains_workspace_baseline_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory(prefix="srp-retention-test-") as temporary:
            root = Path(temporary)
            run_root = root / "run"
            (run_root / "sessions").mkdir(parents=True)
            auth = root / "auth.json"
            auth.write_text("{}")
            auth.chmod(0o600)

            def prepare_workspace(_variant: str, output: Path, _logs: Path) -> str:
                self.init_git_repo(output)
                (output / ".gitignore").write_text("node_modules/\n**/node_modules/\n")
                (output / "source.txt").write_text("preserve this source\n")
                self.git("add", "-A", cwd=output)
                self.git("commit", "-qm", "baseline", cwd=output)
                return self.git("rev-parse", "HEAD", cwd=output).stdout.strip()

            failed_capture = runner.AbortRun("final_patch_capture_failed", "injected fixture failure")
            real_capture = runner.capture

            def capture_side_effect(argv, stdout_path, stderr_path, **kwargs):
                if "--subject" in argv and str(runner.VERIFY) in argv:
                    stdout_path.parent.mkdir(parents=True, exist_ok=True)
                    stdout_path.write_text("fixture verification pass\n")
                    stderr_path.write_text("")
                    return 0
                return real_capture(argv, stdout_path, stderr_path, **kwargs)

            with mock.patch.object(runner, "capture_final_patch", side_effect=failed_capture) as patch_capture:
                with mock.patch.object(runner, "capture", side_effect=capture_side_effect), \
                     mock.patch.object(runner, "prepare_workspace", side_effect=prepare_workspace), \
                     mock.patch.object(runner, "compose_env", return_value={}), \
                     mock.patch.object(runner, "compose_preflight"), \
                     mock.patch.object(runner, "ensure_gateway_and_database"), \
                     mock.patch.object(runner, "launch_agent"), \
                     mock.patch.object(runner, "wait_agent", return_value=({"OOMKilled": False}, 0)), \
                     mock.patch.object(runner, "read_termination", return_value={"outcome": "completed"}), \
                     mock.patch.object(runner, "harvest_agent_logs"), \
                     mock.patch.object(runner, "validate_trace", return_value={"available": True, "has_started_turn": True, "provider_or_cli_error_events": 0}), \
                     mock.patch.object(runner, "compose_down", return_value=True), \
                     mock.patch.object(runner, "remove_container"), \
                     mock.patch.object(runner, "grade_and_record", side_effect=AssertionError("grader must not start")):
                    with self.assertRaises(runner.AbortRun) as caught:
                        runner.run_one(
                            {"id": "fixture", "position": 1, "task": "T01", "repetition": 1, "variant": "A"},
                            run_id="fixture-run",
                            run_root=run_root,
                            manifest={"runtime": {"image_id": "sha256:fixture"}, "source_trees": {"A": "fixture-tree"}, "budgets": {}},
                            auth=auth,
                            global_started=0,
                        )

            self.assertEqual(caught.exception.code, "final_patch_capture_failed")
            self.assertEqual(patch_capture.call_count, 2, "primary and fallback capture were attempted")
            session = run_root / "sessions" / "01-fixture"
            self.assertEqual((session / "workspace" / "source.txt").read_text(), "preserve this source\n")
            self.assertTrue((session / "baseline.git").is_dir())
            snapshot = session / "final-source.tar.gz"
            self.assertTrue(snapshot.is_file())
            with tarfile.open(snapshot, "r:gz") as source:
                self.assertEqual(source.extractfile("./source.txt").read(), b"preserve this source\n")
            record = runner.load_json(session / "artifact-capture-error.json")
            self.assertEqual(record["attempt"], "fallback")
            self.assertTrue(record["source_preserved"])
            self.assertTrue(record["snapshot_present"])

    def test_protected_patch_is_unsuccessful_and_does_not_stop_next_session(self) -> None:
        with tempfile.TemporaryDirectory(prefix="srp-integrity-test-") as temporary:
            root = Path(temporary)
            protected_name = "src/protected.spec.js"
            baseline_text = "frozen protected test\n"
            instruction_text = "fixture instructions\n"
            verify_root = root / "verification-root"
            verify_path = verify_root / "experiments/srp/tools/verify.py"
            verify_path.parent.mkdir(parents=True)
            shutil.copy2(runner.ROOT / "experiments/srp/tools/verify.py", verify_path)
            manifest_path = verify_root / "experiments/srp/config/execution-manifest.json"
            manifest_path.parent.mkdir(parents=True)
            verification_manifest = {
                "artifact_sha256": {},
                "protected_subject_sha256": {
                    protected_name: hashlib.sha256(baseline_text.encode()).hexdigest(),
                },
                "common_instruction_sha256": hashlib.sha256(instruction_text.encode()).hexdigest(),
            }
            manifest_path.write_text(json.dumps(verification_manifest))

            def prepare_workspace(_variant: str, output: Path, _logs: Path) -> str:
                self.init_git_repo(output)
                (output / protected_name).parent.mkdir(parents=True)
                (output / protected_name).write_text(baseline_text)
                (output / "AGENTS.md").write_text(instruction_text)
                self.git("add", "-A", cwd=output)
                self.git("commit", "-qm", "baseline", cwd=output)
                return self.git("rev-parse", "HEAD", cwd=output).stdout.strip()

            launches: list[str] = []

            def launch_agent(_project: str, container: str, env: dict[str, str], _logs: Path) -> None:
                launches.append(container)
                protected_file = Path(env["BENCHMARK_WORKSPACE"]) / protected_name
                with protected_file.open("a") as source:
                    source.write("// injected test edit\n")

            auth = root / "auth.json"
            auth.write_text("{}")
            auth.chmod(0o600)
            run_root = root / "run"
            (run_root / "sessions").mkdir(parents=True)
            manifest = {
                "runtime": {"image_id": "sha256:fixture"},
                "source_trees": {"A": "fixture-tree"},
                "budgets": {"external_grading_seconds": 60},
                "local_cache": {},
            }

            with mock.patch.object(runner, "VERIFY", verify_path), \
                 mock.patch.object(runner, "prepare_workspace", side_effect=prepare_workspace), \
                 mock.patch.object(runner, "compose_env", side_effect=lambda _m, _c, w, _a: {"BENCHMARK_WORKSPACE": str(w)}), \
                 mock.patch.object(runner, "compose_preflight"), \
                 mock.patch.object(runner, "ensure_gateway_and_database"), \
                 mock.patch.object(runner, "launch_agent", side_effect=launch_agent), \
                 mock.patch.object(runner, "wait_agent", return_value=({"OOMKilled": False}, 0)), \
                 mock.patch.object(runner, "read_termination", return_value={"outcome": "completed"}), \
                 mock.patch.object(runner, "harvest_agent_logs"), \
                 mock.patch.object(runner, "validate_trace", return_value={"available": True, "has_started_turn": True, "provider_or_cli_error_events": 0}), \
                 mock.patch.object(runner, "compose_down", return_value=True), \
                 mock.patch.object(runner, "remove_container"), \
                 mock.patch.object(runner, "grade_session", side_effect=AssertionError("protected patch reached grader")):
                outcomes = []
                for position, task in ((1, "T01"), (2, "T02")):
                    outcomes.append(runner.run_one(
                        {"id": f"integrity-{position}", "position": position, "task": task, "repetition": position, "variant": "A"},
                        run_id="fixture-run",
                        run_root=run_root,
                        manifest=manifest,
                        auth=auth,
                        global_started=0,
                    ))

            self.assertEqual(len(launches), 2)
            self.assertEqual([outcome["state"] for outcome in outcomes], ["unsuccessful", "unsuccessful"])
            self.assertEqual([outcome["grading"]["status"] for outcome in outcomes], ["integrity_failure", "integrity_failure"])
            for position in (1, 2):
                session = run_root / "sessions" / f"{position:02d}-integrity-{position}"
                self.assertTrue((session / "final.patch").is_file())
                self.assertTrue((session / "artifacts.json").is_file())
                evaluation_source = session / "evaluation-source" / protected_name
                self.assertIn("// injected test edit", evaluation_source.read_text())
                verify_log = session / "grading-preparation" / "protected-source-verify.stderr"
                self.assertIn(f"Changed or missing protected subject input: {protected_name}", verify_log.read_text())
            recorded = [json.loads(line) for line in (run_root / "outcomes.jsonl").read_text().splitlines()]
            self.assertEqual(sum(item.get("state") == "unsuccessful" for item in recorded), 2)


if __name__ == "__main__":
    unittest.main()
