# C2-059 — Per-cell HDS with minimum support two

## Hypothesis

The official fallback diagnostic is dominated by HDS HOLD for insufficient observations. In the C2-052 per-cell pilot, one cell was explicitly below the minimum teacher support of three. Test whether lowering only that minimum from three to two independent teacher grids allows additional correct per-cell candidates.

This is a single-parameter change from C2-052. It does not accept one-example rules: each relation still comes from a distinct original teacher grid. Exact held-out scoring remains outside the solver.

## Matched conditions and safeguards

- Use the same public ARC-AGI-2 training split, source/overlap exclusions, fold order, per-cell features, HDS connector, C2-045 baseline, and maximum conditions=2.
- Change only per-cell HDS minimum support from 3 to 2. A teacher grid contributes at most one relation per coordinate.
- Require a full grid with unique, nonconflicting output-color predictions. HOLD/fallback is incorrect.
- Do not save task identifiers, grids, fold rows, or hidden/evaluation answers. No answer maps, problem-ID/hash branching, or runtime access to held-out outputs.
- Do not change production code, Notebook, submission artifact, or Kaggle competition state.

## Pilot gate

Run the first four eligible public-training tasks, capped at five minutes. Record previous/current/delta, complete candidate grids, exact/wrong/fallback, regressions, aggregate diagnostics, and runtime. Stop without full LOO if there is no complete exact candidate or no union-exact improvement. Adoption requires full matched LOO and regression evidence.

Experiment runner: 運用/証拠/ARC26-UNIFIED/P5_HDS_per_cell_support2_LOO.py.
