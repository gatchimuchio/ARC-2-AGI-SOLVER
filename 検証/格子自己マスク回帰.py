"""固定32候補の役割・anchor・合意と既存HDS排気の対照。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 格子自己マスク as view
from 接続.ARC2.HDS接続 import HDS学習実行系, 観測へ, 課題を解く, 候補機構を学習, 出力格子

U=((1,0,1),(1,1,1))
H=((1,0,1),(1,1,1),(1,0,1))
T=((0,1,0),(1,1,1),(1,0,1))
モデル=('common_background','exclusive','identity')


def 作る(mask=U, macro=(5,6), origin=(1,2), seeds=None, colors=(9,4,3,1)):
    sep,base,source,shared=colors;h,w=len(mask),len(mask[0]);mh,mw=macro
    if seeds is None:seeds={(1,c)for c in range(w)}
    a=[[base]*w for _ in range(h)];a[0][0]=shared
    b=[[source if x else shared for x in row]for row in mask]
    def canvas(active):
        g=[[sep]*(mw*(w+1)+1)for _ in range(mh*(h+1)+1)]
        for r in range(mh):
            for c in range(mw):
                tile=b if (r,c)in active else a
                for y,row in enumerate(tile):g[1+r*(h+1)+y][1+c*(w+1):1+c*(w+1)+w]=row
        return g
    active={(origin[0]+r,origin[1]+c)for r,row in enumerate(mask)for c,v in enumerate(row)if v}
    given={(origin[0]+r,origin[1]+c)for r,c in seeds}
    return {'input':canvas(given),'output':canvas(active)}


def 教師():
    return [作る(),作る(H,(5,5),(1,1),colors=(7,8,6,2)),
            作る(T,(7,7),(2,1),seeds={(1,0),(1,1),(1,2),(2,0)},colors=(5,2,8,4))]


class 格子自己マスク回帰(unittest.TestCase):
    def test_可変寸法と配色から入力自己maskを読む(self):
        v=view.格子自己マスク教材(教師())
        self.assertEqual(set(v.モデル群),{モデル,('common_background','exclusive','flip_h')})
        q=作る(H,(6,5),(2,1),colors=(0,2,7,8))
        self.assertEqual(v.候補(q['input'],{})[0],q['output'])

    def test_全separatorと既存seedを保持(self):
        p=作る();q,tiles,counts=view.格子を読む(p['input'])
        out,_=view.配置候補(p['input'],モデル)
        for r in range(len(out)):
            for c in range(len(out[0])):
                if r in q['separator_rows']or c in q['separator_cols']:
                    self.assertEqual(out[r][c],p['input'][r][c])
        source=min(counts,key=counts.get)
        for i,(r0,r1)in enumerate(q['row_segments']):
            for j,(c0,c1)in enumerate(q['col_segments']):
                if tiles[i][j]==source:self.assertEqual(view.格子鍵([r[c0:c1+1]for r in out[r0:r1+1]]),source)

    def test_頻度同率と第三種類と不等寸法は保留(self):
        p=作る(U,(2,2),(0,0),seeds={(1,0),(1,1)})
        self.assertIsNone(view.配置候補(p['input'],モデル)[0])
        p=作る();p['input'][1][2]=6
        self.assertIsNone(view.配置候補(p['input'],モデル)[0])
        p=作る();p['input'].insert(2,p['input'][2][:])
        self.assertIsNone(view.配置候補(p['input'],モデル)[0])

    def test_anchorなし又は複数を保留(self):
        for seeds,empty in (({(0,0)},False),({(0,0),(0,1),(0,2),(1,0),(1,1),(1,2)},True)):
            p=作る(seeds=seeds);out,detail=view.配置候補(p['input'],モデル)
            self.assertIsNone(out)
            self.assertEqual(detail['anchors']==0,empty)

    def test_教師同値の二モデルがqueryで競合(self):
        v=view.格子自己マスク教材(教師());mask=((1,1,0),(1,1,1))
        p=作る(mask,seeds={(1,0),(1,1),(1,2)})
        out,detail=v.候補(p['input'],{})
        self.assertIsNone(out);self.assertEqual(detail['failure'],'教師整合モデル間の予測競合')

    def test_一モデルだけ失敗しても無視しない(self):
        v=view.格子自己マスク教材(教師());mask=((1,1,0),(1,1,1))
        p=作る(mask,seeds={(0,0),(1,0),(1,2)})
        self.assertIsNotNone(view.配置候補(p['input'],モデル)[0])
        out,detail=v.候補(p['input'],{})
        self.assertIsNone(out);self.assertEqual(detail['failure'],'教師整合モデルが未確定')

    def test_同一HDSで教師観測をモデル数で複製しない(self):
        p=作る(H,(6,5),(2,1),colors=(0,2,7,8))
        r=課題を解く({'train':教師(),'test':[{'input':p['input']}]},[])
        self.assertEqual(r['results'][0]['answer'],p['output'])
        f=next(f for f in r['families']if f['境界']=='ARC格子自己マスク')
        self.assertEqual(f['現在観測数'],3);self.assertEqual(f['事前観測数'],0)
        self.assertTrue(f['同値採用']);self.assertEqual(r['minimum_support'],3)

    def test_既定支持不足と後発反例はHOLD(self):
        v=view.格子自己マスク教材(教師());e=HDS学習実行系();boundary='格子対照'
        p=作る(H,(6,5),(2,1),colors=(0,2,7,8))
        r=候補機構を学習(e,{'train':教師()[:2]},[],boundary,v.候補)
        self.assertFalse(r['同値採用'])
        e=HDS学習実行系();候補機構を学習(e,{'train':教師()},[],boundary,v.候補)
        e.実行(観測へ({'候補':教師()[0]['output'],'出力':[[8]]},boundary))
        self.assertIsNone(出力格子(e,観測へ({'候補':p['output']},boundary),同値必須=True)['answer'])

    def test_重複教師と不一致教師は採用しない(self):
        p=教師()[0]
        self.assertFalse(view.格子自己マスク教材([p,deepcopy(p)]).モデル群)
        ps=教師();ps[-1]['output'][0][0]=9
        self.assertFalse(view.格子自己マスク教材(ps).モデル群)


if __name__=='__main__':unittest.main()
