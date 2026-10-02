"""凡例の役割と全経路証明、実観測によるnative採用を確認する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 凡例経路教材 as module
from 接続.ARC2.凡例経路教材 import certified_legend_gap, 凡例経路教材
from 接続.ARC2.既存凡例経路 import render_legend_payload_gap_connectors
from 接続.ARC2.HDS接続 import 課題を解く, HDS学習実行系, 候補機構を学習, 出力格子, 観測へ


def 盤面(shape, panels, sequence, *, background=0, frame=1, legend_row=None):
    grid = [[background] * shape[1] for _ in range(shape[0])]
    for r, c, color in panels:
        for dr in range(3):
            for dc in range(3):
                grid[r + dr][c + dc] = frame if dr in {0, 2} or dc in {0, 2} else color
    if legend_row is None:
        legend_row = shape[0] - 1
    for i, color in enumerate(sequence):
        grid[legend_row][1 + 2 * i] = color
    return grid


def 教材(gap=3, height=8):
    right = 4 + gap
    grid = 盤面((height, right + 5), [(1, 1, 2), (1, right, 3)], [2, 3])
    output = deepcopy(grid)
    for col in range(4, right):
        output[2][col] = 2
    return {'input': grid, 'output': output}


def 教師():
    return [教材(3), 教材(4, 9), 教材(5, 10)]


class 凡例経路回帰(unittest.TestCase):
    def test_入力凡例で異なる間隔と位置を接続(self):
        for pair in 教師() + [教材(7, 11)]:
            output, record = certified_legend_gap(pair['input'])
            self.assertEqual(output, pair['output'])
            self.assertEqual(record['certificate']['complete_paths'], 1)
        pair = 教材()
        grid = deepcopy(pair['input']); grid[0] = grid[-1]; grid[-1] = [0] * len(grid[0])
        expected = deepcopy(pair['output']); expected[0] = expected[-1]; expected[-1] = [0] * len(expected[0])
        self.assertEqual(certified_legend_gap(grid)[0], expected)

    def test_配色と可変長方形frameでpayload幅を保存(self):
        grid = [[0] * 18 for _ in range(10)]
        for left, color in [(1, 2), (11, 3)]:
            for r in range(1, 6):
                for c in range(left, left + 6):
                    grid[r][c] = 1 if r in {1, 5} or c in {left, left + 5} else 0
            for r in (2, 3):
                for c in (left + 1, left + 2):
                    grid[r][c] = color
        grid[8][1], grid[8][3] = 2, 3
        expected = deepcopy(grid)
        for r in (2, 3):
            for c in range(7, 11):
                expected[r][c] = 2
        recolor = lambda g: [[9 - v for v in row] for row in g]
        self.assertEqual(certified_legend_gap(grid)[0], expected)
        self.assertEqual(certified_legend_gap(recolor(grid))[0], recolor(expected))

    def test_同じ全格子を作る逆向き二経路は重複扱い(self):
        grid = 盤面((8, 12), [(1, 1, 2), (1, 7, 2)], [2, 2])
        output, record = certified_legend_gap(grid)
        self.assertIsNotNone(output)
        self.assertEqual(record['certificate']['complete_paths'], 2)
        self.assertEqual(record['certificate']['distinct_outputs'], 1)

    def test_異なる全格子を作る経路は保留(self):
        grid = 盤面((14, 14), [(1, 1, 2), (1, 7, 3), (7, 1, 2), (7, 7, 3)], [2, 3])
        self.assertIsNotNone(render_legend_payload_gap_connectors(grid)[0])
        self.assertEqual(certified_legend_gap(grid)[1]['failure'], 'complete_path_output_disagreement')

    def test_一つでも異色通路交差なら全体保留(self):
        grid = 盤面((19, 19), [(7, 1, 2), (7, 13, 3), (1, 13, 4), (1, 7, 5), (13, 7, 6)], [2, 3, 4, 5, 6])
        self.assertIsNotNone(render_legend_payload_gap_connectors(grid)[0])
        self.assertEqual(certified_legend_gap(grid)[1]['failure'], 'complete_path_paint_conflict')

    def test_候補発見後でも探索上限なら保留(self):
        grid = 盤面((8, 12), [(1, 1, 2), (1, 7, 2)], [2, 2])
        with patch.object(module, 'NODE_BUDGET', 3):
            output, record = certified_legend_gap(grid)
        self.assertIsNone(output)
        self.assertEqual(record['failure'], 'path_certificate_budget')
        self.assertEqual(record['complete_paths'], 1)

    def test_後続frame検査で競合役割を捨てない(self):
        grid = 盤面((14, 14), [(1, 1, 2), (1, 7, 2)], [2, 3])
        for left in (1, 7):
            for r in range(7, 10):
                for c in range(left, left + 3):
                    grid[r][c] = 4 if r in {7, 9} or c in {left, left + 2} else 3
        grid[7][1] = 0  # この役割は後続の閉境界検査では失敗するが、raw役割から除外しない
        output, record = certified_legend_gap(grid)
        self.assertIsNone(output)
        self.assertEqual(record['failure'], 'raw_frame_role_not_unique')
        self.assertEqual(record['roles'], [1, 4])

    def test_最長行同率別系列と複数外部行を保留(self):
        grid = 盤面((8, 12), [(1, 1, 2), (1, 7, 3)], [3, 2])
        self.assertEqual(certified_legend_gap(grid)[1]['failure'], 'legend_sequence_not_unique')
        grid = 教材()['input']; grid[6][8] = 4
        self.assertEqual(certified_legend_gap(grid)[1]['failure'], 'outside_legend_row_not_unique')

    def test_開いたframeと未解析frameを保留(self):
        grid = 教材()['input']; grid[1][1] = 0
        self.assertEqual(certified_legend_gap(grid)[1]['failure'], 'open_panel_frame')
        grid = 教材()['input']; grid[5][9] = 1
        self.assertEqual(certified_legend_gap(grid)[1]['failure'], 'unparsed_frame_component')

    def test_凡例に使わないpanelもそのまま保存(self):
        grid = 盤面((13, 12), [(1, 1, 2), (1, 7, 3), (7, 1, 5)], [2, 3])
        output, record = certified_legend_gap(grid)
        self.assertIsNotNone(output)
        self.assertEqual(len(record['path_panels']), 2)
        self.assertEqual([row[1:4] for row in output[7:10]], [row[1:4] for row in grid[7:10]])

    def test_元rendererと異なる答えへ置換しない(self):
        with patch.object(module.old, 'render_legend_payload_gap_connectors', return_value=([[9]], {})):
            output, record = certified_legend_gap(教材()['input'])
        self.assertIsNone(output)
        self.assertEqual(record['failure'], 'source_output_disagrees')

    def test_不正入力と背景同率を拒否(self):
        for grid in ([], [[0], [0, 1]], [[10]], [[True]], [[0] * 31]):
            self.assertEqual(certified_legend_gap(grid)[1]['failure'], 'invalid_grid')
        self.assertEqual(certified_legend_gap([[0, 1], [1, 0]])[1]['failure'], 'background_tie')

    def test_教師反例と重複教師は採用しない(self):
        pairs = 教師(); pairs[-1]['output'] = [[9]]
        self.assertFalse(凡例経路教材(pairs).全教師再現)
        self.assertFalse(凡例経路教材([教材(), 教材(), 教材()]).全教師再現)

    def test_native支持は三教師格子で後発反例も保留(self):
        pairs = 教師(); query = 教材(7, 11); view = 凡例経路教材(pairs)
        result = 課題を解く({'train': pairs, 'test': [{'input': query['input']}]}, [])
        self.assertEqual(result['results'][0]['answer'], query['output'])
        record = next(r for r in result['families'] if r['境界'] == 'ARC凡例経路接続')
        self.assertEqual(record['現在観測数'], 3); self.assertEqual(record['事前観測数'], 0)
        self.assertTrue(record['同値採用']); self.assertEqual(result['minimum_support'], 3)
        engine = HDS学習実行系(); boundary = '凡例経路対照'
        self.assertFalse(候補機構を学習(engine, {'train': pairs[:2]}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系()
        self.assertTrue(候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)['同値採用'])
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[9]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'])

    def test_採用済み経路の曖昧queryは全体保留(self):
        grid = 盤面((14, 14), [(1, 1, 2), (1, 7, 3), (7, 1, 2), (7, 7, 3)], [2, 3])
        result = 課題を解く({'train': 教師(), 'test': [{'input': grid}]}, [])
        self.assertIsNone(result['results'][0]['answer'])
        self.assertTrue(any('ARC凡例経路接続' in s for s in result['results'][0]['reasons']))


if __name__ == '__main__':
    unittest.main()
