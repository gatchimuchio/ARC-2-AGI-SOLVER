# ARC2 C2-063 — Sparse D4 support and many-to-one palette pilot

## Matched evaluation

- Public ARC-AGI-2 training only, using the same 575-task cohort with exactly three training pairs as C2-062.
- Four tasks were evaluated in 12 LOO folds. Both solvers received two teacher pairs and only the held-out input; the parent scored the held-out output after each return.
- Previous used the current connector. Current used an isolated copy with two D4-only changes: support two when exactly two teachers are present, and deterministic many-to-one rather than bijective palette consistency.
- All remaining D4, equality-admission, and HOLD conditions were preserved.

## Results

| Metric | Current connector | Sparse support + palette merge | Delta |
| --- | ---: | ---: | ---: |
| Answer rows | 0 | 0 | 0 |
| Exact | 0 | 0 | 0 |
| Wrong | 0 | 0 | 0 |
| Fallback | 12 | 12 | 0 |
| Union exact | 0 | 0 | 0 |

Previous runtime was 5.439 s and current runtime was 5.412 s, a change of -0.027 s. Combined wall time was 18.170 s.

## Decision

REJECTED_NO_PILOT_GAIN. Combining the two isolated changes did not produce a candidate or exact answer in the pilot, so the remaining 571 tasks were not evaluated. No production, Notebook, submission, or official Kaggle state changed.

Machine evidence: P5_HDS_D4_sparse_support2_many_to_one_LOO_pilot.json. Runner: P5_HDS_D4_sparse_support2_many_to_one_LOO.py.
