# Frozen154 independent seam audit

Verdict: PASS within the teacher-only and synthetic audit scope. No blocker found. This does not establish task-score improvement or authorize integration.

## Integrity and scope

Read the previous153 independent audit and its fixed-order exhaustive geometric oracle; read unchanged anchored_rectangle.py and accepted candidate142 AGENTS.md/work-budget implementation. Read only the two supplied teacher pairs and proposal-local source/documentation. No original queries, evaluation targets, scorer, or denied047 access. No author-source or production edits, no integration, no evidence rewriting outside this audit directory.

Frozen source hashes verified before and after execution:

- proposal154-rectangle-seam-composition-20261007/seam_rectangle.py: 1e7d97da06e3c72808147c0e6e4fedd0956798733dfd3f605954695836f6d0c4
- proposal153-existing-composition-20261007/anchored_rectangle.py: 3b25da045f96cb799a4d84c0c4159fd3b39e34214212f72936ea5b87940e4ad7

## Static review

The only new semantic constraint is exact equality of facing color profiles over each whole shared contact interval, or one entire profile uniformly equal to the role's wall color. For two solid axis-aligned rectangles, contact along a given axis is one contiguous interval; grouping adjacent cells by ordered owner pair and axis therefore implements the stated interval constraint. Top-to-bottom / left-to-right ordering is consistent on both profiles. This does not allow alternating which side supplies a wall pixel.

The revised runtime consumes every completed placement record from base.assemble, even when the base output is None because old geometric outputs disagree. Every proposal gets a contact record; all seam-qualified physical arrangements remain in feasible_count, including identical outputs. All surviving outputs must agree. All structural roles are retained, and any failed role or cross-role disagreement holds. Rejecting a placement with a recorded seam violation is the declared new CSP constraint, not teacher-target-based selection. There are no target-dependent runtime branches, source/task identifiers, lookup answers, fitted numbers, or externally selected success branches. Teacher outputs are used only for exact certification in fit.

The no-role parser is unchanged: predict invokes base.observe directly. Reconstruction derives dimensions from complete rectangular paint and restores the same signed anchor. Pure state-first predict(State, grid) and fit(teachers) use a frozen program-only State. BudgetIncomplete from either geometry or seam checks returns RESOURCE_INCOMPLETE, complete=false, and no answer; fit propagates this status. The submission has no production integration to verify, so caller propagation remains a future integration obligation.

## Independent execution

Command: PYTHONDONTWRITEBYTECODE=1 python candidate154-independent-audit-20261007/audit.py

All 669 assertions passed:

- Teacher fit and all 16 teacher D4 cases.
- Every positive insufficient budget for both teacher predictions returns RESOURCE_INCOMPLETE; exact budgets succeed, covering seam-stage exhaustion as well as geometry-stage exhaustion.
- Explicit equal-profile, full wall on either side, mismatched profile, and alternating partial-wall tests.
- 360 synthetic role-level CSP cases. An exhaustive fixed-piece-order oracle tries all placement coordinates; an independent seam oracle calculates contact intervals analytically from rectangle bounds. All 527 complete geometric arrangements matched retained proposal counts. All 472 seam-valid and 55 seam-invalid arrangements matched, as did exact feasible placement sets, distinct output counts, and consensus decisions. Eight cases retained multiple distinct seam-valid outputs and correctly held. Role-level tests explicitly mock observation to isolate the declared complete-arrangement constraint; they are not claims that these roles were recovered by the parser.
- Invalid/no-role inputs retain unchanged no-role behavior.
- A real observed ten-piece input exhausts the default budget with no answer; two distinct such teachers propagate RESOURCE_INCOMPLETE from fit.
- Controlled multi-role cases verify later failure and exhaustion override an earlier successful role, while agreement succeeds. Mocks are explicitly limited to aggregation checks.
- Both source hashes unchanged after all tests.

Reproducible script: audit.py. Full machine-readable assertions and counts: evidence.json.
