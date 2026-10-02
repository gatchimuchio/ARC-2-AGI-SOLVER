"""固定下向き流路、全入力の拒否条件、六盤面のnative支持を検証する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 流路教材 as module
from 接続.ARC2.流路教材 import guarded_render, raw_fits, 流路教材
from 接続.ARC2.既存流路 import CorridorFit, gravity_corridor_route
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 出力格子, 観測へ, 課題を解く

FIT = CorridorFit(1, 2)


def 教材(height=9, width=11, left=3, right=7, seed=5, wall=3):
    grid = [[0] * width for _ in range(height)]
    grid[0][seed] = 1
    for c in range(left, right + 1):
        grid[wall][c] = 2
    output = deepcopy(grid)
    for r in range(wall):
        output[r][seed] = 1
    for c in range(max(0, left - 1), min(width - 1, right + 1) + 1):
        output[wall - 1][c] = 1
    for c in (left - 1, right + 1):
        if 0 <= c < width:
            for r in range(wall, height):
                output[r][c] = 1
    return {'input': grid, 'output': output}


def 教師():
    return [教材(), 教材(10, 12), 教材(11, 13), 教材(12, 14), 教材(13, 15), 教材(14, 16)]


def 飛越():
    grid = [[0] * 9 for _ in range(7)]
    grid[2][3] = 1; grid[2][4] = 2
    for c in range(2, 7):
        grid[3][c] = 2
    return grid


class 流路回帰(unittest.TestCase):
    def test_障害run上側と両端の流路(self):
        pair = 教材(); output, record = guarded_render(pair['input'], FIT)
        self.assertEqual(output, pair['output'])
        self.assertEqual(record['obstacle_run_contacts'], 1)
        self.assertEqual(record['seed_count'], 1)

    def test_左右反転と役割色置換(self):
        pair = 教材(left=2, right=6, seed=4)
        flipped = {k: [row[::-1] for row in v] for k, v in pair.items()}
        self.assertEqual(guarded_render(flipped['input'], FIT)[0], flipped['output'])
        recolor = lambda grid: [[{0: 7, 1: 4, 2: 9}[v] for v in row] for row in grid]
        self.assertEqual(guarded_render(recolor(pair['input']), CorridorFit(4, 9))[0], recolor(pair['output']))

    def test_盤面端の出口と全幅障害(self):
        for pair in (教材(left=0, right=6, seed=3), 教材(left=0, right=10, seed=5)):
            output, record = guarded_render(pair['input'], FIT)
            self.assertEqual(output, pair['output'])
            self.assertEqual(record['clipped_exit_runs'], 1)
        self.assertTrue(all(v == 0 for v in output[-1]))

    def test_すべてのseedから展開する(self):
        pair = 教材(); pair['input'][0][0] = 1
        expected = deepcopy(pair['output'])
        for row in expected:
            row[0] = 1
        output, record = guarded_render(pair['input'], FIT)
        self.assertEqual(output, expected); self.assertEqual(record['seed_count'], 2)

    def test_横障害飛越は全体HOLD(self):
        grid = 飛越()
        self.assertIsNotNone(gravity_corridor_route(grid, FIT))
        self.assertEqual(guarded_render(grid, FIT)[1]['failure'], 'triggered_span_crosses_obstacle')
        grid[0][0] = 1  # 別の正常seedがあっても部分回答しない。
        self.assertEqual(guarded_render(grid, FIT)[1]['failure'], 'triggered_span_crosses_obstacle')

    def test_未到達の横障害を不要に拒否しない(self):
        grid = [[0] * 9 for _ in range(8)]
        grid[0][0] = 1; grid[2][4] = 2
        expected = deepcopy(grid)
        for row in expected:
            row[0] = 1
        self.assertEqual(guarded_render(grid, FIT)[0], expected)

    def test_背景同率と未知色と役割逆転はHOLD(self):
        self.assertEqual(guarded_render([[0, 0, 1], [2, 2, 1]], FIT)[1]['failure'], 'background_tie')
        grid = 教材()['input']; grid[-1][-1] = 9
        self.assertEqual(guarded_render(grid, FIT)[1]['failure'], 'palette_out_of_scope')
        self.assertEqual(guarded_render([[1, 1, 1], [1, 0, 2]], FIT)[1]['failure'], 'palette_out_of_scope')

    def test_無変化と不正格子役割はHOLD(self):
        grid = [[0] * 5 for _ in range(5)]; grid[-1][0] = 1; grid[0][-1] = 2
        self.assertEqual(guarded_render(grid, FIT)[1]['failure'], 'source_no_candidate')
        for grid in ([], [[0], [0, 1]], [[True]], [[10]], [[0] * 31]):
            self.assertEqual(guarded_render(grid, FIT)[1]['failure'], 'invalid_arc_grid')
        self.assertEqual(guarded_render(教材()['input'], CorridorFit(1, 1))[1]['failure'], 'invalid_roles')

    def test_元出力不一致は検証格子へ置換しない(self):
        pair = 教材(); bad = deepcopy(pair['output']); bad[-1][-1] = 9
        with patch.object(module.old, 'gravity_corridor_route', return_value=bad):
            self.assertEqual(guarded_render(pair['input'], FIT)[1]['failure'], 'source_output_disagrees')

    def test_raw全fit一意をguardより先に確定(self):
        pairs = 教師(); self.assertEqual(raw_fits(pairs), [FIT])
        with patch.object(module, 'raw_fits', return_value=[FIT, CorridorFit(2, 1)]):
            with patch.object(module, 'guarded_render', side_effect=AssertionError('guard called before uniqueness')):
                self.assertIsNone(流路教材(pairs).役割)

    def test_矛盾と重複教師から役割を採用しない(self):
        pairs = 教師(); pairs[-1]['output'][-1][-1] = 9
        self.assertIsNone(流路教材(pairs).役割)
        pair = 教材(); self.assertIsNone(流路教材([pair, pair]).役割)

    def test_native支持は六盤面でseed数を加算しない(self):
        pairs = 教師(); view = 流路教材(pairs); boundary = '下向き流路対照'
        self.assertEqual(view.役割, FIT)
        self.assertFalse(候補機構を学習(HDS学習実行系(), {'train': pairs[:2]}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系()
        record = 候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertEqual(record['現在観測数'], 6); self.assertEqual(record['事前観測数'], 0)
        query = 教材(15, 17)
        self.assertEqual(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'], query['output'])
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[9]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'])

    def test_採用済み候補の飛越queryは全体HOLD(self):
        task = {'train': 教師(), 'test': [{'input': 飛越()}]}
        result = 課題を解く(task, [])
        record = next(r for r in result['families'] if r['境界'] == 'ARC下向き流路')
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
