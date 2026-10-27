# ARC2 C2-065 — Input-stratified edge-transform ambiguity pilot

## Selection

An input-only scan over the 267-task / 1,191-fold public-training LOO population found six folds where the held-out input produced exactly two matching edge-guided D4 transform names. Three rendered the payload identically; three produced different or invalid payload grids. No held-out outputs were read during this scan, and no task identifiers or grids were saved.

The targeted LOO runner evaluated all six folds across four tasks. It submitted only the remaining teacher pairs and held-out input to both solvers, then read the public held-out output after both had returned.

## Previous / current / delta

| Cohort | Folds | Metric | Unique transform name | Equivalent-output acceptance | Delta |
| --- | ---: | --- | ---: | ---: | ---: |
| All ambiguous inputs | 6 | Answers / exact | 0 / 0 | 0 / 0 | 0 / 0 |
| All ambiguous inputs | 6 | Wrong / fallback | 0 / 6 | 0 / 6 | 0 / 0 |
| Equivalent rendered payload | 3 | Answers / exact | 0 / 0 | 0 / 0 | 0 / 0 |
| Different or invalid payload | 3 | Answers / exact | 0 / 0 | 0 / 0 | 0 / 0 |

There were no solver exceptions. Previous runtime was 7.186 s; current runtime was 6.812 s, a change of -0.374 s. Combined wall time was 22.268 s.

## Decision

REJECTED_NO_TARGETED_PILOT_GAIN. The proposed acceptance rule did not produce an answer even on all three equivalent-output inputs. The six-fold cohort was fully evaluated; the remaining 1,185 folds were not run. C2-064 remains unadopted. No production code, Notebook, private kernel, or official submission changed.

Evidence: `P5_HDS_edge_transform_output_equivalence_targeted.json`. Runner: `P5_HDS_edge_transform_output_equivalence_targeted_LOO.py`. Specification: `運用/ARC26-UNIFIED/C2-065_edge_transform_ambiguity_stratified_LOO.md`.
