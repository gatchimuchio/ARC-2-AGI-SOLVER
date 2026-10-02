"""bbox包含priorの全成分証明と四盤面のnative支持を検証する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 包含正規化教材 as module
from 接続.ARC2.包含正規化教材 import guarded_render, 包含正規化教材
from 接続.ARC2.既存包含正規化 import render_nested_frame_inventory
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 出力格子, 観測へ, 課題を解く


def 枠(grid, r0, c0, r1, c1, color=1):
    for r in range(r0, r1 + 1): grid[r][c0] = grid[r][c1] = color
    for c in range(c0, c1 + 1): grid[r0][c] = grid[r1][c] = color


def 教材(variant=0):
    grid = [[0] * 30 for _ in range(28)]
    枠(grid, 2, 2, 24, 24)
    if variant == 0:
        for r in range(6, 9):
            for c in range(6, 9): grid[r][c] = 1
        out = [[0] * 5 for _ in range(5)]; 枠(out, 0, 0, 4, 4); out[2][2] = 1
    elif variant == 1:
        grid[6][7] = grid[14][7] = 1
        out = [[0] * 5 for _ in range(7)]; 枠(out, 0, 0, 6, 4); out[2][2] = out[4][2] = 1
    elif variant == 2:
        枠(grid, 6, 6, 18, 18); grid[10][10] = 1
        out = [[0] * 9 for _ in range(9)]; 枠(out, 0, 0, 8, 8); 枠(out, 2, 2, 6, 6); out[4][4] = 1
    else:
        grid[6][6] = grid[6][27] = 1
        out = [[0] * 8 for _ in range(5)]; 枠(out, 0, 0, 4, 4); out[2][2] = out[2][6] = 1
    return {'input': grid, 'output': out}


def 教師():
    return [教材(i) for i in range(4)]


def 潰れる葉():
    grid = [[0] * 20 for _ in range(20)]; 枠(grid, 2, 2, 17, 17)
    for r, c in ((4, 4), (4, 5), (5, 4), (5, 6), (6, 5), (6, 6)): grid[r][c] = 1
    return grid


class 包含正規化回帰(unittest.TestCase):
    def test_全成分と全包含対を保持して小枠点へ正規化(self):
        for i, pair in enumerate(教師()):
            output, record = guarded_render(pair['input'])
            self.assertEqual(output, pair['output'])
            self.assertEqual(record['certificate']['physical_components'], [2, 3, 3, 3][i])
            self.assertEqual(record['certificate']['strict_containment_pairs'], [1, 2, 3, 1][i])
            self.assertLess(record['certificate']['output_foreground_cells'], record['certificate']['input_foreground_cells'])

    def test_回転反転と非固定配色(self):
        pair = 教材(3)
        def transform(g, flip, turns):
            g = [row[::-1] if flip else row[:] for row in g]
            for _ in range(turns): g = [list(row) for row in zip(*g[::-1])]
            return [[7 if v == 0 else 3 for v in row] for row in g]
        for flip in (False, True):
            for turns in range(4):
                self.assertEqual(guarded_render(transform(pair['input'], flip, turns))[0], transform(pair['output'], flip, turns))

    def test_入力は完全長方形枠でなくbbox包含を使う(self):
        pair = 教材()
        pair['input'][2][12] = 0
        self.assertEqual(guarded_render(pair['input'])[0], pair['output'])

    def test_別leafを同一点へ潰す元出力は全体HOLD(self):
        grid = 潰れる葉()
        self.assertIsNotNone(render_nested_frame_inventory(grid)[0])
        self.assertEqual(guarded_render(grid)[1]['failure'], 'canonical_components_overlap')

    def test_交差するcontainerを面積で選ばない(self):
        grid = [[0] * 30 for _ in range(30)]; 枠(grid, 0, 0, 27, 27)
        for c in range(2, 17): grid[2][c] = 1
        for r in range(2, 17): grid[r][2] = 1
        for c in range(8, 23): grid[22][c] = 1
        for r in range(8, 23): grid[r][22] = 1
        grid[12][12] = 1
        self.assertIsNotNone(render_nested_frame_inventory(grid)[0])
        self.assertEqual(guarded_render(grid)[1]['failure'], 'containers_not_strict_chain')

    def test_外部axis同率を先着groupで決めない(self):
        grid = [[0] * 27 for _ in range(24)]; 枠(grid, 1, 1, 20, 20)
        for r in range(3, 6): grid[r][5] = 1
        for r in range(9, 12): grid[r][5] = 1
        for r in range(4, 11): grid[r][23] = 1
        self.assertIsNotNone(render_nested_frame_inventory(grid)[0])
        self.assertEqual(guarded_render(grid)[1]['failure'], 'external_axis_tie_or_source_disagrees')

    def test_重なり区間は入力順でなく連結群(self):
        items = [{'id': i, 'bbox': (a, 0, b, 0), 'render_height': 1} for i, (a, b) in enumerate(((1, 3), (6, 8), (3, 6)))]
        expected, groups = module.old.arrange_axis(items, 'row')
        self.assertEqual(expected, {0: 0, 1: 0, 2: 0})
        self.assertEqual(len(groups), 1)
        self.assertEqual(module.old.arrange_axis(items[::-1], 'row')[0], expected)

    def test_背景同率と二から八成分の全入力契約(self):
        self.assertEqual(guarded_render([[0, 1], [1, 0]])[1]['failure'], 'background_tie')
        grid = [[0] * 25 for _ in range(25)]; 枠(grid, 1, 1, 23, 23)
        for col in range(3, 18, 2): grid[10][col] = 1
        self.assertEqual(guarded_render(grid)[1]['failure'], 'component_count_out_of_range')
        grid[10][17] = 0
        self.assertIsNotNone(guarded_render(grid)[0])

    def test_両寸法の縮小とARC格子を要求(self):
        grid = [[0] * 5 for _ in range(7)]; 枠(grid, 1, 0, 5, 4); grid[3][2] = 1
        self.assertEqual(guarded_render(grid)[1]['failure'], 'canonical_output_size_invalid')
        for bad in ([], [[0], [0, 1]], [[True]], [[10]]):
            self.assertEqual(guarded_render(bad)[1]['failure'], 'invalid_arc_grid')

    def test_全成分coverageと元parentの不一致を拒否(self):
        grid = 教材(2)['input']; original = module.old.foreground_components
        with patch.object(module.old, 'foreground_components', side_effect=lambda g, bg: original(g, bg)[:-1]):
            self.assertEqual(guarded_render(grid)[1]['failure'], 'input_component_coverage_invalid')
        original_tree = module.old.build_containment_tree
        def wrong_parent(cs):
            cs = original_tree(cs); cs[-1]['parent'] = None; return cs
        with patch.object(module.old, 'build_containment_tree', side_effect=wrong_parent):
            self.assertEqual(guarded_render(grid)[1]['failure'], 'source_parent_or_children_disagree')

    def test_元格子と元記録を別案へ置換しない(self):
        grid = 教材()['input']; output, record = render_nested_frame_inventory(grid)
        wrong = deepcopy(output); wrong[0][0] = 9
        bad_record = deepcopy(record); bad_record['component_count'] = 99
        for o, r in ((wrong, record), (output, bad_record)):
            with patch.object(module.old, 'render_nested_frame_inventory', return_value=(o, r)):
                self.assertEqual(guarded_render(grid)[1]['failure'], 'source_output_or_record_disagrees')

    def test_全教師raw適合先決と重複教師拒否(self):
        pairs = 教師(); pairs[-1]['output'][0][0] = 9
        with patch.object(module, 'guarded_render', side_effect=AssertionError('guard before raw fit')):
            self.assertFalse(包含正規化教材(pairs).適合)
        pair = 教材(); self.assertFalse(包含正規化教材([pair, pair]).適合)

    def test_native支持は四盤面でcomponentや包含対を加算しない(self):
        pairs = 教師(); view = 包含正規化教材(pairs); boundary = '包含正規化対照'
        self.assertTrue(view.適合)
        engine = HDS学習実行系(最小支持数=3)
        self.assertFalse(候補機構を学習(engine, {'train': pairs[:2]}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系(最小支持数=3)
        record = 候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertEqual(record['現在観測数'], 4); self.assertEqual(record['事前観測数'], 0)
        query = pairs[0]['output']
        self.assertEqual(出力格子(engine, 観測へ({'候補': query}, boundary), 同値必須=True)['answer'], query)
        engine.実行(観測へ({'候補': query, '出力': [[9]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': query}, boundary), 同値必須=True)['answer'])

    def test_採用後の未解決queryは全体HOLDと情報分離(self):
        task = {'train': 教師(), 'test': [{'input': 潰れる葉()}]}
        result = 課題を解く(task, [])
        record = next(r for r in result['families'] if r['境界'] == 'ARCbbox包含正規化')
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertEqual(record['現在観測数'], 4)
        self.assertIsNone(result['results'][0]['answer'])
        task['task_id'] = 'forbidden'
        with self.assertRaises(ValueError): 課題を解く(task, [])
        task.pop('task_id'); task['test'][0]['output'] = [[1]]
        with self.assertRaises(ValueError): 課題を解く(task, [])


if __name__ == '__main__':
    unittest.main()
