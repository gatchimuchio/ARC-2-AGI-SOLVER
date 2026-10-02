"""固定形態prior・保守的role競合guard・教師palette/native支持を確認する。"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 既存穴輪郭 as source
from 接続.ARC2.穴輪郭教材 import 穴輪郭教材, guarded_hole_outline
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.HDS接続 import 課題を解く, HDS学習実行系, 候補機構を学習, 出力格子, 観測へ

方針 = (4, 1, 2, 6, 8)


def 教材(height=5, width=5):
    grid = [[4] * 25 for _ in range(22)]
    output = deepcopy(grid)
    for top, left, h, w, holed in ((2, 2, height, width, True), (12, 15, 3, 4, False)):
        for r in range(top - 1, top + h + 1):
            for c in range(left - 1, left + w + 1):
                inside = top <= r < top + h and left <= c < left + w
                if not inside:
                    output[r][c] = 2
                elif holed and top < r < top + h - 1 and left < c < left + w - 1:
                    output[r][c] = 6
                else:
                    grid[r][c] = 1
                    output[r][c] = 8 if holed else 1
    return {'input': grid, 'output': output}


def 教師():
    return [教材(5, 5), 教材(5, 7), 教材(7, 5)]


class 穴輪郭回帰(unittest.TestCase):
    def test_可変寸法の有穴物体と無穴物体を区別(self):
        for pair in 教師() + [教材(7, 9)]:
            out, record = guarded_hole_outline(pair['input'], 方針)
            self.assertEqual(out, pair['output']); self.assertEqual(record['hole_outline_holed_component_count'], 1)

    def test_回転反転と教師paletteの配色変更(self):
        pair = 教材(5, 7)
        for name in ('rot90', 'rot180', 'flip_h', 'transpose'):
            self.assertEqual(guarded_hole_outline(transform_grid_by_name(pair['input'], name), 方針)[0], transform_grid_by_name(pair['output'], name))
        mapping = {4: 3, 1: 7, 2: 0, 6: 2, 8: 5}
        recolor = lambda g: [[mapping[v] for v in row] for row in g]
        pairs = [{'input': recolor(p['input']), 'output': recolor(p['output'])} for p in 教師()]
        view = 穴輪郭教材(pairs)
        self.assertEqual(view.方針, tuple(mapping[v] for v in 方針)); self.assertEqual(view.適合方針数, 1)

    def test_開いた輪郭は穴に数えない(self):
        grid = 教材()['input']; grid[2][4] = 4
        out, record = guarded_hole_outline(grid, 方針)
        self.assertEqual(record['hole_outline_holed_component_count'], 0)
        self.assertNotIn(6, {v for row in out for v in row}); self.assertNotIn(8, {v for row in out for v in row})

    def test_複数穴でも元の有穴分岐を使う(self):
        pair = 教材(5, 9)
        for r in range(3, 6):
            pair['input'][r][6] = 1; pair['output'][r][6] = 8
        out, record = guarded_hole_outline(pair['input'], 方針)
        self.assertEqual(out, pair['output'])
        self.assertEqual(record['component_records'][0]['hole_count'], 2)

    def test_入れ子のrole競合を保留し診断と格子を区別(self):
        grid = [[4] * 11 for _ in range(11)]
        for r in range(1, 10):
            for c in range(1, 10):
                if r in (1, 9) or c in (1, 9):
                    grid[r][c] = 1
        grid[5][5] = 1
        forward, first = source.render_binary_object_hole_outline_renderer(grid, *方針)
        original = source.color_components
        with patch.object(source, 'color_components', lambda *args, **kwargs: list(reversed(original(*args, **kwargs)))):
            reverse, last = source.render_binary_object_hole_outline_renderer(grid, *方針)
        self.assertEqual(forward, reverse)
        self.assertEqual((first['hole_outline_border_cell_count'], last['hole_outline_border_cell_count']), (40, 48))
        self.assertEqual(sum(v == 2 for row in forward for v in row), 40)
        self.assertEqual(guarded_hole_outline(grid, 方針)[1]['failure'], 'conflicting_component_role_proposals')

    def test_同色の外輪郭の重なりは許可(self):
        grid = [[4] * 7 for _ in range(7)]; grid[2][2] = grid[4][4] = 1
        out, _ = guarded_hole_outline(grid, 方針)
        self.assertEqual(out[3][3], 2); self.assertEqual(sum(v == 2 for row in out for v in row), 15)

    def test_背景役割は最多色で上書きしない(self):
        grid = [[4] * 20 for _ in range(20)]
        for r in range(1, 19):
            for c in range(1, 19):
                grid[r][c] = 1
        grid[9][9] = 4
        self.assertEqual(Counter(v for row in grid for v in row).most_common(1)[0][0], 1)
        out, _ = guarded_hole_outline(grid, 方針)
        self.assertEqual(out[9][9], 6); self.assertEqual(sum(v == 8 for row in out for v in row), 323)

    def test_画像端の外輪郭は格子内に限定(self):
        grid = [[4] * 4 for _ in range(4)]; grid[0][0] = 1
        out, _ = guarded_hole_outline(grid, 方針)
        self.assertEqual(sum(v == 2 for row in out for v in row), 3)
        self.assertEqual(out[0][0], 1)

    def test_未知入力色と不正役割と不正格子(self):
        grid = 教材()['input']; grid[0][0] = 9
        self.assertIsNone(guarded_hole_outline(grid, 方針)[0])
        self.assertIsNone(guarded_hole_outline(教材()['input'], (4, 1, 2, 2, 8))[0])
        for g in ([], [[4] * 31], [[4, 4], [4]]):
            self.assertIsNone(guarded_hole_outline(g, 方針)[0])

    def test_教師反例と重複を支持に入れない(self):
        pairs = 教師(); pairs[1]['output'][0][0] = 9
        self.assertIsNone(穴輪郭教材(pairs).方針)
        pair = 教材(); self.assertIsNone(穴輪郭教材([pair, deepcopy(pair)]).方針)

    def test_三教師だけをnative支持として観測(self):
        pair = 教材(7, 9)
        result = 課題を解く({'train': 教師(), 'test': [{'input': pair['input']}]}, [])
        self.assertEqual(result['results'][0]['answer'], pair['output'])
        family = next(x for x in result['families'] if x['境界'] == 'ARC穴輪郭')
        self.assertEqual(family['現在観測数'], 3); self.assertEqual(family['事前観測数'], 0)
        self.assertTrue(family['同値採用']); self.assertEqual(result['hole_outline']['適合方針数'], 1)

    def test_native支持不足と後発反例は保留(self):
        pairs = 教師(); view = 穴輪郭教材(pairs); boundary = '穴輪郭対照'
        engine = HDS学習実行系()
        self.assertFalse(候補機構を学習(engine, {'train': pairs[:2]}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系()
        self.assertTrue(候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)['同値採用'])
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[3]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': pairs[1]['output']}, boundary), 同値必須=True)['answer'])


if __name__ == '__main__':
    unittest.main()
