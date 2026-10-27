# C2-057: shared-engine HDS task-wide color map

## Why this is a separate experiment

C2-056 assigned one HDS engine to each source color. HDS requires at least two distinct condition values to induce a relation, so that arrangement cannot test a color map. C2-057 uses one shared engine across all color relations; the synthetic contract check returned the expected mappings for two distinct input-color conditions. The C2-056 metrics remain preserved as an invalid integration result, not evidence against the hypothesis.

## Candidate contract

- Public training pairs only; held-out input only at solve time; held-out output is read by the evaluator only after return.
- Each same-shaped teacher pair contributes at most one relation per input color. Reject a teacher pair whose same input color maps to multiple output colors.
- A single HDS engine uses `min_support=2`, `max_conditions=1`, and all distinct color conditions. Require two independent teacher-pair supports for every test color.
- Require unique HDS output prediction for each test color, no request/conflict/quarantine, injective mapping across test colors, and a non-identity candidate.
- Unknown or unsupported test colors force abstention. Fallback is not counted correct; only complete-grid exact matches count.
- Save aggregate metrics only; do not save task IDs, grids, fold rows, or hidden/evaluation answers.

## Evaluation and stop rule

Run the same four-task public-training LOO pilot, capped at five minutes. Report baseline/current/delta on the same folds, complete-grid/exact/wrong/fallback, and runtime. Expand to full LOO only after a complete exact candidate and positive union-exact delta with no regression. Otherwise do not adopt or expand.

No production solver, official Notebook, submission artifact, or Kaggle submission changes are permitted in this experiment.
