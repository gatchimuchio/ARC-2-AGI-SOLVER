# 195 independent source-ready gate audit

Verdict: PASS for teacher-fitted state only. This is a source-ready gate, not a query result or promotion claim.

Audited pure source: boundary_table.py, SHA256 0e1e9de98003f0059036f88e94408c2857d2632203b987dfc83957506815e133.
Base: arc2-current109/source. Teachers: arc2-current99/teachers-only/dbff022c.json, train only.
Read the full purpose-reset instructions and AGENTS before beginning. No query, RESULT.md, pure-evidence.json, image, or official answer read. No canonical source edited.

## Semantics and scope

- Runtime uses input geometry only. No task identifier, filename/hash routing, answer map, fixed output, teacher pixel table, or runtime external I/O.
- Complete mixed C8 non-background rectangles with two rows or two columns are retained as table candidates. Every table survives role enumeration; within each table every lane tied at the minimum corresponding canvas-edge distance survives. A 2x2 table can retain four lanes.
- Boundary-nearest key direction is an explicit prior. Teacher fit validates that prior; three teachers do not establish it as the uniquely identifiable rule.
- Each role uses original-input monochrome C8 components and C4 complement cavities within object bounding boxes. Components touching the selected table are skipped. Foreign cavity occupancy is a role failure. This includes a disconnected same-color object nested inside a cavity.
- Writes are simultaneous via the existing merge_proposals primitive. Any retained role failure or disagreement yields HOLD; unsuccessful alternatives are not discarded. Table cells and all original non-background cells remain unchanged on successful tested scenes.
- This prior includes a unique modal background and excludes background-containing tables. No support for broader scene semantics is claimed.

## Independent checks

Teacher exact 3/3; D4 transforms 24/24; nontrivial all-color permutation 3/3.
Synthetic checks passed: one table; all-table agreement; table disagreement; one failed table alongside a successful table; conflicting keys; equidistant two-lane agreement/disagreement; four-way 2x2 tie; foreign occupancy; nested same-color ownership; diagonal C8 wall/C4 cavity; open C4 leak; simultaneous 1→2 and 2→3 hole filling without chaining; input nonmutation and original non-background preservation.
Eight invalid grid cases rejected; malformed/insufficient teacher examples rejected; 250 seeded random legal grids raised no exceptions.
Execution: OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=1, MKL_NUM_THREADS=1; CPU limit 10 seconds, address-space limit 512 MiB.
Reproducer: independent_audit.py. Results: independent-audit-results.json.

## Guard boundary

predict(grid, 1), predict(grid, [1]), and predict(grid, [None]) raise TypeError rather than returning HOLD. Empty/wrong well-formed models return no_fitted_model. Parent explicitly accepts exception propagation for malformed external model state and limits the adapter to unmodified fit-returned state. Under that contract this does not block source-ready status. Arbitrary-model API completeness is not claimed. Adapter source itself remains outside this pure-file audit until its path is supplied.

## Adapter follow-on gate

Inspected candidate195-production/source/接続/ARC2/境界表穴転写教材.py and evidence-20261008/runtime.diff. The new pure kernel SHA exactly matches the audited freeze. Adapter state is initialized to () and assigned only from api.fit(teachers)[0]; no external model setter or parsing path is present. Teacher guard requires a literal list of at least two literal dicts, valid equal-shaped input/output grids, and uniqueness of every input. HDS diff contains exactly four additions: import, teacher construction, empty-prior mechanism registration, and record. Independent adapter execution reproduced 3/3 teachers and closed six malformed/duplicate teacher cases. Gate PASS for this bounded integration. No HDS query or official evaluation was run by this auditor.
