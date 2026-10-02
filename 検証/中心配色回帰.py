"""中心形態priorの全対象処理・票の一意性・三盤面支持を検証。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 中心配色教材 as module
from 接続.ARC2.中心配色教材 import guarded_render, 中心配色教材
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 出力格子, 観測へ, 課題を解く


def 教材(up=3, down=5):
    grid = [[0] * 20 for _ in range(20)]
    for r in range(8, 11):
        for c in range(8, 11): grid[r][c] = 7
    parts = [({(r, 9) for r in range(8 - up, 8)}, 1),
             ({(r, 9) for r in range(11, 11 + down)}, 2),
             ({(9, c) for c in range(4, 8)}, 1),
             ({(9, c) for c in range(11, 15)}, 2)]
    for cells, _ in parts:
        for r, c in cells: grid[r][c] = 7
    for r, c, v in [(2,8,1),(2,9,1),(2,10,2),(18,8,2),(18,9,2),(18,10,1),
                    (8,1,1),(9,1,1),(10,1,2),(8,18,2),(9,18,2),(10,18,1)]:
        grid[r][c] = v
    output = deepcopy(grid)
    for cells, color in parts:
        for r, c in cells: output[r][c] = color
    output[9][9] = 2 if down > up else 1
    return {'input': grid, 'output': output}


def 教師():
    return [教材(), 教材(4, 6), 教材(2, 4)]


def 領域同率():
    grid = 教材()['input']; grid[2][8] = 0
    return grid


class 中心配色回帰(unittest.TestCase):
    def test_全target処理とperimeter_source背景保存(self):
        for pair in 教師():
            output, record = guarded_render(pair['input'])
            self.assertEqual(output, pair['output'])
            cert = record['certificate']
            self.assertEqual(cert['target_cells'] - cert['recolored_target_cells'], 8)
            self.assertEqual(cert['protected_cells'] + cert['recolored_target_cells'], 400)

    def test_配色回転反転と可変canvas位置(self):
        pair = 教材()
        def transform(grid, k):
            x = [row[::-1] if k // 4 else row[:] for row in grid]
            for _ in range(k % 4): x = [list(row) for row in zip(*x[::-1])]
            return [[{0: 6, 7: 4, 1: 9, 2: 3}[v] for v in row] for row in x]
        for k in range(8): self.assertEqual(guarded_render(transform(pair['input'], k))[0], transform(pair['output'], k))
        pad = lambda g: [[0] * 24 for _ in range(2)] + [[0] * 3 + row + [0] for row in g] + [[0] * 24]
        self.assertEqual(guarded_render(pad(pair['input']))[0], pad(pair['output']))

    def test_重心でcomponent全体を分類しsector外cellも処理(self):
        pair = 教材(); grid = pair['input']
        for r in range(5, 8): grid[r][9] = 0
        cells = {(7,8),(6,8),(6,7),(6,6),(5,6),(5,5)}
        for r, c in cells: grid[r][c] = 7
        grid[2][2] = grid[2][3] = 1; grid[3][2] = 2
        output, record = guarded_render(grid)
        self.assertIsNotNone(output)
        self.assertEqual(module.integer_sector(cells, (8, 8)), 'top_left')
        self.assertTrue(any(not module.sector_contains('top_left', r, c, (8, 8)) for r, c in cells))
        self.assertTrue(all(output[r][c] == 1 for r, c in cells))
        self.assertEqual(record['certificate']['center_area_votes'], {1: 10, 2: 9})
        self.assertEqual(output[9][9], 1)

    def test_中心はcomponent個数でなく面積加重(self):
        grid = 教材()['input']
        for r in range(5, 8): grid[r][9] = 0
        for c in range(4, 7): grid[9][c] = 0
        for r in (6, 7): grid[r][8] = grid[r][10] = 7
        grid[16][9] = grid[17][9] = 7
        output, record = guarded_render(grid)
        self.assertIsNotNone(output)
        assignments = record['source_record']['assignments']
        self.assertEqual(sum(a['selected_color'] == 1 for a in assignments), 3)
        self.assertEqual(sum(a['selected_color'] == 2 for a in assignments), 2)
        self.assertEqual(record['certificate']['center_area_votes'], {1: 5, 2: 11})
        self.assertEqual(output[9][9], 2)

    def test_票に使わないsourceも保存(self):
        pair = 教材(0, 5); output, record = guarded_render(pair['input'])
        self.assertEqual(output, pair['output'])
        self.assertEqual(record['certificate']['source_cells_unused_and_preserved'], 3)
        self.assertEqual(output[2], pair['input'][2])

    def test_領域票tieを数値色で解決しない(self):
        grid = 領域同率()
        self.assertIsNotNone(module.old._target_square_palette_render(grid)[0])
        self.assertEqual(guarded_render(grid)[1]['failure'], 'sector_source_vote_tie')

    def test_中心面積tieを左側優先で解決しない(self):
        grid = 教材(5, 5)['input']
        self.assertIsNotNone(module.old._target_square_palette_render(grid)[0])
        self.assertEqual(guarded_render(grid)[1]['failure'], 'center_area_vote_tie')

    def test_最大targetを先決し小targetへfallbackしない(self):
        grid = 教材()['input']
        for r in range(5):
            for c in range(14, 19): grid[r][c] = 9
        self.assertEqual(guarded_render(grid)[1]['failure'], 'largest_target_tie')
        for c in range(14, 19): grid[5][c] = 9
        self.assertEqual(guarded_render(grid)[1]['failure'], 'source_palette_not_two')

    def test_唯一3x3と同色全cell帰属を要求(self):
        grid = 教材()['input']; grid[0][0] = 7
        self.assertEqual(guarded_render(grid)[1]['failure'], 'split_target_color')
        grid = 教材()['input']
        for r in range(1, 4):
            for c in range(8, 11): grid[r][c] = 7
        grid[4][9] = 7
        self.assertEqual(guarded_render(grid)[1]['failure'], 'anchor_not_unique_3x3')

    def test_欠落target分割は全体HOLD(self):
        original = module.old._palette_cell_components
        def missing(cells, diagonal=False):
            result = original(cells, diagonal)
            return result if diagonal else result[:-1]
        with patch.object(module.old, '_palette_cell_components', side_effect=missing):
            self.assertEqual(guarded_render(教材()['input'])[1]['failure'], 'target_partition_incomplete')

    def test_元格子記録不一致と背景同率無効格子(self):
        grid = 教材()['input']; output, record = module.old._target_square_palette_render(grid)
        bad_record = deepcopy(record); bad_record['center_color'] = 9
        for o, r in (([[9]], record), (output, bad_record)):
            with patch.object(module.old, '_target_square_palette_render', return_value=(o, r)):
                self.assertEqual(guarded_render(grid)[1]['failure'], 'source_output_or_record_disagrees')
        self.assertEqual(guarded_render([[0, 1], [1, 0]])[1]['failure'], 'background_tie')
        for bad in ([], [[0], [0, 1]], [[True]], [[10]]):
            self.assertEqual(guarded_render(bad)[1]['failure'], 'invalid_arc_grid')

    def test_最低二教師と全raw適合先決と重複拒否(self):
        self.assertFalse(中心配色教材(教師()[:1]).適合)
        pairs = 教師(); pairs[-1]['output'][0][0] = 9
        with patch.object(module, 'guarded_render', side_effect=AssertionError('guard before raw fit')):
            self.assertFalse(中心配色教材(pairs).適合)
        pair = 教材(); self.assertFalse(中心配色教材([pair, pair]).適合)

    def test_native支持は三盤面で領域票や面積を加算しない(self):
        pairs = 教師(); view = 中心配色教材(pairs); boundary = '中心配色対照'
        engine = HDS学習実行系(最小支持数=3)
        self.assertFalse(候補機構を学習(engine, {'train': pairs[:2]}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系(最小支持数=3)
        record = 候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertEqual(record['現在観測数'], 3); self.assertEqual(record['事前観測数'], 0)
        query = pairs[0]['output']
        self.assertEqual(出力格子(engine, 観測へ({'候補': query}, boundary), 同値必須=True)['answer'], query)
        engine.実行(観測へ({'候補': query, '出力': [[9]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': query}, boundary), 同値必須=True)['answer'])

    def test_採用済み同率queryの全体HOLDと情報分離(self):
        task = {'train': 教師(), 'test': [{'input': 領域同率()}]}; result = 課題を解く(task, [])
        record = next(r for r in result['families'] if r['境界'] == 'ARC中心anchor配色')
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertEqual(record['現在観測数'], 3)
        self.assertIsNone(result['results'][0]['answer'])
        task['task_id'] = 'forbidden'
        with self.assertRaises(ValueError): 課題を解く(task, [])
        task.pop('task_id'); task['test'][0]['output'] = [[1]]
        with self.assertRaises(ValueError): 課題を解く(task, [])


if __name__ == '__main__':
    unittest.main()
