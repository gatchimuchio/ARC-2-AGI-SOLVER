"""全辞書・有限軌道・全前景保存とnative教師盤面支持の回帰。"""
import copy,unittest,itertools
from unittest.mock import patch
from pathlib import Path
import sys
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 凡例旋回教材 as g
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,課題を解く
TEACHER_INPUTS=[[[5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5], [5, 1, 0, 0, 0, 5, 5, 6, 0, 0, 0, 5, 5, 4, 0, 0, 0, 5, 5, 2, 0, 0, 0, 5], [5, 1, 0, 0, 0, 5, 5, 6, 0, 0, 0, 5, 5, 4, 0, 0, 0, 5, 5, 2, 0, 0, 0, 5], [5, 1, 0, 0, 0, 5, 5, 6, 0, 0, 0, 5, 5, 4, 0, 0, 0, 5, 5, 2, 0, 0, 0, 5], [5, 1, 0, 0, 0, 5, 5, 6, 0, 0, 0, 5, 5, 4, 0, 0, 0, 5, 5, 2, 0, 0, 0, 5], [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5], [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3], [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3], [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3], [1, 1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3], [1, 1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 3, 3], [1, 1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 3, 3], [1, 1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 3, 3], [1, 1, 1, 1, 3, 3, 3, 3, 8, 8, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 3, 3], [1, 1, 1, 1, 3, 3, 3, 3, 8, 8, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 3, 3], [1, 1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 3, 3], [1, 1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 3, 3], [1, 1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3], [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3], [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3], [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3], [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3], [3, 3, 3, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3], [3, 3, 3, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3], [3, 3, 3, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3]], [[5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5], [5, 0, 0, 0, 2, 5, 5, 4, 0, 0, 0, 5, 5, 0, 0, 0, 6, 5, 5, 3, 0, 0, 0, 5], [5, 0, 0, 0, 2, 5, 5, 4, 0, 0, 0, 5, 5, 0, 0, 0, 6, 5, 5, 3, 0, 0, 0, 5], [5, 0, 0, 0, 2, 5, 5, 4, 0, 0, 0, 5, 5, 0, 0, 0, 6, 5, 5, 3, 0, 0, 0, 5], [5, 0, 0, 0, 2, 5, 5, 4, 0, 0, 0, 5, 5, 0, 0, 0, 6, 5, 5, 3, 0, 0, 0, 5], [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5], [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 6, 6, 6, 6, 6, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 6, 6, 6, 6, 6, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], [2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 3, 3, 3, 3, 1, 1, 1, 1], [2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 3, 3, 3, 3, 1, 1, 1, 1], [2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 3, 3, 3, 3, 1, 1, 1, 1], [2, 2, 2, 2, 1, 1, 1, 1, 8, 8, 1, 1, 1, 1, 1, 1, 3, 3, 3, 3, 1, 1, 1, 1], [2, 2, 2, 2, 1, 1, 1, 1, 8, 8, 1, 1, 1, 1, 1, 1, 3, 3, 3, 3, 1, 1, 1, 1], [2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 3, 3, 3, 3, 1, 1, 1, 1], [2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 4, 4, 4, 4, 4, 4, 4, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 4, 4, 4, 4, 4, 4, 4, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 4, 4, 4, 4, 4, 4, 4, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]], [[5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5], [5, 0, 0, 0, 4, 5, 5, 6, 0, 0, 0, 5, 5, 3, 0, 0, 0, 5, 5, 0, 0, 0, 2, 5], [5, 0, 0, 0, 4, 5, 5, 6, 0, 0, 0, 5, 5, 3, 0, 0, 0, 5, 5, 0, 0, 0, 2, 5], [5, 0, 0, 0, 4, 5, 5, 6, 0, 0, 0, 5, 5, 3, 0, 0, 0, 5, 5, 0, 0, 0, 2, 5], [5, 0, 0, 0, 4, 5, 5, 6, 0, 0, 0, 5, 5, 3, 0, 0, 0, 5, 5, 0, 0, 0, 2, 5], [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5], [7, 7, 7, 7, 7, 7, 7, 7, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 7, 7, 7, 7, 7, 7], [7, 7, 7, 7, 7, 7, 7, 7, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 7, 7, 7, 7, 7, 7], [7, 7, 7, 7, 7, 7, 7, 7, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 7, 7, 7, 7, 7, 7], [7, 7, 7, 7, 7, 7, 7, 7, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 7, 7, 6, 6, 6, 6], [7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 6, 6, 6, 6], [7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 6, 6, 6, 6], [7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 6, 6, 6, 6], [2, 2, 2, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 6, 6, 6, 6], [2, 2, 2, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 6, 6, 6, 6], [2, 2, 2, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 6, 6, 6, 6], [2, 2, 2, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 6, 6, 6, 6], [2, 2, 2, 7, 7, 7, 7, 7, 7, 7, 7, 7, 8, 8, 7, 7, 7, 7, 7, 7, 6, 6, 6, 6], [2, 2, 2, 7, 7, 7, 7, 7, 7, 7, 7, 7, 8, 8, 7, 7, 7, 7, 7, 7, 6, 6, 6, 6], [2, 2, 2, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 6, 6, 6, 6], [2, 2, 2, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7], [2, 2, 2, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7], [2, 2, 2, 7, 7, 7, 7, 7, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 7, 7], [2, 2, 2, 7, 7, 7, 7, 7, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 7, 7], [2, 2, 2, 7, 7, 7, 7, 7, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 7, 7]]]
TRAIN=[{"input":x,"output":g._legend_guided_turning_corridor_render(x)[0]}for x in TEACHER_INPUTS]

def fixture(entries=2,size=3):
    w=6*entries;h=20;keys=[2,3,4,6,7][:entries];control=[[0]*w for _ in range(6)]
    for index,key in enumerate(keys):
        left=6*index
        for r in range(6):
            for c in range(6):
                if r in(0,5)or c in(0,5):control[r][left+c]=5
        for r in range(1,5):control[r][left+(1 if index%2==0 else 4)]=key
    body=[[1]*w for _ in range(h)];sr=8;sc=(w-size)//2
    for r in range(sr,sr+size):
        for c in range(sc,sc+size):body[r][c]=8
    body[1][sc]=keys[0]
    return control+body

class Controls(unittest.TestCase):
    def test_01_teacher_complete(self):
        model,record=g.fit_teachers(TRAIN);self.assertEqual(model,{'program':'legend_guided_turning_corridor'})
        for pair,n in zip(TRAIN,[112,120,134]):
            out,r=g.guarded_render(pair['input']);self.assertEqual(out,pair['output']);self.assertEqual(r['proposal_union'],n);self.assertEqual(r['dictionary_cells'],144)
            self.assertEqual(len(r['rays']),4);self.assertTrue(all(x['termination']=='body_bounds'for x in r['rays']))
    def test_02_dictionary_counts_and_seed_size(self):
        for entries,size in[(2,2),(2,3),(5,3)]:
            x=fixture(entries,size);out,r=g.guarded_render(x);self.assertIsNotNone(out,r);self.assertEqual(r['dictionary_cells'],36*entries);self.assertEqual(r['seed_pixels'],size*size)
            self.assertGreater(r['proposal_union'],0)
    def test_03_nonzero_colour_permutation(self):
        perm={0:0,**{x:(x+3)%9+1 for x in range(1,10)}}
        for p in TRAIN:
            x=[[perm[v]for v in row]for row in p['input']];y=[[perm[v]for v in row]for row in p['output']];self.assertEqual(g.guarded_render(x)[0],y)
    def test_04_cross_region_alias_allowed(self):
        x=copy.deepcopy(TRAIN[0]['input'])
        for row in x[:6]:
            for c,v in enumerate(row):
                if v==5:row[c]=3
        self.assertIsNotNone(g.guarded_render(x)[0])
        x=fixture()
        for row in x[6:]:
            for c,v in enumerate(row):
                if v==1:row[c]=0
        self.assertIsNotNone(g.guarded_render(x)[0])
    def test_05_unused_dictionary_kept(self):
        out,r=g.guarded_render(TRAIN[0]['input']);self.assertIsNotNone(out);self.assertEqual(r['unused_dictionary_colours'],[6]);self.assertEqual(len(r['raw_record']['legend_corridor_panel_records']),4)
    def test_06_initial_obstacle(self):
        x=copy.deepcopy(TRAIN[0]['input']);x[11][8]=6
        self.assertIsNotNone(g._legend_guided_turning_corridor_render(x)[0]);self.assertEqual(g.guarded_render(x)[1]['failure'],'initial_block_obstacle_overlap')
    def test_07_initial_oob(self):
        x=copy.deepcopy(TRAIN[0]['input'])
        for r in[13,14]:
            for c in[8,9]:x[r][c]=3
        for r in[6,7]:
            for c in[8,9]:x[r][c]=8
        self.assertIsNotNone(g._legend_guided_turning_corridor_render(x)[0]);self.assertEqual(g.guarded_render(x)[1]['failure'],'initial_block_out_of_bounds')
    def test_08_background_key_alias(self):
        x=copy.deepcopy(TRAIN[0]['input'])
        for r in range(1,5):x[r][7]=3
        self.assertIsNotNone(g._legend_guided_turning_corridor_render(x)[0]);self.assertEqual(g.guarded_render(x)[1]['failure'],'body_background_key_alias')
    def test_09_mode_ties(self):
        x=fixture();x[:6]=[[1 if(r+c)%2 else 2 for c in range(12)]for r in range(6)];self.assertEqual(g.guarded_render(x)[1]['failure'],'guide_mode_tie')
        x=fixture();x[6:]=[[0 if c%2 else 1 for c in range(12)]for r in range(20)];self.assertEqual(g.guarded_render(x)[1]['failure'],'body_background_tie')
    def test_10_control_and_body_coverage(self):
        x=fixture();x[2][2]=9;self.assertEqual(g.guarded_render(x)[1]['failure'],'dictionary_key_bar_unresolved')
        x=fixture();x[6+18][10]=9;self.assertEqual(g.guarded_render(x)[1]['failure'],'body_component_unowned')
        x=fixture();x[7][5]=2;x[8][5]=2;self.assertEqual(g.guarded_render(x)[1]['failure'],'body_component_not_rectangle')
    def test_11_multicolour_hit(self):
        body=[[0]*7 for _ in range(7)];obstacles={(1,2):2,(1,3):3};body[1][2]=2;body[1][3]=3
        paint,r=g.trace_ray(body,0,2,(0,2,2),{2:'left',3:'right'},obstacles);self.assertIsNone(paint);self.assertEqual(r['failure'],'trajectory_multicolour_hit')
    def test_12_cycle(self):
        body=[[0]*8 for _ in range(8)];obstacles={(1,3):2,(2,1):2,(4,2):2,(3,4):2}
        for(r,c),v in obstacles.items():body[r][c]=v
        paint,r=g.trace_ray(body,0,2,(0,2,2),{2:'left'},obstacles);self.assertIsNone(paint);self.assertEqual(r['failure'],'trajectory_cycle')
    def test_13_all_ray_orders_same_union(self):
        x=fixture();out,r=g.guarded_render(x);self.assertIsNotNone(out);body=x[6:];bg=r['raw_record']['legend_corridor_background_color'];turns={p['marker_color']:p['turn']for p in r['raw_record']['legend_corridor_panel_records']};obstacles={(a,b):v for a,row in enumerate(body)for b,v in enumerate(row)if v in turns};results=[g.trace_ray(body,bg,3,tuple(s),turns,obstacles)[0]for s in r['initial_blocks']]
        self.assertTrue(all(v is not None for v in results))
        for order in itertools.permutations(range(4)):
            union=set()
            for index in order:union.update(results[index])
            expected=[row[:]for row in body]
            for a,b in union:expected[a][b]=8
            self.assertEqual(expected,out)
    def test_14_one_failed_ray_veto(self):
        x=fixture();original=g.trace_ray;count=[0]
        def one_fail(*args):
            count[0]+=1
            return (None,{'failure':'synthetic_unresolved'})if count[0]==4 else original(*args)
        with patch.object(g,'trace_ray',side_effect=one_fail):self.assertEqual(g.guarded_render(x)[1]['failure'],'synthetic_unresolved')
    def test_15_original_grid_record_only(self):
        x=fixture();out,record=g._legend_guided_turning_corridor_render(x);y=copy.deepcopy(out);y[-1][-1]=0
        with patch.object(g,'_legend_guided_turning_corridor_render',return_value=(y,record)):self.assertEqual(g.guarded_render(x)[1]['failure'],'original_grid_or_record_disagreement')
        with patch.object(g,'_legend_guided_turning_corridor_render',return_value=(out,dict(record,legend_corridor_event_count=99))):self.assertEqual(g.guarded_render(x)[1]['failure'],'original_grid_or_record_disagreement')
    def test_16_raw_fit_before_proof(self):
        pairs=copy.deepcopy(TRAIN);pairs[0]['output'][0][0]=9
        with patch.object(g,'guarded_render',side_effect=AssertionError('must not run')):self.assertIsNone(g.fit_teachers(pairs)[0])
    def test_17_invalid_duplicate_fixed_format(self):
        for x in[[],[[0],[]],[[True]],[[10]],[[0]*31]]:self.assertIsNone(g.guarded_render(x)[0])
        self.assertEqual(g.fit_teachers([TRAIN[0],TRAIN[0]])[1]['failure'],'duplicate_teacher_inputs')
        self.assertEqual(g.guarded_render([[0]*13 for _ in range(10)])[1]['failure'],'fixed_dictionary_shape_required')

    def test_native_support_is_teacher_boards(self):
        material=g.凡例旋回教材(TRAIN)
        for minimum,admitted in [(3,True),(4,False)]:
            machine=HDS学習実行系(最小支持数=minimum)
            record=候補機構を学習(machine,{'train':TRAIN,'test':[]},(),'ARC凡例旋回経路',material.候補)
            self.assertEqual(record['現在観測数'],3);self.assertEqual(record['事前観測数'],0)
            self.assertEqual(record['同値採用'],admitted);self.assertEqual(record['隔離数'],0)
    def test_native_one_unresolved_is_hold(self):
        x=copy.deepcopy(TRAIN[0]['input']);bad=copy.deepcopy(x);bad[11][8]=6
        result=課題を解く({'train':TRAIN,'test':[{'input':x},{'input':bad}]},[])
        self.assertEqual(result['results'][0]['answer'],g.guarded_render(x)[0]);self.assertIsNone(result['results'][1]['answer'])
    def test_no_identifier_or_test_target(self):
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[],'task_id':'forbidden'},[])
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[{'input':[[0]],'output':[[0]]}]},[])

if __name__=='__main__':unittest.main()
