"""完全十字の全match和集合と、教師由来の色遷移・三盤面支持を検証する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 十字教材 as module
from 接続.ARC2.十字教材 import guarded_render, raw_color_fit, 十字教材
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 出力格子, 観測へ, 課題を解く


def 教材(height=9, width=10, row=3, col=4):
    grid = [[0] * width for _ in range(height)]
    cells = {(row, col), (row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)}
    for r, c in cells:
        grid[r][c] = 4
    grid[-2][-2] = grid[-2][-3] = 4
    grid[0][0] = 8; grid[0][-1] = 9
    output = deepcopy(grid)
    for r, c in cells:
        output[r][c] = 8
    return {'input': grid, 'output': output}


def 教師():
    return [教材(), 教材(10, 12, 4, 5), 教材(12, 14, 5, 6)]


class 十字回帰(unittest.TestCase):
    def test_十字だけ着色し他色と非match同色を保持(self):
        pair = 教材(); output, record = guarded_render(pair['input'], 4, 8)
        self.assertEqual(output, pair['output'])
        self.assertEqual(record['centers'], 1); self.assertEqual(record['union_pixels'], 5)
        self.assertEqual(record['source_outside_union'], 2)
        self.assertEqual(output[0][0], 8); self.assertEqual(output[0][-1], 9)

    def test_密な3x3ではcornerを条件にしない(self):
        grid = [[4] * 3 for _ in range(3)]
        expected = [[4, 8, 4], [8, 8, 8], [4, 8, 4]]
        output, record = guarded_render(grid, 4, 8)
        self.assertEqual(output, expected); self.assertEqual(record['union_pixels'], 5)

    def test_重複matchを原入力から全て和集合にする(self):
        grid = [[4] * 5 for _ in range(5)]
        expected = [[8] * 5 for _ in range(5)]
        for r, c in ((0, 0), (0, 4), (4, 0), (4, 4)):
            expected[r][c] = 4
        output, record = guarded_render(grid, 4, 8)
        self.assertEqual(output, expected)
        self.assertEqual(record['centers'], 9); self.assertEqual(record['union_pixels'], 21)
        self.assertEqual(record['overlap_reuses'], 24)

    def test_D4の全方向で同じ局所形態を扱う(self):
        pair = 教材()
        for name in ('identity', 'rot90', 'rot180', 'rot270', 'flip_h', 'flip_v', 'transpose', 'anti_transpose'):
            self.assertEqual(guarded_render(transform_grid_by_name(pair['input'], name), 4, 8)[0],
                             transform_grid_by_name(pair['output'], name))

    def test_色遷移は加算や背景規約ではない(self):
        for source, target in ((0, 9), (9, 1), (7, 2)):
            grid = [[source] * 3 for _ in range(3)]
            expected = [[source, target, source], [target, target, target], [source, target, source]]
            self.assertEqual(guarded_render(grid, source, target)[0], expected)
            self.assertEqual(raw_color_fit([{'input': grid, 'output': expected}]), (source, target))

    def test_端に接する完全matchと不完全盤外を区別(self):
        grid = [[0, 4, 0], [4, 4, 4], [0, 4, 0]]
        self.assertEqual(guarded_render(grid, 4, 8)[0], [[0, 8, 0], [8, 8, 8], [0, 8, 0]])
        self.assertEqual(guarded_render([[4, 4, 4], [0, 4, 0]], 4, 8)[1]['failure'], 'no_complete_plus_match')
        self.assertEqual(guarded_render([[0] * 4 for _ in range(4)], 4, 8)[1]['failure'], 'no_complete_plus_match')

    def test_不正格子と同一色役割はHOLD(self):
        for grid in ([], [[0], [0, 1]], [[True]], [[10]], [[0] * 31]):
            self.assertEqual(guarded_render(grid, 4, 8)[1]['failure'], 'invalid_arc_grid')
        for roles in ((4, 4), (False, 8), (4, 10)):
            self.assertEqual(guarded_render(教材()['input'], *roles)[1]['failure'], 'invalid_color_roles')

    def test_元出力不一致と不完全着色は代替禁止(self):
        pair = 教材(); bad = deepcopy(pair['output']); bad[3][4] = 4
        for output in (bad, pair['input'], None):
            with patch.object(module.old, 'plus_recolor', return_value=output):
                self.assertEqual(guarded_render(pair['input'], 4, 8)[1]['failure'], 'source_output_disagrees')

    def test_全教師共通の一遷移と全盤面fitが必要(self):
        pairs = 教師(); self.assertEqual(raw_color_fit(pairs), (4, 8))
        pairs[-1]['output'][5][6] = 9
        self.assertIsNone(十字教材(pairs).色遷移)
        pair = 教材(); self.assertIsNone(十字教材([pair, pair]).色遷移)
        pair = 教材(); pair['output'][0][-1] = 8
        self.assertIsNone(raw_color_fit([pair]))

    def test_rawfit失敗後にguardで別色を選ばない(self):
        with patch.object(module, 'raw_color_fit', return_value=None):
            with patch.object(module, 'guarded_render', side_effect=AssertionError('guard before raw fit')):
                self.assertIsNone(十字教材(教師()).色遷移)

    def test_native支持は三盤面でmatch数を加算しない(self):
        pairs = 教師(); view = 十字教材(pairs); boundary = '十字対照'
        self.assertEqual(view.色遷移, (4, 8))
        self.assertFalse(候補機構を学習(HDS学習実行系(), {'train': pairs[:2]}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系()
        record = 候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertEqual(record['現在観測数'], 3); self.assertEqual(record['事前観測数'], 0)
        query = 教材(14, 16, 6, 7)
        self.assertEqual(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'], query['output'])
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[9]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'])

    def test_採用済みno_match_queryは全体HOLD(self):
        task = {'train': 教師(), 'test': [{'input': [[0] * 6 for _ in range(6)]}]}
        result = 課題を解く(task, [])
        record = next(r for r in result['families'] if r['境界'] == 'ARC十字形態着色')
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
