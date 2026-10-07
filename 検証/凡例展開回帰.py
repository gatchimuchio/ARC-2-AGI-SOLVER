"""凡例・配置・palette役割、全tile積とnative教師盤面支持の回帰。"""
import copy,unittest
from unittest.mock import patch
from pathlib import Path
import sys
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 凡例展開教材 as g
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,課題を解く

def sample(n=3,permuted=False,palette=(6,7,8)):
    h,w=2*n+4,3*n+2;x=[[0]*w for _ in range(h)];starts=[i*(n+1)for i in range(3)];keys=[1,2,3]
    for key,start in zip(keys,starts):
        for r in range(n):
            for c in range(n):
                if(r+c+key)%3!=0:x[r][start+c]=key
    for r in [n,2*n+1]:
        for c in range(0,w,2):x[r][c]=5
    for c in [n,2*n+1]:
        for r in list(range(0,n,2))+[2*n+2]:x[r][c]=5
    for i,start in enumerate(starts):
        key=keys[(i+1)%3]if permuted else keys[i];r,c=divmod(i,n);x[n+1+r][start+c]=key
        x[h-1][start+n//2]=palette[i]
    return x

def teacher(n=3,permuted=False):
    x=sample(n,permuted);return{'input':x,'output':g.original_render(x)[0]}

class Controls(unittest.TestCase):
    def test_full_product_active_and_inactive(self):
        x=sample();out,r=g.guarded_render(x);self.assertIsNotNone(out)
        self.assertEqual(r['active_macro_cells'],3);self.assertEqual(r['inactive_macro_cells'],6);self.assertEqual(r['checked_output_cells'],81)
        self.assertEqual(sum(v!=0 for row in out for v in row),18)
        self.assertTrue(all(v==0 for row in out[3:]for v in row))
    def test_dictionary_lookup_crosses_column(self):
        x=sample(permuted=True);out,r=g.guarded_render(x);self.assertIsNotNone(out)
        self.assertEqual([p['token_color']for p in r['raw_record']['legend_token_macro_placement_records']],[2,3,1])
        self.assertEqual([p['output_color']for p in r['raw_record']['legend_token_macro_placement_records']],[7,8,6])
    def test_glyph_size_not_fixed_three(self):
        for n in [2,4,5]:
            out,r=g.guarded_render(sample(n));self.assertIsNotNone(out);self.assertEqual(len(out),n*n);self.assertEqual(r['checked_output_cells'],n**4)
    def test_output_limit_is_whole_hold(self):
        x=sample(6);self.assertEqual(len(g.original_render(x)[0]),36)
        self.assertEqual(g.guarded_render(x)[1]['failure'],'output_shape_out_of_arc_bounds')
    def test_separator_colour_elsewhere_not_exempt(self):
        for color in [5,9]:
            x=sample();x.append([0]*len(x[0]));x[-1][0]=color
            self.assertIsNotNone(g.original_render(x)[0]);self.assertEqual(g.guarded_render(x)[1]['failure'],'unowned_foreground')
    def test_output_palette_can_use_separator_colour(self):
        out,r=g.guarded_render(sample(palette=(5,7,8)));self.assertIsNotNone(out)
        self.assertEqual(sum(v==5 for row in out for v in row),6)
    def test_all_raw_separator_colours_before_later_parse(self):
        x=sample();x.append([0]*len(x[0]));x[-1][0]=9;x[-1][1]=9
        self.assertIsNotNone(g.original_render(x)[0])
        with patch.object(g,'_legend_token_macro_parse',side_effect=RuntimeError('must not run')):
            self.assertEqual(g.guarded_render(x)[1]['failure'],'raw_separator_role_not_unique')
    def test_query_uniform_map_row_keeps_strict_teacher_domain(self):
        pairs=[teacher(),teacher(4,True)];material=g.凡例展開教材(pairs)
        x=sample();x[5][:3]=[1,1,1]
        self.assertEqual(g.guarded_render(x)[1]['failure'],'raw_separator_role_not_unique')
        raw,raw_record=g.original_render(x);out,record=material.候補(x,None)
        self.assertEqual(out,raw);self.assertEqual(record['raw_record'],raw_record)
        self.assertIn([5,1],record['raw_separator_rows'])
        self.assertFalse(g.fit_teachers([pairs[0],{'input':x,'output':raw}])[0])
        for pair in pairs:self.assertEqual(material.候補(pair['input'],None),g.guarded_render(pair['input']))
    def test_query_unowned_uniform_row_is_still_early_hold(self):
        material=g.凡例展開教材([teacher(),teacher(4,True)])
        x=sample();x[5][:3]=[1,1,1];x.append([0]*len(x[0]));x[-1][:2]=[9,9]
        with patch.object(g,'_legend_token_macro_parse',side_effect=RuntimeError('must not run')):
            self.assertEqual(material.候補(x,None)[1]['failure'],'raw_separator_role_not_unique')
        x=sample();x[5][:4]=[1,1,1,1]
        self.assertEqual(material.候補(x,None)[1]['failure'],'unowned_raw_row_foreground')
    def test_overlapping_macro_rejected_without_late_selection(self):
        x=sample();x[4][1]=1
        self.assertIsNotNone(g.original_render(x)[0]);self.assertEqual(g.guarded_render(x)[1]['failure'],'macro_position_overlap')
    def test_negative_slot_is_not_wrapped_or_replaced(self):
        original=g._legend_token_macro_parse
        def corrupt(x):
            p,r=original(x);p['template_records'][0]['slot_start']=-1;return p,r
        with patch.object(g,'_legend_token_macro_parse',corrupt):self.assertEqual(g.guarded_render(sample())[1]['failure'],'slot_out_of_bounds')
    def test_overlapping_slots_are_not_dropped(self):
        original=g._legend_token_macro_parse
        def corrupt(x):
            p,r=original(x);p['template_records'][1]['slot_start']=2;return p,r
        with patch.object(g,'_legend_token_macro_parse',corrupt):self.assertEqual(g.guarded_render(sample())[1]['failure'],'slot_overlap')
    def test_real_negative_index_exception_is_hold(self):
        x=[[0,1,0,2,0,0]for _ in range(14)]+[[5,5,0,0,0,0]]+[[0]*6 for _ in range(14)]+[[5,5,0,0,0,0]]
        self.assertEqual(g.original_render(x)[1]['failure'],'original_parse_exception')
        self.assertEqual(g.guarded_render(x)[1]['failure'],'original_parse_exception')
    def test_missing_token_or_marker_not_silently_ignored(self):
        x=sample();x[4][0]=0;self.assertIsNone(g.guarded_render(x)[0])
        x=sample();x[9][1]=0;self.assertIsNone(g.guarded_render(x)[0])
    def test_colour_relabelling_including_zero(self):
        x=sample();out,_=g.guarded_render(x);palette={0:4,1:0,2:8,3:2,5:9,6:3,7:1,8:7}
        self.assertEqual(g.guarded_render([[palette[v]for v in row]for row in x])[0],[[palette[v]for v in row]for row in out])
    def test_original_output_and_record_only(self):
        original=g._legend_token_macro_render
        for change_record in [False,True]:
            def corrupt(x):
                out,r=original(x)
                if change_record:r=dict(r,legend_token_macro_event_count=999)
                else:out[0][0]=9
                return out,r
            with patch.object(g,'_legend_token_macro_render',corrupt):self.assertEqual(g.guarded_render(sample())[1]['failure'],'original_grid_or_record_disagreement')
    def test_raw_teachers_before_guard(self):
        pairs=[teacher(),teacher(4,True)];self.assertTrue(g.fit_teachers(pairs)[0]);pairs[1]['output'][0][0]=9
        with patch.object(g,'guarded_render',side_effect=RuntimeError('must not run')):self.assertFalse(g.fit_teachers(pairs)[0])
    def test_invalid_duplicate_and_background_tie(self):
        for x in [[],[[0],[]],[[True]],[[10]],[[0,1],[2,3]]]:self.assertIsNone(g.guarded_render(x)[0])
        self.assertFalse(g.fit_teachers([teacher(),teacher()])[0])

    def test_native_support_is_teacher_boards(self):
        pairs=[teacher(),teacher(4,True)];material=g.凡例展開教材(pairs)
        for minimum,admitted in [(2,True),(3,False)]:
            machine=HDS学習実行系(最小支持数=minimum)
            r=候補機構を学習(machine,{'train':pairs,'test':[]},(),'ARC凡例token積展開',material.候補)
            self.assertEqual(r['現在観測数'],2);self.assertEqual(r['事前観測数'],0)
            self.assertEqual(r['同値採用'],admitted);self.assertEqual(r['隔離数'],0)
    def test_native_ambiguous_admitted_family_is_hold(self):
        pairs=[teacher(),teacher(4,True)];x=sample();bad=sample();bad.append([0]*len(bad[0]));bad[-1][0]=9;bad[-1][1]=9
        r=課題を解く({'train':pairs,'test':[{'input':x},{'input':bad}]},[])
        self.assertEqual(r['results'][0]['answer'],g.guarded_render(x)[0]);self.assertIsNone(r['results'][1]['answer'])
    def test_no_identifier_or_test_target(self):
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[],'task_id':'forbidden'},[])
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[{'input':[[0]],'output':[[0]]}]},[])

if __name__=='__main__':unittest.main()
