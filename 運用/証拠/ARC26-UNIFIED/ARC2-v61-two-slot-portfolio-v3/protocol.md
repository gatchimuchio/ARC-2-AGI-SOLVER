# Frozen v61 two-slot portfolio — local experiment protocol v3

This artifact is an unmeasured hypothesis for a future candidate. It does not change the frozen next official candidate, active connector tree, Kaggle records, AGENTS.md, or 制御/現在状態.json. Sibling v1 and v2 builds are preserved. Build and syntax compilation do not establish improved ability. V2's matched 20-task result did not establish gain and is not adopted.

## Parent and scope

- Parent: exact `v61-kaggle-staging-20261026/bundle.zip`, SHA-256 `06f7e19da4f1b6fc0059a4aef03833fd9074bc725204a3f9c5c1b33523e0fbee`.
- Only bundled `接続/ARC2/Kaggle提出.py` changes. Other 282 payload members, including HDS, memories and candidate-generator source, remain byte-identical.
- Execute legacy v61 selection first and freeze its normalized attempt_2 before modifying attempt_1.
- Eligible only when original HDS answer is HOLD (`None`), there is no legacy candidate pair and legacy attempt_1 is input copy. Both-copy and nonidentity-second rows have separate fixed provider scopes. Error/malformed rows remain outside the intervention.
- New attempt_1 must differ from both input and frozen attempt_2. Preserve original answer=None, status, HOLD reasons and actual normalized attempt_2. This is an external portfolio prediction, not an adopted HDS answer.

## Full-current-train qualification

New attempt_1 uses only a provider whose same fitted predictor reproduces every current support input/output pair exactly. Qualification records `train_exact`, `train_total`, `qualified`, `fit_error_type`, `validation_error_counts`, `validation_invalid_grid_count` and `validation_mismatch_count`. `train_total` must equal the support count and be positive. Fit errors, invalid training grids, mismatches and validation exceptions all reject the provider. Rejected qualification is cached and never calls that provider on test queries.

Each provider is lazily constructed in a separate portfolio-only instance, including separate ObjectExtractionCandidate instances for its four methods. It receives a copy of current train pairs. Each qualification call receives a training input only, and the output is compared afterward. The exact same bound predictor is used for every validation input and later test query; no per-query refit is requested. The simple transform provider fits its entire ensemble once and retains the frozen unique-output rule. Providers may perform their original internal lazy model fitting during validation, recorded as validation time.

Qualification runs once per provider per task and is reused across all test rows. Portfolio training/query calls cannot mutate the baseline v61 model instances or their caches. Baseline fit and candidate selection are unchanged. Timing and total task timeout can nevertheless affect overall output availability, so actual multi-test attempt_2 equality must be measured.

Legacy teacher-pair consensus remains available for frozen attempt_2 under its original partial support rule. A NEW teacher-pair attempt_1 is accepted only after the full-current-train qualification. Repeated-panel partial-fit proposals remain excluded from NEW attempt_1, consistent with their frozen attempt_2-only source restriction.

## Fixed target-independent ranking

For nonidentity legacy attempt_2, priority remains fixed before scoring: teacher-pair consensus, object extraction, object outlier, object palette, local cell context, simple unique transform, composite geometry. For BOTH-COPY rows, query ONLY composite geometry; the six other exposed provider methods already fill an empty legacy second slot whenever they produce a nonidentity proposal. Composite geometry instead enters the shared unique-plurality pool and can be discarded on a top-vote tie (frozen wrapper lines265–279, unique selector70–91). Whether any such row produces a useful held-out prediction remains unmeasured.

The per-task registry may configure a known, unique, nonempty ordered subset. Requested provider subsets must respect the fixed global order. Both-copy selector calls reject every subset except exactly composite geometry. Other lazy factories remain unfitted on that path; if a later test row has a nonidentity second slot, all seven providers may then be requested and prior qualification is reused.

After structural deduplication, choose the lowest fixed-priority-index qualifying nonidentity proposal distinct from frozen attempt_2. Any tie uses lexicographic grid order. Task IDs, filenames, hashes, held-out outputs and evaluation/hidden solutions never enter ranking. Runtime metadata may identify rows for evidence but never selects answers. The formatter rechecks scope labels, requested families, selected family and all-train qualification. Both-copy keeps the original input-copy attempt_2, protecting that baseline guess; timeouts remain an output-loss risk.

## Instrumentation and failure boundaries

- Every source records qualification, current-query generated/valid status, query exception type and numeric model evidence. The selected qualification is copied to `selected_qualification`; formatter rechecks it against actual support count before materializing.
- `eligibility_scope` distinguishes `both_copy_composite_only` from `noncopy_second_seven_provider`. `requested_provider_families` and actual `sources` must match the relevant fixed allowlist. The evaluator counts provider-scope invariant failures and all actual attempt_2 differences.
- Per-source timing reports `qualification_attempted`, `qualification_cached`, `fit_seconds`, `validation_seconds`, `query_seconds`. Fit/validation totals are charged once per provider/task; later cached rows report zero incremental fit/validation cost. Task-context setup has separate `task_context_setup_seconds`. `extra_seconds` includes setup, qualification and selection overhead.
- Diagnostics carry counts, errors and family names, no raw train grids/targets or proposal pools. Worker response carries the selected prediction required by submission.json.
- Legacy fallback_count retains primary HOLD/worker-error provenance. `true_input_copy_fallback_count` records actual attempt_1 input copies. HOLD remains even when an external portfolio answer is materialized.
- `v61_attempt2_preserved` asserts exact legacy normalization. Runtime matched evaluation must also detect changed outputs caused by timeouts/errors and compare every test row.
- No output/score improvement is established until matched previous/current/delta is measured. Input-copy fallback can coincide with truth, so changed attempt_1 may regress and must be scored explicitly.

## Proposed matched public-training evaluation — not executed by this build

1. Previous is exact frozen v61; current is this payload. Do not substitute active-worktree HDS.
2. Use grouped task LOO on public training with identical support/query, prior exclusions, order, seed and time/resource limits. Held-out targets exist only in parent scorer after both predictions finish. Generic prior may be disabled identically on both sides if its source-task provenance is stripped; template examples require parent-side held-out-task exclusion.
3. First run pure invariants and preflight. Require `new_attempt1_training_requirement=all_current_train_exact`, the v3 scope manifest, selected qualification exact/total equal actual support, no changed row outside eligibility, independent portfolio models, and composite-only calls on both-copy rows.
4. Score all folds, retaining timeouts/errors in denominator. Report attempt_1, attempt_2, pass@2 and primary-HOLD versus true input-copy fallback separately. Record previous/current/delta, regressions and every actual baseline/candidate attempt_2 mismatch across multi-test tasks.
5. Measure setup, provider fitting, validation, test-query and total wall costs; report timeout/worker-error changes. A preserved selector can still lose output under a task timeout.
6. Use the same original20-task cohort/seed20261026 as v2 for the first comparison; keep cohort construction, source labels and prior exclusions unchanged. Repeat the identical candidate/cohort for reproducibility and expand same-condition regression only after a useful initial result. Adopt only measured improvement with no regressions or new failures. Leave frozen official candidate unchanged until an explicit adoption decision.

## Static build

`python 運用/証拠/ARC26-UNIFIED/ARC2-v61-two-slot-portfolio-v3/build.py`

The builder verifies exact parent/member hashes and the parent manifest, compiles text without importing solver modules, emits the local payload/launcher and unified diff, and refuses to overwrite an existing build. It emits no Kaggle metadata, performs no network operation and runs no solver/LOO job.
