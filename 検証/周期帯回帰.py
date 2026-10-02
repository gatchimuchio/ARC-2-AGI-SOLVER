"""全fit周期、観測済みaction、元最小周期格子と二盤面支持を検証。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 周期帯教材 as module
from 接続.ARC2.周期帯教材 import fit_guarded, guarded_render, 周期帯教材
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 出力格子, 観測へ, 課題を解く


def 入力(height=7, width=7):
    grid = [[0] * width for _ in range(height)]
    grid[-1][2] = grid[-1][3] = 2
    for row in range(height - 1): grid[row][1] = 8
    return grid


def 教師(recolor=False):
    pairs = []
    for width in (7, 8):
        grid = 入力(7, width); output = deepcopy(grid)
        for row, color in enumerate((2, 3, 0, 2, 3, 0, 2)):
            output[row][2] = output[row][3] = color
            if recolor and color == 3: output[row][1] = 3
        pairs.append({'input': grid, 'output': output})
    return pairs


def 転置(grid):
    return [list(row) for row in zip(*grid)]


class 周期帯回帰(unittest.TestCase):
    def test_全fitperiodを保持し最小periodを元どおり先決(self):
        fit = fit_guarded(教師())
        self.assertEqual([m['policy']['period'] for m in fit['models']], [3, 6, 7])
        self.assertEqual(fit['selected_period'], 3)
        for pair in 教師():
            output, record = guarded_render(pair['input'], fit)
            self.assertEqual(output, pair['output'])
            self.assertEqual(record['retained_periods'], [3, 6, 7])

    def test_解決済み全候補の異なる周期延長はHOLD(self):
        fit = fit_guarded(教師()); query = 入力(9, 7); query[1][1] = 0
        self.assertTrue(all(module.certify_render(query, m)[0] is not None for m in fit['models']))
        self.assertEqual(guarded_render(query, fit)[1]['failure'], 'retained_model_grids_disagree')

    def test_既定falseは外側payloadの証拠にしない(self):
        fit = fit_guarded(教師()); record = guarded_render(入力(9, 7), fit)[1]
        self.assertEqual(record['failure'], 'retained_model_unresolved')
        self.assertEqual(record['period'], 7)
        self.assertEqual(record['reason']['failure'], 'unobserved_outside_payload_action')

    def test_欠落位相のidentityへ逃げない(self):
        pairs = [{'input': 転置(p['input']), 'output': 転置(p['output'])} for p in 教師()]
        fit = fit_guarded(pairs)
        self.assertEqual([m['policy']['period'] for m in fit['models']], [3, 6, 7, 8])
        query = 転置(入力(9, 7)); query[1][0] = query[1][1] = 0
        record = guarded_render(query, fit)[1]
        self.assertEqual(record['period'], 8)
        self.assertEqual(record['reason']['failure'], 'unobserved_band_action')

    def test_最初の教師規約を入替で救済しない(self):
        pairs = 教師(); pairs[1]['input'][0][0] = pairs[1]['output'][0][0] = 8
        self.assertIsNone(module.old._periodic_marker_band_parse(pairs[1]['input'])[0])
        self.assertIsNotNone(fit_guarded(pairs))
        self.assertIsNone(fit_guarded(pairs[::-1]))

    def test_既知markerを他色境界で選び直さない(self):
        fit = fit_guarded(教師()); query = 入力(7, 9); query[0][0] = 8
        expected = deepcopy(query)
        for row, color in enumerate((2, 3, 0, 2, 3, 0, 2)): expected[row][2] = expected[row][3] = color
        self.assertIsNone(module.old._periodic_marker_band_parse(query)[0])
        self.assertEqual(guarded_render(query, fit)[0], expected)

    def test_外側全payload色の再着色とBGmarker保存(self):
        fit = fit_guarded(教師(True)); query = 入力(7, 10)
        query[1][8] = 5; query[4][8] = 9; query[1][6] = 2
        output, record = guarded_render(query, fit)
        self.assertIsNotNone(output)
        self.assertEqual((output[1][8], output[4][8], output[1][6], output[1][7]), (3, 3, 2, 0))
        self.assertEqual(output[0][1], 8)
        self.assertEqual(record['models'][0]['certificate']['band_cells'], 14)

    def test_配色と境界方向を入力から解釈(self):
        convert = lambda g: [[{0: 7, 2: 4, 3: 6, 8: 9}[v] for v in row] for row in g[::-1]]
        pairs = [{'input': convert(p['input']), 'output': convert(p['output'])} for p in 教師(True)]
        fit = fit_guarded(pairs)
        self.assertEqual(fit['common_marker_color'], 4)
        self.assertEqual(fit['models'][0]['policy']['fill_color'], 6)
        for pair in pairs: self.assertEqual(guarded_render(pair['input'], fit)[0], pair['output'])

    def test_学習fill新色契約と背景同率と無効格子(self):
        fit = fit_guarded(教師()); query = 入力(); query[0][0] = 3
        self.assertEqual(guarded_render(query, fit)[1]['reason']['failure'], 'learned_fill_is_not_new')
        self.assertEqual(module.certify_render([[0, 2], [2, 0]], fit['models'][0])[1]['failure'], 'background_tie')
        for bad in ([], [[0], [0, 1]], [[True]], [[10]]):
            self.assertEqual(module.certify_render(bad, fit['models'][0])[1]['failure'], 'invalid_arc_grid')

    def test_後続model一件の元renderer失敗も全体HOLD(self):
        fit = fit_guarded(教師()); original = module.old._periodic_marker_band_render
        def fail_later(grid, policy):
            return (None, {'failure': 'adverse_control'}) if policy['period'] == 6 else original(grid, policy)
        with patch.object(module.old, '_periodic_marker_band_render', side_effect=fail_later):
            record = guarded_render(入力(), fit)[1]
            self.assertEqual(record['failure'], 'retained_model_unresolved')
            self.assertEqual(record['period'], 6)

    def test_元格子と全記録の不一致を代替しない(self):
        fit = fit_guarded(教師()); original = module.old._periodic_marker_band_render
        def wrong_grid(grid, policy): return [[9]], original(grid, policy)[1]
        def wrong_record(grid, policy):
            output, record = original(grid, policy); record['periodic_marker_band_event_count'] += 1
            return output, record
        for wrong in (wrong_grid, wrong_record):
            with patch.object(module.old, '_periodic_marker_band_render', side_effect=wrong):
                self.assertEqual(guarded_render(入力(), fit)[1]['reason']['failure'], 'source_output_or_record_disagrees')

    def test_全教師raw適合先決と矛盾重複拒否(self):
        pairs = 教師(); pairs[-1]['output'][0][0] = 9
        with patch.object(module, 'guarded_render', side_effect=AssertionError('guard before raw fit')):
            self.assertIsNone(fit_guarded(pairs))
        pair = 教師()[0]; self.assertIsNone(fit_guarded([pair, pair]))

    def test_native支持は二盤面でperiodや行を加算しない(self):
        pairs = 教師(); view = 周期帯教材(pairs); boundary = '周期帯対照'
        engine = HDS学習実行系(最小支持数=2)
        self.assertFalse(候補機構を学習(engine, {'train': pairs[:1]}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系(最小支持数=2)
        record = 候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertEqual(record['現在観測数'], 2); self.assertEqual(record['事前観測数'], 0)
        query = pairs[0]['output']
        self.assertEqual(出力格子(engine, 観測へ({'候補': query}, boundary), 同値必須=True)['answer'], query)
        engine.実行(観測へ({'候補': query, '出力': [[9]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': query}, boundary), 同値必須=True)['answer'])

    def test_採用後の全候補競合HOLDと情報分離(self):
        query = 入力(9, 7); query[1][1] = 0
        task = {'train': 教師(), 'test': [{'input': query}]}; result = 課題を解く(task, [])
        record = next(r for r in result['families'] if r['境界'] == 'ARC境界marker周期帯')
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertEqual(record['現在観測数'], 2)
        self.assertIsNone(result['results'][0]['answer'])
        task['task_id'] = 'forbidden'
        with self.assertRaises(ValueError): 課題を解く(task, [])
        task.pop('task_id'); task['test'][0]['output'] = [[1]]
        with self.assertRaises(ValueError): 課題を解く(task, [])


if __name__ == '__main__':
    unittest.main()
