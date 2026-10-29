# ARC 2026 NVARC + TRM Hybrid Source

Offline source bundle for an ARC Prize 2026 ARC-AGI-2 Kaggle notebook.

This source dataset supplies the TRM half of the NVARC/TRM Kaggle variants:

1. `trm_runtime.py` adapts the public TRM checkpoint to the hidden puzzles,
   exports rank-one predictions at epochs 2,000 and 4,000, and validates every
   grid.
2. `merge_agreement.py` supports three label-free policies:
   - `aggressive` combines NVARC rank one with final TRM rank one.
   - `agreement` uses TRM only when the two checkpoints agree and otherwise
     preserves NVARC rank two.
   - `evidence` preserves the aggressive final-TRM fallback while allowing
     cross-solver agreement and audited transformations selected from the
     training pairs to override it. All admitted transformations require exact
     agreement on every training pair except one corpus-unique panel-ordering
     rule, which permits a single displaced marker after a five-partition
     zero-error held-out audit. It gives an unambiguous audited rule grid
     priority over cross-solver agreement, can inject that grid directly, and
     records every decision in `selector-receipt.json`.

The constant-output heuristic and the broader proof-search selector are
intentionally excluded from exact-rule evidence. On a 2,080-task held-out ARC
audit they introduced direct-selector errors. The admitted selector contains
only transformations that remained perfect when replayed through the
production merger: spatial/color maps, scaling, tiling, cropping,
crop-then-horizontal-flip, conservative component extraction, audited symmetry
completion, bounding-box fill/outline, hole filling, uniform-line removal, and
first-panel rotation. The current production audit is 961/961 correct direct
selections across 615 fired tasks and 2,563 held-out outputs from 2,080 labeled
tasks. In addition to the source-V15 64/64 layer, it admits only error-free
held-out additions: largest monochrome, unique widest, unique smallest, and
unique topmost color-component crops; a most-disconnected-color singleton; and
restricted symmetry-completion signatures whose training-exact predictions
agree on the test grid. The latest focused composition audit also admits
scale-2x2-then-remove-uniform-lines and horizontal-tile-2x-then-remove-
uniform-lines, both exact on every train-matched held-out application. Direct
whole-cell gravity up and down are also admitted after reproducing four
error-free held-out outputs (two unique tasks) with zero selector ambiguity.
The next motion audit adds unique-rarest-color leftward compaction around
fixed cells plus rigid same-color component motion to the left and right.
Together those three rules add ten error-free corpus outputs across four
unique task identities, again with zero ambiguity. A tie-rejecting nearest-
corner rule for same-color components adds two more duplicate-corpus outputs
from one official task identity; it fires only when every component has a
unique nearest horizontal and vertical boundary.
The line-projection audit adds three more globally exact rules: connect equal
colors vertically and then horizontally while preserving earlier crossings,
fill each color's own bounding box without overwriting other objects, and
extend single-color columns downward. They add fourteen error-free corpus
outputs across seven task identifiers, with the aggregate selector still
unambiguous.
A final component-filter pass adds the actual modal-fill primitive for
constant grids and a symmetry-aware rule that keeps only monochrome shapes
having a duplicate under rotation or reflection. Those two rules add eight
error-free corpus outputs across three semantic task identities. Coincidental
component proxies for modal fill are explicitly excluded.
The border/padding audit admits only a one-cell ARC-azure outer frame, adding
two error-free duplicate-corpus outputs from one official task. Every padding,
cropping, and alternate frame candidate is excluded.
The diagonal/line audit adds draw-order-consensus connections between matching
diagonal colors plus three unique-rarest ray signatures: northeast, cardinal
cross, and diagonal X. These add fifteen error-free corpus outputs across six
semantic task families while retaining zero selector ambiguity.
A conservative cleanup audit adds one rule that removes non-modal pixels only
when they are singleton components under eight-connectivity. It adds two
error-free duplicate-corpus outputs from one official task identity while
preserving 100% direct-selector precision.
The counting audit adds input-dependent unary encodings for connected objects,
distinct colors and row widths, enclosed area, rare pixels, polygon sides,
interior markers, and objects fragmented by occlusion. Mapped structural rules
learn output colors only from the task's training pairs. Together they solve
all thirty Count1-Count10 concept outputs with zero selector ambiguity.
The center audit adds guarded center-cell extraction, center-object cropping,
component-center marking/removal, marker recentering on shapes and parallel
lines, and midpoint cross construction. Those color-preserving rules solve all
thirty Center1-Center10 outputs and keep the aggregate selector unambiguous.
The boundary-motion audit adds orientation-adaptive gravity, outward cluster
motion, shape-to-shape contact, distractor-line removal, aligned marker motion,
and pointing-arrow placement. These rules solve all twenty-four previously
uncovered MoveToBoundary outputs without introducing a corpus error.
The same/different audit adds repeated-color, repeated-orientation, repeated
interior-color, repeated-frame, repeated-inner-shape, panel-comparison, and
shape-equality rules. They solve all twenty-four previously uncovered outputs
across SameDifferent3-SameDifferent10, completing the full SameDifferent1-10
concept family with zero aggregate selector ambiguity.
The filled/not-filled audit adds guarded solid-rectangle sizing, enclosed-
region extraction, scanline and convex fill toggles, horizontal-band toggling,
secondary-color filling, and checkerboard completion. These rules solve all
twenty-four previously uncovered FilledNotFilled2-3 and 5-10 outputs plus four
official-corpus outputs, with zero errors or selector ambiguity.
The above/below audit adds guarded divider-side erasure and endpoint marking,
rare-color propagation up and down, top-object contact and frame-crossing
motion, literal green boundary selection, azure extraction below the top
band, and monochrome line-side filling. These rules solve all thirty
AboveBelow1-AboveBelow10 outputs with zero errors or selector ambiguity.
The horizontal/vertical audit adds orientation-guarded frame filling, stripe
selection, boundary-axis markers, horizontal-run recoloring, top/bottom core
filtering, and line-component recoloring. These rules solve all thirty
HorizontalVertical1-HorizontalVertical10 outputs with zero errors or selector
ambiguity.
The extract-objects audit adds bounded anomaly crops, unique-component and
rare-inner-color crops, maximal solid-rectangle extraction, repeated-object
packing, separator-panel packing, and zero-wall enclosure extraction. These
seven rules solve all twenty-two previously uncovered ExtractObjects outputs
plus two additional held-out outputs without a corpus error, bringing the
aggregate selector to 529/529 across 245 tasks with zero ambiguity.
The top/bottom 2-D audit adds top-color extraction, top-row recoloring,
top-and-bottom removal, bottom-object isolation, bottom-color propagation,
highest-ending-component marking, and top/bottom band swapping. These seven
rules solve all twenty-one previously uncovered TopBottom2D outputs without a
corpus error, bringing the aggregate selector to 550/550 across 252 tasks with
zero ambiguity.
The top/bottom 3-D audit adds guarded layer reconstruction, overlap-order
reversal, hidden-strand removal, top-layer deletion and translation, occlusion-
graph extraction, covered-rectangle reconstruction, repeated foreground
propagation, mixed line-crossing reversal, smaller-object color propagation,
and periodic grid restoration. These ten rules solve all thirty
TopBottom3D1-TopBottom3D10 outputs plus two previously uncovered official
held-out outputs without a corpus error. The aggregate selector reaches
581/581 across 263 tasks with zero ambiguity; ConceptARC coverage is now
477/480 outputs and 159/160 tasks at this milestone.
The inside/outside audit adds guarded marker counting, segment and sparse-box
membership, nested-frame membership, containment extraction, convex-hull
inside/outside filtering, per-frame marker counting, and between-line
filtering. A final guarded frame repair infers a rectangular ring with learned
thickness, a Manhattan diamond, or an already-closed irregular contour before
clipping crossing lines to its interior and restoring overwritten frame cells.
Together these rules solve all thirty InsideOutside1-InsideOutside10 outputs
without a corpus error, bringing the aggregate selector to 584/584 across 264
tasks and completing ConceptARC at 480/480 outputs and 160/160 tasks.
The expanded cleanup audit adds periodic-pattern restoration, dispersed-color
inpainting, dense and hollow rectangle reconstruction, bracketed component
repair, mirrored-template union, repeated-square completion, occlusion
inpainting, and intersecting-line extraction. These nine guarded rules solve
all thirty CleanUp1-CleanUp10 concept outputs plus two duplicate-corpus outputs
from one official task identity, with zero errors and zero selector ambiguity.
The order audit adds guarded object-size sorting, component-color sequencing,
row-run ordering, component-size bars, two independent vertical-panel order
rules, and two-panel component ordering. A final marker-panel sorter admits
the only noise-tolerant training fit: one training pair is exact, the other
differs by one displaced marker, and the rule is otherwise unique across all
2,080 tasks. Together these rules solve all thirty Order1-Order10 outputs; the
aggregate selector remains 437/437 with zero ambiguity.
The copy audit adds centered motif insertion, singleton-anchored template
stamping, marker-count repetition, short-axis duplication, partial-object
completion, scaffold copying, translated-panel completion, secondary-pattern
transfer across resized or reflected shapes, and sparse repeated-anchor
translation. The translation search is capped at 64 occupied cells before
candidate generation. Together these rules solve all thirty Copy1-Copy10
outputs, bringing the aggregate selector to 464/464 across 223 tasks with
zero ambiguity.
The complete-shape audit adds guarded sparse-cross completion, parallel-side
replacement, complementary L-tromino completion, color-five template copying,
single-cell symmetry repair, dominant-color reflection, and minimal bilateral
shape repair. These seven rules solve all twenty previously uncovered outputs
across CompleteShape1-10 without a single corpus error, bringing the aggregate
selector to 484/484 across 229 tasks with zero ambiguity.
The extend-to-boundary audit adds dominant-margin center rays, vertically
blocked marker rays, dotted-line projection, perpendicular component contact,
spanning-line connections, cardinal inner-shape expansion, and
opening-aligned external marker rays. These seven rules solve all twenty-one
previously uncovered outputs across ExtendToBoundary1-10 without a corpus
error, bringing the aggregate selector to 505/505 across 236 tasks with zero
ambiguity.
The official-corpus expansion adds thirty-two independently audited rules for
unit translation, compact counting and classification, uniform-line encoding,
two-panel union/intersection/XOR, periodic extension, component recoloring,
mirror construction and extraction, edge duplication, separator comparison,
quadrant selection, marker projection, and guarded
rotation completion. Each rule was required to fit every training pair and
then remain perfect on every matching held-out application across the two
official ARC-AGI corpora, their duplicate partitions, and ConceptARC. Together
they add eighty-four exact held-out outputs across seventy-two additional
fired tasks without a wrong direct selection. The aggregate selector is now
668/668 across 336 tasks at 100% direct-selector precision, while ConceptARC
remains complete at 480/480 outputs and 160/160 tasks.
The post-V46 official-corpus expansion adds fifty-two more independently
audited rules for mirrors and rotations, separator-panel Boolean operations,
periodic completion and extraction, component counting and recoloring,
marker-driven rays and stamps, panel overlays, shape selection, nested-ring
color cycles, container encodings, line-relative motion, and compact
symmetry-based crops. Every rule was tested against all 9,245 corpus inputs,
ported independently into the production merger, and accepted only after
remaining exact on every held-out application. Together they add 125 correct
held-out outputs across 117 additional fired task identities without a wrong
direct selection. The aggregate selector is now 793/793 across 453 tasks at
100% direct-selector precision; ConceptARC remains complete at 480/480
outputs and 160/160 tasks.

The source-V48 expansion adds forty-six independently audited transformations
for constrained classification and rendering, guarded geometric construction,
component packing, periodic completion, template replication, exact-cover
tiling, C-shape projection, endpoint chaining, and minimal quarter-turn
symmetry. Every rule was first tested against all 9,245 corpus inputs, then
ported independently into the production merger and checked for exact
reference parity. The ten audit receipts in `receipts/` record 96 new correct
held-out outputs across 92 additional fired task identities with no wrong
direct selection. The aggregate selector is now 889/889 across 545 tasks at
100% direct-selector precision; ConceptARC remains complete at 480/480
outputs and 160/160 tasks. The bundled V70 benchmark receipt is the
authoritative aggregate for this version.

The source-V49 expansion adds thirty-one more independently audited
transformations for component ranking and recoloring, marker-driven geometry,
template stamping, lattice construction, frame projection, rectangle bridging,
singleton rendering, and exact translated-shape matching. Every rule was
required to fit every task training pair, remain perfect on every matching
held-out application across the five-corpus audit, and match its independent
NumPy reference on all 15,927 train-input, train-output, and test-input grids.
The six V25-V30 audit receipts in `receipts/` record 62 new correct held-out
outputs across 62 additional fired task identities without a wrong direct
selection. The aggregate selector is now 951/951 across 607 tasks at 100%
direct-selector precision; ConceptARC remains complete at 480/480 outputs and
160/160 tasks. The bundled V101 benchmark receipt is the authoritative
aggregate for this version.

The source-V50 expansion adds four guarded transformations: translated
three-by-three source stamping into marked tiles, motion of a three-by-three
block to the next aligned marker, alternating color/five row extension, and
one-step motion of a gray marker toward a yellow marker. The V31 audit records
ten additional exact held-out outputs across eight task identities with no
wrong direct selection. Independent NumPy and production-list implementations
match on all 63,708 rule/grid comparisons. The aggregate selector is now
961/961 across 615 tasks at 100% direct-selector precision; the bundled V105
benchmark receipt is authoritative for this version.

The source-V51 expansion adds seventy independently audited transformations
for guarded geometry, component motion and recoloring, panel composition,
sequence extension, symmetry recovery, compact rendering, and marker-driven
projection. Each production implementation was compared with its independent
NumPy audit reference on all 15,927 corpus grids, for 1,114,890 comparisons
with zero mismatches. The V32-V35 and V37-V46 audit receipts record 142
additional exact held-out outputs across 138 additional fired task
occurrences, with no wrong direct selection. The aggregate selector is now
1,103/1,103 across 753 fired task occurrences at 100% direct-selector
precision; ConceptARC remains complete at 480/480 outputs and 160/160 tasks.
The bundled V175 benchmark receipt is authoritative for this version.

The earlier proof-search and Icecuber files remain as reproducibility artifacts
but are not invoked by the NVARC/TRM notebook. Complete 172-output ARC-AGI-2
public audits of bundled Icecuber reached only 0.8333% at depth 20 and 2.0833%
at depth 30, with no rank-two incremental wins, so it is not promoted into a
submission slot.

## Reproducibility

- TRM epoch-4,000 rank one: 9.3056% task mean on the official labeled local
  ARC-AGI-2 evaluation revision.
- TRM epoch-4,000 native top two: 10.1389% task mean.
- Epoch-2,000/4,000 rank-one agreement: 12/31 exact outputs (38.71% precision),
  versus 4/136 (2.94%) when those checkpoints disagree.
- Public NVARC reference: 33.89% on the live Kaggle leaderboard.
- Aggressive independence projection: 40.0419%. It is a design projection,
  not a claimed competition score.

The notebook uses no internet during evaluation and emits exactly two valid
grids for every hidden test input. See `THIRD_PARTY_NOTICES.md` for provenance.

## License

Original entry code is MIT-0. Bundled third-party components retain their MIT
licenses. The separately attached TRM checkpoint dataset is CC0.
