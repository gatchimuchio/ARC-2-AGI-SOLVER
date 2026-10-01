"""旧辺対応のunique-count基準と新しい曖昧入力拒否guardの対照。"""
from pathlib import Path
import sys
import unittest

根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 既存辺対応抽出 as view
from 接続.ARC2.HDS接続 import HDS学習実行系, 観測へ, 候補機構を学習, 出力格子, 課題を解く


def 教材(transform='identity', shape=(3,5), permutation=None):
    h,w=shape;g=[[0]*(w+8)for _ in range(h+8)]
    for c in range(w+8):g[0][c]=1;g[-1][c]=2
    for r in range(h+8):g[r][0]=3;g[r][-1]=4
    g[0][0]=0  # 背景色も外周paletteに含む入力領域
    crop=[[6+(r*2+c)%3 for c in range(w)]for r in range(h)]
    for r,row in enumerate(crop):g[4+r][4:4+w]=row
    colors={'top':1,'bottom':2,'left':3,'right':4}
    mapping=view.SIDE_TRANSFORM_MAPS[transform]
    g[3][4:4+w]=[colors[mapping['top']]]*w
    for r in range(4,4+h):g[r][3]=colors[mapping['left']]
    out=view.transform_grid_by_name(crop,transform)
    if permutation:
        g=[[permutation.get(v,v)for v in row]for row in g]
        out=[[permutation.get(v,v)for v in row]for row in out]
    return {'input':g,'output':out}


def 教師():
    return [教材('rot90',(3,5)),教材('flip_v',(4,3)),教材('anti_transpose',(2,4),{0:9,9:0,1:2,2:1})]


class 辺対応抽出回帰(unittest.TestCase):
    def test_全D4可変長方形と配色(self):
        for transform in view.SIDE_TRANSFORM_MAPS:
            for perm in (None,{0:9,9:0,1:4,4:1,2:3,3:2}):
                p=教材(transform,(3,5),perm)
                out,detail=view.辺対応候補(p['input'],{})
                self.assertEqual(out,p['output'])
                self.assertEqual(detail['payload_transform'],transform)

    def test_外周は一様性でなく旧unique最大数(self):
        p=教材('identity',(3,5));g=p['input']
        g[0][2]=3
        out,_=view.辺対応候補(g,{})
        self.assertEqual(out,p['output'])
        self.assertGreater(len(set(g[0][1:-1])),1)

    def test_未解決の外周guideを他の二辺で無視しない(self):
        p=教材('identity',(3,3));g=p['input']
        g[7][4:7]=[2]*3
        for r in range(len(g)):g[r][-1]=2
        g[-1][0]=2
        self.assertIsNotNone(view.render_edge_guided_payload_crop_normalizer(g)[0])
        out,detail=view.辺対応候補(g,{})
        self.assertIsNone(out);self.assertEqual(detail['failure'],'guideの外周辺が未確定')

    def test_弱い帯と同率帯と混在帯を保留(self):
        for values in ([2,4,0,0,0],[2,2,4,4],[1,1,0]):
            p=教材('identity',(3,len(values)));g=p['input'];g[7][4:4+len(values)]=values
            out,detail=view.辺対応候補(g,{})
            self.assertIsNone(out);self.assertEqual(detail['failure'],'guide帯が非一様又は空')

    def test_背景同率と不足guideは保留(self):
        out,detail=view.辺対応候補([[0,1],[1,0]],{})
        self.assertIsNone(out);self.assertEqual(detail['failure'],'背景頻度が同率')
        p=教材();g=p['input']
        for r in range(4,7):g[r][3]=0
        self.assertIsNone(view.辺対応候補(g,{})[0])

    def test_全制約の矛盾を保留(self):
        p=教材();g=p['input']
        for r in range(4,7):g[r][3]=1
        out,detail=view.辺対応候補(g,{})
        self.assertIsNone(out);self.assertEqual(detail['matching_transforms'],[])

    def test_空入力と出力三十上限(self):
        self.assertIsNone(view.辺対応候補([],{})[0])
        out,detail=view.辺対応候補(教材('identity',(31,2))['input'],{})
        self.assertIsNone(out);self.assertEqual(detail['failure'],'出力寸法範囲外')

    def test_同一HDSで三教師同値を採用(self):
        p=教材('transpose',(4,5),{0:9,9:0,1:2,2:1})
        r=課題を解く({'train':教師(),'test':[{'input':p['input']}]},[])
        self.assertEqual(r['results'][0]['answer'],p['output'])
        f=next(f for f in r['families']if f['境界']=='ARC辺対応抽出')
        self.assertEqual(f['現在観測数'],3);self.assertEqual(f['事前観測数'],0)
        self.assertTrue(f['同値採用']);self.assertEqual(r['minimum_support'],3)

    def test_既定支持不足と反例は元のgateで保留(self):
        e=HDS学習実行系();boundary='辺対応対照'
        r=候補機構を学習(e,{'train':教師()[:2]},[],boundary,view.辺対応候補)
        self.assertFalse(r['同値採用'])
        e=HDS学習実行系();候補機構を学習(e,{'train':教師()},[],boundary,view.辺対応候補)
        e.実行(観測へ({'候補':教師()[0]['output'],'出力':[[9]]},boundary))
        p=教材('transpose',(4,5))
        self.assertIsNone(出力格子(e,観測へ({'候補':p['output']},boundary),同値必須=True)['answer'])


if __name__=='__main__':unittest.main()
