# SRP preparation report — 2026-10-12

**Preparation completed locally; benchmark execution has not started.** This report describes deterministic setup, oracle, and equivalence checks. Their passing/failing counts are software validation evidence, not Codex task outcomes or evidence for H0/H1.

## Subject and treatment

A is unchanged upstream `63273f8e599e73f0fb38c0739314e8d46b6bc83d`. B is reconstructed with [variant-b.patch](variant-b.patch); its exact local commit and tree are pinned in [execution-manifest.json](../config/execution-manifest.json).

The decomposition separates transfer/interchange, hierarchy/order, search, and collection events. The facade retains every public operation, the original three-argument constructor, and the three private hierarchy hooks used by upstream tests. Unused private forwarding stubs are removed; extracted internal helpers retain private visibility where no facade calls them. Application behavior, SQL statements, retry limits, error handling, event topics/payloads, dependencies, schemas, and shared sort types are unchanged. The benchmark requirements remain unmet in both starts.

Original method bodies were compared as TypeScript tokens against all 22 extracted bodies, permitting only event routing and hierarchy compatibility-hook substitutions. All retained public signatures are unchanged. Four source files are added; only the original collection service is otherwise modified. The facade changes from 1,576 to 611 lines; the facade plus four collaborators total 1,915 lines (339 more overall). Constructor/delegation glue and retained compatibility hooks add code and indirection. These are recorded treatment effects, not evidence of better or worse maintainability. This is a bounded responsibility separation, not a claim that the whole application satisfies SRP.

The patch retains upstream-derived source. Distribution basis is the explicit upstream root MIT license/README, whose notice is preserved in [UPSTREAM-LICENSE](UPSTREAM-LICENSE). The backend manifest's conflicting UNLICENSED field is retained and remains an upstream metadata discrepancy; it is not silently relabeled.

## Validation

| Check | Evidence |
| --- | --- |
| Dependency setup | Frozen upstream lockfile; pnpm 10.34.5, Node 22.23.3; lifecycle scripts disabled, Prisma generation and backend build run explicitly. No application dependencies added/upgraded. |
| PostgreSQL | PostgreSQL 15.19; original migrations applied, including pg_trgm. Dedicated isolated databases; no host ports exposed. |
| Backend builds | A and B pass the unchanged backend build. |
| Existing backend unit tests | A and B each pass all 19 suites / 761 tests, unchanged. |
| Independent regressions | All 13 database/authorization/event scenarios pass in A and B. |
| Acceptance sensitivity | Both starts have identical statuses across 30 oracle cases: 13 regression passes, one compatible task case pass, and 16 expected unmet task cases. Every T01–T05 has a failing new requirement. |
| Positive control | A private, manually corrected control passes all 30 oracle cases. Its fixes are absent from A/B and not distributed as agent inputs. This validates oracle sensitivity, not agent performance. |
| Behavioral observations | Normalized CRUD/event, move, and search observations match byte-for-byte. This is bounded scenario evidence, not exhaustive equivalence proof. |
| Public contracts | Generated GraphQL SDLs match byte-for-byte. Actual /ping, /health, missing-root, and unauthenticated-search observations match. |
| Broken upstream scaffold | Unchanged e2e scaffold fails TS2349; it also statically expects an obsolete root response. [Amendment 001](amendment-001.md) excludes it equally from scoring and substitutes actual endpoint checks. |
| Execution isolation | Non-model sandbox probes permit project writes, deny private driver-home reads, and connect to the dedicated PostgreSQL socket. An isolated task container has no external egress; only its internal authenticated gateway can reach the provider. Gateway authentication/routing/model restrictions pass fixture tests. |
| Instrumentation | Tool-item/usage parser fixture tests pass, including deduplication and incomplete/missing usage. No live benchmark-driver trace has been collected. Partial token totals are lower bounds and cannot be used as complete-run efficiency observations. |

The oracle/prompts were committed at `9318672` before the decomposition. Additional endpoint checks follow the previously identified actual routes; they do not depend on the treatment's internal layout. Preparation was carried out with Codex assistance in this chat; the same preparer authored the oracle, positive-control corrections, and B. No independent authorship, treatment review, or blinded assessment is claimed. These preparation interactions are outside the frozen benchmark driver and are not measured maintenance sessions.

## Frozen execution configuration

[The manifest](../config/execution-manifest.json) records artifact/protected-input hashes, source identities, runtime/database digests, resource limits, model catalog provenance, task prompts, common instructions, budgets, the schedule, local dependency/image/seed caches, and preparation evidence hashes.

The selected model is gpt-6-sol with high reasoning under Codex CLI 0.158.0. The authenticated CLI catalog lists it; gpt-6.1-sol was absent from that CLI catalog. No model was specified by the user. A hosted immutable weight/snapshot identity is not exposed and is recorded as unknown. Catalog access is not proof of successful inference or account entitlement at execution time.

Each session uses a fresh neutral Git snapshot, fresh container/home, identical paths and instructions, two CPUs, 4 GiB memory with no swap, and the recorded schedule. Personal memory, apps/browser tools, and multi-agent features are disabled. The task container mounts no benchmark/evaluator or host credentials. Its driver token is withheld from command environments, and private control/home paths are denied by the Codex filesystem policy. The gateway alone reads upstream credentials; it exposes only authenticated fixed-model Responses routes.

Codex requires unprivileged namespace operations inside Docker. The frozen profile derives from a pinned Moby default profile and adds only clone/unshare/mount/umount2/pivot_root/setns allowances. All host capabilities remain dropped, no privileged mode is used, and no host kernel policy is changed. Source/license provenance is included. PostgreSQL uses a shared local socket so the task needs no external database network.

## Reproduction and later launch

1. Run `python experiments/srp/tools/verify.py`. The saved database seed was also restored successfully into a fresh database (49 configuration rows, 22 migration records, zero fixture teams). Restore the hashed private caches if needed; the image archive and dependency/seed artifacts are in ignored work/. Verify hashes before `docker load` or extraction. A rebuilt image is not automatically the frozen image, even if its recipe is unchanged.
2. Use `python experiments/srp/tools/prepare.py --variant A --output work/fresh-a` (or B). The output must not exist. It stages the pinned source and dependencies, applies the frozen B patch when requested, adds identical instructions, and creates one neutral commit without upstream history. Verify with `verify.py --subject work/fresh-a`.
3. Start a fresh dedicated database from the pinned image, restore the identical private seed, and create its protected socket metadata directories as specified by the Compose healthcheck. Do not reuse the previous session's data. [runtime.env](../config/runtime.env) documents the TCP grading setup; [agent-runtime.env](../config/agent-runtime.env) freezes the equivalent socket setup for both agents.
4. Stage private control inputs: the frozen task prompt, session-driver.cjs, and a fresh random driver token of at least 32 characters. Supply an upstream auth file only to the gateway. Never commit credentials or raw traces. The Compose input paths are mandatory and explicitly resolved by the operator.
5. Validate current provider authentication/model availability and the complete isolated transport using a non-benchmark instrumentation prompt before starting the measured schedule. Live inference/usage semantics were intentionally not tested here; this readiness check may not use or solve a benchmark task. If a frozen assumption is invalid, amend the protocol before measured outcomes rather than silently substitute a model/configuration.
6. **Only after a separate execution request**, invoke a session with session-driver.cjs's explicit `--execute-approved-session` switch. It otherwise exits without launching Codex. The driver enforces the 30-minute agent budget, captures private JSONL/stderr, terminates descendants, and records termination. Grade externally in a fresh workspace/database with the frozen task-specific oracle, unchanged required tests, build, and protected-file checks, capped at 10 minutes.

[compose.yaml](../config/compose.yaml) fixes the isolation graph, with mandatory absolute control/workspace/auth/seccomp paths and the immutable runtime image supplied from the manifest. It has no published host ports. Normal preparation does not invoke its execution switch. There is no automatic 30-session orchestration, remote publication, or synthetic result dataset.

## Remaining methodological risks

The sample still has five task clusters from one subsystem; task selection, decomposition judgment, file/navigation/coupling effects, public-code memorization, cache/provider drift, and subjective scope review remain. Compatibility hooks add indirection; this treatment's total effect cannot be generalized to every SRP design. Concurrency and all possible inputs are not exhaustively proven equivalent. Live authenticated inference, effective token-usage semantics, and hosted snapshot immutability remain unverified, distinct from the passing local software checks.
