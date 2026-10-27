# P5: task-local training-proven candidate pool — full LOO

Observed 2026-10-24 07:06 UTC. **Decision: reject; no production change.**

## Hypothesis

For alternative collection only, include a mechanism's candidate when it exactly reproduces every remaining public-training example, even when HDS global equality admission is false. Keep the normal HDS answer behind the original equality gate. The experiment patched a temporary copy of `接続/ARC2/HDS接続.py`; repository solver code was not changed.

## Previous / current / delta

| Measure | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| LOO folds | 1,191 | 1,191 | 0 |
| HDS first-answer rows | 16 | 16 | 0 |
| HDS first-answer exact | 16 | 16 | 0 |
| Folds with any distinct alternative | 1 | 1 | 0 |
| Raw candidate-family votes | 17 | 17 | 0 |
| One-vote second-guess exact / wrong | 1 / 0 | 1 / 0 | 0 / 0 |
| First answer or one-vote second guess exact | 17 | 17 | 0 |
| Elapsed seconds | 1,600.275 | 1,628.948 | +28.673 (+1.791%) |

The only distinct candidate seen by the current pool was already present in the previous pool. No additional candidate came from a fully training-reproducing mechanism outside the HDS equality gate. The first-answer row and exact totals match the previous full run; source inspection also confirms the ordinary HDS answer remains gated by the unchanged equality-admission check. The baseline report did not record its Python package versions, so the timing delta is retained as an observed run-to-run measurement, not a controlled performance claim.

## Conditions and evidence

- Public ARC-AGI-2 `training` split only; 267 eligible tasks, minimum 3 teacher examples, 0 prior examples. Each held-out output was scored only after `課題を解く` returned.
- `fallback_as_correct=false`; no evaluation-split solutions were read; task IDs and grids were not saved.
- Previous and current full runs use the same 1,191 folds, training manifest SHA-256 `10a0146ab6374f18f44a770b37154ccb6d579fddb9a321eb3bf936666bc85aa8`, and production HDS source SHA-256 `d1b31e1c39aac62e99b86a1bbf267725e5306a13f54fced6690e67e133345f55`.
- Current process: project `.venv`, Python 3.12.10, NumPy 2.3.5, SciPy 1.17.0. SciPy emitted a nonfatal warning that the `threads` option is passed through to HiGHS; the run exited 0.
- Runner SHA-256 `0db3b6a9a4637fcc477890bc1733242469348860468c0ea49eab6d75358ac725`; temporary patched file SHA-256 `ee81956c8a0fd4afc9d5dc5dacd8740fbeaa7c6f59e10055112e9ea5d4fbc7fa`.
- Previous runner SHA-256 `5a459dd7cdc3136011f050b0495f9faece932411706e134474a81bf283e1c23e`; previous result SHA-256 `37e33e116155a833df01991c49f44ddfef218818d603de340e4cabe6519b5a28`; current result SHA-256 `3991f1a403cbaad3f6718b4cd9b814b1d5923a5b49f95552d140280f37fa7f75`.

Raw aggregate: [P5_HDS_train_proven_candidate_LOO.json](P5_HDS_train_proven_candidate_LOO.json). Previous baseline: [P5_HDS_raw_candidate_LOO.json](../ARC2_公式スコア起点_20261024/P5_HDS_raw_candidate_LOO.json).
