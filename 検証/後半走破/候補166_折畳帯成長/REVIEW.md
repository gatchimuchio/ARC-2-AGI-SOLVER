# Candidate166 production validation

PASS for root admission review; no admission or Git write performed.

- Base: accepted164 commit `8ed932f805e6e489005da53870448688caff9059`, 96 tasks / 137 examples.
- Isolated shared-object clone with independent Git metadata. All 2,336 non-cache source/fixture files copied and hashed before native runtime, including ignored official sources. Base remained untouched.
- Updated the existing growth implementation and adapter in place. No competing family. Frozen source SHA256 `6b2139090fb1d2f94412bc8b330f33ed4868a03c1736f3a6f8ab3448ee99faaa` is exact.
- All 19 old model/geometry functions remain AST-identical. The only old function changes are aggregate inclusion and explicit fit-contract version 3→4. Adapter accepts exactly version4; prior version3 is now an additional negative control. Core and HDS bridge are byte-identical.
- Native final parity: both 2×21 and 8×17 outputs exactly equal input-only results through the ordinary single-family/global gates; three current teachers, zero prior support, scorer calls0.
- Preserved old focused controls: 2,385 checks. New strip controls:49 checks. No behavioral assertions removed or relaxed.
- An added result-count formatter initially called len() on an integer after all strip assertions passed. The original failure, script, and first complete regression logs are preserved in `failed-harness-count/`. Only the reporting expression was corrected. A clean complete current rerun then passed.
- Final regression coverage:109 freshly executed scripts plus the unchanged29-case window scope, yielding110 scripts /7,868 checks. `window29-conservation.json` contains exact file hashes and bridge-AST conservation.
- Freeze:2,337 files before the sole official score; bytes, sizes and modes unchanged afterward.
- Sole same-condition score on120 tasks /167 examples: previous96/137, current97/138, delta+1/+1. All137 previous grids exactly conserved; no lost or changed grid; zero wrong outputs or resource failures.
- `delta.json`, `native-parity.json`, `static-review.json`, `full-regression-selected.json`, `pre-score-freeze.json`, and `current-official.json` bind the result. No target-dependent runtime edits were made after scoring.

The existing unrelated generated untracked artifacts were present in accepted164 before this work and remain preserved. No commit, accepted-state update, push, or upload was performed. Root must decide admission.
