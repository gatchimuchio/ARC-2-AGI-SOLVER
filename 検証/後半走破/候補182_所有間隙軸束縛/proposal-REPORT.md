# Proposal 182: owned row-gap axis binding

Status: pure teacher fit and input-only candidate freeze. Not scored, adopted, committed, or uploaded. Accepted source remains unchanged.

## Observed failure and smallest missing relation

Read the entire purpose instruction, AGENTS, authority order, current state, and strategy. Visually inspected both teachers and both query INPUTS in `grids.png`. No query answers, solutions, scorer, or denied 047 were read.

Current `対称剪定教材.guarded_render` fits both teachers. Query 0 holds on its eight-cell green component, with two retained foreground maxima: axis2 36 and 37, each keeping six cells. Query 1 succeeds. Foreground retention and removal-budget checks do not distinguish the query-0 axes.

Existing C8 object extraction, vertical reflection, deletion action, source renderer, and admission gate remain in use. Existing marker reflection requires an external point/line marker; these objects supply none. Existing bidirectional completion fills zero masks and cannot express background deletion. The missing view is the background intervals bracketed by cells of one C8 object on each row. This is an open or closed row-gap view, not flood-fill cavity detection. Existing wall-profile code uses row-run interior ownership, but its cap/two-rail/terminal semantics do not fit arbitrary objects here, so those semantics were not imported.

All six teacher objects have a nonempty row-gap set, fully symmetric around their unique foreground-maximizing axis. Query 0's tied green object owns gap cell (16,18). Its only complete reflection axis is 36; axis 37 reflects it onto a foreground cell. Both foreground maxima and their removed cells remain in the evidence.

## Narrow extension

Only `source/接続/ARC2/対称剪定教材.py` changes. The existing family learns one additional boolean: every teacher already fits the ORIGINAL guard and its nonempty owned gaps agree with that original axis, with at least one witness per teacher. No teacher/query grid is stored in the fitted object.

The normal renderer defaults to its unchanged behavior. With the fitted boolean, only an actual foreground-maxima tie can consult owned gaps. The complete gap symmetry must be unique and must intersect the foreground-maxima set in exactly one axis. Empty gaps, foreign-color ownership, asymmetric gaps, no intersection, or unresolved intersections remain HOLD. All original edit budgets, original selected-axis agreement, and original rendered-output agreement remain mandatory. Other components, including components with no gaps or imperfect gaps, follow the ordinary unique-maximum path unchanged.

This is an additional input-relation prior supported by all teachers, not a claim of logically unique induction. It does not minimize disconnected noise, choose a left axis, use bounding-box priority as new authority, or add a competing family. The original renderer's tie priority is still only a required agreement check after independent gap binding. If it disagrees, the result remains HOLD.

## Checks

- `check_candidate.py` accepts an arbitrary input-only task file and performs only pure candidate checks: 18 passed.
- Both teachers reproduced exactly; both queries produce candidates; query 1's entire old result tuple is unchanged.
- Preserved default HOLD, gapless tie HOLD, foreign ownership refusal, asymmetric-gap refusal, teacher mismatch/duplicate denial, source-output disagreement, relabeling, and orientation/source-agreement behavior.
- All component maxima and gap witnesses retained in `pure-freeze.json`.
- Existing `検証/対称剪定回帰.py`: 13 passed. Note: that existing suite includes synthetic native-support tests and a synthetic HDS HOLD test. Running the suite therefore executed those synthetic native checks before the requested stage boundary. No target-task native run, official scoring, global regression, adoption, commit, or upload occurred. This stage deviation is disclosed rather than relabeled pure.

Next: independent audit, then parent-controlled HDS/native and regression/evaluation stages if approved. No ARC score improvement is claimed.
