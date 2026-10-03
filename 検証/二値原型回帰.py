"""現在教師の原型記憶・全照合とnative盤面支持の回帰。"""
import copy,random,unittest
from unittest.mock import patch
from pathlib import Path
import sys
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 二値原型教材 as g
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,課題を解く
def pattern(seed=1,balanced=False):
    rng=random.Random(seed)
    values=[0]*200+[1]*200 if balanced else[rng.randrange(2)for _ in range(400)]
    if balanced:rng.shuffle(values)
    return[values[r*20:(r+1)*20]for r in range(20)]

def surface(template,index=0,colours=(2,7)):
    out=[row[:]for row in template]
    for _ in range(index//2):out=[list(row)for row in zip(*out[::-1])]
    if index%2:out=[row[::-1]for row in out]
    return[[colours[v]for v in row]for row in out]

def crop(grid,top=2,left=3,height=7,width=8):
    return[row[left:left+width]for row in grid[top:top+height]]

def teachers(seed=1,balanced=False):
    template=pattern(seed,balanced);pairs=[]
    for index,colours,origin in[(0,(2,7),(2,3)),(3,(1,8),(8,1)),(6,(4,9),(5,8))]:
        out=surface(template,index,colours);pairs.append({'input':crop(out,*origin),'output':out})
    return pairs

# All persistent fixtures use unrelated generated patterns; no evaluation reference image.
TRAIN=teachers(17)
for index,colours,origin in[(1,(0,6),(9,7)),(4,(3,5),(11,2))]:
    expected=surface(pattern(17),index,colours)
    TRAIN.append({'input':crop(expected,*origin),'output':expected})

class Controls(unittest.TestCase):
    def test_01_all_current_teachers(self):
        model,record=g.fit_teachers(TRAIN);self.assertIsNotNone(model,record)
        for pair in TRAIN:
            out,r=g.guarded_render(pair['input'],model);self.assertEqual(out,pair['output']);self.assertEqual(r['physical_models_checked'],16);self.assertEqual(r['stored_template_bits'],400)
    def test_02_unrelated_patterns(self):
        for seed in range(8):
            pairs=teachers(seed);model,record=g.fit_teachers(pairs);self.assertIsNotNone(model,record);expected=surface(pattern(seed),5,(0,3));self.assertEqual(g.guarded_render(crop(expected,10,9,8,9),model)[0],expected)
    def test_03_all_d4_and_palette_bindings(self):
        template=pattern(11)
        for index in range(8):
            for colours in[(2,7),(7,2)]:
                expected=surface(template,index,colours);self.assertEqual(g.guarded_render(crop(expected,5,6,9,8),template)[0],expected)
    def test_04_mode_tie_is_binary_gauge(self):
        pairs=teachers(12,True);self.assertEqual(sum(v==2 for row in pairs[0]['output']for v in row),200);model,record=g.fit_teachers(pairs);self.assertIsNotNone(model,record)
        complement=[[1-v for v in row]for row in model];x=pairs[1]['input'];self.assertEqual(g.guarded_render(x,model)[0],g.guarded_render(x,complement)[0])
    def test_05_first_teacher_and_leave_one_out(self):
        for i in range(len(TRAIN)):
            order=TRAIN[i:]+TRAIN[:i];model,record=g.fit_teachers(order);self.assertIsNotNone(model,record)
            self.assertEqual(g.guarded_render(TRAIN[0]['input'],model)[0],TRAIN[0]['output'])
            model,record=g.fit_teachers(TRAIN[:i]+TRAIN[i+1:]);self.assertIsNotNone(model,record);self.assertEqual(g.guarded_render(TRAIN[i]['input'],model)[0],TRAIN[i]['output'])
    def test_06_same_surface_multiple_offsets(self):
        template=pattern(63);patch_bits=crop(template,1,1,5,5)
        for r in range(5):
            for c in range(5):template[12+r][12+c]=patch_bits[r][c]
        expected=surface(template);x=crop(expected,1,1,5,5);out,rec=g.guarded_render(x,template)
        self.assertEqual(out,expected);self.assertEqual(rec['distinct_crop_placements'],[[1,1],[12,12]]);self.assertEqual(rec['raw_record']['dihedral_placement_count'],2)
    def test_07_different_surfaces_whole_hold(self):
        template=[[(r+c)%2 for c in range(20)]for r in range(20)];out,r=g.guarded_render([[2,7],[7,2]],template)
        self.assertIsNone(out);self.assertEqual(r['failure'],'complete_surface_not_unique');self.assertEqual(r['distinct_matching_surfaces'],2)
    def test_08_same_input_other_template_changes_completion(self):
        a=pattern(31);b=copy.deepcopy(a);b[19][19]=1-b[19][19];x=crop(surface(a),2,3,8,9);oa,_=g.guarded_render(x,a);ob,_=g.guarded_render(x,b)
        self.assertIsNotNone(oa);self.assertIsNotNone(ob);self.assertNotEqual(oa,ob);self.assertEqual(sum(v!=w for r,s in zip(oa,ob)for v,w in zip(r,s)),1)
    def test_09_symmetry_duplicates_are_output_agreement(self):
        template=[[min(r,c,19-r,19-c)%2 for c in range(20)]for r in range(20)];expected=surface(template);out,r=g.guarded_render(crop(expected,0,0,20,19),template)
        self.assertEqual(out,expected);self.assertEqual(len(r['physical_matches']),8);self.assertEqual(r['distinct_matching_surfaces'],1)
    def test_10_noop_is_original_failure(self):
        template=pattern();out,r=g.guarded_render(surface(template),template);self.assertIsNone(out);self.assertEqual(r['raw_record']['failure'],'identity_dihedral_pattern_completion')
    def test_11_fixed_shape_not_generalised(self):
        template=pattern();x=crop(surface(template))
        for bad in[[row[:19]for row in template[:19]],[row+[0]for row in template]+[[0]*21]]:self.assertEqual(g.guarded_render(x,bad)[1]['failure'],'invalid_fixed20_binary_template')
    def test_12_all_origins_and_input_cells(self):
        template=pattern(17);expected=surface(template)
        for top,left in[(0,0),(0,14),(14,0),(14,14)]:
            out,r=g.guarded_render(crop(expected,top,left,6,6),template);self.assertEqual(out,expected);self.assertEqual(r['crop_origins_checked'],16*15*15);self.assertIn([top,left],r['distinct_crop_placements'])
        x=crop(expected,2,3,10,10);x[5][5]=9;self.assertEqual(g.guarded_render(x,template)[1]['failure'],'input_not_two_colours')
    def test_13_unmatched_or_oversize_crop(self):
        template=pattern(17);out,r=g.guarded_render([[2,7]*15],template);self.assertIsNone(out);self.assertEqual(r['crop_origins_checked'],0)
    def test_14_only_original_grid_record(self):
        template=pattern();x=crop(surface(template));out,record=g.render_dihedral_binary_pattern_completion(x,template);changed=copy.deepcopy(out);changed[-1][-1]=2 if changed[-1][-1]==7 else 7
        with patch.object(g,'render_dihedral_binary_pattern_completion',return_value=(changed,record)):self.assertEqual(g.guarded_render(x,template)[1]['failure'],'original_grid_or_record_disagreement')
        with patch.object(g,'render_dihedral_binary_pattern_completion',return_value=(out,dict(record,dihedral_placement_count=999))):self.assertEqual(g.guarded_render(x,template)[1]['failure'],'original_grid_or_record_disagreement')
        with patch.object(g,'render_dihedral_binary_pattern_completion',return_value=(None,{'failure':'synthetic_original_failure'})):self.assertEqual(g.guarded_render(x,template)[1]['failure'],'original_renderer_unresolved')
    def test_15_raw_teacher_reproduction_before_proof(self):
        pairs=teachers();pairs[1]['output'][0][0]=0
        with patch.object(g,'guarded_render',side_effect=AssertionError('must not run')):self.assertIsNone(g.fit_teachers(pairs)[0])
    def test_16_pattern_detached_from_teacher_objects(self):
        pairs=teachers();model,r=g.fit_teachers(pairs);self.assertIsNotNone(model,r);x=crop(surface(pattern(),5,(0,3)),4,7);before=g.guarded_render(x,model)[0]
        for pair in pairs:
            for row in pair['output']:row[:]=[9]*len(row)
        self.assertEqual(g.guarded_render(x,model)[0],before);self.assertEqual({v for row in model for v in row},{0,1})
    def test_17_invalid_and_duplicate(self):
        template=pattern()
        for x in[[],[[0],[]],[[True]],[[10]],[[0]*31]]:self.assertIsNone(g.guarded_render(x,template)[0])
        self.assertIsNone(g.guarded_render([[2,7]],[[False]*20 for _ in range(20)])[0]);pairs=teachers();self.assertEqual(g.fit_teachers([pairs[0],pairs[0]])[1]['failure'],'duplicate_teacher_inputs')

    def test_native_support_is_teacher_boards(self):
        material=g.二値原型教材(TRAIN)
        for minimum,admitted in[(3,True),(6,False)]:
            machine=HDS学習実行系(最小支持数=minimum)
            record=候補機構を学習(machine,{'train':TRAIN,'test':[]},(),'ARC二値原型補完',material.候補)
            self.assertEqual(record['現在観測数'],5);self.assertEqual(record['事前観測数'],0)
            self.assertEqual(record['同値採用'],admitted);self.assertEqual(record['隔離数'],0)
    def test_native_unresolved_is_hold(self):
        x=copy.deepcopy(TRAIN[0]['input']);bad=copy.deepcopy(x);bad[0][0]=9
        result=課題を解く({'train':TRAIN,'test':[{'input':x},{'input':bad}]},[])
        model,_=g.fit_teachers(TRAIN);self.assertEqual(result['results'][0]['answer'],g.guarded_render(x,model)[0]);self.assertIsNone(result['results'][1]['answer'])
    def test_no_identifier_or_test_target(self):
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[],'task_id':'forbidden'},[])
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[{'input':[[0]],'output':[[0]]}]},[])
    def test_current_task_pattern_only_no_shared_reference(self):
        first=g.二値原型教材(teachers(1));second=g.二値原型教材(teachers(2));self.assertEqual(set(vars(first)),{'原型'});self.assertEqual(set(vars(second)),{'原型'})
        out1=surface(pattern(1),7,(3,8));out2=surface(pattern(2),7,(3,8));q1=crop(out1);q2=crop(out2)
        self.assertEqual(first.候補(q1,{})[0],out1);self.assertEqual(second.候補(q2,{})[0],out2);self.assertEqual(first.候補(q1,{})[0],out1)
        self.assertNotEqual(first.原型,second.原型)

if __name__=='__main__':unittest.main()
