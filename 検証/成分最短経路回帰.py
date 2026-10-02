"""既存の型付きgraph・唯一最短経路・教師共有paletteの対照。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 既存成分最短経路 as graph
from 接続.ARC2.成分経路教材 import 成分経路教材,背景が一意
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.HDS接続 import 課題を解く,HDS学習実行系,候補機構を学習,出力格子,観測へ


def 教材(size=2,blocks=3,colors=(8,1,2,0),outputs=(3,5),offpath=True):
    bg,terminal,block,connector=colors;n=blocks+2;w=n*size+(n-1)*2+2;h=2*size+5
    g=[[bg]*w for _ in range(h)];y=deepcopy(g);row=1;wire_row=1+size//2
    for i in range(n):
        col=1+i*(size+2);role=terminal if i in(0,n-1)else block;out=terminal if role==terminal else outputs[0]
        for r in range(row,row+size):
            for c in range(col,col+size):g[r][c]=role;y[r][c]=out
        if i<n-1:
            for c in range(col+size,col+size+2):g[wire_row][c]=connector;y[wire_row][c]=outputs[1]
    if offpath:
        for r in range(size+4,size+4+size):
            for c in range(4,4+size):g[r][c]=block;y[r][c]=block
    return {'input':g,'output':y}


def 教師():
    return [教材(),教材(blocks=1,colors=(9,6,7,4),offpath=False),教材(size=3,colors=(7,2,1,6))]


def 二経路():
    g=[[8]*21 for _ in range(15)]
    for r,c,color in [(6,1,1),(6,18,1),(2,9,2),(10,9,2),(12,5,2)]:
        for y in range(r,r+2):
            for x in range(c,c+2):g[y][x]=color
    cells=({(r,1)for r in range(3,6)}|{(3,c)for c in range(2,9)}
           |{(3,c)for c in range(11,19)}|{(r,18)for r in range(4,6)}
           |{(r,1)for r in range(8,11)}|{(10,c)for c in range(2,9)}
           |{(11,c)for c in range(11,19)}|{(r,18)for r in range(8,11)})
    for r,c in cells:g[r][c]=0
    return g


class 成分最短経路回帰(unittest.TestCase):
    def test_全D4と大きさ配色を変えて経路を選ぶ(self):
        v=成分経路教材(教師());self.assertEqual(v.出力色対,(3,5))
        for size in (2,3):
            p=教材(size=size,colors=(4,0,9,1))
            for name in ('identity','rot90','rot180','rot270','flip_h','flip_v','transpose','anti_transpose'):
                self.assertEqual(v.候補(transform_grid_by_name(p['input'],name),{})[0],transform_grid_by_name(p['output'],name))

    def test_同距離経路を最初の一つで断定しない(self):
        p,rec=graph.terminal_square_path_policy(二経路())
        self.assertIsNone(p);self.assertEqual(rec['failure'],'non_unique_shortest_path_between_terminal_squares')

    def test_端点role曖昧と追加色を拒否(self):
        p,rec=graph.terminal_square_path_policy(教材(blocks=2,offpath=False)['input'])
        self.assertIsNone(p);self.assertEqual(rec['failure'],'terminal_square_path_terminal_color_not_unique')
        g=教材()['input'];g[-1][-1]=7
        self.assertIsNone(graph.terminal_square_path_policy(g)[0])

    def test_非接続を保留(self):
        g=教材()['input'];g[2][3:5]=[8,8]
        p,rec=graph.terminal_square_path_policy(g)
        self.assertIsNone(p);self.assertEqual(rec['failure'],'no_path_between_terminal_squares')

    def test_背景同率と空入力は拒否(self):
        v=成分経路教材(教師())
        for g in ([],[[0,1],[1,0]]):
            self.assertFalse(背景が一意(g));self.assertIsNone(v.候補(g,{})[0])

    def test_教師palette不一致と重複は採用しない(self):
        ps=教師();ps[-1]=教材(size=3,colors=(7,2,1,6),outputs=(4,5))
        self.assertIsNone(成分経路教材(ps).出力色対)
        p=教師()[0];self.assertIsNone(成分経路教材([p,deepcopy(p)]).出力色対)
        ps=教師();ps[-1]['output'][0][0]=0
        self.assertIsNone(成分経路教材(ps).出力色対)

    def test_出力色衝突と入力既出色は拒否(self):
        g=教材()['input']
        for colors in ((3,3),(1,5),(3,0)):
            self.assertIsNone(graph.render_terminal_square_component_path_recolorer(g,*colors)[0])

    def test_経路外と端点と背景を保存(self):
        p=教材();policy,_=graph.terminal_square_path_policy(p['input']);out,_=graph.render_terminal_square_component_path_recolorer(p['input'],3,5)
        changed=set().union(*(policy['components'][i]['cells']for i in policy['path_indices'][1:-1]))
        self.assertGreater(len(changed),0)
        for r,row in enumerate(p['input']):
            for c,value in enumerate(row):
                if (r,c)not in changed:self.assertEqual(out[r][c],value)
                else:self.assertNotEqual(out[r][c],value)

    def test_同一HDSにnode数でなく三教師を観測(self):
        p=教材(size=3,colors=(4,0,9,1));r=課題を解く({'train':教師(),'test':[{'input':p['input']}]},[])
        self.assertEqual(r['results'][0]['answer'],p['output'])
        f=next(f for f in r['families']if f['境界']=='ARC成分最短経路')
        self.assertEqual(f['現在観測数'],3);self.assertEqual(f['事前観測数'],0);self.assertTrue(f['同値採用'])

    def test_既定支持不足と後発反例はHOLD(self):
        v=成分経路教材(教師());e=HDS学習実行系();b='経路対照'
        r=候補機構を学習(e,{'train':教師()[:2]},[],b,v.候補);self.assertFalse(r['同値採用'])
        e=HDS学習実行系();候補機構を学習(e,{'train':教師()},[],b,v.候補)
        e.実行(観測へ({'候補':教師()[0]['output'],'出力':[[3]]},b))
        p=教材(size=3,colors=(4,0,9,1))
        self.assertIsNone(出力格子(e,観測へ({'候補':p['output']},b),同値必須=True)['answer'])


if __name__=='__main__':unittest.main()
