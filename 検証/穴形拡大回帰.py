"""入力から得る穴形状・glyph尺度と曖昧時の全格子保留を確認する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2.穴形拡大教材 import 穴形拡大教材,guarded_hole_scale
from 接続.ARC2.既存穴形拡大 import _hole_scale_render
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.HDS接続 import 課題を解く,HDS学習実行系,候補機構を学習,出力格子,観測へ

形=[{(0,0)},{(0,0),(0,1)},{(0,0),(1,0),(1,1)}]
位置=[(2,2),(4,2),(2,5)]


def glyph(g,shape,scale,color,top,left):
    for r,c in shape:
        for dr in range(scale):
            for dc in range(scale):g[top+r*scale+dr][left+c*scale+dc]=color


def 教材(h=8,w=8,scale=2,colors=(1,2,3),map_color=8,bg=0):
    g=[[bg]*30 for _ in range(30)];small=[[map_color]*w for _ in range(h)]
    for r in range(h):
        for c in range(w):g[1+r][1+c]=map_color
    for i,(shape,(r0,c0),color)in enumerate(zip(形,位置,colors)):
        for r,c in shape:g[1+r0+r][1+c0+c]=bg;small[r0+r][c0+c]=color
        glyph(g,shape,scale,color,i*8,18)
    y=[[v for v in row for _ in range(scale)]for row in small for _ in range(scale)]
    return {'input':g,'output':y}


def 教師():return [教材(),教材(10,8)]


class 穴形拡大回帰(unittest.TestCase):
    def test_教師尺度2から入力尺度3も同じpriorで構成(self):
        for p in 教師()+[教材(9,8,3),教材(8,9,3,(4,5,6),2,9)]:
            out,rec=guarded_hole_scale(p['input']);self.assertEqual(out,p['output'])
            self.assertEqual(rec['hole_scale_template_count'],3)

    def test_D4で変えた配置と穴形状にも対応(self):
        p=教材(10,8,3)
        for name in ('flip_h','flip_v','transpose','rot90'):
            self.assertEqual(guarded_hole_scale(transform_grid_by_name(p['input'],name))[0],transform_grid_by_name(p['output'],name))

    def test_同じcanonical形の異色catalogはscaleを無効化(self):
        p=教材();glyph(p['input'],形[0],2,7,25,20)
        out,rec=guarded_hole_scale(p['input'])
        self.assertIsNone(out);self.assertEqual(rec['failure'],'hole_scale_missing_block_complete_templates')

    def test_複数の完全尺度から最初を選ばない(self):
        p=教材(colors=(1,2));glyph(p['input'],形[0],3,1,18,1);glyph(p['input'],形[1],3,2,23,10)
        out,rec=guarded_hole_scale(p['input'])
        self.assertIsNone(out);self.assertEqual(rec['failure'],'hole_scale_render_candidate_not_unique')
        self.assertEqual(rec['hole_scale_candidate_scales'],[2,3])

    def test_未対応穴を残した部分回答は出さない(self):
        p=教材()
        for r in range(30):
            for c in range(30):
                if p['input'][r][c]==3:p['input'][r][c]=0
        self.assertIsNone(guarded_hole_scale(p['input'])[0])

    def test_旧catalog下限は異なる形でなく物理成分数(self):
        p=教材(colors=(1,));p['input'][6][6]=0
        for r in range(10,12):
            for c in range(10,12):p['output'][r][c]=1
        self.assertIsNone(guarded_hole_scale(p['input'])[0])
        glyph(p['input'],形[0],2,1,25,20)
        out,rec=guarded_hole_scale(p['input'])
        self.assertEqual(out,p['output']);self.assertEqual(rec['hole_scale_template_count'],1)

    def test_containerの幾何同率を色番号で解決しない(self):
        p=教材();g=p['input']
        for r in range(8):
            for c in range(8):g[20+r][1+c]=9 if g[1+r][1+c]==8 else 0
        out,rec=guarded_hole_scale(g)
        self.assertIsNone(out);self.assertEqual(rec['failure'],'tied_container_geometry_rank')

    def test_選択mapの異色と不完全境界は保留(self):
        p=教材();p['input'][2][2]=7
        self.assertEqual(guarded_hole_scale(p['input'])[1]['failure'],'foreign_color_inside_map')
        p=教材();p['input'][1][3]=0
        self.assertEqual(guarded_hole_scale(p['input'])[1]['failure'],'map_border_not_complete')

    def test_上限を超えた最大mapから小さいmapへ逃げない(self):
        p=教材(11,8,3);g=p['input']
        for r in range(8):
            for c in range(8):g[20+r][1+c]=9
        for shape,(r0,c0)in zip(形,位置):
            for r,c in shape:g[20+r0+r][1+c0+c]=0
        raw,rec=_hole_scale_render(g);self.assertEqual(rec['hole_scale_output_shape'],[33,24])
        self.assertEqual(guarded_hole_scale(g)[1]['failure'],'scaled_output_exceeds_arc_bounds')
        for r in range(1,12):
            for c in range(1,9):g[r][c]=0
        self.assertIsNotNone(guarded_hole_scale(g)[0])

    def test_背景同率と不正入力は保留(self):
        for g in ([[0,1],[1,0]],[],[[0]*31],[[0,0],[0]],[[0]*5 for _ in range(5)]):
            self.assertIsNone(guarded_hole_scale(g)[0])

    def test_教師反例と重複を支持に入れない(self):
        ps=教師();ps[1]['output'][0][0]=1
        self.assertFalse(穴形拡大教材(ps).全教師再現)
        p=教材();self.assertFalse(穴形拡大教材([p,deepcopy(p)]).全教師再現)

    def test_穴やglyphではなく二教師の最終格子だけを観測(self):
        p=教材(9,8,3);r=課題を解く({'train':教師(),'test':[{'input':p['input']}]},[])
        self.assertEqual(r['results'][0]['answer'],p['output']);self.assertEqual(r['minimum_support'],2)
        f=next(f for f in r['families']if f['境界']=='ARC穴形拡大')
        self.assertEqual(f['現在観測数'],2);self.assertEqual(f['事前観測数'],0);self.assertTrue(f['同値採用'])

    def test_支持不足と後発反例はnativegateで保留(self):
        ps=教師();v=穴形拡大教材(ps);b='穴形拡大対照';e=HDS学習実行系()
        r=候補機構を学習(e,{'train':ps},[],b,v.候補);self.assertFalse(r['同値採用'])
        e=HDS学習実行系(最小支持数=2);r=候補機構を学習(e,{'train':ps},[],b,v.候補);self.assertTrue(r['同値採用'])
        e.実行(観測へ({'候補':ps[0]['output'],'出力':[[3]]},b))
        self.assertIsNone(出力格子(e,観測へ({'候補':ps[1]['output']},b),同値必須=True)['answer'])


if __name__=='__main__':unittest.main()
