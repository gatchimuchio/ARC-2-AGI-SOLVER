"""凡例集合の全役割・全成分・全モデル合意とnative支持の回帰。"""
from pathlib import Path
from copy import deepcopy
import sys,unittest
from unittest.mock import patch
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 凡例集合教材 as p
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,課題を解く

def fixture(h=14,w=18,fh=4,fw=4,variant=False,ambiguous=False):
    x=[[7]*w for _ in range(h)]
    for r in range(fh):x[r][fw-1]=3
    for c in range(fw):x[fh-1][c]=3
    for r,c,v in [(0,0,1),(1,1,2)]:x[r][c]=v
    groups=[[(6,5,1),(6,6,2)],[(8,4,1),(8,5,2),(9,5,5)],
            [(5,11,1),(6,11,5)],[(10,12,8)]]
    if ambiguous:groups=[groups[0],groups[3]]
    if variant:groups[-1].append((10,13,9))
    for group in groups:
        for r,c,v in group:x[r][c]=v
    y=deepcopy(x)
    for group in groups:
        if {1,2}<={v for r,c,v in group}:
            for r,c,v in group:y[r][c]=7
    return {'input':x,'output':y},groups


def rotated(grid):return [list(row)for row in zip(*grid[::-1])]


def training():
    return [fixture()[0],fixture(variant=True)[0],fixture(fh=5,fw=7)[0]]


class Controls(unittest.TestCase):
    def test_three_synthetic_teachers(self):
        train=training()
        models,rec=p.fit_models(train)
        self.assertEqual(models,['contains:erase_matching'])
        self.assertEqual([x['models'][0]['record']['removed_cells']for x in rec['teacher_records']],[5,5,5])
        for pair in train:self.assertEqual(p.consensus(pair['input'],models)[0],pair['output'])

    def test_all_component_shapes_and_relation(self):
        pair,groups=fixture();y,rec=p.render_model(pair['input'],'contains:erase_matching')
        self.assertEqual(y,pair['output'])
        self.assertEqual(rec['outside_components'],4)
        self.assertEqual(rec['removed_cells'],5)
        self.assertEqual(rec['retained_outside_foreground_cells'],3)
        self.assertTrue(any(obj['size']==1 for obj in rec['objects']))

    def test_all_four_corners_and_reflections(self):
        pair,_=fixture()
        for flip in [False,True]:
            x=deepcopy(pair['input']);y=deepcopy(pair['output'])
            if flip:x=[row[::-1]for row in x];y=[row[::-1]for row in y]
            for _ in range(4):
                self.assertEqual(p.render_model(x,'contains:erase_matching')[0],y)
                x=rotated(x);y=rotated(y)

    def test_permutations_including_zero(self):
        pair,_=fixture();permutation=[9,0,6,8,5,1,3,2,7,4]
        change=lambda grid:[[permutation[v]for v in row]for row in grid]
        self.assertEqual(p.render_model(change(pair['input']),'contains:erase_matching')[0],change(pair['output']))

    def test_nonsquare_legend_size(self):
        pair,_=fixture(fh=5,fw=7)
        self.assertEqual(p.render_model(pair['input'],'contains:erase_matching')[0],pair['output'])

    def test_global_mode_can_change_without_background_change(self):
        pair,_=fixture(h=30,w=30)
        for grid in pair.values():
            for r in range(15,30):grid[r]=[0]*30
        y,rec=p.render_model(pair['input'],'contains:erase_matching')
        self.assertEqual(y,pair['output']);self.assertEqual(rec['background'],7)
        self.assertGreater(sum(v==0 for row in pair['input']for v in row),sum(v==7 for row in pair['input']for v in row))

    def test_duplicate_palette_occurrence_is_set_membership(self):
        pair,_=fixture()
        for grid in pair.values():grid[0][1]=1
        y,rec=p.render_model(pair['input'],'contains:erase_matching')
        self.assertEqual(y,pair['output']);self.assertEqual(rec['palette'],[1,2])

    def test_second_raw_frame_veto_even_empty_palette(self):
        pair,_=fixture();x=pair['input'];h,w=len(x),len(x[0])
        for r in range(h-4,h):x[r][w-4]=6
        for c in range(w-4,w):x[h-4][c]=6
        y,rec=p.render_model(x,'contains:erase_matching')
        self.assertIsNone(y);self.assertEqual(rec['failure'],'raw_frame_unresolved')
        self.assertEqual(len(rec['raw_frames']),2)

    def test_interior_tie_and_empty_palette(self):
        for values,failure in [([7]*4+[1]*4+[2],'legend_background_tie'),([7]*9,'empty_palette')]:
            x=fixture()[0]['input']
            for index,v in enumerate(values):x[index//3][index%3]=v
            self.assertEqual(p.render_model(x,'contains:erase_matching')[1]['failure'],failure)

    def test_background_frame_alias_after_raw_uniqueness(self):
        x=[[7]*15 for _ in range(15)]
        for r in range(8):x[r][7]=3
        for c in range(8):x[7][c]=3
        for r in range(1,6):
            for c in range(1,6):x[r][c]=3
        x[12][12]=1
        self.assertEqual(p.render_model(x,'contains:erase_matching')[1]['failure'],'background_frame_alias')

    def test_original_component_crossing_legend_is_not_cut(self):
        x=fixture()[0]['input'];x[4][2]=5
        self.assertEqual(p.render_model(x,'contains:erase_matching')[1]['failure'],'component_crosses_legend')

    def test_missing_objects_and_malformed_frame(self):
        x=fixture()[0]['input']
        for r in range(len(x)):
            for c in range(len(x[0])):
                if not(r<4 and c<4):x[r][c]=7
        self.assertEqual(p.render_model(x,'contains:erase_matching')[1]['failure'],'no_outside_objects')
        x=fixture()[0]['input'];x[3][1]=7
        self.assertEqual(p.render_model(x,'contains:erase_matching')[1]['failure'],'raw_frame_unresolved')

    def test_whole_component_coverage_is_checked(self):
        x=fixture()[0]['input'];old=p.mixed_region_dicts_for_grid
        with patch.object(p,'mixed_region_dicts_for_grid',side_effect=lambda *args,**kwargs:old(*args,**kwargs)[:-1]):
            self.assertEqual(p.render_model(x,'contains:erase_matching')[1]['failure'],'mixed_component_coverage_invalid')
        oldmono=p.color_component_dicts_for_grid
        with patch.object(p,'color_component_dicts_for_grid',side_effect=lambda grid,colour,**kw:[] if colour==1 else oldmono(grid,colour,**kw)):
            self.assertEqual(p.render_model(x,'contains:erase_matching')[1]['failure'],'monochrome_component_coverage_invalid')

    def test_all_models_retained_and_disagreement(self):
        train=[fixture(ambiguous=True)[0],fixture(ambiguous=True,variant=True)[0]]
        models,_=p.fit_models(train)
        self.assertEqual(models,['intersects:erase_matching','contains:erase_matching','equals:erase_matching'])
        y,rec=p.consensus(fixture()[0]['input'],models)
        self.assertIsNone(y);self.assertEqual(rec['failure'],'retained_model_grids_disagree')
        self.assertEqual(len(rec['models']),3)

    def test_opposite_action_is_learnable(self):
        train=[]
        for variant in [False,True]:
            pair,groups=fixture(variant=variant);pair['output']=deepcopy(pair['input'])
            for group in groups:
                if not {1,2}<={v for r,c,v in group}:
                    for r,c,v in group:pair['output'][r][c]=7
            train.append(pair)
        self.assertEqual(p.fit_models(train)[0],['contains:erase_nonmatching'])

    def test_one_retained_failure_is_hold(self):
        raw=p.render_model
        def failed(grid,model):return (None,{'failure':'synthetic'})if model=='equals:erase_matching'else raw(grid,model)
        with patch.object(p,'render_model',failed):
            self.assertEqual(p.consensus(fixture()[0]['input'],['contains:erase_matching','equals:erase_matching'])[1]['failure'],'retained_model_unresolved')

    def test_noop_only_after_all_model_agreement(self):
        pair,groups=fixture();x=pair['input']
        for group in groups[:2]:
            for r,c,v in group:x[r][c]=7
        y,rec=p.consensus(x,['contains:erase_matching','equals:erase_matching'])
        self.assertIsNone(y);self.assertEqual(rec['failure'],'no_change');self.assertEqual(len(rec['models']),2)
        self.assertEqual(p.consensus(x,['contains:erase_matching','intersects:erase_matching'])[1]['failure'],'retained_model_grids_disagree')

    def test_component_order_does_not_select(self):
        pair,_=fixture();old=p.mixed_region_dicts_for_grid
        with patch.object(p,'mixed_region_dicts_for_grid',side_effect=lambda *args,**kw:list(reversed(old(*args,**kw)))):
            self.assertEqual(p.render_model(pair['input'],'contains:erase_matching')[0],pair['output'])

    def test_minimum_distinct_and_invalid_inputs(self):
        pair=fixture()[0]
        self.assertEqual(p.fit_models([pair])[1]['failure'],'too_few_teachers')
        self.assertEqual(p.fit_models([pair,deepcopy(pair)])[1]['failure'],'duplicate_teacher_inputs')
        for x in [[],[[True]],[[0]*31],[[0]]*31,[[0],[1,2]]]:self.assertIsNone(p.render_model(x,'contains:erase_matching')[0])
        self.assertEqual(p.consensus(pair['input'],[['bad']])[1]['failure'],'invalid_models')


    def test_native_teacher_board_support(self):
        train=training();material=p.凡例集合教材(train)
        self.assertEqual(vars(material),{'モデル':['contains:erase_matching']})
        for minimum,admitted in [(3,True),(4,False)]:
            machine=HDS学習実行系(最小支持数=minimum)
            record=候補機構を学習(machine,{'train':train,'test':[]},(),'ARC凡例集合選択',material.候補)
            self.assertEqual(record['現在観測数'],3);self.assertEqual(record['事前観測数'],0)
            self.assertEqual(record['同値採用'],admitted);self.assertEqual(record['隔離数'],0)

    def test_native_unresolved_is_whole_hold(self):
        train=training();x=train[0]['input'];bad=deepcopy(x);bad[4][2]=5
        result=課題を解く({'train':train,'test':[{'input':x},{'input':bad}]},[])
        self.assertEqual(result['results'][0]['answer'],train[0]['output'])
        self.assertIsNone(result['results'][1]['answer'])

    def test_identifier_and_test_target_rejected(self):
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[],'task_id':'forbidden'},[])
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[{'input':[[0]],'output':[[0]]}]},[])


if __name__=='__main__':unittest.main()
