# Candidate 150 revised-source independent audit

Verdict: **PASS for the bounded teacher/synthetic audit and the requested failure-propagation correction.** This is not a production accuracy or adoption claim.

Frozen source SHA-256: a3568dd28202b318494f843b5f882cf5a283e3e4f7c3b2e9bc3d87e73f0f4b88.
Base remains candidate142-production-20261007 fa39a567b17eb94b04312dc3bcddbb263e8b17cb.
Original source archive verified as f2759c8e92f0ce5de61ff957cf6dc22cada4bee8dc073074c0d227fdaa83960e. The original audit verdict and evidence remain untouched in the parent audit directory.

## Changed behavior

The source diff changes only completed-cover failure handling. Cue overlap now returns failure instead of skipping a cover. Ownership failure, an outgoing ray, and conflicting receiver assignments now have explicit failure reasons and return an empty scene set. Existing accumulated successful scenes cannot conceal a later failure. The finite model class, fitting enumeration, teacher-output matching, roles, transfers, and cue-turn behavior are unchanged.

## Rechecked evidence

- All 26 previous independent checks pass against the revision, including all four teachers, exact 16 retained models, both unobserved lower corners HOLD, simultaneous transfer, palette refits, retained-model failure, incomplete-resource abort, and exception propagation.
- All 26 author tests pass, executed from copies under this revision audit directory so author artifacts are not overwritten. Existing-view incompatibility checks were included.
- Six additional checks pass: original two-cover counterexample now fails parsing with eligible_cover_ray_out_of_bounds; all 16 retained models fail and prediction HOLDs; reordered direction enumeration processes a successful cover before the failed cover and still HOLDs; distinct payloads targeting the same connected region fail with eligible_cover_assignment_conflict; prediction of that conflict HOLDs; original archive hash matches the original audited pin.

No remaining confirmed failure-propagation gap found. Cue-overlap and ownership branches were reviewed statically; the direct executable synthetic regressions exercise outgoing-ray and assignment-conflict failures, plus success-before-failure ordering.

## Scope

Only four supplied teachers, their palette permutations, existing pure helper views, and synthetic grids. No original queries, hidden targets, denied047, scorer, evaluation, integration, or source edits. No model pruning, task-ID routes, runtime output patches, or new I/O introduced by the revision.

## Reproduction

Use PYTHONDONTWRITEBYTECODE=1 and PYTHONPATH=candidate142-production-20261007:proposal150-existing-composition-20261007 from the workspace root, then execute this directory's audit.py, test_region_commands.py, and test_revision.py. Results are results.json, test-evidence.json, and revision-results.json respectively.
