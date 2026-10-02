"""全actorの同時色提案を検査し、元rendererと同じ格子だけを通す。"""
from collections import Counter
from .既存標識移動 import (
    _guided_box_components, _guided_box_side, _guided_box_far_wall,
    _guided_box_fill_key, _guided_box_marker_compaction_render, _guided_box_role_candidates,
)


def guarded_guided_box(grid, policy, *, allow_contact_deletion=False):
    if not grid or not grid[0] or len(grid) > 30 or len(grid[0]) > 30 or any(len(row) != len(grid[0]) for row in grid):
        return None, {'failure': 'invalid_grid'}
    roles = policy.get('roles', {})
    required = {'marker_color', 'interior_color', 'fuel_color', 'filled_color'}
    if set(roles) != required or len(set(roles.values())) != 4:
        return None, {'failure': 'invalid_roles'}
    counts = Counter(v for row in grid for v in row if v not in roles.values())
    if not counts or sum(n == max(counts.values()) for n in counts.values()) != 1:
        return None, {'failure': 'travel_background_not_unique'}
    background = max(counts, key=counts.get)
    components = _guided_box_components(grid, roles)
    covered = set().union(*components) if components else set()
    if any(v in roles.values() and v != roles['marker_color'] and (r, c) not in covered
           for r, row in enumerate(grid) for c, v in enumerate(row)):
        return None, {'failure': 'unparsed_nonmarker_role_component'}
    moved, proposals = set(), {}
    deleted, moved_count = 0, 0
    for cells in components:
        parsed = _guided_box_side(grid, cells, roles['marker_color'])
        if parsed is None:
            return None, {'failure': 'unparsed_actor'}
        side, bbox, marker_bbox = parsed
        row0, col0, row1, col1 = bbox
        mr0, mc0, mr1, mc1 = marker_bbox
        if ((side in 'UD' and mr0 - row0 == row1 - mr1)
                or (side in 'LR' and mc0 - col0 == col1 - mc1)):
            return None, {'failure': 'actor_side_tie'}
        far_record = _guided_box_far_wall(grid, bbox, marker_bbox, side, roles, background)
        if far_record is None:
            return None, {'failure': 'unresolved_destination'}
        far, contact = far_record
        near = mr0 if side == 'U' else mr1 if side == 'D' else mc0 if side == 'L' else mc1
        fuel = sorted([cell for cell in cells if grid[cell[0]][cell[1]] == roles['fuel_color']],
                      key=_guided_box_fill_key(side))
        move = min(abs(far - near), len(fuel))
        if move <= 0:
            continue
        moved_count += 1
        moved |= cells
        converted = set(fuel[:move])
        dr, dc = {'U': (-1, 0), 'D': (1, 0), 'L': (0, -1), 'R': (0, 1)}[side]
        for row, col in cells:
            tr, tc = row + dr * move, col + dc * move
            if not (0 <= tr < len(grid) and 0 <= tc < len(grid[0])):
                return None, {'failure': 'out_of_bounds_target'}
            if (contact and grid[tr][tc] == background and grid[row][col] == roles['marker_color']
                    and ((side in 'UD' and tr == far) or (side in 'LR' and tc == far))):
                deleted += 1
                continue
            value = roles['filled_color'] if (row, col) in converted else grid[row][col]
            proposals.setdefault((tr, tc), set()).add(value)
    if deleted and not allow_contact_deletion:
        return None, {'failure': 'contact_deletion_without_teacher_witness'}
    if any(len(values) != 1 for values in proposals.values()):
        return None, {'failure': 'conflicting_final_color_proposals'}
    union = [row[:] for row in grid]
    for row, col in moved:
        union[row][col] = background
    for (row, col), values in proposals.items():
        value = next(iter(values))
        if (row, col) not in moved and grid[row][col] != background and grid[row][col] != value:
            return None, {'failure': 'different_stationary_overwrite'}
        union[row][col] = value
    output, record = _guided_box_marker_compaction_render(grid, policy)
    if output is None:
        return None, record
    if output != union:
        return None, {'failure': 'source_differs_from_simultaneous_union'}
    return output, {**record, 'actor_count': len(components), 'moved_actor_count': moved_count,
                    'contact_marker_deletions': deleted}


class 標識移動教材:
    def __init__(self, 教師群):
        self.方針 = None
        self.接触消去教師数 = 0
        self.適合方針数 = 0
        if not 教師群 or len({tuple(map(tuple, p['input'])) for p in 教師群}) != len(教師群):
            return
        適合 = []
        for 色役割 in _guided_box_role_candidates(教師群):
            方針 = {'roles': dict(zip(('marker_color', 'interior_color', 'fuel_color', 'filled_color'), 色役割))}
            for 対 in 教師群:
                候補, _ = _guided_box_marker_compaction_render(対['input'], 方針)
                if 候補 != 対['output']:
                    break
            else:
                適合.append(方針)
        self.適合方針数 = len(適合)
        if len(適合) != 1:
            return
        記録群 = []
        for 対 in 教師群:
            候補, 記録 = guarded_guided_box(対['input'], 適合[0], allow_contact_deletion=True)
            if 候補 != 対['output']:
                return
            記録群.append(記録)
        self.方針 = 適合[0]
        self.接触消去教師数 = sum(r['contact_marker_deletions'] > 0 for r in 記録群)

    def 候補(self, 格子, _policy):
        if self.方針 is None:
            return None, {'failure': '全教師を再現する役割方針が一意でない'}
        return guarded_guided_box(格子, self.方針, allow_contact_deletion=self.接触消去教師数 > 0)

    def 記録(self):
        return {'適合方針数': self.適合方針数, '方針': self.方針, '接触消去教師数': self.接触消去教師数}
