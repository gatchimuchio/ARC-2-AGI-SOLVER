# Frozen158 independent exact-pruning audit

Verdict: PASS within the declared frozen155 model and bounded teacher/synthetic audit. No blocker found. This does not establish query completion, task-score improvement, or production integration.

## Exactness proof

155's unchanged observer admits only filled, axis-aligned rectangles, with conserved disjoint ownership. A pair of already placed whole rectangles can share at most one positive-length horizontal or vertical boundary interval. `fixed_contact` computes that complete interval, oriented top-to-bottom or left-to-right, and samples its profiles in precisely the row-major order used by unchanged154 `certify_contacts`. Reverse orientation recurses once with swapped pieces; corner-only touching yields no contact. The equality-or-one-whole-profile-wall predicate is identical, including the rule that the wall test applies to the shared interval rather than the rectangle's entire edge.

The existing placement predicate forbids overlap and never changes a placed rectangle. Therefore no extension can remove, shorten, recolor, or otherwise repair a failing pair contact. Every rejected prefix has no feasible completed extension. Conversely, every globally seam-valid placement has passing contacts at each prefix and cannot be removed by the new test. At each insertion the new rectangle is checked against every earlier rectangle, so all pairs in a completed placement were tested. The shape loop, host placement, first-empty-cell rule, remaining-piece order, outer-wall/overlap/bounds conditions, and exhaustive traversal are unchanged. Thus the ordered sequence of seam-feasible completed placements is preserved; only seam-invalid branches are omitted. Original154 certification is still applied at completion.

The observer is literally the imported155 function. AST comparison verifies that prediction/role aggregation is identical to155 after substituting the assembler call, and that fit is identical. All retained roles remain mandatory; within-role ambiguity, role failure and cross-role disagreement still HOLD. No first-success or partial-model answer was added. Diagnostic outer-only proposal counts and rejection/work details intentionally differ; these are not a change to the completed feasible model.

## Resource behavior

The same 100000 maximum and validation apply. Existing charges remain and new pair/profile checks are charged to the same meter. A single enclosing BudgetIncomplete handler covers observation, geometry and final seam certification, returns RESOURCE_INCOMPLETE with complete=false and no output or partial role results. Fit propagates this status. Exhaustion can happen at different work points and the added checks need not improve every instance; semantic parity is asserted when both runs complete, not resource-status parity at every smaller budget. This is a work-unit budget, not a full accounting of every Python operation or wall-clock limit.

## Bounded replay

Run: `PYTHONDONTWRITEBYTECODE=1 python candidate158-independent-audit-20261007/audit.py`

- All author's 22 parity fixtures and 37 complete-proposal contact comparisons replayed. Parsed replay evidence exactly matches the author's saved evidence.
- Teachers: 2/2 exact and FIT. Author cases include all teacher D4 transforms, invalid/matching/wall seams, six equivalent outputs, six disagreeing outputs, and multiple ownership alternatives.
- Three additional contact probes: reversed vertical partial interval with wall semantics; reversed horizontal one-cell failing seam; corner-only non-contact. Each compared against full painted154 certification.
- Budget=1 control, a real just-below-completion budget, interruption after the first certified model, and explicit fit shortage propagation all pass. The last two are isolated runtime fault-injection tests, clearly separated from actual resource measurements; no source files were modified.
- 153/154/155/158 source and author's test hashes verified unchanged before/after. The author's harness was executed without file changes, with only its evidence output destination redirected into this audit directory.

## Boundaries and hashes

Read only the specified source, prior155 audit report, applicable AGENTS instructions, author test/evidence, and153 teachers-only fixture. No original query, target, scorer, denied047, or resource-incomplete query artifact was read or run. No production/source edits, integration, commit, push, or score claim. Audit artifacts are confined to this directory.

- 153 anchored_rectangle.py: 3b25da045f96cb799a4d84c0c4159fd3b39e34214212f72936ea5b87940e4ad7
- 154 seam_rectangle.py: 1e7d97da06e3c72808147c0e6e4fedd0956798733dfd3f605954695836f6d0c4
- 155 touching_rectangle.py: 121d31d0921c9383b769b3b6515aa669259f4aca397c82da70760ba3a6889357
- 158 propagated_rectangle.py: cf9ca4dc1fe6a4bfb077e09cdf97dc7f5cb27e9f2cf93b2d5363e49b992d72ce
- Author test_parity.py: fa5baba06adad066b802873b83c0f1f35d845e0b8a321ea56da5872ef6ced404
