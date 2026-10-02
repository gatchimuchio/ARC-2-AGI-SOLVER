"""新しい格子写像の全parameter保持・全model合意・native盤面支持。"""
from pathlib import Path
import sys,unittest
from copy import deepcopy
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 正方形格子教材 as m
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,出力格子,観測へ,課題を解く

def block(grid,r,c,size,color):
    for rr in range(r,r+size):
        for cc in range(c,c+size):grid[rr][cc]=color

def pair(n=0,a=1,b=2,pitch=3):
    grid=[[0]*(25+n)for _ in range(25+n)]
    for r,c,color in ((1,1,2),(1,1+a+1,3),(1+a+1,1,4),(1+a+1,1+a+1,5)):
        block(grid,r,c,a,color)
    block(grid,11+n,12,b,2);block(grid,11+n,12+pitch,b,3)
    out=deepcopy(grid);block(out,11+n+pitch,12,b,4);block(out,11+n+pitch,12+pitch,b,5)
    return {'input':grid,'output':out}

def repeated_grid(top=15):
    grid=[[0]*30 for _ in range(30)]
    for r in (0,2,4):
        for c in (0,2,4):grid[r][c]=2
    block(grid,top,15,2,2);block(grid,top,21,2,2)
    return grid

def symmetric_pair():
    grid=[[0]*25 for _ in range(25)]
    for r,c,color in ((1,1,2),(1,3,2),(3,1,4),(3,3,4)):
        grid[r][c]=color
    block(grid,10,12,2,2);block(grid,10,16,2,2)
    out=deepcopy(grid);block(out,14,12,2,4);block(out,14,16,2,4)
    return {'input':grid,'output':out}

def remap(grid):return [[(v+4)%10 for v in row]for row in grid]

class 正方形格子回帰(unittest.TestCase):
    def test_全教師共通規則と入力由来parameter(self):
        pairs=[pair(i)for i in range(3)];models,rec=m.fit_models(pairs)
        self.assertEqual(models,('rot0',))
        for i,p in enumerate(pairs):
            out,r=m.render_model(p['input'],'rot0');self.assertEqual(out,p['output'])
            self.assertEqual(r['seed_parameters'],[[3,11+i,12]])
            self.assertEqual(r['component_count'],6)
    def test_side倍率とpitch独立でsingletonに固定しない(self):
        p=pair(a=2,b=3,pitch=5);out,r=m.render_model(p['input'],'rot0')
        self.assertEqual(out,p['output']);self.assertEqual(r['source_pitch'],[3,3]);self.assertEqual(r['seed_parameters'],[[5,11,12]])
    def test_配色とD4と可変canvas(self):
        for i in range(3):
            p=pair(i)
            for k in range(8):
                def transform(grid):
                    out=[row[::-1]if k//4 else row[:]for row in grid]
                    for _ in range(k%4):out=[list(row)for row in zip(*out[::-1])]
                    return remap(out)
                self.assertEqual(m.render_model(transform(p['input']),'rot0')[0],transform(p['output']))
    def test_全seedparameter異格子ならHOLD(self):
        out,r=m.render_model(repeated_grid(),'rot0');self.assertIsNone(out)
        self.assertEqual(r['seed_parameter_count'],9);self.assertEqual(r['failed_parameters'],0)
        self.assertEqual(r['failure'],'seed_parameter_grids_disagree')
    def test_一parameter失敗を捨てて選ばない(self):
        out,r=m.render_model(repeated_grid(8),'rot0');self.assertIsNone(out)
        self.assertGreater(r['failed_parameters'],0);self.assertGreater(r['distinct_output_count'],0)
        self.assertEqual(r['failure'],'seed_consistent_parameter_failed')
    def test_列挙seed順はparameter集合を変えない(self):
        parsed,_=m.parse_input(repeated_grid());a=m.seed_parameters(parsed,'rot0')[1]
        parsed['seeds'].reverse();self.assertEqual(a,m.seed_parameters(parsed,'rot0')[1])
    def test_対称modelを保持し競合と一失敗を全体HOLD(self):
        p=symmetric_pair();models,_=m.fit_models([p,{k:remap(v)for k,v in p.items()}])
        self.assertEqual(models,('rot0','rot0_flip_h'))
        self.assertEqual(m.consensus(p['input'],models)[0],p['output'])
        q=pair()['input'];out,r=m.consensus(q,models)
        self.assertIsNone(out);self.assertEqual(r['failure'],'retained_model_unresolved')
        q=deepcopy(p['input']);q[3][3]=5
        out,r=m.consensus(q,models);self.assertIsNone(out);self.assertEqual(r['failure'],'retained_model_grids_disagree')
    def test_noopは全合意後に規則全体HOLD(self):
        out,r=m.render_model(pair()['output'],'rot0');self.assertIsNone(out)
        self.assertEqual(r['distinct_output_count'],1);self.assertEqual(r['failure'],'consensus_no_change')
    def test_同色でもsource領域を覆わない(self):
        g=[[0]*20 for _ in range(20)]
        for r,c,color in ((5,5,4),(5,9,3),(9,5,4),(9,9,5)):g[r][c]=color
        block(g,1,5,2,4);block(g,1,8,2,3)
        out,z=m.render_model(g,'rot0');self.assertIsNone(out)
        self.assertEqual(z['seed_parameters'],[[3,1,5]])
        self.assertEqual(z['parameter_records'][0]['failure'],'source_overlap')
    def test_全componentと軸間隔を検査(self):
        g=pair()['input'];g[11][11]=2
        self.assertEqual(m.parse_input(g)[1]['failure'],'not_all_solid_squares')
        g=pair()['input'];g[6][1]=4
        self.assertEqual(m.parse_input(g)[1]['failure'],'source_axis_not_uniform')
        g=pair()['input'];block(g,18,1,3,6)
        self.assertEqual(m.parse_input(g)[1]['failure'],'not_two_square_sizes')
    def test_入力検査背景tieとseed不足(self):
        for bad in ([],[[0],[0,1]],[[True]],[[10]]):self.assertEqual(m.parse_input(bad)[1]['failure'],'invalid_grid')
        self.assertEqual(m.parse_input([[0,1],[1,0]])[1]['failure'],'background_tie')
        g=pair()['input'];block(g,11,15,2,0)
        self.assertEqual(m.parse_input(g)[1]['failure'],'too_few_seeds')
    def test_最低二教師と入力重複拒否(self):
        p=pair();self.assertFalse(m.正方形格子教材([p]).モデル)
        self.assertFalse(m.正方形格子教材([p,p]).モデル)
        pairs=[pair(i)for i in range(3)];pairs[2]['output'][0][0]=9
        self.assertFalse(m.正方形格子教材(pairs).モデル)
    def test_native支持は三盤面でseedや候補数で増やさない(self):
        pairs=[pair(i)for i in range(3)];view=m.正方形格子教材(pairs);boundary='正方形格子対照'
        engine=HDS学習実行系(最小支持数=3)
        self.assertFalse(候補機構を学習(engine,{'train':pairs[:2]},[],boundary,view.候補)['同値採用'])
        engine=HDS学習実行系(最小支持数=3);r=候補機構を学習(engine,{'train':pairs},[],boundary,view.候補)
        self.assertTrue(r['同値採用']);self.assertTrue(r['採用可']);self.assertEqual(r['現在観測数'],3);self.assertEqual(r['事前観測数'],0)
        q=pairs[0]['output'];self.assertEqual(出力格子(engine,観測へ({'候補':q},boundary),同値必須=True)['answer'],q)
        engine.実行(観測へ({'候補':q,'出力':[[9]]},boundary))
        self.assertIsNone(出力格子(engine,観測へ({'候補':q},boundary),同値必須=True)['answer'])
    def test_採用済み未解決query全体HOLDと情報分離(self):
        task={'train':[pair(i)for i in range(3)],'test':[{'input':repeated_grid()}]}
        result=課題を解く(task,[]);r=next(r for r in result['families']if r['境界']=='ARC正方形格子写像')
        self.assertTrue(r['同値採用']);self.assertEqual(r['現在観測数'],3);self.assertIsNone(result['results'][0]['answer'])
        task['task_id']='forbidden'
        with self.assertRaises(ValueError):課題を解く(task,[])
        task.pop('task_id');task['test'][0]['output']=[[1]]
        with self.assertRaises(ValueError):課題を解く(task,[])

if __name__=='__main__':unittest.main()
