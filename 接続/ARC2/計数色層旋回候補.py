"""Complete square/cue ownership followed by repeated accepted D4 mask actions.

The scene grammar and composition are new. Every square/background role and
all teacher-fitting action programs survive; disagreement or a failed retained
alternative yields HOLD. Unexpected implementation/resource errors propagate.
There is no task data, identifier routing, filesystem access, or output memory.
"""
from dataclasses import dataclass
from .既存領域転写 import _bbox_for_cells
from .既存物体特徴 import color_components
from .既存配置展開 import crop_bbox
from .既存格子操作 import lattice_tile_mask, transform_grid_by_name

D4 = ('identity', 'rot90', 'rot180', 'rot270', 'flip_h', 'flip_v',
      'transpose', 'anti_transpose')


def valid_grid(grid):
    return (isinstance(grid, list) and 1 <= len(grid) <= 30
            and isinstance(grid[0], list) and 1 <= len(grid[0]) <= 30
            and all(isinstance(row, list) and len(row) == len(grid[0])
                    and all(type(v) is int and 0 <= v <= 9 for v in row)
                    for row in grid))


@dataclass(frozen=True)
class Role:
    background: int
    bbox: tuple
    # All layers use the same square coordinates, including their blank cells.
    layers: tuple  # (color, frozenset of local cells, cue length, cue cells)


def _prefix(grid, color):
    h, w = len(grid), len(grid[0])
    out = [[0] * (w + 1) for _ in range(h + 1)]
    for r, row in enumerate(grid):
        for c, value in enumerate(row):
            out[r+1][c+1] = (out[r][c+1] + out[r+1][c] - out[r][c]
                              + (value == color))
    return out


def _count(prefix, box):
    r, c, b, e = box
    return prefix[b+1][e+1] - prefix[r][e+1] - prefix[b+1][c] + prefix[r][c]


def parse(grid):
    """Enumerate, never rank, the entire bounded square/background role space.

    A role owns one tight multicolor square spanned on all four bounds by
    at least one color layer, plus zero/one whole straight C4
    component for each layer color outside it. At least one external cue is
    required. Cue lengths are unrestricted within the 30-cell ARC dimension.
    Other cells must be background. The canvas need not be connected.
    """
    if not valid_grid(grid):
        return (), {'failure': 'invalid_grid'}
    h, w = len(grid), len(grid[0])
    palette = sorted({v for row in grid for v in row})
    cells = {color: {(r, c) for r, row in enumerate(grid)
                     for c, v in enumerate(row) if v == color}
             for color in palette}
    prefixes = {color: _prefix(grid, color) for color in palette}
    components = {color: {frozenset(comp['cells'])
                          for comp in color_components(grid, color, False)}
                  for color in palette}
    roles = []
    considered = 0
    for background in palette:
        foreground = [color for color in palette if color != background]
        if len(foreground) < 2:
            continue
        for size in range(2, min(h, w) + 1):
            for top in range(h - size + 1):
                for left in range(w - size + 1):
                    considered += 1
                    box = (top, left, top + size - 1, left + size - 1)
                    inside_counts = {color: _count(prefixes[color], box)
                                     for color in foreground}
                    # Every foreground color must belong to the canvas; all its
                    # remaining cells must fit one straight cue if any remain.
                    if any(n == 0 or len(cells[color]) - n > max(h, w)
                           for color, n in inside_counts.items()):
                        continue
                    if all(len(cells[color]) == n
                           for color, n in inside_counts.items()):
                        continue
                    outside = {color: frozenset((r, c) for r, c in cells[color]
                                               if not (top <= r <= box[2]
                                                       and left <= c <= box[3]))
                               for color in foreground}
                    eligible = True
                    for color, cue in outside.items():
                        if not cue:
                            continue
                        r0, c0, r1, c1 = _bbox_for_cells(cue)
                        if (cue not in components[color]
                                or (r0 != r1 and c0 != c1)
                                or len(cue) != (r1-r0+1) * (c1-c0+1)):
                            eligible = False
                            break
                    if not eligible:
                        continue
                    owned = set().union(*(cells[color] - outside[color]
                                          for color in foreground))
                    if _bbox_for_cells(owned) != box:
                        continue
                    # A complete square layer establishes the shared canvas.
                    # No preference by size, position, or action success.
                    if not any(_bbox_for_cells(cells[color] - outside[color]) == box
                               for color in foreground):
                        continue
                    canvas = crop_bbox(grid, box)
                    layers = tuple((color,
                                    lattice_tile_mask(canvas, (0, 0, size-1, size-1), color),
                                    len(outside[color]), tuple(sorted(outside[color])))
                                   for color in foreground)
                    # Verify complete input ownership independently of fitting.
                    reconstructed = [[background] * w for _ in range(h)]
                    for color, mask, count, cue in layers:
                        if len(mask) != inside_counts[color] or count != len(cue):
                            raise AssertionError('layer_ownership_count')
                        for r, c in mask:
                            reconstructed[top+r][left+c] = color
                        for r, c in cue:
                            reconstructed[r][c] = color
                    if reconstructed != grid:
                        raise AssertionError('incomplete_scene_ownership')
                    roles.append(Role(background, box, layers))
    return tuple(roles), {'roles': len(roles), 'square_background_trials': considered}


def render_role(role, program):
    if program not in D4:
        raise ValueError('unknown_action_program')
    size = role.bbox[2] - role.bbox[0] + 1
    output = [[role.background] * size for _ in range(size)]
    occupied = set()
    collisions = []
    for color, cells, count, _cue in role.layers:
        mask = [[int((r, c) in cells) for c in range(size)] for r in range(size)]
        for _ in range(count):
            mask = transform_grid_by_name(mask, program)
            if mask is None:
                raise AssertionError('accepted_transform_rejected_declared_program')
        moved = {(r, c) for r, row in enumerate(mask) for c, v in enumerate(row) if v}
        if len(moved) != len(cells):
            raise AssertionError('accepted_transform_changed_cardinality')
        if occupied & moved:
            collisions.append(color)
        occupied.update(moved)
        for r, c in moved:
            output[r][c] = color
    if collisions:
        return None, {'failure': 'different_color_layer_collision',
                      'colliding_colors': collisions}
    return output, {'canvas': role.bbox, 'background': role.background,
                    'cue_counts': [(color, count) for color, _, count, _ in role.layers]}


def render_roles(roles, program):
    if not roles:
        return None, {'failure': 'no_complete_scene_role'}
    outputs = []
    records = []
    for role in roles:
        output, record = render_role(role, program)
        records.append(record)
        outputs.append(output)
    if any(output is None for output in outputs):
        return None, {'failure': 'eligible_role_failed', 'role_records': records}
    if any(output != outputs[0] for output in outputs[1:]):
        return None, {'failure': 'eligible_roles_disagree', 'roles': len(roles),
                      'role_records': records}
    return outputs[0], {'roles': len(roles), 'role_records': records}


class LayerTurnCandidate:
    def __init__(self, teachers):
        self.programs = ()
        self.teacher_count = len(teachers)
        self.fit_records = ()
        self.fit_table = ()
        if not teachers or any(not valid_grid(p['input']) or not valid_grid(p['output'])
                               for p in teachers):
            return
        if len({tuple(map(tuple, p['input'])) for p in teachers}) != len(teachers):
            return
        parsed = [parse(p['input']) for p in teachers]
        self.fit_records = tuple(record for _roles, record in parsed)
        # Materialize all 8 x teacher_count evaluations before fitting. Teacher
        # grids and rendered grids are not retained in the fitted candidate.
        table = []
        for program in D4:
            evaluations = [render_roles(roles, program) for roles, _record in parsed]
            table.append({'program': program, 'teachers': tuple(
                {'exact': output == pair['output'], 'record': record}
                for (output, record), pair in zip(evaluations, teachers))})
        self.fit_table = tuple(table)
        self.programs = tuple(row['program'] for row in self.fit_table
                              if all(result['exact'] for result in row['teachers']))

    def predict(self, grid):
        if not self.programs:
            return None, {'failure': 'no_teacher_fitting_program'}
        roles, parse_record = parse(grid)
        outputs = []
        records = []
        for program in self.programs:
            output, record = render_roles(roles, program)
            outputs.append(output)
            records.append({'program': program, 'render': record})
        if any(output is None for output in outputs):
            return None, {'failure': 'retained_program_failed', 'parse': parse_record,
                          'programs': records}
        if any(output != outputs[0] for output in outputs[1:]):
            return None, {'failure': 'retained_programs_disagree', 'programs': records}
        return outputs[0], {'parse': parse_record, 'programs': records}

    def 候補(self, grid, _policy=None):
        return self.predict(grid)

    def 記録(self):
        return {'teacher_count': self.teacher_count, 'programs': self.programs,
                'fit_records': self.fit_records, 'fit_table': self.fit_table,
                'grammar_count': len(D4),
                'new_composition': 'all tight square/cue roles; repeated shared D4 per color'}
