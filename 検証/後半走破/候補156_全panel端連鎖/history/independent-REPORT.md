# Frozen156 independent audit

Verdict: PASS for the stated fixed whole-panel opposite-port-chain schema. Eligible for the parent's next authorized gate; no integration, original-query result, or accuracy claim.

## Frozen source and boundary

- Accepted150 base HEAD verified as `fe705e1`; its AGENTS.md was read.
- Source SHA256 verified before and after audit: `091f639523ddedc4bd11b222e7e931a1defb19e38ebd6173b5abf6b37fd1cdbb`.
- Read only proposal source/documentation/tests, its three supplied teachers, and directly reused base primitive definitions. No original queries, evaluation targets, scorer, denied047, or other task data.
- No source edits or integration. All independent artifacts are in this audit directory.

## Compact source proof

`views` enumerates every separator color returned by the generic full-uniform-line primitive. It rejects exterior lines and unequal separator-band thickness, partitions all remaining rows/columns into complete rectangles, and requires at least two equal-sized panels. Each panel must have exactly two colors excluding the separator. Every common background candidate and both axes are considered. The other color must form exactly one 4-connected component. Opposite-face foreground coordinate sets are ports; any transverse occupancy or a body with neither port excludes that axis. These are explicit prior restrictions, not learned or query-specific ranking criteria. The base primitives inspect only their input grids; partitioning skips separator bands and component connectivity defaults to four neighbors.

For any retained role, DFS starts at every panel with empty incoming port. At every prefix it visits every unused panel whose incoming set equals the preceding nonempty outgoing set. Thus by induction every and only compatible distinct-panel prefixes are explored; a depth-n sequence is retained exactly when its last outgoing port is empty. The used-index set enforces all-panel use exactly once. No color/order preference, first-success return, beam, or heuristic pruning exists. Whole unrotated panels and the input-derived separator thickness are concatenated. Every completed arrangement is validated against ARC size/color constraints and represented by its full rendered output, so interchangeable identities may agree while distinguishable chains cannot silently tie-break.

A role with zero complete chains, any invalid complete output, or more than one distinct output decisively returns HOLD. Otherwise its sole output enters cross-role consensus; disagreement returns HOLD. Early return on a witnessed failed role is a sound terminal rejection, not selective role dropping. An OK result requires successful complete enumeration and agreement of all roles. There is only one fixed model schema, so no hidden retained-model alternatives exist.

The resource limit increments on every DFS call, globally across roles. Exceeding it raises SearchIncomplete; render, fit, and predict contain no catch converting it into HOLD or a result. fit validates every supplied teacher by exact render equality and stores only a frozen schema tag. predict accepts that tag and recomputes from the new grid. Runtime source contains no task IDs, fixed answers, I/O, target access, or stored training examples.

## Focused executable evidence

- Supplied proposal test suite: 3/3 tests pass.
- Independent implementation of separator/background/axis roles, four-neighbor connectivity, exhaustive permutation arrangements, and rendering: 39/39 grid comparisons pass, including all three teachers.
- Synthetic cases include all 27 three-panel start/middle/end combinations; equivalent duplicate identities; distinguishable ambiguity; differing exact port positions; thickness two; transpose; valid input producing an over-30 output; and malformed structures.
- SearchIncomplete propagates through all three entry points (render, fit, predict).
- Five injected role collections isolate successful duplicate-role consensus, failed retained role in either order, and output-disagreeing roles in either order. Injection is test-only, not a claim that those role combinations naturally arise in a grid.
- Teacher output perturbation, no teachers, unfitted model, and wrong schema are rejected. Grid immutability checked.

Reproduce: `PYTHONPATH=candidate150-production-20261007:proposal156-existing-composition-20261007 python candidate156-independent-audit-20261007/audit.py`

This is a bounded-schema correctness audit, not evidence that this prior covers other task families or improves accepted150's 95/133 score.
