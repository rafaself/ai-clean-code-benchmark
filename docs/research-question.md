# Research question

## Motivation

Clean Code guidance was largely developed around human comprehension and collaboration. An AI coding agent may benefit from coherent responsibility boundaries, but it may also pay additional costs when relevant behavior is spread across more files, interfaces, and tool interactions. Neither effect should be presumed to dominate.

This project investigates those competing possibilities through controlled maintenance tasks on existing open-source software. It evaluates one explicitly defined SRP refactoring, rather than treating all practices associated with Clean Code as one intervention.

## Testable question

> Under fixed Codex configuration and evaluation budgets, does responsibility separation in Hoppscotch's team-collection subsystem improve correct maintenance-task completion compared with the original implementation, and what efficiency and change-scope trade-offs accompany it?

The comparison is between the pinned original implementation and one functionally equivalent decomposition. Each task starts from its respective unmodified variant; patches do not accumulate across tasks or repetitions.

## Meaning of performance

| Dimension | Operational meaning | Observable evidence |
| --- | --- | --- |
| Effectiveness | Completing the requested behavior without introducing tested regressions. | Independent acceptance results, frozen regression scenarios, successful build, and evaluator integrity. |
| Efficiency | Resources consumed while attempting the same task within the same budget. | Agent wall-clock time, reported input/output tokens, tool calls or disclosed event proxies, and explicitly inspected files. |
| Maintainability | Whether the resulting patch correctly implements the request with justified scope. | Functional checks and a documented review of final files, lines, and unnecessary diff hunks. |

The primary outcome is effectiveness. A short, cheap, incorrect attempt is not evidence of superior maintenance performance. Efficiency and patch scope must be interpreted with correctness and failure rates visible.

## Understanding and navigation

Successful maintenance requires finding and interpreting relevant behavior, but those internal processes are not directly measured. File inspection, tool activity, and patch correctness provide observable traces. A high or low inspection count is not inherently good: an agent may inspect more files because it is confused or because it is thorough. The study does not score fluency of explanations as proof of understanding.

## Intervention and inference boundary

SRP is operationalized through distinct reasons for change: collection interchange contracts, hierarchy/order rules, search behavior, and subscriber notification contracts. This follows [Robert C. Martin's SRP discussion](https://blog.cleancoder.com/uncle-bob/2014/05/08/SingleReponsibilityPrinciple.html). These boundaries are research judgments, not verified claims about Hoppscotch's organizational actors. Smaller files alone are not sufficient evidence of SRP.

The treatment inevitably changes some combination of file layout, coupling, indirection, and names of new collaborators. The estimate concerns the total effect of this specified responsibility separation. It cannot identify a perfectly isolated abstract SRP effect or justify claims about unrelated Clean Code principles.

The audience is researchers and engineers assessing AI-assisted maintenance. The initial objective is to establish feasibility, collect interpretable exploratory observations later, and inform a broader confirmatory design. See [hypotheses](hypotheses.md), [methodology](methodology.md), and [limitations](limitations.md).
