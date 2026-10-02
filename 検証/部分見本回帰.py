"""同色の外部見本・固定panel正規化・保留条件とnative支持を確認する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2.部分見本教材 import 部分見本教材,guarded_panel_exemplar
from 接続.ARC2.既存部分見本転写 import select_panel_exemplar_group
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.HDS接続 import 課題を解く,HDS学習実行系,候補機構を学習,出力格子,観測へ


def 教材(rows=2,cols=2,side=5,mask=((0,0),(0,2),(2,0)),colors=None,bg=0):
    colors=colors or list(range(1,rows*cols+1))
    g=[[bg]*30 for _ in range(30)]
    y=[[bg]*(cols*(side+1)+1)for _ in range(rows*(side+1)+1)]
    mh=max(r for r,c in mask)+1;mw=max(c for r,c in mask)+1
    for i,color in enumerate(colors):
        pr,pc=divmod(i,cols);r0=1+pr*(side+2);c0=1+pc*(side+2)
        for r in range(side):
            for c in range(side):
                g[r0+r][c0+c]=color;y[1+pr*(side+1)+r][1+pc*(side+1)+c]=color
        for r,c in mask:
            g[i*4+r][26+c]=color
            y[1+pr*(side+1)+(side-mh)//2+r][1+pc*(side+1)+(side-mw)//2+c]=bg
    return {'input':g,'output':y}


def 教師():return [教材(3,1),教材(1,3),教材(2,2)]


class 部分見本回帰(unittest.TestCase):
    def test_縦横格子配置と未見六panelを正規化(self):
        for p in 教師()+[教材(3,2)]:self.assertEqual(guarded_panel_exemplar(p['input'])[0],p['output'])

    def test_色と寸法と非連結見本を入力から得る(self):
        for p in (教材(1,2,3,((0,0),),[4,7],9),教材(2,2,7,((0,0),(2,2)),[3,5,6,8],1)):
            self.assertEqual(guarded_panel_exemplar(p['input'])[0],p['output'])
            group=select_panel_exemplar_group(p['input'])
            self.assertEqual(len(group['masks'][next(iter(group['masks']))]['cells']),1 if len(p['output'])==5 else 2)

    def test_鏡映と転置でも入力配置を保つ(self):
        p=教材(2,2)
        for name in ('flip_h','flip_v','transpose','rot180'):
            self.assertEqual(guarded_panel_exemplar(transform_grid_by_name(p['input'],name))[0],transform_grid_by_name(p['output'],name))

    def test_同色panel重複と不完全な配置は候補なし(self):
        p=教材(2,2);g=p['input']
        for r in range(8,13):
            for c in range(8,13):g[r][c]=0
        for r,c in ((12,26),(12,28),(14,26)):g[r][c]=0
        self.assertIsNone(guarded_panel_exemplar(g)[0])
        p=教材(1,2,colors=[1,1]);self.assertIsNone(guarded_panel_exemplar(p['input'])[0])

    def test_外部見本欠落と背景同率と不正寸法(self):
        p=教材(1,2)
        for r in range(30):
            for c in range(26,30):p['input'][r][c]=0
        for g in (p['input'],[[0,1],[1,0]],[],[[0]*31],[[0,0],[0]]):
            self.assertIsNone(guarded_panel_exemplar(g)[0])

    def test_奇数中心差は床関数で丸めず保留(self):
        p=教材(1,2,mask=((0,0),(1,2)))
        self.assertIsNotNone(select_panel_exemplar_group(p['input']))
        out,rec=guarded_panel_exemplar(p['input'])
        self.assertIsNone(out);self.assertEqual(rec['failure'],'mask_bbox_center_not_integer')

    def test_出力上限後に小さいgroupへ逃げない(self):
        g=[[0]*30 for _ in range(30)]
        for i in range(5):
            for r in range(i*5,i*5+5):
                for c in range(5):g[r][c]=i+1
            g[i*4][26]=i+1
        for i,color in enumerate((6,7)):
            for r in range(25,28):
                for c in range(i*5,i*5+3):g[r][c]=color
            g[29][10+i*2]=color
        self.assertEqual(select_panel_exemplar_group(g)['panel_height'],5)
        out,rec=guarded_panel_exemplar(g)
        self.assertIsNone(out);self.assertEqual(rec['failure'],'normalized_output_exceeds_arc_bounds')
        smaller=deepcopy(g)
        for r in range(30):
            for c in range(30):
                if smaller[r][c]in range(1,6):smaller[r][c]=0
        self.assertIsNotNone(guarded_panel_exemplar(smaller)[0])

    def test_整数中心が不成立でも小さいgroupへ逃げない(self):
        g=教材(1,2,mask=((0,0),(1,2)))['input']
        for i,color in enumerate((6,7)):
            for r in range(15,18):
                for c in range(1+i*5,4+i*5):g[r][c]=color
            g[24+i*2][20]=color
        self.assertEqual(select_panel_exemplar_group(g)['panel_height'],5)
        self.assertEqual(guarded_panel_exemplar(g)[1]['failure'],'mask_bbox_center_not_integer')
        for r in range(30):
            for c in range(30):
                if g[r][c]in (1,2):g[r][c]=0
        self.assertIsNotNone(guarded_panel_exemplar(g)[0])

    def test_教師反例と重複を拒否(self):
        ps=教師();ps[1]['output'][0][0]=1
        self.assertFalse(部分見本教材(ps).全教師再現)
        p=教材();self.assertFalse(部分見本教材([p,deepcopy(p)]).全教師再現)

    def test_panel数ではなく三教師の最終格子だけを観測(self):
        p=教材(3,2);r=課題を解く({'train':教師(),'test':[{'input':p['input']}]},[])
        self.assertEqual(r['results'][0]['answer'],p['output']);self.assertEqual(r['minimum_support'],3)
        f=next(f for f in r['families']if f['境界']=='ARC部分見本転写')
        self.assertEqual(f['現在観測数'],3);self.assertEqual(f['事前観測数'],0);self.assertTrue(f['同値採用'])

    def test_支持不足と後発反例はnativegateで保留(self):
        ps=教師();v=部分見本教材(ps);b='部分見本対照';e=HDS学習実行系()
        r=候補機構を学習(e,{'train':ps[:2]},[],b,v.候補);self.assertFalse(r['同値採用'])
        e=HDS学習実行系();r=候補機構を学習(e,{'train':ps},[],b,v.候補);self.assertTrue(r['同値採用'])
        e.実行(観測へ({'候補':ps[0]['output'],'出力':[[3]]},b))
        self.assertIsNone(出力格子(e,観測へ({'候補':ps[1]['output']},b),同値必須=True)['answer'])


if __name__=='__main__':unittest.main()
