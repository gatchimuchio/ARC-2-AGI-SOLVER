# Witnessed growth composition164 — frozen teacher/synthetic candidate

Frozen162 and diagnostic163 remain unchanged. This isolated revision incorporates the authorized source-observed gaps. No test targets, scorer, second-input repair, integration, or evaluation were used. Its code and checks do not read sanitized test inputs. Input-only diagnosis of the first test source motivated the declared views; no test-output comparison was possible or performed.

## Results before freeze

- Existing teachers: 3/3 exact
- Teacher D4/palette transformations: 120/120 exact
- Existing independent axis growth synthetics: 15/15 exact
- New centered periodic-growth / interior-crop synthetics across D4: 72/72 exact
- Exact quadratic inequality checks: 5,324/5,324 cases against direct integer evaluation
- Unbounded geometry: detected
- Multiple finite indices: both1 and3 retained in focused witness
- Unfamiliar source-fitted prediction failure: global HOLD
- Modal-background tie across D4: HOLD
- Portable absolute-path import: pass
- Three corrupted-source controls: HOLD; incorrect-output fit: rejected

## Language and changes

GRAMMAR.md records the finite language declaration and authorized amendments made before freeze. All consistent programs within it are retained; there is no minimum-description winner.

1. The marker rectangle may be any contained crop, rather than spanning the full object width.
2. Bbox coordinates and witnessed word-repeat counts retain both exact quadratic laws and every exactly fitting periodic-first-difference law with period shorter than the observed difference sequence. A repeated phase must therefore actually have been seen.
3. A centered-row view requires common center parity, exact mirror symmetry, full source reconstruction, and at least two complete spatial cycles at distinct radii. Every fitting spatial period is retained.
4. At fixed source width, row symbols are literal rows, preserving distinct observations such as100 versus110. Width-changing sources retain162's affine run-width representation. An unobserved width cannot be extrapolated from a single-width channel.
5. Existing prefix/unit/suffix and radial-component programs remain. All families, internal axes, and D4 views contribute to consensus; a source-fitted future failure forces HOLD.

The existing accepted minimal-prefix-period operator remains the explicit pigment/component-period language, as documented and audited for162. The newly enumerated coordinate, repeat-count, and centered-row grammars do not use minimum-period selection.

## Exact future-index completeness

For each Cartesian combination of coordinate laws, let P be the LCM of all periodic-difference periods. Every nonnegative n lies in exactly one residue n=Pq+r, 0≤r<P. Each coordinate is affine or quadratic in integer q. Evaluating at q=0,1,2 gives its exact doubled integer coefficients, without approximation.

Intersect q≥ceil((source_count−r)/P) and the four containment inequalities. The nonnegative_intervals helper solves a*q²+b*q+c≥0 exactly:

- Linear/constant cases use integer floor/ceiling division.
- For a>0, strict negativity is equivalent to (2aq+b)²<D, where D=b²−4ac. Therefore the forbidden integer interval uses isqrt(D−1); its complement is retained.
- For a<0, negate the polynomial and solve ≤0. The allowed interval uses isqrt(D), including exact roots.

Every integer interval is retained and intersections are exact. Every finite surviving index is enumerated. Any unbounded surviving interval sets unbounded_geometry and forces HOLD; no guessed index cap is introduced. Multiple distinct future bboxes/indices also cause conservative HOLD rather than dropping a role. Equal geometric records are deduplicated only because they refer to exactly the same index and bbox; all shape-family alternatives are still evaluated there.

## Files and use

- growth_series.py: self-contained pure module; caller supplies accepted primitive imports on sys.path. predict(grid, with_evidence=False); fit(teachers) only accepts complete teacher closure.
- check.py / report.json: teacher and original synthetic regression
- focused.py / focused-report.json: new synthetic, inequality, consensus and portability checks
- GRAMMAR.md: declared scope
- frozen-manifest.json: source/evidence hashes for independent review

Reproduce with PYTHONDONTWRITEBYTECODE=1 and run check.py then focused.py from this folder. Only check drivers configure workspace paths; the pure module has no filesystem reads or workspace bootstrap.

Limits: this is a bounded composition proposal, not general inductive completeness or an accepted score improvement. First-input prediction has not been executed by this worker after freeze; the parent controls any subsequent input-only run. The second query's model deficiency was not inspected or repaired by this revision.
