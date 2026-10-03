"""全対象・全copyと消去witness/native盤面支持を区別する。"""
import unittest,copy
from unittest.mock import patch
from pathlib import Path
import sys
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 制御複写教材 as g
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,課題を解く
P=[2,3,5,4]

def glyph(x,top,left,color):
    for dr,cols in [(0,[1,2,3]),(1,[0,1,2,3,4]),(2,[1,2,3])]:
        for dc in cols:x[top+dr][left+dc]=color

def sample(bg=0,count=3):
    x=[[bg]*22 for _ in range(20)]
    for top in [2,6,10][:count]:glyph(x,top,1,9)
    glyph(x,14,13,1);glyph(x,6,7,6)
    for c in range(1,6):x[-1][c]=2
    for c in range(13,18):x[-1][c]=3
    return x

def pair(bg=0,count=3):
    x=sample(bg,count);return{'input':x,'output':g.render_control_bar_shape_rewrite(x,*P)[0]}

class Controls(unittest.TestCase):
    def test_shared_roles_vary_bg_and_count(self):
        model,r=g.fit_teachers([pair(0,3),pair(7,2)]);self.assertEqual(model['policy'],P)
        self.assertEqual(model['control_consumption_witnesses'],2)
        for count in [1,2,3]:
            out,r=g.guarded_render(sample(count=count),P,True);self.assertIsNotNone(out)
            self.assertEqual(r['copy_operation_count'],count);self.assertEqual(r['copy_proposed_pixels'],11*count)
    def test_control_erasure_requires_complete_witness(self):
        out,r=g.guarded_render(sample(),P,False);self.assertIsNone(out);self.assertEqual(r['failure'],'unwitnessed_control_consumption')
        bad=[pair(),pair(7)];bad[1]['output'][0][0]=8;model,r=g.fit_teachers(bad)
        self.assertIsNone(model);self.assertNotIn('control_consumption_witnesses',r)
    def test_bottom_straddler_not_silently_erased(self):
        x=sample();x[18][20]=4;x[19][20]=4
        self.assertIsNotNone(g.render_control_bar_shape_rewrite(x,*P)[0])
        self.assertEqual(g.guarded_render(x,P,True)[1]['failure'],'component_coverage_failed')
    def test_clip_cannot_drop_copy_cells(self):
        x=sample()
        for r in range(14,17):
            for c in range(13,18):
                if x[r][c]==1:x[r-12][c]=1;x[r][c]=0
        self.assertIsNotNone(g.render_control_bar_shape_rewrite(x,*P)[0])
        self.assertEqual(g.guarded_render(x,P,True)[1]['failure'],'copy_clipping_required')
    def test_gcd_fallback_is_unwitnessed(self):
        x=sample();x[5][20]=4;s,_=g._control_bar_shape_source(x);self.assertEqual(s['inferred_period'],1)
        self.assertIsNotNone(g.render_control_bar_shape_rewrite(x,*P)[0])
        self.assertEqual(g.guarded_render(x,P,True)[1]['failure'],'unwitnessed_gcd_period_branch')
    def test_height_mode_tie_before_period(self):
        x=[[0]*22 for _ in range(20)];x[10][2]=9;glyph(x,14,13,1)
        for c in range(1,6):x[-1][c]=2
        for c in range(13,18):x[-1][c]=3
        self.assertIsNotNone(g.render_control_bar_shape_rewrite(x,2,3,5,2)[0])
        self.assertEqual(g.guarded_render(x,[2,3,5,2],True)[1]['failure'],'shape_height_mode_tie')
    def test_fitted_period_not_reinferred_to_rescue(self):
        self.assertEqual(g.guarded_render(sample(),[2,3,5,8],True)[1]['failure'],'fitted_period_input_disagreement')
    def test_recolor_copy_final_colour_collision(self):
        x=[[0]*18 for _ in range(14)]
        for c in range(1,16):x[10][c]=1
        x[8][2]=1;x[8][3]=1
        for c in range(1,4):x[-1][c]=2
        for c in range(13,16):x[-1][c]=3
        raw,r=g.render_control_bar_shape_rewrite(x,2,3,5,2);self.assertIsNotNone(raw);self.assertEqual(raw[8][2],1)
        self.assertEqual(g.guarded_render(x,[2,3,5,2],True)[1]['failure'],'simultaneous_colour_conflict')
    def test_same_colour_union_distinct_from_operation_count(self):
        x=[[0]*18 for _ in range(20)]
        for r in [4,6,8]:x[r][2]=9
        for r in range(12,15):x[r][14]=1
        for c in range(1,4):x[-1][c]=2
        for c in range(13,16):x[-1][c]=3
        out,r=g.guarded_render(x,[2,3,5,2],True);self.assertIsNotNone(out)
        self.assertEqual(r['copy_operation_count'],3);self.assertEqual(r['copy_proposed_pixels'],9)
        self.assertEqual(r['copy_union_pixels'],7);self.assertEqual(r['copy_added_background_pixels'],6)
    def test_extra_control_role_whole_hold_after_raw_fit(self):
        pairs=[pair(),pair(7)]
        for p in pairs:
            for c in range(7,10):p['input'][-1][c]=4
            p['output']=g.render_control_bar_shape_rewrite(p['input'],*P)[0]
        policy,r=g.raw_teacher_policy(pairs);self.assertEqual(policy,P)
        model,r=g.fit_teachers(pairs);self.assertIsNone(model);self.assertEqual(r['failure'],'teacher_certificate_failed')
    def test_existing_target_colour_not_banned(self):
        x=sample()
        for r,row in enumerate(x):
            for c,v in enumerate(row):
                if v==6:x[r][c]=5
        out,r=g.guarded_render(x,P,True);self.assertIsNotNone(out)
        for rr,row in enumerate(x):
            for cc,v in enumerate(row):
                if v==5:self.assertEqual(out[rr][cc],5)
    def test_unselected_shape_and_original_copy_source_preserved(self):
        x=sample();out,r=g.guarded_render(x,P,True);self.assertIsNotNone(out)
        for rr,row in enumerate(x):
            for cc,v in enumerate(row):
                if v in [1,6]:self.assertEqual(out[rr][cc],v)
    def test_raw_grid_and_record_only(self):
        original=g.render_control_bar_shape_rewrite
        def corrupt(*a,**k):
            out,r=original(*a,**k)
            if out is not None:out[0][0]=8
            return out,r
        with patch.object(g,'render_control_bar_shape_rewrite',corrupt):self.assertIsNone(g.guarded_render(sample(),P,True)[0])
    def test_invalid_duplicate_and_role_alias(self):
        for x in [[],[[True]],[[10]],[[0],[]]]:self.assertIsNone(g.guarded_render(x,P,True)[0])
        self.assertIsNone(g.fit_teachers([pair(),pair()])[0])
        self.assertIsNone(g.guarded_render(sample(),[2,2,5,4],True)[0])
        x=sample(5);self.assertIsNone(g.guarded_render(x,P,True)[0])
    def test_source_is_not_fixed_canvas(self):
        x=sample();x=[row+[0]*3 for row in x];out,r=g.guarded_render(x,P,True)
        self.assertIsNotNone(out);self.assertEqual([len(out),len(out[0])],[20,25])
        mapping={0:8,1:7,2:6,3:4,5:3,6:2,9:1};y=[[mapping[v]for v in row]for row in x]
        self.assertEqual(g.guarded_render(y,[6,4,3,4],True)[0],[[mapping[v]for v in row]for row in out])

    def test_native_support_not_control_or_witness_count(self):
        pairs=[pair(),pair(7,2)];material=g.制御複写教材(pairs)
        self.assertEqual(material.モデル['control_consumption_witnesses'],2)
        for minimum,admitted in [(2,True),(3,False)]:
            machine=HDS学習実行系(最小支持数=minimum)
            r=候補機構を学習(machine,{'train':pairs,'test':[]},(),'ARC制御bar個数複写',material.候補)
            self.assertEqual(r['現在観測数'],2);self.assertEqual(r['事前観測数'],0)
            self.assertEqual(r['同値採用'],admitted);self.assertEqual(r['隔離数'],0)
    def test_native_complete_output_and_unresolved_hold(self):
        pairs=[pair(),pair(7,2)];x=sample(count=1);bad=sample();bad[18][20]=4;bad[19][20]=4
        r=課題を解く({'train':pairs,'test':[{'input':x},{'input':bad}]},[])
        self.assertEqual(r['results'][0]['answer'],g.guarded_render(x,P,True)[0]);self.assertIsNone(r['results'][1]['answer'])
    def test_no_identifier_or_target_input(self):
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[],'task_id':'forbidden'},[])
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[{'input':[[0]],'output':[[0]]}]},[])

if __name__=='__main__':unittest.main()
