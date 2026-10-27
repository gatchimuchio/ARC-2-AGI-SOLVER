"""Isolated composition of accepted patch, component, placement and mask actions.

Input grids and fitted programs only. No task identifiers or data access.
Fixed priors: isolated, filled rectangular legend patches with a uniform wall
perimeter; each legend is fully partitioned into straight tail-to-head chains;
four-neighbour wall enclosures; rectilinear or diagonal unit translation to the
first blocked swept placement; simultaneous source erase and endpoint paint.
Additional prior: a diagonal unit step requires both orthogonal intermediate
footprints to remain in the same owner region (no boundary corner cutting).
Intermediate marker occupancy is not a boundary; existing endpoint collision
models remain unchanged. This is a boundary-topology prior, not swept physics.
"""
from dataclasses import asdict, dataclass
from itertools import permutations, product

from 接続.ARC2.既存領域転写 import mixed_region_dicts_for_grid, _enclosed_non_wall_regions
from 接続.ARC2.既存物体特徴 import color_components
from 接続.ARC2.既存格子操作 import lattice_tile_mask
from 接続.ARC2.既存配置展開 import crop_bbox
from 接続.ARC2.既存空白移動 import is_rectangle, valid_rectangle_positions
from 接続.ARC2.既存疎点転写 import shifted_sparse_point_mask
from 接続.ARC2.既存凡例穴対応 import clone_grid
from 接続.ARC2.既存色群関係 import bbox_relation_for_bboxes

DIRECTIONS = tuple((dr, dc) for dr, dc in product((-1, 0, 1), repeat=2) if (dr, dc) != (0, 0))


@dataclass(frozen=True, order=True)
class Model:
    background: int
    tail: int
    head: int
    marker: int
    marker_diagonal: bool
    other_markers: str


@dataclass(frozen=True)
class Fitted:
    models: tuple[Model, ...]


def valid_grid(grid):
    return (isinstance(grid, list) and 1 <= len(grid) <= 30
            and isinstance(grid[0], list) and 1 <= len(grid[0]) <= 30
            and all(isinstance(row, list) and len(row) == len(grid[0])
                    and all(type(v) is int and 0 <= v <= 9 for v in row) for row in grid))


def parse(grid, model):
    if not valid_grid(grid):
        return None, {"failure": "invalid_grid"}
    bg, tail, head, marker = model.background, model.tail, model.head, model.marker
    roles = {bg, tail, head, marker}
    if len(roles) != 4 or model.other_markers not in ("block", "transparent"):
        return None, {"failure": "invalid_model"}
    patches, patch_cells, legends, diagnostics = [], set(), {}, []
    local_tail_colors = {tail}
    for component in mixed_region_dicts_for_grid(grid, bg, False):
        colors = set(component["colors"])
        if head not in colors:
            continue
        box = component["bbox"]
        top, left, bottom, right = box
        if component["size"] != (bottom-top+1)*(right-left+1):
            continue
        border = {(r,c) for r in range(top,bottom+1) for c in range(left,right+1)
                  if r in (top,bottom) or c in (left,right)}
        walls = {grid[r][c] for r,c in border}
        if len(walls) != 1 or walls & {bg, head, marker}:
            continue
        wall = next(iter(walls))
        # A color can be a wall in one legend and tail ink in another.
        # Resolve only that role collision from the local rectangular patch;
        # otherwise the fitted tail binding remains mandatory.
        local_tails = colors - {wall, head}
        if len(local_tails) != 1 or local_tails & {bg, marker}:
            continue
        local_tail = next(iter(local_tails))
        if wall != tail and local_tail != tail:
            continue
        local = crop_bbox(grid, box)
        tail_mask = set(lattice_tile_mask(grid, box, local_tail))
        head_mask = set(lattice_tile_mask(grid, box, head))
        ink = tail_mask | head_mask
        view = [[tail if (r,c) in ink else bg for c in range(len(local[0]))]
                for r in range(len(local))]
        chain_records = []
        for chain in color_components(view, tail, True):
            cells = set(chain["cells"])
            ends = cells & head_mask
            options = []
            if len(ends) == 1:
                endpoint = next(iter(ends))
                for dr, dc in DIRECTIONS:
                    expected = {(endpoint[0]-k*dr, endpoint[1]-k*dc)
                                for k in range(1,len(cells))}
                    if expected and expected == cells & tail_mask:
                        options.append((dr,dc))
            chain_records.append({"cells": sorted(cells), "directions": options})
        patch = {"bbox": list(box), "wall": wall, "chains": chain_records}
        diagnostics.append(patch)
        if not chain_records or any(len(x["directions"]) != 1 for x in chain_records):
            return None, {"failure": "legend_chain_unresolved", "patches": diagnostics}
        directions = {x["directions"][0] for x in chain_records}
        if len(directions) != 1:
            return None, {"failure": "legend_directions_disagree", "patches": diagnostics}
        direction = next(iter(directions))
        if wall in legends and legends[wall] != direction:
            return None, {"failure": "same_wall_legends_disagree", "patches": diagnostics}
        legends[wall] = direction
        patches.append(patch)
        patch_cells.update(component["cells"])
        local_tail_colors.add(local_tail)
    if not patches:
        return None, {"failure": "no_legend_patches"}
    signal_colors = (local_tail_colors | {head}) - set(legends)
    signal_cells = {(r,c) for r,row in enumerate(grid) for c,v in enumerate(row) if v in signal_colors}
    if not signal_cells <= patch_cells:
        return None, {"failure": "signal_cells_outside_legends", "patches": patches}
    wall_colors = {v for r,row in enumerate(grid) for c,v in enumerate(row)
                   if (r,c) not in patch_cells} - {bg, marker}
    if not wall_colors <= set(legends):
        return None, {"failure": "wall_color_without_legend", "patches": patches}
    # An aliased instruction color is a wall only where a particular wall
    # component itself encloses a marker. A color match cannot give isolated
    # instruction ink ownership in an unrelated enclosure.
    for wall in local_tail_colors & set(legends):
        for component in color_components(grid, wall, False):
            cells = set(component["cells"])
            if cells <= patch_cells:
                continue
            wall_view = [[wall if (r,c) in cells else bg for c in range(len(grid[0]))]
                         for r in range(len(grid))]
            component_holes = _enclosed_non_wall_regions(wall_view, wall)
            if not any(any(grid[r][c] == marker for r,c in region)
                       for region in component_holes):
                return None, {"failure": "unowned_aliased_wall_component",
                              "wall": wall, "cells": sorted(cells), "patches": patches}
    holes = {wall: [set(x) for x in _enclosed_non_wall_regions(grid,wall)] for wall in legends}
    markers = color_components(grid,marker,model.marker_diagonal)
    if not markers:
        return None, {"failure": "no_markers", "patches": patches}
    objects = []
    for obj in markers:
        cells = set(obj["cells"])
        if not is_rectangle(list(cells)):
            return None, {"failure": "marker_not_rectangle", "cells": sorted(cells)}
        owners = [(wall,index) for wall,regions in holes.items() for index,region in enumerate(regions)
                  if cells <= region]
        objects.append({"cells": sorted(cells), "bbox": list(obj["bbox"]), "owners": owners})
    if any(not x["owners"] for x in objects):
        return None, {"failure": "marker_without_enclosing_wall", "markers": objects, "patches": patches}
    return {"patches": patches, "patch_cells": patch_cells, "legends": legends,
            "holes": holes, "markers": objects}, {"failure": None, "patches": patches, "markers": objects}


def execute(grid, model, scene, owners):
    bg, marker = model.background, model.marker
    h,w = len(grid),len(grid[0])
    events, failures, destinations = [], [], []
    for index, (obj,owner) in enumerate(zip(scene["markers"],owners)):
        wall,hole_index = owner
        dr,dc = scene["legends"][wall]
        source = set(map(tuple,obj["cells"]))
        top,left,bottom,right = obj["bbox"]
        rh,cw = bottom-top+1,right-left+1
        view = clone_grid(grid)
        for r,c in source:
            view[r][c] = bg
        allowed = {bg,marker} if model.other_markers == "transparent" else {bg}
        valid = valid_rectangle_positions(view,rh,cw,allowed)
        region = scene["holes"][wall][hole_index]
        path = [(top,left)]
        row,col = top,left
        while (row+dr,col+dc) in valid:
            if dr and dc:
                flanks = ((row+dr,col), (row,col+dc))
                flank_masks = [shifted_sparse_point_mask(source,rr-top,cc-left,h,w)
                               for rr,cc in flanks]
                if any(mask is None for mask in flank_masks):
                    raise RuntimeError("placement helper and swept shift disagree")
                if any(not mask <= region for mask in flank_masks):
                    break
            moved = shifted_sparse_point_mask(source,row+dr-top,col+dc-left,h,w)
            if moved is None:
                raise RuntimeError("placement helper and shift helper disagree")
            if not moved <= region:
                break
            row,col = row+dr,col+dc
            path.append((row,col))
        target = shifted_sparse_point_mask(source,row-top,col-left,h,w)
        if target is None:
            raise RuntimeError("final valid placement is out of bounds")
        destinations.append(target)
        events.append({"marker": index, "owner": owner, "direction": (dr,dc), "path": path,
                       "source": sorted(source), "target": sorted(target),
                       "box_relation": bbox_relation_for_bboxes(tuple(obj["bbox"]),(row,col,row+rh-1,col+cw-1))._asdict()})
    occupied = set()
    for index,target in enumerate(destinations):
        if occupied & target:
            failures.append({"failure": "destination_overlap", "marker": index})
        occupied.update(target)
    if occupied & scene["patch_cells"]:
        failures.append({"failure": "destination_overlaps_legend"})
    if failures:
        return None, {"failure": "placement_conflict", "failures": failures, "events": events}
    output = clone_grid(grid)
    for obj in scene["markers"]:
        for r,c in obj["cells"]:
            output[r][c] = bg
    for r,c in occupied:
        output[r][c] = marker
    return output, {"failure": None, "events": events}


def render_model(grid, model):
    scene, record = parse(grid,model)
    if scene is None:
        return None, record
    returns = []
    for owners in product(*(obj["owners"] for obj in scene["markers"])):
        output, execution = execute(grid,model,scene,owners)
        returns.append({"owners": owners, "output": output, "record": execution})
    # Every ordinary return is collected before failure or whole-grid consensus.
    if any(x["output"] is None for x in returns):
        return None, {"failure": "owner_alternative_failed", "parse": record, "returns": returns}
    if any(x["output"] != returns[0]["output"] for x in returns):
        return None, {"failure": "owner_outputs_disagree", "parse": record, "returns": returns}
    return returns[0]["output"], {"failure": None, "parse": record, "returns": returns}


def all_models(teachers):
    palettes = [{v for row in p["input"] for v in row} for p in teachers]
    common = sorted(set.intersection(*palettes))
    return tuple(Model(*roles,diagonal,collision)
                 for roles in permutations(common,4)
                 for diagonal,collision in product((False,True),("block","transparent")))


def fit_teachers(teachers):
    if (not isinstance(teachers,list) or len(teachers)<2
            or any(not isinstance(p,dict) or not valid_grid(p.get("input"))
                   or not valid_grid(p.get("output"))
                   or len(p["input"])!=len(p["output"])
                   or len(p["input"][0])!=len(p["output"][0]) for p in teachers)
            or len({tuple(map(tuple,p["input"])) for p in teachers})!=len(teachers)):
        return None, {"failure": "invalid_teachers"}
    alternatives,retained = [],[]
    for model in all_models(teachers):
        returns = []
        for pair in teachers:
            output,record = render_model(pair["input"],model)
            returns.append({"output": output, "record": record, "exact": output == pair["output"]})
        exact = all(x["exact"] for x in returns)
        alternatives.append({"model": asdict(model), "returns": returns, "all_exact": exact})
        if exact:
            retained.append(model)
    return (Fitted(tuple(retained)) if retained else None), {
        "failure": None if retained else "no_shared_model", "complete": True,
        "model_count": len(alternatives), "call_count": len(alternatives)*len(teachers),
        "retained_models": [asdict(m) for m in retained], "alternatives": alternatives}


def predict(grid, fitted):
    if not isinstance(fitted,Fitted) or not fitted.models:
        return None,{"failure": "no_fitted_models"}
    returns = []
    for model in fitted.models:
        output,record = render_model(grid,model)
        returns.append({"model": asdict(model), "output": output, "record": record})
    if any(x["output"] is None for x in returns):
        return None,{"failure": "retained_model_failed", "returns": returns}
    if any(x["output"] != returns[0]["output"] for x in returns):
        return None,{"failure": "retained_model_outputs_disagree", "returns": returns}
    return returns[0]["output"], {"failure": None, "returns": returns}
