"""固定prior適用後の一意組立・標識/色在庫・除去分岐証拠を確認する。"""
from collections import Counter
from .既存放射組立 import _marker_radial_component_sets, _marker_radial_assembly_parse, _marker_radial_assembly_render


def guarded_radial_assembly(grid, *, allow_unpaired_removal=False):
    if not grid or not grid[0] or len(grid) > 30 or len(grid[0]) > 30 or any(len(row) != len(grid[0]) for row in grid):
        return None, {'failure': 'invalid_grid'}
    counts = Counter(v for row in grid for v in row)
    if sum(n == max(counts.values()) for n in counts.values()) != 1:
        return None, {'failure': 'background_tie'}
    parsed, rejection = _marker_radial_assembly_parse(grid)
    if parsed is None:
        return None, rejection
    background = parsed['background']
    components = _marker_radial_component_sets(grid, background)
    unpaired = {color: parts[0] for color, parts in components.items()
                if not any(len(part) == 2 for part in parts)}
    if unpaired and not allow_unpaired_removal:
        return None, {'failure': 'unpaired_removal_without_teacher_witness'}
    output, record = _marker_radial_assembly_render(grid, {})
    if output is None:
        return None, record
    if record['solution_count'] != 1:
        return None, {'failure': 'multiple_complete_placement_combinations'}
    expected = Counter({color: n for color, n in counts.items() if color != background})
    for color, cells in unpaired.items():
        expected[color] -= len(cells)
    expected = +expected
    actual = Counter(v for row in output for v in row if v != background)
    if expected != actual:
        return None, {'failure': 'foreground_inventory_not_conserved'}
    if any(output[r][c] != marker['color'] for marker in parsed['marker_records'] for r, c in marker['cells']):
        return None, {'failure': 'marker_changed'}
    return output, {**record, 'unpaired_shape_count': len(unpaired),
                    'unpaired_removed_pixels': sum(len(cells) for cells in unpaired.values())}


class 放射組立教材:
    def __init__(self, 教師群):
        self.全教師再現 = False
        self.未対応除去教師数 = 0
        if not 教師群 or len({tuple(map(tuple, p['input'])) for p in 教師群}) != len(教師群):
            return
        記録群 = []
        for 対 in 教師群:
            候補, 記録 = guarded_radial_assembly(対['input'], allow_unpaired_removal=True)
            if 候補 != 対['output']:
                return
            記録群.append(記録)
        self.全教師再現 = True
        self.未対応除去教師数 = sum(r['unpaired_removed_pixels'] > 0 for r in 記録群)

    def 候補(self, 格子, _policy):
        if not self.全教師再現:
            return None, {'failure': '全教師を再現する放射組立なし'}
        return guarded_radial_assembly(格子, allow_unpaired_removal=self.未対応除去教師数 > 0)

    def 記録(self):
        return {'全教師再現': self.全教師再現, '未対応除去教師数': self.未対応除去教師数}
