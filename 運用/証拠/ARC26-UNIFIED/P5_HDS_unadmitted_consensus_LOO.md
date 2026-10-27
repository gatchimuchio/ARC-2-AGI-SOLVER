# P5: unconfirmed HDS consensus as attempt-2 candidate — full LOO

Observed 2026-10-24 07:35 UTC. **Decision: reject; no production change.**

## Hypothesis

When the ordinary HDS result is HOLD because no principle is equality-admitted, a valid raw output grid may still be unanimous across all HDS output predictions. Test whether that unique consensus can serve only as a distinct `attempt_2` candidate while preserving the original answer and HOLD gates.

The experiment added a `raw_consensus_candidate` observation and candidate-pool entry only in a temporary copy of `接続/ARC2/HDS接続.py`. No production solver file was changed.

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
| Elapsed seconds | 1,600.275 | 1,602.707 | +2.432 (+0.152%) |

The new consensus rule emitted no additional candidate: the single existing distinct alternative and its one exact second guess were already present in the baseline. It did not improve coverage or accuracy. No fallback was counted as correct.

## Conditions and evidence

- Public ARC-AGI-2 `training` split only; 267 eligible tasks, minimum 3 teacher examples, no prior examples. Held-out outputs were scored by the parent process only after solver return.
- Evaluation-split solutions were not read. Task IDs and grids were not saved.
- Previous/current full runs have the same 1,191 folds, training manifest SHA-256 `10a0146ab6374f18f44a770b37154ccb6d579fddb9a321eb3bf936666bc85aa8`, and production HDS source SHA-256 `d1b31e1c39aac62e99b86a1bbf267725e5306a13f54fced6690e67e133345f55`.
- Current process: project `.venv`, Python 3.12.10, NumPy 2.3.5, SciPy 1.17.0. A nonfatal SciPy warning noted that `threads` is passed through to HiGHS; the run exited 0. The baseline report does not record package versions, so timing is an observed run-to-run comparison rather than a controlled performance claim.
- Runner SHA-256 `64147b7b24beb30fc0edb69d257f81637ecf915bc55056ee12b8f6c34521ed3d`; shared helper SHA-256 `0db3b6a9a4637fcc477890bc1733242469348860468c0ea49eab6d75358ac725`; temporary patched file SHA-256 `35e604b66834a39a04b881731824016120912eec3c9a6beba8be08d1481dd2b6`.
- Previous runner SHA-256 `5a459dd7cdc3136011f050b0495f9faece932411706e134474a81bf283e1c23e`; previous result SHA-256 `37e33e116155a833df01991c49f44ddfef218818d603de340e4cabe6519b5a28`; current result SHA-256 `65dd610a60b212bcb46e464529f1acfb9fbc0819ad95eb91d5dfd017c06815cc`.

Raw aggregate: [P5_HDS_unadmitted_consensus_LOO.json](P5_HDS_unadmitted_consensus_LOO.json). Previous baseline: [P5_HDS_raw_candidate_LOO.json](../ARC2_公式スコア起点_20261024/P5_HDS_raw_candidate_LOO.json).
