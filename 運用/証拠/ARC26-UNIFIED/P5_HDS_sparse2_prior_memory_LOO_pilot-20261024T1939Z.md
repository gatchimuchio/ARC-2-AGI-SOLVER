# ARC2 C2-060 — Two-example task prior-memory pilot

## Conditions

- Public ARC-AGI-2 training split only. The sparse cohort contains 157 leakage-safe tasks with exactly two training pairs after excluding one prior-source task; no additional input-overlap task was excluded.
- Four eligible tasks were evaluated, giving 8 LOO folds. Each solver call received one remaining within-task teacher pair. The current condition also received the two approved training-only prior examples; the previous condition received none.
- Held-out outputs were read only by the parent evaluator after solver return. No task identifiers, grids, fold rows, hidden answers, or evaluation answers were saved.

## Results

| Metric | No prior | Approved prior | Delta |
| --- | ---: | ---: | ---: |
| Solver answers | 0 | 0 | 0 |
| Fallback folds | 8 | 8 | 0 |
| Distinct second candidates | 0 | 0 | 0 |
| Second exact | 0 | 0 | 0 |
| Second wrong | 0 | 0 | 0 |
| Union exact | 0 | 0 | 0 |

Previous runtime was 0.423 s and current runtime was 0.504 s: +0.081 s (+19.086%). The combined wall time was 0.935 s. The pilot produced no accuracy or coverage gain; runtime is not a basis for adoption.

## Decision

REJECTED_NO_PILOT_GAIN. No union-exact improvement occurred, so the full 157-task sparse cohort was not run. The result only describes this four-task pilot and does not establish a full-cohort prior-memory effect. Production code, Notebook, submission, and official Kaggle state were unchanged.

Machine evidence: P5_HDS_sparse2_prior_memory_LOO_pilot.json. Runner: P5_HDS_sparse2_prior_memory_LOO.py.
