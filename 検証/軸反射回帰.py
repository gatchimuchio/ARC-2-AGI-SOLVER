"""点/軸反射とnearest-valid guard、全parameter合意の対照。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2.軸反射教材 import 軸反射教材,guarded_reflection
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.HDS接続 import 課題を解く,HDS学習実行系,候補機構を学習,出力格子,観測へ


def 教材(marker=2,color=3,bg=0,axis='vertical'):
    g=[[bg]*14 for _ in range(12)]
    for r in range(2,6):g[r][6]=marker
    for r,c in ((2,4),(3,3),(3,4)):g[r][c]=color
    y=deepcopy(g)
    for r,c in ((2,8),(3,9),(3,8)):y[r][c]=color
    if axis=='horizontal':g=transform_grid_by_name(g,'transpose');y=transform_grid_by_name(y,'transpose')
    return {'input':g,'output':y}


def 教師(marker=2):
    return [教材(marker=marker),教材(marker=marker,color=4,bg=8,axis='horizontal')]


def sparse(shape,cells):
    h,w=shape;g=[[0]*w for _ in range(h)]
    for r,c,color in cells:g[r][c]=color
    return g


class 軸反射回帰(unittest.TestCase):
    def test_標識色は教師から選びD4と配色に従う(self):
        for marker in (2,7):
            v=軸反射教材(教師(marker));self.assertEqual(v.標識色候補,(marker,))
            p=教材(marker=marker,color=5,bg=9)
            for name in ('identity','rot90','rot180','rot270','flip_h','flip_v','transpose','anti_transpose'):
                out,_=v.候補(transform_grid_by_name(p['input'],name),{})
                self.assertEqual(out,transform_grid_by_name(p['output'],name))

    def test_点は中心を挟む180度反射(self):
        g=sparse((12,12),[(6,6,2),(4,4,5),(4,5,5),(5,4,5)])
        y=deepcopy(g)
        for r,c in ((8,8),(8,7),(7,8)):y[r][c]=5
        self.assertEqual(guarded_reflection(g,2)[0],y)

    def test_同率nearest_validは全格子保留(self):
        g=sparse((12,12),[(4,3,2),(4,7,2),(4,5,3)])
        out,rec=guarded_reflection(g,2)
        self.assertIsNone(out);self.assertEqual(rec['failure'],'nearest_marker_tie')

    def test_適格でも完全反射できない物体を飛ばさない(self):
        g=sparse((12,12),[(1,1,2),(3,3,3),(9,9,2),(8,7,5)])
        out,rec=guarded_reflection(g,2)
        self.assertIsNone(out);self.assertEqual(rec['failure'],'eligible_object_without_complete_reflection')

    def test_最寄り適格が無効でも唯一のvalidを使う(self):
        g=sparse((12,12),[(1,1,2),(3,7,2),(3,3,3)]);y=deepcopy(g);y[3][11]=3
        self.assertEqual(guarded_reflection(g,2)[0],y)

    def test_異色出力競合は保留し同色の重複は合成(self):
        g=sparse((13,13),[(4,5,2),(3,7,2),(4,3,3),(2,7,4)])
        self.assertEqual(guarded_reflection(g,2)[1]['failure'],'reflection_collision')
        g[2][7]=3;y=deepcopy(g);y[4][7]=3
        self.assertEqual(guarded_reflection(g,2)[0],y)

    def test_不適格な遠い物体と元の全前景を保存(self):
        g=sparse((20,20),[(5,5,2),(4,4,3),(17,17,4)])
        y=deepcopy(g);y[6][6]=3
        self.assertEqual(guarded_reflection(g,2)[0],y)

    def test_背景同率とunsupported標識と寸法を拒否(self):
        g=sparse((12,12),[(5,5,2),(5,6,2),(6,5,2),(3,3,3)])
        for value in (g,[[0,2],[2,0]],[],[[0]*31]):self.assertIsNone(guarded_reflection(value,2)[0])

    def test_全教師反例と重複は採用しない(self):
        ps=教師();ps[1]['output'][0][0]=1
        self.assertEqual(軸反射教材(ps).標識色候補,())
        p=教材();self.assertEqual(軸反射教材([p,deepcopy(p)]).標識色候補,())

    def test_保持parameterの未解決と異なる完全格子を保留(self):
        # 合意gateの対照として二つの保持仮説を与える。教師支持は増やさない。
        v=軸反射教材(教師());v.標識色候補=(2,3)
        self.assertIsNone(v.候補(教材()['input'],{})[0])
        g=sparse((12,12),[(5,5,2),(5,7,3)])
        self.assertIsNotNone(guarded_reflection(g,2)[0]);self.assertIsNotNone(guarded_reflection(g,3)[0])
        self.assertIsNone(v.候補(g,{})[0])

    def test_二教師だけを同一HDSへ観測(self):
        p=教材(color=5,bg=9);r=課題を解く({'train':教師(),'test':[{'input':p['input']}]},[])
        self.assertEqual(r['results'][0]['answer'],p['output']);self.assertEqual(r['minimum_support'],2)
        f=next(f for f in r['families']if f['境界']=='ARC軸反射')
        self.assertEqual(f['現在観測数'],2);self.assertEqual(f['事前観測数'],0);self.assertTrue(f['同値採用'])

    def test_中核既定支持3と後発隔離は保留(self):
        v=軸反射教材(教師());b='反射対照';e=HDS学習実行系()
        r=候補機構を学習(e,{'train':教師()},[],b,v.候補);self.assertFalse(r['同値採用'])
        e=HDS学習実行系(最小支持数=2);候補機構を学習(e,{'train':教師()},[],b,v.候補)
        e.実行(観測へ({'候補':教師()[0]['output'],'出力':[[3]]},b))
        self.assertIsNone(出力格子(e,観測へ({'候補':教材(color=5)['output']},b),同値必須=True)['answer'])


if __name__=='__main__':unittest.main()
