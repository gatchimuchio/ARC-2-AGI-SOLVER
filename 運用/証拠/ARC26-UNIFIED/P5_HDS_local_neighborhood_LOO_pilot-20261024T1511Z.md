# P5 HDS cell-neighborhood pilot result

- Observed: 2026-10-24 15:11:01 UTC.
- Procedure: 運用/ARC26-UNIFIED/C2-047_HDS_local_neighborhood_public_LOO.md; governing source: 運用/ARC26-UNIFIED/v3_0/03_共通Codex指示書.md.
- Data: public ARC-AGI-2 training only. Leakage guard and training manifest match C2-045; the current connector hash also matches. This is a four-task, 19-fold pilot from a population of 267 tasks / 1,191 folds. It is not a full LOO result, so it does not establish the full-population previous/current comparison (baseline_matches_c2_045 is null).

## Observed pilot metrics

| Metric | Baseline | Local-neighborhood candidate | Delta |
|---|---:|---:|---:|
| First exact | 0 | unchanged | 0 |
| First wrong | 0 | unchanged | 0 |
| Fallback | 19 | 19 | 0 |
| Distinct second | 0 | 0 | 0 |
| Second exact | 0 | 0 | 0 |
| Second wrong | 0 | 0 | 0 |
| Union exact | 0 | 0 | 0 |

The candidate completed zero grids. Its 974 teacher relation records produced 14 cell queries; all 14 were quarantined. Five folds failed the shape precondition. Runtime was 136.638 s for the baseline solver, 76.921 s for the candidate, and 213.736 s combined. These timing figures cover only this pilot.

A separate five-task attempt completed four tasks (19 folds) but remained on the fifth task for about ten minutes and was stopped. Its progress snapshot also showed zero complete candidate grids. The interruption is recorded separately and is not treated as a performance result.

## Decision and boundaries

The hypothesis showed no pilot gain and no complete candidate. The 4-task pilot is too small to claim general performance, while the attempted fifth task reached the practical runtime cap. Do not run the full 267-task LOO and do not adopt this candidate into production or a Kaggle notebook. Reconsider only with a materially cheaper generic formulation and the same leakage-controlled evaluation.

Held-out outputs were scored only after solver return; no held-out output was passed to the solver. Fallback was not counted correct. No task IDs, grids, or fold-level answers were saved. No hidden/evaluation solutions, production code, submission candidate, or official Kaggle submission were changed.
