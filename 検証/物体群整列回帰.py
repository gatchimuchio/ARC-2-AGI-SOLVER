"""教師で選ぶ群・方向とnative支持/保留を確認する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 物体群整列 as view
from 接続.ARC2.HDS接続 import HDS学習実行系, 観測へ, 課題を解く

形 = {'枠': [(r,c) for r in range(3) for c in range(3) if r in (0,2) or c in (0,2)],
      '塊': [(r,c) for r in range(3) for c in range(3)],
      '十': [(0,1),(1,0),(1,1),(1,2),(2,1)]}


def 教材(ずれ=0, 反転=False, 行群=False, 単調=False, 三群=False):
    種類 = ['塊','枠','塊','枠'] if not 三群 else ['十','塊','枠']
    列群 = [1,5,10,15] if 単調 else [10,1,14,5]
    格子 = [[0]*23 for _ in range(22)]
    物体 = []
    for i, kind in enumerate(種類):
        r,c = 1+i*4+ずれ, 列群[i]
        color = i+1+ずれ
        for y,x in 形[kind]:格子[r+y][c+x]=color
        物体.append((kind,color,[[color if (y,x) in 形[kind] else 0 for x in range(3)]for y in range(3)]))
    区分 = {'枠':0,'塊':1,'十':2}
    if 反転:区分={'枠':1,'塊':0,'十':2}
    群 = {i:[]for i in range(3 if 三群 else 2)}
    for kind,color,tile in 物体:群[区分[kind]].append(tile)
    if 反転:
        for items in 群.values():items.reverse()
    length=max(map(len,群.values()));h,w=(len(群)*3,length*3)if 行群 else(length*3,len(群)*3)
    out=[[0]*w for _ in range(h)]
    for lane,items in 群.items():
        for pos,tile in enumerate(items):
            r,c=(lane*3,pos*3)if 行群 else(pos*3,lane*3)
            for y,row in enumerate(tile):out[r+y][c:c+3]=row
    return {'input':格子,'output':out}


def 学習(train):
    v=view.物体群教材(train);e=HDS学習実行系(最小支持数=3);v.学習する(e,観測へ)
    return v,e


class 物体群整列回帰(unittest.TestCase):
    def test_群軸と並びの方向を教師から選ぶ(self):
        for rev,axis in ((False,False),(True,False),(True,True)):
            v,e=学習([教材(0,rev,axis),教材(1,rev,axis)])
            p=教材(2,rev,axis)
            self.assertEqual(v.候補(p['input'],{})[0],p['output'])
            self.assertEqual({m[0]for m in v.モデル群},{0 if axis else 1})
            self.assertEqual({m[3]for m in v.モデル群},{rev})

    def test_二群や特定面積を固定しない(self):
        v,e=学習([教材(0,三群=True),教材(1,三群=True)])
        p=教材(2,三群=True)
        self.assertEqual(v.候補(p['input'],{})[0],p['output'])
        self.assertEqual(len(p['output'][0]),9)

    def test_配色と現在の群個数から出力寸法を決める(self):
        def 配色(p):return {k:[[9 if v==0 else v for v in row]for row in g]for k,g in p.items()}
        second=教材(1)
        for r in range(2,5):
            second['input'][r][18:21]=second['input'][r][10:13];second['input'][r][10:13]=[0,0,0]
        v,e=学習([配色(教材()),配色(second)])
        p=教材(2)
        for kind,color,col in (('枠',7,1),('塊',8,10)):
            for y,x in 形[kind]:p['input'][19+y][col+x]=color
        tail=[[7 if (y,x) in 形['枠'] else 0 for x in range(3)]+[8]*3 for y in range(3)]
        p['output'].extend(tail);p=配色(p)
        out=v.候補(p['input'],{})[0]
        self.assertEqual(out,p['output']);self.assertEqual((len(out),len(out[0])),(9,6))

    def test_観測を特徴や順序候補数で複製しない(self):
        train=[教材(0,単調=True),教材(1,単調=True)]
        v,e=学習(train)
        self.assertGreater(len(v.モデル群),1)
        self.assertEqual(v.記録()['物理物体観測数'],8)
        self.assertEqual(v.記録()['境界観測数'],{'ARC物体群スロット区分1':8})
        identities={(j,tuple(sorted(o['cells'])))for j,p in enumerate(train)for o in view.物体を読む(p['input'])[3]}
        self.assertEqual(len(identities),8)

    def test_全教師整合モデルの競合は保留(self):
        v,e=学習([教材(0,単調=True),教材(1,単調=True)])
        g=教材(2)['input']
        for r in range(3,6):
            g[r][18:21]=g[r][10:13];g[r][10:13]=[0,0,0]
        out,detail=v.候補(g,{})
        self.assertIsNone(out);self.assertEqual(detail['failure'],'教師整合モデル間の出力競合')
        g=教材(2)['input']
        for r in range(3,6):
            g[r][14:17]=g[r][10:13];g[r][10:13]=[0,0,0]
        out,detail=v.候補(g,{})
        self.assertIsNone(out);self.assertEqual(detail['failure'],'未解決の配置モデル')

    def test_未観測特徴と群欠落と順序同率を保留(self):
        v,e=学習([教材(),教材(1)])
        g=教材(2)['input'];g[4][11]=0;g[3][10]=0
        out,detail=v.候補(g,{})
        self.assertIsNone(out);self.assertEqual(detail['failure'],'未観測の物体特徴')
        parsed=view.物体を読む(教材()['input']);bg,h,w,objects=parsed
        self.assertIsNone(view.配置する(parsed,[0]*4,1,0,False,{0,1}))
        copied=deepcopy(parsed);copied[3][2]['bbox']=(1,14,3,16)
        self.assertIsNone(view.配置する(copied,[1,0,1,0],1,0,False,{0,1}))
        self.assertIsNone(view.配置する(parsed,[0,2,0,2],1,0,False,{0,2}))

    def test_重複教材と重複物体対応を保留(self):
        p=教材();v=view.物体群教材([p,deepcopy(p)])
        self.assertFalse(v.モデル群)
        p=教材();p['input']=[[1 if x==3 else x for x in row]for row in p['input']]
        self.assertIsNone(view.物体を読む(p['input']))

    def test_許容関係の後発反例も別境界反例も保留(self):
        for boundary in ('ARC物体群スロット区分1','無関係な境界'):
            v,e=学習([教材(),教材(1)])
            if boundary=='無関係な境界':
                for x in (1,2,3):e.実行(観測へ({'特徴2':x,'区分':x},boundary))
                e.実行(観測へ({'特徴2':1,'区分':2},boundary))
            else:e.実行(観測へ({'特徴2':8.0,'区分':1},boundary))
            self.assertIsNone(v.候補(教材(2)['input'],{})[0])

    def test_同一HDSの完全格子gateと一教師不足(self):
        p=教材(2)
        r=課題を解く({'train':[教材(),教材(1)],'test':[{'input':p['input']}]},[])
        self.assertEqual(r['results'][0]['answer'],p['output'])
        self.assertTrue(r['results'][0]['equality_admitted'])
        r=課題を解く({'train':[教材()],'test':[{'input':p['input']}]},[])
        self.assertIsNone(r['results'][0]['answer'])

    def test_不正な配置数と型と出力寸法は保留(self):
        parsed=view.物体を読む(教材()['input'])
        for labels in ([0],[0,1,0,True],[0,1,0,2]):
            self.assertIsNone(view.配置する(parsed,labels,1,0,False,{0,1}))
        large=(parsed[0],20,parsed[2],parsed[3])
        self.assertIsNone(view.配置する(large,[1,0,1,0],1,0,False,{0,1}))


if __name__=='__main__':unittest.main()
