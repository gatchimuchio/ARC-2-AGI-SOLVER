# C2-056: HDS task-wide input/output color map

## Hypothesis

The latest runtime diagnosis points to candidate coverage/admission rather than timeout. A generic task-wide color relation may cover recoloring tasks missing from the current mechanism set: for each input color, learn one output color from independent teacher pairs and apply it to the held-out input.

## Candidate contract

- Use only public training pairs and the held-out input during solving. The evaluator reads held-out output only after the candidate returns.
- Require same-shaped teacher input/output grids.
- Reject a teacher pair if one input color maps to multiple output colors within that pair.
- Train one HDS engine per test color with at most one relation per teacher pair, `min_support=2`, and `max_conditions=1`.
- Require every test color to have a unique HDS output prediction, no request/conflict/quarantine, and an injective non-identity mapping across test colors.
- Return no candidate if any test color is unseen or lacks two teacher-pair supports. Do not count input-copy fallback as correct.
- Save aggregate metrics only; never save task IDs, grids, fold rows, or hidden/evaluation answers.

## Evaluation and stop rule

Start with the eligible four-task public LOO pilot, capped at five minutes. Compare baseline/current/delta on the same folds and record complete-grid, exact, wrong, fallback, and runtime metrics. Expand to full LOO only if the pilot produces a complete exact candidate and a nonzero union-exact improvement without a regression. Otherwise stop and do not adopt.

Production solver, official Notebook, submission artifact, and Kaggle submission remain unchanged.
