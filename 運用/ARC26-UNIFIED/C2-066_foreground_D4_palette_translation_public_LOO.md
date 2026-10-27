# C2-066 — Compound foreground geometry and palette rule

## Evidence and hypothesis

The public-training candidate attribution baseline covered 267 tasks and 1,191 LOO folds. It found 20 teacher-consistent candidates across 127,437 family-fold checks, with geometry and whole-foreground translation among the only families producing fits. Separate D4 and color-map pilots did not change exact coverage. The untested interaction is one global foreground D4 transform, a bijective color map including the background relation, and one constant translation, all required to agree across every teacher pair.

Test this as a standalone shadow family. Require exact geometric occupancy, injective color correspondence, same canvas dimensions, and a consistent D4 name/translation/color map across all remaining teacher pairs. If multiple programs predict different test grids, abstain. Do not relax existing HDS support or HOLD rules.

## Matched pilot

- Public ARC-AGI-2 training split only; preserve the 267-task / 1,191-fold baseline manifest.
- Pre-screen folds using remaining teacher pairs only. A candidate may use the held-out input, but not its held-out output.
- From candidate-applicable folds, select a reproducible sample of up to 12 distinct tasks using reservoir sampling seeded by the public training manifest. Evaluate one applicable fold per sampled task.
- Run the existing HDS baseline and the isolated candidate on the same teachers and held-out input. The parent reads the held-out public output only after both return.
- Compare the baseline first answer against the union of the baseline first answer plus the new candidate as a second guess. Report candidate answer, exact, wrong, fallback, union-exact, regressions, and runtime.
- Save aggregate metrics only; no task IDs, grids, fold-level answers, or per-task predictions. Fallback is incorrect. Hidden/evaluation solutions are not read.
- No production, Notebook, private kernel, or official Kaggle state changes.

## Decision gate

Reject if the pilot has no positive union-exact delta, adds an unacceptable wrong-candidate rate, or exceeds its runtime budget. Expand to full matched LOO only after a positive pilot with no regression. Adoption requires full-cohort previous/current/delta, regression review, targeted tests, and source audit.

Runner: `運用/証拠/ARC26-UNIFIED/P5_HDS_compound_foreground_D4_palette_translation_LOO.py`.
