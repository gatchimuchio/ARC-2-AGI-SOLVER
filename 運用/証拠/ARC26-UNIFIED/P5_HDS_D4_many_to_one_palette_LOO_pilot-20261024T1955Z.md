# ARC2 C2-061 — D4 deterministic many-to-one palette pilot

## Matched evaluation

- Public ARC-AGI-2 training only; the leakage-free population is 267 tasks with at least four training pairs.
- The first four eligible tasks were evaluated in 19 LOO folds. Each solver saw at least three remaining teacher pairs and the held-out input only. Held-out outputs were scored by the parent after each solver returned.
- Previous used the unchanged production D4 bijective palette check. Current used an isolated copy that removed only reverse palette uniqueness, preserving a deterministic input-color function, D4 transform consistency, teacher support, HDS equality admission, and HOLD behavior.

## Results

| Metric | Bijective palette | Deterministic many-to-one | Delta |
| --- | ---: | ---: | ---: |
| Answer rows | 0 | 0 | 0 |
| Exact | 0 | 0 | 0 |
| Wrong | 0 | 0 | 0 |
| Fallback | 19 | 19 | 0 |
| Union exact | 0 | 0 | 0 |

Previous runtime was 103.071 s; current runtime was 101.728 s, a change of -1.343 s. Combined wall time was 214.149 s. No accuracy or coverage signal appeared in the pilot.

The existing MILP feature emitted a nonfatal SciPy warning that the threads option was unrecognized by the wrapper and passed through to HiGHS. It appeared in both conditions and did not stop this pilot.

## Decision

REJECTED_NO_PILOT_GAIN. The pilot gate requires positive union-exact improvement, so the remaining eligible cohort was not run. This four-task pilot does not establish a full-population result. Production code, Notebook, submission artifact, and official Kaggle state were unchanged.

Machine evidence: P5_HDS_D4_many_to_one_palette_LOO_pilot.json. Runner: P5_HDS_D4_many_to_one_palette_LOO.py.
