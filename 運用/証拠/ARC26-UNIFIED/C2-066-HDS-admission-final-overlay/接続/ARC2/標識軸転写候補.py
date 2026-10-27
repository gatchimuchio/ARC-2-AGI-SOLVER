"""Teacher-only attempt02 chirality transfer; a separate new, unconfirmed fixed prior.

The prospective 360-program contract is immutable. This module receives grids and
programs only; it has no task IDs, query loader, scorer, HDS, publication, or palette
special case. Exact SIDE_TRANSFORM_MAPS, D4, and mixed-component primitives are
imported from the current repository, without weakening the old edge extractor.
"""
from __future__ import annotations

from collections import Counter
from itertools import product

from .既存辺対応抽出 import SIDE_TRANSFORM_MAPS
from .既存格子操作 import transform_grid_by_name
from .既存領域転写 import mixed_region_dicts_for_grid
from .標識組立教材 import valid_grid

RESOURCE_ERRORS = (MemoryError, RecursionError, TimeoutError)
SIDES = ("top", "bottom", "left", "right")


def programs():
    return [dict(body_color=b, marker_color=m, object_connectivity=c,
                 unconstrained_axis_chirality=s)
            for b, m, c, s in product(range(10), range(10), (4, 8), (-1, 1)) if b != m]


def valid_program(p):
    return (isinstance(p, dict) and set(p) == {"body_color", "marker_color",
            "object_connectivity", "unconstrained_axis_chirality"}
            and all(type(x) is int for x in p.values())
            and 0 <= p["body_color"] <= 9 and 0 <= p["marker_color"] <= 9
            and p["body_color"] != p["marker_color"]
            and p["object_connectivity"] in (4, 8)
            and p["unconstrained_axis_chirality"] in (-1, 1))


def bbox(cells):
    return [min(r for r, c in cells), min(c for r, c in cells),
            max(r for r, c in cells), max(c for r, c in cells)]


def intervals(indices):
    out = []
    for i in sorted(indices):
        if out and i == out[-1][1] + 1:
            out[-1][1] = i
        else:
            out.append([i, i])
    return out


def inside(cell, box):
    r, c = cell
    r0, c0, r1, c1 = box
    return r0 <= r <= r1 and c0 <= c <= c1


def band_view(grid, background, order, record=None):
    """Remove complete lines in the residual Cartesian rectangle to a fixed point.

    Every maximal same-color adjacent run is a band; the full trace includes each
    removed line and cell, with no width or round limit. Both orders are retained.
    """
    h, w = len(grid), len(grid[0])
    rows, cols = set(range(h)), set(range(w))
    rec = {} if record is None else record
    rec.update(order=list(order), removal_rounds=[], fixed_cells=[],
               remaining_rows=sorted(rows), remaining_cols=sorted(cols), chambers=[])
    fixed, rounds = set(), rec["removal_rounds"]
    while rows and cols:
        changed = False
        for axis in order:
            rec["active_stage"] = dict(axis=axis, scan_complete=False, scanned_line_indices=[])
            own, other = (rows, cols) if axis == "row" else (cols, rows)
            lines = []
            rec["active_stage"]["candidate_lines"] = lines
            for i in sorted(own):
                cells = [(i, j) if axis == "row" else (j, i) for j in sorted(other)]
                colors = {grid[r][c] for r, c in cells}
                if len(colors) == 1 and background not in colors:
                    lines.append(dict(index=i, color=next(iter(colors)), cells=cells))
                rec["active_stage"]["scanned_line_indices"].append(i)
            rec["active_stage"]["scan_complete"] = True
            if lines:
                bands = []
                rec["active_stage"]["bands"] = bands
                for line in lines:
                    if (bands and line["index"] == bands[-1]["end"] + 1
                            and line["color"] == bands[-1]["color"]):
                        bands[-1]["end"] = line["index"]
                        bands[-1]["cells"].extend(line["cells"])
                    else:
                        bands.append(dict(start=line["index"], end=line["index"],
                                          color=line["color"], cells=list(line["cells"])))
                rounds.append(dict(axis=axis, lines=lines, bands=bands))
                for line in lines:
                    own.remove(line["index"])
                    fixed.update(line["cells"])
                    rec["fixed_cells"] = sorted(fixed)
                    rec["remaining_rows"] = sorted(rows)
                    rec["remaining_cols"] = sorted(cols)
                changed = True
            if not rows or not cols:
                break
        if not changed:
            break
    rec.pop("active_stage", None)
    if not rows or not cols:
        rec["failure"] = "all_lines_removed"
        return rec
    for rr, cc in product(intervals(rows), intervals(cols)):
        r0, r1 = rr
        c0, c1 = cc
        adjacent = {
            "top": [(r0 - 1, c) for c in range(c0, c1 + 1)] if r0 else [],
            "bottom": [(r1 + 1, c) for c in range(c0, c1 + 1)] if r1 + 1 < h else [],
            "left": [(r, c0 - 1) for r in range(r0, r1 + 1)] if c0 else [],
            "right": [(r, c1 + 1) for r in range(r0, r1 + 1)] if c1 + 1 < w else [],
        }
        walls, wall_records, failures = {}, {}, []
        chamber = dict(index=len(rec["chambers"]), bbox=[r0, c0, r1, c1],
                       walls=walls, wall_records=wall_records, side_failures=failures,
                       complete=False)
        rec["chambers"].append(chamber)
        for side, cells in adjacent.items():
            colors = {grid[r][c] for r, c in cells}
            wall_records[side] = dict(cells=cells, colors=sorted(colors),
                                      all_fixed=set(cells) <= fixed)
            if not cells:
                walls[side] = None
            elif set(cells) <= fixed and len(colors) == 1:
                walls[side] = next(iter(colors))
            else:
                failures.append(side)
        if failures:
            chamber["failure"] = "incomplete_or_nonmonochrome_adjacent_wall"
            chamber["failure_sides"] = failures
        chamber["complete"] = True
    if any("failure" in c for c in rec["chambers"]):
        rec["failure"] = "invalid_chamber_walls"
    return rec


def parse_roles(grid, background, p, view, record=None):
    rec = {} if record is None else record
    rec.update(objects=[], anchors=[], components=[], failures=[], owned_foreground=[])
    if "failure" in view:
        rec["failures"].append(view["failure"])
        return rec
    fixed = set(map(tuple, view["fixed_cells"]))
    bar_palette = {grid[r][c] for r, c in fixed}
    b, m = p["body_color"], p["marker_color"]
    rec["bar_palette"] = sorted(bar_palette)
    if b in bar_palette | {background} or m in bar_palette | {background}:
        rec["failures"].append("body_or_marker_conflicts_with_background_or_bars")
        return rec
    if not fixed:
        rec["failures"].append("no_fixed_bands")
        return rec
    masked = [[background if (r, c) in fixed else value for c, value in enumerate(row)]
              for r, row in enumerate(grid)]
    rec["component_extraction"] = dict(primitive="existing_mixed_region_dicts_for_grid",
        complete=False, interruption_boundary="Unmodified legacy primitive is atomic; internal partial component traversal is unavailable")
    components = mixed_region_dicts_for_grid(masked, background,
                                            include_diagonal=p["object_connectivity"] == 8)
    rec["component_extraction"].update(complete=True, returned_components=components)
    owned = set()
    for component in components:
        cells = set(map(tuple, component["cells"]))
        colors = set(component["colors"])
        chambers = [c["index"] for c in view["chambers"]
                    if all(inside(x, c["bbox"]) for x in cells)]
        raw = dict(component=component, chamber_indices=chambers)
        rec["components"].append(raw)
        owned.update(cells)
        rec["owned_foreground"] = sorted(owned)
        if len(chambers) != 1:
            raw["failure"] = "component_chamber_ownership_not_unique"
        elif b in colors:
            body = {x for x in cells if grid[x[0]][x[1]] == b}
            marker = {x for x in cells if grid[x[0]][x[1]] == m}
            label = cells - body - marker
            r0, c0, r1, c1 = bbox(body)
            label_records, constraints, failures = [], [], []
            raw.update(body_cells=sorted(body), marker_cells=sorted(marker),
                       label_records=label_records, constraints=constraints, role_failures=failures)
            for r, c in sorted(label):
                sides = []
                if r < r0 and c0 <= c <= c1: sides.append("top")
                if r > r1 and c0 <= c <= c1: sides.append("bottom")
                if c < c0 and r0 <= r <= r1: sides.append("left")
                if c > c1 and r0 <= r <= r1: sides.append("right")
                label_records.append(dict(cell=[r, c], color=grid[r][c], sides=sides))
                if len(sides) != 1:
                    failures.append("label_not_exactly_one_outside_face")
                else:
                    constraints.append(dict(side=sides[0], color=grid[r][c], cell=[r, c]))
            by_side = {side: {x["color"] for x in constraints if x["side"] == side}
                       for side in SIDES}
            if any(len(values) > 1 for values in by_side.values()):
                failures.append("inconsistent_colors_on_label_side")
            if not marker: failures.append("object_has_no_marker")
            if not label: failures.append("object_has_no_label")
            obj = dict(index=len(rec["objects"]), cells=sorted(cells), bbox=bbox(cells),
                       body_cells=sorted(body), marker_cells=sorted(marker),
                       label_cells=sorted(label), body_bbox=[r0, c0, r1, c1],
                       source_chamber=chambers[0], label_records=label_records,
                       constraints=constraints, failures=failures)
            rec["objects"].append(obj)
            raw["role"] = "object"
            if failures: raw["failure"] = "invalid_object_roles"
        elif colors == {m}:
            rec["anchors"].append(dict(index=len(rec["anchors"]), cells=sorted(cells),
                                       bbox=bbox(cells), chamber=chambers[0]))
            raw["role"] = "anchor"
        else:
            raw["failure"] = "unowned_foreground_component"
    foreground = {(r, c) for r, row in enumerate(grid) for c, v in enumerate(row)
                  if v != background and (r, c) not in fixed}
    if owned != foreground:
        rec["failures"].append("foreground_inventory_incomplete")
    if any("failure" in x for x in rec["components"]):
        rec["failures"].append("invalid_foreground_role")
    if not rec["objects"] or not rec["anchors"]:
        rec["failures"].append("no_objects_or_anchors")
    if len(rec["objects"]) != len(rec["anchors"]):
        rec["failures"].append("object_anchor_counts_differ")
    rec["owned_foreground"] = sorted(owned)
    return rec


def source_axis(side):
    return "row" if side in ("top", "bottom") else "col"


def transform_determinant(transform):
    """Derive chirality from the old side map's two positive source basis axes.

    Columns are the destination vectors of positive source row and column.
    det(G T G^-1) == det(T); this geometric invariant is the new fixed prior,
    not an assertion that the task semantics must select a given chirality.
    """
    vectors = {"top": (-1, 0), "bottom": (1, 0), "left": (0, -1), "right": (0, 1)}
    row_vector = vectors[SIDE_TRANSFORM_MAPS[transform]["bottom"]]
    col_vector = vectors[SIDE_TRANSFORM_MAPS[transform]["right"]]
    return row_vector[0] * col_vector[1] - row_vector[1] * col_vector[0]


def enumerate_proposals(grid, background, p, view, roles, records):
    for obj in roles["objects"]:
        r0, c0, r1, c1 = obj["bbox"]
        cells = set(map(tuple, obj["cells"]))
        crop = [[grid[r][c] if (r, c) in cells else background
                 for c in range(c0, c1 + 1)] for r in range(r0, r1 + 1)]
        axes = {source_axis(x["side"]) for x in obj["constraints"]}
        free_axis = next(iter({"row", "col"} - axes)) if len(axes) == 1 else None
        for name, side_map in SIDE_TRANSFORM_MAPS.items():
            transformed = transform_grid_by_name(crop, name)
            if transformed is None:
                raise AssertionError("existing_D4_rejected_its_declared_transform")
            marker = {(r, c) for r, row in enumerate(transformed) for c, v in enumerate(row)
                      if v == p["marker_color"]}
            foreground = [(r, c, v) for r, row in enumerate(transformed)
                          for c, v in enumerate(row) if v != background]
            for chamber, anchor in product(view["chambers"], roles["anchors"]):
                proposal = dict(index=len(records), object=obj["index"],
                                transform=name, chamber=chamber["index"], anchor=anchor["index"],
                                transformed_crop=transformed, transformed_marker=sorted(marker),
                                constrained_axes=sorted(axes), free_axis=free_axis,
                                transform_determinant=transform_determinant(name),
                                constraints=[], rejection_reasons=[])
                records.append(proposal)
                for constraint in obj["constraints"]:
                    destination_side = side_map[constraint["side"]]
                    wall_color = chamber["walls"].get(destination_side)
                    satisfied = constraint["color"] == wall_color
                    proposal["constraints"].append(dict(**constraint,
                        destination_side=destination_side, wall_color=wall_color, satisfied=satisfied))
                if not all(x["satisfied"] for x in proposal["constraints"]):
                    proposal["rejection_reasons"].append("label_wall_mismatch")
                if free_axis and proposal["transform_determinant"] != p["unconstrained_axis_chirality"]:
                    proposal["rejection_reasons"].append("one_axis_chirality_mismatch")
                if anchor["chamber"] != chamber["index"]:
                    proposal["rejection_reasons"].append("anchor_not_in_chamber")
                target = set(map(tuple, anchor["cells"]))
                dr = min(r for r, c in target) - min(r for r, c in marker)
                dc = min(c for r, c in target) - min(c for r, c in marker)
                proposal["translation"] = [dr, dc]
                translated_marker = {(r + dr, c + dc) for r, c in marker}
                if translated_marker != target:
                    proposal["rejection_reasons"].append("complete_marker_support_mismatch")
                footprint = [(r + dr, c + dc, v) for r, c, v in foreground]
                proposal["footprint"] = footprint
                if any(not (0 <= r < len(grid) and 0 <= c < len(grid[0])) for r, c, v in footprint):
                    proposal["rejection_reasons"].append("out_of_bounds")
                if any(not inside((r, c), chamber["bbox"]) for r, c, v in footprint):
                    proposal["rejection_reasons"].append("outside_destination_chamber")
                proposal["admitted"] = not proposal["rejection_reasons"]


def render_assignment(grid, background, p, view, roles, selected, record=None):
    rec = {} if record is None else record
    rec.update(proposals=[x["index"] for x in selected], failures=[],
               erased_source_cells=[], checked_paint_cells=[])
    fixed = set(map(tuple, view["fixed_cells"]))
    source = {tuple(cell) for obj in roles["objects"] for cell in obj["cells"]}
    anchors = {tuple(cell) for anchor in roles["anchors"] for cell in anchor["cells"]}
    out = [row[:] for row in grid]
    for r, c in sorted(source):
        out[r][c] = background
        rec["erased_source_cells"].append([r, c])
    painted, paint = set(), {}
    for proposal in selected:
        assigned = set(map(tuple, roles["anchors"][proposal["anchor"]]["cells"]))
        for r, c, value in proposal["footprint"]:
            cell = (r, c)
            if not (0 <= r < len(grid) and 0 <= c < len(grid[0])):
                rec["failures"].append("out_of_bounds")
                continue
            if cell in painted: rec["failures"].append("moved_object_overlap_including_same_color")
            if cell in fixed: rec["failures"].append("fixed_bar_overlap")
            if cell in anchors and not (cell in assigned and value == p["marker_color"]):
                rec["failures"].append("foreign_anchor_overlap")
            if out[r][c] != background and not (cell in assigned and value == p["marker_color"]
                                                and out[r][c] == p["marker_color"]):
                rec["failures"].append("foreign_foreground_overlap")
            painted.add(cell)
            paint[cell] = value
            rec["checked_paint_cells"].append([r, c, value])
    rec["paint"] = [[r, c, paint[(r, c)]] for r, c in sorted(paint)]
    if rec["failures"]:
        return None, rec
    for (r, c), value in paint.items(): out[r][c] = value
    counts_before = Counter(v for row in grid for v in row)
    counts_expected = counts_before.copy()
    internal_marker_count = sum(len(x["marker_cells"]) for x in roles["objects"])
    counts_expected[p["marker_color"]] -= internal_marker_count
    counts_expected[background] += internal_marker_count
    counts_after = Counter(v for row in out for v in row)
    rec["conservation"] = dict(before=dict(counts_before), expected=dict(counts_expected),
                                after=dict(counts_after), consumed_internal_markers=internal_marker_count)
    if counts_after != counts_expected: rec["failures"].append("color_count_conservation_failed")
    untouched = {(r, c) for r, row in enumerate(grid) for c in range(len(row))} - source - painted
    if any(out[r][c] != grid[r][c] for r, c in untouched | fixed):
        rec["failures"].append("fixed_or_unowned_cell_changed")
    if not valid_grid(out) or len(out) != len(grid) or len(out[0]) != len(grid[0]):
        rec["failures"].append("shape_or_palette_changed")
    return (None if rec["failures"] else out), rec


def all_assignments(grid, background, p, view, roles, proposals, trace):
    by_object = [[x for x in proposals if x["object"] == i and x["admitted"]]
                 for i in range(len(roles["objects"]))]
    trace["per_object_proposal_indices"] = [[x["index"] for x in xs] for xs in by_object]
    trace["assignments"] = []
    trace["assignment_rejections"] = []

    def visit(i, selected, used):
        trace["active_search_path"] = dict(object_index=i,
            proposals=[x["index"] for x in selected], used_anchors=sorted(used))
        if i == len(by_object):
            if used != set(range(len(roles["anchors"]))):
                trace["assignment_rejections"].append(dict(proposals=[x["index"] for x in selected],
                                                            failure="unused_anchor"))
                return
            assignment = dict(output=None, detail={}, complete=False)
            trace["assignments"].append(assignment)
            output, detail = render_assignment(grid, background, p, view, roles, selected,
                                                record=assignment["detail"])
            assignment.update(output=output, detail=detail, complete=True)
            return
        for proposal in by_object[i]:
            if proposal["anchor"] in used:
                trace["assignment_rejections"].append(dict(
                    proposals=[x["index"] for x in selected] + [proposal["index"]],
                    failure="anchor_already_assigned"))
                continue
            visit(i + 1, selected + [proposal], used | {proposal["anchor"]})

    visit(0, [], set())
    trace.pop("active_search_path", None)
    assignments = trace["assignments"]
    if not assignments: return None, "no_complete_bijective_assignment"
    if any(x["output"] is None for x in assignments): return None, "complete_assignment_failed"
    outputs = {tuple(map(tuple, x["output"])) for x in assignments}
    if len(outputs) != 1: return None, "complete_assignment_outputs_disagree"
    return assignments[0]["output"], None


def render(grid, p):
    trace = dict(program=p, views=[], output=None)
    try:
        if not valid_grid(grid):
            trace["failure"] = "invalid_arc_grid"
            return None, trace
        if not valid_program(p):
            trace["failure"] = "invalid_program"
            return None, trace
        counts = Counter(v for row in grid for v in row)
        highest = max(counts.values())
        modes = sorted(v for v, n in counts.items() if n == highest)
        trace["background_modes"] = modes
        if len(modes) != 1:
            trace["failure"] = "background_mode_tie"
            return None, trace
        background = modes[0]
        trace["background"] = background
        for order in (("row", "col"), ("col", "row")):
            vt = dict(partition={}, roles={}, proposals=[], admitted=False, stage="band_view")
            trace["views"].append(vt)
            band_view(grid, background, order, record=vt["partition"])
            vt["stage"] = "parse_roles"
            roles = parse_roles(grid, background, p, vt["partition"], record=vt["roles"])
            if roles["failures"]:
                vt["failure"] = "raw_role_view_out_of_scope"
                vt["output"] = None
                vt["stage"] = "complete"
                continue
            vt["admitted"] = True
            vt["stage"] = "enumerate_proposals"
            enumerate_proposals(grid, background, p, vt["partition"], roles, vt["proposals"])
            vt["stage"] = "all_assignments"
            vt["output"], failure = all_assignments(grid, background, p, vt["partition"], roles,
                                                    vt["proposals"], vt)
            if failure: vt["failure"] = failure
            vt["stage"] = "complete"
        admitted = [x for x in trace["views"] if x["admitted"]]
        if not admitted:
            trace["failure"] = "no_admitted_role_view"
        elif any(x["output"] is None for x in admitted):
            trace["failure"] = "admitted_role_view_failed"
        elif len({tuple(map(tuple, x["output"])) for x in admitted}) != 1:
            trace["failure"] = "admitted_role_outputs_disagree"
        else:
            trace["output"] = admitted[0]["output"]
        return trace["output"], trace
    except RESOURCE_ERRORS as exc:
        trace["resource_exception"] = type(exc).__name__
        exc.partial_full_return = trace
        raise


def consensus(grid, fitted_programs):
    trace = dict(program_returns=[], output=None)
    try:
        for index, p in enumerate(fitted_programs):
            output, detail = render(grid, p)
            trace["program_returns"].append(dict(index=index, program=p, output=output, detail=detail))
        if not fitted_programs: trace["failure"] = "no_teacher_fit_program"
        elif any(x["output"] is None for x in trace["program_returns"]):
            trace["failure"] = "retained_program_failed"
        elif len({tuple(map(tuple, x["output"])) for x in trace["program_returns"]}) != 1:
            trace["failure"] = "retained_program_outputs_disagree"
        else: trace["output"] = trace["program_returns"][0]["output"]
        return trace["output"], trace
    except RESOURCE_ERRORS as exc:
        trace["resource_exception"] = type(exc).__name__
        trace["interrupted_program_partial_return"] = getattr(exc, "partial_full_return", None)
        exc.partial_full_return = trace
        raise


def fit(teachers, sink=None):
    trace = dict(programs=[], retained_programs=[], conceptual_program_count=360,
                 teacher_count=len(teachers) if isinstance(teachers, list) else None,
                 teacher_validation=[], completed_program_teacher_returns=0)
    try:
        if not isinstance(teachers, list) or not teachers:
            trace["failure"] = "invalid_or_empty_teacher_list"
            return [], trace
        for ti, pair in enumerate(teachers):
            pair_shape = isinstance(pair, dict) and set(pair) == {"input", "output"}
            trace["teacher_validation"].append(dict(teacher_index=ti,
                pair_keys_valid=pair_shape,
                input_valid=pair_shape and valid_grid(pair["input"]),
                output_valid=pair_shape and valid_grid(pair["output"])))
        if any(not all(x[k] for k in ("pair_keys_valid", "input_valid", "output_valid"))
               for x in trace["teacher_validation"]):
            trace["failure"] = "invalid_teacher_pair_or_grid"
            return [], trace
        for index, p in enumerate(programs()):
            pr = dict(index=index, program=p, teachers=[])
            trace["programs"].append(pr)
            for ti, pair in enumerate(teachers):
                output, detail = render(pair["input"], p)
                result = dict(teacher_index=ti, output=output, detail=detail,
                              exact_teacher_match=output is not None and valid_grid(output)
                              and output == pair["output"])
                pr["teachers"].append(result)
                trace["completed_program_teacher_returns"] += 1
                if sink: sink(index, p, result)
            pr["exact_all_teachers"] = bool(teachers) and all(x["exact_teacher_match"] for x in pr["teachers"])
            if pr["exact_all_teachers"]: trace["retained_programs"].append(p)
        return trace["retained_programs"], trace
    except RESOURCE_ERRORS as exc:
        trace["resource_exception"] = type(exc).__name__
        trace["interrupted_render_partial_return"] = getattr(exc, "partial_full_return", None)
        exc.partial_full_return = trace
        raise
