# P5: admit HDS rules with one observed condition value — full LOO

Observed 2026-10-24 09:09 UTC. **Decision: reject; no production change.**

## Hypothesis

HDS inference and validation require at least two distinct condition values before a relation can be admitted. Test whether allowing one observed condition value, while retaining minimum support and exact agreement on teacher examples, generalizes to held-out examples.

The experiment patched only temporary copies of the HDS inference and validation modules. Candidate collection used the same isolated LOO instrumentation as the baseline.

## Previous / current / delta

| Measure | Previous | Current | Delta |
| --- | ---: | ---: | ---: |
| LOO folds | 1,191 | 1,191 | 0 |
| HDS first-answer rows | 16 | 16 | 0 |
| HDS first-answer exact | 16 | 16 | 0 |
| Distinct candidate folds | 1 | 1 | 0 |
| Raw candidate-family votes | 17 | 17 | 0 |
| Top-vote second-guess exact / wrong | 1 / 0 | 1 / 0 | 0 / 0 |
| First answer or top-vote second guess exact | 17 | 17 | 0 |
| Elapsed seconds | 1,600.275 | 1,668.792 | +68.517 (+4.282%) |

The changed diversity gate produced no new candidates and did not change the first-answer aggregate. Accuracy remained unchanged, so the hypothesis is rejected.

## Conditions and evidence

- Public ARC-AGI-2 `training` split only; 267 eligible tasks, 1,191 LOO folds, minimum 3 teacher examples, and no prior examples. Held-out outputs were scored by the parent evaluator only after solver return.
- Evaluation-split solutions were not read; task identifiers and grids were not saved; fallbacks were never counted as correct.
- Previous and current runs have the same training manifest SHA-256 `10a0146ab6374f18f44a770b37154ccb6d579fddb9a321eb3bf936666bc85aa8` and production ARC2 HDS connection SHA-256 `d1b31e1c39aac62e99b86a1bbf267725e5306a13f54fced6690e67e133345f55`.
- Current runtime: project `.venv`, Python 3.12.10, NumPy 2.3.5, SciPy 1.17.0. The run exited 0; SciPy emitted a nonfatal warning that `threads` is passed to HiGHS. Baseline runtime metadata was not recorded, so timing is an observed run-to-run comparison, not a controlled performance claim.
- Runner SHA-256 `376f16d6c9b28b9af151d20b137966045c08bbd1b2723dcf58d9c3a56e7153c5`; shared candidate-collection runner SHA-256 `0db3b6a9a4637fcc477890bc1733242469348860468c0ea49eab6d75358ac725`.
- Temporary inference/validation source digest `6f3b3c49919967e0ef47e8fc3166ded06ecc7e52e50a5805a99975bd261ae50e`; combined temporary variant digest `64119599ca93d9802d07cedad739a2eb85624ee629b868ce2d3ad05b367ad3c9`.
- Result JSON SHA-256 `babf24f23655d6607a5828f29848f6dd34254b44f675fe258d0bcfaa2864aa8d`; baseline JSON SHA-256 `37e33e116155a833df01991c49f44ddfef218818d603de340e4cabe6519b5a28`.

Aggregate result: [P5_HDS_single_condition_type_LOO.json](P5_HDS_single_condition_type_LOO.json). Baseline: [P5_HDS_raw_candidate_LOO.json](../ARC2_公式スコア起点_20261024/P5_HDS_raw_candidate_LOO.json).
