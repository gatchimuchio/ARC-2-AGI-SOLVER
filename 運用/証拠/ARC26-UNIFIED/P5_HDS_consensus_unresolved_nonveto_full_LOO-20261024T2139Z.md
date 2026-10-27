# C2-067 Full Matched LOO Result

- Observed: 2026-10-24 21:39:56 UTC
- Data: public ARC-AGI-2 training split; 267 tasks / 1191 matched folds.
- Previous HDS first answer: 16 exact, 1175 fallback, 0 wrong; 16 answers / 16 union exact.
- Current unresolved-family non-veto policy: 16 exact, 1175 fallback, 0 wrong; 16 answers / 16 union exact.
- Delta: exact 0, fallback 0, wrong 0, newly answered 0, regressions 0; all 1191 folds matched.
- Runtime: previous 1510.437 s, current 1476.022 s (-34.415 s). Runtime alone does not satisfy the accuracy gate and is not treated as a solver gain.
- Current hold-reason counts are overlapping occurrences, not disjoint folds: insufficient observations 1171; quarantined unresolved principles 44; D4 test candidate unresolved 3; foreground translation exhausted by HDS 1.
- No evaluation solutions were read; no held-out output was passed to either solver; fallback was not counted correct; no task IDs/grids were saved.
- No production or Notebook change, official submission, or rerun occurred. Base HDS SHA-256 remains `d1b31e1c39aac62e99b86a1bbf267725e5306a13f54fced6690e67e133345f55`.

**Decision: REJECT.** The predeclared gate requires a positive exact delta with no regressions or wrong-count increase. The full-cohort delta is zero, so the policy is not adopted.

Evidence JSON: `運用/証拠/ARC26-UNIFIED/P5_HDS_consensus_unresolved_nonveto_full_LOO.json` (SHA-256 `7ce5bd1b82201121d56e3e755d18c98c8bfa3bf32ecdb06f2220971fcd9497ff`).
Runner: `運用/証拠/ARC26-UNIFIED/P5_HDS_consensus_unresolved_nonveto_full_LOO.py` (SHA-256 `f7386c4f91dc280875fe618564380573353d41de0db779526b6a1a8a45a1593a`).
Training manifest SHA-256: `10a0146ab6374f18f44a770b37154ccb6d579fddb9a321eb3f936666bc85aa8`.