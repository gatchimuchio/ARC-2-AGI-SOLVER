"""旧縦周期stripの全side証明・保存範囲・同一HDS盤面支持。"""
from pathlib import Path
import sys,unittest
from copy import deepcopy
from unittest.mock import patch
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 側周期教材 as m
from 接続.ARC2.既存側周期 import repeated_shape_vertical_side_periodic_extension as raw
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,出力格子,観測へ,課題を解く

def simple(second_color=4,same_column=False,height=14):
    g=[[8]*15 for _ in range(height)]
    for c in range(2,5):g[4][c]=1
    for c in range(2,5)if same_column else range(9,12):g[10][c]=1
    g[3][3]=2;g[9][3 if same_column else 10]=second_color
    return g

def pair(height=14):
    g=simple(height=height);out=deepcopy(g)
    for r in range(3):out[r][3]=2
    for r in range(9):out[r][10]=4
    return {'input':g,'output':out}

def key_collision():
    g=[[8]*20 for _ in range(20)]
    for c in range(2,5):g[10][c]=1
    for c in range(10,13):g[15][c]=1
    for rr,cc in ((4,3),(18,17)):
        for r in range(rr,rr+2):
            for c in range(cc,cc+2):g[r][c]=5
    g[9][3]=2
    return g

class 側周期回帰(unittest.TestCase):
    def test_合成完全格子と複数key(self):
        for h in (14,17,21):
            p=pair(h);out,r=m.guarded_render(p['input']);self.assertEqual(out,p['output']);self.assertEqual(r['key_count'],2)
            self.assertEqual(r['changed_pixels'],12)
    def test_幅二周期三と可変key寸法(self):
        g=[[8]*20 for _ in range(26)]
        for r,c in ((8,2),(20,12)):
            for cc in range(c,c+4):g[r][cc]=1
        period=[(2,3),(4,5),(6,7)]
        for r,vals in zip((19,18,17),period):g[r][13:15]=vals
        expected=deepcopy(g)
        for r in range(17):expected[r][13:15]=period[(19-r)%3]
        out,z=m.guarded_render(g);self.assertEqual(out,expected)
        self.assertEqual(next(e['period']for e in z['events']if 'period'in e),[list(t)for t in period])
    def test_固定縦向きを保つ反転と配色(self):
        p=pair()
        for v in (False,True):
            for h in (False,True):
                for colour in (False,True):
                    def t(g):return [[(x+3)%10 if colour else x for x in(row[::-1]if h else row)]for row in(g[::-1]if v else g)]
                    self.assertEqual(m.guarded_render(t(p['input']))[0],t(p['output']))
    def test_非連続sideを捨てず全体HOLD(self):
        g=simple();g[3][3]=8;g[3][2]=2;g[3][4]=3
        self.assertNotEqual(raw(g)[0],g);self.assertEqual(m.guarded_render(g)[1]['failure'],'noncontiguous_adjacent_payload')
    def test_inactiveと無変化sideも記録する(self):
        g=simple()
        for r in range(3):g[r][3]=2
        out,z=m.guarded_render(g);self.assertIsNotNone(out)
        self.assertEqual(sum('inactive'in e for e in z['events']),2)
        self.assertEqual(sum('period'in e for e in z['events']),2);self.assertEqual(len(z['raw_records']),1)
    def test_同色proposalは和集合(self):
        g=simple(2,True);out,z=m.guarded_render(g);self.assertEqual(out,raw(g)[0]);self.assertIsNotNone(out)
        self.assertLess(z['proposal_cells'],sum(e.get('proposal_count',0)for e in z['events']))
    def test_異色proposalは全体HOLD(self):
        g=simple(4,True);self.assertNotEqual(raw(g)[0],g)
        self.assertEqual(m.guarded_render(g)[1]['failure'],'proposal_colour_conflict')
    def test_全key_seed_提案外の保存(self):
        g=simple();g[12][0]=5;out,z=m.guarded_render(g)
        self.assertEqual(out[12][0],5)
        for c in range(2,5):self.assertEqual(out[4][c],1)
        for c in range(9,12):self.assertEqual(out[10][c],1)
        self.assertEqual(out[3][3],2);self.assertEqual(out[9][10],4)
    def test_strip内元payloadは規約どおり上書き(self):
        g=simple();g[1][3]=5;out,z=m.guarded_render(g)
        self.assertEqual(out[1][3],2);self.assertEqual(z['changed_original_payload'],1)
    def test_元最小prefix周期(self):
        g=simple()
        for r,c in zip((3,2,1,0),(2,3,2,3)):g[r][3]=c
        out,z=m.guarded_render(g);self.assertIsNotNone(out)
        e=next(e for e in z['events']if e.get('columns')==[3]);self.assertEqual(e['period'],[[2],[3]])
    def test_size二成分は元認識域外で外側保存(self):
        g=simple()
        for c in (0,1,6,7):g[12][c]=5
        out,z=m.guarded_render(g);self.assertIsNotNone(out);self.assertEqual(z['key_group_count'],1);self.assertEqual(out[12],g[12])
    def test_別group_keyも保護(self):
        g=key_collision();self.assertNotEqual(raw(g)[0][4][3],g[4][3])
        self.assertEqual(m.guarded_render(g)[1]['failure'],'key_changed')
    def test_入力背景nochangeと元格子限定(self):
        for bad in ([],[[]],[[0],[0,1]],[[True]],[[10]],[[0]*31],[[0]]*31,None):
            self.assertEqual(m.guarded_render(bad)[1]['failure'],'invalid_arc_grid')
        self.assertEqual(m.guarded_render([[0,1],[1,0]])[1]['failure'],'background_tie')
        self.assertEqual(m.guarded_render(pair()['output'])[1]['failure'],'no_change')
        g=simple();out,rec=raw(g);out[13][14]=9
        with patch.object(m,'repeated_shape_vertical_side_periodic_extension',return_value=(out,rec)):
            self.assertEqual(m.guarded_render(g)[1]['failure'],'source_grid_disagreement')
    def test_二盤面支持と重複拒否および反例隔離(self):
        pairs=[pair(14),pair(15)];self.assertFalse(m.側周期教材(pairs[:1]).成立);self.assertFalse(m.側周期教材([pairs[0]]*2).成立)
        view=m.側周期教材(pairs);boundary='側周期対照';engine=HDS学習実行系(最小支持数=3)
        self.assertFalse(候補機構を学習(engine,{'train':pairs},[],boundary,view.候補)['同値採用'])
        engine=HDS学習実行系(最小支持数=2);r=候補機構を学習(engine,{'train':pairs},[],boundary,view.候補)
        self.assertEqual(r['現在観測数'],2);self.assertEqual(r['事前観測数'],0);self.assertTrue(r['採用可']);self.assertTrue(r['同値採用'])
        q=pairs[0]['output'];self.assertEqual(出力格子(engine,観測へ({'候補':q},boundary),同値必須=True)['answer'],q)
        engine.実行(観測へ({'候補':q,'出力':[[9]]},boundary));self.assertIsNone(出力格子(engine,観測へ({'候補':q},boundary),同値必須=True)['answer'])
    def test_採用済み未解決は全体HOLDと情報分離(self):
        task={'train':[pair(14),pair(15)],'test':[{'input':simple(4,True)}]};result=課題を解く(task,[])
        r=next(r for r in result['families']if r['境界']=='ARC反復形側周期延長');self.assertTrue(r['同値採用']);self.assertIsNone(result['results'][0]['answer'])
        task['task_id']='forbidden'
        with self.assertRaises(ValueError):課題を解く(task,[])
        task.pop('task_id');task['test'][0]['output']=[[1]]
        with self.assertRaises(ValueError):課題を解く(task,[])

if __name__=='__main__':unittest.main()
