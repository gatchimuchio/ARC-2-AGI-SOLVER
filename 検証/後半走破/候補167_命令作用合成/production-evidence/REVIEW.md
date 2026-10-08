# Candidate167 production review

Status: PASS, pending root acceptance review. No commit, push, upload, or accepted-tree source changes performed.

## Measured result

- Immutable accepted base: candidate166-production-20261007, commit 3838872c3cdb7cad741819b59b4e70f7a0494071. Candidate165 was not used.
- Exactly one official current score: 120 tasks / 167 examples, same challenge/solution hashes, CPU 10 s, memory 512 MiB, wall 60 s, three workers.
- Previous 97 tasks / 138 examples; current 98 / 139; delta +1 / +1.
- All 138 previous emitted grids remain exactly identical. No lost or changed grid. Wrong emitted 0; resource failures 0.
- New emission: 4c7dc4dd query 1. Task identifier appears only in scorer evidence, never runtime routing.

## Integration and validation

- Existing ARC記号命令列 family only. Three existing modules updated, one view module added. All four are byte-identical to proposal167 frozen runtime sources. Actual accepted166 was compared, rather than assuming candidate131/135 was adopted.
- Periodic module SHA256: 2549295bf02989c15b86f7154e1993ad8985ef3f8fb1498f429762786b9c7d24.
- Unchanged HDS bridge, core, global gates, wrapper and other tracked files. Only generated regression JSON outputs are additional artifacts.
- All 1,125 official-source fixture files recursively copied and verified before native execution; native imports checked against candidate167.
- Native final outputs match input-only results exactly (5×5, 6×6); two current teachers, zero prior teachers, equality admitted.
- Targeted production checks: two teachers, five constructed contrasts, three old-outcome preservation cases, periodic pair-local positive; 4,608 independent action comparisons, all 288 actions, seven fallback guards, two resource propagation checks, three binding guards.
- Full existing regression: 109 fresh scripts / 7,839 checks, all successful. Pinned window scope retained only after exact dependency and bridge AST conservation: 29 checks. Composed total 110 scripts / 7,868 checks.
- 2,400 source/data/artifact pins frozen before score and verified unchanged afterward. Proposal freeze remains intact.

## Evidence details

- native-parity.json, import-paths.json, integration.json, static-review.json
- inherited-result.json, independent-result.json, targeted.stdout
- full-regression-current.json, full-regression-selected.json, window29-conservation.json
- pre-score-freeze.json, post-score-pin-conservation.json
- score-command.json, score-terminal.json, current-official.json, delta.json

The composed report inherited a cosmetic scope label starting Candidate166; its root, inventories, fresh execution records and pins correctly identify candidate167. The raw record was preserved instead of rewriting post-freeze evidence.

One initial targeted harness import check incorrectly expected __file__ on a namespace package. Its failed stdout/stderr is retained under initial-harness-import-error. The check was corrected to validate namespace paths, then all targeted checks executed successfully against production modules. No runtime source was changed for this harness correction.
