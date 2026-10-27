# C2-063 — Sparse D4 support with deterministic color merging

## Evidence and hypothesis

C2-062 lowered only the D4 family support threshold to two on sparse two-teacher folds, while retaining bijective palettes; its pilot produced no answer. C2-061 allowed deterministic many-to-one palettes with three teachers; its pilot also produced no answer. Test their interaction on the exact sparse cohort: a generic D4 transform may need both two-teacher availability and a color-merging map.

## Matched conditions and safeguards

- Public ARC-AGI-2 training tasks with exactly three pairs; leave one out so both solvers receive two teachers.
- Previous is the current connector. Current is an isolated copy that changes only the D4-family support threshold to two for two teachers and removes reverse palette uniqueness. Preserve distinct-input checks, deterministic forward mapping, D4 transform agreement, HDS equality admission, and HOLD behavior.
- The held-out output is scored only by the parent after solver return. Fallback is incorrect.
- Aggregate metrics only; no task identifiers, grids, fold rows, answer maps, hidden solutions, or evaluation data.
- No production, Notebook, submission, or Kaggle changes.

## Pilot gate

Run the first four eligible tasks with a five-minute cap. Compare previous/current/delta for answer rows, exact, wrong, fallback, union-exact, and runtime. Run the full sparse cohort only if the combined condition adds union-exact answers without regression.

Runner: 運用/証拠/ARC26-UNIFIED/P5_HDS_D4_sparse_support2_many_to_one_LOO.py.
