"""対角線橋・交点射影の独立した幾何対照とHDS排気対照。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2.対角線橋教材 import 対角線橋教材,対角線橋候補
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.HDS接続 import 課題を解く,HDS学習実行系,候補機構を学習,出力格子,観測へ


def 教材(length=4,start=(2,1),shape=(12,14),bg=0,primary=1,other=6,hit=2):
    h,w=shape;r0,c0=start;g=[[bg]*w for _ in range(h)]
    g[r0][c0]=primary;g[r0+length][c0+length]=primary
    if hit is not None:g[r0+hit][c0+hit]=other
    g[-1][-1]=other  # 橋から離れた同色markerは動作を起こさない。
    y=deepcopy(g)
    for i in range(1,length):
        if i!=hit:y[r0+i][c0+i]=primary
    if hit is not None:
        total=r0+c0+2*hit
        for r in range(h):
            c=total-r
            if 0<=c<w and g[r][c]==bg:y[r][c]=other
    return {'input':g,'output':y}


def 教師(primary=1,other=6):
    return [教材(primary=primary,other=other),
            教材(length=5,start=(1,2),shape=(13,15),primary=primary,other=other,hit=3),
            教材(length=6,start=(1,1),shape=(15,16),bg=8,primary=primary,other=other,hit=None),
            教材(length=3,start=(3,2),shape=(14,17),primary=primary,other=other,hit=1),
            教材(length=7,start=(1,1),shape=(17,19),primary=primary,other=other,hit=None)]


def 複数橋():
    p=教材(length=4,start=(1,1),shape=(20,20))
    q=教材(length=4,start=(1,11),shape=(20,20))
    return {key:[[a or b for a,b in zip(ar,br)]for ar,br in zip(p[key],q[key])]for key in ('input','output')}


class 対角線橋回帰(unittest.TestCase):
    def test_主色は教師から選びD4と背景変更に従う(self):
        for primary,other in ((1,6),(3,7)):
            v=対角線橋教材(教師(primary,other));self.assertEqual(v.主色候補,(primary,))
            p=教材(length=5,start=(2,3),shape=(16,18),bg=9,primary=primary,other=other)
            for name in ('identity','rot90','rot180','rot270','flip_h','flip_v','transpose','anti_transpose'):
                self.assertEqual(v.候補(transform_grid_by_name(p['input'],name),{})[0],transform_grid_by_name(p['output'],name))

    def test_入力から複数橋を列挙する(self):
        p=複数橋();out,rec=対角線橋教材(教師()).候補(p['input'],{})
        self.assertEqual(out,p['output']);self.assertEqual(rec['bridge_count'],2)

    def test_橋と射影の異色競合をHOLD(self):
        g=[[0]*20 for _ in range(20)]
        for r,c in ((1,1),(7,7),(1,5),(7,11)):g[r][c]=1
        g[3][3]=6;g[4][8]=6
        out,rec=対角線橋候補(g,1)
        self.assertIsNone(out);self.assertEqual(rec['failure'],'conflicting_bridge_ray_proposals')

    def test_射影同士は同色合成可で異色はHOLD(self):
        g=[[0]*12 for _ in range(12)]
        for r,c in ((1,1),(7,7),(1,9),(7,3)):g[r][c]=1
        g[3][3]=6;g[4][6]=7
        self.assertIsNone(対角線橋候補(g,1)[0])
        g[4][6]=6
        out,rec=対角線橋候補(g,1)
        self.assertIsNotNone(out);self.assertEqual(out[2][4],6);self.assertEqual(rec['bridge_count'],2)

    def test_全既存前景と橋外markerを保存(self):
        p=教材(hit=None);out,_=対角線橋候補(p['input'],1)
        self.assertEqual(out,p['output']);self.assertEqual(out[-1][-1],6)
        for r,row in enumerate(p['input']):
            for c,v in enumerate(row):
                if v!=0:self.assertEqual(out[r][c],v)

    def test_背景同率と不正格子を拒否(self):
        for g in ([],[[0,1],[1,0]],[[0,0],[0]],[[0]*31]):
            self.assertIsNone(対角線橋候補(g,1)[0])

    def test_元の教師制限と予測制限を保持(self):
        ps=教師();ps[0]['input'][0][0]=5
        self.assertEqual(対角線橋教材(ps).主色候補,())
        ps=教師();ps[0]=複数橋()
        self.assertEqual(対角線橋教材(ps).主色候補,())
        g=[[0]*20 for _ in range(20)]
        for i in range(31):g[i//20][i%20]=1
        self.assertEqual(対角線橋候補(g,1)[1]['failure'],'primary_marker_count_out_of_bounds')

    def test_教師反例と重複と色不一致は未採用(self):
        ps=教師();ps[-1]['output'][0][0]=2
        self.assertEqual(対角線橋教材(ps).主色候補,())
        p=教師()[0];self.assertEqual(対角線橋教材([p,deepcopy(p)]).主色候補,())
        ps=教師();ps[-1]=教材(primary=3,other=7)
        self.assertEqual(対角線橋教材(ps).主色候補,())

    def test_同一HDSへ五教師を一度ずつ観測(self):
        p=複数橋();r=課題を解く({'train':教師(),'test':[{'input':p['input']}]},[])
        self.assertEqual(r['results'][0]['answer'],p['output'])
        f=next(f for f in r['families']if f['境界']=='ARC対角線橋')
        self.assertEqual(f['現在観測数'],5);self.assertEqual(f['事前観測数'],0);self.assertTrue(f['同値採用'])

    def test_既定支持不足と後発反例でHOLD(self):
        v=対角線橋教材(教師());b='橋対照';e=HDS学習実行系()
        r=候補機構を学習(e,{'train':教師()[:2]},[],b,v.候補);self.assertFalse(r['同値採用'])
        e=HDS学習実行系();候補機構を学習(e,{'train':教師()},[],b,v.候補)
        e.実行(観測へ({'候補':教師()[0]['output'],'出力':[[3]]},b))
        self.assertIsNone(出力格子(e,観測へ({'候補':複数橋()['output']},b),同値必須=True)['answer'])


if __name__=='__main__':unittest.main()
