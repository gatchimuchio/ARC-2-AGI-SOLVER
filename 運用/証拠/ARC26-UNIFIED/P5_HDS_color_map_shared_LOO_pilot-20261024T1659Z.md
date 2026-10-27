# C2-057 pilot result — shared-engine HDS task-wide color map

- Completed: 2026-10-24 16:59 UTC
- Evidence JSON: `P5_HDS_color_map_shared_LOO_pilot.json`
- Evidence SHA-256: `42c557ad0109f8ea7b42b81af6825d54644b34e59428cecd4c8b6583db779e44`
- Scope: 4 eligible public-training tasks, 19 held-out folds; pilot only, not full LOO.
- Baseline: 19 fallback; exact, wrong, distinct-second, and union-exact all 0.
- Candidate: 19 fallback; exact, wrong, distinct-second, and union-exact all 0.
- Candidate minus baseline on the same pilot folds: all 0. `baseline_matches_c2_045` is null because this is a subset of the full population.
- Candidate diagnostics: 5 shape-precondition failures, 9 within-teacher color-map conflicts, 5 shared-engine HDS queries blocked by request/conflict/quarantine, and 60 teacher color-relation records. These events can overlap and do not partition folds. No complete candidate grid was produced.
- Runtime: baseline 121.084 s; candidate 0.296 s. Runtime reduction did not produce an answer.
- The synthetic shared-engine contract check succeeded, but this public-training pilot found no ARC candidate. Decision: do not adopt or expand to full LOO.
- Integrity: held-out output was scored only after return; no hidden/evaluation solutions were read; fallback was not counted correct; no production solver, Notebook, submission, or official Kaggle state changed.
