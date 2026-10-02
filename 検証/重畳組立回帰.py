"""最大overlap prior内の一意性と背景を含む同時crop整合を検証する。"""
from copy import deepcopy
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 重畳組立教材 as module
from 接続.ARC2.重畳組立教材 import guarded_overlap_mosaic, 重畳組立教材
from 接続.ARC2.既存重畳組立 import overlap_mosaic_assembly
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.HDS接続 import 課題を解く, HDS学習実行系, 候補機構を学習, 出力格子, 観測へ


def 散布(parts, order=None):
    grid = [[0] * 30 for _ in range(30)]
    if order is None:
        order = list(range(len(parts)))
    for top, index in zip((1, 10, 19), order):
        for r, row in enumerate(parts[index]):
            for c, value in enumerate(row):
                grid[top + r][1 + c] = value
    return grid


def 教材(seed=11):
    generator = random.Random(seed)
    canvas = [[generator.randint(1, 8) for _ in range(12)] for _ in range(5)]
    parts = [[row[:6] for row in canvas], [row[4:9] for row in canvas], [row[7:] for row in canvas]]
    return {'input': 散布(parts), 'output': canvas}, parts


def 教師():
    return [教材(seed)[0] for seed in (11, 23)]


class 重畳組立回帰(unittest.TestCase):
    def test_全三断片を最大overlapで再構成(self):
        pair, _ = 教材()
        output, record = guarded_overlap_mosaic(pair['input'])
        self.assertEqual(output, pair['output'])
        certificate = record['maximum_tree_certificate']
        self.assertEqual(certificate['fragment_count'], 3)
        self.assertEqual(certificate['selected_offset_counts'], [1, 1])
        self.assertEqual([edge['overlap_area'] for edge in record['selected_edges']], [10, 10])

    def test_D4と配色でも同じ組立(self):
        pair, _ = 教材()
        for transform in ('rot90', 'rot180', 'rot270', 'flip_h', 'transpose'):
            self.assertEqual(guarded_overlap_mosaic(transform_grid_by_name(pair['input'], transform))[0],
                             transform_grid_by_name(pair['output'], transform))
        recolor = lambda g: [[9 - v for v in row] for row in g]
        self.assertEqual(guarded_overlap_mosaic(recolor(pair['input']))[0], recolor(pair['output']))

    def test_入力断片の配置順に依存しない(self):
        pair, parts = 教材()
        for order in ([2, 0, 1], [1, 2, 0]):
            self.assertEqual(guarded_overlap_mosaic(散布(parts, order))[0], pair['output'])

    def test_採用edgeの最大shift同率を先着で選ばない(self):
        grid = 散布([[[2] * 6 for _ in range(5)], [[2] * 3 for _ in range(3)]])
        self.assertIsNotNone(overlap_mosaic_assembly(grid)[0])
        self.assertEqual(guarded_overlap_mosaic(grid)[1]['failure'], 'selected_edge_offset_not_unique')

    def test_未採用edgeがpath最弱と同率なら保留(self):
        pair, _ = 教材(); part = pair['output'][:3]
        grid = 散布([part, part, part])
        self.assertIsNotNone(overlap_mosaic_assembly(grid)[0])
        self.assertEqual(guarded_overlap_mosaic(grid)[1]['failure'], 'unresolved_maximum_tree')

    def test_foreign前景をbbox断片へ二重取り込みしない(self):
        grid = [[0] * 12 for _ in range(12)]
        for r in range(1, 8):
            for c in range(1, 8):
                if r in {1, 7} or c in {1, 7}:
                    grid[r][c] = 2
        grid[4][4] = 3
        self.assertEqual(guarded_overlap_mosaic(grid)[1]['failure'], 'foreign_foreground_in_fragment_bbox')

    def test_元の逐次paintが通す背景不一致も保留(self):
        parts = [[[1, 0, 2, 3], [1, 1, 2, 3]], [[2, 3], [2, 3]], [[1, 9, 2, 3], [1, 1, 2, 3]]]
        grid = [[0] * 10 for _ in range(10)]
        for top, part in zip((1, 4, 7), parts):
            for r, row in enumerate(part):
                grid[top + r][1:1 + len(row)] = row
        self.assertEqual(overlap_mosaic_assembly(grid)[0], parts[2])
        self.assertEqual(guarded_overlap_mosaic(grid)[1]['failure'], 'simultaneous_crop_conflict')

    def test_出力ARC範囲を超える組立を保留(self):
        generator = random.Random(17)
        canvas = [[generator.randint(1, 8) for _ in range(40)] for _ in range(5)]
        grid = 散布([[row[:18] for row in canvas], [row[12:30] for row in canvas], [row[24:] for row in canvas]])
        raw, _ = overlap_mosaic_assembly(grid)
        self.assertEqual(raw, canvas)
        self.assertEqual(guarded_overlap_mosaic(grid)[1]['failure'], 'output_outside_arc_bounds')

    def test_元rendererと異なる格子を返さない(self):
        pair, _ = 教材(); output, record = overlap_mosaic_assembly(pair['input'])
        bad = deepcopy(output); bad[0][0] = 9
        with patch.object(module.old, 'overlap_mosaic_assembly', return_value=(bad, record)):
            self.assertEqual(guarded_overlap_mosaic(pair['input'])[1]['failure'], 'source_output_disagrees')

    def test_無効格子と背景同率と断片不足(self):
        for grid in ([], [[0], [0, 1]], [[True]], [[10]], [[0] * 31]):
            self.assertEqual(guarded_overlap_mosaic(grid)[1]['failure'], 'invalid_grid')
        self.assertEqual(guarded_overlap_mosaic([[0, 1], [1, 0]])[1]['failure'], 'background_tie')
        self.assertEqual(guarded_overlap_mosaic([[0] * 5 for _ in range(5)])[1]['failure'], 'too_few_fragments')

    def test_教師反例と重複を採用しない(self):
        pairs = 教師(); pairs[-1]['output'] = [[9]]
        self.assertFalse(重畳組立教材(pairs).全教師再現)
        pair, _ = 教材()
        self.assertFalse(重畳組立教材([pair, pair]).全教師再現)

    def test_native支持は二盤面で中核既定3と隔離を保持(self):
        pairs = 教師(); query, _ = 教材(31); view = 重畳組立教材(pairs)
        self.assertTrue(view.全教師再現)
        result = 課題を解く({'train': pairs, 'test': [{'input': query['input']}]}, [])
        self.assertEqual(result['results'][0]['answer'], query['output'])
        record = next(r for r in result['families'] if r['境界'] == 'ARC重畳組立')
        self.assertEqual(record['現在観測数'], 2); self.assertEqual(record['事前観測数'], 0)
        self.assertTrue(record['同値採用']); self.assertEqual(result['minimum_support'], 2)
        boundary = '重畳対照'; engine = HDS学習実行系()
        self.assertFalse(候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系(最小支持数=2)
        self.assertTrue(候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)['同値採用'])
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[9]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'])

    def test_採用済み機構の未解決queryは全体保留(self):
        grid = 散布([[[2] * 6 for _ in range(5)], [[2] * 3 for _ in range(3)]])
        result = 課題を解く({'train': 教師(), 'test': [{'input': grid}]}, [])
        self.assertIsNone(result['results'][0]['answer'])
        self.assertTrue(any('ARC重畳組立' in s for s in result['results'][0]['reasons']))


if __name__ == '__main__':
    unittest.main()
