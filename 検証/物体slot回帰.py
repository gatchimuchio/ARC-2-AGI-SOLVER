"""物体slotの全対応証明と消去witness/native盤面支持の分離。"""
from pathlib import Path
import sys,copy,unittest
from unittest.mock import patch
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 物体slot教材 as g
from 接続.ARC2 import 既存物体slot as raw
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,出力格子,観測へ,課題を解く

def sample(noise=True):
    x=[[1]*18 for _ in range(15)]
    for r in range(3,10):x[r][3]=3
    for r in (4,8):
        for c in range(3,7):x[r][c]=3
    x[6][4]=3;x[6][13]=2
    if noise:x[12][1]=2
    return x

def crossing(conflict=True):
    x=[[1]*18 for _ in range(16)]
    for r in range(3,10):x[r][3]=3
    for r in (4,8):
        for c in range(3,7):x[r][c]=3
    x[6][4]=3
    for c in range(8,15):x[2][c]=3
    for r in range(2,6):x[r][8]=3
    for r in range(2,7):x[r][14]=3
    if conflict:
        for r in range(2,5):x[r][10]=3
    x[5][13]=3;x[6][13]=2;x[12][10]=2;x[13][10]=2
    return x

def pair(noise=True,alternate=False):
    x=sample(noise)
    if alternate:x=[[{1:5,3:6}.get(v,v)for v in row]for row in x]
    return {'input':x,'output':raw.render_object_slot_marker_corridor_projector(x,2,4)[0]}

class 物体slot回帰(unittest.TestCase):
    def test_own_object_support_not_borrowed(self):
        x=[[1]*14 for _ in range(13)]
        for r in range(2,9):x[r][4]=3
        for c in range(4,7):x[2][c]=3
        x[10][5]=3;x[5][10]=2
        self.assertIsNotNone(raw.render_object_slot_marker_corridor_projector(x,2,4)[0])
        self.assertEqual(g.guarded_render(x,2,4,True)[1]['failure'],'event_borrows_other_object_support')

    def test_real_slot_corridor_conflict(self):
        x=crossing();out,rec=raw.render_object_slot_marker_corridor_projector(x,2,4);self.assertIsNotNone(out);self.assertEqual(rec['object_slot_pair_count'],2)
        self.assertEqual(g.guarded_render(x,2,4,True)[1]['failure'],'proposal_colour_conflict')

    def test_source_event_order_changes_real_conflict_cell(self):
        x=crossing();policy,_=raw.object_slot_policy(x,2);expected,_=raw.render_object_slot_marker_corridor_projector(x,2,4);policy['events'].reverse()
        with patch.object(raw,'object_slot_policy',return_value=(policy,{})):
            reversed_grid,_=raw.render_object_slot_marker_corridor_projector(x,2,4)
        self.assertNotEqual(expected[6][10],reversed_grid[6][10])
        self.assertEqual(sum(a!=b for ar,br in zip(expected,reversed_grid)for a,b in zip(ar,br)),1)

    def test_same_corridor_overlap_union(self):
        x=crossing(False);out,z=g.guarded_render(x,2,4,True);self.assertIsNotNone(out);self.assertEqual(z['pair_count'],2)
        self.assertEqual(z['selected_marker_pixels'],3);self.assertEqual(z['slot_pixels'],3)
        self.assertLess(z['corridor_union_pixels'],sum(e['path_cell_count']+e['marker_cell_count']for e in z['events']))

    def test_unmatched_objects_preserved(self):
        x=sample();x[12][12]=3;out,z=g.guarded_render(x,2,4,True);self.assertIsNotNone(out);self.assertEqual(out[12][12],3)
        self.assertEqual(z['pair_count'],1)

    def test_exact_unmatched_removal_permission(self):
        x=sample();self.assertEqual(g.guarded_render(x,2,4,False)[1]['failure'],'unwitnessed_unmatched_marker_removal')
        out,z=g.guarded_render(x,2,4,True);self.assertIsNotNone(out);self.assertEqual(z['unmatched_marker_pixels'],1)
        self.assertEqual(out[12][1],1);self.assertEqual(sum(v==2 for row in out for v in row),1)

    def test_no_witness_training_does_not_grant_removal(self):
        model,z=g.fit_teachers([pair(False),pair(False,True)]);self.assertIsNotNone(model);self.assertEqual(model['unmatched_removal_witnesses'],0)
        self.assertFalse(model['allow_unmatched_removal']);self.assertIsNone(g.guarded_render(sample(),2,4,model['allow_unmatched_removal'])[0])

    def test_one_complete_teacher_witness_separate_from_support(self):
        model,z=g.fit_teachers([pair(True),pair(False,True)]);self.assertEqual(model['unmatched_removal_witnesses'],1)
        self.assertIsNotNone(g.guarded_render(sample(),2,4,model['allow_unmatched_removal'])[0])

    def test_raw_multiple_pairings_not_selected(self):
        x=sample(False);x[6][4]=1
        x[5][4]=3;x[7][4]=3;x[6][13]=1;x[5][13]=2;x[7][13]=2
        out,z=g.guarded_render(x,2,4,True);self.assertIsNone(out);self.assertEqual(z['raw_record']['failure'],'object_slot_ambiguous_marker_slot_pairs')

    def test_nonrectangular_marker_not_silently_dropped(self):
        x=sample();x[12][2]=2;x[13][1]=2
        out,z=g.guarded_render(x,2,4,True);self.assertIsNone(out);self.assertEqual(z['raw_record']['failure'],'object_slot_non_rectangular_marker_component')

    def test_raw_teacher_failure_precedes_structure_and_witness(self):
        pairs=[pair(),pair(alternate=True)];pairs[0]['output'][0][0]=3
        with patch.object(g,'guarded_render',side_effect=AssertionError('guard before raw fit')):
            model,z=g.fit_teachers(pairs)
        self.assertIsNone(model);self.assertEqual(z['failure'],'raw_teacher_reproduction_failed');self.assertNotIn('unmatched_removal_witnesses',z)

    def test_failed_structure_cannot_grant_witness(self):
        with patch.object(g,'guarded_render',return_value=(None,{'failure':'injected'})):
            model,z=g.fit_teachers([pair(),pair(alternate=True)])
        self.assertIsNone(model);self.assertEqual(z['failure'],'teacher_certificate_failed');self.assertNotIn('unmatched_removal_witnesses',z)

    def test_original_grid_and_record_only(self):
        x=sample();out,r=raw.render_object_slot_marker_corridor_projector(x,2,4);bad=copy.deepcopy(out);bad[0][0]=9
        for output,record in((bad,r),(out,dict(r,object_slot_pair_count=99))):
            with patch.object(g,'render_object_slot_marker_corridor_projector',return_value=(output,record)):
                self.assertEqual(g.guarded_render(x,2,4,True)[1]['failure'],'source_output_or_record_disagreement')

    def test_duplicate_and_single_teachers_rejected(self):
        p=pair();self.assertIsNone(g.fit_teachers([p])[0]);self.assertIsNone(g.fit_teachers([p,p])[0])

    def test_valid_arc_and_new_colour(self):
        for x in ([],[[True]],[[10]],[[0],[0,1]],[[0]*31]):self.assertEqual(g.guarded_render(x,2,4,True)[1]['failure'],'invalid_arc_grid')
        self.assertEqual(g.guarded_render(sample(),2,2,True)[1]['failure'],'invalid_role_colors')
        x=sample();x[0][0]=4;self.assertIsNone(g.guarded_render(x,2,4,True)[0])

    def test_完全合成盤面と保存範囲(self):
        x=sample();expected=copy.deepcopy(x);expected[12][1]=1;expected[6][5]=2
        for c in range(6,14):expected[6][c]=4
        out,z=g.guarded_render(x,2,4,True);self.assertEqual(out,expected)
        self.assertEqual(z['selected_marker_pixels'],1);self.assertEqual(z['slot_pixels'],1)
        self.assertEqual(z['unmatched_marker_pixels'],1);self.assertEqual(z['pair_count'],1)
        self.assertEqual(z['raw_record']['object_slot_event_count'],z['changed_pixels'])
    def test_D4と配色(self):
        x=sample();expected=copy.deepcopy(x);expected[12][1]=1;expected[6][5]=2
        for c in range(6,14):expected[6][c]=4
        for k in range(8):
            for offset in(0,3,7):
                def t(grid):
                    out=[row[::-1]if k//4 else row[:]for row in grid]
                    for _ in range(k%4):out=[list(row)for row in zip(*out[::-1])]
                    return [[(v+offset)%10 for v in row]for row in out]
                self.assertEqual(g.guarded_render(t(x),(2+offset)%10,(4+offset)%10,True)[0],t(expected))
    def test_native三盤面とwitness二件を分離(self):
        x=[[{1:7,3:8}.get(v,v)for v in row]for row in sample()]
        pairs=[pair(),pair(False,True),{'input':x,'output':raw.render_object_slot_marker_corridor_projector(x,2,4)[0]}]
        view=g.物体slot教材(pairs);self.assertEqual(view.モデル['unmatched_removal_witnesses'],2)
        boundary='物体slot対照';engine=HDS学習実行系(最小支持数=3)
        self.assertFalse(候補機構を学習(engine,{'train':pairs[:2]},[],boundary,view.候補)['同値採用'])
        engine=HDS学習実行系(最小支持数=3);record=候補機構を学習(engine,{'train':pairs},[],boundary,view.候補)
        self.assertTrue(record['同値採用']);self.assertTrue(record['採用可']);self.assertEqual(record['現在観測数'],3);self.assertEqual(record['事前観測数'],0)
        q=pairs[0]['output'];self.assertEqual(出力格子(engine,観測へ({'候補':q},boundary),同値必須=True)['answer'],q)
        engine.実行(観測へ({'候補':q,'出力':[[9]]},boundary));self.assertIsNone(出力格子(engine,観測へ({'候補':q},boundary),同値必須=True)['answer'])
    def test_採用済み失敗全体HOLDと情報分離(self):
        x=[[{1:7,3:8}.get(v,v)for v in row]for row in sample()]
        pairs=[pair(),pair(False,True),{'input':x,'output':raw.render_object_slot_marker_corridor_projector(x,2,4)[0]}]
        task={'train':pairs,'test':[{'input':crossing()}]};result=課題を解く(task,[])
        record=next(r for r in result['families']if r['境界']=='ARC物体slot標識回廊')
        self.assertTrue(record['同値採用']);self.assertEqual(record['現在観測数'],3);self.assertIsNone(result['results'][0]['answer'])
        task['task_id']='forbidden'
        with self.assertRaises(ValueError):課題を解く(task,[])
        task.pop('task_id');task['test'][0]['output']=[[1]]
        with self.assertRaises(ValueError):課題を解く(task,[])

if __name__=='__main__':unittest.main()
