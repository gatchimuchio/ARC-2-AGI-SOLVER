"""全policy・全tile・区間制約・四lane範囲とnative教師盤面支持の回帰。"""
import copy,unittest
from unittest.mock import patch
from pathlib import Path
import sys
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 枠列整列教材 as g
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,課題を解く

def tile(x,top,left,n,outer,inner):
    for r in range(n):
        for c in range(n):x[top+r][left+c]=outer if r in(0,n-1)or c in(0,n-1)else inner

def policy(n=3,margin=1,reverse=False):
    return{'tile_shape':[n,n],'side_by_outer':{'2':'R'if reverse else'L','8':'L'if reverse else'R'},'lane_edge_offset':margin}

def sample(variant=False):
    x=[[0]*16 for _ in range(16)];d=int(variant)
    for top,left,outer,inner in [(1+d,4,2,3),(2+d,10,2,4),(7+d,1,8,6),(8+d,7,8,7)]:tile(x,top,left,3,outer,inner)
    return x

def teacher(variant=False,reverse=False):
    x=sample(variant);return{'input':x,'output':g._framed_tile_group_relinearization_render(x,policy(reverse=reverse))[0]}

class Controls(unittest.TestCase):
    def test_policy_learns_size_sides_and_margin(self):
        p,r=g.fit_teachers([teacher(),teacher(True)]);self.assertIsNotNone(p)
        self.assertEqual(p['tile_shape'],[3,3]);self.assertEqual(p['side_by_outer'],{'2':'L','8':'R'});self.assertEqual(p['lane_edge_offset'],1)
        q,_=g.fit_teachers([teacher(reverse=True),teacher(True,True)]);self.assertEqual(q['side_by_outer'],{'2':'R','8':'L'})
    def test_all_tiles_and_colours_conserved(self):
        x=sample();out,r=g.guarded_render(x,policy());self.assertIsNotNone(out)
        self.assertEqual(r['processed_tiles'],4);self.assertEqual(r['foreground_pixels'],36)
        self.assertEqual(g.Counter(v for row in x for v in row),g.Counter(v for row in out for v in row))
        self.assertNotEqual(r['destination_writes_changed'],r['whole_grid_changed_cells'])
    def test_destination_may_use_another_old_source(self):
        x=sample();out,r=g.guarded_render(x,policy());self.assertIsNotNone(out)
        self.assertEqual(x[8][9],8);self.assertEqual(out[8][9],8)
        self.assertEqual(r['raw_record']['framed_tile_relinearization_lane_records'][2]['target_anchor'],[7,9])
    def test_noop_and_unmoved_tiles_remain(self):
        first,_=g.guarded_render(sample(),policy());again,r=g.guarded_render(first,policy())
        self.assertEqual(again,first);self.assertEqual(r['unmoved_tiles'],4);self.assertEqual(r['whole_grid_changed_cells'],0)
        self.assertEqual(r['raw_record']['framed_tile_relinearization_event_count'],4)
    def test_adjacent_vertical_intervals_are_not_overlapping(self):
        group=[{'row':1,'col':2},{'row':4,'col':8}];lanes,r=g.certify_lanes(group,'L',3)
        self.assertEqual(lanes,[0,0]);self.assertEqual(r['interval_edges'],[]);self.assertEqual(r['isolated_default_indices'],[0,1])
        group[1]['row']=3;self.assertEqual(g.certify_lanes(group,'L',3)[0],[0,1]);self.assertEqual(g.certify_lanes(group,'R',3)[0],[1,0])
    def test_all_pair_constraints_no_late_selection(self):
        x=[[0]*22 for _ in range(16)]
        for top,left,outer,inner in [(1,0,2,3),(1,4,2,4),(1,8,2,5),(8,0,8,6),(9,5,8,7)]:tile(x,top,left,3,outer,inner)
        self.assertIsNone(g._framed_tile_group_relinearization_render(x,policy())[0]);self.assertEqual(g.guarded_render(x,policy())[1]['failure'],'interval_constraints_conflict')
    def test_extra_foreground_not_silently_discarded(self):
        x=sample();x[15][15]=9
        self.assertIsNone(g._framed_tile_group_relinearization_render(x,policy())[0]);self.assertEqual(g.guarded_render(x,policy())[1]['failure'],'original_inventory_unresolved')
    def test_inner_colour_may_equal_other_border_colour(self):
        x=sample();x[8][2]=2
        out,r=g.guarded_render(x,policy());self.assertIsNotNone(out);self.assertEqual(out[8][10],2)
    def test_four_lane_domain_not_only_used_lane_bounds(self):
        self.assertEqual(g.guarded_render(sample(),policy(margin=3))[1]['failure'],'four_lane_bounds_failed')
    def test_background_tie_is_hold(self):
        x=[[0]*13 for _ in range(6)]
        for top,left,outer,inner in [(0,0,1,3),(0,4,1,4),(0,8,2,6),(3,0,1,7),(3,4,2,8),(3,8,2,9)]:tile(x,top,left,3,outer,inner)
        p={'tile_shape':[3,3],'side_by_outer':{'1':'L','2':'R'},'lane_edge_offset':0}
        self.assertIsNotNone(g._framed_tile_group_relinearization_render(x,p)[0]);self.assertEqual(g.guarded_render(x,p)[1]['failure'],'background_tie')
    def test_original_grid_and_record_only(self):
        original=g._framed_tile_group_relinearization_render
        for record_change in [False,True]:
            def corrupt(x,p):
                out,r=original(x,p)
                if record_change:r=dict(r,framed_tile_relinearization_event_count=999)
                else:out[0][0]=9
                return out,r
            with patch.object(g,'_framed_tile_group_relinearization_render',corrupt):self.assertEqual(g.guarded_render(sample(),policy())[1]['failure'],'original_grid_or_record_disagreement')
    def test_multiple_raw_policies_before_guard(self):
        pairs=[teacher(),teacher(True)];model,_=g.fit_teachers(pairs)
        with patch.object(g,'_framed_tile_group_relinearization_policy',return_value=model),patch.object(g,'guarded_render',side_effect=RuntimeError('must not run')):
            out,r=g.fit_teachers(pairs)
        self.assertIsNone(out);self.assertEqual(r['raw_policy_count'],6)
    def test_raw_teacher_failure_before_guard(self):
        pairs=[teacher(),teacher(True)];pairs[1]['output'][0][0]=9
        with patch.object(g,'guarded_render',side_effect=RuntimeError('must not run')):self.assertIsNone(g.fit_teachers(pairs)[0])
    def test_invalid_duplicate_or_changed_learned_palette(self):
        self.assertIsNone(g.fit_teachers([teacher(),teacher()])[0])
        for x in [[],[[0],[]],[[True]],[[10]]]:self.assertIsNone(g.guarded_render(x,policy())[0])
        p=policy();p['side_by_outer']={'2':'L','7':'R'};self.assertEqual(g.guarded_render(sample(),p)[1]['failure'],'learned_side_roles_disagree')
    def test_palette_remapping_and_vertical_reflection(self):
        x=sample();out,_=g.guarded_render(x,policy());self.assertEqual(g.guarded_render(x[::-1],policy())[0],out[::-1])
        colours={0:5,1:1,2:7,3:0,4:9,5:4,6:3,7:6,8:2};p={'tile_shape':[3,3],'side_by_outer':{'7':'L','2':'R'},'lane_edge_offset':1}
        self.assertEqual(g.guarded_render([[colours[v]for v in row]for row in x],p)[0],[[colours[v]for v in row]for row in out])

    def test_native_support_is_teacher_boards(self):
        pairs=[teacher(),teacher(True)];material=g.枠列整列教材(pairs)
        for minimum,admitted in [(2,True),(3,False)]:
            machine=HDS学習実行系(最小支持数=minimum)
            r=候補機構を学習(machine,{'train':pairs,'test':[]},(),'ARC枠tile二列整列',material.候補)
            self.assertEqual(r['現在観測数'],2);self.assertEqual(r['事前観測数'],0)
            self.assertEqual(r['同値採用'],admitted);self.assertEqual(r['隔離数'],0)
    def test_native_admitted_unresolved_is_hold(self):
        pairs=[teacher(),teacher(True)];x=sample();bad=sample();bad[15][15]=9
        r=課題を解く({'train':pairs,'test':[{'input':x},{'input':bad}]},[])
        self.assertEqual(r['results'][0]['answer'],g.guarded_render(x,policy())[0]);self.assertIsNone(r['results'][1]['answer'])
    def test_no_identifier_or_test_target(self):
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[],'task_id':'forbidden'},[])
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[{'input':[[0]],'output':[[0]]}]},[])
    def test_arc_four_lane_size_boundary(self):
        for n,width,accepted in [(7,28,True),(8,30,False)]:
            x=[[0]*width for _ in range(30)]
            for top,left,outer,inner in [(1,0,2,3),(2,10,2,4),(16,0,8,6),(17,10,8,7)]:tile(x,top,left,n,outer,inner)
            out,r=g.guarded_render(x,policy(n=n,margin=0));self.assertEqual(out is not None,accepted)
            if accepted:self.assertEqual(r['foreground_pixels'],196)
            else:self.assertEqual(r['failure'],'four_lane_bounds_failed')

if __name__=='__main__':unittest.main()
