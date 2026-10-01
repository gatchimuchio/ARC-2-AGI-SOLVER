"""合成例によるHDS接続の回帰。ARC性能の採点とは分離する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ルート = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ルート), str(ルート / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2.HDS接続 import 課題を解く, 事前教材を読む


def 合成充填対(色):
    return {
        'input': [[3,3,3,1,1,1],[3,1,3,1,色,1],[3,3,3,1,1,1]],
        'output': [[3,3,3],[3,色,3],[3,3,3]],
    }


class 接続回帰(unittest.TestCase):
    def setUp(self):
        # この合成教材は回帰専用。productionの事前記憶には格納しない。
        self.事前 = [合成充填対(2), 合成充填対(4)]
        self.課題 = {'train': [合成充填対(5), 合成充填対(6)],
                     'test': [{'input': 合成充填対(7)['input']}]}

    def test_真の追加証拠と同値原理で未知色を出力(self):
        r = 課題を解く(self.課題, self.事前)
        self.assertEqual(r['results'][0]['answer'], 合成充填対(7)['output'])
        self.assertTrue(r['results'][0]['equality_admitted'])
        self.assertEqual((r['prior_observations'], r['current_observations']), (2,2))

    def test_支持不足ではhelperを直接排出しない(self):
        r = 課題を解く(self.課題, [])
        self.assertIsNone(r['results'][0]['answer'])

    def test_教師反例の隔離を解除しない(self):
        bad = deepcopy(self.課題)
        bad['train'][-1]['output'][1][1] = 8
        r = 課題を解く(bad, self.事前)
        self.assertIsNone(r['results'][0]['answer'])
        self.assertGreater(r['quarantined'], 0)

    def test_既存の恒等関係を保持(self):
        task = {'train': [{'input':[[i]],'output':[[i]]} for i in (1,2,3)],
                'test': [{'input':[[4,5],[6,7]]}]}
        self.assertEqual(課題を解く(task, self.事前)['results'][0]['answer'], [[4,5],[6,7]])

    def test_評価正解と課題識別子をruntimeへ入れない(self):
        for field in ('output', 'task_id'):
            bad = deepcopy(self.課題)
            if field == 'output':
                bad['test'][0][field] = [[0]]
            else:
                bad[field] = '診断用識別子'
            with self.assertRaises(ValueError):
                課題を解く(bad, self.事前)

    def test_実教材は異なる二つの教師観測(self):
        prior = 事前教材を読む()
        self.assertEqual(len(prior), 2)
        self.assertNotEqual(prior[0], prior[1])
        self.assertTrue(all(set(x) == {'input','output'} for x in prior))


if __name__ == '__main__':
    unittest.main()
