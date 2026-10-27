# C2-067 HDS consensus survives unresolved accepted families

Status: hypothesis only; production adoption is gated on matched full public-training LOO.

## Observation

C2-066 showed an existing HDS answer changing from exact to HOLD when an accepted family could not produce a candidate for a held-out input. The final result arbitration currently lets any such unresolved reason override an otherwise available HDS prediction.

## Hypothesis

An accepted family's missing or HDS-rejected test candidate should not veto other available HDS predictions when those predictions agree. Existing HDS answer admission remains unchanged, and disagreement among available predictions remains HOLD. If no prediction is available, unresolved reasons still produce HOLD.

## Minimal isolated change

In a copied HDS connector, change the unresolved-family branch so it forces HOLD only when the accepted prediction set is empty. Do not modify production sources or notebooks during this experiment.

## Evaluation gates

1. Target the four C2-066 teacher-fit folds; previous output must not regress.
2. Run matched previous/current LOO on all 267 eligible public-training tasks and 1,191 folds, with the identical public training manifest. Count fallback as incorrect and report answer/exact/wrong/fallback deltas.
3. Reject if exact answers do not improve, any previous exact regresses, wrong answers increase, or hidden/evaluation data enters the runtime.
4. If the policy helps, assess impact on actual ARC2 output and the official notebook in a separate shadow build. Do not submit until the UTC-day quota and all submission gates are rechecked.

## 2026-10-24 20:49 UTC: targeted C2-066 regression gate

The isolated overlay combines C2-066 with the proposed result-arbitration policy and evaluates all four teacher-fit folds.

- Previous/current: 3/4 exact, fallback 1/4, wrong 0; delta 0 for every metric.
- Candidate-applicable folds: previous/current 2 exact and 1 fallback across 3 folds.
- Candidate-not-applicable fold: the previous exact answer is preserved.
- C2-066 was HDS-admitted on 4/4 folds but selected as the returned answer on 0/4; it did not contribute a new exact answer.
- Exceptions: 0. Production connector and notebook unchanged.

Targeted aggregate: 運用/証拠/ARC26-UNIFIED/C2-067-targeted-C2-066-policy-LOO.json, SHA256 6096d98158fa8e59203bba08d730b2937b056bb9f1403ef687724ff37a550761.

The targeted gate passes its no-regression condition but does not establish a capability gain. Matched full LOO across 267 tasks and 1,191 folds is running before any adoption decision.

## 2026-10-24 21:39 UTC: full matched LOO rejected

C2-067 completed all 1191 matched public-training folds across 267 tasks. Previous and current both produced 16 exact, 1175 fallback, and 0 wrong; delta exact=0, fallback=0, wrong=0, newly answered=0, regressions=0. Runtime moved from 1510.437 s to 1476.022 s, but runtime alone does not meet the score gate. Hold-reason occurrences overlap: 1171 insufficient observations, 44 unresolved quarantined principles, 3 unresolved D4 test candidates, and 1 foreground-translation HDS exhaust. No evaluation solutions, task IDs, or grids were read/saved; production and Notebook remain unchanged. C2-067 is rejected and not adopted. Full result: `運用/証拠/ARC26-UNIFIED/P5_HDS_consensus_unresolved_nonveto_full_LOO.json`; report: `運用/証拠/ARC26-UNIFIED/P5_HDS_consensus_unresolved_nonveto_full_LOO-20261024T2139Z.md`.