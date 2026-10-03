"""D4色規約・全best証明・上限・native教師盤面支持の回帰。"""
import copy,unittest
from unittest.mock import patch
from pathlib import Path
import sys
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 接触配置教材 as g
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,課題を解く

def sample(two=False,ambiguous=False):
    h,w=(24,20)if two else(14,16);x=[[0]*w for _ in range(h)]
    shape={(0,1):2,(0,2):2,(1,0):3,(2,0):3}
    if ambiguous:shape={(0,1):2,(0,2):3,(1,0):2,(2,0):3}
    for top,left in ([(2,14),(10,14)]if two else[(2,10)]):
        for(r,c),v in shape.items():x[top+r][left+c]=v
    for top,left in ([(6,2),(16,2)]if two else[(6,2)]):
        dest={(top+r,left+c)for r,c in shape}
        boundary={(r+dr,c+dc)for r,c in dest for dr,dc in [(1,0),(-1,0),(0,1),(0,-1)]}-dest
        for r,c in boundary:x[r][c]=5
    return x

def overlapping_best():
    x=[[0]*4 for _ in range(15)]
    for top,left in [(1,0),(5,2)]:
        for r in range(2):
            for c in range(2):x[top+r][left+c]=2+r
    for r in [11,12]:x[r][0]=5;x[r][3]=6
    return x

class Controls(unittest.TestCase):
    def test_same_grid_d4_duplicates_remain(self):
        x=sample();out,record=g.guarded_render(x);self.assertIsNotNone(out)
        self.assertEqual(record['complete_assignments'],2);self.assertEqual(record['best_assignments'],2)
        self.assertEqual(record['best_score'],12);self.assertTrue(record['exhausted'])
        self.assertEqual(sum(v!=0 for row in out for v in row),14)
        self.assertEqual([out[6][3],out[6][4],out[7][2],out[8][2]],[2,2,3,3])
    def test_all_best_outputs_must_agree(self):
        out,record=g.guarded_render(sample(ambiguous=True));self.assertIsNone(out)
        self.assertEqual(record['failure'],'best_assignment_grids_disagree');self.assertEqual(record['best_assignments'],2)
    def test_bijective_multiple_payloads_all_same_grid(self):
        x=sample(two=True);out,record=g.guarded_render(x);self.assertIsNotNone(out)
        self.assertEqual(record['roles']['payload_count'],2);self.assertEqual(record['roles']['slot_group_count'],2)
        self.assertEqual(record['complete_assignments'],8);self.assertEqual(record['best_assignments'],8)
        self.assertEqual(sum(v in(2,3)for row in out for v in row),8)
        self.assertEqual(sum(v==5 for row in out for v in row),20)
    def test_same_colour_or_different_colour_overlap_veto(self):
        out,record=g.guarded_render(overlapping_best());self.assertIsNone(out)
        self.assertEqual(record['failure'],'invalid_best_assignment');self.assertIn('payload_overlap',record['best_failures'])
    def test_budget_after_complete_assignment_holds(self):
        x=sample(two=True);out,record=g.guarded_render(x);self.assertIsNotNone(out)
        limit=sum(p['placement_trials']for p in record['pairs'])+5+7
        with patch.object(g,'PROOF_STATE_LIMIT',limit),patch.object(g,'_chiral_payload_slot_render',side_effect=RuntimeError('must not run')):
            out,record=g.guarded_render(x)
        self.assertIsNone(out);self.assertEqual(record['failure'],'certificate_budget_exhausted')
        self.assertEqual(record['complete_assignments_before_stop'],4);self.assertFalse(record['exhausted'])
    def test_candidate_scanning_budget_precedes_generator(self):
        with patch.object(g,'PROOF_STATE_LIMIT',1),patch.object(g,'_chiral_payload_candidates',side_effect=RuntimeError('must not run')):
            out,record=g.guarded_render(sample())
        self.assertIsNone(out);self.assertEqual(record['failure'],'certificate_budget_exhausted')
    def test_unknown_component_not_silently_ignored(self):
        x=sample();x[11][13]=6;x[11][14]=7;x[11][15]=8
        self.assertIsNotNone(g._chiral_payload_slot_render(x)[0])
        with patch.object(g,'_chiral_payload_candidates',side_effect=RuntimeError('must not run')):
            self.assertEqual(g.guarded_render(x)[1]['failure'],'unassigned_foreground_component')
    def test_small_colour_role_component_is_whole_hold(self):
        x=sample();x[11][13]=6;x[11][14]=7
        self.assertIsNotNone(g._chiral_payload_slot_render(x)[0])
        self.assertEqual(g.guarded_render(x)[1]['failure'],'unassigned_foreground_component')
    def test_foreground_source_consumed_slots_preserved(self):
        x=sample();out,record=g.guarded_render(x);self.assertIsNotNone(out)
        self.assertTrue(all(out[r][c]==5 for r,row in enumerate(x)for c,v in enumerate(row)if v==5))
        self.assertTrue(all(out[r][c]==0 for r,row in enumerate(x)for c,v in enumerate(row)if v in(2,3)))
    def test_original_grid_and_record_are_required(self):
        original=g._chiral_payload_slot_render
        for record_change in [False,True]:
            def corrupt(x):
                out,record=original(x)
                if record_change:record=dict(record,assignment_score=999)
                else:out[0][0]=9
                return out,record
            with patch.object(g,'_chiral_payload_slot_render',corrupt):self.assertEqual(g.guarded_render(sample())[1]['failure'],'original_grid_or_record_disagreement')
    def test_original_failure_never_replaced_by_proof(self):
        with patch.object(g,'_chiral_payload_slot_render',return_value=(None,{'failure':'synthetic'})):
            self.assertEqual(g.guarded_render(sample())[1]['failure'],'original_renderer_unresolved')
    def test_raw_teachers_before_certificate(self):
        pairs=[{'input':sample(v),'output':g._chiral_payload_slot_render(sample(v))[0]}for v in [False,True]]
        self.assertTrue(g.fit_teachers(pairs)[0]);pairs[1]['output'][0][0]=9
        with patch.object(g,'guarded_render',side_effect=RuntimeError('must not execute')):self.assertFalse(g.fit_teachers(pairs)[0])
    def test_invalid_duplicate_and_tied_background(self):
        for x in [[],[[0],[]],[[True]],[[10]],[[0,1],[2,3]]]:self.assertIsNone(g.guarded_render(x)[0])
        p={'input':sample(),'output':g._chiral_payload_slot_render(sample())[0]};self.assertFalse(g.fit_teachers([p,p])[0])
    def test_d4_and_colour_relabelling(self):
        x=sample();out,_=g.guarded_render(x)
        for flip in [False,True]:
            a=[r[::-1]for r in x]if flip else copy.deepcopy(x);b=[r[::-1]for r in out]if flip else copy.deepcopy(out)
            for _ in range(4):
                self.assertEqual(g.guarded_render(a)[0],b);a=[list(r)for r in zip(*a[::-1])];b=[list(r)for r in zip(*b[::-1])]
        palette={0:7,2:6,3:0,5:4};self.assertEqual(g.guarded_render([[palette[v]for v in r]for r in x])[0],[[palette[v]for v in r]for r in out])
    def test_same_output_does_not_delete_raw_choice(self):
        x=sample();parsed,_=g.certified_groups(x);bg,payloads,slots=parsed;raw=g._chiral_payload_candidates(x,payloads[0],slots[0],bg);best=max(r['contact_count']for r in raw);retained=[r for r in raw if r['contact_count']==best]
        self.assertEqual(len(retained),2);self.assertEqual({r['transform_index']for r in retained},{0,6})
        self.assertEqual(retained[0]['mapped'],retained[1]['mapped'])
    def test_reflection_swaps_roles_not_colour_counts(self):
        x=[[0]*25 for _ in range(20)]
        shape={(0,1):2,(1,1):2,(2,0):2,(2,1):2,(3,0):2,(3,1):2,**{(r,0):3 for r in range(4,9)},(8,1):3,(8,2):3,(9,2):3}
        for(r,c),v in shape.items():x[1+r][18+c]=v
        dest={(12+c,2+r)for r,c in shape};boundary={(r+dr,c+dc)for r,c in dest for dr,dc in [(1,0),(-1,0),(0,1),(0,-1)]}-dest
        for r,c in boundary:x[r][c]=5
        out,record=g.guarded_render(x);self.assertIsNotNone(out);self.assertEqual(record['raw_record']['transform_indices'],[6])
        self.assertEqual(sum(v==2 for row in out for v in row),8);self.assertEqual(sum(v==3 for row in out for v in row),6)
        self.assertEqual(sum(v!=0 for row in out for v in row),38)
    def test_original_group_must_match_whole_closure(self):
        original=g._chiral_payload_slot_groups
        def corrupt(x):
            parsed=original(x);parsed[2][0]['cells'].pop();return parsed
        with patch.object(g,'_chiral_payload_slot_groups',corrupt):self.assertEqual(g.guarded_render(sample())[1]['failure'],'original_slot_closure_disagrees')

    def test_native_support_is_teacher_boards(self):
        pairs=[{'input':sample(v),'output':g._chiral_payload_slot_render(sample(v))[0]}for v in [False,True]]
        material=g.接触配置教材(pairs)
        for minimum,admitted in [(2,True),(3,False)]:
            machine=HDS学習実行系(最小支持数=minimum)
            r=候補機構を学習(machine,{'train':pairs,'test':[]},(),'ARCD4最大接触配置',material.候補)
            self.assertEqual(r['現在観測数'],2);self.assertEqual(r['事前観測数'],0)
            self.assertEqual(r['同値採用'],admitted);self.assertEqual(r['隔離数'],0)
    def test_native_ambiguous_admitted_family_is_hold(self):
        pairs=[{'input':sample(v),'output':g._chiral_payload_slot_render(sample(v))[0]}for v in [False,True]]
        x=sample();bad=sample(ambiguous=True)
        r=課題を解く({'train':pairs,'test':[{'input':x},{'input':bad}]},[])
        self.assertEqual(r['results'][0]['answer'],g.guarded_render(x)[0]);self.assertIsNone(r['results'][1]['answer'])
    def test_no_identifier_or_test_target(self):
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[],'task_id':'forbidden'},[])
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[{'input':[[0]],'output':[[0]]}]},[])

if __name__=='__main__':unittest.main()
