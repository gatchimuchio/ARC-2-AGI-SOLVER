"""Complete relational input view over the unchanged strict macro action.

The strict parser/fitter always has priority. A complete zero-role parse alone
permits independently placed source components and framed, independently sized
corner/direction cues on either side of a solid row or column divider.
"""
from itertools import product
from . import 厳密枠命令配置 as strict
from 接続.ARC2.既存枠計数 import perimeter_cells

MODELS = strict.MODELS
fit = strict.fit
act = strict.act
D4 = strict.D4


def partitions(grid):
    """All solid straight splits; each side is tried as the instruction area."""
    h, w = len(grid), len(grid[0])
    views = []
    for transposed in (False, True):
        inspected = strict.transform(grid, 'transpose') if transposed else grid
        for entry in strict.full_height_color_columns(inspected):
            p, color = entry['col'], entry['color']
            extent = h if transposed else w
            if not 0 < p < extent - 1:
                continue
            boxes = (((0, 0, p-1, w-1), (p+1, 0, h-1, w-1)) if transposed
                     else ((0, 0, h-1, p-1), (0, p+1, h-1, w-1)))
            for side in (0, 1):
                views.append({'axis': 'row' if transposed else 'column',
                              'position': p, 'frame_color': color,
                              'instruction_bbox': boxes[side],
                              'canvas_bbox': boxes[1-side]})
    return views


def framed_regions(panel, frame):
    """Rectangular C4 regions whose visible expanded perimeter is all frame."""
    h, w = len(panel), len(panel[0])
    regions = strict.foreground_mixed_components(panel, frame, include_diagonal=False)
    result = []
    for region in regions:
        r0, c0, r1, c1 = region['bbox']
        cells = set(region['cells'])
        if len(cells) != (r1-r0+1)*(c1-c0+1):
            continue
        box = (r0-1, c0-1, r1+1, c1+1)
        visible = {p for p in perimeter_cells(box) if 0 <= p[0] < h and 0 <= p[1] < w}
        vertical = c0 > 0 or c1+1 < w
        horizontal = r0 > 0 or r1+1 < h
        if (not vertical or not horizontal or len(visible) < 4
                or any(panel[r][c] != frame for r, c in visible)):
            continue
        result.append({'bbox': region['bbox'], 'cells': cells,
                       'perimeter': visible,
                       'grid': strict.crop_bbox(panel, region['bbox'])})
    return result


def cues(region, background):
    grid = region['grid']; h, w = len(grid), len(grid[0])
    ink = [(r, c) for r, row in enumerate(grid) for c, value in enumerate(row)
           if value != background]
    colors = {grid[r][c] for r, c in ink}
    if len(colors) != 1:
        return None, None
    anchor = direction = None
    if h >= 2 and w >= 2 and len(ink) == 1:
        r, c = ink[0]
        if r in (0, h-1) and c in (0, w-1):
            anchor = (0 if r == 0 else 2, 0 if c == 0 else 2)
    if h >= 3 and w >= 3 and h % 2 and w % 2 and len(ink) == 2:
        center = (h//2, w//2)
        if center in ink:
            end = next(p for p in ink if p != center)
            dr, dc = end[0]-center[0], end[1]-center[1]
            if abs(dr)+abs(dc) == 1:
                direction = (1+dr, 1+dc)
    return anchor, direction


def relational_parse(grid):
    if not strict.valid_grid(grid):
        return [], {'failure': 'invalid_grid', 'complete': True}
    roles = []; probes = []
    for view in partitions(grid):
        panel = strict.crop_bbox(grid, view['instruction_bbox'])
        canvas = strict.crop_bbox(grid, view['canvas_bbox'])
        frame = view['frame_color']
        regions = framed_regions(panel, frame)
        trace = {**view, 'framed_regions': [list(r['bbox']) for r in regions],
                 'background_returns': []}
        probes.append(trace)
        if len(regions) < 2:
            trace['failure'] = 'fewer_than_two_framed_regions'
            continue
        for bg in sorted(set(sum(panel, [])) - {frame}):
            cue_roles = [cues(region, bg) for region in regions]
            anchors = [(i, pair[0]) for i, pair in enumerate(cue_roles) if pair[0] is not None]
            directions = [(i, pair[1]) for i, pair in enumerate(cue_roles) if pair[1] is not None]
            for (ai, anchor), (di, direction) in product(anchors, directions):
                entry = {'background': bg, 'anchor_region': ai, 'direction_region': di}
                trace['background_returns'].append(entry)
                if ai == di:
                    entry['failure'] = 'cue_roles_overlap'; continue
                cue_cells = regions[ai]['cells'] | regions[di]['cells']
                source = [[bg if value == frame or (r, c) in cue_cells else value
                           for c, value in enumerate(row)] for r, row in enumerate(panel)]
                components = strict.foreground_mixed_components(source, bg)
                pairs = [(a, b) for a in components for b in components
                         if a is not b and len(a['colors']) == 2 and len(b['colors']) == 1
                         and b['colors'][0] not in a['colors']]
                if len(components) != 2 or len(pairs) != 1:
                    entry['failure'] = 'source_component_roles'; continue
                tile, stencil = pairs[0]
                tile_grid = strict.crop_bbox(source, tile['bbox'])
                if (len(tile_grid) != len(tile_grid[0])
                        or set(sum(tile_grid, [])) != set(tile['colors'])):
                    entry['failure'] = 'template_not_full_two_colour_square'; continue
                stencil_grid = strict.crop_bbox(source, stencil['bbox'])
                if set(sum(stencil_grid, [])) - {bg, stencil['colors'][0]}:
                    entry['failure'] = 'foreign_source_inside_stencil_bbox'; continue
                source_cells = set(tile['cells']) | set(stencil['cells'])
                frame_cells = {(r, c) for r, row in enumerate(panel)
                               for c, value in enumerate(row) if value == frame}
                frame_owners = regions[ai]['perimeter'] | regions[di]['perimeter']
                source_regions = []
                for ri, region in enumerate(regions):
                    if ri in (ai, di):
                        continue
                    contained = [component for component in (tile, stencil)
                                 if set(component['cells']) <= region['cells']]
                    if contained:
                        frame_owners |= region['perimeter']; source_regions.append(ri)
                if frame_owners != frame_cells:
                    entry['failure'] = 'unowned_frame_cells'; continue
                cue_ink = {(r, c) for r, c in cue_cells if panel[r][c] != bg}
                foreground = {(r, c) for r, row in enumerate(panel)
                              for c, value in enumerate(row) if value != bg}
                if ((source_cells | cue_ink | frame_cells) != foreground
                        or source_cells & cue_cells or source_cells & frame_cells
                        or cue_ink & frame_cells):
                    raise RuntimeError('relational_input_ownership_failed')
                role = {'source': source, 'background': bg, 'tile': tile_grid,
                        'tile_bbox': tile['bbox'], 'stencil_bbox': stencil['bbox'],
                        'cue_size': 3, 'anchor': anchor, 'direction': direction,
                        'canvas': canvas}
                entry.update(role_index=len(roles), source_regions=source_regions,
                             source_cells=len(source_cells), cue_ink_cells=len(cue_ink),
                             frame_cells=len(frame_cells), neutral_cells=sum(v == bg for row in panel for v in row),
                             instruction_cells=len(panel)*len(panel[0]),
                             canvas_cells=len(canvas)*len(canvas[0]))
                roles.append(role)
    return roles, {'complete': True, 'roles': len(roles), 'view_probes': probes}


def render(grid, model):
    original_roles, original_record = strict.parse(grid)
    if original_roles or not strict.valid_grid(grid):
        return strict.render(grid, model)
    roles, record = relational_parse(grid)
    returns = [{'role_index': i, 'return': out, 'record': rec}
               for i, role in enumerate(roles) for out, rec in [strict.act(role, model)]]
    record.update(original_parse=original_record, model=model, role_returns=returns)
    if not returns:
        return None, {**record, 'failure': 'no_complete_relational_role'}
    if any(r['return'] is None for r in returns):
        return None, {**record, 'failure': 'relational_role_failed'}
    if any(r['return'] != returns[0]['return'] for r in returns[1:]):
        return None, {**record, 'failure': 'relational_role_disagreement'}
    return returns[0]['return'], record


def consensus(grid, models):
    returns = [{'model': model, 'return': out, 'record': rec}
               for model in models for out, rec in [render(grid, model)]]
    record = {'complete': True, 'model_returns': returns}
    if not returns:
        return None, {**record, 'failure': 'no_models'}
    if any(r['return'] is None for r in returns):
        return None, {**record, 'failure': 'retained_model_failed'}
    if any(r['return'] != returns[0]['return'] for r in returns[1:]):
        return None, {**record, 'failure': 'retained_model_disagreement'}
    return returns[0]['return'], record
