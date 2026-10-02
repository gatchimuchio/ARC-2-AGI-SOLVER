"""固定0panel、全外部inventoryとmarker非加算、三盤面支持を検証する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 標識計数教材 as module
from 接続.ARC2.標識計数教材 import guarded_render, 標識計数教材
from 接続.ARC2.既存標識計数 import render_marker_panel_inventory_count_lattice
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 出力格子, 観測へ, 課題を解く


def 教材(shape=(7, 9), origin=(18, 2), rows=(1, 3), marker_col=1, counts=(2, 1)):
    height, width = shape
    top, left = origin
    grid = [[9] * 28 for _ in range(28)]
    for r in range(top, top + height):
        for c in range(left, left + width):
            grid[r][c] = 0
    output = [[0] * width for _ in range(height)]
    for index, (row, count) in enumerate(zip(rows, counts)):
        color = index + 1
        grid[top + row][left + marker_col] = color
        for item in range(count):
            r, c = 1 + 3 * item, 2 + 7 * index
            grid[r][c] = grid[r + 1][c + 1] = color  # 8近傍では一つの成分。
        for item in range(count):
            output[row][marker_col + 2 * item] = color
    grid[5][20] = grid[6][21] = 4  # 未標識の外部色は計数対象外。
    return {'input': grid, 'output': output}


def 教師():
    return [教材(), 教材((5, 7), (14, 15), (1, 3), 2, (1, 2)),
            教材((9, 11), (17, 3), (3, 5), 3, (2, 3))]


class 標識計数回帰(unittest.TestCase):
    def test_8近傍外部成分数をmarker位置から表示(self):
        pair = 教材(); output, record = guarded_render(pair['input'])
        self.assertEqual(output, pair['output'])
        cert = record['certificate']
        self.assertEqual(cert['external_counts'], {1: 2, 2: 1})
        self.assertEqual(cert['external_components'], 3)
        self.assertFalse(cert['marker_added_to_count'])
        self.assertEqual(sum(v == 1 for row in output for v in row), 2)

    def test_panel位置寸法とmarker行列は入力由来(self):
        for pair in 教師():
            self.assertEqual(guarded_render(pair['input'])[0], pair['output'])

    def test_0は固定型で他色の置換は許容(self):
        pair = 教材(); mapping = {0: 0, 9: 8, 1: 4, 2: 7, 4: 3}
        convert = lambda grid: [[mapping[v] for v in row] for row in grid]
        self.assertEqual(guarded_render(convert(pair['input']))[0], convert(pair['output']))
        self.assertEqual(guarded_render([[0] * 4 for _ in range(4)])[1]['failure'], 'zero_is_background')

    def test_余分な0島を黙殺しない(self):
        grid = 教材()['input']; grid[0][0] = 0
        self.assertIsNotNone(render_marker_panel_inventory_count_lattice(grid)[0])
        self.assertEqual(guarded_render(grid)[1]['failure'], 'zero_cells_outside_selected_component')

    def test_marker色の境界跨ぎを外部countから黙って外さない(self):
        grid = 教材(marker_col=0)['input']; grid[19][1] = 1
        self.assertIsNotNone(render_marker_panel_inventory_count_lattice(grid)[0])
        self.assertEqual(guarded_render(grid)[1]['failure'], 'marker_color_component_straddles_panel')

    def test_未標識色の外部成分は対象外(self):
        pair = 教材(); grid = deepcopy(pair['input'])
        grid[3][22] = grid[4][22] = 6
        output, record = guarded_render(grid)
        self.assertEqual(output, pair['output'])
        self.assertEqual(record['certificate']['external_components'], 3)

    def test_外部0個をmarker一個として数えない(self):
        grid = 教材()['input']
        for r, row in enumerate(grid):
            for c, value in enumerate(row):
                if value == 2 and not (18 <= r < 25 and 2 <= c < 11):
                    grid[r][c] = 9
        self.assertEqual(guarded_render(grid)[1]['failure'], 'missing_external_component')

    def test_容量超過は別panelや切り詰めへ逃げない(self):
        grid = 教材()['input']
        # panel幅9、marker col1の容量4に対して色1を5成分にする。
        for r in (8, 11, 14):
            grid[r][2] = grid[r + 1][3] = 1
        self.assertIsNone(render_marker_panel_inventory_count_lattice(grid)[0])
        self.assertEqual(guarded_render(grid)[1]['failure'], 'count_exceeds_panel_width')

    def test_背景同率不正格子を拒否(self):
        self.assertEqual(guarded_render([[0, 1], [1, 0]])[1]['failure'], 'background_tie')
        for grid in ([], [[0], [0, 1]], [[True]], [[10]], [[0] * 31]):
            self.assertEqual(guarded_render(grid)[1]['failure'], 'invalid_arc_grid')

    def test_元panel選択不一致と元格子不一致を代替しない(self):
        pair = 教材(); output, record = render_marker_panel_inventory_count_lattice(pair['input'])
        changed_record = deepcopy(record); changed_record['panel']['bbox'][0] += 1
        changed_grid = deepcopy(output); changed_grid[0][0] = 5
        for candidate, rec in ((output, changed_record), (changed_grid, record)):
            with patch.object(module.old, 'render_marker_panel_inventory_count_lattice', return_value=(candidate, rec)):
                self.assertEqual(guarded_render(pair['input'])[1]['failure'], 'raw_selection_or_output_disagrees')

    def test_全marker色componentのcoverageを欠落させない(self):
        pair = 教材(); original = module.old.color_components
        def incomplete(grid, color, include_diagonal=False):
            result = original(grid, color, include_diagonal)
            return result[1:] if include_diagonal and color == 1 else result
        with patch.object(module.old, 'color_components', side_effect=incomplete):
            self.assertEqual(guarded_render(pair['input'])[1]['failure'], 'marker_color_coverage_incomplete')

    def test_失敗と重複教師を採用しない(self):
        pairs = 教師(); pairs[-1]['output'][0][0] = 5
        self.assertFalse(標識計数教材(pairs).適合)
        pair = 教材(); self.assertFalse(標識計数教材([pair, pair]).適合)

    def test_native支持は三盤面でmarkerや物体数を加算しない(self):
        pairs = 教師(); view = 標識計数教材(pairs); boundary = '標識計数対照'
        self.assertTrue(view.適合)
        self.assertFalse(候補機構を学習(HDS学習実行系(), {'train': pairs[:2]}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系()
        record = 候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertEqual(record['現在観測数'], 3); self.assertEqual(record['事前観測数'], 0)
        query = 教材((9, 11), (17, 3), (3, 5), 2, (3, 2))
        self.assertEqual(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'], query['output'])
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[5]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'])

    def test_採用済み余分0queryは全体HOLD(self):
        grid = 教材()['input']; grid[0][0] = 0
        task = {'train': 教師(), 'test': [{'input': grid}]}
        result = 課題を解く(task, [])
        record = next(r for r in result['families'] if r['境界'] == 'ARC標識panel計数')
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertIsNone(result['results'][0]['answer'])
        task['task_id'] = 'forbidden'
        with self.assertRaises(ValueError):
            課題を解く(task, [])
        task.pop('task_id'); task['test'][0]['output'] = [[1]]
        with self.assertRaises(ValueError):
            課題を解く(task, [])


if __name__ == '__main__':
    unittest.main()
