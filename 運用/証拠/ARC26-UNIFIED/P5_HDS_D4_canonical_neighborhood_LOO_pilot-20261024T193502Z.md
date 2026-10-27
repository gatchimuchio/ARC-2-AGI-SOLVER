# ARC2 C2-058 — D4-canonical neighborhood pilot

## Conditions

- Data: public ARC-AGI-2 training split only; first four eligible tasks, 19 LOO folds.
- Matched baseline: C2-045 previous_no_prior; HDS connector unchanged.
- Candidate: one HDS relation per original teacher pair and cell; center color, boundary count, and the canonical representative of the eight rotations/reflections of a 3x3 neighborhood; support 3, maximum 2 conditions.
- Held-out outputs were read only by the parent evaluator after solver return. No task identifiers, grids, fold rows, hidden answers, or evaluation answers were saved.

## Results

| Metric | Baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| Fallback folds | 19 | 19 | 0 |
| Distinct second candidates | 0 | 0 | 0 |
| Second exact | 0 | 0 | 0 |
| Second wrong | 0 | 0 | 0 |
| Union exact | 0 | 0 | 0 |

The candidate produced zero complete grids. Aggregate cell diagnostics: 5 shape-precondition failures, 8 additional-observation requests, and 6 cells without a prediction. These are cell-level counts, not disjoint fold counts.

Baseline solver time was 103.525 s; candidate solver time was 0.712 s; combined wall time was 104.405 s. The combined run was 0.880 s (+0.85%) above the baseline solver time. Runtime does not offset the absence of an exact candidate.

## Decision

REJECTED_NO_PILOT_GAIN. The pilot produced no complete exact candidate and no union-exact improvement, so the full LOO expansion gate was not met. Do not adopt this representation or change production code, notebook, or submission. No official submission or rerun occurred.

Machine evidence: P5_HDS_D4_canonical_neighborhood_LOO_pilot.json. Runner: P5_HDS_D4_canonical_neighborhood_LOO.py.
