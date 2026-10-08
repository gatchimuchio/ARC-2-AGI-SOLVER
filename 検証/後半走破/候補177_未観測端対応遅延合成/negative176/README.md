# Remaining-composition diagnosis 176

Outcome: no new teacher-supported implementation is justified by this scan. Accepted candidate167 / 98 tasks, 139 examples is unchanged. This is a source/history inventory plus one teacher-only diagnostic, not proof that every possible ARC representation is exhausted.

## Ranked concrete gaps

1. **Occluder-port pairing (a47bf94d).** Proposal125 already composes accepted component, octilinear-segment, and complete write-merge helpers with half-edge tracing. All three teachers close, retaining straight and ordered-opposite cover pairings. Its independent unrestricted teacher-0 cover test retains all 15 perfect matchings: 13 violate input constraints and two give different complete outputs. Thus replacing opposite pairing with unrestricted matching cannot close the relation while retaining all alternatives. Stored input-only diagnostic metadata reports incomplete cover pairing; no query grid was inspected here. The genuinely missing relation is which cover ports connect when opposite pairing is not applicable. Another line painter cannot supply that relation. Existing teacher evidence does not identify a safe broader pairing rule.

2. **Cavity incidence and seed ownership (8b7bacbf).** Proposal124 closes all four teachers with (8,8,8,canvas_closed). The source explicitly isolates each monochrome component, derives its C4 cavities, requires unique physical boundary and target ownership, then constructs a bipartite cavity/wire graph. Recorded failures distinguish singleton-seed disagreement from overlapping cavity ownership. These are distinct upstream relations. Accepted hole filling alone cannot resolve either; dropping overlapping owners or picking the successful seed would discard alternatives. The teachers contain no failing instance of those retained contracts. No semantic extension was implemented.

These are ranked diagnostic opportunities, not ready-to-integrate fixes. Their old failure records remain authoritative. The source scan also rejected the apparent new lead faa9f03d after identifying its recovered118 staged-path history.

## New bounded evidence: tangential alignment

581f7754 was examined because proposal132 is still teacher-incomplete, unlike most of the remaining paths. diagnose_alignment.py imports accepted mixed-component extraction and bounded translation and replays the unchanged132 renderer. It compares complete colored shapes, never individual successful pixels.

- Both C4 and C8 views reproduce teacher0/2, but not teacher1: unchanged 2/3.
- Teacher1's square ring, input bbox (2,9,4,11), has the observed translation (+1,-1). Every object in that teacher has a unique full-shape output correspondence.
- Hold other objects at their unique observed destinations and enumerate every in-canvas tangential offset while satisfying the cue's normal-coordinate alignment.
- Exactly three placements have no overlap, no C4 contact, and no C8 contact with the other objects or cues: (+1,-1), (+1,0), (+1,+1).
- Therefore neither collision avoidance nor even strict component separation forces the observed lateral shift. Minimum Manhattan/Euclidean motion instead prefers (+1,0), contradicting that observation.
- No ranking, nearest-gap choice, square-ring exception, or new prediction model was introduced. This diagnostic conditions on teacher destinations to test a claimed necessity; it is not a predictive algorithm.

The initial target-component view treated an unchanged cue touching the last object in teacher0 as part of that output component. Its original evidence and script are retained as *-v1.*. The final diagnostic first checks every input cue unchanged and masks those known cue roles in its diagnostic target view. This restores unique object correspondences for all teachers; it does not change the teacher1 three-placement counterexample. check_alignment.py verifies both C4/C8 evidence paths.

## Full assigned inventory (identifiers are orchestration labels only)

| Task | Relevant preserved route | Concrete current limit / reason not to repeat |
|---|---|---|
| 0934a4d8 | historical079, proposal120 | Original reflection witness absent. Extra D4 and all finite translation checks supplied no useful teacher-supported witness. |
| 247ef758 | 126/129/168 | Equal-size overlap priority unidentified; source-first success cannot erase small-first conflict. |
| 3dc255db | 140 and historical count route | Four retained count/boundary policies close teachers; clipped observations do not distinguish pixel versus C4 count or missing-edge ownership. |
| 446ef5d2 | 153/154/155/158/159 | Rectangle ownership, exact seams and global C4 payload connectivity still leave multiple complete assemblies. No placement preference is identified. |
| 5545f144 | historical052, 144/147 | Forward-first marker traversal is already teacher-complete; snapshot-stride versus consume-all horizons both survive. No new teacher-visible implementation defect found. |
| 581f7754 | 132, new176 diagnostic | Extra tangential translation is not explained by collision, separation, or minimum-motion constraints. |
| 71e489b6 | historical068, 122 | Sequential cleanup/outline grammar already closes teachers; teachers do not distinguish erase/outline collision ordering. No new teacher-derived relation. |
| 7b80bb43 | prior K/I/D work, 157 | Endpoint/root/axis bridge grammar already closes teachers; nonlinear residual/contact cases are explicit domain holds. |
| 88bcf3b4 | 141/143/149/152 | Contact necessity and object-local views already explored; exact rail necessity optimization does not add semantics. No new teacher-visible action defect. |
| 88e364bc | 171r2/174 | Rejected path already checked for owner, direction, obstacle and contextual legend binding; no supported corrective relation. Not revisited. |
| 8b7bacbf | 124 | Seed-role consensus and cavity ownership remain separate unresolved relations; see rank2. |
| 8e5c0c38 | accepted vertical pruning, 130 | Teachers already exact; stored failure is maximum-retention-axis tie. No teacher evidence supports tie-breaking or a new symmetry axis. |
| a47bf94d | 125 | Occluder connectivity beyond opposite pairing unidentified; unrestricted all-matchings already ambiguous. See rank1. |
| a6f40cea | 123/172 | Continuous frame-period2 contradicted by teacher3; unrestricted cycle words expose free phases. Alternate ownership/repaint semantics unidentified. |
| abc82100 | historical keyed stamp, 127/128 | Complete and partial legend views already teacher-complete; unused-label extension is explicit. No new teacher-visible parser defect found. |
| b6f77b65 | accepted support, 170 | Multicolor control intersects/contains/equals are indistinguishable on singleton-control teachers. |
| d35bdbdc | 136/142 | Graph side-midpoint binding already teacher-complete; necessary ownership proof only optimizes impossible cases. No new teacher-supported source binding found. |
| dbff022c | 137/161 | Table-to-scene relevance extension already exists; stored no-table-scene-binding is not repaired by relaxing ownership on teacher success alone. |
| de809cff | 138/165 | Whole-defect ownership and complete visible-boundary witnesses already explored. New priorities or hidden-layer ownership require further evidence. |
| e12f9a14 | 119/169 | Locally D4-identical core windows require different activation; global contact timing/bundle phase remains unidentified. Not repeated. |
| faa9f03d | historical048 exposure; recovered118 | Recovered staged grammar already reproduces4/4 teachers. Distinct repair/control ownership and crossing models are explicit; not a novel composition route. |

62593bfd was excluded because another worker owns it. This inventory does not use rejection labels to select alternative semantics. Histories that are absent were not reconstructed as if verified.

## Scope, artifacts and reproduction

- teachers-only.json: train pairs only, extracted from the authorized sanitized challenge source; no test input/output stored here.
- alignment-evidence.json: all final teacher correspondences and every tangential-offset trial, including failures.
- alignment-evidence-v1.json and diagnose_alignment-v1.py: preserved initial target-view evidence.
- diagnose_alignment.py and check_alignment.py: diagnostic and independent assertions.
- manifest.json: source/evidence hashes and status.

Run:

    python -B proposal176-remaining-composition-diagnosis-20261008/diagnose_alignment.py
    python -B proposal176-remaining-composition-diagnosis-20261008/check_alignment.py

Read-only history review included baseline60 teacher inventory, proposal119–174 source/reports as relevant, recovered118 README/core and teacher verification (4 teachers,8 complete model comparisons,4 reproduced), and scalar failure metadata from preserved input-only diagnostic records. No query grid was displayed, no query prediction was executed, and no targets/solutions/scorer/denied047 were accessed. No accepted edits, HDS/global-gate changes, integration, commits, uploads, or evaluation were performed.

Next useful work requires a genuinely supported new input relation, not another invocation of these same closed or ambiguous routes. The smallest outstanding relation is a finite ownership/connection choice (cover ports, cavity/seed roles, or tangential placement); none is supplied by unchanged drawing primitives alone.
