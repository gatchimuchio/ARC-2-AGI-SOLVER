# NEW135: separate local ink from the enclosing periodic tag

Status: isolated and frozen; no actual query rendered and no acceptance claim.
The accepted base remains clean `8eca96d5ff325bfaef359cf824d8cae50344a499`
at `candidate129-production-20261007`. Its 93/129 result was supplied by the
parent task and was not rerun here.

## Source contract and exact correction

The frozen131 query parser supplies `color` as the pair-local panel rim/ink,
and separately retains `outer_color` as the enclosing group tag. Strict binary
and segment actions consume that local ink. `periodic_action` uses its
`group_color` only as a tag that must be absent from the panel payload; it does
not use that argument to choose or paint a phase color. Binding this argument
to a rim color present in the panel therefore rejects every periodic model.

Only the demonstration and target arguments passed to `periodic_action`
changed: use the explicit `outer_color` when present, otherwise retain
`color`. All four runtime files and their public function signatures are
frozen. The other three files are byte-identical to frozen131. The AST audit
proves that these two arguments are the only change in the fourth file.

The strict interpreter, periodic action implementation, action inventories,
parser/cohort/cover rules, model/direction enumeration, and complete role/model
consensus remain unchanged. The default old parser does not emit
`outer_color`, so all its calls retain exactly the old tag and return records.
The teacher fitter and query fallback gate remain unchanged. No model or
structural role is selected using target rendering success.

## Bounded verification

- Both authorized actual teachers are exact, including the wrapper binding
- Teacher returns and wrapper fit records equal preserved131 exactly
- All five existing constructed contrasts pass with unchanged result records
- All three existing old-outcome preservation cases pass unchanged
- One new constructed periodic pair-local-rim case has one complete role:
  frozen131 has no compatible actions and fails; NEW135 returns the expected
  periodic complement, with the enclosing target tag recorded as 4
- Source/API/result hashes and the exact two-argument AST delta are verified

Run `PYTHONDONTWRITEBYTECODE=1 python check_train_and_contrasts.py` for those
checks only, and `python verify_freeze.py` for the read-only frozen audit.
The ordinary constructed case is not evidence of an actual-query improvement.

## Preserved evidence and exposure

`preserved131/` contains the original proposal131 source, teachers, checks,
result, diff, structural metadata, and freeze unchanged. The parent reported
that its actual changed-view attempt preserved q0 and fit, while q1 had one
complete cohort/cover and no compatible actions. That failure remains part of
the history; it is not replaced by NEW135's constructed positive.

The original failed-attempt receipts remain preserved in place at
`/workspace/scratch/7408259c1ab2/candidate131-view-input-only-20261007`
(`result.json`, `query-1.json`, `terminal.json`). The parent confirmed this
location. This worker references it without duplicating or reading its payload.

The inherited131 structural evidence exposes actual-query panel/group labels,
colors, shapes, positions, and role information. NEW135 must not be described
as a clean label-blind derivation. The correction is justified by the source
contract above. No official query payload, official target, solution or score
was loaded in this task. No actual query was rendered. No accepted-root/HDS
edits, native/full/public runs, candidate047 access, or runtime identifiers
were introduced.

The source/API/actual-teacher result freeze is `freeze.json`; the runtime diff
is `existing-source.diff`. Any later actual-query attempt must retain this
freeze and the earlier failed131 evidence.
