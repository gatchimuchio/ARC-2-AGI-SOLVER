"""全共同role・櫛/pin・clip所有とnative盤面支持の回帰。"""
import copy
import unittest
from pathlib import Path
import sys
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 櫛配置教材 as p
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,課題を解く

def sample(*,height=20,width=30,frame=(2,15,16,28),baseline=13,source_first=2,heights=(6,3,7),pin_ranges=((3,9),(5,11),(6,12)),colours=(1,2,3),pin_columns=None):
    g=[[0]*width for _ in range(height)];out=copy.deepcopy(g);r0,c0,r1,c1=frame
    border={(r,c)for r in range(r0,r1+1)for c in range(c0,c1+1)if r in(r0,r1)or c in(c0,c1)}-{(baseline-1,c0),(baseline,c0)}
    for r,c in border:g[r][c]=out[r][c]=5
    columns=tuple(c0+3+2*i for i in range(len(heights)))if pin_columns is None else pin_columns
    source_columns=[source_first+2*i for i in range(len(heights))]
    for c in range(source_columns[0],source_columns[-1]+1):g[baseline][c]=5
    for source_col,n in zip(source_columns,heights):
        for r in range(baseline-n,baseline):g[r][source_col]=5
    for col,source_height,(lo,hi),colour in zip(columns,heights,pin_ranges,colours):
        for r in range(r0+1,lo):g[r][col]=5
        for r in range(lo,hi+1):g[r][col]=colour
        tooth_top=baseline-source_height;advance=max(0,hi-tooth_top+1)
        for r in range(r0+1,max(r0+1,lo-advance)):out[r][col]=5
        for r in range(max(r0+1,lo-advance),min(r1,hi-advance+1)):out[r][col]=colour
        for r in range(tooth_top,baseline+1):out[r][col]=5
    for c in range(columns[0],columns[-1]+1):out[baseline][c]=5
    return g,out

def recolour(g,mapping):return [[mapping.get(v,v)for v in row]for row in g]

class Controls(unittest.TestCase):
    def hold(self,g,reason=None):
        out,record=p.render(g);self.assertIsNone(out)
        if reason:self.assertEqual(record['failure'],reason)
        return record

    def test_01_static_placement_interval_oracle(self):
        g,o=sample();out,record=p.render(g);self.assertEqual(out,o)
        self.assertEqual(record['translation'],[0,16]);self.assertEqual(record['pin_count'],3)
        self.assertGreater(record['pin_clipped_cells'],0)

    def test_02_all_d4_and_arbitrary_colours(self):
        g,o=sample();g=recolour(g,{0:7,5:0,1:9,2:6,3:4});o=recolour(o,{0:7,5:0,1:9,2:6,3:4})
        for _ in range(4):
            self.assertEqual(p.render(g)[0],o);self.assertEqual(p.render([r[::-1]for r in g])[0],[r[::-1]for r in o])
            g=[list(row)for row in zip(*g[::-1])];o=[list(row)for row in zip(*o[::-1])]

    def test_03_variable_tooth_count_and_shape(self):
        for n in range(1,6):
            heights=tuple(2+i%3 for i in range(n));ranges=tuple((3+i%2,12)for i in range(n));colours=tuple(1+i%3 for i in range(n))
            for source_first in(1,2,3):
                g,o=sample(source_first=source_first,heights=heights,pin_ranges=ranges,colours=colours)
                self.assertEqual(p.render(g)[0],o,(n,source_first,p.render(g)[1]))

    def test_04_non_square_off_centre_frames(self):
        for top in(1,2,3):
            for left in(13,15,17):
                g,o=sample(frame=(top,left,17,29),pin_ranges=((4,9),(5,11),(6,12)))
                self.assertEqual(p.render(g)[0],o)

    def test_05_same_colour_distinct_pins(self):
        g,o=sample(colours=(2,2,2));out,r=p.render(g);self.assertEqual(out,o);self.assertEqual(r['pin_count'],3)

    def test_06_comb_is_also_raw_u_frame(self):
        g,o=sample(heights=(6,2,6),pin_ranges=((3,9),(5,11),(6,12)))
        out,r=p.render(g);self.assertEqual(out,o);self.assertEqual(len(r['parse']['raw_frames']),2);self.assertEqual(r['parse']['input_role_count'],1)

    def test_07_ambiguous_joint_orientation_precedes_placement(self):
        g,o=sample(heights=(1,),pin_ranges=((3,15),),colours=(1,))
        r=self.hold(g,'joint_input_role_not_unique');self.assertEqual(len(r['raw_frames']),1);self.assertEqual(r['input_role_count'],2)

    def test_08_unknown_outside_colour(self):
        g,o=sample();g[0][0]=8;self.hold(g,'joint_input_role_not_unique')

    def test_09_extra_outside_base_component(self):
        g,o=sample();g[0][0]=5;self.hold(g,'joint_input_role_not_unique')

    def test_10_opening_not_blank(self):
        g,o=sample();g[12][15]=4;self.hold(g,'joint_input_role_not_unique')

    def test_11_incomplete_pin_stem(self):
        g,o=sample();g[3][20]=0;self.hold(g,'joint_input_role_not_unique')

    def test_12_unowned_grey_interior(self):
        g,o=sample();g[14][26]=5;self.hold(g,'joint_input_role_not_unique')

    def test_13_branched_or_disconnected_pin(self):
        g,o=sample();g[7][19]=1;self.hold(g,'joint_input_role_not_unique')
        g,o=sample();g[6][18]=0;self.hold(g,'joint_input_role_not_unique')

    def test_14_tooth_count_failure_keeps_selected_role(self):
        g,o=sample()
        for r in range(3,13):g[r][22]=0
        rec=self.hold(g,'all_teeth_pins_count_mismatch');self.assertEqual(rec['parse']['input_role_count'],1)

    def test_15_all_columns_must_share_translation(self):
        g,o=sample(pin_columns=(18,21,24));rec=self.hold(g,'tooth_pin_translation_not_shared');self.assertEqual(rec['parse']['input_role_count'],1)

    def test_16_no_perpendicular_baseline_repair(self):
        g,o=sample();source={(r,c)for r,row in enumerate(g)for c,v in enumerate(row)if v==5 and c<15}
        for r,c in source:g[r][c]=0
        for r,c in source:g[r-1][c]=5
        self.hold(g,'joint_input_role_not_unique')

    def test_17_whole_comb_out_of_frame_no_clip(self):
        g,o=sample(heights=(12,3,7));rec=self.hold(g,'whole_comb_target_outside_frame');self.assertEqual(rec['parse']['input_role_count'],1)

    def test_18_comb_may_not_merge_with_old_stem(self):
        g,o=sample(heights=(9,3,7),pin_ranges=((5,9),(5,11),(6,12)))
        rec=self.hold(g,'comb_target_hits_original_base');self.assertEqual(rec['parse']['input_role_count'],1)

    def test_19_declared_complete_pin_clip(self):
        g,o=sample(heights=(10,),pin_ranges=((3,8),),colours=(1,));out,rec=p.render(g)
        self.assertEqual(out,o);self.assertEqual(rec['pin_source_cells'],6);self.assertEqual(rec['pin_visible_cells'],0);self.assertEqual(rec['pin_clipped_cells'],6)

    def test_20_stationary_pin_is_still_processed(self):
        g,o=sample(heights=(2,),pin_ranges=((3,4),),colours=(1,));out,rec=p.render(g)
        self.assertEqual(out,o);self.assertEqual(rec['pin_moves'][0]['advance'],0);self.assertEqual(rec['pin_visible_cells'],2)

    def test_21_stem_repaint_and_nonconserved_colour_counts(self):
        g,o=sample();out,rec=p.render(g);self.assertEqual(out,o);self.assertGreater(len(rec['stem_overwritten_cells']),0)
        self.assertNotEqual(rec['before_colour_counts'],rec['after_colour_counts'])
        self.assertEqual(rec['comb_source_cells'],rec['comb_target_cells'])
        self.assertEqual(rec['pin_source_cells'],rec['pin_visible_cells']+rec['pin_clipped_cells'])

    def test_22_all_source_and_unaffected_cells(self):
        g,o=sample();out,rec=p.render(g)
        self.assertEqual(out,o);role=rec['parse']['role']
        self.assertTrue(all(out[r][c]==0 for r,c in role['source_cells']))
        self.assertTrue(all(out[r][c]==g[r][c]for r,c in role['frame_boundary']))
        self.assertEqual(out[12][15],0);self.assertEqual(out[13][15],0)

    def test_23_invalid_grid_and_bg_tie(self):
        for g in([],[[0],[]],[[True]],[[10]],[[0]*31],[[0]]*31):self.hold(g,'invalid_arc_grid')
        self.hold([[0,1]],'background_mode_tie')
        g,o=sample(height=30,width=30);self.assertEqual(p.render(g)[0],o)

    def test_24_teacher_fit_and_boolean_detachment(self):
        a,ao=sample();b,bo=sample(source_first=1);train=[{'input':a,'output':ao},{'input':b,'output':bo}]
        state,r=p.fit_teachers(train);self.assertIs(state,True);self.assertEqual(r['pair_fits'],[True,True])
        self.assertIs(p.fit_teachers(train[::-1])[0],True);self.assertIs(p.fit_teachers([train[0],train[0]])[0],False)
        bad=copy.deepcopy(train);bad[0]['output'][0][0]=9;self.assertIs(p.fit_teachers(bad)[0],False)
        train[0]['input'][:]=[[0]];train[0]['output'][:]=[[0]];self.assertIs(state,True);self.assertEqual(p.render(b)[0],bo)

    def test_25_source_tooth_break_cannot_be_ignored(self):
        g,o=sample();g[10][2]=0;self.hold(g,'joint_input_role_not_unique')

    def test_26_extra_coloured_pin_cannot_be_ignored(self):
        g,o=sample()
        for r in range(3,8):g[r][25]=8
        rec=self.hold(g,'all_teeth_pins_count_mismatch');self.assertEqual(rec['parse']['input_role_count'],1)


    def test_27_native_support_is_two_boards(self):
        a,ao=sample();b,bo=sample(heights=(6,4,7));train=[{'input':a,'output':ao},{'input':b,'output':bo}]
        material=p.櫛配置教材(train);self.assertEqual(vars(material),{'適合':True})
        for minimum,admitted in[(2,True),(3,False)]:
            machine=HDS学習実行系(最小支持数=minimum)
            rec=候補機構を学習(machine,{'train':train,'test':[]},(),'ARC櫛配置押上げ',material.候補)
            self.assertEqual(rec['現在観測数'],2);self.assertEqual(rec['事前観測数'],0)
            self.assertEqual(rec['同値採用'],admitted);self.assertEqual(rec['隔離数'],0)

    def test_28_partial_native_hold_is_input_derived(self):
        a,ao=sample();b,bo=sample(heights=(6,4,7));train=[{'input':a,'output':ao},{'input':b,'output':bo}]
        good,expected=sample(source_first=3)
        bad,_=sample(heights=(9,3,7),pin_ranges=((5,9),(5,11),(6,12)))
        for queries,answers in[([good,bad],[expected,None]),([bad,good],[None,expected])]:
            result=課題を解く({'train':train,'test':[{'input':g}for g in queries]},[])
            self.assertEqual([r['answer']for r in result['results']],answers)
        train2=copy.deepcopy(train);material=p.櫛配置教材(train2);train2[0]['input'][:]=[[0]];train2[0]['output'][:]=[[0]]
        self.assertEqual(vars(material),{'適合':True});self.assertEqual(material.候補(good,None)[0],expected)

    def test_29_identifier_and_test_output_rejected(self):
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[],'task_id':'forbidden'},[])
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[{'input':[[0]],'output':[[0]]}]},[])

if __name__=='__main__':unittest.main()
