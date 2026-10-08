# Teacher-only observed-series composition: 3/3 closure

This isolated proposal closes the three supplied teachers exactly. It is not integrated, evaluated, or accepted; no score change is claimed. Accepted156, core, and protected files were not edited. Runtime imports use accepted156 component extraction and minimal-prefix-period primitives read-only. No queries, external targets, scorer, excluded047 material, task IDs, hashes, or filename-based answer routes were used.

## Result

| Check | Result |
|---|---:|
| Supplied teachers | 3/3 exact |
| D4 × five palette permutations × three teachers | 120/120 exact |
| Independently generated axis-series cases, including skipped indices | 15/15 exact |
| Source-pigment corruption negative controls | 3/3 HOLD |
| Incorrect teacher output passed to fit | Rejected |

Retained complete predictions for teachers 1/2/3: **4/2/12**. Each teacher has exactly one distinct prediction and zero incomplete eligible models. Teacher 1 has equivalent row- and column-extrusion descriptions. Teacher 2 uses radial layers. Teacher 3 retains six axis factorizations in each of two eligible D4 views.

## Representation and completeness boundary

Both families are attempted on every input and both internal axes, across all D4 views. Family eligibility depends on source structure, never teacher identity or output success. Predictions from all eligible models must agree; incomplete eligible models or disagreement cause HOLD.

**Axis extrusion.** Each row is represented by its ordered run-color signature. Each run length must be an exact affine function of observed patch width. Monochrome objects factor pigment into the existing minimal-prefix-period operator, and use binary shape symbols. A signature observed at only one width cannot extrapolate to another width. This is a restricted structural grammar: two row shapes with the same run signature but incompatible lengths are rejected, rather than separately memorized.

Every prefix / nonempty repeat unit / suffix factorization of the shortest observed sequence is enumerated. The core must be nonempty in every source and repeated at least twice in some source; its count must grow by one exact positive affine function of source index. Every source word must reconstruct exactly. These source-witness conditions bound the grammar; there is no shortest-description selection or post-fit pruning. All fitting factorizations, including longer prefixes/suffixes, are retained. The generated future raster must have the independently inferred bbox dimensions.

**Radial layers.** Same-color C4 components must form uniform, symmetric layers. Their normalized masks and pigments use independent existing minimal-prefix-period operators indexed by radius. All observed source rasters, including background, are replayed exactly before prediction. This extends prior148's diagnostic with explicit full-source replay and internal-axis enumeration.

**Geometry.** The prior teacher-only inventory is retained: dominant background, two separate three-cell 2×2 corner-marker components, horizontally ordered disjoint body components, quadratic bbox endpoint continuation, and marker-window matching. A view with no matching future geometric role is not eligible. Multiple matching future roles cause HOLD. D4 enumeration removes a fixed global orientation, but the inherited index search remains bounded below 30. Geometry has not been expanded into a general layout solver.

The existing minimal-prefix-period primitive is an explicit language operator, not enumeration of every longer period that could interpolate finite observations. Allowing arbitrary unseen periods or unrestricted affine/polynomial theories would destroy identifiability. This proposal does not claim completeness over those larger languages. The axis grammar itself retains every consistent source-witnessed factorization.

## New versus reused

Reused: accepted156 C4/mixed-region extraction, normalized component information, and exact minimal-prefix-period operator. Copied prior teacher-only geometry and radial composition are isolated here for reproducibility. New: source-witnessed prefix/period/suffix growth grammar, affine run-width channel, union/agreement across families/internal axes/D4, explicit source replay, and pure fit/predict contract.

This is consequently a new bounded composition, not a claim that accepted production already supported these teachers. It needs independent review before any integration or evaluation.

## Files and reproduction

- `growth_series.py`: input-only `predict(grid, with_evidence=False)` and all-teacher `fit(teachers)` gate. Fit does not choose programs by target success.
- `geometry.py`: copied input-only layout inference.
- `radial.py`: source-replayed layer grammar.
- `check.py`: supplied teachers and owned synthetic checks only.
- `report.json`: all model/failure evidence and checks.

Run: `PYTHONDONTWRITEBYTECODE=1 python proposal160-growth-series-composition-20261007/check.py`.

Remaining gap: generalization outside this bounded source-witnessed grammar is unestablished. No integration/evaluation was attempted or authorized in this work item.
