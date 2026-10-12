# Evaluation criteria and measurement procedures

## Correct completion

For every task, an evaluator outside the agent workspace will grade the final working-tree patch against an immutable test and fixture revision. The agent's prose, exit status, or own newly written tests cannot replace external acceptance checks.

A run succeeds only when all of the following hold:

1. Every independent acceptance scenario for the requested change passes.
2. Every frozen regression scenario and required unchanged backend test passes.
3. The backend build succeeds; test execution alone is insufficient because the inspected Jest configuration disables TypeScript diagnostics.
4. Protected tests, grading fixtures, configuration, and dependency controls retain their required integrity. Disabling checks, changing dependency versions, or weakening authentication is not an acceptable solution.

No partial credit contributes to the primary rate. Record individual scenario outcomes to explain unsuccessful attempts. Acceptance tests for newly requested behavior are distinct from regression tests for previously valid behavior.

The initial regression boundary is the selected backend. Do not claim that passing it proves absence of every possible regression in the full Hoppscotch application. Agent-added tests may support the patch but do not change the frozen scoring suite.

## Metrics

| Metric | Measurement procedure |
| --- | --- |
| Correct completion rate | Successful evaluable runs divided by evaluable runs, overall and separately for each task. Planned denominator: 15 per variant and three per task/variant cell. |
| Execution time | Use a monotonic clock from launching Codex to process termination or budget termination. Include model waiting, agent commands, retries, and agent-invoked tests. Exclude provisioning, dependency preparation, database reset, and external grading. |
| Token consumption | Preserve available reported input, cached input, output, and reasoning token fields from the frozen CLI event schema. Deduplicate records by turn/session identity. Sum turn usage only after establishing whether fields are incremental or cumulative; never sum repeated cumulative totals. |
| Total tokens | Input plus output tokens as reported. Cached input is a subset of input and must not be added again. If reasoning output is included in output, do not count it twice. Record source semantics and coverage. |
| Tool calls | Count unique invocations if exact telemetry is available. Otherwise count unique actionable JSONL item IDs for command execution, file change, MCP tool call, and web search as an observed-tool-action proxy. Count started/completed representations once. Exclude reasoning, agent messages, and plan updates. Do not pretend a batched command item measures its internal calls exactly. |
| Files inspected | Audit explicit reads and content searches in the agent trace; resolve unique source/test/configuration paths relative to the workspace. Filename-only listings and incidental compiler/runtime dependency reads do not count. Mark the count as a lower bound when paths or output are incomplete. |
| Files modified and patch size | Diff the final tracked and untracked project files against that run's clean starting variant. Record added, modified, deleted, and renamed files, plus added/deleted lines. Exclude evaluator-generated caches and build outputs. Report the SRP preparation diff separately. |
| Regression count | Count distinct failing predefined regression scenario IDs that passed preflight, rather than multiplying a single scenario by its assertions. Also preserve upstream failing test names. Report run-level regression incidence separately. |
| Unnecessary changes | Review diff hunks against the task contract. A hunk is unnecessary when it does not contribute to the request, required compatibility, or directly relevant verification. Record its file, hunk, changed-line count, reason, and any uncertainty. Broad formatting, unrelated refactors, and unrelated behavior changes qualify. |

Patch scope is descriptive: extraction can increase the number of legitimately affected files. Review necessary glue and relevant tests fairly; do not classify extra files as unnecessary solely because B has more files.

## Telemetry and evidence

Use Codex's `--json` event stream with separately captured process stderr, final patch, process outcome, evaluator output, and run metadata. The [official non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode) describes command/file-change events and reported usage. The event schema and CLI version must be verified and frozen during preparation; documentation examples are not a guarantee that every failed or interrupted run reports complete usage.

Record a run ID, task ID, neutral variant label, repetition, schedule position, protocol revision, upstream/variant commits, prompt hash, instruction/test/fixture hashes, model identity, reasoning configuration, CLI version, environment fingerprint, timestamps, termination reason, metric coverage, and grading outcomes. This is a documentation contract, not an implemented schema or runner.

Keep original traces privately with restricted access. Before any later publication, remove credentials, authentication material, personal paths, and sensitive output without modifying outcome evidence. Preserve hashes of original artifacts and explain redactions. Do not put credentials into task prompts, project environment files, or captured command output.

Missing measurements are recorded as unavailable with a reason, never zero and never fabricated. Incomplete telemetry does not invalidate otherwise trustworthy functional grading; it limits the applicable secondary analysis.

## Budgets and failures

- Agent budget: **30 minutes per run**, identically enforced across variants. Timeout is unsuccessful; retain and grade the resulting patch for diagnostic purposes, without upgrading the primary outcome.
- External grading budget: **10 minutes per patch**. This includes its acceptance checks, frozen regression checks, and build; it is outside the agent clock. Measure suite feasibility during preparation before freezing the protocol.
- Thirty scheduled agent runs imply at most 15 agent-hours; their external grading permits at most five additional hours, excluding preparation and the limited infrastructure replacements below.
- Token and tool counts are measured, not separately capped in this initial design. Token reporting on terminated runs may be incomplete.
- A grader timeout caused by the patch counts as unsuccessful. A timeout or failure independently shown to be caused by infrastructure follows the replacement rule.

Count agent-caused build/test failures, invalid patches, agent-created hangs, and failure to complete within budget as unsuccessful. Do not silently discard unfavorable attempts.

Allow at most **one replacement per scheduled run** for independently verified infrastructure failure, such as a provider outage or a corrupted clean environment unrelated to the patch. Keep the original attempt, evidence, classification reason, and replacement linkage. Execute replacements after the original schedule, using the same task, variant, and configuration. Do not change prompts or budgets. A second infrastructure failure leaves that scheduled observation missing, reduces the evaluable denominator, and must be reported; no extra replacement is permitted.

Establish infrastructure classification before using the affected run's task score to decide replacement. An unknown cause is not sufficient evidence for exclusion. Report both evaluable outcomes and the inventory of all attempts, including invalid attempts and replacements.

## Analysis

Report per-task success counts, overall completion-rate difference in percentage points, all-run resource distributions, successful-run task-balanced efficiency ratios, regression incidence, and reviewed patch scope. With complete balanced data, averaging task-level success rates equals the aggregate rate. With missing scheduled observations, report task-balanced rates as well as raw rates and do not substitute replacement successes for undocumented exclusions.

The numerical threshold of three extra successes applies only when both variants have all 15 evaluable observations; otherwise apply the predefined 20 percentage-point criterion and disclose missingness. Apply the efficiency eligibility and no-worse-correctness rules in [hypotheses](hypotheses.md). No initial result should be presented as statistically supported evidence of a universal effect.
