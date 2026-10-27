# ARC2 C2-064 — Edge-transform output-equivalence pilot

## Matched evaluation

- Public ARC-AGI-2 training only; 267 eligible tasks with at least four training pairs.
- The first four tasks were evaluated in 19 LOO folds. Each solver received three teacher pairs and the held-out input only. The parent scored held-out outputs after return.
- Previous required one edge-guided transform name. Current used an isolated edge-family copy that accepts multiple matching D4 transforms only when every transform produces the identical cropped output grid.
- Side constraints, teacher reproduction, HDS equality admission, and HOLD behavior remained unchanged.

## Results

| Metric | Unique transform name | Equivalent outputs accepted | Delta |
| --- | ---: | ---: | ---: |
| Answer rows | 0 | 0 | 0 |
| Exact | 0 | 0 | 0 |
| Wrong | 0 | 0 | 0 |
| Fallback | 19 | 19 | 0 |
| Union exact | 0 | 0 | 0 |

Previous runtime was 101.759 s; current runtime was 102.482 s, a change of +0.723 s. Combined wall time was 211.158 s.

The existing MILP feature emitted the same nonfatal SciPy warning seen in earlier runs: its wrapper did not recognize the threads option and passed it to HiGHS. The warning did not stop the pilot.

## Decision

REJECTED_NO_PILOT_GAIN. The equivalent-output condition produced no answer or exact-match increase, so the remaining 263 tasks were not evaluated. The single ambiguous challenge input remains unvalidated for correctness. No production, Notebook, submission, or official Kaggle state changed.

Machine evidence: P5_HDS_edge_transform_output_equivalence_LOO_pilot.json. Runner: P5_HDS_edge_transform_output_equivalence_LOO.py.
