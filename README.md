# AI Clean Code Benchmark

An exploratory research project investigating whether established software engineering practices help AI coding agents maintain existing software. The initial study evaluates the Single Responsibility Principle (SRP) using OpenAI Codex. Benefits, costs, and no improvement are all possible outcomes.

**Status at execution freeze: readiness passed; measured schedule authorized, not yet started.** The research foundation is followed by a frozen oracle, validated SRP patch, and execution configuration. See the [preparation report](experiments/srp/preparation/README.md), [readiness amendment](experiments/srp/preparation/amendment-002.md), and [execution procedure](experiments/srp/execution.md). Subsequent findings belong in `experiments/srp/results/`; preparation checks are not benchmark outcomes.

## Research question

> Under fixed Codex configuration and evaluation budgets, does responsibility separation in Hoppscotch's team-collection subsystem improve correct maintenance-task completion compared with the original implementation, and what efficiency and change-scope trade-offs accompany it?

Performance means effectiveness (correct completion without regressions), efficiency (time, tokens, and tool activity), and maintainability of the resulting patch (correctness and justified change scope). Inspection activity is an imperfect observable proxy for navigation; it does not reveal an agent's internal understanding.

## Initial study

- Subject: [Hoppscotch](https://github.com/hoppscotch/hoppscotch), upstream commit `63273f8e599e73f0fb38c0739314e8d46b6bc83d`.
- Experimental surface: its TypeScript/NestJS backend, centered on team collections and their collaborating components.
- Variant A: pinned original implementation. Variant B: the validated separation of responsibilities described in the preparation report.
- Design: five independent maintenance tasks, two variants, three fresh runs per task and variant: **30 sessions, 15 per variant**.
- Primary metric: correct task completion rate under identical acceptance tests, regression checks, and budgets.
- Budget: 30 minutes of agent execution and 10 minutes of external grading per run.
- Preliminary signals: a 20 percentage-point completion-rate increase, or a 20% efficiency improvement without worse completion or regression incidence.

These thresholds are exploratory practical signals, not significance tests. Five task clusters in one subsystem cannot establish universal conclusions about SRP, Clean Code, Codex, or AI coding agents.

## Documentation

| Document | Purpose |
| --- | --- |
| [Research question](docs/research-question.md) | Motivation, definitions, and the claim this study can investigate. |
| [Hypotheses](docs/hypotheses.md) | H0, H1, and predefined interpretation rules. |
| [Evaluation criteria](docs/evaluation-criteria.md) | Scoring, operational metrics, budgets, and missing-data rules. |
| [Project selection](docs/project-selection.md) | Candidate comparison, pinned evidence, architecture, and verification limits. |
| [Methodology](docs/methodology.md) | A/B controls, preparation gates, run isolation, and analysis procedures. |
| [Limitations](docs/limitations.md) | Biases, confounding variables, validity threats, and unresolved risks. |
| [SRP experiment specification](experiments/srp/README.md) | Responsibility boundaries and the five proposed task contracts. |

## Preparation and next phase

Reproducible setup, independent acceptance/regression tests, Variant B, and the execution manifest are prepared and validated locally. A/B builds and all 761 unchanged unit tests pass; their 13 independent regression cases and unmet task requirements match. The GraphQL schema and tested HTTP contracts match. A private positive control validates the acceptance oracle.

The original broken e2e scaffold remains unchanged and is disclosed in [amendment 001](experiments/srp/preparation/amendment-001.md). Software validation is not benchmark evidence. The live authentication/telemetry readiness check passed using a non-benchmark prompt. Amendment 002 corrects the Code Mode host setting identically for both variants, hardens grading isolation, and freezes the reviewed serial runner before measured outcomes. Execution requires explicit switches and the recorded user authorization.

## Future organization

Each later experiment belongs in its own directory under `experiments/`, with its question, treatment definition, frozen protocol revision, tasks, provenance, and eventual sanitized evidence. Studies of naming, coupling, complexity, or other principles must define separate treatments rather than silently adding them to this SRP experiment. Shared metric definitions live in `docs/`; study-specific amendments must be dated and committed before their outcomes are collected.

The initial Git branch is `master`. The protocol and execution manifest are prospective freezes, not an independently registered study.

## License

Original benchmark documentation and future original benchmark code are licensed under [MIT](LICENSE). Subject code retains its upstream license and notices. Hoppscotch's repository-level MIT declaration and conflicting private-package license metadata are documented in [project selection](docs/project-selection.md#license-and-provenance).
