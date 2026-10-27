# C2-061 — D4 transform with a deterministic many-to-one palette

## Hypothesis

The public-training candidate-pipeline attribution found 20 teacher-fit and equality-admitted family outcomes across 1,191 folds. Of these, 16 came from the generic D4-grid-transform family and four from foreground translation; 1,190 folds had no distinct raw candidate.

The D4 family currently requires a bijective partial input/output color map. ARC transformations can merge colors while remaining a deterministic function. Test whether removing only the reverse-uniqueness constraint allows the same D4 spatial transform and a consistent input-color-to-output-color function to explain more held-out examples.

## Matched conditions and safeguards

- Public ARC-AGI-2 training split only; include tasks with at least four training pairs and evaluate each held-out pair against at least three remaining teacher pairs.
- Compare the unchanged production connector with an isolated copy that changes only D4 palette consistency from bijective to deterministic many-to-one. Preserve support count, D4 transform agreement, HDS equality admission, HOLD behavior, and all other solver code.
- Give the held-out input, but never its output, to either solver. The parent evaluator compares the returned answer afterward; fallback is incorrect.
- Save aggregate results only. Do not save task identifiers, grids, or fold rows. Do not use answer maps, task/hash branches, hidden solutions, or evaluation data.
- Do not modify production files, Notebook, submission artifact, or Kaggle state.

## Pilot gate

Run the first four eligible public-training tasks, capped at five minutes. Record previous/current/delta for answer rows, exact, wrong, fallback, union-exact, and runtime. Run the full 1,191-fold matched LOO only if the pilot adds union-exact answers with no regression and remains within the runtime budget. Do not adopt this change without full LOO and regression evidence.

Runner: 運用/証拠/ARC26-UNIFIED/P5_HDS_D4_many_to_one_palette_LOO.py.
