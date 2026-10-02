"""距離層周期prior、全領域保存と三盤面支持を検証する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 距離層教材 as module
from 接続.ARC2.距離層教材 import guarded_render, 距離層教材
from 接続.ARC2.既存距離層 import seeded_separator_layer_fill, boundary_layers_8, detect_separator
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 出力格子, 観測へ, 課題を解く


def 教材(height=12, side=6, left=(3, 4), right=(5,)):
    grid = [[1] * (2 * side + 1) for _ in range(height)]
    for row in grid:
        row[side] = 2
    output = deepcopy(grid)
    for start, sequence in ((0, left), (side + 1, right)):
        if sequence is None:
            continue
        for layer, color in enumerate(sequence):
            if color is not None:
                grid[layer][start + layer] = color
        for r in range(height):
            for c in range(side):
                layer = min(r, height - 1 - r, c, side - 1 - c)
                color = sequence[layer % len(sequence)]
                output[r][start + c] = 1 if color is None else color
    return {'input': grid, 'output': output}


def 教師():
    return [教材(), 教材(14, 7, (None, 3), (5, 0, 4)), 教材(10, 5, (7,), None)]


class 距離層回帰(unittest.TestCase):
    def test_矩形領域の独立距離式と一致(self):
        pair = 教材()
        output, rec = guarded_render(pair['input'])
        self.assertEqual(output, pair['output'])
        self.assertEqual(rec['open_component_count'], 2)
        self.assertEqual([r['sequence'] for r in rec['rewrite_records']], [[3, 4], [5]])

    def test_D4と全配色置換(self):
        pair = 教材(14, 7, (None, 3), (5, 0, 4))
        for name in ('identity', 'rot90', 'rot180', 'rot270', 'flip_h', 'flip_v', 'transpose', 'anti_transpose'):
            self.assertEqual(guarded_render(transform_grid_by_name(pair['input'], name))[0],
                             transform_grid_by_name(pair['output'], name))
        remap = lambda g: [[9 - v for v in row] for row in g]
        self.assertEqual(guarded_render(remap(pair['input']))[0], remap(pair['output']))

    def test_最大seed層を周期とし周期5も扱う(self):
        pair = 教材(20, 10, (None, None, None, None, 3), None)
        output, rec = guarded_render(pair['input'])
        self.assertEqual(output, pair['output'])
        self.assertEqual(rec['rewrite_records'][0]['sequence'], [1, 1, 1, 1, 3])

    def test_最小周期へ置換しない(self):
        pair = 教材(14, 7, (3, 3, 3), None)
        output, rec = guarded_render(pair['input'])
        self.assertEqual(output, pair['output'])
        self.assertEqual(rec['rewrite_records'][0]['sequence'], [3, 3, 3])

    def test_未seed位相BGと無seed領域保存(self):
        pair = 教材(14, 7, (None, 3), None)
        output, rec = guarded_render(pair['input'])
        self.assertEqual(output, pair['output'])
        self.assertEqual(rec['rewrite_records'][0]['sequence'], [1, 3])
        self.assertEqual(output[0][:7], [1] * 7)
        self.assertTrue(all(row[8:] == [1] * 7 for row in output))

    def test_零も通常のseed色(self):
        pair = 教材(14, 7, (0, 3), (5, 0, 4))
        self.assertEqual(guarded_render(pair['input'])[0], pair['output'])

    def test_八近傍の斜め境界露出(self):
        cells = {(r, c) for r in range(7) for c in range(7)} - {(0, 0), (0, 1), (1, 0), (1, 1)}
        layers = boundary_layers_8(cells, 7, 7)
        self.assertEqual(layers[2, 2], 0)
        self.assertEqual(layers[3, 3], 1)

    def test_一領域のseed競合で正常領域も出力しない(self):
        grid = 教材()['input']; grid[0][5] = 6
        self.assertIsNone(seeded_separator_layer_fill(grid)[0])
        self.assertIsNone(guarded_render(grid)[0])

    def test_separator頻度条件は元の全入力gate(self):
        grid = 教材()['input']
        for r in (2, 3, 4, 5):
            grid[r][0] = 3
        self.assertIsNone(detect_separator(grid)[0])
        self.assertIsNone(guarded_render(grid)[0])
        tie = [[0] * 11 for _ in range(11)]
        for r in range(11):
            tie[r][3] = 2; tie[r][7] = 3
        self.assertIsNone(detect_separator(tie)[0])

    def test_全seedとseparatorを保存(self):
        pair = 教材(14, 7, (None, 3), (5, 0, 4))
        output, _ = guarded_render(pair['input'])
        self.assertTrue(all(output[r][c] == v for r, row in enumerate(pair['input'])
                            for c, v in enumerate(row) if v != 1))

    def test_元renderer不一致は代替格子を返さない(self):
        pair = 教材(); output, rec = seeded_separator_layer_fill(pair['input'])
        bad = deepcopy(output); bad[0][0] = 9
        with patch.object(module, 'seeded_separator_layer_fill', return_value=(bad, rec)):
            self.assertEqual(guarded_render(pair['input'])[1]['failure'], 'source_output_disagrees')

    def test_不正格子と背景同率と無seed(self):
        for grid in ([], [[0], [0, 1]], [[True]], [[10]], [[0] * 31]):
            self.assertEqual(guarded_render(grid)[1]['failure'], 'invalid_arc_grid')
        self.assertEqual(guarded_render([[1, 2], [1, 2]])[1]['failure'], 'background_tie')
        self.assertIsNone(guarded_render(教材(left=None, right=None)['input'])[0])

    def test_教師反例と重複は採用しない(self):
        pairs = 教師(); pairs[-1]['output'][0][0] = 9
        self.assertFalse(距離層教材(pairs).全教師再現)
        pair = 教材()
        self.assertFalse(距離層教材([pair, pair]).全教師再現)

    def test_native支持は三盤面で分岐証拠を加算しない(self):
        pairs = 教師(); view = 距離層教材(pairs); boundary = '距離層対照'
        self.assertTrue(view.全教師再現)
        self.assertEqual(view.背景位相証拠数, 1); self.assertEqual(view.無seed保存証拠数, 1)
        engine = HDS学習実行系()
        self.assertFalse(候補機構を学習(engine, {'train': pairs[:2]}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系()
        record = 候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)
        self.assertTrue(record['同値採用']); self.assertEqual(record['現在観測数'], 3)
        self.assertEqual(record['事前観測数'], 0)
        query = 教材(18, 9, (5, 4, 3), (0, 7))
        self.assertEqual(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'], query['output'])
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[9]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'])

    def test_採用済みqueryの競合は全体HOLD(self):
        grid = 教材()['input']; grid[0][5] = 6
        result = 課題を解く({'train': 教師(), 'test': [{'input': grid}]}, [])
        record = next(r for r in result['families'] if r['境界'] == 'ARC距離層周期充填')
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertIsNone(result['results'][0]['answer'])


if __name__ == '__main__':
    unittest.main()
