"""教師由来役割、多始点到達、消去証拠と三盤面支持を検証する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 種境界教材 as module
from 接続.ARC2.種境界教材 import guarded_render, 種境界教材
from 接続.ARC2.既存種境界 import seeded_boundary_barrier_recolor, infer_seed_boundary_colors
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 出力格子, 観測へ, 課題を解く

COLORS = {'background': 0, 'barrier': 1, 'seed': 2, 'fill': 3}


def 教材(height=10, width=12, wall=5, remove=True, interior=False):
    grid = [[0] * width for _ in range(height)]
    for row in grid:
        row[wall] = 1
    grid[-1][0] = 2
    if remove:
        for r in (3, 4):
            for c in (wall + 3, wall + 4):
                grid[r][c] = 1
    internal = {(r, c) for r in (3, 4) for c in (2, 3)} if interior else set()
    for r, c in internal:
        grid[r][c] = 1
    output = [[0] * width for _ in range(height)]
    for r in range(height):
        output[r][wall] = 1
        for c in range(wall):
            if (r, c) in internal:
                output[r][c] = 1
            elif r in (0, height - 1) or c in (0, wall - 1):
                output[r][c] = 3
    output[-1][0] = 2
    return {'input': grid, 'output': output}


def 教師(with_witness=True):
    return [教材(remove=with_witness), 教材(12, 15, 8, False, True), 教材(14, 18, 10, False)]


class 種境界回帰(unittest.TestCase):
    def test_全格子と非接触barrier消去(self):
        pair = 教材(); output, rec = guarded_render(pair['input'], COLORS, removal_witness=True)
        self.assertEqual(output, pair['output'])
        self.assertEqual(rec['certificate']['removed_barrier_pixels'], 4)
        self.assertEqual(rec['certificate']['preserved_barrier_pixels'], 10)

    def test_内部barrierを保存して境界源にはしない(self):
        pair = 教材(12, 15, 8, False, True)
        output, rec = guarded_render(pair['input'], COLORS)
        self.assertEqual(output, pair['output'])
        self.assertEqual(output[3][2], 1)
        self.assertEqual(output[2][2], 0)
        self.assertEqual(rec['certificate']['removed_barrier_pixels'], 0)

    def test_D4と役割色置換(self):
        pair = 教材()
        for name in ('identity', 'rot90', 'rot180', 'rot270', 'flip_h', 'flip_v', 'transpose', 'anti_transpose'):
            self.assertEqual(guarded_render(transform_grid_by_name(pair['input'], name), COLORS, removal_witness=True)[0],
                             transform_grid_by_name(pair['output'], name))
        recolor = lambda g: [[9 - v for v in row] for row in g]
        roles = {k: 9 - v for k, v in COLORS.items()}
        self.assertEqual(guarded_render(recolor(pair['input']), roles, removal_witness=True)[0], recolor(pair['output']))

    def test_seedの複数開始点から両背景領域を取る(self):
        grid = [[0] * 9 for _ in range(9)]
        for row in grid:
            row[4] = 1
        grid[4][4] = 2
        output, rec = guarded_render(grid, COLORS)
        self.assertEqual(rec['certificate']['seed_background_start_count'], 2)
        self.assertEqual(rec['certificate']['seed_region_size'], 72)
        self.assertEqual(output[0][0], 3); self.assertEqual(output[0][8], 3)
        self.assertEqual(output[4][4], 2)

    def test_queryで背景最多色を取り直さない(self):
        grid = [[1] * 5 for _ in range(5)]
        for r in (0, 1):
            for c in (0, 1):
                grid[r][c] = 0
        grid[0][0] = 2
        output, _ = guarded_render(grid, COLORS)
        expected = deepcopy(grid)
        for r, c in ((0, 1), (1, 0), (1, 1)):
            expected[r][c] = 3
        self.assertEqual(output, expected)

    def test_未知色と既存fillを暗黙に消さない(self):
        for value in (3, 9):
            grid = 教材()['input']; grid[1][1] = value
            self.assertIsNotNone(seeded_boundary_barrier_recolor(grid, COLORS)[0])
            self.assertEqual(guarded_render(grid, COLORS, removal_witness=True)[1]['failure'], 'unknown_or_existing_fill_color')

    def test_非接触barrier消去には教師証拠が必要(self):
        grid = 教材()['input']
        self.assertEqual(guarded_render(grid, COLORS)[1]['failure'], 'nonadjacent_removal_without_teacher_witness')
        self.assertIsNotNone(guarded_render(grid, COLORS, removal_witness=True)[0])

    def test_再現教師に消去が無ければqueryでも許可しない(self):
        view = 種境界教材(教師(False))
        self.assertIsNotNone(view.色役割)
        self.assertEqual(view.消去証拠数, 0)
        self.assertEqual(view.候補(教材()['input'], {})[1]['failure'], 'nonadjacent_removal_without_teacher_witness')

    def test_raw役割fit後の教師背景tieを選び直さない(self):
        grid = [[0, 0, 1], [0, 1, 1], [2, 0, 1]]
        output, _ = seeded_boundary_barrier_recolor(grid, COLORS)
        pair = {'input': grid, 'output': output}
        self.assertEqual(infer_seed_boundary_colors({'train': [pair]}), COLORS)
        self.assertIsNone(種境界教材([pair]).色役割)

    def test_元出力不一致を検証格子へ置換しない(self):
        pair = 教材(); output, records = seeded_boundary_barrier_recolor(pair['input'], COLORS)
        bad = deepcopy(output); bad[0][0] = 9
        with patch.object(module, 'seeded_boundary_barrier_recolor', return_value=(bad, records)):
            self.assertEqual(guarded_render(pair['input'], COLORS, removal_witness=True)[1]['failure'], 'source_output_disagrees')

    def test_barrier記録を一部欠落させない(self):
        pair = 教材()
        with patch.object(module, 'same_color_components', return_value=[]):
            self.assertEqual(guarded_render(pair['input'], COLORS, removal_witness=True)[1]['failure'], 'barrier_coverage_incomplete_or_overlapping')

    def test_不正格子役割seedを保留(self):
        for grid in ([], [[0], [0, 1]], [[True]], [[10]], [[0] * 31]):
            self.assertEqual(guarded_render(grid, COLORS)[1]['failure'], 'invalid_arc_grid')
        self.assertEqual(guarded_render([[0]], {'fill': 3})[1]['failure'], 'invalid_distinct_roles')
        grid = 教材()['input']; grid[0][0] = 2
        self.assertEqual(guarded_render(grid, COLORS)[1]['failure'], 'seed_not_unique')
        self.assertEqual(guarded_render([[1, 1, 1], [1, 2, 1], [1, 1, 1]], COLORS)[1]['failure'], 'no_seed_background_neighbor')

    def test_教師反例重複からwitnessを得ない(self):
        pairs = 教師(); pairs[-1]['output'][0][0] = 9
        view = 種境界教材(pairs)
        self.assertIsNone(view.色役割); self.assertEqual(view.消去証拠数, 0)
        pair = 教材(); self.assertIsNone(種境界教材([pair, pair]).色役割)

    def test_native支持は三盤面で消去証拠を加算しない(self):
        pairs = 教師(); view = 種境界教材(pairs); boundary = '種境界対照'
        self.assertEqual(view.色役割, COLORS); self.assertEqual(view.消去証拠数, 1)
        self.assertFalse(候補機構を学習(HDS学習実行系(), {'train': pairs[:2]}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系()
        record = 候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)
        self.assertTrue(record['同値採用']); self.assertEqual(record['現在観測数'], 3)
        self.assertEqual(record['事前観測数'], 0)
        query = 教材(16, 20, 11, True)
        self.assertEqual(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'], query['output'])
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[9]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'])

    def test_採用済みqueryの未知色は全体HOLD(self):
        grid = 教材()['input']; grid[1][1] = 9
        result = 課題を解く({'train': 教師(), 'test': [{'input': grid}]}, [])
        record = next(r for r in result['families'] if r['境界'] == 'ARCseed境界着色')
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertIsNone(result['results'][0]['answer'])


if __name__ == '__main__':
    unittest.main()
