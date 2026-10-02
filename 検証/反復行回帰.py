"""最小境界period・行singleton・fallback禁止と二盤面支持を検証する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 反復行教材 as module
from 接続.ARC2.反復行教材 import guarded_render, 反復行教材
from 接続.ARC2.既存反復行 import infer_panel_periods
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 出力格子, 観測へ, 課題を解く


def 教材(n=4, interior=2):
    grid, output = [], []
    for index, border in enumerate((0, 5, 2)):
        payload = [v for v in range(10) if v != border][:interior]
        if index == 0:
            payload = list(range(1, interior + 1))
        chunks = [[border] + payload[:] for _ in range(n)]
        chosen = chunks[0][:]
        if index:
            chosen[1] = 9
            chunks[0 if index == 1 else n - 1] = chosen[:]
        grid.append([v for chunk in chunks for v in chunk] + [border])
        output.append(chosen + [border])
    return {'input': grid, 'output': output}


def 教師():
    return [教材(), 教材(5, 3)]


class 反復行回帰(unittest.TestCase):
    def test_行ごとに異なるpanelから抽出(self):
        pair = 教材(); output, rec = guarded_render(pair['input'])
        self.assertEqual(output, pair['output'])
        self.assertEqual(rec['raw_periods'], [3, 6])
        self.assertEqual(rec['period'], 3)
        self.assertEqual([r['branch'] for r in rec['row_records']], ['all_identical', 'unique_singleton', 'unique_singleton'])

    def test_periodとpanel数を入力から取得(self):
        for n, interior in ((3, 1), (3, 4), (5, 2), (4, 5)):
            pair = 教材(n, interior); output, rec = guarded_render(pair['input'])
            self.assertEqual(output, pair['output'])
            self.assertEqual(rec['period'], interior + 1)
            self.assertEqual(rec['panel_count'], n)

    def test_唯一singletonは多数決ではない(self):
        grid = [[0, 1, 0, 1, 0, 2, 0, 2, 0, 3, 0]]
        output, rec = guarded_render(grid)
        self.assertEqual(output, [[0, 3, 0]])
        self.assertEqual(rec['row_records'][0]['multiplicities'], [1, 2, 2])

    def test_全同一行は共通chunk(self):
        self.assertEqual(guarded_render([[0, 1, 2, 0, 1, 2, 0, 1, 2, 0]])[0], [[0, 1, 2, 0]])

    def test_最小period失敗後に大periodへ逃げない(self):
        grid = [[0, 1, 0, 2, 0, 3, 0, 1, 0, 2, 0, 3, 0]]
        self.assertEqual(infer_panel_periods(grid), [2, 4, 6])
        output, rec = guarded_render(grid)
        self.assertIsNone(output)
        self.assertEqual(rec['failure'], 'ambiguous_row_at_minimum_period')
        self.assertEqual(rec['period'], 2)

    def test_一行の複数singletonでも全体HOLD(self):
        grid = [[0, 1, 0, 1, 0, 2, 0], [0, 1, 0, 2, 0, 3, 0]]
        self.assertIsNone(guarded_render(grid)[0])
        self.assertIsNone(guarded_render([[0, 1, 0, 1, 0, 2, 0, 2, 0]])[0])

    def test_境界は行で異なり最多色同率も許す(self):
        grid = [[0, 1, 0, 1, 0, 2, 0], [1, 0, 1, 0, 1, 2, 1]]
        self.assertEqual(guarded_render(grid)[0], [[0, 2, 0], [1, 2, 1]])

    def test_配色と高さ両端境界を保持(self):
        pair = 教材()
        recolor = lambda g: [[9 - v for v in row] for row in g]
        self.assertEqual(guarded_render(recolor(pair['input']))[0], recolor(pair['output']))
        output, rec = guarded_render(pair['input'])
        self.assertEqual(len(output), len(pair['input']))
        self.assertTrue(all(len(row) == rec['period'] + 1 for row in output))
        self.assertTrue(all(a[0] == b[0] and a[-1] == b[-1] for a, b in zip(pair['input'], output)))

    def test_元periodと元出力の不一致を置換しない(self):
        pair = 教材()
        with patch.object(module, 'select_panel_period', return_value=6):
            self.assertEqual(guarded_render(pair['input'])[1]['failure'], 'source_period_not_minimum')
        bad = deepcopy(pair['output']); bad[0][1] = 8
        with patch.object(module, 'periodic_panel_anomaly_compress', return_value=bad):
            self.assertEqual(guarded_render(pair['input'])[1]['failure'], 'source_output_disagrees')

    def test_不正格子とperiodなし(self):
        for grid in ([], [[0], [0, 1]], [[True]], [[10]], [[0] * 31]):
            self.assertEqual(guarded_render(grid)[1]['failure'], 'invalid_arc_grid')
        self.assertEqual(guarded_render([[0, 1, 2, 3]])[1]['failure'], 'no_periodic_boundary_columns')

    def test_教師反例と重複を採用しない(self):
        pairs = 教師(); pairs[-1]['output'][0][1] = 9
        self.assertFalse(反復行教材(pairs).全教師再現)
        pair = 教材()
        self.assertFalse(反復行教材([pair, pair]).全教師再現)

    def test_native支持は二盤面で既定3と隔離を保持(self):
        pairs = 教師(); view = 反復行教材(pairs); boundary = '反復行対照'
        self.assertTrue(view.全教師再現)
        self.assertFalse(候補機構を学習(HDS学習実行系(), {'train': pairs}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系(最小支持数=2)
        record = 候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)
        self.assertTrue(record['同値採用']); self.assertEqual(record['現在観測数'], 2)
        self.assertEqual(record['事前観測数'], 0)
        query = 教材(3, 4)
        self.assertEqual(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'], query['output'])
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[9]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'])

    def test_採用済みqueryの曖昧行は全体HOLD(self):
        grid = [[0, 1, 0, 2, 0, 3, 0, 1, 0, 2, 0, 3, 0]]
        result = 課題を解く({'train': 教師(), 'test': [{'input': grid}]}, [])
        record = next(r for r in result['families'] if r['境界'] == 'ARC反復行singleton抽出')
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertIsNone(result['results'][0]['answer'])


if __name__ == '__main__':
    unittest.main()
