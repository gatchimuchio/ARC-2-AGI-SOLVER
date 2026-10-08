# Proposed next revision: delay exhaustive peer fit until first applicable query

This is a proposal only. The frozen rejected candidate175 has not been changed and no second official score has been run.

## Necessary condition and equivalence proof

The frozen predict method has two returns before it reads peer_models or calls peer render:

1. If len(tables) != 1, return the entire original legacy candidate, unchanged.
2. Extract the original objects and feature keys. If every key is in the original table, return the entire original legacy candidate, unchanged.

Therefore a peer fit result can affect a returned candidate only when there is exactly one original feature model AND at least one current object key is absent from that model's original teacher table. This is an explicit existing control-flow condition, not an accuracy-derived heuristic, new cap, model filter, reduced domain or successful-subset rule. Empty-object coverage remains vacuously true and delegates exactly as before.

The exhaustive fit implementation consumes only teacher grids and fixed helper functions; it neither reads nor writes the HDS machine, query grid, legacy tables or confirmed-principle set. Deferring it across unchanged original learning and complete-coverage/zero/multimodel predictions does not change its eventual model tuple. For calls where both implementations terminate, candidate outputs and all subsequent failure gates remain identical. Deferral avoids resource failures from work whose result the original candidate branch cannot use; it does not promise that applicable high-cost fitting will fit the production budget.

## Exact proposed design

- Construct legacy as before; build the same tables and confirmed-principle set.
- Store an immutable-in-effect deep snapshot of the original teacher pairs, and an explicit UNFITTED sentinel, instead of running fit in the constructor. A deep snapshot preserves constructor-time teacher values even if callers later mutate their input.
- Keep learn unchanged, including LearningWitness and confirmed-principle provenance.
- In predict, preserve both early legacy delegation branches verbatim. Immediately after the all-known-keys return, ensure the exhaustive fit is evaluated once against the stored teacher snapshot.
- That ensure operation must call exactly the original frozen fit implementation. Keep all 48 programs, every teacher, original enumeration order, all retained alternatives, and exception propagation. Assign the cached model tuple only after successful completion; an interrupted fit must never install a partial model set. Do not silently retry an exception within a prediction.
- Every later applicable prediction reuses the same completed tuple. In particular, cache an empty tuple as a completed result, so failed teacher fitting is not repeated.
- Preserve all current peer-failure, ownership, known/shared-key, exact original HDS missing-request, action-conservation and final-output-consensus checks verbatim.
- Native 記録 must not trigger fitting. Report whether fitting has happened; report the retained count only if fitted, otherwise null/uncomputed. Metadata equality is deliberately not claimed for unused eager fit details; candidate output equality is the contract.

## Required new verification before another score

Independent source review must confirm unchanged exhaustive fit and all failure gates. Tests must count zero fit/render calls during construction, learning, zero/multimodel prediction and fully covered prediction; exactly one fit on the first applicable prediction and zero additional fits for later applicable predictions, including empty-model caching. Compare lazy/eager retained tuples, all outputs and all existing failure injections after materialization. Test caller teacher mutation, input/table/model immutability, fit exceptions with no partial cache, unchanged HDS learning observations and native policy forwarding. Re-run native parity, legacy and full public regression, resource diagnostics, source/protected conservation, then obtain authorization for any official scoring. Keep all rejected175 evidence unchanged.
