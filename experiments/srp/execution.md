# SRP execution procedure

This procedure is frozen before measured outcomes under amendment 002. The user authorized the next steps in the accompanying Codex chat. The schedule remains five tasks × two variants × three fresh repetitions, serial and in its recorded order. Preparatory subagents do not assist measured agents.

## Launch controls

Run `python experiments/srp/tools/verify.py` and verify the ignored dependency, image, and database caches against the manifest. `serial-runner.py` performs these gates again. It defaults to validation without launching services. An explicit `--execute-approved-schedule`, private `--auth-file`, new ignored `--root-output`, and the exact `--reviewed-script-sha256` are required to launch. The script records its digest, repository commit, protocol/input hashes, schedule, image identities, and readiness proof before any measured inference.

Each observation has a new neutral Git snapshot without upstream history, empty container home, protected prompt/control directory and per-session gateway token, dedicated seeded PostgreSQL database, identical instructions/configuration and `/workspace` path. Only the separate gateway receives account credentials. All attempts, private raw traces, termination records, final source patch, and grading diagnostics are retained. Driver tokens are removed after use. This document contains no credentials or executable launch command with secrets.

## External grading

After the agent container stops, the runner captures changes relative to its preserved starting snapshot, including new files and agent commits. It builds a new evaluation clone from that baseline plus the final patch and frozen dependency cache. Protected original tests/configuration/dependencies are checked before restoring caches so alteration cannot be masked.

The common ten-minute grading deadline includes clone staging, protected-input verification, dedicated database setup, the task-specific acceptance group plus all RG scenarios, the required unchanged unit suite, and the backend build. No subsequent check starts after the deadline. Teardown can finish after checks are stopped; cleanup time is recorded separately where applicable and does not permit extra evaluation. Tests mount the subject and evaluator read-only, using temporary caches; their stdout JSON is captured privately on the host. The build receives its disposable source clone writable; protected inputs are checked afterward. Failure of an acceptance test does not skip regression/build diagnostics.

The primary outcome is derived with `tools/score.py` from termination, all required acceptance/regression scenario identities, passing original unit tests, successful build, and integrity. The pre-outcome `preparation/required-test-identities.json` records every original test identity and oracle scenario; matching a reported count alone is insufficient. Additional directly relevant tests are permitted; the original 761 must still pass without skips. A successful CLI exit alone is not sufficient. Timeout/resource errors remain outcomes unless an independent infrastructure cause is established. The runner halts for review on unexpected provider, launcher, resource, grading, or cleanup errors; it never automatically hides, repeats, excludes, or relabels them. Continuation must preserve schedule order, retain attempted observations, and apply the original replacement rule only after the original schedule.

## Analysis and disclosure

Use the frozen [metric definitions](../../docs/evaluation-criteria.md) and [interpretation](../../docs/hypotheses.md). Audit inspected files as a disclosed lower bound from explicit trace paths/content. Count final modified files and added/deleted lines against each observation's own variant start, excluding the B preparation patch. Review diff hunks against the task with written reasons, including any evaluator interference; disclose reviewers and lack of blinding.

Publish sanitized per-run records, task-level success counts, completion-rate differences, all-run resource distributions, successful-run task-balanced median ratios, regressions, missing telemetry, and reviewed change scope. Tokens with incomplete usage are lower bounds and are ineligible for complete-run efficiency comparisons. Cached input is already part of reported input. JSONL action counts omit Code Mode wrappers and are proxies. Do not publish account credentials, driver tokens, unsanitized traces, or corrected-control solutions. No confirmatory or universal SRP conclusion follows from this small clustered sample.
