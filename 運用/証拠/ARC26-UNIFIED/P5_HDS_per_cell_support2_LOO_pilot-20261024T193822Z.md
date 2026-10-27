# ARC2 C2-059 — Per-cell minimum-support-two pilot

## Conditions

- Data: public ARC-AGI-2 training split only; first four eligible tasks, 19 LOO folds.
- Matched baseline: C2-045 previous_no_prior; HDS connector and per-cell feature encoding unchanged from C2-052.
- Candidate change: per-cell HDS minimum support 3→2; maximum conditions remains 2. Each original teacher grid still contributes at most one relation per coordinate.
- Held-out outputs were read only by the parent evaluator after solver return. No task identifiers, grids, fold rows, hidden answers, or evaluation answers were saved.

## Results

| Metric | Baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| Fallback folds | 19 | 19 | 0 |
| Distinct second candidates | 0 | 0 | 0 |
| Second exact | 0 | 0 | 0 |
| Second wrong | 0 | 0 | 0 |
| Union exact | 0 | 0 | 0 |

The candidate produced zero complete grids. Aggregate cell diagnostics: 5 shape-precondition failures, 4 additional-observation requests, 3 quarantined-principle cells, 1 conflict, and 6 cells without a prediction. These are overlapping cell-level diagnostic counts, not fold buckets. Compared with C2-052's support-three pilot, the explicit below-minimum-support count fell from 1 to 0, but the candidate still produced no complete grid.

Baseline solver time was 102.639 s; candidate solver time was 0.803 s; combined wall time was 103.505 s. Combined time was 0.866 s (+0.84%) above baseline. The runtime does not offset the absence of an exact candidate.

## Decision

REJECTED_NO_PILOT_GAIN. The pilot produced no complete exact candidate and no union-exact improvement, so the full LOO expansion gate was not met. Do not adopt this support threshold or change production code, notebook, or submission. No official submission or rerun occurred.

Machine evidence: P5_HDS_per_cell_support2_LOO_pilot.json. Runner: P5_HDS_per_cell_support2_LOO.py.
