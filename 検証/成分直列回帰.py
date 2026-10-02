"""全成分のpath直列化、固定端点選好と二盤面の支持を検証する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 成分直列教材 as module
from 接続.ARC2.成分直列教材 import guarded_render, 成分直列教材
from 接続.ARC2.既存成分直列 import panel_shape_ordering_compress
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 出力格子, 観測へ, 課題を解く


def 教材(sizes=(3, 2, 4), colors=(1, 2, 3), height=12, width=14):
    a, b, c = sizes
    grid = [[0] * width for _ in range(height)]
    for col in range(2, 2 + a):
        grid[2][col] = colors[0]
    for row in range(3, 3 + b):
        grid[row][1 + a] = colors[1]
    for col in range(1 + a, 1 + a + c):
        grid[3 + b][col] = colors[2]
    return {'input': grid, 'output': [[color] for color, size in zip(colors, sizes) for _ in range(size)]}


def 教師():
    return [教材(), 教材((2, 3, 5), (4, 5, 6))]


class 成分直列回帰(unittest.TestCase):
    def test_全成分のpath順と全画素数(self):
        pair = 教材(); output, record = guarded_render(pair['input'])
        self.assertEqual(output, pair['output'])
        self.assertEqual(record['components'], 3); self.assertEqual(record['foreground_pixels'], 9)
        self.assertEqual(record['ordered_color_sizes'], [[1, 3], [2, 2], [3, 4]])

    def test_同色の離れた成分と単一成分を保存(self):
        grid = [[0] * 9 for _ in range(9)]; grid[4][2:5] = [1, 2, 1]
        self.assertEqual(guarded_render(grid)[0], [[1], [2], [1]])
        grid = [[0] * 9 for _ in range(9)]; grid[3][3:6] = [4, 4, 4]
        output, record = guarded_render(grid)
        self.assertEqual(output, [[4], [4], [4]]); self.assertEqual(record['components'], 1)

    def test_上端優先と同じ上端で左優先(self):
        pair = 教材(); output, _ = guarded_render(pair['input'][::-1])
        self.assertEqual(output, [[3]] * 4 + [[2]] * 2 + [[1]] * 3)
        grid = [[0] * 12 for _ in range(8)]; grid[3][2:8] = [1, 1, 2, 2, 2, 3]
        self.assertEqual(guarded_render(grid)[0], [[1], [1], [2], [2], [2], [3]])
        self.assertEqual(guarded_render([row[::-1] for row in grid])[0], [[3], [2], [2], [2], [1], [1]])

    def test_配色置換と背景が固定色でない(self):
        pair = 教材(); mapping = {0: 8, 1: 7, 2: 4, 3: 9}
        convert = lambda grid: [[mapping[v] for v in row] for row in grid]
        self.assertEqual(guarded_render(convert(pair['input']))[0], convert(pair['output']))

    def test_分岐閉路孤立と対角接触は全体HOLD(self):
        branch = [[0] * 9 for _ in range(9)]
        for r, c, v in ((3, 4, 1), (4, 4, 2), (4, 3, 3), (4, 5, 4), (5, 4, 5)):
            branch[r][c] = v
        cycle = [[0] * 9 for _ in range(9)]
        for r, c, v in ((3, 3, 1), (3, 4, 2), (4, 4, 3), (4, 3, 4)):
            cycle[r][c] = v
        isolated = 教材()['input']; isolated[-1][-1] = 9
        diagonal = [[0] * 9 for _ in range(9)]; diagonal[3][3] = 1; diagonal[4][4] = 2
        for grid in (branch, cycle, isolated, diagonal):
            self.assertIsNone(guarded_render(grid)[0]); self.assertIsNone(panel_shape_ordering_compress(grid))

    def test_30を通して31は切り詰めない(self):
        grid = [[0] * 30 for _ in range(3)]; grid[0] = [1] * 30
        self.assertEqual(guarded_render(grid)[0], [[1]] * 30)
        grid[1][0] = 1
        self.assertEqual(len(panel_shape_ordering_compress(grid)), 31)
        self.assertEqual(guarded_render(grid)[1]['failure'], 'output_height_out_of_arc_bounds')

    def test_背景同率と不正格子はHOLD(self):
        self.assertEqual(guarded_render([[0, 1], [1, 0]])[1]['failure'], 'background_tie')
        self.assertIsNone(guarded_render([[0] * 4 for _ in range(4)])[0])
        for grid in ([], [[0], [0, 1]], [[True]], [[10]], [[0] * 31]):
            self.assertEqual(guarded_render(grid)[1]['failure'], 'invalid_arc_grid')

    def test_全成分coverageを欠落重複させない(self):
        pair = 教材(); components = module.old.same_color_components_excluding_background(pair['input'])
        for altered in (components[:-1], components + [components[0]]):
            with patch.object(module.old, 'same_color_components_excluding_background', return_value=altered):
                self.assertIsNone(guarded_render(pair['input'])[0])

    def test_元出力不一致を検証格子へ置換しない(self):
        pair = 教材(); bad = deepcopy(pair['output']); bad[-1] = [9]
        with patch.object(module.old, 'panel_shape_ordering_compress', return_value=bad):
            self.assertEqual(guarded_render(pair['input'])[1]['failure'], 'source_output_disagrees')

    def test_矛盾と重複教師を採用しない(self):
        pairs = 教師(); pairs[-1]['output'][0] = [9]
        self.assertFalse(成分直列教材(pairs).適合)
        pair = 教材(); self.assertFalse(成分直列教材([pair, pair]).適合)

    def test_native支持は二盤面で成分数を加算しない(self):
        pairs = 教師(); view = 成分直列教材(pairs); boundary = '成分直列対照'
        self.assertTrue(view.適合)
        self.assertFalse(候補機構を学習(HDS学習実行系(), {'train': pairs}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系(最小支持数=2)
        record = 候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertEqual(record['現在観測数'], 2); self.assertEqual(record['事前観測数'], 0)
        query = 教材((4, 3, 3), (7, 8, 9))
        self.assertEqual(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'], query['output'])
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[9]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'])

    def test_採用済み未解決queryは全体HOLD(self):
        grid = 教材()['input']; grid[-1][-1] = 9
        task = {'train': 教師(), 'test': [{'input': grid}]}
        result = 課題を解く(task, [])
        record = next(r for r in result['families'] if r['境界'] == 'ARC成分path直列化')
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
