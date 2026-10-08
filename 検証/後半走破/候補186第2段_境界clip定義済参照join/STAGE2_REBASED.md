# Stage 2 rebased on adopted stage 1 revision 2

FROZEN FOR INDEPENDENT REVIEW; no official score asserted.
Source: stage2_rebased_core.py
SHA256: 5bfb14ba308720f9767173feee25ee7a07cf204083e6ee478fd157177953882d
Production replacement target: 接続/ARC2/連結箱参照核.py
Base: arc2-current102-145/source (102 tasks / 145 grids)
Diff: stage2_rebased.diff
Validation: check_stage2_rebased.py; stage2_rebased_targeted.json (161 checks PASS).

The original combined linked_box_core.py and all earlier frozen revisions/hashes are unchanged and remain separate history. This implementation does not restore the rejected C8 replacement. The objective instruction was read in full at task start and after reporting the candidate result, before validation continued.

## First observed gap and domain
The current q2 ownership parser proves unavoidable_wire_has_multiple_colors: it has four complete C4 squares but cannot own the bottom clipped object. The new domain is decided before path_graph, terminal actions, or output generation:
1. Run the entire old physical ownership parser.
2. If any old ownership exists, return all old roles and the old record exactly, even if a later graph/lookup/merge fails or disagrees.
3. Otherwise, continue only with the explicit unavoidable-wire multiple-colors proof, at least one original complete C4 square, and at least one recognized boundary-clipped square fragment using an observed complete square's side length.
4. Enumerate ownerships again with all original C4 candidates retained and all new clipped candidates added. Every retained extended ownership must contain a clipped object. Preserve the complete original failed parse inside the new record.

The clipped object owns only visible cells, with a visible center. Its monochrome visible shell must be exactly one existing C4 same-color component apart from that center. No clipping is added to the nonrectangular C8-shell domain. No old candidate/ownership is selected or discarded based on rendered success.

## Geometry check before adding the reference prior
stage2_geometry_check.json records the local vectors for every teacher endpoint and the q2 endpoints. At q2 (7,2), the last wire step points right; the upper and lower candidates are both perpendicular (dot product zero). Straight-only contact is contradicted by teacher 1. A signed right-turn prior happens to fit the teachers, but a uniform handedness restriction is contradicted by the already accepted q0 endpoint (3,7), whose incoming vector is (-1,1) and object direction (-2,0), giving the opposite cross-product sign. No uniform forward/straight or handedness rule both resolves q2 and preserves the accepted scope. A restriction only on perpendicular contacts would be another unsupported special geometric prior; it is not adopted.

## Explicit reference-domain prior
Only roles admitted through the new clipped domain carry reference_domain_binding=True. Before rendering, intersect every spatial endpoint contact with the input reference relation: original center value must occur as an object key. Every removed contact has its missing_lookup_key witness recorded; no output is consulted. Empty bound contacts HOLD. All remaining terminal combinations and every lookup source remain in the old exhaustive execution, with any failure or full-grid disagreement producing HOLD.

This is a declared extra prior. The teachers are consistent with it, including a separate forced-binding check on each teacher, but do not logically entail its uniqueness. Old complete-object domains do not use this filter, including their preexisting missing-key and disagreement failures.

## Results and retained failures
- All 3 teachers reproduced; all 27 teacher/program verdicts and retained program unchanged.
- Old q0 and q1 complete API/render outputs retained; q2 becomes an input-only OUTPUT. No q2 answer was read.
- Exact original ownership and full (output, record) tuples retained for every program on available old ownership domains, including teacher inputs, old queries, and ordinary fixtures.
- Independent 10x19 C4-square/diagonal-wire regression fixture retains the exact old successful tuple and ownership.
- Old six ordinary fixtures pass, including missing-reference and multiple-attachment HOLD.
- New-domain contrasts: all references undefined -> HOLD with reason; two defined terminal choices -> both executed and disagreement HOLD; broken wire -> disconnected HOLD; missing visible shell cell -> HOLD.
- All query D4/palette checks and new/old-domain RuntimeError/MemoryError propagation pass.

The initial test attempt incorrectly expected wire_not_exactly_two_ends for a wire deletion that produces a degree-zero isolated cell. The unchanged graph correctly returned wire_not_connected. Only the test expectation was corrected; the failed attempt and unrun later checks are described in stage2_test_initial_failure.txt. No runtime repair followed that test failure.

Native integration, full regression, official evaluation, adoption, commit, push, and upload remain the parent's next stage; none were performed here. HDS v0.4.2, global gate, candidate API and existing program inventory remain unchanged.
