# C2-054 pilot result — teacher-consensus identity override

- Observed: 2026-10-24 16:42 UTC
- Evidence: `P5_HDS_identity_override_LOO_pilot.json`
- Evidence SHA-256: `0598e6c1193090a960b46985943beab73b4fdf5c3d1a2e3066ad879298361d48`
- Scope: 4 eligible public-training tasks, 19 held-out folds; this is a pilot, not full LOO.
- Baseline: 19 fallback; exact, wrong, distinct-second, and union-exact all 0.
- Candidate: 19 fallback; exact, wrong, distinct-second, and union-exact all 0.
- Candidate minus baseline on this same pilot subset: all 0.
- Candidate diagnostics: 172 cell engines, 169 queries, 42 supported identity cells, including 8 identity fills after HDS output-color conflict/quarantine; 7 conflicts and 5 quarantines observed; 0 complete candidate grids.
- Solver time: baseline 164.346 s; candidate 3.917 s. Runtime reduction did not produce a complete grid or solve, so it is not an ability gain.
- `baseline_matches_c2_045` is null because the pilot covers only a subset of the full population; no full-LOO equivalence claim is made.
- A nonfatal SciPy/HiGHS warning reported an unrecognized `threads` option.
- No production solver, notebook, submission artifact, protected file, or official submission was changed.
- Decision: no gain demonstrated; do not adopt and do not expand to full LOO.
