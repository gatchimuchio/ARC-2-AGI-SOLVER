"""境界軸の全pixel所有・消去範囲・旧prior同値とnative支持の回帰。"""
from pathlib import Path
from copy import deepcopy
from collections import Counter
import sys
import unittest
from unittest.mock import patch
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 軸投射教材 as g
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,課題を解く

def case(height=11,width=15,vertical='top',horizontal='right',background=0,marker=1,object_colour=2):
    grid=[[background]*width for _ in range(height)]
    objects={(2,4),(2,5),(3,5),(3,7),(3,9),(4,9),(5,3),(5,7),(6,4),(7,4),(7,8),(8,10)}
    for r,c in objects:grid[r][c]=object_colour
    if vertical:grid[0 if vertical=='top'else height-1][7]=marker
    if horizontal:grid[5][0 if horizontal=='left'else width-1]=marker
    return grid


def examples():
    grids=[case(),case(vertical='bottom',horizontal=None),case(vertical=None,horizontal='left')]
    return [{'input':x,'output':g.source.render_edge_marker_axis_projection(x)[0]} for x in grids]


class Controls(unittest.TestCase):
    def test_three_generated_teacher_grids(self):
        train=examples();model,record=g.fit_teachers(train)
        self.assertIsNotNone(model);self.assertEqual(len(record['teacher_records']),3)
        self.assertTrue(all(r['exact'] for r in record['teacher_records']))

    def test_all_orientations_and_non_square(self):
        grid=case();expected,_=g.source.render_edge_marker_axis_projection(grid)
        self.assertIsNotNone(expected)
        for mirror in [False,True]:
            x=[r[::-1]for r in grid]if mirror else deepcopy(grid)
            y=[r[::-1]for r in expected]if mirror else deepcopy(expected)
            for _ in range(4):
                out,record=g.guarded_render(x);self.assertEqual(out,y)
                c=record['certificate'];self.assertEqual(c['output_object_count'],c['input_object_count']-len(c['erased_cells']))
                x=[list(r)for r in zip(*x[::-1])];y=[list(r)for r in zip(*y[::-1])]

    def test_arbitrary_colour_roles_including_zero(self):
        for background,marker,obj in [(7,0,9),(2,9,0),(8,4,5),(0,3,7)]:
            x=case(background=background,marker=marker,object_colour=obj)
            out,record=g.guarded_render(x);self.assertIsNotNone(out)
            c=record['certificate'];counts=Counter(v for row in out for v in row)
            self.assertEqual(counts[obj],c['output_object_count']);self.assertEqual(counts[marker],c['actual_marker_cells'])

    def test_every_single_marker_edge_preserves_object_count(self):
        for v,h in [('top',None),('bottom',None),(None,'left'),(None,'right')]:
            out,record=g.guarded_render(case(vertical=v,horizontal=h));self.assertIsNotNone(out)
            self.assertEqual(record['certificate']['erased_cells'],[])
            self.assertEqual(record['certificate']['output_object_count'],12)

    def test_each_double_marker_erases_only_opposite_group(self):
        for v in ['top','bottom']:
            for h in ['left','right']:
                x=case(vertical=v,horizontal=h);out,record=g.guarded_render(x);self.assertIsNotNone(out)
                opposite={(r,c)for r,row in enumerate(x)for c,value in enumerate(row)
                          if value==2 and r!=5 and c!=7 and ((r<5)!=(v=='top'))and((c<7)!=(h=='left'))}
                self.assertEqual({tuple(p)for p in record['certificate']['erased_cells']},opposite)

    def test_disconnected_pixels_all_have_roles(self):
        x=case();x[9][11]=2;x[1][1]=2
        out,record=g.guarded_render(x);self.assertIsNotNone(out);c=record['certificate']
        roles=[tuple(p)for p in c['original_axis_cells']+c['erased_cells']]
        roles+=[tuple(p)for q in c['groups']for p in q['source_cells']]
        objects={(r,col)for r,row in enumerate(x)for col,v in enumerate(row)if v==2}
        self.assertEqual(len(roles),len(set(roles)));self.assertEqual(set(roles),objects)

    def test_all_axis_object_pixels_no_groups_can_succeed(self):
        x=[[0]*9 for _ in range(8)];x[0][4]=1;x[4][4]=2
        out,record=g.guarded_render(x);self.assertIsNotNone(out)
        self.assertEqual(record['certificate']['groups'],[])
        self.assertEqual(record['certificate']['actual_marker_cells'],4)
        self.assertEqual(out[4][4],2)

    def test_original_identity_hold_preserved(self):
        x=[[0]*9 for _ in range(8)];x[0][4]=1
        for r in range(1,6):x[r][4]=2
        self.assertIsNone(g.source.render_edge_marker_axis_projection(x)[0])
        out,record=g.guarded_render(x);self.assertIsNone(out)
        self.assertEqual(record['original']['failure'],'identity_render')

    def test_empty_or_absent_marker(self):
        for x in [[[0]*8 for _ in range(8)],case(vertical=None,horizontal=None)]:
            out,record=g.guarded_render(x);self.assertIsNone(out)
            self.assertEqual(record['failure'],'original_renderer_failed')

    def test_corner_or_too_many_axis_markers(self):
        for mutations in [[(0,7,0),(0,0,1)],[(10,7,1)],[(0,6,1)]]:
            x=case()
            for r,c,v in mutations:x[r][c]=v
            self.assertIsNone(g.guarded_render(x)[0])

    def test_ambiguous_raw_marker_colour_is_not_selected(self):
        x=[[0]*9 for _ in range(9)];x[0][3]=1;x[8][5]=2
        out,record=g.guarded_render(x);self.assertIsNone(out)
        self.assertEqual(record['original']['marker_candidate_count'],2)

    def test_missing_one_axis_witness_rejects_whole_input(self):
        x=case();x[0][7]=0;x[0][6]=1
        out,record=g.guarded_render(x);self.assertIsNone(out)
        self.assertEqual(record['original']['failure'],'vertical_axis_has_no_object_cells')

    def test_boundary_object_pixel_is_not_ignored(self):
        x=case();x[10][2]=2
        out,record=g.guarded_render(x);self.assertIsNone(out)
        self.assertEqual(record['original']['failure'],'object_touches_edge')

    def test_extra_unknown_colour_is_not_ignored(self):
        x=case();x[4][4]=3
        self.assertIsNone(g.guarded_render(x)[0])

    def test_unique_background_is_additional_guard(self):
        x=[[0]*7 for _ in range(7)]
        for r in range(1,6):
            for c in range(1,6):x[r][c]=2
        x[3][2]=0;x[0][3]=1
        self.assertIsNotNone(g.source.render_edge_marker_axis_projection(x)[0])
        out,record=g.guarded_render(x);self.assertIsNone(out);self.assertEqual(record['failure'],'background_tie')

    def test_every_translation_is_injective_and_nonoverlapping(self):
        x=case();out,record=g.guarded_render(x);self.assertIsNotNone(out);c=record['certificate']
        destinations=[]
        for q in c['groups']:
            dr,dc=q['shift'];translated={(r+dr,col+dc)for r,col in q['source_cells']}
            self.assertEqual(translated,{tuple(p)for p in q['destinations']})
            self.assertEqual(len(translated),len(q['source_cells']));destinations+=list(translated)
        self.assertEqual(len(destinations),len(set(destinations)))
        self.assertFalse(set(destinations)&{tuple(p)for p in c['axis_segment_cells']})

    def test_marker_segment_count_is_not_actual_marker_colour_count(self):
        out,record=g.guarded_render(case());self.assertIsNotNone(out)
        old,c=record['original'],record['certificate']
        self.assertGreater(old['axis_segment_cell_count'],c['actual_marker_cells'])
        self.assertEqual(old['axis_segment_cell_count']-len(c['original_axis_cells']),c['actual_marker_cells'])

    def test_old_grid_and_record_modification_rejected(self):
        x=case();old,rec=g.source.render_edge_marker_axis_projection(x)
        changed=deepcopy(old);changed[-1][-1]=(changed[-1][-1]+1)%10
        with patch.object(g.source,'render_edge_marker_axis_projection',return_value=(changed,rec)):
            self.assertEqual(g.guarded_render(x)[1]['failure'],'original_grid_disagrees')
        modified={**rec,'axis_segment_cell_count':rec['axis_segment_cell_count']+1}
        with patch.object(g.source,'render_edge_marker_axis_projection',return_value=(old,modified)):
            self.assertEqual(g.guarded_render(x)[1]['failure'],'original_record_disagrees')

    def test_raw_teacher_mismatch_precedes_proof(self):
        a=case();b=case(vertical='bottom',horizontal=None)
        train=[{'input':a,'output':deepcopy(a)},{'input':b,'output':deepcopy(b)}]
        with patch.object(g,'guarded_render',side_effect=RuntimeError('proof too early')):
            model,rec=g.fit_teachers(train)
        self.assertIsNone(model);self.assertEqual(rec['failure'],'original_teacher_mismatch')

    def test_invalid_grid_and_largest_canvas(self):
        for x in [[],[[]],[[True]],[[11]],[[0],[0,1]],[[0]*31],[[0]for _ in range(31)]]:
            self.assertEqual(g.guarded_render(x)[1]['failure'],'invalid_grid')
        x=case(height=30,width=30);out,record=g.guarded_render(x)
        self.assertIsNotNone(out);self.assertEqual([len(out),len(out[0])],[30,30])

    def test_distinct_teacher_wrapper_and_constant_state(self):
        train=[]
        for x in [case(),case(vertical='bottom',horizontal=None)]:
            y,_=g.source.render_edge_marker_axis_projection(x);train.append({'input':x,'output':y})
        model,record=g.fit_teachers(train);self.assertEqual(model,{'renderer':'edge_axis_projection'})
        self.assertEqual(g.fit_teachers(train[:1])[1]['failure'],'too_few_teachers')
        self.assertEqual(g.fit_teachers([train[0],deepcopy(train[0])])[1]['failure'],'duplicate_teacher_inputs')
        train[0]['input'][0][0]=9;self.assertEqual(model,{'renderer':'edge_axis_projection'})


    def test_native_support_is_three_boards_not_pixels(self):
        train=examples();material=g.軸投射教材(train)
        self.assertEqual(vars(material),{'適合':True})
        for minimum,admitted in [(3,True),(4,False)]:
            machine=HDS学習実行系(最小支持数=minimum)
            record=候補機構を学習(machine,{'train':train,'test':[]},(),'ARC境界軸投射',material.候補)
            self.assertEqual(record['現在観測数'],3);self.assertEqual(record['事前観測数'],0)
            self.assertEqual(record['同値採用'],admitted);self.assertEqual(record['隔離数'],0)

    def test_native_hold_and_detached_boolean_fit(self):
        train=examples();material=g.軸投射教材(train);query=case(vertical='bottom',horizontal='right')
        expected,_=g.source.render_edge_marker_axis_projection(query)
        train[0]['input'][0][0]=8;train[0]['output'][0][0]=8
        self.assertEqual(material.候補(query,None)[0],expected)
        result=課題を解く({'train':examples(),'test':[{'input':query},{'input':[[0]]}]},[])
        self.assertEqual(result['results'][0]['answer'],expected)
        self.assertIsNone(result['results'][1]['answer'])

    def test_identifier_and_test_output_are_rejected(self):
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[],'task_id':'forbidden'},[])
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[{'input':[[0]],'output':[[0]]}]},[])

if __name__=='__main__':unittest.main()
