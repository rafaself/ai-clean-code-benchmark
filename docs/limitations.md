# Limitations and threats to validity

No experimental observations exist. The following risks are prospective and must remain visible when interpreting any future outcomes.

| Threat | Why it matters | Planned control and remaining limitation |
| --- | --- | --- |
| Small, clustered sample | Five tasks and three repetitions per cell offer little evidence about broad task populations. Tasks share one subsystem and dependencies. | Report task-level outcomes and descriptive differences. Do not treat 30 sessions as 30 independent tasks or claim universal/statistically established results. |
| Project and task selection bias | Choosing an apparently mixed-responsibility service may favor a decomposition. Three proposed tasks concern interchange behavior. | Freeze tasks before outcomes and disclose the targeted selection. Later studies need independently sampled projects/tasks and broader responsibility coverage. |
| Treatment subjectivity | Responsibility boundaries and reasons for change are researcher judgments. A different valid SRP design may behave differently. | Publish the responsibility map and preparation diff, review treatment fidelity, and limit claims to this decomposition. File size is not the definition. |
| Bundled structural effects | SRP extraction changes file count, names, coupling, and indirection, affecting navigation independently of any abstract principle. | Inventory those changes and interpret the total treatment effect. Do not claim perfect isolation or use smaller patch/file counts as automatic proof of quality. |
| Refactoring quality and author expectations | An especially good or poor implementation of B could dominate outcomes; its author may prefer H1. | Freeze B, require behavior equivalence, keep benchmark fixes out of preparation, and review it separately before execution. One treatment implementation remains a limitation. |
| Mocked and implementation-specific tests | Collection tests mock Prisma, directly instantiate the service, spy on private helpers, and assert exact queries. They may miss database bugs and constrain extraction. | Retain unchanged tests and compatibility hooks, add independent database-backed scenarios, and document the resulting constraints. Passing tests is not complete behavioral proof. |
| Incomplete regression coverage | Existing end-to-end scaffolding is narrow, and the grading boundary is the backend. | Require build and independent integration scenarios, preserving team/authorization/event invariants. Avoid claiming no regressions anywhere in the full product. |
| Existing build/setup problems | Node version sensitivity, generated Prisma artifacts, schema-generation scripts, and dependency interactions can cause failures unrelated to SRP. | Reproduce the environment before execution and pin identical artifacts. Never reinterpret unresolved baseline failures as treatment outcomes. |
| Public-code memorization | The pinned source and related fixes may be in training data, potentially benefiting the original layout differently from B. | Disable external solution retrieval and hide historical patches during runs. These controls cannot remove knowledge already present in model weights. |
| Task/oracle leakage | Public protocol descriptions or hidden test fixtures could help agents beyond the task prompt. | Do not mount the benchmark repository or evaluator into agent workspaces; use identical prompts and isolated hidden grading. Accidental leakage must be recorded. |
| Model and provider drift | A model identifier may not pin all provider behavior; service updates and latency can vary. | Pin and record exposed identities/configuration, interleave variants, and disclose run dates. Full repeatability of a hosted model may remain impossible. |
| Dependence and cache effects | Fresh contexts can share prompt caching or provider state; local caches and load influence timing. | Restore local state, use equal resources and serial randomized blocks, record cached-token usage. Operational independence does not prove statistical independence. |
| Telemetry incompleteness | Terminated runs may lack token usage; JSONL actions may differ from internal calls; shell reads may be ambiguous. | Record missingness, distinguish exact counts from proxies/lower bounds, and preserve raw traces. Do not fill gaps with invented measurements. |
| Successful-run selection | Efficiency calculations among successes can compare different subsets and favor selective outcomes. | Report all-run resource use, success/failure rates, contributing task subsets, and regression incidence alongside the predefined ratio. No-worse observed correctness is not proven non-inferiority. |
| Budget sensitivity | Another deadline may change the success-rate difference; a short failed run may look efficient. | Use identical predefined budgets, count timeouts as failures, and label the thresholds preliminary. Budget sensitivity requires a separate later study. |
| Reviewer subjectivity | Unnecessary-change judgments depend on interpretation; extracted architecture may reveal the variant. | Use a written rubric, independent reviews when available, and logged disagreement. Disclose single-reviewer or failed-blinding conditions. |
| Multiple metrics and outcome selection | Choosing whichever secondary metric improves can overstate evidence. | Report every predefined metric and both favorable and harmful differences. Use no significance claims from this exploratory design. |
| License metadata discrepancy | Hoppscotch's root MIT declaration conflicts with the private backend manifest's `UNLICENSED` field. | Document both, retain notices, and review distribution basis before redistributing variant source. Do not invent an upstream explanation. |

## Unresolved preparation risks

Local runtime feasibility, the independent oracle, compatibility with required private-method spies, bounded equivalence, environment/model configuration, and grading duration are now evidenced in the [preparation report](../experiments/srp/preparation/README.md). Live authenticated inference and token semantics, hosted model snapshot identity, exhaustive concurrency equivalence, and independent reviewer availability remain unresolved. These limits are distinct from passing local checks.

If a preparation gate cannot be satisfied, revise the prospective protocol or project selection with a recorded rationale before collecting outcomes. Do not relax protections or remove inconvenient checks after inspecting measured performance.

## What the initial study cannot conclude

It cannot demonstrate that all SRP refactorings improve all agents, establish the value of Clean Code generally, directly measure internal understanding, prove absence of untested regressions, or establish equivalence from a non-significant difference. It also does not measure long-term maintenance cost through subsequent developer work; patch scope is an immediate, limited proxy.

See [hypotheses](hypotheses.md) for interpretation rules and [methodology](methodology.md) for preparation controls.
