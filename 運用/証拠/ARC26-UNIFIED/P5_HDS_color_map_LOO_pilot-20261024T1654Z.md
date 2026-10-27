# C2-056 pilot result — HDS task-wide color map

- Completed: 2026-10-24 16:54 UTC
- Evidence JSON: `P5_HDS_color_map_LOO_pilot.json`
- Evidence SHA-256: `3c32fecb1f341405b36a4efba6be3929efe09d87872572b3cddf02aa7b67f93c`.
- Scope: 4 eligible public-training tasks, 19 held-out folds; pilot only, not full LOO.
- Baseline: 19 fallback; exact, wrong, distinct-second, and union-exact all 0.
- Candidate: 19 fallback; exact, wrong, distinct-second, and union-exact all 0.
- Candidate minus baseline on the same pilot folds: all 0. `baseline_matches_c2_045` is null because this is a subset of the full population.
- Candidate diagnostics: 5 shape-precondition failures, 9 within-teacher color-map conflicts, and 5 color queries without a unique HDS prediction. These diagnostic events may overlap and are not a partition of folds. No complete candidate grid was produced.
- Runtime: baseline 122.566 s; candidate 0.040 s. The faster candidate produced no answer, so this is not an ability improvement.
- Decision: stop this hypothesis; do not expand to full LOO and do not adopt. No production solver, Notebook, submission, or official Kaggle state changed.
- Integrity: held-out outputs were scored only after candidate return; no hidden/evaluation solutions were read; fallback was not counted correct.
