"""最大倍率・固定anchor・全motif同時置換と二盤面支持を検証する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 倍率置換教材 as module
from 接続.ARC2.倍率置換教材 import guarded_render, 倍率置換教材
from 接続.ARC2.既存倍率置換 import render_motif_pair_scaled_anchor_swap, compress_pattern, anchor_offset
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 出力格子, 観測へ, 課題を解く

A = ((1, 1, 1), (None, 2, None))
B = ((None, 2, None), (3, 3, 3))


def 配置(items, shape=(24, 28)):
    grid = [[0] * shape[1] for _ in range(shape[0])]
    for pattern, scale, top, left in items:
        for r, row in enumerate(pattern):
            for c, value in enumerate(row):
                if value is None:
                    continue
                for dr in range(scale):
                    for dc in range(scale):
                        grid[top + r * scale + dr][left + c * scale + dc] = value
    return grid


def 教材(variant=0):
    if variant == 0:
        src = [(A, 1, 2, 2), (B, 2, 10, 10)]
        dst = [(B, 1, 3, 2), (A, 2, 8, 10)]
    else:
        src = [(A, 2, 1, 2), (B, 1, 12, 16), (A, 1, 15, 3)]
        dst = [(B, 2, 3, 2), (A, 1, 11, 16), (B, 1, 16, 3)]
    return {'input': 配置(src), 'output': 配置(dst)}


def 教師():
    return [教材(), 教材(1)]


def 色同率():
    return 配置([(((1, 2),), 1, 2, 2), (((2, 1),), 1, 7, 7)])


class 倍率置換回帰(unittest.TestCase):
    def test_全component置換とanchor位置倍率の保持(self):
        for pair in 教師():
            output, record = guarded_render(pair['input'])
            self.assertEqual(output, pair['output'])
            self.assertEqual(record['certificate']['components'], len(record['source_record']['placements']))
        self.assertEqual(guarded_render(教材()['input'])[1]['certificate']['valid_scales'], [[1], [1, 2]])

    def test_教師より大きい倍率と非固定配色(self):
        grid = 配置([(A, 3, 1, 1), (B, 1, 18, 20)])
        expected = 配置([(B, 3, 4, 1), (A, 1, 17, 20)])
        self.assertEqual(guarded_render(grid)[0], expected)
        convert = lambda g: [[{0: 8, 1: 4, 2: 9, 3: 6}[v] for v in row] for row in g]
        self.assertEqual(guarded_render(convert(grid))[0], convert(expected))

    def test_最大exact_blockを先決し全scale合意にはしない(self):
        pattern = ((2, 2, 1, 1), (2, 2, 1, 1), (3, 3, None, None), (3, 3, None, None))
        self.assertEqual(compress_pattern(pattern), (2, ((2, 1), (3, None))))
        original = module.old.compress_pattern
        def smaller(p): return (1, p) if len(p) > 2 else original(p)
        with patch.object(module.old, 'compress_pattern', side_effect=smaller):
            self.assertEqual(guarded_render(教材()['input'])[1]['failure'], 'source_maximum_scale_disagrees')

    def test_共通色countは異なる二primitiveだけを各一回数える(self):
        a, b = ((2, 1, 1, 1, 1),), ((2, 2, 2, 2, 1, 1),)
        grid = 配置([(a, 1, 2, 2), (b, 1, 6, 2), (b, 1, 10, 2), (b, 1, 14, 2)])
        output, record = guarded_render(grid)
        self.assertIsNotNone(output)
        self.assertEqual(record['certificate']['anchor_color_counts'], {1: 6, 2: 5})
        self.assertEqual(record['source_record']['anchor_color'], 2)
        self.assertGreater(sum(v == 2 for row in grid for v in row), sum(v == 1 for row in grid for v in row))

    def test_同色の最上左anchorは固定規約(self):
        a, b = ((2, 2, 1), (1, 1, 1)), ((2, 1, 1), (None, 3, None))
        grid = 配置([(a, 1, 2, 2), (b, 1, 10, 10)])
        expected = 配置([(b, 1, 2, 2), (a, 1, 10, 10)])
        self.assertEqual(anchor_offset(a, 2, 3), (0, 0))
        self.assertEqual(guarded_render(grid)[0], expected)

    def test_共通色同率を数値色順で解決しない(self):
        self.assertIsNotNone(render_motif_pair_scaled_anchor_swap(色同率())[0])
        self.assertEqual(guarded_render(色同率())[1]['failure'], 'anchor_color_count_tie')

    def test_全component置換は全画素数保存ではない(self):
        a, b = ((2, 1, 1),), ((2, 1, 1), (3, None, None))
        grid = 配置([(a, 1, 2, 2), (a, 2, 7, 3), (b, 1, 14, 16)])
        output, record = guarded_render(grid)
        self.assertIsNotNone(output)
        self.assertEqual((record['certificate']['foreground_before'], record['certificate']['foreground_after']), (19, 23))
        self.assertEqual(set(sum(output, [])), set(sum(grid, [])))

    def test_同色重なりは元どおりunionで一度だけ塗る(self):
        grid = 配置([(((1, 1, 2),), 1, 5, 3), (((2, 1, 1),), 1, 5, 9)])
        output, record = guarded_render(grid)
        self.assertEqual(output[5][5:10], [2, 1, 1, 1, 2])
        cert = record['certificate']
        self.assertEqual((cert['foreground_before'], cert['foreground_after'], cert['same_color_overlapping_proposals']), (6, 5, 1))

    def test_異色衝突と範囲外を部分置換で救済しない(self):
        conflict = 配置([(((3, 3, 1, 1, 2),), 1, 5, 1), (((2, 1, 1, 3, 3),), 1, 5, 10)])
        self.assertEqual(guarded_render(conflict)[1]['failure'], 'different_color_proposals_overlap')
        outside = 配置([(((2, 1, 1),), 1, 2, 0), (((1, 1, 2),), 1, 10, 10)])
        self.assertEqual(guarded_render(outside)[1]['failure'], 'placement_out_of_bounds')

    def test_背景同率追加第三型と不正格子を拒否(self):
        self.assertEqual(guarded_render([[0, 1], [1, 0]])[1]['failure'], 'background_tie')
        grid = 教材()['input']; grid[22][26] = 5
        self.assertEqual(guarded_render(grid)[1]['failure'], 'primitive_group_count_not_two')
        for grid in ([], [[0], [0, 1]], [[True]], [[10]], [[0] * 31]):
            self.assertEqual(guarded_render(grid)[1]['failure'], 'invalid_arc_grid')

    def test_coverage欠落と逆展開不一致を拒否(self):
        grid = 教材()['input']; original = module.old.extract_motif_components
        with patch.object(module.old, 'extract_motif_components', side_effect=lambda g: original(g) + original(g)[:1]):
            self.assertEqual(guarded_render(grid)[1]['failure'], 'component_coverage_invalid')
        original_compress = module.old.compress_pattern
        def broken(p):
            s, q = original_compress(p); rows = [list(row) for row in q]; rows[0][0] = 9
            return s, tuple(map(tuple, rows))
        with patch.object(module.old, 'compress_pattern', side_effect=broken):
            self.assertEqual(guarded_render(grid)[1]['failure'], 'primitive_inverse_expansion_disagrees')

    def test_元格子と元記録不一致を代替しない(self):
        grid = 教材()['input']; output, rec = render_motif_pair_scaled_anchor_swap(grid)
        wrong = deepcopy(output); wrong[0][0] = 9
        bad_rec = deepcopy(rec); bad_rec['anchor_color'] = 1
        for o, r in ((wrong, rec), (output, bad_rec)):
            with patch.object(module.old, 'render_motif_pair_scaled_anchor_swap', return_value=(o, r)):
                self.assertEqual(guarded_render(grid)[1]['failure'], 'source_output_or_record_disagrees')

    def test_元全教師再現先決と矛盾重複拒否(self):
        pairs = 教師(); pairs[-1]['output'][0][0] = 9
        with patch.object(module, 'guarded_render', side_effect=AssertionError('guard before raw fit')):
            self.assertFalse(倍率置換教材(pairs).適合)
        pair = 教材(); self.assertFalse(倍率置換教材([pair, pair]).適合)

    def test_native支持は二盤面でmotifや倍率を加算しない(self):
        pairs = 教師(); view = 倍率置換教材(pairs); boundary = '倍率置換対照'
        self.assertTrue(view.適合)
        engine = HDS学習実行系(最小支持数=2)
        self.assertFalse(候補機構を学習(engine, {'train': pairs[:1]}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系(最小支持数=2)
        record = 候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertEqual(record['現在観測数'], 2); self.assertEqual(record['事前観測数'], 0)
        query = 配置([(B, 3, 4, 1), (A, 1, 17, 20)])
        self.assertEqual(出力格子(engine, 観測へ({'候補': query}, boundary), 同値必須=True)['answer'], query)
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[9]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': query}, boundary), 同値必須=True)['answer'])

    def test_採用後の役割同率queryは全体HOLDと情報分離(self):
        task = {'train': 教師(), 'test': [{'input': 色同率()}]}
        result = 課題を解く(task, [])
        record = next(r for r in result['families'] if r['境界'] == 'ARC倍率motif相互置換')
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertEqual(record['現在観測数'], 2)
        self.assertIsNone(result['results'][0]['answer'])
        task['task_id'] = 'forbidden'
        with self.assertRaises(ValueError): 課題を解く(task, [])
        task.pop('task_id'); task['test'][0]['output'] = [[1]]
        with self.assertRaises(ValueError): 課題を解く(task, [])


if __name__ == '__main__':
    unittest.main()
