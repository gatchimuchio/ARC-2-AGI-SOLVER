"""最大保持証明、全成分の原編集量制限、既存native支持を検証する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 対称剪定教材 as module
from 接続.ARC2.対称剪定教材 import guarded_render, 対称剪定教材
from 接続.ARC2.既存対称剪定 import apply_vertical_symmetry_pruning, vertical_prune_candidate
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 出力格子, 観測へ, 課題を解く


def 盤面(cells, height=14, width=24, color=2):
    grid = [[0] * width for _ in range(height)]
    for r, c in cells:
        grid[r][c] = color
    return grid


def 教材(stem=4):
    core = {(2, 3), (2, 4), (2, 5)} | {(r, 4) for r in range(3, 3 + stem)}
    return {'input': 盤面(core | {(3, 5)}), 'output': 盤面(core)}


def 教師():
    return [教材(4), 教材(5)]


class 対称剪定回帰(unittest.TestCase):
    def test_唯一最大保持と元出力が一致(self):
        pair = 教材(); output, rec = guarded_render(pair['input'])
        self.assertEqual(output, pair['output'])
        certificate = rec['maximum_retention_certificate'][0]
        self.assertEqual(certificate['axis2'], 8)
        self.assertEqual(certificate['removed_count'], 1)
        self.assertEqual(certificate['original_removal_limit'], max(3, certificate['component_size'] // 4 + 1))

    def test_半整数axisも列挙する(self):
        core = {(r, c) for r in range(2, 5) for c in (4, 5)}
        grid = 盤面(core | {(1, 3)})
        output, rec = guarded_render(grid)
        self.assertEqual(output, 盤面(core))
        self.assertEqual(rec['maximum_retention_certificate'][0]['axis2'], 9)

    def test_縦axisを保つ反転と配色(self):
        pair = 教材()
        for name in ('flip_h', 'flip_v', 'rot180'):
            self.assertEqual(guarded_render(transform_grid_by_name(pair['input'], name))[0],
                             transform_grid_by_name(pair['output'], name))
        change = lambda g: [[8 if v == 0 else 5 for v in row] for row in g]
        self.assertEqual(guarded_render(change(pair['input']))[0], change(pair['output']))

    def test_完全対称も含めて比較する(self):
        grid = 盤面({(2, 2), (2, 3), (3, 2), (3, 3)})
        self.assertIsNotNone(apply_vertical_symmetry_pruning(grid)[0])
        self.assertEqual(guarded_render(grid)[1]['failure'], 'source_excludes_complete_symmetry')

    def test_保持数同率をbboxや左優先で選ばない(self):
        grid = 盤面({(2, 2), (3, 2), (3, 3)})
        self.assertIsNotNone(apply_vertical_symmetry_pruning(grid)[0])
        self.assertEqual(guarded_render(grid)[1]['failure'], 'maximum_retention_axis_tie')

    def test_唯一最大でも元編集量制限を越えれば保留(self):
        cells = {(0, 0), (0, 1), (0, 2), (1, 2), (1, 3), (2, 3), (2, 4)}
        candidate = vertical_prune_candidate(sorted(cells))
        self.assertEqual(candidate['axis2'], 2)
        self.assertEqual(len(candidate['removed']), 4)
        self.assertEqual(guarded_render(盤面(cells))[1]['failure'], 'component_over_original_removal_limit')

    def test_予算超過を無視した部分剪定を拒否(self):
        cells = {(0, 0), (0, 1), (0, 2), (1, 2), (1, 3), (2, 3), (2, 4)}
        grid = 盤面(cells)
        pair = 教材()
        for r, row in enumerate(pair['input']):
            for c, value in enumerate(row):
                if value:
                    grid[r + 3][c + 10] = 3
        self.assertIsNotNone(apply_vertical_symmetry_pruning(grid)[0])
        self.assertEqual(guarded_render(grid)[1]['failure'], 'component_over_original_removal_limit')

    def test_singletonと元が保持する縦線も証明に含む(self):
        pair = 教材()
        for g in (pair['input'], pair['output']):
            g[10][18] = 3
            for r in (2, 3, 4):
                g[r][20] = 4
        output, rec = guarded_render(pair['input'])
        self.assertEqual(output, pair['output'])
        self.assertEqual(len(rec['maximum_retention_certificate']), 3)
        self.assertEqual([r['removed_count'] for r in rec['maximum_retention_certificate']], [1, 0, 0])

    def test_元出力不一致は証明格子へ置換しない(self):
        pair = 教材(); output, rec = apply_vertical_symmetry_pruning(pair['input'])
        bad = deepcopy(output); bad[0][0] = 9
        with patch.object(module, 'apply_vertical_symmetry_pruning', return_value=(bad, rec)):
            self.assertEqual(guarded_render(pair['input'])[1]['failure'], 'source_output_disagrees')

    def test_不正格子背景同率と変更なし(self):
        for grid in ([], [[0], [0, 1]], [[True]], [[10]], [[0] * 31]):
            self.assertEqual(guarded_render(grid)[1]['failure'], 'invalid_arc_grid')
        self.assertEqual(guarded_render([[0, 1], [1, 0]])[1]['failure'], 'background_tie')
        self.assertIsNone(guarded_render(盤面({(3, 3)}))[0])

    def test_教師反例と重複は採用しない(self):
        pairs = 教師(); pairs[-1]['output'][0][0] = 9
        self.assertFalse(対称剪定教材(pairs).全教師再現)
        pair = 教材()
        self.assertFalse(対称剪定教材([pair, pair]).全教師再現)

    def test_native支持は二盤面で既定3と隔離を保持(self):
        pairs = 教師(); view = 対称剪定教材(pairs); boundary = '剪定対照'
        self.assertTrue(view.全教師再現)
        self.assertFalse(候補機構を学習(HDS学習実行系(), {'train': pairs}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系(最小支持数=2)
        record = 候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)
        self.assertTrue(record['同値採用']); self.assertEqual(record['現在観測数'], 2)
        self.assertEqual(record['事前観測数'], 0)
        query = 教材(6)
        self.assertEqual(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'], query['output'])
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[9]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'])

    def test_採用済みqueryの同率は全体HOLD(self):
        grid = 盤面({(2, 2), (3, 2), (3, 3)})
        result = 課題を解く({'train': 教師(), 'test': [{'input': grid}]}, [])
        record = next(r for r in result['families'] if r['境界'] == 'ARC最大保持対称剪定')
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertIsNone(result['results'][0]['answer'])


if __name__ == '__main__':
    unittest.main()
