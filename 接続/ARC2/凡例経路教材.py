"""役割一意性と全経路合意を確認し、元rendererと同じ格子だけ返す。"""
from __future__ import annotations
from collections import Counter
from . import 既存凡例経路 as old

NODE_BUDGET = 100_000


def _row_sequence(row, background, frame):
    sequence, col = [], 0
    while col < len(row):
        if row[col] in {background, frame}:
            col += 1
            continue
        values = []
        while col < len(row) and row[col] not in {background, frame}:
            values.append(row[col]); col += 1
        sequence.extend([values[0]] if len(set(values)) == 1 else values)
    return sequence


def _raw_frame_roles(grid, background):
    roles = []
    for color in sorted(set(v for row in grid for v in row) - {background}):
        count = 0
        for part in old.color_components(grid, color):
            r0, c0, r1, c1 = part['bbox']
            if r1 - r0 + 1 < 3 or c1 - c0 + 1 < 3:
                continue
            payload = {grid[r][c] for r in range(r0, r1 + 1)
                       for c in range(c0, c1 + 1)
                       if grid[r][c] not in {background, color}}
            count += len(payload) == 1
        if count >= 2:
            roles.append(color)
    return roles


def certified_legend_gap(grid):
    if (not isinstance(grid, list) or not 1 <= len(grid) <= 30
            or not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30
            or any(not isinstance(row, list) or len(row) != len(grid[0])
                   or any(type(v) is not int or not 0 <= v <= 9 for v in row)
                   for row in grid)):
        return None, {'failure': 'invalid_grid'}
    counts = Counter(v for row in grid for v in row)
    modes = [v for v, n in counts.items() if n == max(counts.values())]
    if len(modes) != 1:
        return None, {'failure': 'background_tie'}
    background = modes[0]
    roles = _raw_frame_roles(grid, background)
    if len(roles) != 1:
        return None, {'failure': 'raw_frame_role_not_unique', 'roles': roles}
    frame = roles[0]
    if old.choose_frame_color(grid, background) != frame:
        return None, {'failure': 'source_frame_choice_disagrees'}
    parsed = old.extract_payload_panels(grid)
    if parsed is None:
        return None, {'failure': 'source_parse_failed'}
    _, _, panels = parsed
    if len(old.color_components(grid, frame)) != len(panels):
        return None, {'failure': 'unparsed_frame_component'}
    covered = set()
    for panel in panels:
        r0, c0, r1, c1 = panel['frame_bbox']
        box = {(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)}
        if covered & box:
            return None, {'failure': 'overlapping_panel_boxes'}
        if any(grid[r][c] != frame for r, c in box
               if r in {r0, r1} or c in {c0, c1}):
            return None, {'failure': 'open_panel_frame'}
        covered.update(box)
    outside = [(r, c) for r, row in enumerate(grid) for c, v in enumerate(row)
               if v not in {background, frame} and (r, c) not in covered]
    legend_rows = {r for r, c in outside}
    if len(legend_rows) != 1:
        return None, {'failure': 'outside_legend_row_not_unique'}
    legend_row = next(iter(legend_rows))
    if any(r == legend_row for panel in panels for r, c in panel['payload_cells']):
        return None, {'failure': 'legend_row_contains_panel_payload'}
    sequences = [_row_sequence(row, background, frame) for row in grid]
    longest = max(map(len, sequences))
    best_sequences = {tuple(s) for s in sequences if len(s) == longest}
    sequence = sequences[legend_row]
    if (len(best_sequences) != 1 or len(sequence) < 2 or len(sequence) != longest
            or old.extract_legend_sequence(grid, background, frame) != sequence):
        return None, {'failure': 'legend_sequence_not_unique'}
    by_color = {}
    for index, panel in enumerate(panels):
        by_color.setdefault(panel['color'], []).append(index)
    if len(sequence) > len(panels) or any(v not in by_color for v in sequence):
        return None, {'failure': 'legend_has_no_complete_panel_path'}

    cache, outputs = {}, set()
    nodes, complete = 0, 0
    failure = None

    def relation(first, second):
        key = (first, second)
        if key not in cache:
            cache[key] = old.relation_between_panels(grid, background, panels[first], panels[second])
        return cache[key]

    def search(path, used):
        nonlocal nodes, complete, failure
        nodes += 1
        if nodes > NODE_BUDGET:
            failure = 'path_certificate_budget'
            return
        if len(path) == len(sequence):
            complete += 1
            paint = {}
            for first, second in zip(path, path[1:]):
                record = relation(first, second)
                r0, c0, r1, c1 = record['fill_rect']
                for r in range(r0, r1 + 1):
                    for c in range(c0, c1 + 1):
                        color = record['fill_color']
                        if (r, c) in paint and paint[r, c] != color:
                            failure = 'complete_path_paint_conflict'
                            return
                        paint[r, c] = color
            output = [row[:] for row in grid]
            for (r, c), color in paint.items():
                output[r][c] = color
            outputs.add(tuple(map(tuple, output)))
            if len(outputs) > 1:
                failure = 'complete_path_output_disagreement'
            return
        for index in by_color[sequence[len(path)]]:
            if index in used or (path and relation(path[-1], index) is None):
                continue
            search(path + [index], used | {index})
            if failure:
                return

    search([], set())
    certificate = {'nodes': nodes, 'complete_paths': complete,
                   'distinct_outputs': len(outputs), 'node_budget': NODE_BUDGET}
    if failure or len(outputs) != 1:
        return None, {'failure': failure or 'no_complete_path', **certificate}
    source_output, record = old.render_legend_payload_gap_connectors(grid)
    if source_output is None or tuple(map(tuple, source_output)) != next(iter(outputs)):
        return None, {'failure': 'source_output_disagrees', **certificate}
    return source_output, {**record, 'certificate': certificate, 'legend_row': legend_row}


class 凡例経路教材:
    def __init__(self, 教師群):
        self.全教師再現 = False
        if not 教師群 or len({tuple(map(tuple, p['input'])) for p in 教師群}) != len(教師群):
            return
        self.全教師再現 = all(certified_legend_gap(p['input'])[0] == p['output'] for p in 教師群)

    def 候補(self, 格子, _policy):
        if not self.全教師再現:
            return None, {'failure': '全教師を再現する確定凡例経路なし'}
        return certified_legend_gap(格子)

    def 記録(self):
        return {'全教師再現': self.全教師再現, '経路探索上限': NODE_BUDGET}
