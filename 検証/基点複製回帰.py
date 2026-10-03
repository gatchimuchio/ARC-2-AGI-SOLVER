"""全役割・全配置・色別倍率とnative教師盤面支持の回帰。"""
import unittest,copy
from unittest.mock import patch
from pathlib import Path
import sys
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 基点複製教材 as g
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,課題を解く

def sample(alternate=False):
    bg=7 if alternate else 0;x=[[bg]*21 for _ in range(20)]
    points=[(5,8),(5,9),(6,8)]+([(6,10)]if alternate else[])
    for r,c in points:x[r][c]=2
    x[15][15]=2;x[15][11]=3;x[15][17]=3
    return x

def teacher(alternate=False):
    x=sample(alternate);return{'input':x,'output':g.render_anchored_singleton_motif_tiler(x)[0]}

class Controls(unittest.TestCase):
    def test_raw_roles_before_oob_or_palette_filter(self):
        x=sample();x[0][0]=1;x[19][20]=1
        self.assertEqual(len(g.raw_roles(x,0)),2);self.assertIsNotNone(g.render_anchored_singleton_motif_tiler(x)[0])
        self.assertEqual(g.guarded_render(x)[1],{'failure':'raw_role_count_not_one','raw_role_count':2})
    def test_unknown_nonpoint_colour_not_silently_erased(self):
        x=sample();x[19][19]=1;x[19][20]=1
        self.assertEqual(len(g.raw_roles(x,0)),1);raw,_=g.render_anchored_singleton_motif_tiler(x);self.assertIsNotNone(raw);self.assertEqual(raw[19][19],0)
        self.assertEqual(g.guarded_render(x)[1]['failure'],'foreground_role_coverage_failed')
    def test_zero_axis_default_has_no_placement_effect(self):
        out,r=g.guarded_render(sample());self.assertIsNotNone(out);self.assertEqual(r['zero_axes'],[0])
        self.assertEqual(r['raw_record']['anchored_row_step'],1);self.assertEqual(r['raw_record']['anchored_col_step'],2)
        self.assertEqual(r['raw_record']['anchored_placements'],[[5,4],[5,10]])
        for divisor in [1,2,7]:self.assertEqual([5+(15-15)*2//divisor for _ in range(2)],[5,5])
    def test_counts_and_prototype_colour_switch(self):
        x=sample();out,r=g.guarded_render(x);self.assertIsNotNone(out)
        self.assertEqual(r['motif_pixels'],3);self.assertEqual(r['source_output_pixels'],6);self.assertEqual(r['marker_output_pixels'],3)
        self.assertTrue(all(out[rr][cc]==3 for rr,cc in [(5,8),(5,9),(6,8)]));self.assertEqual(r['instruction_cells_now_background'],3)
    def test_instruction_position_can_receive_computed_output(self):
        x=[[0]*21 for _ in range(20)]
        for r,c in [(5,8),(5,9),(6,8),(5,4)]:x[r][c]=2
        x[5][2]=3;x[5][6]=3;out,r=g.guarded_render(x);self.assertIsNotNone(out)
        self.assertEqual(out[5][6],2);self.assertEqual(r['instruction_point_count'],3);self.assertEqual(r['instruction_cells_now_background'],2)
    def test_non_square_motif_pitch(self):
        out,r=g.guarded_render(sample(True));self.assertIsNotNone(out);self.assertEqual(r['raw_record']['anchored_motif_shape'],[2,3])
        self.assertEqual(r['raw_record']['anchored_placements'],[[5,2],[5,11]])
    def test_largest_gcd_unit_not_fixed_two(self):
        x=sample();x[15][11]=0;x[15][17]=0;x[15][12]=3;x[15][18]=3
        out,r=g.guarded_render(x);self.assertIsNotNone(out);self.assertEqual(r['raw_record']['anchored_col_step'],3)
        self.assertEqual(r['raw_record']['anchored_placements'],[[5,6],[5,10]])
    def test_any_placement_oob_is_whole_hold(self):
        x=sample()
        for r,c in [(5,8),(5,9),(6,8)]:x[r][c]=0;x[r][c-7]=2
        self.assertEqual(len(g.raw_roles(x,0)),1);self.assertIsNone(g.render_anchored_singleton_motif_tiler(x)[0])
        self.assertEqual(g.guarded_render(x)[1]['failure'],'projected_bbox_out_of_bounds')
    def test_multiple_source_anchor_points_not_selected(self):
        x=sample();x[19][10]=2;self.assertEqual(g.guarded_render(x)[1]['failure'],'raw_role_count_not_one')
    def test_marker_component_not_a_point(self):
        x=sample();x[15][12]=3;self.assertIsNone(g.guarded_render(x)[0])
    def test_d4_and_bijective_palette(self):
        x=sample(True);expected,_=g.guarded_render(x)
        for flip in [False,True]:
            a=[row[::-1]for row in x]if flip else copy.deepcopy(x);b=[row[::-1]for row in expected]if flip else copy.deepcopy(expected)
            for _ in range(4):
                self.assertEqual(g.guarded_render(a)[0],b);a=[list(row)for row in zip(*a[::-1])];b=[list(row)for row in zip(*b[::-1])]
        mapping={7:3,2:0,3:5};self.assertEqual(g.guarded_render([[mapping[v]for v in row]for row in x])[0],[[mapping[v]for v in row]for row in expected])
    def test_original_output_and_record_only(self):
        original=g.render_anchored_singleton_motif_tiler
        for change_record in [False,True]:
            def corrupt(x):
                out,r=original(x)
                if change_record:r=dict(r,anchored_marker_count=999)
                else:out[0][0]=9
                return out,r
            with patch.object(g,'render_anchored_singleton_motif_tiler',corrupt):self.assertIsNone(g.guarded_render(sample())[0])
    def test_raw_teacher_fit_before_certificate(self):
        pairs=[teacher(),teacher(True)];self.assertTrue(g.fit_teachers(pairs)[0]);pairs[1]['output'][0][0]=9
        with patch.object(g,'guarded_render',side_effect=RuntimeError('must not execute')):self.assertFalse(g.fit_teachers(pairs)[0])
    def test_invalid_duplicate_background_tie(self):
        self.assertFalse(g.fit_teachers([teacher(),teacher()])[0])
        for x in [[],[[0],[]],[[True]],[[10]],[[0,1],[2,3]]]:self.assertIsNone(g.guarded_render(x)[0])
    def test_every_marker_kept_in_complete_prediction(self):
        x=sample();x[12][15]=3
        out,r=g.guarded_render(x);self.assertIsNotNone(out)
        self.assertEqual(r['raw_record']['anchored_marker_count'],3);self.assertEqual(r['source_output_pixels'],9)
        self.assertEqual(len(r['normalized_marker_coordinates']),3);self.assertEqual(r['projected_bbox_count'],4)

    def test_native_support_not_placements(self):
        pairs=[teacher(),teacher(True)];material=g.基点複製教材(pairs)
        for minimum,admitted in [(2,True),(3,False)]:
            machine=HDS学習実行系(最小支持数=minimum)
            r=候補機構を学習(machine,{'train':pairs,'test':[]},(),'ARC基点motif展開',material.候補)
            self.assertEqual(r['現在観測数'],2);self.assertEqual(r['事前観測数'],0)
            self.assertEqual(r['同値採用'],admitted);self.assertEqual(r['隔離数'],0)
    def test_native_complete_grid_and_unknown_role_hold(self):
        x=sample();x[12][15]=3;bad=sample();bad[19][19]=1;bad[19][20]=1
        r=課題を解く({'train':[teacher(),teacher(True)],'test':[{'input':x},{'input':bad}]},[])
        self.assertEqual(r['results'][0]['answer'],g.guarded_render(x)[0]);self.assertIsNone(r['results'][1]['answer'])
    def test_no_identifier_or_target_input(self):
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[],'task_id':'forbidden'},[])
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[{'input':[[0]],'output':[[0]]}]},[])

if __name__=='__main__':unittest.main()
