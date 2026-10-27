# ARC2 C2-062 — D4 support-two sparse-task pilot

## Matched evaluation

- Public ARC-AGI-2 training only. The population contains 575 tasks with exactly three training pairs.
- Four tasks were evaluated, with 12 LOO folds. Each solver received the two remaining teacher pairs and only the held-out input; the parent scored held-out outputs after return.
- Previous used the current D4 family minimum support of three. Current used an isolated copy that lowers only this D4-family threshold to two when exactly two teachers are present.
- Distinct-input validation, D4 transform and palette consistency, the connector's support rule, equality admission, and HOLD behavior were retained.

## Results

| Metric | D4 minimum 3 | D4 minimum 2 | Delta |
| --- | ---: | ---: | ---: |
| Answer rows | 0 | 0 | 0 |
| Exact | 0 | 0 | 0 |
| Wrong | 0 | 0 | 0 |
| Fallback | 12 | 12 | 0 |
| Union exact | 0 | 0 | 0 |

Previous runtime was 5.477 s and current runtime was 5.229 s, a change of -0.248 s. Combined wall time was 17.802 s.

## Decision

REJECTED_NO_PILOT_GAIN. Since the pilot produced no answer or exact-match increase, the remaining 571 tasks were not evaluated. This does not establish a full-cohort result. Production, Notebook, submission, and official Kaggle state were unchanged.

Machine evidence: P5_HDS_D4_support2_sparse_LOO_pilot.json. Runner: P5_HDS_D4_support2_sparse_LOO.py.
