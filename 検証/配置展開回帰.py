"""全mask/tile対応・色数倍率とnative教師盤面支持の回帰。"""
import unittest,copy
from unittest.mock import patch
from pathlib import Path
import sys
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 配置展開教材 as g
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,課題を解く

def place(grid,tile,top,left):
    for r,row in enumerate(tile):
        for c,v in enumerate(row):grid[top+r][left+c]=v

def sample(tile=None,mask=None,bg=0):
    if tile is None:tile=[[1,2,0],[2,1,1]]
    if mask is None:mask=[[3,0],[3,3]]
    x=[[bg]*14 for _ in range(11)];place(x,tile,1,1);place(x,mask,6,9);return x

def teacher(alternate=False):
    x=sample()if not alternate else sample([[1,2],[2,1]],[[3,3,3],[0,3,0]])
    return{'input':x,'output':g.render_layout_mask_macro_tile_expander(x)[0]}

class Controls(unittest.TestCase):
    def test_full_block_product_and_inactive_tiles(self):
        out,r=g.guarded_render(sample());self.assertIsNotNone(out);self.assertEqual([len(out),len(out[0])],[4,6])
        self.assertEqual(r['inactive_layout_cell_count'],1);self.assertEqual(r['output_cell_count'],24)
        self.assertEqual([row[3:]for row in out[:2]],[[0,0,0],[0,0,0]])
        self.assertEqual(r['output_foreground_counts'],[(1,9),(2,6)])
    def test_foreign_mask_inside_motif_bbox(self):
        x=[[0]*9 for _ in range(9)]
        for r in range(1,6):
            for c in range(1,6):
                if r in [1,5]or c in [1,5]:x[r][c]=2 if(r+c)%2==0 else 1
        x[3][3]=3
        out,r=g.render_layout_mask_macro_tile_expander(x);self.assertIsNotNone(out);self.assertEqual(out[2][2],3)
        self.assertEqual(g.guarded_render(x)[1],{'failure':'foreign_foreground_in_bbox','role':'motif'})
    def test_foreign_motif_inside_layout_bbox(self):
        x=[[0]*11 for _ in range(11)]
        for r in range(1,10):
            for c in range(1,10):
                if r in [1,9]or c in [1,9]:x[r][c]=3
        place(x,[[1,2,1],[2,1,2],[1,2,1]],4,4)
        self.assertIsNotNone(g.render_layout_mask_macro_tile_expander(x)[0])
        self.assertEqual(g.guarded_render(x)[1],{'failure':'foreign_foreground_in_bbox','role':'layout'})
    def test_background_tie_whole_hold(self):
        x=[[0,1,2,0,0,3,3,3]for _ in range(3)]
        self.assertIsNotNone(g.render_layout_mask_macro_tile_expander(x)[0])
        self.assertEqual(g.guarded_render(x)[1]['failure'],'background_tie')
    def test_disconnected_mask_is_not_grouped_by_colour(self):
        x=sample();x[9][11]=3;self.assertIsNone(g.guarded_render(x)[0])
    def test_roles_fixed_before_drawing(self):
        for tile,mask in [([[1,1],[1,1]],[[3,3],[3,3]]),([[1,2],[2,1]],[[3,4],[4,3]]),([[1,2],[2,1]],[[1,1],[1,1]])]:
            self.assertIsNone(g.guarded_render(sample(tile,mask))[0])
    def test_motif_holes_are_repeated(self):
        tile=[[1,1,2],[2,0,1],[1,2,2]];out,r=g.guarded_render(sample(tile,[[3,3]]))
        self.assertIsNotNone(out);self.assertEqual(out[1][1],0);self.assertEqual(out[1][4],0)
    def test_background_not_required_in_output(self):
        out,r=g.guarded_render(sample([[1,2],[2,1]],[[3,3],[3,3]]))
        self.assertEqual({v for row in out for v in row},{1,2});self.assertEqual(r['output_foreground_counts'],[(1,8),(2,8)])
    def test_non_square_and_singleton_layout(self):
        out,r=g.guarded_render(sample([[1,2,1,2]],[[3,3],[0,3],[3,3]]))
        self.assertEqual([len(out),len(out[0])],[3,8]);self.assertEqual(len(r['active_layout_cells']),5)
        self.assertEqual(g.guarded_render(sample(mask=[[3]]))[0],[[1,2,0],[2,1,1]])
    def test_arc_bounds_without_clipping(self):
        for size,accepted in [(15,True),(16,False)]:
            x=[[0]*30 for _ in range(30)];place(x,[[1,2]],1,1);place(x,[[3]*size for _ in range(size)],10,10)
            out,r=g.guarded_render(x);self.assertEqual(out is not None,accepted)
            if accepted:self.assertEqual([len(out),len(out[0])],[15,30])
    def test_d4_and_colour_remap(self):
        x=sample();expected,_=g.guarded_render(x)
        for flip in [False,True]:
            a=[row[::-1]for row in x]if flip else copy.deepcopy(x);b=[row[::-1]for row in expected]if flip else copy.deepcopy(expected)
            for _ in range(4):
                self.assertEqual(g.guarded_render(a)[0],b);a=[list(row)for row in zip(*a[::-1])];b=[list(row)for row in zip(*b[::-1])]
        m={0:7,1:0,2:4,3:9};self.assertEqual(g.guarded_render([[m[v]for v in row]for row in x])[0],[[m[v]for v in row]for row in expected])
    def test_full_foreground_coverage_required(self):
        x=sample();components=g.foreground_mixed_components(x,0);components=copy.deepcopy(components);components[0]['cells']=components[0]['cells'][1:]
        with patch.object(g,'foreground_mixed_components',return_value=components):self.assertEqual(g.guarded_render(x)[1]['failure'],'foreground_coverage_failed')
    def test_original_grid_and_record_only(self):
        original=g.render_layout_mask_macro_tile_expander
        for change_record in [False,True]:
            def corrupt(x):
                out,r=original(x)
                if change_record:r=dict(r,macro_active_cell_count=999)
                else:out[0][0]=9
                return out,r
            with patch.object(g,'render_layout_mask_macro_tile_expander',corrupt):self.assertIsNone(g.guarded_render(sample())[0])
    def test_teacher_raw_fit_before_guard(self):
        pairs=[teacher(),teacher(True)];self.assertTrue(g.fit_teachers(pairs)[0]);pairs[1]['output'][0][0]=9
        with patch.object(g,'guarded_render',side_effect=RuntimeError('must not run')):self.assertFalse(g.fit_teachers(pairs)[0])
    def test_duplicate_and_invalid_input(self):
        self.assertFalse(g.fit_teachers([teacher(),teacher()])[0])
        for x in [[],[[0],[]],[[True]],[[10]]]:self.assertIsNone(g.guarded_render(x)[0])

    def test_native_support_not_tiles(self):
        pairs=[teacher(),teacher(True)];material=g.配置展開教材(pairs)
        for minimum,admitted in [(2,True),(3,False)]:
            machine=HDS学習実行系(最小支持数=minimum)
            r=候補機構を学習(machine,{'train':pairs,'test':[]},(),'ARC配置mask展開',material.候補)
            self.assertEqual(r['現在観測数'],2);self.assertEqual(r['事前観測数'],0)
            self.assertEqual(r['同値採用'],admitted);self.assertEqual(r['隔離数'],0)
    def test_native_grid_and_unresolved_hold(self):
        x=sample([[1,2],[1,2]],[[3,0,3],[3,3,3]]);bad=sample();bad[9][11]=3
        r=課題を解く({'train':[teacher(),teacher(True)],'test':[{'input':x},{'input':bad}]},[])
        self.assertEqual(r['results'][0]['answer'],g.guarded_render(x)[0]);self.assertIsNone(r['results'][1]['answer'])
    def test_no_identifier_or_target_input(self):
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[],'task_id':'forbidden'},[])
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[{'input':[[0]],'output':[[0]]}]},[])

if __name__=='__main__':unittest.main()
