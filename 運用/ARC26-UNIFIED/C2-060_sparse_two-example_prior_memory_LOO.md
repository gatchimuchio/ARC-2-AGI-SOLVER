# C2-060 — Prior-memory ablation on two-example tasks

## Hypothesis

The official ARC2 runtime diagnostic has 45 challenge tasks with two training pairs, while the completed C2-045 leakage-guarded LOO population required at least three pairs and therefore did not measure this sparse cohort. Test whether the two approved public-training prior examples add useful support specifically when a sparse task leaves only one within-task teacher in LOO.

This is a focused prior-memory ablation, not a new answer rule. Previous and current conditions use the same HDS connector and held-out folds; current adds only the two approved prior examples. Prior-source tasks and any task with an input overlapping prior inputs are excluded.

## Matched conditions and safeguards

- Public ARC-AGI-2 training split only; tasks must have exactly two training pairs.
- For each held-out pair, the solver receives one remaining within-task teacher pair. Previous receives no prior; current additionally receives the two approved training-only prior examples.
- Held-out outputs are available only to the parent evaluator after solver return. Fallback is incorrect.
- Save aggregate metrics only. Do not save task IDs, grids, fold rows, hidden/evaluation answers, or use ID/hash branches or answer maps.
- Do not change production code, Notebook, submission artifact, or Kaggle competition state.

## Pilot gate

Run the first four leakage-safe sparse tasks, capped at five minutes. Compare previous/current/delta for exact outputs, distinct second candidates, fallback, regressions, and runtime. Expand to the full sparse cohort only after a positive union-exact signal with no regression. No adoption without full matched evaluation.

Experiment runner: 運用/証拠/ARC26-UNIFIED/P5_HDS_sparse2_prior_memory_LOO.py.
