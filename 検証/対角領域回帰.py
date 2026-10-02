"""固定方向の領域和・新色条件・二教師のnative排気を確認する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2.対角領域教材 import 対角領域教材,対角領域候補
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.HDS接続 import 課題を解く,HDS学習実行系,候補機構を学習,出力格子,観測へ


def 教材(offset=(0,0),shape=(9,9),bg=0,marker=4,fill=2,third=False):
    dr,dc=offset;h,w=shape;g=[[bg]*w for _ in range(h)]
    wall={(1,3),(2,2),(3,1),(3,5),(4,4),(5,3)}
    added={(2,3),(3,2),(2,4),(3,3),(4,2),(3,4),(4,3)}
    if third:
        wall|={(5,7),(6,6),(7,5)}
        added|={(4,5),(5,4),(4,6),(5,5),(6,4),(5,6),(6,5)}
    for r,c in wall:g[r+dr][c+dc]=marker
    y=deepcopy(g)
    for r,c in added:y[r+dr][c+dc]=fill
    return {'input':g,'output':y}


def 教師(fill=2,marker=4):
    return [教材(fill=fill,marker=marker),教材(offset=(1,2),shape=(11,14),bg=8,fill=fill,marker=marker)]


class 対角領域回帰(unittest.TestCase):
    def test_手計算した二線分間の七画素(self):
        p=教材();out,rec=対角領域候補(p['input'],2)
        self.assertEqual(out,p['output']);self.assertEqual(rec['added_pixels'],7)

    def test_全pairの重なりは同色の和(self):
        p=教材(third=True);out,rec=対角領域候補(p['input'],2)
        self.assertEqual(out,p['output']);self.assertEqual(rec['segments'],3);self.assertEqual(rec['added_pixels'],14)

    def test_方向を保つ対称性と配色移動(self):
        for marker,fill in ((4,2),(6,3)):
            v=対角領域教材(教師(fill,marker));self.assertEqual(v.充填色,fill)
            p=教材(offset=(1,2),shape=(12,15),bg=9,marker=marker,fill=fill,third=True)
            for name in ('identity','rot180','transpose','anti_transpose'):
                self.assertEqual(v.候補(transform_grid_by_name(p['input'],name),{})[0],transform_grid_by_name(p['output'],name))

    def test_singleton線分を勝手に除外せずD4へ拡張しない(self):
        g=[[0]*7 for _ in range(7)];g[1][1]=4;g[3][3]=4
        expected=deepcopy(g);expected[2][2]=2
        self.assertEqual(対角領域候補(g,2)[0],expected)
        self.assertIsNone(対角領域候補(transform_grid_by_name(g,'flip_h'),2)[0])

    def test_d範囲非重複と同じsでは追加なし(self):
        for cells in (((1,3),(2,2),(8,4),(9,3)),((1,5),(2,4),(4,2),(5,1))):
            g=[[0]*13 for _ in range(13)]
            for r,c in cells:g[r][c]=4
            self.assertIsNone(対角領域候補(g,2)[0])

    def test_元前景を保存し別の前景色は保留(self):
        p=教材(third=True);out,_=対角領域候補(p['input'],2)
        for r,row in enumerate(p['input']):
            for c,v in enumerate(row):
                if v!=0:self.assertEqual(out[r][c],v)
        p['input'][0][0]=7
        self.assertIsNone(対角領域候補(p['input'],2)[0])

    def test_充填色既出と背景同率と不正寸法(self):
        g=教材()['input'];g[0][0]=2
        for value in (g,教材(bg=2)['input'],[[0,4],[4,0]],[],[[0]*31]):
            self.assertIsNone(対角領域候補(value,2)[0])

    def test_教師全再現と色一致と非重複を要求(self):
        ps=教師();ps[1]['output'][3][5]=8
        self.assertIsNone(対角領域教材(ps).充填色)
        self.assertIsNone(対角領域教材([教材(),教材(offset=(1,2),shape=(11,14),fill=3)]).充填色)
        p=教材();self.assertIsNone(対角領域教材([p,deepcopy(p)]).充填色)

    def test_二つの実教師が既存課題支持2で出力(self):
        p=教材(third=True);r=課題を解く({'train':教師(),'test':[{'input':p['input']}]},[])
        self.assertEqual(r['results'][0]['answer'],p['output']);self.assertEqual(r['minimum_support'],2)
        f=next(f for f in r['families']if f['境界']=='ARC対角領域')
        self.assertEqual(f['現在観測数'],2);self.assertEqual(f['事前観測数'],0);self.assertTrue(f['同値採用'])

    def test_中核既定支持3と後発反例gateは無変更(self):
        v=対角領域教材(教師());b='対角領域対照';e=HDS学習実行系()
        r=候補機構を学習(e,{'train':教師()},[],b,v.候補);self.assertFalse(r['同値採用'])
        e=HDS学習実行系(最小支持数=2);候補機構を学習(e,{'train':教師()},[],b,v.候補)
        e.実行(観測へ({'候補':教師()[0]['output'],'出力':[[3]]},b))
        self.assertIsNone(出力格子(e,観測へ({'候補':教材(third=True)['output']},b),同値必須=True)['answer'])


if __name__=='__main__':unittest.main()
