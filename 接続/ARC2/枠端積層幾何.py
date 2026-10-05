"""元提案から必要な入力幾何・完全crop描画のみをAST不変で再利用する。"""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from itertools import permutations, product
from . import 既存領域転写 as regions
from . import 既存格子操作 as operations
from . import 既存凡例穴対応 as holes
CENTERS = ("exact", "floor", "ceil")


def grid_key(grid):
    return tuple(tuple(row) for row in grid)


def valid_grid(grid):
    return (isinstance(grid, list) and 1 <= len(grid) <= 30
            and isinstance(grid[0], list) and 1 <= len(grid[0]) <= 30
            and all(isinstance(row, list) and len(row) == len(grid[0])
                    and all(type(v) is int and 0 <= v <= 9 for v in row)
                    for row in grid))


def counts(grid, background=None):
    return dict(sorted(Counter(v for row in grid for v in row
                               if background is None or v != background).items()))


@dataclass(frozen=True)
class Program:
    fast_color: int
    connectivity: int
    fast_sign: int
    slow_sign: int
    horizontal_transform: str
    vertical_transform: str
    center: str

    def record(self):
        return asdict(self)


def component_inventory(grid, role, connectivity):
    """Build complete input inventory, including every invalid crop's evidence."""
    payload = role["payload"]
    bg = role["background"]
    row_ids, col_ids = role["row_ids"], role["col_ids"]
    foreground = {(r, c) for r, row in enumerate(payload)
                  for c, value in enumerate(row) if value != bg}
    raw = regions.mixed_region_dicts_for_grid(payload, bg, connectivity == 8)
    owner = {}
    failures = []
    for index, component in enumerate(raw):
        cells = set(component["cells"])
        if len(cells) != component["size"]:
            failures.append({"kind": "domain", "code": "component_record_inconsistent", "component": index})
        for cell in cells:
            if cell not in foreground or cell in owner:
                failures.append({"kind": "domain", "code": "component_ownership_invalid", "cell": cell})
            owner[cell] = index
    if set(owner) != foreground:
        failures.append({"kind": "domain", "code": "incomplete_payload_coverage"})
    objects = []
    for index, component in enumerate(raw):
        r0, c0, r1, c1 = component["bbox"]
        crop = [row[c0:c1 + 1] for row in payload[r0:r1 + 1]]
        foreign = [(r, c, owner[(r, c)]) for r in range(r0, r1 + 1)
                   for c in range(c0, c1 + 1)
                   if (r, c) in owner and owner[(r, c)] != index]
        if foreign:
            failures.append({"kind": "domain", "code": "foreign_payload_in_full_crop",
                             "component": index, "foreign_cells": foreign})
        cells = sorted(component["cells"])
        absolute_cells = [(row_ids[r], col_ids[c]) for r, c in cells]
        objects.append({"id": index, "payload_bbox": list(component["bbox"]),
                        "input_bbox": [row_ids[r0], col_ids[c0], row_ids[r1], col_ids[c1]],
                        "payload_cells": cells, "input_cells": absolute_cells,
                        "size": component["size"], "colors": component["colors"],
                        "color_counts": component["color_counts"], "full_crop": crop,
                        "crop_all_color_counts": counts(crop),
                        "hole_count": holes.component_hole_count(component)})
    if not objects:
        failures.append({"kind": "domain", "code": "empty_payload"})
    return {"connectivity": connectivity, "objects": objects,
            "ownership": [[row_ids[r], col_ids[c], index]
                          for (r, c), index in sorted(owner.items())],
            "foreground_count": len(foreground),
            "foreground_color_counts": counts(payload, bg), "failures": failures}


def prepare_input(grid):
    """No outputs or fitted parameters enter this exhaustive role parser."""
    if not valid_grid(grid):
        return {"input": grid, "roles": [], "corner_probes": [],
                "failure": {"kind": "domain", "code": "invalid_arc_grid"}}
    h, w = len(grid), len(grid[0])
    roles, probes = [], []
    for r_corner, c_corner in product((0, h - 1), (0, w - 1)):
        probe = {"corner": [r_corner, c_corner], "failures": []}
        probes.append(probe)
        rows = [r for r in range(h) if r != r_corner]
        cols = [c for c in range(w) if c != c_corner]
        if not rows or not cols:
            probe["failures"].append("empty_residual_interior")
            continue
        row_colors = sorted({grid[r_corner][c] for c in cols})
        col_colors = sorted({grid[r][c_corner] for r in rows})
        probe.update(horizontal_colors=row_colors, vertical_colors=col_colors,
                     corner_color=grid[r_corner][c_corner])
        if len(row_colors) != 1 or len(col_colors) != 1:
            probe["failures"].append("incident_edge_not_uniform")
            continue
        corner_color = grid[r_corner][c_corner]
        if len({corner_color, row_colors[0], col_colors[0]}) != 3:
            probe["failures"].append("guide_symbols_not_distinct")
            continue
        payload = [[grid[r][c] for c in cols] for r in rows]
        frequencies = Counter(v for row in payload for v in row)
        modes = sorted(c for c, n in frequencies.items() if n == max(frequencies.values()))
        probe.update(residual_color_counts=dict(frequencies), background_hypotheses=modes)
        for bg in modes:
            if bg in {corner_color, row_colors[0], col_colors[0]}:
                probe["failures"].append({"background": bg, "code": "background_is_guide_symbol"})
                continue
            guide_cells = sorted({(r_corner, c) for c in range(w)}
                                 | {(r, c_corner) for r in range(h)})
            role = {"id": len(roles), "corner": [r_corner, c_corner],
                    "horizontal_color": row_colors[0], "vertical_color": col_colors[0],
                    "corner_color": corner_color, "background": bg,
                    "guide_cells": guide_cells, "row_ids": rows, "col_ids": cols,
                    "payload": payload,
                    "background_cells": [(r, c) for r in rows for c in cols if grid[r][c] == bg]}
            role["inventories"] = {str(conn): component_inventory(grid, role, conn) for conn in (4, 8)}
            roles.append(role)
    return {"input": grid, "input_shape": [h, w], "corner_probes": probes, "roles": roles,
            "failure": None if roles else {"kind": "role", "code": "no_boundary_role"}}


def all_orders(objects, role, program, fast_horizontal):
    """Declared lexicographic coordinates; enumerate every complete-key tie."""
    rc, cc = role["corner"]
    by_key = defaultdict(list)
    key_records = []
    for obj in objects:
        distances = [(abs(r - rc), abs(c - cc)) for r, c in obj["input_cells"]]
        fast_axis, slow_axis = (1, 0) if fast_horizontal else (0, 1)
        fast = min(program.fast_sign * v[fast_axis] for v in distances)
        slow = min(program.slow_sign * v[slow_axis] for v in distances)
        key = (slow, fast)
        by_key[key].append(obj["id"])
        key_records.append({"object": obj["id"], "scan_key": key})
    groups = [by_key[key] for key in sorted(by_key)]
    orders = [tuple(i for group in choice for i in group)
              for choice in product(*(permutations(group) for group in groups))]
    return orders, key_records


def render_role(role, program):
    inventory = role["inventories"][str(program.connectivity)]
    record = {"role_id": role["id"], "connectivity": program.connectivity,
              "failure": None, "alternatives": []}
    # These are input/program semantic failures, never resource failures.
    if program.fast_color not in (role["horizontal_color"], role["vertical_color"]):
        record["failure"] = {"kind": "role", "code": "fast_symbol_absent_from_edges"}
        return record
    if inventory["failures"]:
        record["failure"] = {"kind": "domain", "code": "component_inventory_invalid",
                             "details": inventory["failures"]}
        return record
    fast_horizontal = program.fast_color == role["horizontal_color"]
    transform = program.horizontal_transform if fast_horizontal else program.vertical_transform
    record.update(fast_axis="horizontal" if fast_horizontal else "vertical", transform=transform)
    objects = inventory["objects"]
    orders, keys = all_orders(objects, role, program, fast_horizontal)
    record["scan_keys"] = keys
    tiles = {obj["id"]: operations.transform_grid_by_name(obj["full_crop"], transform) for obj in objects}
    width = max(len(tile[0]) for tile in tiles.values())
    height = sum(len(tile) for tile in tiles.values())
    record["output_shape"] = [height, width]
    for order in orders:
        result = {"order": order, "output": None, "failure": None, "placements": []}
        record["alternatives"].append(result)
        if not 1 <= height <= 30 or not 1 <= width <= 30:
            result["failure"] = {"kind": "domain", "code": "output_arc_bounds"}
            continue
        odd_ids = [i for i in order if (width - len(tiles[i][0])) % 2]
        if program.center == "exact" and odd_ids:
            result["failure"] = {"kind": "domain", "code": "nonintegral_center", "objects": odd_ids}
            continue
        out = [[role["background"]] * width for _ in range(height)]
        offset = 0
        for i in order:
            tile, obj = tiles[i], objects[i]
            difference = width - len(tile[0])
            left = (difference + (program.center == "ceil")) // 2
            for r, row in enumerate(tile):
                out[offset + r][left:left + len(row)] = row
            transformed_cells = [(r, c) for r, row in enumerate(tile)
                                 for c, value in enumerate(row) if value != role["background"]]
            tile_component = {"cells": transformed_cells,
                              "bbox": (0, 0, len(tile) - 1, len(tile[0]) - 1)}
            checks = {"all_crop_color_counts": counts(tile) == obj["crop_all_color_counts"],
                      "foreground_color_counts": counts(tile, role["background"]) == obj["color_counts"],
                      "holes": holes.component_hole_count(tile_component) == obj["hole_count"]}
            if not all(checks.values()):
                raise AssertionError(("primitive_or_preservation_contract_broken", checks))
            result["placements"].append({"object": i, "source_bbox": obj["input_bbox"],
                                         "transform": transform, "transformed_crop": tile,
                                         "target_bbox": [offset, left, offset + len(tile) - 1,
                                                         left + len(tile[0]) - 1],
                                         "checks": checks})
            offset += len(tile)
        if counts(out, role["background"]) != inventory["foreground_color_counts"]:
            raise AssertionError("foreground_conservation_broken")
        result.update(output=out, foreground_conservation=True)
    return record


def collapse(records):
    failures = [record["failure"] for record in records if record["failure"]]
    outputs = []
    for record in records:
        for result in record["alternatives"]:
            if result["failure"]:
                failures.append(result["failure"])
            else:
                outputs.append(result["output"])
    if failures:
        return None, {"kind": "unresolved", "code": "one_or_more_hypotheses_failed", "failures": failures}
    if not outputs:
        return None, {"kind": "role", "code": "no_rendered_hypotheses"}
    if len({grid_key(out) for out in outputs}) != 1:
        return None, {"kind": "ambiguity", "code": "role_or_order_disagreement"}
    return outputs[0], None
