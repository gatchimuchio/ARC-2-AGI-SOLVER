# Pure candidate 194: local rail / chain / obstacle ownership

Status: FROZEN PURE CANDIDATE, not admitted. Baseline 108/152 unchanged. No native, full regression, official evaluation, commit, upload or remote write was performed. HDS/core/gate/authority unchanged.

## Concrete observation and gap
All five teacher input/output pairs and both input-only queries were rendered and visually inspected. The teacher transformation preserves the stationary straight rail and the passive obstacle, removes a bent monochrome chain, and redistributes its cell count from the rail's free endpoint around the near contour of the forward obstacle. Counting before clipping explains teacher 0 (6 logical cells, 2 clipped) and teacher 3 (6 logical cells, 1 clipped); the other teachers retain all logical cells.

The queries contain several independent triples. In query 1 the same blue color is both an upper moving chain and a lower stationary rail; the same gray color is both a middle moving chain and an independent lower obstacle. A global color-to-role assignment loses physical ownership. This is not repaired by another exact-three-color guard.

Reused current capabilities: `既存物体特徴.color_components(..., True)` for C8 monochrome physical objects, and `境界点周期候補.valid_grid`; D4 verification uses `既存格子操作.transform_grid_by_name`. Local endpoint contacts, simultaneous edits, and fail-closed consensus compose these components. The missing mechanism is local compound rail/chain binding plus forward profile placement. No color, task ID, filename, hash or stored grid is used by the kernel.

## Old assets and negative history
A bounded workspace/current-source search did not recover complete source for proposals 143, 149 or 152. Therefore this is a reconstruction, not a source-identical restoration, and duplication of the lost implementation cannot be ruled out. Parent supplied the 143 exact-three-color limitation. The preserved 149 regression timeout and 152 two wrong outputs / three CPU failures / old losses were read from their decision summaries; no hidden solutions or official query answers were read. Those scores were not used to select or reverse any answer. The candidate follows fresh teacher/input geometry.

## Explicit priors, not teacher uniqueness
- Unique dominant background and whole monochrome C8 ownership.
- A rail is a straight border-reaching component jointly recognized with a lateral chain touching its free endpoint. Straight border components without such contact remain passive objects. All geometrically valid compound assignments are retained.
- Chain cells lie on its original lateral side and behind the rail's free end. Their count is the logical output path length.
- The target is a nearest strictly forward passive component. Both minimum Chebyshev and squared Euclidean metrics are fitted and retained, including all distance ties.
- Follow the near-side extreme profile, with unit transverse steps. Both early and late unit interpolation before the profile are retained. After the obstacle, continue diagonally toward the opposite side. Original lateral ownership fixes the near contour; there is no arbitrary left/right tie breaker.
- Simultaneous source removal and path deposition; stationary objects are preserved; any collision, overlap of physical owners, retained failure, or disagreement is HOLD.

All four metric/interpolation models fit all five teachers and agree on both queries. This does not make the semantics logically unique: nearest-object selection, count preservation, contour choice and post-profile continuation are explicit additional priors. A full retained candidate failure prevents output. Exceptions including MemoryError propagate. There is no partial-model fallback or swallowed resource exception.

## Checks and failures kept
Initial border-object-only recognition mistakenly demanded a chain for teacher 1's top-border target: `initial-border-object-failure.json` retains that all-teacher failure. It was fixed by recognizing a rail jointly with endpoint-chain contact. A metamorphic check exposed vacuous fit on empty training; the final kernel rejects empty training. A same-color collision was also tightened to HOLD because matching paint does not confer shared physical ownership.

Final `pure-evidence.json`: 5/5 teachers, both input-only outputs, full role/path/cell-count/clip diagnostics, all four retained models. `metamorphic-evidence.json`: 163 checks, including eight D4 transforms and twelve color permutations on all seven observed inputs, retained-model failure, resource exception propagation, empty-teacher rejection, and all per-chain mass counts. `q0-candidate.png` and `q1-candidate.png` are candidate visualizations, not official answers.

All executions explicitly used OPENBLAS_NUM_THREADS=1, CPU 10 seconds, address-space 512 MiB, wall 60 seconds. No changes to that launch contract. The original purpose instruction was reread in full after reporting the mechanical all-teacher result and before continuing checks.

## Handoff
Runtime kernel: `local_chain.py` (pure fit/predict/render). `fit` state contains only version and retained abstract metric/interpolation models, no teacher grids or diagnostic answer state. Use the frozen kernel only after independent audit and authorized normal HDS integration. Do not claim a score improvement from this pure result.
