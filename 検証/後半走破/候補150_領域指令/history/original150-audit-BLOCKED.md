# Candidate 150 independent frozen-source audit

Verdict: **BLOCKED under the requested strict no-failure-dropping contract.** Most claimed semantics are verified, but a concrete synthetic case drops a failed exact ownership interpretation and emits from the surviving one.

## Scope and identity

- Base: candidate142-production-20261007, git fa39a567b17eb94b04312dc3bcddbb263e8b17cb; AGENTS.md read; working tree clean.
- Frozen region_commands.py SHA-256: f2759c8e92f0ce5de61ff957cf6dc22cada4bee8dc073074c0d227fdaa83960e, verified before and after.
- Only four supplied teachers and newly constructed synthetic grids used. No original query, hidden targets, scorer, denied047, integration, or production-source edits.

## Blocking finding: failed exact-cover interpretations discarded

region_commands.py lines 85–92 marks a completed ownership cover failed for bad ownership, an outgoing ray, or conflicting assignments, then `continue`s. Line 72 also skips cue-overlap covers. Thus render's scene consensus sees only surviving interpretations.

Reproduction in failure-drop-reproduction.json and reproduce_failure_drop.py uses a 9×9 synthetic map. Eight marker cells have two complete disjoint exact covers:

1. Centers (2,2) pointing north and (3,3) pointing south. The north ray exits the grid without a receiver.
2. Same centers pointing west and east. Both rays hit the surrounding region.

parse returns only the second cover as one scene. predict with all 16 teacher-fitted models emits an all-2 grid rather than HOLD. This is a real survivor-only result, not an injected parser failure. If failed covers are intentionally defined as impossible grammatical parses, this is a semantics-policy distinction; it still does not satisfy the requested strict no-failure-dropping behavior. Resolve that distinction before adoption, or conservatively propagate any completed-cover failure as HOLD. No code changes made by this auditor.

## Verified properties

26 independent assertions pass (results.json): all four teacher outputs; immutable teacher inputs; exactly the 16 models marker=1/cue=9/turns=(1,3,a,b), a,b∈{0,1,2,3}; unseen lower cue orientations HOLD; all four command directions; colored-center payload; simultaneous two-way exchange; preservation of a disconnected same-colored region; unowned-marker, no-marker and outgoing-ray HOLD; retained-model failure is not dropped; resource-incomplete aborts fit; dependency exceptions propagate through fit and predict; four independent palette-permutation refits; corrupt teacher no-fit; duplicate teacher no-fit.

Static inspection finds a generic T-stencil/exact-cover/region/ray-transfer implementation with a finite glyph-turn dictionary. Only marker, optional cue color, and four corner-turn choices are fitted. No task-ID, filename, hash, target lookup, hidden-output, or runtime file/network routes appear in the frozen module. Helpers are base color_components and transform_grid_by_name. Fitted runtime state contains models only, no teacher outputs or patches. All retained models are evaluated during prediction. Invalid color/cue hypotheses are eliminated during teacher fit; incomplete resource results abort rather than select survivors.

Bounded ambiguity search first examined 6,964 synthetic split-map cases, including 32 multiple-cover cases, without finding partial survival. A framed-map search found the blocking case after 41 cases. These checks establish local behavior only, not production accuracy.

## Reproduce

From workspace root:

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=candidate142-production-20261007:proposal150-existing-composition-20261007 python candidate150-independent-audit-20261007/audit.py
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=candidate142-production-20261007:proposal150-existing-composition-20261007 python candidate150-independent-audit-20261007/reproduce_failure_drop.py
