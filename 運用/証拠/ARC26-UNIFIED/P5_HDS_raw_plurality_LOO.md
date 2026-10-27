# P5: raw HDS plurality as an attempt-2 candidate — full LOO

Observed 2026-10-24 08:08 UTC. **Decision: reject; no production change.**

## Hypothesis

When the ordinary HDS result is HOLD because no principle is equality-admitted, a valid raw output grid with a unique plurality of at least two predictions might be useful as an `attempt_2` candidate. The experiment preserved the normal answer and HOLD gates and changed only candidate collection in a temporary copy of `接続/ARC2/HDS接続.py`.

## Previous / current / delta

| Measure | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| LOO folds | 1,191 | 1,191 | 0 |
| HDS first-answer rows | 16 | 16 | 0 |
| HDS first-answer exact | 16 | 16 | 0 |
| Folds with any distinct candidate | 1 | 1 | 0 |
| Raw candidate-family votes | 17 | 17 | 0 |
| One-vote second-guess exact / wrong | 1 / 0 | 1 / 0 | 0 / 0 |
| First answer or top-vote second guess exact | 17 | 17 | 0 |
| Elapsed seconds | 1,600.275 | 1,865.054 | +264.779 (+16.546%) |

The plurality rule added no new candidate. The existing single candidate and one exact second guess remained unchanged; no fallback was scored as correct. With no accuracy gain and higher observed runtime, the hypothesis is rejected.

## Conditions and evidence

- Public ARC-AGI-2 `training` split only; 267 eligible tasks, 1,191 LOO folds, minimum 3 teacher examples, and no prior examples. Held-out outputs were scored in the parent evaluator only after solver return.
- Evaluation-split solutions were not read; task identifiers and grids were not saved.
- Previous and current runs have the same training manifest SHA-256 `10a0146ab6374f18f44a770b37154ccb6d579fddb9a321eb3bf936666bc85aa8` and production HDS source SHA-256 `d1b31e1c39aac62e99b86a1bbf267725e5306a13f54fced6690e67e133345f55`.
- Current runtime: project `.venv`, Python 3.12.10, NumPy 2.3.5, SciPy 1.17.0. The run exited 0; SciPy emitted a nonfatal warning that `threads` is passed to HiGHS. Baseline runtime metadata was not recorded, so timing is an observed run-to-run comparison, not a controlled performance claim.
- Runner SHA-256 `c86e76bb9f989f5e7bb656f86b69fc12a62aaa5e46db5037e683a9bbe2c5d6c2`; shared candidate-collection runner SHA-256 `0db3b6a9a4637fcc477890bc1733242469348860468c0ea49eab6d75358ac725`; temporary variant SHA-256 `a6ad0117a6cfa94fff71520ee2e75aca5b433ca469f0cba84a1c0741dfb5901a`.
- Result JSON SHA-256 `659be5937e20ba3d11562f15e7bad8c3e6c095b9dfe29a246764937f6216017b`; baseline JSON SHA-256 `3991f1a403cbaad3f6718b4cd9b814b1d5923a5b49f95552d140280f37fa7f75`.

Aggregate result: [P5_HDS_raw_plurality_LOO.json](P5_HDS_raw_plurality_LOO.json). Baseline: [P5_HDS_train_proven_candidate_LOO.json](P5_HDS_train_proven_candidate_LOO.json).
