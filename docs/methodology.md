# Proposed experimental methodology

## Study status and design

This is a documentation-only, prospective exploratory protocol. No variants, independent test harness, runner, or results exist yet. All preparation and measured execution described here are future work.

The initial design has five tasks, two variants, and three fresh sessions for each task/variant cell: **30 scheduled sessions**. The experimental treatment is one specified SRP decomposition of Hoppscotch's team-collection subsystem at upstream SHA `63273f8e599e73f0fb38c0739314e8d46b6bc83d`. A repetition is an independent fresh context operationally, not a guarantee of independent model samples statistically.

## Variants and treatment controls

**A — Baseline:** retain original upstream application source at the pinned commit. Common fixtures, test infrastructure, and agent instructions live outside application source or are added identically to both variants. Any unavoidable setup intervention must be documented, identical, and behavior-neutral; do not quietly repair A.

**B — SRP:** later extract collection transfer, hierarchy/order operations, search, and notification responsibilities behind the existing service interface. Preserve constructor compatibility and observable delegation hooks used by upstream tests. If this cannot be achieved without weakening tests or changing behavior, stop preparation and amend the protocol before any measured session.

No benchmark task may be solved while preparing B. The refactoring may move existing defects or limitations but must not repair them, optimize algorithms, upgrade dependencies, redesign errors, introduce new security policy, or add unrelated architectural patterns. Behavior changes requested by a maintenance task belong only in that task's later run patch.

| Controlled factor | Required equality |
| --- | --- |
| Observable behavior before tasks | REST/GraphQL contracts, returned values/errors, authorization, database state changes, transaction semantics, ordering where specified, and notification topics/payloads. |
| Dependencies and persistence | Identical manifests, lockfile, database schema/migrations, and dependency artifacts. |
| Runtime configuration | Identical sanitized environment values, clock/timezone policy, service configuration, and local test endpoints. |
| Agent input | Identical task text, visible test corpus, effective instructions, capabilities, and budgets for the same task. No treatment-specific SRP hints. |
| Execution environment | Same pinned OS/runtime images, resources, package manager, database version, workspace path, and prepared dependency state. |
| Evaluation | Same immutable acceptance/regression suite, fixtures, build requirements, and grader configuration. |

File count, new collaborator names, call graph, coupling, indirection, and navigation cannot necessarily remain equal. Record them in a preparation inventory rather than controlling away the treatment's inherent effects. The inference concerns the total effect of this implementation of responsibility separation.

## Preparation gates before execution

1. **Reproduce the subject.** Retrieve and verify the pinned commit, preserve license notices, establish the backend setup using Node 22 and pnpm 10.34.5, and pin exact versions/digests after validation. Prepare PostgreSQL and its upstream migrations, including `pg_trgm`. Run backend tests, build, and relevant startup/endpoint checks. These checks have not occurred in this phase.
2. **Establish the independent oracle.** Build deterministic acceptance fixtures and backend regression scenarios outside the agent workspace. Cover database effects, authorization/team boundaries, notification behavior, nested structures, errors, and task-specific edge cases. Reuse existing test dependencies; do not add production dependencies just for the benchmark.
3. **Freeze task contracts.** Translate the five proposed tasks into identical agent prompts and implementation-independent assertions. Confirm that each requested new requirement fails on A. Avoid giving agents expected patches, helper names, or architectural hints. Existing source-specific tests remain unchanged.
4. **Prepare and review B.** Perform only the defined responsibility separation. Map original behavior to extracted responsibilities, record the structural diff, and retain compatibility required by upstream tests. Do not generate benchmark results during preparation.
5. **Validate equivalence.** Both starting variants must pass identical frozen regression checks and builds. Compare response/error contracts, database effects, authorization, and event observations on the same fixtures. Both must fail the same new task acceptance requirements. Differential equivalence is supported by these scenarios, not proven for every possible input.
6. **Freeze execution configuration.** Record protocol and variant commits, prompt/instruction/test/fixture hashes, model identifier and exposed snapshot identity if available, reasoning settings, CLI version, permissions, telemetry schema, and environment digests. CLI 0.158.0 was observed during planning; this is not yet an execution pin. Do not allow silent defaults or model upgrades during the study.
7. **Validate measurement feasibility.** Check trace parsing and timeout/grader behavior using fixtures or non-benchmark instrumentation checks. Ensure grading fits its 10-minute budget and metrics are observable. Do not use measured-task agent runs as unrecorded calibration. Any needed change requires a dated pre-outcome amendment.

An upstream test or environment failure is a preparation blocker, not a reason to delete failing checks. Resolve setup or revise the documented selection/protocol before measured sessions. Benchmark execution begins only after all gates are satisfied in a subsequent phase.

## Isolation and run procedure

Create 15 task/repetition blocks: T01–T05 crossed with repetitions 1–3. Before launch, use a versioned randomization algorithm and recorded seed to shuffle block order and assign A/B versus B/A order within each block. Save the schedule before collecting outcomes. Execute serially with equal resources to avoid concurrent resource contention.

For each scheduled session:

1. Restore the appropriate clean variant, fresh project state, deterministic fixtures, prepared dependencies, and reset database. Use the same mounted workspace path and neutral variant metadata.
2. Start a fresh Codex session with no resume, prior conversation, user memory, personal skills/plugins, or inherited project-specific instructions beyond the frozen effective instruction set. Preserve identical applicable upstream instructions and record all effective instructions. Disable multi-agent delegation for this initial design.
3. Make only the intended subject context and identical visible tests available. Hide the benchmark documentation, evaluator, hidden acceptance fixtures, other variant, prior runs, and preparation diff/history. Do not expose upstream history as a shortcut to known patches.
4. Restrict solution retrieval and external network tools. Model-provider connectivity is permitted; arbitrary web/GitHub access and dependency changes during tasks are not. Use isolated environments, local services, and sandboxed project writes. Do not expose host credentials to application scripts or the agent's shell.
5. Deliver the task prompt, capture JSONL/stderr, and start the monotonic 30-minute budget. Allow autonomous inspection, editing, and local verification; no human hints, prompt amendments, or follow-up repair sessions.
6. At process exit or timeout, preserve the final patch and evidence. Grade it externally for at most 10 minutes, using the same protected suite and clean grading environment. Do not return hidden-test feedback for further repair.
7. Classify outcomes and infrastructure exceptions under the predefined [evaluation rules](evaluation-criteria.md). Reset state before the next session.

Host caches and provider prompt caches cannot necessarily be eliminated. Standardize prepared local caches, record reported cached-token usage, interleave variants, and disclose residual cache/service effects. Fresh context is not a guarantee of deterministic or fully independent model behavior.

## Review and analysis

Use deterministic functional grading for the primary outcome. Review patch scope separately using the documented unnecessary-change rubric. Have two reviewers independently assess scope when available, conceal variant labels where practical, and record disagreements. If only one reviewer is available, disclose that limitation rather than claiming independent agreement. Architecture can reveal the variant even when labels are concealed.

Publish task-level success counts, the completion-rate difference, metric coverage, resource summaries, the predefined efficiency comparison, regression incidence, and scope judgments. Keep failures and mixed outcomes visible. Treat the five tasks as clusters; three repetitions do not turn one task into three independent task samples.

A larger confirmatory study would require more independently sampled tasks/projects, a frozen primary comparison, treatment fidelity checks, and an explicit sample-size/statistical plan. This phase does not claim those requirements are satisfied.

## Amendments and evidence retention

The committed foundation specifies preliminary decisions. Before execution, commit a frozen study manifest and dated amendments that explain any changes introduced by feasibility checks. Record every attempted session, including infrastructure failures and the single allowed replacement per scheduled run. Protect raw evidence and publish only reviewed, sanitized artifacts later. Do not create placeholder numeric results or run examples that could be mistaken for observations.
