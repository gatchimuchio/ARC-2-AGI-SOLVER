"""四欄反復の新組合せと全入力/出力対応・native支持の回帰。"""
from pathlib import Path
from copy import deepcopy
import random
import sys
import unittest
from unittest.mock import patch
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 四欄反復教材 as g
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,課題を解く

def case(mask=None,components=None,axis='columns',blank=0,mask_colour=4,count_colour=3,paint=2,fill=9,separator=1,margin=1):
    mask=mask if mask is not None else [[1,1],[1,0]]
    components=components if components is not None else [{(0,0),(1,0)},{(0,0),(1,0)}]
    mh,mw=len(mask),len(mask[0]);height=max(mh+2*margin,max((max(r for r,c in s)+1 for s in components),default=1)+2*margin,3)
    p0=[[blank]*(mw+2*margin)for _ in range(height)]
    for r,row in enumerate(mask):
        for c,v in enumerate(row):
            if v:p0[margin+r][margin+c]=mask_colour
    sizes=[max(c for r,c in s)+1 for s in components]
    count_width=max(1,sum(sizes)+max(0,len(components)-1)+2*margin)
    p1=[[blank]*count_width for _ in range(height)];left=margin
    for shape,width in zip(components,sizes):
        for r,c in shape:p1[margin+r][left+c]=count_colour
        left+=width+1
    grid=[a+[separator]+b+[separator]+[paint]*2+[separator]+[fill]*2 for a,b in zip(p0,p1)]
    painted=[[paint if v else fill for v in row]for row in mask];output=[]
    for row in painted:
        values=[]
        for i in range(len(components)):
            if i:values.append(fill)
            values.extend(row)
        output.append(values)
    if axis=='rows':grid=[list(r)for r in zip(*grid)];output=[list(r)for r in zip(*output)]
    return {'input':grid,'output':output}


def examples():
    return [case(),case(axis='rows'),case(mask=[[1,1,1],[1,0,1]],paint=6,fill=7),
            case(components=[{(0,0)},{(0,0),(1,0),(1,1)},{(0,0),(0,1)}],paint=8,fill=2)]


class Controls(unittest.TestCase):
    def test_four_synthetic_teachers(self):
        train=examples();model,rec=g.fit_teachers(train)
        self.assertIsNotNone(model)
        self.assertEqual(len(rec['teacher_records']),4)
        self.assertTrue(all(r['exact'] for r in rec['teacher_records']))

    def test_both_axes_non_square_masks(self):
        for axis in ['columns','rows']:
            for mask in [[[1,1,1],[1,0,1]],[[1,0],[1,1],[0,1]],[[1]]]:
                p=case(mask=mask,axis=axis);self.assertEqual(g.render(p['input'])[0],p['output'])

    def test_count_component_area_shape_not_pixel_count(self):
        shapes=[{(0,0)}, {(0,0),(1,0),(1,1)}, {(0,0),(0,1),(0,2),(1,1),(2,1)}]
        p=case(components=shapes);y,rec=g.render(p['input']);self.assertEqual(y,p['output'])
        self.assertEqual(rec['repeat_count'],3);self.assertEqual([r['size']for r in rec['count_components']],[1,3,5])
        self.assertEqual(rec['count_pixels'],9)

    def test_count_one_no_gap(self):
        p=case(components=[{(0,0),(0,1),(1,0)}]);y,rec=g.render(p['input']);self.assertEqual(y,p['output']);self.assertEqual(rec['gap_cells'],0)

    def test_four_neighbor_diagonal_contacts_remain_separate(self):
        p=case(components=[{(0,0)},{(0,0)}]);x=p['input'];start=len([[1,1],[1,0]][0])+2+1
        x[1][start+3]=0;x[2][start+2]=3
        y,rec=g.render(x);self.assertEqual(y,p['output']);self.assertEqual(rec['repeat_count'],2)
        self.assertEqual([r['size']for r in rec['count_components']],[1,1])

    def test_internal_blank_cells_retained_as_fill(self):
        p=case(mask=[[1,1,1],[1,0,1],[1,1,1]]);y,rec=g.render(p['input']);self.assertEqual(y,p['output']);self.assertEqual(rec['paint_owned_cells'],16)
        self.assertEqual(y[1][1],9);self.assertEqual(y[1][5],9)

    def test_arbitrary_colours_including_zero_roles(self):
        p=case();rng=random.Random(919)
        for _ in range(30):
            mapping=list(range(10));rng.shuffle(mapping)
            change=lambda x:[[mapping[v]for v in row]for row in x]
            self.assertEqual(g.render(change(p['input']))[0],change(p['output']))
        p=case(blank=7,mask_colour=0,count_colour=3,paint=0,fill=6,separator=1)
        self.assertEqual(g.render(p['input'])[0],p['output'])

    def test_palette_role_alias_and_equal_paint_fill(self):
        for paint,fill in[(2,3),(6,4),(0,6),(7,7),(4,0)]:
            p=case(paint=paint,fill=fill);y,r=g.render(p['input']);self.assertEqual(y,p['output'])
            if paint==fill:self.assertEqual(r['output_colour_counts'],[[paint,len(y)*len(y[0])]])

    def test_uniform_palette_area_not_quantity(self):
        p=case();x=deepcopy(p['input']);x=[row+[9,9]for row in x]
        self.assertEqual(g.render(x)[0],p['output'])

    def test_multiple_raw_layouts_one_typed_is_still_hold(self):
        x=[[4,0,4,0,4,1,3,0,3,1,2,1,9]for _ in range(3)]
        self.assertEqual(len(g.parse_input(x)[1]['raw_layout_candidates']),2)
        self.assertEqual(g.render(x)[1]['failure'],'raw_layout_not_unique')
        # The colour1 layout has binary mask/count and uniform palettes;
        # colour0 layout starts with uniform4, so only later content would select1.
        candidates=g.parse_input(x)[1]['raw_layout_candidates']
        self.assertEqual({c['separator_colour']for c in candidates},{0,1})

    def test_extra_separator_not_dropped(self):
        p=case();x=[row[:2]+[1]+row[2:]for row in p['input']]
        self.assertEqual(g.render(x)[1]['failure'],'raw_layout_not_unique')

    def test_missing_or_thick_separator(self):
        p=case();parsed,rec=g.parse_input(p['input']);pos=rec['raw_layout_candidates'][0]['separator_positions'][1]
        x=deepcopy(p['input']);x[0][pos]=0
        self.assertEqual(g.render(x)[1]['failure'],'raw_layout_not_unique')
        x=[row[:pos]+[1]+row[pos:]for row in p['input']]
        self.assertEqual(g.render(x)[1]['failure'],'raw_layout_not_unique')

    def test_binary_role_ambiguity_and_unknown_value(self):
        p=case();x=deepcopy(p['input']);_,rec=g.parse_input(x);start,end=rec['raw_layout_candidates'][0]['intervals'][1]
        for row in x:
            for c in range(start,end):
                if row[c]==3:row[c]=4
        self.assertEqual(g.render(x)[1]['failure'],'shared_blank_not_unique')
        p=case();p['input'][0][0]=7
        self.assertEqual(g.render(p['input'])[1]['failure'],'mask_count_fields_not_binary')

    def test_nonuniform_palette(self):
        p=case();_,rec=g.parse_input(p['input']);c=rec['raw_layout_candidates'][0]['intervals'][2][0];p['input'][0][c]=7
        self.assertEqual(g.render(p['input'])[1]['failure'],'palette_field_not_uniform')

    def test_30_perpendicular_extent_and_31_repeat_hold(self):
        p=case(mask=[[1,0]for _ in range(30)],margin=0)
        # Add blank mask column already present and nonblank count panels with blank cells.
        y,rec=g.render(p['input']);self.assertIsNotNone(y);self.assertEqual(len(y),30)
        mask=[[1]*15,[1]+[0]*14]
        p=case(mask=mask);y,rec=g.render(p['input']);self.assertIsNone(y);self.assertEqual(rec['failure'],'output_outside_arc');self.assertEqual(rec['output_shape'],[2,31])

    def test_input_partition_and_no_mutation(self):
        p=case();before=deepcopy(p['input']);y,rec=g.render(p['input']);self.assertEqual(p['input'],before)
        self.assertEqual(rec['separator_cells']+rec['field_cells'],len(before)*len(before[0]))
        self.assertEqual(rec['copy_cells']+rec['gap_cells'],len(y)*len(y[0]))
        owned=[tuple(cell)for c in rec['count_components']for cell in c['cells']]
        self.assertEqual(len(owned),len(set(owned)));self.assertEqual(len(owned),rec['count_pixels'])

    def test_component_extractor_partial_result_veto(self):
        p=case()
        with patch.object(g,'color_component_dicts_for_grid',return_value=[]):self.assertEqual(g.render(p['input'])[1]['failure'],'count_pixels_not_fully_owned')

    def test_invalid_grids(self):
        for x in[[],[[]],[[0],[]],[[True]],[[10]],[[0]*31],[[0]for _ in range(31)]]:self.assertEqual(g.render(x)[1]['failure'],'invalid_grid')

    def test_all_teacher_agreement_and_distinct(self):
        train=[case(),case(mask=[[1,1,1],[1,0,1]],paint=6,fill=7)]
        self.assertIsNotNone(g.fit_teachers(train)[0]);bad=deepcopy(train);bad[1]['output'][0][0]=0
        self.assertIsNone(g.fit_teachers(bad)[0])
        self.assertEqual(g.fit_teachers([train[0]])[1]['failure'],'too_few_teachers')
        self.assertEqual(g.fit_teachers([train[0],deepcopy(train[0])])[1]['failure'],'duplicate_teacher_inputs')

    def test_native_support_counts_teacher_grids(self):
        train=examples();material=g.四欄反復教材(train)
        self.assertEqual(vars(material),{'適合':True})
        for minimum,admitted in [(3,True),(5,False)]:
            machine=HDS学習実行系(最小支持数=minimum)
            rec=候補機構を学習(machine,{'train':train,'test':[]},(),'ARC四欄反復',material.候補)
            self.assertEqual(rec['現在観測数'],4)
            self.assertEqual(rec['事前観測数'],0)
            self.assertEqual(rec['同値採用'],admitted)
            self.assertEqual(rec['隔離数'],0)

    def test_native_hold_and_detached_acceptance_state(self):
        train=examples();material=g.四欄反復教材(train);query=case(paint=7,fill=3)
        train[0]['output'][0][0]=0
        self.assertEqual(material.候補(query['input'],None)[0],query['output'])
        result=課題を解く({'train':examples(),'test':[{'input':query['input']},{'input':[[0]]}]},[])
        self.assertEqual(result['results'][0]['answer'],query['output'])
        self.assertIsNone(result['results'][1]['answer'])

    def test_identifier_and_test_target_are_rejected(self):
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[],'task_id':'forbidden'},[])
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[{'input':[[0]],'output':[[0]]}]},[])

if __name__=='__main__':unittest.main()
