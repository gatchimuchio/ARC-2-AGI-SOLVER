"""教師共有絶対軸・全有限軌道証明とnative支持の回帰。"""
from pathlib import Path
from copy import deepcopy
import random
import sys
import unittest
from unittest.mock import patch
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 二軸補完教材 as g
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,課題を解く

def example(height=9,width=12,axes=(8,10),seed=4):
    rng=random.Random(seed);rs,cs=axes
    output=[[0]*width for _ in range(height)];orbits=set()
    for r in range(height):
        for c in range(width):
            orbits.add(tuple(sorted((a,b) for a,b in {(r,c),(rs-r,c),(r,cs-c),(rs-r,cs-c)}
                                     if 0<=a<height and 0<=b<width)))
    for orbit in sorted(orbits):
        colour=rng.randint(1,9)
        for r,c in orbit:output[r][c]=colour
    grid=deepcopy(output)
    for orbit in sorted(orbits):
        for r,c in orbit[1:]:
            if rng.random()<.65:grid[r][c]=0
    return {'input':grid,'output':output}


class Controls(unittest.TestCase):
    def test_synthetic_teacher_axis_consensus(self):
        train=[example(seed=s) for s in (2,3,4,5)]
        model,record=g.fit_teachers(train)
        self.assertEqual(model,{'axes':[8,10]})
        self.assertEqual(len(record['teacher_records']),4)
        for pair,row in zip(train,record['teacher_records']):
            self.assertEqual(row['filled_zero_count'],sum(v==0 for line in pair['input'] for v in line))

    def test_other_dimensions_integer_half_integer_axes(self):
        for h,w,a in [(9,12,(8,10)),(9,12,(7,13)),(6,8,(4,9)),(7,7,(6,6)),(30,30,(29,29)),(1,9,(0,8)),(8,1,(7,0))]:
            p=example(h,w,a)
            y,r=g.guarded_render(p['input'],a)
            self.assertEqual(y,p['output'])
            self.assertEqual(r['observed_cells_preserved']+r['filled_zero_count'],h*w)

    def test_partial_canvas_orbits(self):
        p=example(9,12,(8,10));y,r=g.guarded_render(p['input'],(8,10))
        self.assertEqual(y,p['output'])
        self.assertTrue(any(len(o['cells'])<4 for o in r['orbits']))
        self.assertEqual(sum(len(o['cells']) for o in r['orbits']),108)

    def test_known_only_conflict(self):
        p=example();x=p['input'];x[0][0]=1;x[8][0]=2;x[0][10]=1;x[8][10]=1
        self.assertIsNotNone(g.render_zero_mask_bidirectional_reflection_fill(x,8,10)[0])
        self.assertEqual(g.guarded_render(x,(8,10))[1]['failure'],'known_orbit_conflict')

    def test_conflicting_zero_sources(self):
        p=example();x=p['input'];x[0][0]=0;x[8][0]=2;x[0][10]=1;x[8][10]=1
        self.assertIsNone(g.render_zero_mask_bidirectional_reflection_fill(x,8,10)[0])
        self.assertEqual(g.guarded_render(x,(8,10))[1]['failure'],'known_orbit_conflict')

    def test_no_original_witness(self):
        p=example();x=p['input']
        for r,c in [(0,0),(8,0),(0,10),(8,10)]:x[r][c]=0
        self.assertEqual(g.guarded_render(x,(8,10))[1]['failure'],'orbit_without_original_witness')

    def test_missing_fixed_point(self):
        p=example(7,7,(6,6));p['input'][3][3]=0
        self.assertEqual(g.guarded_render(p['input'],(6,6))[1]['failure'],'orbit_without_original_witness')

    def test_axes_outside_before_renderer(self):
        p=example()
        with patch.object(g,'render_zero_mask_bidirectional_reflection_fill',side_effect=AssertionError('called')):
            for axes in [(-1,10),(17,10),(8,-1),(8,23)]:
                self.assertEqual(g.guarded_render(p['input'],axes)[1]['failure'],'axis_centres_outside_canvas')

    def test_nonzero_permutation(self):
        p=example();f=lambda x:[[0 if v==0 else 10-v for v in row] for row in x]
        self.assertEqual(g.guarded_render(f(p['input']),(8,10))[0],f(p['output']))

    def test_all_known_preserved_and_input_unmodified(self):
        p=example();before=deepcopy(p['input']);y,rec=g.guarded_render(p['input'],(8,10))
        self.assertEqual(p['input'],before)
        self.assertTrue(all(y[r][c]==v for r,row in enumerate(before) for c,v in enumerate(row) if v))
        self.assertTrue(all(o['observed'] for o in rec['orbits']))
        self.assertTrue(all(before[r][c]==v for o in rec['orbits'] for r,c,v in o['observed']))

    def test_noop(self):
        p=example();self.assertEqual(g.guarded_render(p['output'],(8,10))[1]['failure'],'no_zero_mask_cells')

    def test_invalid_grids_axes(self):
        for x in [[],[[]],[[0],[]],[[10]],[[True]],[[0]*31],[[0] for _ in range(31)]]:
            self.assertEqual(g.guarded_render(x,(0,0))[1]['failure'],'invalid_grid')
        for a in [None,[],[1],[1,2,3],[True,1],[1.0,1]]:
            self.assertEqual(g.guarded_render([[0,1]],a)[1]['failure'],'invalid_axes')

    def test_grid_record_and_original_failure(self):
        p=example();raw=g.render_zero_mask_bidirectional_reflection_fill(p['input'],8,10)
        altered=deepcopy(raw[0]);altered[0][0]=9 if altered[0][0]!=9 else 8
        for value,failure in [((altered,raw[1]),'original_grid_disagrees'),((raw[0],{}),'original_record_disagrees'),((None,{}),'original_renderer_failed')]:
            with patch.object(g,'render_zero_mask_bidirectional_reflection_fill',return_value=value):
                self.assertEqual(g.guarded_render(p['input'],(8,10))[1]['failure'],failure)

    def test_shared_ambiguous_axes_before_proof(self):
        train=[]
        for missing in [(1,1),(0,0)]:
            x=[[1]*3 for _ in range(3)];x[missing[0]][missing[1]]=0
            train.append({'input':x,'output':[[1]*3 for _ in range(3)]})
        with patch.object(g,'guarded_render',side_effect=AssertionError('proof called')):
            model,rec=g.fit_teachers(train)
        self.assertIsNone(model);self.assertGreater(len(rec['common_axes']),1)
        self.assertEqual(rec['failure'],'raw_common_axes_not_unique')

    def test_raw_mismatch_before_proof(self):
        train=[example(seed=2),example(seed=3)];train[0]['output'][0][0]=0
        with patch.object(g,'guarded_render',side_effect=AssertionError('proof called')):
            self.assertIsNone(g.fit_teachers(train)[0])

    def test_raw_renderer_reproduction_before_proof(self):
        train=[example(seed=2),example(seed=3)]
        with patch.object(g,'render_zero_mask_bidirectional_reflection_fill',return_value=(None,{})),patch.object(g,'guarded_render',side_effect=AssertionError('proof called')):
            self.assertEqual(g.fit_teachers(train)[1]['failure'],'raw_teacher_mismatch')

    def test_synthetic_shared_fit_and_copied_state(self):
        train=[example(seed=2),example(seed=3)];model,rec=g.fit_teachers(train)
        self.assertEqual(model,{'axes':[8,10]});self.assertEqual(len(rec['teacher_records']),2)
        before=g.guarded_render(example(seed=7)['input'],model['axes'])
        train[0]['output'][0][0]=0
        self.assertEqual(g.guarded_render(example(seed=7)['input'],model['axes']),before)

    def test_minimum_distinct(self):
        p=example()
        self.assertEqual(g.fit_teachers([p])[1]['failure'],'too_few_teachers')
        self.assertEqual(g.fit_teachers([p,deepcopy(p)])[1]['failure'],'duplicate_teacher_inputs')
        self.assertEqual(g.fit_teachers([p,{}])[1]['failure'],'invalid_teachers')

    def test_native_support_is_teacher_boards(self):
        train=[example(seed=s) for s in (2,3,4,5)];material=g.二軸補完教材(train)
        self.assertEqual(vars(material),{'軸':(8,10)})
        for minimum,admitted in [(3,True),(5,False)]:
            machine=HDS学習実行系(最小支持数=minimum)
            rec=候補機構を学習(machine,{'train':train,'test':[]},(),'ARC二軸欠損補完',material.候補)
            self.assertEqual(rec['現在観測数'],4)
            self.assertEqual(rec['事前観測数'],0)
            self.assertEqual(rec['同値採用'],admitted)
            self.assertEqual(rec['隔離数'],0)

    def test_native_whole_hold_and_material_detached(self):
        train=[example(seed=s) for s in (2,3,4,5)];pair=example(seed=7)
        material=g.二軸補完教材(train)
        train[0]['output'][0][0]=0
        self.assertEqual(material.候補(pair['input'],None)[0],pair['output'])
        train=[example(seed=s) for s in (2,3,4,5)]
        result=課題を解く({'train':train,'test':[{'input':pair['input']},{'input':[[0]]}]},[])
        self.assertEqual(result['results'][0]['answer'],pair['output'])
        self.assertIsNone(result['results'][1]['answer'])

    def test_identifier_and_test_target_are_rejected(self):
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[],'task_id':'forbidden'},[])
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[{'input':[[0]],'output':[[0]]}]},[])

if __name__=='__main__':unittest.main()
