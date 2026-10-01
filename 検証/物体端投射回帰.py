"""教師由来の物体特徴・方向と完全格子の境界対照。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ルート = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ルート), str(ルート/'HDS/学習系統/v0.4.2')]
from 接続.ARC2.HDS接続 import 課題を解く, 観測へ
from 接続.ARC2.物体端投射 import 端投射教材, 配置する
from 接続.ARC2.既存物体特徴 import edge_pack_components, dominant_background_for_grid
from hds学習系統 import HDS学習実行系, 最小排気系


def 教材(a,b,offset=0):
    x=[[0]*9 for _ in range(7)]; y=deepcopy(x)
    x[2+offset][1]=a; x[3+offset][1]=a
    x[2][6]=b
    y[0][1]=a; y[1][1]=a; y[6][6]=b
    return {'input':x,'output':y}


形群 = [[(0,i) for i in range(3)], [(i,0) for i in range(3)],
        [(0,i) for i in range(4)], [(i,0) for i in range(4)],
        [(0,0),(1,0),(1,1)], [(0,0),(0,1),(1,0)],
        [(0,0),(0,1),(1,0),(1,1)], [(0,0),(0,1),(0,2),(1,1)]]


def 複数教材(形一覧, 逆=False):
    x=[[0]*30 for _ in range(12)];y=deepcopy(x)
    for i,形 in enumerate(形一覧):
        高さ=max(r for r,c in 形)+1;先頭=0 if (len(形)==3) != 逆 else 12-高さ
        for r,c in 形:
            x[r+4][c+1+i*7]=i+1;y[r+先頭][c+1+i*7]=i+1
    return {'input':x,'output':y}


class 物体端投射回帰(unittest.TestCase):
    def test_色と位置が違っても教師方向を再利用(self):
        教師=[複数教材(形群[:4]),複数教材(形群[4:])];test=複数教材(形群[1:5])
        r=課題を解く({'train':教師,'test':[{'input':test['input']}]},[])
        self.assertEqual(r['results'][0]['answer'],test['output'])
        self.assertEqual(r['object_learning']['特徴番号群'],[2])
        self.assertEqual(r['object_learning']['物理物体観測数'],8)
        参照={(i,tuple(sorted(o['cells']))) for i,p in enumerate(教師)
              for o in edge_pack_components(p['input'],dominant_background_for_grid(p['input']))}
        m=HDS学習実行系();教材系=端投射教材(教師)
        with patch.object(m,'実行',wraps=m.実行) as learn:
            教材系.学習する(m,観測へ)
        self.assertEqual(learn.call_count,len(参照))

    def test_上下対応を逆にしても教師から学ぶ(self):
        教師=[複数教材(形群[:4],True),複数教材(形群[4:],True)]
        test=複数教材(形群[1:5],True)
        r=課題を解く({'train':教師,'test':[{'input':test['input']}]},[])
        self.assertEqual(r['results'][0]['answer'],test['output'])

    def test_未知特徴は全格子を保留(self):
        t={'train':[複数教材(形群[:4]),複数教材(形群[4:])],
           'test':[{'input':複数教材([[(0,i) for i in range(5)]])['input']}]}
        self.assertIsNone(課題を解く(t,[])['results'][0]['answer'])

    def test_教師全体の再現と保存が必要(self):
        t=[教材(1,2),教材(3,4)];t[1]['output'][4][4]=8
        self.assertFalse(端投射教材(t).特徴番号群)

    def test_両端に一致する教師は曖昧(self):
        grid=[[0,0,1,0,0] for _ in range(3)]
        t=[{'input':grid,'output':deepcopy(grid)}]
        self.assertFalse(端投射教材(t).特徴番号群)

    def test_配置重複は同色でも拒否(self):
        x=[[0]*3 for _ in range(5)];x[1][1]=2;x[3][1]=2
        objects=[{'bbox':(r,1,r,1),'cells':{(r,1)},'color':2} for r in (1,3)]
        self.assertIsNone(配置する(x,objects,['top','top']))

    def test_反例による既存隔離を消さない(self):
        m=HDS学習実行系(最小支持数=2)
        for x,y in [(1,'a'),(2,'b'),(1,'b')]:m.実行(観測へ({'特徴':x,'向き':y},'test'))
        r=m.照会(観測へ({'特徴':1},'test'))
        self.assertGreater(len(r.係争中原理群),0)
        self.assertEqual(最小排気系().排出する(r).状態,'断定保留')


if __name__=='__main__':unittest.main()
