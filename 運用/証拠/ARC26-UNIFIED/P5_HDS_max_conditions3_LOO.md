# P5: increase the ARC2 HDS condition bound to three — full LOO

Observed 2026-10-24 08:38 UTC. **Decision: reject; no production change.**

## Hypothesis

The HDS engine defaults to a maximum of two conditions and records higher-order relationships as unresolved residuals. Test whether the ARC2 wrapper can admit three conditions to its generic inference search while preserving the normal equality-admission and HOLD gates.

The experiment changed only `最大条件数` from 2 to 3 in a temporary copy of `接続/ARC2/HDS接続.py`. Candidate collection used the same isolated LOO instrumentation as the baseline.

## Previous / current / delta

| Measure | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| LOO folds | 1,191 | 1,191 | 0 |
| HDS first-answer rows | 16 | 16 | 0 |
| HDS first-answer exact | 16 | 16 | 0 |
| Folds with any distinct candidate | 1 | 1 | 0 |
| Raw candidate-family votes | 17 | 17 | 0 |
| Top-vote second-guess exact / wrong | 1 / 0 | 1 / 0 | 0 / 0 |
| First answer or top-vote second guess exact | 17 | 17 | 0 |
| Elapsed seconds | 1,600.275 | 1,665.518 | +65.243 (+4.077%) |

Raising the condition bound produced no new candidate and no accuracy change. The one existing exact second guess remained 1 exact / 0 wrong. With no measured gain, the hypothesis is rejected.

## Conditions and evidence

- Public ARC-AGI-2 `training` split only; 267 eligible tasks, 1,191 LOO folds, minimum 3 teacher examples, and no prior examples. The parent evaluator scored held-out outputs only after solver return.
- Evaluation-split solutions were not read; task identifiers and grids were not saved; fallbacks were never counted as correct.
- Previous and current runs have the same training manifest SHA-256 `10a0146ab6374f18f44a770b37154ccb6d579fddb9a321eb3bf936666bc85aa8` and production HDS source SHA-256 `d1b31e1c39aac62e99b86a1bbf267725e5306a13f54fced6690e67e133345f55`.
- Current runtime: project `.venv`, Python 3.12.10, NumPy 2.3.5, SciPy 1.17.0. The run exited 0; SciPy emitted a nonfatal warning that `threads` is passed to HiGHS. Baseline runtime metadata was not recorded, so timing is an observed run-to-run comparison, not a controlled performance claim.
- Runner SHA-256 `1982e5d149b7b349dd52155071f84048859f58feb1003cf1b43079ed9f6cd212`; shared candidate-collection runner SHA-256 `0db3b6a9a4637fcc477890bc1733242469348860468c0ea49eab6d75358ac725`; temporary variant SHA-256 `6e14128586cecbc38924330cd01ee40c4fa58d1ea2b7b8cc84dabc685c14798c`.
- Result JSON SHA-256 `f287f2316def0f2b584e7584705a899d8e02785ef2971f75279b2bda15e885ae`; baseline JSON SHA-256 `3991f1a403cbaad3f6718b4cd9b814b1d5923a5b49f95552d140280f37fa7f75`.

Aggregate result: [P5_HDS_max_conditions3_LOO.json](P5_HDS_max_conditions3_LOO.json). Baseline: [P5_HDS_train_proven_candidate_LOO.json](P5_HDS_train_proven_candidate_LOO.json).
