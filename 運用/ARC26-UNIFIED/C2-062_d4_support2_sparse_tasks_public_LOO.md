# C2-062 — D4 support two on sparse tasks

## Evidence and hypothesis

The ARC2 connector lowers its HDS minimum support to two when a task has two distinct training inputs. The specialized D4-grid family still hard-codes a minimum of three teacher grids, making it unavailable on that sparse cohort. Public training contains 575 tasks with exactly three pairs; leaving one pair out gives two teacher pairs and matches the official two-example inference condition.

Test whether lowering only the D4 family's local teacher minimum from three to two lets its generic, mutually consistent D4 transform and palette candidates pass through the unchanged HDS admission and HOLD gates.

## Matched conditions and safeguards

- Public ARC-AGI-2 training tasks with exactly three pairs; evaluate each held-out pair with the other two pairs as teachers.
- Previous is the current connector. Current is an isolated copy changing only D4-family minimum support from three to two when it receives exactly two teacher pairs.
- Keep distinct-input validation, common D4 transform agreement, color consistency, HDS equality admission, and HOLD behavior. No task-specific branches.
- Pass only the held-out input to either solver; score its output in the parent afterward. Fallback is incorrect.
- Save aggregate metrics only. Do not save task identifiers, grids, fold rows, hidden answers, or evaluation data.
- Do not change production, Notebook, submission artifact, or Kaggle state.

## Pilot gate

Run the first four eligible tasks, capped at five minutes. Compare answer rows, exact, wrong, fallback, union-exact, and runtime. Run all 575 tasks / 1,725 folds only if the pilot adds union-exact answers with no regressions and is within the runtime budget.

Runner: 運用/証拠/ARC26-UNIFIED/P5_HDS_D4_support2_sparse_LOO.py.
