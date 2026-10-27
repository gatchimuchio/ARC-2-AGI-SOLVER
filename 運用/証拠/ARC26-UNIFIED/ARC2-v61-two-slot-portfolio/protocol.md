# Frozen v61 two-slot portfolio — local experiment protocol v1

This artifact is a hypothesis for a future local candidate. It does not change the frozen next official candidate, current connector tree, Kaggle records, AGENTS.md, or 制御/現在状態.json. No performance result is claimed.

## Parent and intervention

- Parent: exact `v61-kaggle-staging-20261026/bundle.zip`, SHA-256 `06f7e19da4f1b6fc0059a4aef03833fd9074bc725204a3f9c5c1b33523e0fbee`.
- Only the bundled `接続/ARC2/Kaggle提出.py` changes. All HDS, memory, candidate-generator sources and training-prior data remain byte-identical.
- Run the original v61 candidate selection first, and freeze its normalized attempt_2.
- Eligible only when the original HDS answer is HOLD (`None`), legacy attempt_1 is the input copy, and v61 attempt_2 is already a non-input generated candidate.
- Generate alternative proposals from existing v61 models fitted from the same task's train pairs. Select a valid non-input grid that differs from v61 attempt_2 for attempt_1. Preserve v61 attempt_2.
- HDS adoption/state is unchanged. The original `answer=None`, status and HOLD reasons remain in the worker response; materializing an external proposal does not convert HOLD into an HDS answer.
- Existing legacy candidate pairs, nonidentity attempt_1, input-copy attempt_2, malformed output and worker-error cases remain outside the intervention.

## Fixed target-independent policy

Priority is frozen before evaluation: teacher-pair consensus, object extraction, object outlier, object palette, local cell context, simple unique transform, composite geometry. Ties use lexicographic grid order only after structural deduplication. Task ID, filename, hash, held-out output and challenge solutions do not enter ranking.

The generators retain their v61 train-support requirements. Teacher-pair consensus requires one supporting pair when there is only one fitted teacher-pair model, otherwise at least two; the winner must be unique. It does not mean all teacher pairs were reproduced. Other proposal records identify the existing model fit policy. Repeated-panel partial-fit proposals are deliberately excluded from new attempt_1 because their existing v61 source documents attempt_2-only use. The selected v61 attempt_2 may still be such a proposal and remains preserved.

## Instrumentation and audit semantics

- Per eligible HOLD row: source calls, valid proposals, source errors, distinct nonidentity pool size, alternatives to v61 attempt_2, selected family/support policy, actual materialization and extra generation time.
- No raw proposal grids or targets are added to audit records. Worker response carries only the selected prediction needed to write submission.json.
- Legacy `fallback_count` continues counting primary HOLD/worker-error provenance. `true_input_copy_fallback_count` separately counts actual attempt_1 input copies.
- `solver_hold` remains present even after external portfolio materialization. `attempt1_source` distinguishes `external_portfolio` from `input_copy_fallback`.
- `v61_attempt2_preserved` is asserted after legacy normalization and summed in the audit. Matched runtime comparison must additionally prove actual attempt_2 preservation, including timeout/error effects.

## Proposed matched public-training evaluation — not executed yet

1. Use the exact frozen v61 payload as previous and this artifact as current. Do not substitute the current worktree HDS connector.
2. Use public training only, grouped task LOO with identical support examples, input-only held-out queries, prior leakage exclusions, order, seed and CPU/RAM/wall limits. Hold-out outputs remain solely in the scorer after both predictions finish.
3. First collect eligibility/pool counts without reading targets. Then score every fold, retaining timeouts/errors in the denominator. Record primary-HOLD provenance and actual input-copy fallback separately.
4. Compare attempt_1, attempt_2 and pass@2 previous/current/delta. Require attempt_2 equality on every completed paired fold, no changed row outside eligibility, and no task-ID/hash-specific branch. Report identity-output regressions rather than assuming input-copy fallback cannot coincide with truth.
5. Measure candidate-generation overhead, timeout/worker-error deltas and total runtime. Extra proposal work can cause a timeout even though the deterministic output selector preserves attempt_2; this is an explicit regression risk.
6. Repeat the same frozen candidate and cohort to check reproducibility. A broader same-condition regression cohort is required before adoption.
7. Adopt only if measured pass@2 improves with zero regressions, no new runtime failures, and the official score workflow remains intact. This build, syntax compilation, candidate count or changed attempt slot is not a performance improvement.

## Static build

`python 運用/証拠/ARC26-UNIFIED/ARC2-v61-two-slot-portfolio/build.py`

The builder verifies exact parent/member hashes, validates the parent file manifest, compiles source text without executing solver modules, emits a local payload/launcher and unified diff, and refuses to overwrite an existing build. It emits no Kaggle metadata or Notebook and performs no network operation.
