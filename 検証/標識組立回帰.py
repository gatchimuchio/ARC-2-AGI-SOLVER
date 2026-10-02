"""全attachment候補の合意、target保存、四盤面支持を検証する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 標識組立教材 as module
from 接続.ARC2.標識組立教材 import guarded_render, 標識組立教材
from 接続.ARC2.既存標識組立 import marker_guided_assembly_candidates, marker_guided_foreground_component_assembly
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 出力格子, 観測へ, 課題を解く

役割 = {'marker': 7, 'target': 4, 'background': 1}


def 教材(width=2, lower=2, upper=3):
    grid = [[1] * 28 for _ in range(24)]
    grid[8][2] = grid[8][16] = 7
    for r in range(9, 9 + lower):
        for c in range(2, 2 + width):
            grid[r][c] = 4
    for r in range(8 - upper, 8):
        for c in range(16, 17 + width):
            grid[r][c] = 4
    output = [[4] * (width + 1) for _ in range(upper)] + [[4] * width + [1] for _ in range(lower)]
    return {'input': grid, 'output': output}


def 教師():
    return [教材(), 教材(3, 3, 1), 教材(4, 2, 2), 教材(5, 1, 2)]


def 軸同率():
    grid = [[1] * 8 for _ in range(7)]
    for r, c in ((1, 2), (5, 5)):
        grid[r][c] = 7
    for r, c in ((2, 2), (2, 1), (4, 5), (4, 6)):
        grid[r][c] = 4
    return grid


class 標識組立回帰(unittest.TestCase):
    def test_両marker順序を保持して全targetを一度だけ使う(self):
        pair = 教材(); output, record = guarded_render(pair['input'], 役割)
        self.assertEqual(output, pair['output'])
        cert = record['certificate']
        self.assertEqual(cert['raw_candidates'], 2); self.assertEqual(cert['distinct_raw_grids'], 1)
        self.assertEqual(cert['target_components'], 2)
        self.assertEqual(cert['target_pixels'], sum(v == 4 for row in output for v in row))
        self.assertEqual({r['source_marker_index'] for r in cert['all_candidate_records']}, {0, 1})

    def test_寸法配色と左右上下反転(self):
        for pair in 教師():
            for transform in (lambda g: g, lambda g: [row[::-1] for row in g], lambda g: g[::-1]):
                self.assertEqual(guarded_render(transform(pair['input']), 役割)[0], transform(pair['output']))
        mapping = {1: 9, 4: 0, 7: 3}
        convert = lambda g: [[mapping[v] for v in row] for row in g]
        roles = {k: mapping[v] for k, v in 役割.items()}
        self.assertEqual(guarded_render(convert(pair['input']), roles)[0], convert(pair['output']))

    def test_背景を頻度で選び直さない(self):
        grid = [list(map(int, row)) for row in ['444', '444', '171', '111', '171', '441', '444']]
        self.assertGreater(sum(v == 4 for row in grid for v in row), sum(v == 1 for row in grid for v in row))
        expected = [list(map(int, row)) for row in ['444', '444', '441', '444']]
        self.assertEqual(guarded_render(grid, 役割)[0], expected)
        self.assertEqual(標識組立教材(教師()).役割, 役割)

    def test_同じ格子でも優勢軸同率はHOLD(self):
        candidates = marker_guided_assembly_candidates(軸同率(), 役割)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]['output'], candidates[1]['output'])
        self.assertEqual(guarded_render(軸同率(), 役割)[1]['failure'], 'dominant_translation_axis_tie')

    def test_同サイズでも異形markerを拒否(self):
        grid = [list(map(int, row)) for row in ['114111144','477111141','144141111','414111114','411111711','111411711','114111111']]
        self.assertIsNotNone(marker_guided_foreground_component_assembly(grid, 役割)[0])
        self.assertEqual(guarded_render(grid, 役割)[1]['failure'], 'marker_shapes_differ')

    def test_異なる候補格子を面積順位で選ばない(self):
        grid = [list(map(int, row)) for row in ['114141144','117111141','111111114','111111111','111111111','111414711','114111114']]
        self.assertIsNotNone(marker_guided_foreground_component_assembly(grid, 役割)[0])
        self.assertEqual(guarded_render(grid, 役割)[1]['failure'], 'raw_candidate_grids_disagree')

    def test_一候補失敗でも残りを出さない(self):
        grid = 教材()['input']; candidates = marker_guided_assembly_candidates(grid, 役割)
        candidates[-1]['record']['fixed_component_indices'] = []
        with patch.object(module.old, 'marker_guided_assembly_candidates', return_value=candidates):
            self.assertEqual(guarded_render(grid, 役割)[1]['failure'], 'target_partition_incomplete_or_overlapping')

    def test_全成分coverage欠落とcandidate格子不一致を拒否(self):
        grid = 教材()['input']; original = module.old.same_color_components
        def incomplete(g, color):
            result = original(g, color)
            if color == 4:
                result[0]['cells'].remove(min(result[0]['cells']))
            return result
        with patch.object(module.old, 'same_color_components', side_effect=incomplete):
            self.assertEqual(guarded_render(grid, 役割)[1]['failure'], 'target_coverage_incomplete_or_overlapping')
        candidates = marker_guided_assembly_candidates(grid, 役割); candidates[0]['output'][0][0] = 1
        with patch.object(module.old, 'marker_guided_assembly_candidates', return_value=candidates):
            self.assertEqual(guarded_render(grid, 役割)[1]['failure'], 'raw_candidate_render_disagrees')

    def test_元格子不一致を証明側の格子に置換しない(self):
        grid = 教材()['input']; output, records = marker_guided_foreground_component_assembly(grid, 役割)
        output[0][0] = 1
        with patch.object(module.old, 'marker_guided_foreground_component_assembly', return_value=(output, records)):
            self.assertEqual(guarded_render(grid, 役割)[1]['failure'], 'source_output_disagrees')

    def test_入力内に収まる部品でも組立出力30超過はHOLD(self):
        grid = [[1] * 30 for _ in range(30)]; grid[0][1] = grid[29][25] = 7
        for r in range(1, 21): grid[r][1] = 4
        for r in range(9, 29): grid[r][25] = 4
        self.assertEqual(len(marker_guided_foreground_component_assembly(grid, 役割)[0]), 40)
        self.assertEqual(guarded_render(grid, 役割)[1]['failure'], 'raw_candidate_out_of_arc_bounds')

    def test_未知色不正役割格子と候補なしはHOLD(self):
        grid = 教材()['input']; grid[0][0] = 9
        self.assertEqual(guarded_render(grid, 役割)[1]['failure'], 'unknown_input_color')
        self.assertEqual(guarded_render(教材()['input'], {'marker': 7, 'target': 4, 'background': 4})[1]['failure'], 'invalid_roles')
        for grid in ([], [[0], [0, 1]], [[True]], [[10]], [[0] * 31]):
            self.assertEqual(guarded_render(grid, 役割)[1]['failure'], 'invalid_arc_grid')
        grid = 教材()['input']; grid[8][2] = grid[8][16] = 1; grid[0][0] = grid[0][27] = 7
        self.assertIsNone(guarded_render(grid, 役割)[0])

    def test_元全教師再現をguardより先決し矛盾重複を拒否(self):
        pairs = 教師(); pairs[-1]['output'][0][0] = 1
        with patch.object(module, 'guarded_render', side_effect=AssertionError('guard before raw fit')):
            self.assertIsNone(標識組立教材(pairs).役割)
        pair = 教材(); self.assertIsNone(標識組立教材([pair, pair]).役割)

    def test_native支持は四盤面でraw候補や成分数を加算しない(self):
        pairs = 教師(); view = 標識組立教材(pairs); boundary = '標識組立対照'
        self.assertEqual(view.役割, 役割)
        self.assertFalse(候補機構を学習(HDS学習実行系(), {'train': pairs[:2]}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系()
        record = 候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertEqual(record['現在観測数'], 4); self.assertEqual(record['事前観測数'], 0)
        query = 教材(6, 2, 4)
        self.assertEqual(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'], query['output'])
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[9]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'])

    def test_採用後の軸同率queryは全体HOLDと情報分離(self):
        task = {'train': 教師(), 'test': [{'input': 軸同率()}]}
        result = 課題を解く(task, [])
        record = next(r for r in result['families'] if r['境界'] == 'ARC標識誘導組立')
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertEqual(record['現在観測数'], 4)
        self.assertIsNone(result['results'][0]['answer'])
        task['task_id'] = 'forbidden'
        with self.assertRaises(ValueError): 課題を解く(task, [])
        task.pop('task_id'); task['test'][0]['output'] = [[1]]
        with self.assertRaises(ValueError): 課題を解く(task, [])


if __name__ == '__main__':
    unittest.main()
