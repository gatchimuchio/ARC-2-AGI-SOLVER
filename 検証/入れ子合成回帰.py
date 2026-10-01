"""二教師設定・新機構・既存gateの負例対照。ARC性能値ではない。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ルート = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ルート), str(ルート/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import HDS接続 as 接続


def 合成課題():
    return {'train': [{'input': [[i]], 'output': [[i+3]]} for i in (1,2)],
            'test': [{'input': [[3]]}]}


def 一致候補(grid, policy):
    return [[grid[0][0]+3]], {}


class 入れ子接続回帰(unittest.TestCase):
    def 実行(self, task, first=None, second=一致候補):
        no = lambda grid, policy: (None, {'candidate_count': 0})
        with patch.object(接続, '_template_hole_pack_render', first or no), \
             patch.object(接続, '_nested_panel_relation_render', second):
            return 接続.課題を解く(task, [])

    def test_二つの異なる入力でのみ設定二を使用(self):
        with patch.object(接続, 'HDS学習実行系', wraps=接続.HDS学習実行系) as factory:
            r = self.実行(合成課題())
        self.assertEqual(factory.call_count, 1)
        self.assertEqual(r['minimum_support'], 2)
        self.assertEqual(r['results'][0]['answer'], [[6]])
        self.assertTrue(r['results'][0]['equality_admitted'])
        n = next(x for x in r['families'] if x['境界'] == 'ARC入れ子パネル合成')
        self.assertEqual(n['事前観測数'], 0)
        self.assertEqual(n['現在観測数'], 2)

    def test_一観測と重複教師は支持を水増ししない(self):
        for count in (1,2):
            task = 合成課題()
            task['train'] = [deepcopy(task['train'][0]) for _ in range(count)]
            r = self.実行(task)
            self.assertEqual(r['minimum_support'], 3)
            self.assertIsNone(r['results'][0]['answer'])

    def test_三教師時は設定三を保持(self):
        task = 合成課題()
        task['train'].append({'input': [[4]], 'output': [[7]]})
        self.assertEqual(self.実行(task)['minimum_support'], 3)

    def test_二教師の反例を有限対応で迂回しない(self):
        task = 合成課題()
        task['train'][1]['output'] = [[8]]
        self.assertIsNone(self.実行(task)['results'][0]['answer'])

    def test_同じ候補へ異なる教師結果なら保留(self):
        fixed = lambda grid, policy: ([[5]], {})
        self.assertIsNone(self.実行(合成課題(), second=fixed)['results'][0]['answer'])

    def test_曖昧helperは排出しない(self):
        ambiguous = lambda grid, policy: (None, {'candidate_count': 2})
        self.assertIsNone(self.実行(合成課題(), second=ambiguous)['results'][0]['answer'])

    def test_採用機構同士の競合は順位で選ばない(self):
        def alternative(grid, policy):
            return [[grid[0][0]+3 if grid[0][0] < 3 else 7]], {}
        r = self.実行(合成課題(), first=一致候補, second=alternative)
        self.assertIsNone(r['results'][0]['answer'])
        self.assertEqual(r['results'][0]['status'], '断定保留')
        self.assertIn('競合', r['results'][0]['reasons'][0])

    def test_採用済み代替のtest曖昧性を無視しない(self):
        def unresolved(grid, policy):
            return 一致候補(grid, policy) if grid[0][0] < 3 else (None, {'candidate_count': 2})
        r = self.実行(合成課題(), first=一致候補, second=unresolved)
        self.assertIsNone(r['results'][0]['answer'])
        self.assertEqual(r['results'][0]['status'], '断定保留')

    def test_別機構の事前二観測を入れ子の支持に混ぜない(self):
        task = 合成課題()
        task['train'] = task['train'][:1]
        prior = [{'input': [[i]], 'output': [[i+3]]} for i in (4,5)]
        def prior_only(grid, policy):
            return 一致候補(grid, policy) if grid[0][0] in (4,5) else (None, {})
        with patch.object(接続, '_template_hole_pack_render', prior_only), \
             patch.object(接続, '_nested_panel_relation_render', 一致候補):
            r = 接続.課題を解く(task, prior)
        n = next(x for x in r['families'] if x['境界'] == 'ARC入れ子パネル合成')
        self.assertEqual(r['minimum_support'], 3)
        self.assertEqual((n['事前観測数'], n['現在観測数']), (0,1))
        self.assertFalse(n['同値採用'])
        self.assertIsNone(r['results'][0]['answer'])

    def test_別機構の隔離を有効な新機構で無視しない(self):
        prior = [{'input': [[i]], 'output': [[i+3]]} for i in (4,5)]
        def contradicted(grid, policy):
            return 一致候補(grid, policy) if grid[0][0] in (4,5) else ([[9]], {})
        with patch.object(接続, '_template_hole_pack_render', contradicted), \
             patch.object(接続, '_nested_panel_relation_render', 一致候補):
            r = 接続.課題を解く(合成課題(), prior)
        n = next(x for x in r['families'] if x['境界'] == 'ARC入れ子パネル合成')
        self.assertTrue(n['同値採用'])
        self.assertGreater(r['quarantined'], 0)
        self.assertIsNone(r['results'][0]['answer'])


if __name__ == '__main__':
    unittest.main()
