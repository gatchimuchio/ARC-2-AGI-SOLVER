"""全wall/role先決・終端plateau・同列影とnative盤面支持。"""
import copy
import unittest
from unittest.mock import patch
from pathlib import Path
import sys
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 開口壁教材 as p
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,課題を解く


def sample(left=(5,5,6,6,5,5,4,4),right=(13,13,12,12,13,13,14,14),periods=(2,2),height=18,width=19,
           cap=(2,6,12),background=0,wall=2,paint=3,obstacles=((12,9,4),(0,9,5)),cues=((4,9),),thick=False):
    grid=[[background]*width for _ in range(height)];ct,c0,c1=cap
    for x in range(c0,c1+1):grid[ct][x]=wall
    for values,side in((left,'left'),(right,'right')):
        for offset,b in enumerate(values):
            t=ct+1+offset;xs=range(max(0,b-1),b+1)if thick and side=='left'else range(b,min(width,b+2))if thick else(b,)
            for x in xs:grid[t][x]=wall
    for t,x in cues:grid[t][x]=paint
    for t,x,c in obstacles:grid[t][x]=c
    def bound(t,values,sign,period):
        offset=t-ct-1
        return values[offset]if offset<len(values)else values[-1]+sign*(1+(offset-len(values))//period)
    domain={(t,x)for t in range(ct+1,height)for x in range(width)
            if bound(t,left,-1,periods[0])<x<bound(t,right,1,periods[1])}
    expected=[row[:]for row in grid]
    blockers={(t,x)for t,x in domain if grid[t][x]not in(background,wall,paint)}
    for t,x in domain:
        if grid[t][x]==background and not any(bx==x and bt<=t for bt,bx in blockers):expected[t][x]=paint
    return grid,expected,{'domain':domain,'blockers':blockers,'left_end':ct+len(left),'right_end':ct+len(right)}


class OpenWallControls(unittest.TestCase):
    def hold(self,g,failure):
        output,record=p.render(g);self.assertIsNone(output);self.assertEqual(record['failure'],failure);return record

    def test_01_full_grid_direct_cell_formula(self):
        g,o,info=sample();out,r=p.render(g);self.assertEqual(out,o);self.assertEqual(r['raw_role_count'],1)
        self.assertEqual(r['domain_cell_count'],len(info['domain']));self.assertEqual(r['shadowed_bg_count'],5)

    def test_02_all_axes_and_mirror_images(self):
        g,o,_=sample()
        for flipr in(False,True):
            for flipc in(False,True):
                transform=lambda a:[list(reversed(row))if flipc else row[:]for row in(a[::-1]if flipr else a)]
                a,b=transform(g),transform(o);self.assertEqual(p.render(a)[0],b)
                a,b=[list(row)for row in zip(*a)],[list(row)for row in zip(*b)];self.assertEqual(p.render(a)[0],b)

    def test_03_arbitrary_palette_zero_foreground(self):
        g,o,_=sample()
        for permutation in(({0:7,2:0,3:8,4:1,5:2}),({0:9,2:4,3:0,4:8,5:2})):
            mapped=lambda a:[[permutation[v]for v in row]for row in a]
            self.assertEqual(p.render(mapped(g))[0],mapped(o))

    def test_04_thick_rails_are_fully_owned(self):
        g,o,_=sample(thick=True);self.assertEqual(p.render(g)[0],o)
        role,_=p.parse_input(g);wall=role['wall_color'];record=role['record']
        candidate=next(x for x in record['raw_wall_direction_candidates']if x['wall_color']==wall and x['direction']==role['direction'])
        self.assertTrue(candidate['complete_rail_interpretations'][0]['all_wall_cells_owned_exactly_once'])

    def test_05_left_right_different_periods_and_period_three(self):
        g,o,_=sample(left=(5,5,5,5,5,4,3,2),right=(13,13,14,14,14,15,15,15),periods=(1,3))
        out,r=p.render(g);self.assertEqual(out,o);self.assertEqual(r['terminal_parameters']['left']['period'],1);self.assertEqual(r['terminal_parameters']['right']['period'],3)

    def test_06_independent_terminal_rows_at_canvas_edge(self):
        g,o,_=sample(left=(4,4,5,4,3,2),right=(9,9,9,10,11),periods=(1,1),height=16,width=12,cap=(2,5,8),cues=((4,7),))
        out,r=p.render(g);self.assertEqual(out,o);self.assertEqual(r['terminal_parameters']['left']['terminal_t'],8);self.assertEqual(r['terminal_parameters']['right']['terminal_t'],7)

    def test_07_early_rail_end_away_from_canvas_rejects_role(self):
        g,_,_=sample(left=(4,4,5,4,3,2),right=(9,9,9,10,11),periods=(1,1),height=16,width=14,cap=(2,5,8),cues=((4,7),))
        self.hold(g,'joint_role_not_unique')

    def test_08_both_one_run_assignments_are_kept(self):
        g=[[0]*3 for _ in range(7)];g[1]=[2,2,2];g[2]=[2,3,2];g[3]=[0,2,0]
        with patch.object(p,'terminal_parameters',side_effect=AssertionError('ambiguous raw role cannot reach terminal check')):
            r=self.hold(g,'joint_role_not_unique');self.assertGreaterEqual(r['raw_role_count'],2)
            south=next(x for x in r['raw_wall_direction_candidates']if x['wall_color']==2 and x['direction']=='south')
            self.assertEqual(south['complete_rail_interpretation_count'],2)

    def test_09_second_raw_role_with_bad_tail_is_not_removed(self):
        g=[[0]*30 for _ in range(30)]
        for wall,paint,cap0,cap1,left,right in((2,3,5,7,(4,4,3,3),(8,8,9,9)),(4,6,20,22,(19,19,19,19),(23,23,23,23))):
            for x in range(cap0,cap1+1):g[2][x]=wall
            for i,(a,b)in enumerate(zip(left,right)):g[3+i][a]=wall;g[3+i][b]=wall
            g[3][(cap0+cap1)//2]=paint
        with patch.object(p,'terminal_parameters',side_effect=AssertionError('tail cannot select a role')):
            r=self.hold(g,'joint_role_not_unique');self.assertEqual(r['raw_role_count'],2)

    def test_10_entire_cue_colour_must_be_inside_observed_region(self):
        g,_,_=sample();g[0][0]=3;self.hold(g,'joint_role_not_unique')

    def test_11_second_inside_cue_is_ambiguous(self):
        g,_,_=sample();g[4][8]=6
        r=self.hold(g,'joint_role_not_unique');self.assertEqual(r['raw_role_count'],2)

    def test_12_final_two_maximal_plateaus_not_convenient_suffix(self):
        g,_,_=sample(left=(5,5,6,6,5,5,5,4));r=self.hold(g,'terminal_plateau_not_periodic')
        self.assertEqual(r['raw_role_count'],1);self.assertEqual([a['length']for a in r['invalid_rails'][0]['last_two']],[3,1])
        g,_,_=sample(left=(5,5,6,6,5,5,6,6));self.hold(g,'terminal_plateau_not_periodic')
        g,_,_=sample(left=(5,)*8);self.hold(g,'terminal_plateau_not_periodic')

    def test_13_extra_same_wall_pixel_not_ignored(self):
        g,_,_=sample();g[0][0]=2;self.hold(g,'joint_role_not_unique')
        g,_,_=sample();g[6][9]=2;self.hold(g,'joint_role_not_unique')

    def test_14_obstacle_outside_domain_or_behind_cap_no_shadow(self):
        g,o,_=sample(obstacles=((0,9,4),(12,0,5)));out,r=p.render(g);self.assertEqual(out,o)
        self.assertEqual(r['obstacle_encounters'],[]);self.assertEqual(r['shadow_columns'],[])
        self.assertEqual(out[14][9],3)

    def test_15_shadow_persists_through_narrowing_and_foreground_cue(self):
        g,o,_=sample(obstacles=((4,6,4),(0,0,4)),cues=((3,9),(8,6)))
        out,r=p.render(g);self.assertEqual(out,o);self.assertEqual(out[7][6],0);self.assertEqual(out[8][6],3);self.assertEqual(out[9][6],0)
        self.assertEqual(out[5][6],2);self.assertIn(6,r['shadow_columns'])

    def test_16_obstacle_already_in_shadow_is_preserved(self):
        g,o,_=sample(obstacles=((12,9,4),(14,9,5)))
        out,r=p.render(g);self.assertEqual(out,o);self.assertEqual([x['already_shadowed']for x in r['obstacle_encounters']],[False,True]);self.assertEqual(out[14][9],5)

    def test_17_small_cap_lengths_one_and_two(self):
        for a,b,left,right,cue in((8,8,(7,7,6,6),(9,9,10,10),(3,8)),(8,9,(7,7,6,6),(10,10,11,11),(3,8))):
            g,o,_=sample(left=left,right=right,cap=(2,a,b),cues=(cue,),obstacles=())
            self.assertEqual(p.render(g)[0],o)

    def test_18_all_foreground_and_exact_colour_accounting(self):
        g,o,_=sample();out,r=p.render(g);self.assertEqual(out,o)
        self.assertTrue(all(out[y][x]==v for y,row in enumerate(g)for x,v in enumerate(row)if v!=0))
        before,after=dict(r['before_colour_counts']),dict(r['after_colour_counts']);self.assertEqual(before[0]-after[0],r['painted_cell_count']);self.assertEqual(after[3]-before[3],r['painted_cell_count'])
        self.assertEqual(sum(before.values()),sum(after.values()))

    def test_19_no_op_is_accepted_without_late_role_filter(self):
        g,_,info=sample(height=11,obstacles=())
        for t,x in info['domain']:g[t][x]=3
        out,r=p.render(g);self.assertEqual(out,g);self.assertEqual(r['painted_cell_count'],0)

    def test_20_target_independence_and_boolean_detachment(self):
        a,ao,_=sample();b,bo,_=sample(paint=6);train=[{'input':a,'output':ao},{'input':b,'output':bo}]
        state,r=p.fit_teachers(train);self.assertTrue(state)
        bad=copy.deepcopy(train);bad[0]['output'][0][0]=9;self.assertFalse(p.fit_teachers(bad)[0]);self.assertEqual(r['records'],p.fit_teachers(bad)[1]['records'])
        self.assertFalse(p.fit_teachers(train[:1])[0]);self.assertFalse(p.fit_teachers([train[0],train[0]])[0])
        train[0]['input'][:]=[[0]];train[0]['output'][:]=[[0]];self.assertIs(state,True);self.assertEqual(p.render(b)[0],bo)

    def test_21_bg_tie_and_invalid_grid(self):
        self.hold([[0,1]],'background_tie')
        for g in([],[[0],[]],[[True]],[[10]],[[0]*31],[[0]]*31):self.hold(g,'invalid_arc_grid')

    def test_22_disconnected_observed_interior_is_not_split(self):
        g=[[0]*12 for _ in range(12)]
        for x in(1,2):g[1][x]=2
        for x in(0,3,4,5,6,7,8):g[2][x]=2
        for x in(0,1,2,3,6,7,8):g[3][x]=2
        g[2][1]=3
        r=self.hold(g,'joint_role_not_unique')
        candidate=next(a for a in r['raw_wall_direction_candidates']if a['wall_color']==2 and a['direction']=='south')
        self.assertIn('complete branch 0: observed two-rail interior is not one nonempty C4 component',candidate['failed_branch_reasons'])

    def test_23_disappeared_rail_cannot_resume(self):
        g,_,_=sample(left=(4,4,5,4,3,2),right=(9,9,9,10,11),periods=(1,1),height=16,width=12,cap=(2,5,8),cues=((4,7),))
        g[9][11]=2;self.hold(g,'joint_role_not_unique')

    def test_24_wall_cells_do_not_cast_foreground_shadows(self):
        g,o,_=sample();out,r=p.render(g);self.assertEqual(out,o)
        self.assertEqual(g[6][6],2);self.assertEqual(g[7][6],0);self.assertEqual(out[7][6],3)
        self.assertNotIn(6,r['shadow_columns'])

    def test_25_background_may_disappear_after_complete_fill(self):
        g,o,_=sample(left=(0,1,1,0,0),right=(10,9,9,10,10),periods=(2,2),height=6,width=11,cap=(0,0,10),cues=((1,5),),obstacles=(),thick=True)
        out,r=p.render(g);self.assertEqual(out,o);self.assertNotIn(0,{v for row in out for v in row})
        self.assertEqual(dict(r['before_colour_counts'])[0],r['painted_cell_count'])


    def test_26_native_support_is_three_boards(self):
        train=[]
        for paint in(3,6,9):
            g,o,_=sample(paint=paint);train.append({'input':g,'output':o})
        material=p.開口壁教材(train);self.assertEqual(vars(material),{'適合':True})
        for minimum,admitted in((3,True),(4,False)):
            machine=HDS学習実行系(最小支持数=minimum)
            record=候補機構を学習(machine,{'train':train,'test':[]},(),'ARC開口壁充填',material.候補)
            self.assertEqual(record['現在観測数'],3);self.assertEqual(record['事前観測数'],0)
            self.assertEqual(record['同値採用'],admitted);self.assertEqual(record['隔離数'],0)

    def test_27_native_query_hold_and_boolean_state(self):
        train=[]
        for paint in(3,6,9):
            g,o,_=sample(paint=paint);train.append({'input':g,'output':o})
        good,expected,_=sample(paint=7);bad=copy.deepcopy(good);bad[0][0]=7
        for queries,answers in(([good,bad],[expected,None]),([bad,good],[None,expected])):
            result=課題を解く({'train':train,'test':[{'input':g}for g in queries]},[])
            self.assertEqual([row['answer']for row in result['results']],answers)
        material=p.開口壁教材(train);train[0]['input'][:]=[[0]];train[0]['output'][:]=[[0]]
        self.assertEqual(vars(material),{'適合':True});self.assertEqual(material.候補(good,None)[0],expected)

    def test_28_identifier_and_test_output_rejected(self):
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[],'task_id':'forbidden'},[])
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[{'input':[[0]],'output':[[0]]}]},[])

if __name__=='__main__':unittest.main()
