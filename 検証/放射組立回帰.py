"""D4重複と競合、固定境界prior、除去証拠とnative支持を確認する。"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import sys
import unittest

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2.放射組立教材 import 放射組立教材, guarded_radial_assembly
from 接続.ARC2.既存放射組立 import (
    _marker_radial_shape_variants, _marker_radial_assembly_parse,
    _marker_radial_attachment_options, _marker_radial_marker_facing_boundary_count,
)
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.HDS接続 import 課題を解く, HDS学習実行系, 候補機構を学習, 出力格子, 観測へ


def 入力(shape, unpaired=False):
    grid = [[0] * 20 for _ in range(14)]
    for r, c in shape:
        grid[1 + r][1 + c] = 2
    for r in (6, 7):
        grid[r][12] = 2
        grid[r][6] = 3
    if unpaired:
        for r, c in ((1, 10), (1, 11), (2, 11)):
            grid[r][c] = 4
    return grid


def 教材(width=2, unpaired=False):
    grid = 入力({(r, c) for r in range(2) for c in range(width)}, unpaired)
    output = [[0] * 20 for _ in range(14)]
    for r in (6, 7):
        output[r][6] = 3
        for c in range(12, 13 + width):
            output[r][c] = 2
    return {'input': grid, 'output': output}


def 教師():
    return [教材(2, True), 教材(3), 教材(4)]


class 放射組立回帰(unittest.TestCase):
    def test_可変形状を標識の外側へ配置し色在庫を保存(self):
        for pair in 教師() + [教材(6)]:
            out, record = guarded_radial_assembly(pair['input'], allow_unpaired_removal=True)
            self.assertEqual(out, pair['output']); self.assertEqual(record['solution_count'], 1)
            self.assertEqual(Counter(v for row in out for v in row if v in (2, 3)), Counter(v for row in pair['input'] for v in row if v in (2, 3)))

    def test_D4同形重複は競合に数えない(self):
        square = {(0, 0), (0, 1), (1, 0), (1, 1)}
        self.assertEqual(len(_marker_radial_shape_variants(square)), 1)
        self.assertEqual(guarded_radial_assembly(入力(square))[1]['solution_count'], 1)

    def test_異なる二つの最小境界出力は保留(self):
        shape = {(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 3)}
        self.assertEqual(len(_marker_radial_shape_variants(shape)), 8)
        out, record = guarded_radial_assembly(入力(shape))
        self.assertIsNone(out); self.assertEqual(record['failure'], 'marker_radial_assembly_ambiguous')
        self.assertEqual(record['distinct_output_count'], 2)

    def test_最小対向境界は幾何的一意性と異なる固定選好(self):
        pair = 教材(4); parsed, _ = _marker_radial_assembly_parse(pair['input'])
        actor = parsed['active_records'][0]
        options = _marker_radial_attachment_options(pair['input'], actor['large'], actor['marker'], parsed['all_markers'] - actor['marker'], actor['direction'])
        counts = [_marker_radial_marker_facing_boundary_count(option, actor['direction']) for option in options]
        self.assertEqual(sorted(counts), [2, 4])
        self.assertEqual(guarded_radial_assembly(pair['input'])[0], pair['output'])

    def test_回転反転配色を変えても同じ入力関係(self):
        pair = 教材(4)
        for name in ('rot90', 'rot180', 'flip_h', 'transpose'):
            self.assertEqual(guarded_radial_assembly(transform_grid_by_name(pair['input'], name))[0], transform_grid_by_name(pair['output'], name))
        mapping = {0: 9, 2: 5, 3: 6}
        recolor = lambda g: [[mapping[v] for v in row] for row in g]
        self.assertEqual(guarded_radial_assembly(recolor(pair['input']))[0], recolor(pair['output']))

    def test_未対応shape除去は現教師の分岐証拠が必要(self):
        pair = 教材(2, True)
        self.assertEqual(guarded_radial_assembly(pair['input'])[1]['failure'], 'unpaired_removal_without_teacher_witness')
        self.assertEqual(guarded_radial_assembly(pair['input'], allow_unpaired_removal=True)[0], pair['output'])
        view = 放射組立教材([教材(2), 教材(3), 教材(4)])
        self.assertTrue(view.全教師再現); self.assertEqual(view.未対応除去教師数, 0)
        self.assertIsNone(view.候補(pair['input'], {})[0])

    def test_除去許可で不正inventoryを読み飛ばさない(self):
        grid = 教材(2, True)['input']
        for r, c in ((10, 1), (11, 1), (11, 2)):
            grid[r][c] = 4
        self.assertEqual(guarded_radial_assembly(grid, allow_unpaired_removal=True)[1]['failure'], 'marker_radial_unclassified_component_inventory')
        grid = 教材()['input']; grid[10][10] = grid[11][10] = 2
        self.assertEqual(guarded_radial_assembly(grid)[1]['failure'], 'marker_radial_multiple_marker_components')

    def test_中央標識と斜めdominoの曖昧役割は保留(self):
        grid = 教材()['input']
        for r in (6, 7):
            grid[r][18] = 4
        self.assertEqual(guarded_radial_assembly(grid)[1]['failure'], 'marker_radial_marker_direction_ambiguous')
        grid = 教材()['input']; grid[7][6] = 0; grid[7][7] = 3
        self.assertEqual(guarded_radial_assembly(grid)[1]['failure'], 'marker_radial_marker_not_orthogonal_domino')

    def test_背景同率と不正入力は保留(self):
        for grid in ([[0, 1], [1, 0]], [], [[0] * 31], [[0, 0], [0]]):
            self.assertIsNone(guarded_radial_assembly(grid)[0])

    def test_教師反例と重複を支持に入れない(self):
        pairs = 教師(); pairs[1]['output'][0][0] = 1
        self.assertFalse(放射組立教材(pairs).全教師再現)
        pair = 教材(); self.assertFalse(放射組立教材([pair, deepcopy(pair)]).全教師再現)

    def test_三教師だけをnative支持として観測(self):
        pair = 教材(6, True)
        result = 課題を解く({'train': 教師(), 'test': [{'input': pair['input']}]}, [])
        self.assertEqual(result['results'][0]['answer'], pair['output'])
        family = next(x for x in result['families'] if x['境界'] == 'ARC放射組立')
        self.assertEqual(family['現在観測数'], 3); self.assertEqual(family['事前観測数'], 0)
        self.assertTrue(family['同値採用']); self.assertEqual(result['radial_assembly']['未対応除去教師数'], 1)

    def test_native支持不足と後発反例は保留(self):
        pairs = 教師(); view = 放射組立教材(pairs); boundary = '放射組立対照'
        engine = HDS学習実行系()
        self.assertFalse(候補機構を学習(engine, {'train': pairs[:2]}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系()
        self.assertTrue(候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)['同値採用'])
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[3]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': pairs[1]['output']}, boundary), 同値必須=True)['answer'])


if __name__ == '__main__':
    unittest.main()
