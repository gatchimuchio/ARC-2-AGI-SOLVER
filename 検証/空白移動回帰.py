"""空白矩形の全配置到達、一意最遠、色fitと既存native支持を検証する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 空白移動教材 as module
from 接続.ARC2.空白移動教材 import guarded_render, 空白移動教材
from 接続.ARC2.既存空白移動 import render_farthest_blank_rectangle_relocator
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 出力格子, 観測へ, 課題を解く


def 通路(height=1, width=1, distance=4):
    grid = [[3] * (width + distance + 2) for _ in range(height + 2)]
    for r in range(1, height + 1):
        for c in range(1, width + distance + 1):
            grid[r][c] = 1
        for c in range(1 + distance, 1 + distance + width):
            grid[r][c] = 2
        for c in range(1, 1 + width):
            grid[r][c] = 0
    output = deepcopy(grid)
    for r in range(1, height + 1):
        output[r][1:1 + width] = [1] * width
        output[r][1 + distance:1 + distance + width] = [0] * width
    return {'input': grid, 'output': output}


def 教師():
    return [通路(1, 1, 4), 通路(2, 2, 5), 通路(1, 2, 6), 通路(2, 1, 4)]


class 空白移動回帰(unittest.TestCase):
    def test_固定blankと全配置グラフの最遠(self):
        pair = 通路(2, 2, 5)
        output, rec = guarded_render(pair['input'], 1, 2)
        self.assertEqual(output, pair['output'])
        self.assertEqual(rec['component_size'], 6)
        self.assertEqual(rec['farthest_distance'], 5)
        self.assertEqual(rec['rectangle_shape'], [2, 2])

    def test_D4と非0役割色置換(self):
        pair = 通路(2, 3, 5)
        for transform in ('identity', 'rot90', 'rot180', 'rot270', 'flip_h', 'flip_v', 'transpose', 'anti_transpose'):
            src = transform_grid_by_name(pair['input'], transform)
            dst = transform_grid_by_name(pair['output'], transform)
            self.assertEqual(guarded_render(src, 1, 2)[0], dst)
        palette = {0: 0, 1: 7, 2: 9, 3: 4}
        recolor = lambda g: [[palette[v] for v in row] for row in g]
        self.assertEqual(guarded_render(recolor(pair['input']), 7, 9)[0], recolor(pair['output']))

    def test_矩形寸法と距離は入力から(self):
        for h, w, distance in ((1, 1, 2), (3, 2, 7), (4, 5, 9)):
            pair = 通路(h, w, distance)
            output, rec = guarded_render(pair['input'], 1, 2)
            self.assertEqual(output, pair['output'])
            self.assertEqual(rec['farthest_distance'], distance)
            self.assertEqual(sum(v == 0 for row in output for v in row), h * w)

    def test_markerは到達先ではなく通行可能色(self):
        grid = [[3] * 7 for _ in range(5)]
        grid[1] = [3, 0, 1, 1, 1, 1, 3]
        grid[3][3] = 2
        output, rec = guarded_render(grid, 1, 2)
        self.assertEqual(rec['target_bbox'], [1, 5, 1, 5])
        self.assertEqual(output[3][3], 2)
        self.assertEqual(output[1], [3, 1, 1, 1, 1, 0, 3])

    def test_追加の非矩形0領域を黙殺しない(self):
        grid = [[3] * 7 for _ in range(6)]
        grid[1] = [3, 0, 1, 1, 1, 2, 3]
        grid[3][1] = grid[4][1] = grid[4][2] = 0
        self.assertIsNotNone(render_farthest_blank_rectangle_relocator(grid, 1, 2)[0])
        self.assertEqual(guarded_render(grid, 1, 2)[1]['failure'], 'all_zero_cells_must_form_one_rectangle')
        grid[4][2] = 3
        self.assertIsNone(guarded_render(grid, 1, 2)[0])

    def test_最遠同率と移動不能は保留(self):
        tie = [[3] * 7, [3, 2, 1, 0, 1, 2, 3], [3] * 7]
        self.assertEqual(guarded_render(tie, 1, 2)[1]['failure'], 'ambiguous_farthest_reachable_position')
        self.assertEqual(guarded_render([[3] * 3, [3, 0, 3], [3] * 3], 1, 2)[1]['failure'], 'no_reachable_relocation_position')

    def test_元と先が重なってもblank面積を保存(self):
        self.assertEqual(guarded_render([[0, 0, 1]], 1, 2)[0], [[1, 0, 0]])

    def test_ARC範囲と役割と固定0を検証(self):
        for grid in ([], [[0], [0, 1]], [[True]], [[10]], [[0] * 31]):
            self.assertEqual(guarded_render(grid, 1, 2)[1]['failure'], 'invalid_arc_grid')
        for fill, marker in ((0, 2), (1, 1), (1, 10), (True, 2)):
            self.assertEqual(guarded_render([[0, 1]], fill, marker)[1]['failure'], 'invalid_distinct_nonzero_roles')
        self.assertIsNone(guarded_render([[4, 1, 2]], 1, 2)[0])

    def test_元renderer以外の答えを代わりに生成しない(self):
        pair = 通路()
        output, rec = render_farthest_blank_rectangle_relocator(pair['input'], 1, 2)
        bad = deepcopy(output); bad[0][0] = 8
        with patch.object(module, 'render_farthest_blank_rectangle_relocator', return_value=(bad, rec)):
            self.assertEqual(guarded_render(pair['input'], 1, 2)[1]['failure'], 'source_output_or_blank_area_mismatch')

    def test_raw複数色fitを後段guardで選別しない(self):
        pair = 通路()
        with patch.object(module.old, 'marker_color_candidates', return_value=[2, 4]), \
                patch.object(module.old, 'render_farthest_blank_rectangle_relocator', return_value=(pair['output'], {})), \
                patch.object(module, 'guarded_render') as guard:
            view = 空白移動教材([pair])
            self.assertEqual(view.生適合数, 2)
            self.assertIsNone(view.役割)
            guard.assert_not_called()

    def test_教師反例と重複を採用しない(self):
        pairs = 教師(); pairs[-1]['output'][0][0] = 9
        self.assertIsNone(空白移動教材(pairs).役割)
        pair = 通路()
        self.assertIsNone(空白移動教材([pair, pair]).役割)

    def test_native支持は4盤面で経路長を加算しない(self):
        pairs = 教師(); view = 空白移動教材(pairs)
        self.assertEqual(view.役割, (1, 2))
        engine = HDS学習実行系(); boundary = '空白移動対照'
        rec = 候補機構を学習(engine, {'train': pairs[:2]}, [], boundary, view.候補)
        self.assertFalse(rec['同値採用'])
        engine = HDS学習実行系()
        rec = 候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)
        self.assertTrue(rec['同値採用']); self.assertEqual(rec['現在観測数'], 4)
        self.assertEqual(rec['事前観測数'], 0)
        query = 通路(3, 2, 8)
        self.assertEqual(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'], query['output'])
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[9]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'])

    def test_採用済み機構のquery不確定は全体保留(self):
        tie = [[3] * 7, [3, 2, 1, 0, 1, 2, 3], [3] * 7]
        result = 課題を解く({'train': 教師(), 'test': [{'input': tie}]}, [])
        family = next(r for r in result['families'] if r['境界'] == 'ARC空白矩形移動')
        self.assertTrue(family['採用可']); self.assertTrue(family['同値採用'])
        self.assertIsNone(result['results'][0]['answer'])


if __name__ == '__main__':
    unittest.main()
