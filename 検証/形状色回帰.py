"""最大template・D4形状色mode・prototype範囲とnative支持を確認する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2.形状色教材 import 形状色教材, guarded_template_shape_color
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.HDS接続 import 課題を解く, HDS学習実行系, 候補機構を学習, 出力格子, 観測へ

穴群 = [({(0, 0), (0, 1), (1, 0), (1, 1)}, (2, 2), 2),
        ({(0, 0), (0, 1)}, (2, 7), 5),
        ({(0, 0), (1, 0), (1, 1)}, (5, 3), 7)]


def 教材(height=9, width=11):
    grid = [[0] * 30 for _ in range(30)]
    output = [[1] * width for _ in range(height)]
    for r in range(1, height + 1):
        for c in range(1, width + 1):
            grid[r][c] = 1
    for shape, (top, left), color in 穴群:
        for r, c in shape:
            grid[1 + top + r][1 + left + c] = 0
            output[top + r][left + c] = color
    square = 穴群[0][0]
    vertical = {(0, 0), (1, 0)}
    reflected_l = {(0, 0), (0, 1), (1, 1)}
    prototypes = [(square, 2, 1, 15), (square, 2, 1, 20), (square, 3, 1, 25), (square, 4, 6, 15),
                  (vertical, 5, 6, 20), (vertical, 5, 6, 25), (vertical, 6, 11, 15),
                  (reflected_l, 7, 11, 20), (reflected_l, 7, 11, 25), (reflected_l, 8, 16, 15)]
    for shape, color, top, left in prototypes:
        for r, c in shape:
            grid[top + r][left + c] = color
    return {'input': grid, 'output': output}


def 教師():
    return [教材(), 教材(11, 13)]


class 形状色回帰(unittest.TestCase):
    def test_異なる向きのprototypeから全patchを転写(self):
        for pair in 教師() + [教材(13, 13)]:
            out, record = guarded_template_shape_color(pair['input'])
            self.assertEqual(out, pair['output'])
            self.assertEqual(record['prototype_component_count'], 10)
            self.assertEqual(record['template_hole_shape_count'], 3)

    def test_D4と配色変更にも同じ対応(self):
        pair = 教材()
        for name in ('rot90', 'rot180', 'flip_h', 'transpose'):
            self.assertEqual(guarded_template_shape_color(transform_grid_by_name(pair['input'], name))[0], transform_grid_by_name(pair['output'], name))
        recolor = lambda g: [[9 - v for v in row] for row in g]
        self.assertEqual(guarded_template_shape_color(recolor(pair['input']))[0], recolor(pair['output']))

    def test_modeは過半数や全会一致を要求しない(self):
        pair = 教材(); out, record = guarded_template_shape_color(pair['input'])
        self.assertEqual(out, pair['output'])
        counts = record['template_hole_records'][0]['external_shape_color_counts']
        self.assertEqual(counts, {2: 2, 3: 1, 4: 1})

    def test_最多色同率と未知形は全体を保留(self):
        pair = 教材()
        for r in (6, 7):
            for c in (15, 16):
                pair['input'][r][c] = 3
        self.assertEqual(guarded_template_shape_color(pair['input'])[1]['failure'], 'unresolved_template_hole_shapes')
        pair = 教材()
        for row in pair['input']:
            for c, v in enumerate(row):
                if v in (7, 8):
                    row[c] = 0
        self.assertIsNone(guarded_template_shape_color(pair['input'])[0])

    def test_最大同率と背景同率を先着で選ばない(self):
        pair = 教材(); grid = pair['input']
        for r in range(9):
            for c in range(11):
                grid[19 + r][1 + c] = 9 if grid[1 + r][1 + c] == 1 else 0
        self.assertEqual(guarded_template_shape_color(grid)[1]['failure'], 'largest_template_size_tie')
        self.assertEqual(guarded_template_shape_color([[0, 1], [1, 0]])[1]['failure'], 'background_tie')

    def test_最大が不適格でも小templateへ再試行しない(self):
        pair = 教材(); grid = pair['input']
        for r in range(19, 29):
            for c in range(1, 15):
                grid[r][c] = 9
        self.assertEqual(guarded_template_shape_color(grid)[1]['failure'], 'template_hole_main_not_surface')
        for r in range(19, 29):
            for c in range(1, 15):
                grid[r][c] = 0
        self.assertEqual(guarded_template_shape_color(grid)[0], pair['output'])

    def test_内部prototypeを票から抜かず全体保留(self):
        pair = 教材(); pair['input'][3][3] = 9
        self.assertEqual(guarded_template_shape_color(pair['input'])[1]['failure'], 'prototype_enters_selected_template_bbox')

    def test_bbox端のpatchも元の定義通り扱う(self):
        pair = 教材()
        pair['input'][1][6] = pair['input'][1][7] = 0
        pair['output'][0][5] = pair['output'][0][6] = 5
        out, record = guarded_template_shape_color(pair['input'])
        self.assertEqual(out, pair['output']); self.assertEqual(record['template_hole_count'], 4)

    def test_元の20画素25面積3patchと全格子制限(self):
        def small(h, w, holes):
            grid = [[0] * 15 for _ in range(15)]
            for r in range(h):
                for c in range(w):
                    grid[1 + r][1 + c] = 0 if (r, c) in holes else 1
            grid[1][10] = grid[3][10] = 2; grid[5][10] = 3
            return grid
        checker = {(1, 1), (1, 3), (2, 2), (3, 1), (3, 3)}
        self.assertIsNotNone(guarded_template_shape_color(small(5, 5, checker))[0])
        for grid in (small(5, 5, checker | {(1, 2)}), small(4, 6, {(1, 1), (1, 3), (2, 2)})):
            self.assertEqual(guarded_template_shape_color(grid)[1]['failure'], 'template_hole_main_not_surface')
        pair = 教材()
        for r, c in 穴群[2][0]:
            pair['input'][1 + 5 + r][1 + 3 + c] = 1
        self.assertEqual(guarded_template_shape_color(pair['input'])[1]['failure'], 'too_few_template_holes')
        grid = [[1 if r in (0, 29) or c in (0, 29) else 0 for c in range(30)] for r in range(30)]
        self.assertEqual(guarded_template_shape_color(grid)[1]['failure'], 'template_hole_main_full_grid')
        for grid in ([], [[0] * 31], [[0, 0], [0]]):
            self.assertIsNone(guarded_template_shape_color(grid)[0])

    def test_教師反例と重複を支持に入れない(self):
        pairs = 教師(); pairs[1]['output'][0][0] = 9
        self.assertFalse(形状色教材(pairs).全教師再現)
        pair = 教材(); self.assertFalse(形状色教材([pair, deepcopy(pair)]).全教師再現)

    def test_多数のprototypeでもnative支持は二教師(self):
        pair = 教材(13, 13)
        result = 課題を解く({'train': 教師(), 'test': [{'input': pair['input']}]}, [])
        self.assertEqual(result['results'][0]['answer'], pair['output']); self.assertEqual(result['minimum_support'], 2)
        family = next(x for x in result['families'] if x['境界'] == 'ARC形状色転写')
        self.assertEqual(family['現在観測数'], 2); self.assertEqual(family['事前観測数'], 0)
        self.assertTrue(family['同値採用'])

    def test_中核既定支持3と後発反例は保留(self):
        pairs = 教師(); view = 形状色教材(pairs); boundary = '形状色対照'
        engine = HDS学習実行系()
        self.assertFalse(候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系(最小支持数=2)
        self.assertTrue(候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)['同値採用'])
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[3]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': pairs[1]['output']}, boundary), 同値必須=True)['answer'])


if __name__ == '__main__':
    unittest.main()
