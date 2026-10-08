# Pure proposal196: independent surface ownership composition

Status: teacher-fit/input-only candidate, not adopted, not officially scored. Base arc2-current110/source (110 tasks /155 grids). No production source, HDS, gate, authority, or fixture changed.

## Observed first gap and reused capability
Both teacher inputs/outputs and the full 30×30 query input were visually inspected (observed.png and query.png). The established binary hole renderer rejects the three-color input, and binary region family192 has no model because its two-color role contract does not apply. Those actual failures are in existing-gap.json.

Reuse family192's unique_region unmodified separately for each of two surface colors, treating all other colors as absent from that binary mask. The resulting masks must each be certified unique, then must be disjoint. Assemble the clean multicolor region from those owners, mark original background cells inside the restored surfaces using the teacher-derived novel color, and outline each such hole with the other surface's color using existing EIGHT_DELTAS. The clean scene also repairs non-background surplus cells. This adds composition/role binding and simultaneous conflict checks, not a new optimizer.

All retained background/marker models must succeed and agree. Global surface overlap, competing outline colors, surplus/outline collision, nonunique mask, or missing witnesses HOLD. Resource and unexpected exceptions propagate. Strict teachers list/minimum2/all input unique/pair dictionary/both grids valid/same shape guards are included. Only returned models contain learned state, not teachers or outputs.

The inherited prior is unit edit cost + unit orthogonal turn cost, with three-cell majority extrapolation along the image edge. Independent minimal-surface ownership, background-hole marking, and opposite-surface outlines are explicit teacher-consistent assumptions, not a claim of logical uniqueness from two examples. No weight/alternate prior was selected from the prior official failure.

## Pure evidence
pure-evidence.json: both teachers reproduced, one input-only query output, one retained background/marker model. Each of six masks has integral optimum and strictly larger certified next-solution lower bound, with no ownership overlap. Query contains 24 background defects. Query has no provided output and is UNSCORED.

The initial probe.py/probe.log remain unchanged. Its query `fit False` compared a grid against absent output (None); it is not a correctness failure and must not be treated as query feedback. The corrected production check does not compare a query against a nonexistent label.

Final direct test checks: 19. Synthetic checks: 5, including competing owners, competing outline colors, surplus/outline collision, clipped edge holes, retained-model disagreement. D4 eight orientations and a color permutation: 36 checks. All run with OPENBLAS_NUM_THREADS=1, CPU10,512MiB,wall60. Each transform was a separate bounded process. Numerical/uniqueness certification uses the unchanged accepted kernel. No native/full regression/official evaluation was run.

## Old candidate limitations
Candidate165 revision2 REVIEW.md recovered from base rejected165 evidence. It records teacher-fit then wrong1, delta0; rejection remains intact. Neither complete165 nor138 source was recovered by the bounded local search. Therefore source-level difference or same-output equivalence to those candidates is UNVERIFIED. This candidate is explicitly the accepted192 binary ownership composition described above, independently supported by input and teachers; it is not claimed to restore165 and must not be represented as a verified novel mechanism relative to missing source. No old query output or official correct output was read, and the rejection was not used to select an inverse answer or alternate prior.

The complete owner instruction was read before starting and reread after the first mechanical result was reported. Freeze binds only the pure kernel and current inherited source dependencies. No commit, upload, remote write, adoption, hidden-label read, or score claim.
