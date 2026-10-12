# SRP exploratory experiment

**Status: specification only.** No subject source, refactoring, acceptance harness, benchmark sessions, or results are included. This directory describes future preparation and execution.

## Design and treatment

Subject: Hoppscotch, pinned upstream SHA `63273f8e599e73f0fb38c0739314e8d46b6bc83d`. Experimental surface: the backend team-collection service and collaborating collection/request, team, Prisma, PubSub, controller/resolver, and shared-type components.

Variant A retains the pinned original implementation. Variant B will separate responsibilities while preserving behavior and the existing service interface. Both use identical instructions, visible tests, hidden acceptance criteria, dependencies, schemas, runtime configuration, and budgets. See [methodology](../../docs/methodology.md) for controls and preparation gates.

| Responsibility | Reason for change assumed by the study | Refactoring boundary |
| --- | --- | --- |
| Collection transfer | Import/export and client interchange contracts evolve. | Recursive conversion, serialization, and transfer orchestration. |
| Hierarchy and order | Parent/sibling rules, transaction coordination, and ordering policy evolve. | Moves, deletion/reindexing, sorting, and hierarchy-related database operations. |
| Search | Ranking, matching, and ancestry presentation evolve. | Search queries and parent-tree construction. |
| Notifications | Subscription consumers' topic/payload contracts evolve. | Construction and publication of existing collection events. |
| Service interface | Existing callers need a stable operation boundary. | Preserve facade entrypoints and necessary compatibility/delegation hooks. |

These reasons for change are an operationalization of SRP, not a claim about actual upstream teams. The future responsibility map must identify exactly where each existing behavior moves. Preserve constructor signatures and helper hooks used by current tests; do not rewrite tests to accommodate B. New collaborator names and files, coupling changes, indirection, and any retained compatibility wrappers must be inventoried as treatment effects or constraints.

Prepare B before measured runs, without solving any task below. Add no unrelated optimization, dependency changes, schema redesign, error-policy change, or other Clean Code treatment. Both starting variants must pass the same regressions and fail each task's newly requested requirements before execution.

## Proposed maintenance tasks

These are new change requests grounded in inspected code. They are not claims of reproduced upstream bugs. The contracts must be translated into independent, deterministic tests during preparation. Each task starts independently from A or B; it does not include earlier task patches.

| ID | Task | Required behavior and key acceptance cases |
| --- | --- | --- |
| T01 | Canonical request metadata in exports | For requests exported from any nested collection, use database row `id` and `title` for exported `id` and `name`, overriding stale/conflicting stored payload metadata. Preserve every other request payload field and the collection hierarchy. Cover object/string payload forms, renamed requests, multiple nesting levels, and export through duplication paths where applicable. |
| T02 | Ordered root collection export | Export a team's root collection array in ascending `orderIndex`, then ascending ID for ties. Cover roots inserted in a different order, ties, an empty team, and multiple teams. Preserve current nested folder/request ordering and export shape. |
| T03 | Nested import validation | Before opening the write transaction, validate the entire parsed folder tree. Every folder must be a non-null object with a nonempty string `name` and array-valued `folders` and `requests`; every request must be a non-null object with a nonempty string `name`. Empty arrays are valid. Reject malformed input with `TEAM_COLL_INVALID_JSON`, no writes, and no notifications. Cover malformed nested folders, missing arrays, invalid request objects, and partially valid lists. Preserve valid import data, team ownership checks, transaction behavior, and successful notifications. Do not add unrelated request-payload schema restrictions. |
| T04 | Creation-date sorting | Add `CREATED_ASC` to the team-collection sorting contract, ordered by `createdOn` ascending, then ID ascending, assigning contiguous sibling indices. Cover roots/children, equal timestamps, empty lists, and team/parent isolation. Preserve existing title-sort behavior, error behavior, and transaction semantics. The shared `SortOptions` type has other consumers; record the interface effect and regression-check their existing options rather than adding unrelated functionality. |
| T05 | Search relevance ordering | Rank matches by descending PostgreSQL similarity within each existing result group, then ascending ID for equal scores. Keep collection results followed by request results, existing pagination semantics per group, matching/escaping behavior, returned ancestry, and team isolation. Cover exact/partial matches, equal scores, multiple pages, no matches, and multiple teams using real PostgreSQL with `pg_trgm`. Do not introduce global mixed-type ranking or a new pagination API. |

For T03, a nonempty name means string length greater than zero; trimming or normalization is not part of this task. Unknown metadata remains permitted, and existing handling of optional collection data is outside the validation change. Freeze simultaneous-invalid-input error precedence before execution as part of the concrete prompt/oracle, preserving existing ownership behavior for structurally valid inputs.

For all tasks, include negative cases and unchanged behavior alongside positive acceptance. The independent evaluator must observe returned values, database state, and relevant events rather than require a specific extraction or patch style. Existing upstream tests remain a separate unchanged regression check. If task feasibility or those checks conflict, amend the prospective contract before collecting outcomes; do not silently weaken scoring.

## Run matrix and scoring

T01–T05 × A/B × repetitions 1–3 gives **30 scheduled fresh sessions**, 15 per variant. Randomize block and A/B order using a recorded seed. Reset source, session context, database, and fixtures for every run. No human hints or hidden-test repair cycles are permitted.

Agent time is capped at 30 minutes per run; external grading is capped at 10 minutes per patch. Correct completion requires all independent acceptance checks, frozen regressions, successful build, and evaluator integrity. Track time, tokens when available, tool activity, files inspected/modified, regression scenarios, and reviewed unnecessary changes under the shared [evaluation criteria](../../docs/evaluation-criteria.md).

An exploratory effectiveness signal is a 20 percentage-point increase in B's completion rate. An efficiency signal is a 20% reduction in the predefined task-balanced time or token ratio without worse observed completion or regression incidence. These are prospective practical thresholds, not statistically supported conclusions. See [hypotheses](../../docs/hypotheses.md).

## Next phase checklist

- [ ] Reproduce the pinned backend setup, tests, build, and relevant endpoints.
- [ ] Establish immutable independent acceptance fixtures and database-backed regressions.
- [ ] Freeze concrete prompts and verify unmet new requirements on A.
- [ ] Prepare and review B with a responsibility map and structural inventory.
- [ ] Validate A/B equivalence and unmet task requirements on both starts.
- [ ] Freeze model/CLI/environment identities, instructions, telemetry, schedule, and protocol revision.
- [ ] Verify budgets and measurement feasibility without running benchmark tasks as calibration.

Only a subsequent phase executes the measured sessions. Later evidence will link back to the frozen manifest and include all attempts and sanitized artifacts. No numeric results or placeholder outcomes belong in this foundation.
