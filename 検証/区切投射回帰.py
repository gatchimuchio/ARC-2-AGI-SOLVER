"""全成分の区切整列・行gap投射と同一HDSの3盤面支持。"""
from pathlib import Path
import sys,copy,unittest
from unittest.mock import patch
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 区切投射教材 as g
from 接続.ARC2.既存区切投射 import render_separator_aligned_zero_projection as raw,color_components
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,出力格子,観測へ,課題を解く
POLICY={'separator_color':5,'movable_color':0,'target_color':2}

def sample(height=7,width=12,separator=8):
    a=[[1]*width for _ in range(height)]
    for r in range(height):a[r][separator]=5
    for r,c in ((2,1),(2,3),(3,1),(3,2),(3,3)):a[r][c]=0
    return a

def merge_input():
    a=sample()
    for r,c in ((0,6),(0,7),(1,6),(2,6)):a[r][c]=0
    return a

def pair(height=7):
    a=sample(height=height);out=copy.deepcopy(a)
    for r,c in ((2,1),(2,3),(3,1),(3,2),(3,3)):out[r][c]=1
    for r,c in ((2,5),(2,7),(3,5),(3,6),(3,7)):out[r][c]=0
    for c in range(9,12):out[2][c]=2
    return {'input':a,'output':out}

class 区切投射回帰(unittest.TestCase):
    def test_component_merge_uses_original_id_gap(self):
        a=merge_input();out,z=g.guarded_render(a,POLICY);self.assertIsNotNone(out)
        self.assertEqual(len(color_components(a,0)),2);self.assertEqual(len(color_components(out,0)),1)
        self.assertEqual(out[2][5:8],[0,0,0]);self.assertEqual(out[2][9:],[2,2,2]);self.assertEqual(z['projection_rows'],[2])

    def test_legal_vacated_source_target(self):
        a=sample()
        for r,c in ((1,5),(1,6),(2,5)):a[r][c]=0
        out,z=g.guarded_render(a,POLICY);self.assertIsNotNone(out)
        self.assertEqual(a[2][5],0);self.assertEqual(out[2][5],0)
        shifted_A=next(c for c in z['components']if c['input_size']==5)
        shifted_B=next(c for c in z['components']if c['input_size']==3)
        self.assertIn((2,5),shifted_A['moved_cells']);self.assertNotIn((2,5),shifted_B['moved_cells'])
        self.assertEqual(z['source_pixels'],8);self.assertEqual(z['moved_pixels'],8)

    def test_last_column_move_only_is_additional_hold(self):
        a=sample(height=6,width=8,separator=7);out,r=raw(a,**POLICY)
        self.assertIsNotNone(out);self.assertEqual(r['projection_row_count'],1);self.assertFalse(any(v==2 for row in out for v in row))
        self.assertEqual(g.guarded_render(a,POLICY)[1]['failure'],'separator_not_internal')

    def test_raw_nonbackground_axis_ambiguity(self):
        a=sample()
        for r in range(len(a)):a[r][0]=0
        self.assertIsNotNone(raw(a,**POLICY)[0]);self.assertEqual(g.guarded_render(a,POLICY)[1]['failure'],'raw_separator_not_unique')

    def test_overlap_rejected_without_partial_result(self):
        a=sample()
        for r,c in ((1,6),(1,7),(2,7)):a[r][c]=0
        self.assertEqual(g.guarded_render(a,POLICY)[1]['failure'],'component_pixel_collision')

    def test_protected_translation_and_projection(self):
        a=sample();a[2][7]=5
        self.assertEqual(g.guarded_render(a,POLICY)[1]['failure'],'translation_protected_collision')
        a=sample();a[2][10]=5
        self.assertEqual(g.guarded_render(a,POLICY)[1]['failure'],'projection_protected_collision')

    def test_new_colour_contract_and_unknown_palette(self):
        for c in (2,9):
            a=sample();a[0][-1]=c
            self.assertEqual(g.guarded_render(a,POLICY)[1]['failure'],'input_role_palette_violation')

    def test_fixed_vertical_axis_reflection_and_palette(self):
        a=sample();expected,_=raw(a,**POLICY)
        for flip in (False,True):
            for offset in (0,3,7):
                def t(x):return [[(v+offset)%10 for v in row]for row in(x[::-1]if flip else x)]
                p={k:(v+offset)%10 for k,v in POLICY.items()}
                self.assertEqual(g.guarded_render(t(a),p)[0],t(expected))

    def test_background_is_per_input_not_shared_colour(self):
        a=sample();b=sample(height=8);b=[[7 if v==1 else v for v in row]for row in b]
        pairs=[{'input':x,'output':raw(x,**POLICY)[0]}for x in(a,b)]
        policy,z=g.fit_teachers(pairs);self.assertEqual(policy,POLICY);self.assertEqual([r['background']for r in z['role_record']['records']],[1,7])

    def test_zero_shift_and_solid_component_no_projection(self):
        a=sample();b=[[1]*12 for _ in range(9)]
        for r in range(9):b[r][8]=5
        for r,c in ((2,5),(2,7),(3,5),(3,6),(3,7),(6,1),(6,2)):b[r][c]=0
        out,z=g.guarded_render(b,POLICY);self.assertIsNotNone(out);self.assertEqual([c['shift']for c in z['components']],[0,5]);self.assertEqual(z['components'][1]['gap_rows'],[])

    def test_outside_source_move_projection_preserved(self):
        a=sample();a[0][-1]=5;out,z=g.guarded_render(a,POLICY);self.assertIsNotNone(out);self.assertEqual(out[0][-1],5)
        self.assertTrue(all(out[r][8]==5 for r in range(len(a))))

    def test_original_grid_and_record_not_replaced(self):
        a=sample();out,r=raw(a,**POLICY);bad=copy.deepcopy(out);bad[0][0]=9
        for output,record in((bad,r),(out,dict(r,projection_row_count=99))):
            with patch.object(g,'render_separator_aligned_zero_projection',return_value=(output,record)):
                self.assertEqual(g.guarded_render(a,POLICY)[1]['failure'],'source_output_or_record_disagreement')

    def test_raw_teacher_reproduction_precedes_guard(self):
        pairs=[{'input':a,'output':raw(a,**POLICY)[0]}for a in(sample(),sample(height=8))]
        with patch.object(g,'render_separator_aligned_zero_projection',return_value=([[9]],{})),patch.object(g,'guarded_render',side_effect=AssertionError('guard called before raw reproduction')):
            self.assertEqual(g.fit_teachers(pairs)[1]['failure'],'raw_teacher_reproduction_failed')
        self.assertIsNone(g.fit_teachers(pairs[:1])[0]);self.assertIsNone(g.fit_teachers([pairs[0],pairs[0]])[0])

    def test_invalid_bg_tie_right_side_object_and_noop(self):
        for a in([],[[True]],[[10]],[[0],[0,1]],[[0]*31]):self.assertEqual(g.guarded_render(a,POLICY)[1]['failure'],'invalid_arc_grid')
        self.assertEqual(g.guarded_render([[1,5],[5,1]],POLICY)[1]['failure'],'background_tie')
        a=sample();a[5][10]=0;self.assertEqual(g.guarded_render(a,POLICY)[1]['failure'],'all_movable_components_must_be_left')
        a=[[1]*10 for _ in range(6)]
        for r in range(6):a[r][7]=5
        a[3][6]=0;self.assertEqual(g.guarded_render(a,POLICY)[1]['failure'],'original_renderer_unresolved')

    def test_合成完全盤面と全教師共通役割(self):
        pairs=[pair(h)for h in (7,8,9)];view=g.区切投射教材(pairs)
        self.assertEqual(view.役割,POLICY)
        for p in pairs:
            out,z=g.guarded_render(p['input'],POLICY);self.assertEqual(out,p['output'])
            self.assertEqual(z['source_pixels'],5);self.assertEqual(z['moved_pixels'],5);self.assertEqual(z['projection_cells'],3)
        bad=copy.deepcopy(pairs);bad[-1]['output'][0][0]=9
        self.assertIsNone(g.区切投射教材(bad).役割)
    def test_native支持は三盤面で物体数を加算しない(self):
        pairs=[pair(h)for h in (7,8,9)];view=g.区切投射教材(pairs);boundary='区切投射対照'
        engine=HDS学習実行系(最小支持数=3)
        self.assertFalse(候補機構を学習(engine,{'train':pairs[:2]},[],boundary,view.候補)['同値採用'])
        engine=HDS学習実行系(最小支持数=3);r=候補機構を学習(engine,{'train':pairs},[],boundary,view.候補)
        self.assertTrue(r['同値採用']);self.assertTrue(r['採用可']);self.assertEqual(r['現在観測数'],3);self.assertEqual(r['事前観測数'],0)
        q=pairs[0]['output'];self.assertEqual(出力格子(engine,観測へ({'候補':q},boundary),同値必須=True)['answer'],q)
        engine.実行(観測へ({'候補':q,'出力':[[9]]},boundary));self.assertIsNone(出力格子(engine,観測へ({'候補':q},boundary),同値必須=True)['answer'])
    def test_採用済み未解決queryの全体HOLDと情報分離(self):
        q=sample()
        for r,c in ((1,6),(1,7),(2,7)):q[r][c]=0
        task={'train':[pair(h)for h in(7,8,9)],'test':[{'input':q}]};result=課題を解く(task,[])
        r=next(r for r in result['families']if r['境界']=='ARC区切整列gap投射');self.assertTrue(r['同値採用']);self.assertEqual(r['現在観測数'],3);self.assertIsNone(result['results'][0]['answer'])
        task['task_id']='forbidden'
        with self.assertRaises(ValueError):課題を解く(task,[])
        task.pop('task_id');task['test'][0]['output']=[[1]]
        with self.assertRaises(ValueError):課題を解く(task,[])

if __name__=='__main__':unittest.main()
