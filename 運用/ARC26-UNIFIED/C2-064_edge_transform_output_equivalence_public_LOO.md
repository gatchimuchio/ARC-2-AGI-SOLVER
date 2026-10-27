# C2-064 — Admit equivalent outputs from ambiguous edge transforms

## Evidence and hypothesis

The official v5 input-only diagnostics recorded one ambiguous edge-guided payload transform among 240 challenge tasks. The current family rejects whenever more than one D4 transform name matches the edge constraints, even when the transforms may produce the same payload grid. For a generic, symmetric payload, transform-name ambiguity does not imply output ambiguity.

Test whether the isolated edge-family copy can accept multiple matching transforms only when every transform renders the identical payload grid. Keep rejecting differing outputs and every other ambiguous or weak input.

## Matched conditions and safeguards

- Public ARC-AGI-2 training LOO, same 267-task / 1,191-fold population and current connector as baseline.
- Change only the isolated copy of the edge transform resolver. Preserve all side-constraint, teacher-reproduction, equality-admission, and HOLD rules.
- Held-out output is passed only to the parent evaluator after solver return. Fallback is incorrect.
- Aggregate metrics only; no task identifiers, grids, fold rows, hidden answers, or evaluation data.
- No production, Notebook, submission, or Kaggle changes.

## Pilot gate

Run the first four eligible tasks, capped at five minutes. Compare answer rows, exact, wrong, fallback, union-exact, and runtime. Run full LOO only if union-exact improves without regression.

Runner: 運用/証拠/ARC26-UNIFIED/P5_HDS_edge_transform_output_equivalence_LOO.py.
