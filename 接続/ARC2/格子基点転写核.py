"""Compose accepted lattice, component, D4, and scaled-pattern primitives.

No task identity, output table, or fitted grid is retained.  Every compatible
source/anchor role and every teacher-fitting reflection policy is evaluated.
"""
from collections import Counter
from itertools import product

from 接続.ARC2.既存格子操作 import detect_separator_lattice, transform_grid_by_name
from 接続.ARC2.既存倍率置換 import (
    extract_motif_components, pattern_from_component, compress_pattern,
    anchor_offset, scaled_pattern_cells,
)
from 接続.ARC2.既存物体特徴 import color_components


def valid_grid(grid):
    return (isinstance(grid, list) and 1 <= len(grid) <= 30
            and isinstance(grid[0], list) and 1 <= len(grid[0]) <= 30
            and all(isinstance(row, list) and len(row) == len(grid[0])
                    and all(type(v) is int and 0 <= v <= 9 for v in row)
                    for row in grid))


def square(cells):
    if not cells:
        return None
    top = min(r for r, c in cells)
    left = min(c for r, c in cells)
    bottom = max(r for r, c in cells)
    right = max(c for r, c in cells)
    side = bottom - top + 1
    if side != right - left + 1 or len(cells) != side * side:
        return None
    return top, left, side


def parse_roles(grid):
    if not valid_grid(grid):
        return None, [], {"failure": "invalid_grid"}
    lattice = detect_separator_lattice(grid)
    if lattice is None:
        return None, [], {"failure": "no_separator_lattice"}
    if len(lattice["row_segments"]) != 2 or len(lattice["col_segments"]) != 2:
        return None, [], {"failure": "requires_two_by_two_lattice"}
    bg = lattice["background_color"]
    tiles = []
    for i, (r0, r1) in enumerate(lattice["row_segments"]):
        for j, (c0, c1) in enumerate(lattice["col_segments"]):
            tile = [row[c0:c1+1] for row in grid[r0:r1+1]]
            counts = Counter(v for row in tile for v in row)
            leaders = {v for v, n in counts.items() if n == max(counts.values())}
            if leaders != {bg}:
                return None, [], {"failure": "tile_background_not_unique_and_shared"}
            components = extract_motif_components(tile)
            if len(components) != 1:
                return None, [], {"failure": "tile_requires_one_motif", "tile": [i, j]}
            tiles.append(dict(index=[i, j], bbox=[r0, c0, r1, c1], grid=tile,
                              component=components[0]))
    roles = []
    for si, source in enumerate(tiles):
        colors = set(source["component"]["histogram"])
        if len(colors) < 2:
            continue
        for color in sorted(colors):
            anchors = []
            compatible = True
            for ti, tile in enumerate(tiles):
                parts = color_components(tile["grid"], color)
                geometry = square(parts[0]["cells"]) if len(parts) == 1 else None
                if geometry is None or (ti != si and set(tile["component"]["histogram"]) != {color}):
                    compatible = False
                anchors.append(geometry)
            if not compatible:
                continue
            source_scale, primitive = compress_pattern(pattern_from_component(source["component"]))
            primitive_anchor_cells = {(r, c) for r, row in enumerate(primitive)
                                      for c, v in enumerate(row) if v == color}
            primitive_anchor = square(primitive_anchor_cells)
            if primitive_anchor is None:
                continue
            roles.append(dict(source_index=si, anchor_color=color, anchors=anchors,
                              source_scale=source_scale, primitive=primitive,
                              primitive_anchor_side=primitive_anchor[2]))
    if not roles:
        return None, [], {"failure": "no_complete_source_anchor_role"}
    return dict(lattice=lattice, tiles=tiles, background=bg), roles, {}


def render_role(grid, context, role, policy):
    bg = context["background"]
    source = context["tiles"][role["source_index"]]
    sr, sc = source["index"]
    output = [row[:] for row in grid]
    failures = []
    placements = []
    for ti, tile in enumerate(context["tiles"]):
        tr, tc = tile["index"]
        horizontal = policy[0] and tc != sc
        vertical = policy[1] and tr != sr
        transform = "rot180" if horizontal and vertical else "flip_h" if horizontal else "flip_v" if vertical else "identity"
        pattern = transform_grid_by_name([list(row) for row in role["primitive"]], transform)
        top, left, side = role["anchors"][ti]
        primitive_side = role["primitive_anchor_side"]
        if side % primitive_side:
            failures.append({"tile": ti, "failure": "noninteger_anchor_scale"})
            continue
        scale = side // primitive_side
        ar, ac = anchor_offset(pattern, role["anchor_color"], scale)
        r0, c0, r1, c1 = tile["bbox"]
        cells = scaled_pattern_cells(pattern, scale, r0 + top - ar, c0 + left - ac)
        local_failures = []
        for r, c, value in cells:
            if not (r0 <= r <= r1 and c0 <= c <= c1):
                local_failures.append("placement_outside_tile")
            elif grid[r][c] not in {bg, value}:
                local_failures.append("foreground_collision")
        placements.append(dict(tile=ti, transform=transform, scale=scale, cell_count=len(cells)))
        if local_failures:
            failures.append(dict(tile=ti, failures=sorted(set(local_failures))))
        else:
            for r, c, value in cells:
                output[r][c] = value
    record = dict(source_index=role["source_index"], anchor_color=role["anchor_color"],
                  source_scale=role["source_scale"], placements=placements, failures=failures)
    if failures:
        return None, dict(record, failure="incomplete_role_render")
    return output, record


def render(grid, policy):
    if not isinstance(policy, (tuple, list)) or len(policy) != 2 or any(type(v) is not bool for v in policy):
        return None, {"failure": "invalid_policy"}
    context, roles, rejection = parse_roles(grid)
    if context is None:
        return None, rejection
    results = [render_role(grid, context, role, policy) for role in roles]
    record = {"policy": list(policy), "roles": [r for _, r in results], "role_count": len(results)}
    if any(out is None for out, _ in results):
        return None, dict(record, failure="retained_role_failed")
    outputs = {tuple(map(tuple, out)) for out, _ in results}
    if len(outputs) != 1:
        return None, dict(record, failure="role_full_grid_disagreement")
    return results[0][0], record


def fit(teachers):
    if len(teachers) < 2 or any(not valid_grid(p["input"]) or not valid_grid(p["output"]) for p in teachers):
        return None, {"failure": "invalid_or_insufficient_teachers"}
    if len({tuple(map(tuple, p["input"])) for p in teachers}) != len(teachers):
        return None, {"failure": "duplicate_teacher_inputs"}
    retained = []
    records = []
    for policy in product((False, True), repeat=2):
        results = [render(p["input"], policy) for p in teachers]
        fits = [out == pair["output"] for (out, _), pair in zip(results, teachers)]
        records.append(dict(policy=list(policy), teacher_fits=fits, records=[r for _, r in results]))
        if all(fits):
            retained.append(policy)
    if not retained:
        return None, dict(policies=records, failure="no_teacher_fitting_policy")
    return {"policies": retained}, {"policies": records, "retained_policies": retained}


def consensus(grid, model):
    if not model or not model.get("policies"):
        return None, {"failure": "no_retained_policies"}
    results = [render(grid, policy) for policy in model["policies"]]
    record = {"policy_records": [r for _, r in results], "evaluated_policy_count": len(results)}
    if any(out is None for out, _ in results):
        return None, dict(record, failure="retained_policy_failed")
    if len({tuple(map(tuple, out)) for out, _ in results}) != 1:
        return None, dict(record, failure="policy_full_grid_disagreement")
    return results[0][0], record
