# C2-068: admitted HDS family candidates participate in consensus

Status: full matched public-training LOO PASS; production promotion, local regressions, private kernel v9, and output-format gate PASS. Official submission is waiting for the next eligible UTC day and 24-hour gate.

## Observation

C2-066 produced a positive standalone candidate union on 3 applicable folds: 2 previous exact became 3 union exact. The candidate family passed HDS teacher admission and equivalence on all 4 teacher-fit folds, yet was selected as the returned solver answer on 0/4. C2-067 changed unresolved-family veto policy alone and matched full LOO showed no score delta (16/1191 exact before and after).

## Hypothesis

A complete valid candidate from a family that passes existing HDS teacher-reproduction and equivalence admission can participate as an input-only prediction when the base HDS path has no answer. Preserve every answer already returned by the base HDS path. Combine other available HDS and admitted-family predictions by exact consensus; if they disagree, abstain. Families with no test candidate do not veto an available agreeing prediction. This applies generically to admitted HDS families; it uses no task identity, filename/hash lookup, answer map, or evaluation solution.

## Minimal isolated change

In a copied HDS connector only, add valid input-only candidates from teacher-admitted/equivalent families to the prediction consensus when the base HDS answer is absent, and preserve any base HDS answer as-is. Reuse the already public-training-tested C2-066 family as the targeted trigger.

## Acceptance

1. The matched four-fold pilot compared C2-067 policy-only against C2-068 candidate consensus: exact 3→4 (+1), fallback 1→0, wrong 0→0, regressions 0, exceptions 0. One applicable candidate produced one additional exact answer where the policy baseline abstained. Evidence: `運用/証拠/ARC26-UNIFIED/C2-068-matched-targeted-LOO.json`. The earlier exploratory comparison against root HDS is retained but superseded by this matched pilot.
2. Only if the targeted exact delta is positive with zero regressions and zero wrong increase, run matched full LOO across all 267 eligible public-training tasks / 1,191 folds.
3. Full gate passed: C2-067 policy-only 16/1191 exact versus C2-068 17/1191; delta exact +1, fallback -1, wrong 0→0, previous-exact regressions 0, exceptions 0. All 1191 folds matched. Evidence: `運用/証拠/ARC26-UNIFIED/C2-068-matched-full-LOO.json` (SHA-256 `6373afe7cc173df53f5b1c85bdbb9889a8a5650e82507c905f47b5f863b54cbc`). This satisfies the full-cohort threshold, but promotion still requires the separate source and regression gate below.
4. Do not pass held-out output to either solver; score it only after both return. Do not save task identifiers/grids or read hidden/evaluation answers.
5. Production, Notebook, and official submissions remain untouched unless a full-cohort improvement is proved and a later separate promotion gate passes.

## Separate production promotion gate

- Review the candidate family and exact C2-067→C2-068 connector diff for task-ID/hash branching, answer maps, fixed answers, or evaluation/hidden data access.
- Confirm the isolated source hashes still match the successful full LOO evidence.
- Run targeted HDS candidate-collection and ARC2 submission-format/safety regressions against the isolated candidate, then promote only those exact verified source bytes if they pass.
- Keep Notebook build, Kaggle run, and official submission as separate later gates; the local training LOO is not an official score.


## Promotion and Notebook gate update (2026-10-24)

- The C2-066 family and exact C2-067→C2-068 connector diff passed source audit; no task identity/hash branching, answer map, fixed output, or hidden/evaluation runtime access was found.
- Promoted the exact LOO-scored bytes: `接続/ARC2/HDS接続.py` SHA-256 `6ea7e6eceffa0c22407c7ea76ac58da99212ae00eb5b5fc90492ed7ece7d0135`; added family module SHA-256 `ae7364556c21bd04d22043138138c054a4a71d0a7a67ba12d2052b15205d4e3b`. The prior production connector is retained at `運用/証拠/ARC26-UNIFIED/C2-068-production-before-promotion-HDS接続.py` (SHA-256 `d1b31e1c39aac62e99b86a1bbf267725e5306a13f54fced6690e67e133345f55`).
- Targeted HDS candidate collection passed (1 test); submission/safety regression command passed all 18 tests in 7.49s; `py_compile` passed.
- Private Notebook build `出力/Kaggle/arc2-codex-main-baseline-v1/v7` uses source commit `dae0a5dbe124a0c4a01bd69a26dda0036d0379e0+dirty`, 275 whitelisted source files, public training material only, internet disabled, and payload SHA-256 `6456d952d8d3213cfd14e8dc9548af2416268fa48a8dd39a72b9a6aef69736bb`. Notebook SHA-256 `6af02e34b8bd71ac06339579266c7928f2dd7cfe465c7891184f941e35d94f45`.
- Kaggle accepted it as kernel version 9 (the remote version number advanced beyond the local v6 run record); status was `KernelWorkerStatus.RUNNING` at 2026-10-24 22:45:51 UTC. This is a private run, not an official competition submission or score. Output and `submission.json` validation remain pending.
- Gate evidence: `運用/証拠/ARC26-UNIFIED/C2-068-production-promotion-gate-20261024T224551Z.json` (SHA-256 `6a1dff43fbeee3771106370c9a8fcef09886f58672454472d12dcbf477c845b9`).


### Private kernel v9 result (2026-10-24)

- Kaggle kernel v9 completed; audit generated at `2026-10-24T22:48:23.518844+00:00`, with `source_commit` `dae0a5dbe124a0c4a01bd69a26dda0036d0379e0+dirty`.
- It emitted 240 tasks / 259 test examples. `fallback_count` is 254; this is not an accuracy measure and was not counted correct. No private correctness score was measured.
- The production `提出検査` validated the recovered `submission.json` against the official `arc-agi_test_challenges.json` inputs only. Challenge SHA `232264c58f825ee77327dcfc9f4e5cb2f83b8d997eb69032be1bf2205bbe1a83` matched the kernel audit. Submission SHA `c34dcdd39e1afacba8c2fe992ffd93378c92bbbde3885a58f43f3fd02253bcb2` matched both the audit and downloaded file. No evaluation solutions were read or persisted.
- Output evidence: `出力/Kaggle/arc2-codex-main-baseline-v1/v7/remote-output-v9/output-validation.json`; the official competition submit and its score remain pending.

### Preliminary official submission rules review

- The Kaggle rules page was consulted at `2026-10-24T22:54:05Z`: one submission per day, up to two final submissions, CPU/GPU notebook runtime up to 12 hours, internet disabled, and output filename `submission.json`. The overview currently lists the final deadline as 2026-11-02 23:59 UTC.
- The previous official ARC2 submission was `57576155`, received `2026-10-24T00:12:39.127000Z`, COMPLETE/public score `0.00`. The 24-hour gate is therefore no earlier than `2026-10-25T00:12:39.127000Z`; the UTC daily quota and all gates still require a live recheck immediately before submission.
- Sources: [Kaggle competition rules](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/rules), [Kaggle overview and timeline](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2). This is preliminary evidence, not the final submit-time check.
- Evidence: `運用/証拠/ARC26-UNIFIED/ARC2-pre-submit-rule-review-20261024T225405Z.json` (SHA-256 `28f6a0bc2f91b222ccefb559aaa4b441105054958fd30d3c38e1fe083c3a8ce1`).

### Official submission and output follow-up — 2026-10-25

The pending sentence in the earlier v9 section is superseded: submission **57611018** for this v9 output is `COMPLETE`, public score **0.00**, observed at **2026-10-25T11:34:18Z**. Previous submission 57576155 was also 0.00 (official score delta 0.00). This does not measure item-level correctness.

The recovered v9 audit has 240 tasks / 259 test examples and **254** fallbacks, all `solver_hold` with solver status `断定保留`. Detailed HDS hold causes are unavailable in this audit. Fallbacks are not counted correct. Submission SHA `c34dcdd39e1afacba8c2fe992ffd93378c92bbbde3885a58f43f3fd02253bcb2`; audit SHA `e4c430609cf6cfef2b044980d6450bae9743360dfc1d2f3889da049729c9cd48`; validation SHA `943fcb1b01e3ea0c61989f9f0e01749ad4ccdfe7ad37988750461c5d76442aa1`. Official history evidence `運用/証拠/ARC26-UNIFIED/official-history-20261025T113418Z.json`; P5 aggregate follow-up `運用/証拠/ARC26-UNIFIED/P5_ARC2_v9_fallback_followup_20261025T113418Z.json` (SHA `b2d5eb25b6f988aaab5380b6f5f88be37fb6c56a1d31497e3fecac51144a4c99`).

Public-training matched LOO remains exact **16→17** (+1), fallback **1175→1174**, wrong **0→0**, regressions **0**. The official score remains 0.00, so no score improvement is established. Continue the same C2-062 full LOO worker; do not duplicate it or promote based on fallback counts.