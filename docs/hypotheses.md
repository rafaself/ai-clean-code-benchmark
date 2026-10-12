# Hypotheses and predefined interpretation

These hypotheses and preliminary criteria are specified before benchmark execution. No outcome has been collected. They apply to the bounded study in [research question](research-question.md).

## Hypotheses

- **H0 (Null Hypothesis):** Applying SRP does not produce a meaningful improvement in Codex's performance on software maintenance tasks.
- **H1 (Alternative Hypothesis):** Applying SRP improves Codex's effectiveness or efficiency on software maintenance tasks.

Maintainability is a secondary outcome and a potential trade-off. It does not independently satisfy H1 if effectiveness and efficiency do not improve.

## Operational signals

| Signal | Predefined exploratory criterion |
| --- | --- |
| Effectiveness | Variant B's correct completion rate exceeds A's by at least 20 percentage points. With 15 evaluable runs per variant, this requires at least three additional successful runs. |
| Efficiency | At least a 20% reduction in task-balanced median wall-clock time or reported total input-plus-output token usage, with no lower overall correct completion rate and no higher proportion of runs introducing regressions. |

For each efficiency metric, compute each eligible task's median among successful runs in A and B, then its B/A ratio. The task-balanced summary is the median of these task ratios; a ratio at or below 0.80 meets the improvement threshold. A task is eligible only if it has a successful run with that metric observed in each variant. Require at least three eligible tasks to label an efficiency signal; otherwise report the comparison as insufficiently observed. Report the contributing tasks and all missing observations.

These successful-run comparisons can select different attempts in each variant and therefore introduce selection bias. Always accompany them with all-run resource summaries, completion rates, timeout counts, and regression incidence. Do not interpret low resource use on failed runs as an efficiency advantage. Missing token data cannot be substituted with estimates or zeros; an efficiency signal may still be assessed using time.

The thresholds are preliminary judgments about practical importance, not power-derived thresholds. The sample is not adequate to validate a formal non-inferiority claim merely because B has an equal or higher observed success rate.

## Interpretation rules

- Evaluate the primary completion-rate difference first. Present efficiency and maintainability as separate dimensions; do not combine them into an arbitrary composite score.
- Meeting a threshold indicates an exploratory signal consistent with H1, subject to the study's limitations. It does not statistically establish H1 or prove that SRP is beneficial generally.
- Missing a threshold is inconclusive. It does not establish H0, equivalence, or absence of an effect.
- Report harmful, mixed, and null-looking outcomes with the same detail as favorable outcomes. Report whether time and tokens disagree.
- Report all five task-level success counts and outcomes. Repetitions within a task are stochastic replicates, not additional independent task samples.
- Do not use pooled significance testing that assumes 30 independent tasks. The initial study will use descriptive effect sizes and distributions; a confirmatory phase requires a separate sampling and power plan.

The efficiency alternatives and other secondary metrics create multiple opportunities to see favorable differences. Report them all and avoid post-hoc metric selection.

## Protocol changes

Any necessary adjustment to a task, budget, metric, or threshold during preparation must be recorded in a dated, committed amendment before collecting outcomes. If changes are needed after execution starts, stop the affected study and retain the original records; a revised protocol defines a new study version. This repository is a prospective specification, not an independent external preregistration.

See [evaluation criteria](evaluation-criteria.md) for scoring and missing-data procedures.
