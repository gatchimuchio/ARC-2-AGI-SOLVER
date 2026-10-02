"""固定run周期と優先規則、役割・保存、native支持を確認する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 行周期教材 as module
from 接続.ARC2.行周期教材 import guarded_separator_run, raw_separator_candidates, 行周期教材
from 接続.ARC2.既存行周期 import find_partial_vertical_separator, render_separator_run_period_superposition
from 接続.ARC2.HDS接続 import 課題を解く, HDS学習実行系, 候補機構を学習, 出力格子, 観測へ


def 教材(width=19, height=7):
    grid = [[0] * width for _ in range(height)]
    for row in grid:
        row[6] = 9
    grid[2][1:6] = [3, 3, 3, 4, 4]
    output = deepcopy(grid)
    pattern = [4, 0, 4, 3, 4, 0]
    for index in range(width - 7):
        output[2][7 + index] = pattern[index % 6]
    return {'input': grid, 'output': output}


def 教師():
    return [教材(), 教材(20, 8), 教材(21, 9)]


class 行周期回帰(unittest.TestCase):
    def test_周期2と3の重ね合わせは近傍runが優先(self):
        for pair in 教師() + [教材(23, 10)]:
            output, record = guarded_separator_run(pair['input'])
            self.assertEqual(output, pair['output'])
            self.assertEqual(record['row_records'][0]['period_sample_from_separator'], [4, 0, 4, 3, 4, 0])
            self.assertEqual(record['row_records'][0]['period_length'], 6)

    def test_左右上下反転と色の変更(self):
        pair = 教材()
        transforms = [lambda g: [row[::-1] for row in g], lambda g: g[::-1],
                      lambda g: [[9 - v for v in row] for row in g]]
        for transform in transforms:
            self.assertEqual(guarded_separator_run(transform(pair['input']))[0], transform(pair['output']))

    def test_行ごとにactive側が違っても処理(self):
        grid = 教材()['input']; grid[4][7:9] = [5, 5]
        output, record = guarded_separator_run(grid)
        self.assertIsNotNone(output)
        self.assertEqual(output[4][:6], [0, 5, 0, 5, 0, 5])
        self.assertEqual([r['active_side'] for r in record['row_records']], ['left', 'right'])

    def test_部分separatorと非active行は保存(self):
        grid = 教材()['input']; grid[4][4:6] = [5, 5]
        for r in range(len(grid)):
            if r not in {2, 4}:
                grid[r][6] = 0
        output, record = guarded_separator_run(grid)
        self.assertIsNotNone(output)
        self.assertEqual(record['separator']['candidate_record']['non_background_count'], 2)
        self.assertTrue(all(output[r] == grid[r] for r in range(len(grid)) if r not in {2, 4}))
        grid[4] = [0] * len(grid[0])
        self.assertIsNone(guarded_separator_run(grid)[0])

    def test_codeの空白距離は出力位相をずらさない(self):
        grid = 教材()['input']; grid[2][:6] = [0, 5, 5, 5, 5, 0]
        output, record = guarded_separator_run(grid)
        self.assertEqual(output[2][7:], [5, 0, 0, 0] * 3)
        self.assertEqual(record['row_records'][0]['runs_from_separator'][0]['start_distance'], 1)

    def test_周期1抑制とseparator色のrun兼用(self):
        grid = 教材()['input']; grid[2][:6] = [0, 6, 6, 6, 6, 8]
        self.assertEqual(guarded_separator_run(grid)[0][2][7:], [8] * 12)
        grid[2][:6] = [0, 0, 9, 1, 1, 0]
        self.assertEqual(guarded_separator_run(grid)[0][2][7:], [1, 9] * 6)

    def test_rawseparator複数は後段処理前に拒否(self):
        grid = [[0] * 13 for _ in range(7)]
        for row in grid:
            row[3], row[8] = 8, 9
        self.assertEqual(len(raw_separator_candidates(grid, 0)), 2)
        self.assertIsNone(find_partial_vertical_separator(grid, 0))
        self.assertEqual(guarded_separator_run(grid)[1]['candidate_count'], 2)

    def test_両側activeと行イベントなしを保留(self):
        grid = 教材()['input']; grid[2][10] = 5
        self.assertEqual(guarded_separator_run(grid)[1]['failure'], 'both_sides_active')
        grid = 教材()['input']; grid[2][:6] = [0] * 6
        self.assertEqual(guarded_separator_run(grid)[1]['failure'], 'no_rows_changed')

    def test_無効格子と背景同率を拒否(self):
        for grid in ([], [[0], [0, 1]], [[True]], [[10]], [[0] * 31]):
            self.assertEqual(guarded_separator_run(grid)[1]['failure'], 'invalid_grid')
        self.assertEqual(guarded_separator_run([[0, 1], [1, 0]])[1]['failure'], 'background_tie')

    def test_元入力のcodeとseparatorと非active行を守る(self):
        grid = 教材()['input']; good, record = render_separator_run_period_superposition(grid)
        for cell, reason in [((2, 1), 'active_code_changed'), ((0, 6), 'separator_changed'), ((0, 0), 'inactive_row_changed')]:
            bad = deepcopy(good); bad[cell[0]][cell[1]] = 7
            with patch.object(module.old, 'render_separator_run_period_superposition', return_value=(bad, record)):
                self.assertEqual(guarded_separator_run(grid)[1]['failure'], reason)

    def test_教師反例と重複を採用しない(self):
        pairs = 教師(); pairs[-1]['output'] = [[3]]
        self.assertFalse(行周期教材(pairs).全教師再現)
        self.assertFalse(行周期教材([教材(), 教材(), 教材()]).全教師再現)

    def test_native支持は三教師格子で反例隔離も保持(self):
        pairs = 教師(); query = 教材(23, 10); view = 行周期教材(pairs)
        result = 課題を解く({'train': pairs, 'test': [{'input': query['input']}]}, [])
        self.assertEqual(result['results'][0]['answer'], query['output'])
        record = next(r for r in result['families'] if r['境界'] == 'ARC行周期合成')
        self.assertEqual(record['現在観測数'], 3); self.assertEqual(record['事前観測数'], 0)
        self.assertTrue(record['同値採用']); self.assertEqual(result['minimum_support'], 3)
        engine = HDS学習実行系(); boundary = '行周期対照'
        self.assertFalse(候補機構を学習(engine, {'train': pairs[:2]}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系()
        self.assertTrue(候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)['同値採用'])
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[3]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'])

    def test_採用済み機構の未解決queryは全体保留(self):
        grid = 教材()['input']; grid[2][10] = 5
        result = 課題を解く({'train': 教師(), 'test': [{'input': grid}]}, [])
        self.assertIsNone(result['results'][0]['answer'])
        self.assertTrue(any('ARC行周期合成' in s for s in result['results'][0]['reasons']))


if __name__ == '__main__':
    unittest.main()
