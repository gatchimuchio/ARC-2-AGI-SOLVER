"""既存領域候補の境界・同一HDS接続の負例対照。ARC性能値ではない。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ルート = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ルート), str(ルート/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import HDS接続 as 接続
from 接続.ARC2.既存領域転写 import _dual_region_hole_palette_render, _minimum_centroid_assignment


def 教材(色, 壁=2, 背景=0):
    格子 = [[背景]*9 for _ in range(5)]
    for 左 in (1,5):
        for 行 in range(1,4):
            for 列 in range(左,左+3):
                格子[行][列] = 壁 if 行 in (1,3) or 列 in (左,左+2) else 背景
    格子[2][6] = 色
    return {'input': 格子, 'output': [[壁]*3, [壁,色,壁], [壁]*3]}


def 課題():
    return {'train': [教材(3),教材(4)], 'test': [{'input': 教材(5)['input']}]}


class 領域転写回帰(unittest.TestCase):
    def test_実候補を二教師から同一機械で学習(self):
        with patch.object(接続, 'HDS学習実行系', wraps=接続.HDS学習実行系) as factory:
            r = 接続.課題を解く(課題(), [])
        self.assertEqual(factory.call_count, 1)
        self.assertEqual(r['results'][0]['answer'], 教材(5)['output'])
        self.assertTrue(r['results'][0]['equality_admitted'])
        f = next(f for f in r['families'] if f['境界'] == 'ARC閉領域パレット転写')
        self.assertEqual((f['事前観測数'],f['現在観測数']), (0,2))

    def test_色や配置の固定答えではない(self):
        for 色, 壁, 背景 in ((1,7,9),(8,4,6)):
            p = 教材(色,壁,背景)
            shifted = [[背景]*11] + [[背景]+row+[背景] for row in p['input']]
            self.assertEqual(_dual_region_hole_palette_render(shifted,{})[0], p['output'])

    def test_一教師または重複教師では新機構を採用しない(self):
        for count in (1,2):
            t = 課題(); t['train'] = [deepcopy(t['train'][0]) for _ in range(count)]
            r = 接続.課題を解く(t, [])
            self.assertEqual(r['minimum_support'], 3)
            self.assertIsNone(r['results'][0]['answer'])

    def test_教師反例を有限対応で迂回しない(self):
        t = 課題(); t['train'][1]['output'][1][1] = 8
        self.assertIsNone(接続.課題を解く(t, [])['results'][0]['answer'])

    def test_曖昧な同距離割当てと探索上限は不採用(self):
        same = [[(1,1)],[(1,1)]]
        self.assertIsNone(_minimum_centroid_assignment(same,same,(3,3),(3,3)))
        horizontal, vertical = [[(1,0)],[(1,2)]], [[(0,1)],[(2,1)]]
        self.assertIsNone(_minimum_centroid_assignment(horizontal,vertical,(3,3),(3,3)))
        large = [[(i,i)] for i in range(13)]
        self.assertIsNone(_minimum_centroid_assignment(large,large,(15,15),(15,15)))

    def test_採用済み領域機構の未解決testは保留(self):
        t = 課題(); t['test'][0]['input'] = [[0,0],[0,0]]
        r = 接続.課題を解く(t, [])
        self.assertIsNone(r['results'][0]['answer'])
        self.assertIn('未確定', r['results'][0]['reasons'][0])

    def test_既存機構との完全出力競合を保留(self):
        def competing(grid, policy):
            y, detail = _dual_region_hole_palette_render(grid,policy)
            if grid[2][6] == 5:
                y[1][1] = 8
            return y,detail
        with patch.object(接続, '_nested_panel_relation_render', competing):
            r = 接続.課題を解く(課題(), [])
        self.assertIsNone(r['results'][0]['answer'])
        self.assertIn('競合', r['results'][0]['reasons'][0])

    def test_test正解と課題IDのruntime流入を拒否(self):
        for extra in ('output','task_id'):
            t = 課題(); t['test'][0][extra] = 'forbidden'
            with self.assertRaises(ValueError):
                接続.課題を解く(t, [])


if __name__ == '__main__':
    unittest.main()
