# Independent audit: proposal 198

Verdict: PASS for the requested isolated source/teacher/synthetic review. This is not adoption or evidence of an ARC2 score improvement.

Source SHA-256: a6637e397866052318eba6344ab942abbe44701affb9728fe5fdcf5b4ee5b8e1.

Read the complete current111 purpose instruction and AGENTS before work. Inspected only pure source, old171r2 source, accepted imports, and the teacher-only file; did not read query, README, pure-evidence, observed image, or official answers. Canonical source was not changed.

Compared with the old171r2 implementation at arc2-current99/evidence/not-adopted/proposal171-marker-movement-view-20261007/revision2/接続/ARC2/凡例方向移動候補.py, the executable changes are exactly:

1. Eight lines in diagonal execution requiring both orthogonal intermediate full footprints to belong to the same owner region; helper contradiction raises RuntimeError.
2. Expanded teacher validation requiring at least two distinct, same-shape input/output grid pairs.

Docstring changes explicitly describe a boundary-topology prior. Intermediate marker occupancy is ignored for these owner-region checks; endpoint block/transparent semantics remain inherited. The word “swept” in the older introductory sentence should be understood under the explicit boundary-only qualification, not as continuous swept collision physics.

Independent execution under OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=1, CPU limit 10 seconds and address-space limit 512 MiB:

- 480 model candidates, 3 teacher examples, 1440 returned teacher evaluations, exactly 4 retained models.
- Both old171r2 and current198 retain all four marker-diagonal × collision variants. The new topology condition is an explicit prior, not uniquely implied by teacher evidence.
- Teacher predictions remain exact with consensus over every retained model.
- Synthetic checks isolate either missing orthogonal flank, full multi-cell flank footprint, owner membership, preserved endpoint collisions, ignored intermediate marker occupancy, and unchanged open-region movement in all eight directions.
- Instrumented ownership test confirms all 2×3 owner assignments are evaluated, including after an ordinary failure, and failure/disagreement return HOLD.
- Instrumented fitted-model tests confirm all four retained models are evaluated before ordinary failure/disagreement HOLD.
- Invalid grid/teacher guards and propagation of model/helper runtime exceptions pass.
- Source has no task ID, filename/hash selection, fixed answer data, runtime file I/O, dynamic code loading, or exception suppression. Outputs derive from cloned input plus generic erase/paint actions.

Reproduction: OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python proposal198-marker-owner-20261008/independent_boundary_audit.py

Detailed results: independent_boundary_audit.json. Exact source diff: independent_boundary_diff.patch.
