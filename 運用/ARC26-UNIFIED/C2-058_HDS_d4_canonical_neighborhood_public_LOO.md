# C2-058 — HDS D4-canonical local neighborhood

## Hypothesis

C2-047 used rotation-invariant neighbor counts, while later local-pattern pilots used other encodings. A generic per-cell relation may benefit from retaining local adjacency while treating rotations and reflections as equivalent. For each 3x3 neighborhood, encode the lexicographically smallest of its eight D4 variants and use that feature with the center color and boundary count.

This is a feature representation only: each original teacher pair contributes one record per coordinate, so symmetry variants do not multiply independent support. The held-out answer is never passed to the solver.

## Matched conditions and safeguards

- Use the same public ARC-AGI-2 training split, source/overlap exclusions, fold order, HDS connector, C2-045 baseline, support=3, and maximum conditions=2.
- Require same-shaped teacher grids. Emit a candidate only when every cell has one unique, nonconflicting HDS output-color prediction.
- Treat HOLD/fallback as incorrect. The parent evaluator compares the returned full grid to the held-out output only after solver return.
- Do not persist task IDs, grids, fold rows, or evaluation answers. Do not use task-ID, filename, or hash branches, answer maps, or hidden/evaluation data.
- Do not change production code, Notebook, submission artifact, or Kaggle competition state.

## Pilot gate

Run the first four eligible public-training tasks, capped at five minutes. Record baseline/current/delta, complete candidates, exact/wrong/fallback, regressions, aggregate HDS diagnostics, and runtime. Stop without full LOO if no complete exact candidate is produced or union-exact improvement is zero. Expand only after a positive pilot signal with no regression; never adopt without full matched LOO and regression evidence.

Experiment runner: 運用/証拠/ARC26-UNIFIED/P5_HDS_D4_canonical_neighborhood_LOO.py.
