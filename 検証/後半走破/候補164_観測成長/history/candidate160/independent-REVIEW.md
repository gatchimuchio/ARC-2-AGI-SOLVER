# Independent teacher-only audit of original proposal160

Disposition: HOLD original160 pending geometry and portability correction. No accepted production changes or evaluation performed. Only supplied146 teachers, owned160 syntax, and audit-controlled synthetic/adaptor checks were used. The original proposal is preserved in `original/`; audit does not edit author's files.

## Confirmed

- Teacher outputs independently replay 3/3. Fit returns only kind/version after checking every teacher; no target enters predict.
- Axis enumeration includes every prefix/nonempty unit/suffix split of first source with positive exact affine repeat growth and at least one observed repeat. Since positive growth makes first word shortest, using it as the enumeration anchor is sound. No minimum-description selection or successful-subset pruning occurs within this declared axis grammar.
- Run-width affine contradictions reject the family before fitting; single-width extrapolation and future invalid rows count as incomplete after fitting.
- Radial colors/masks use the explicitly declared reused minimal-period operator; every source is fully replayed before extrapolation. This is not completeness over arbitrary unseen periods, and README correctly disclaims that stronger language.
- All four current post-fit radial failure return paths are counted as incomplete. Eight controlled aggregation checks pass: incomplete axis models, four incomplete radial cases, cross-family disagreement, agreement, and ambiguous geometry with a successful radial prediction.

## Required corrections

1. **Modal-background tie silently resolved by first-seen cell.** `tie.py` constructs a 10×15 in-domain grid with counts 0=72, 1=72, 5=6. Identity observe chooses 1 and finds no role; another D4 view chooses 0 and supplies 30 axis predictions, causing EMIT. This does not establish unique background inference. Reject tied modes or explicitly enumerate all background hypotheses under documented completeness semantics. Conservative HOLD is simplest.
2. **Unexplained future index cap.** `check.py` reuses the proposal's synthetic grammar with skip25. Grid65×125 targets zero-based index30, but original observe has no future role and HOLDs. Audit-only extension to index34 yields exact output with 4 predictions and no incompleteness. This is outside ARC30 dimensions but inside the stated pure API and owned synthetic language. Exact integer roots of endpoint polynomials remove the cap; alternatively a rigorously specified input-size restriction and proof are required, not a magic constant.
3. **Radial role enumeration differs from axis.** Axis evaluates each role. Radial re-observes the grid and discards all radial hypotheses whenever total role count differs from one, including roles with no matching future geometry. No realized grid counterexample was established, but this violates claimed role-wise exhaustive composition at the implementation level. Pass an individual role to radial and aggregate every source-fitted outcome.
4. **Proposal is workspace-coupled.** Absolute-path `spec_from_file_location` import from `/tmp` fails with `ModuleNotFoundError: geometry`; sibling helpers rely on ambient sys.path. Accepted156 dependency also uses a named sibling workspace checkout. Use explicit package imports and dependency configuration before integration; the existing documented check.py invocation itself works. See import-report.json.

Author was informed and agrees with tied-mode HOLD, exact horizontal endpoint-root intersection, role-specific radial evaluation, and package-safe imports. Original frozen source must not be silently replaced during review. No teacher-driven model selection or target leakage was found in inspected code.
