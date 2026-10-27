# C2-065 — Hypothesis-targeted public LOO for edge-transform ambiguity

## Why this follow-up is needed

C2-064's first-four-task pilot completed 19 folds but did not encounter its target condition, so its zero delta does not measure the proposed ambiguity rule where that rule can act. An input-only scan over the same public-training LOO population found six ambiguous edge-transform inputs: three render the cropped payload identically across the two matching transform names and three render different payloads. The scan read no held-out outputs and retained no task identifiers or grids.

This follow-up tests the original generic rule on every public-training fold selected by that input-only condition. It is a targeted pilot, not a full-cohort expansion and not an evaluation-task-specific branch.

## Selection and comparison

- Public ARC-AGI-2 training split only; eligible population remains tasks with at least four teacher pairs (267 tasks, 1,191 possible LOO folds).
- Include a fold only if its held-out **input grid alone** causes the existing edge transform predictor to report exactly two matching D4 transform names. Classify their rendered payloads as equivalent or different using the input grid alone.
- Build each solver request from the remaining teacher pairs and held-out input only. Run previous and current solvers before the parent reads the held-out output. Score full-grid exactness only after both return.
- Previous requires a unique transform name. Current accepts multiple names only if all render the identical payload grid; different outputs remain rejected.
- Preserve every other teacher-fit, side-constraint, equality-admission, and HOLD rule.
- Report aggregate counts for the total cohort and the equivalent/different input strata. Do not save task IDs, grids, per-fold answers, or output rows.
- Fallback is incorrect. Do not claim any accepted candidate is correct without an exact public-training match.
- No production, Notebook, Kaggle kernel, or official submission changes.

## Decision gate

This targeted pilot can validate or reject the narrow mechanism on its only actionable input class. It cannot establish broad capability. Do not expand to full LOO or adopt the change unless the aggregate union-exact count improves without a regression; any positive result must then pass full matched LOO and regression review before adoption.

Runner: `運用/証拠/ARC26-UNIFIED/P5_HDS_edge_transform_output_equivalence_targeted_LOO.py`.
