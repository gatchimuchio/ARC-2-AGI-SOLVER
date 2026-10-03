"""曖昧な型を捨てず全規則表の元出力合意を要求する。"""
import unittest
from unittest.mock import patch
from pathlib import Path
import sys
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 疎点転写教材 as g
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,課題を解く

def board(points,singleton,rows=12,cols=14):
    x=[[0]*cols for _ in range(rows)]
    for r,c in points:x[r][c]=2
    x[singleton[0]][singleton[1]]=1
    return x

def teachers():
    inputs=[board([(2,6),(5,3),(6,10)],(4,3)),board([(3,3),(3,8)],(2,2)),board([(3,3),(3,8)],(3,2))]
    rules={'-1,0,edge_graph':'full','-1,-1,edge_graph':'full','0,-1,edge_graph':'full'}
    return [{'input':x,'output':g.render_sparse_octilinear_point_graph_completion(x,rules,sparse_point_copy_defaults=g.sparse_point_copy_defaults(rules))[0]}for x in inputs]

class Controls(unittest.TestCase):
    def setUp(self):self.pairs=teachers();self.fitted,self.record=g.fit_teachers(self.pairs)
    def test_all_four_tables_retained(self):
        self.assertIsNotNone(self.fitted);self.assertEqual(len(self.fitted['models']),4)
        self.assertEqual(self.record['table_count'],8);self.assertTrue(self.record['enumeration_complete'])
        self.assertEqual(sum('edge_graph'in g.sparse_point_copy_defaults(m)for m in self.fitted['models']),1)
        for p in self.pairs:self.assertEqual(g.guarded_render(p['input'],self.fitted)[0],p['output'])
    def test_known_ambiguous_key_disagrees(self):
        x=board([(3,3),(3,8),(6,8)],(2,2));out,r=g.guarded_render(x,self.fitted)
        self.assertIsNone(out);self.assertEqual(r['failure'],'retained_model_grids_disagree')
        self.assertTrue(all('failure'not in q for q in r['model_records']))
    def test_missing_default_is_not_self_success(self):
        x=board([(3,3),(3,8),(6,8)],(4,2));out,r=g.guarded_render(x,self.fitted)
        self.assertIsNone(out);self.assertEqual(r['failure'],'retained_model_unresolved')
        self.assertEqual(sum(q.get('failure')=='unresolved_copy_type'for q in r['model_records']),3)
    def test_unseen_equal_masks_is_output_agreement(self):
        x=board([(3,3),(3,8)],(4,2));out,r=g.guarded_render(x,self.fitted)
        self.assertIsNotNone(out);self.assertTrue(all(q['resolutions'][0]['resolution']=='input_mask_agreement'for q in r['model_records']))
    def test_oob_type_not_filtered(self):
        x=board([(2,2),(2,8),(9,8)],(3,1),10,14)
        self.assertIsNotNone(g.render_sparse_octilinear_point_graph_completion(x,{'1,-1,edge_graph':'incident'})[0])
        p,r=g.inspect_input(x);self.assertIsNone(p);self.assertEqual(r['failure'],'copy_type_out_of_bounds')
    def test_anchor_before_type_and_bounds(self):
        x=board([(3,3),(3,5)],(2,4));p,r=g.inspect_input(x)
        self.assertIsNone(p);self.assertEqual(r['failure'],'physical_anchor_not_unique');self.assertEqual(r['anchor_count'],2)
    def test_absent_anchor_is_whole_hold(self):
        x=board([(3,3),(3,8)],(9,11));out,r=g.certify_model(x,{})
        self.assertIsNone(out);self.assertEqual(r['failure'],'physical_anchor_not_unique')
    def test_base_different_color_crossing(self):
        x=[[0]*14 for _ in range(12)]
        for p in [(5,3),(5,10)]:x[p[0]][p[1]]=2
        for p in [(2,7),(9,7)]:x[p[0]][p[1]]=3
        self.assertIsNotNone(g.render_sparse_octilinear_point_graph_completion(x)[0])
        self.assertEqual(g.certify_model(x,{})[1]['failure'],'base_colour_conflict')
    def test_copy_different_colour_crossing(self):
        x=[[0]*14 for _ in range(12)]
        for p in [(5,2),(5,8)]:x[p[0]][p[1]]=2
        for p in [(1,6),(3,6)]:x[p[0]][p[1]]=3
        x[4][1]=1;x[4][5]=4
        rules={'-1,-1,edge_graph':'full','1,-1,edge_graph':'full'}
        self.assertIsNotNone(g.render_sparse_octilinear_point_graph_completion(x,rules)[0])
        self.assertEqual(g.certify_model(x,rules)[1]['failure'],'simultaneous_colour_conflict')
    def test_disconnected_original_points_preserved(self):
        x=board([(3,3),(3,8)],(2,2));x[9][1]=3;x[10][4]=3
        out,r=g.guarded_render(x,self.fitted);self.assertIsNotNone(out)
        self.assertEqual([(i,j)for i,row in enumerate(out)for j,v in enumerate(row)if v==3],[(9,1),(10,4)])
        self.assertIn('disconnected',[q['kind']for q in r['model_records'][0]['bases']])
    def test_raw_source_output_only(self):
        original=g.render_sparse_octilinear_point_graph_completion
        def corrupted(*args,**kwargs):
            out,r=original(*args,**kwargs)
            if out is not None:out=[row[:]for row in out];out[-1][-1]=9
            return out,r
        with patch.object(g,'render_sparse_octilinear_point_graph_completion',corrupted):
            self.assertIsNone(g.guarded_render(self.pairs[0]['input'],self.fitted)[0])
    def test_budget_rejects_entire_enumeration(self):
        with patch.object(g,'TABLE_BUDGET',7):
            f,r=g.fit_teachers(self.pairs);self.assertIsNone(f);self.assertEqual(r['failure'],'table_enumeration_budget_exceeded');self.assertFalse(r['enumeration_complete'])
    def test_invalid_duplicate_and_identity(self):
        for x in [[],[[0],[]],[[True]],[[10]]]:self.assertIsNone(g.guarded_render(x,self.fitted)[0])
        self.assertIsNone(g.fit_teachers([self.pairs[0],self.pairs[0]])[0])
        x=board([(3,3),(3,4)],(3,2));self.assertIsNone(g.guarded_render(x,self.fitted)[0])
    def test_palette_permutation(self):
        mapping={0:7,1:4,2:8};pairs=[{k:[[mapping[v]for v in row]for row in grid]for k,grid in p.items()}for p in self.pairs]
        fitted,_=g.fit_teachers(pairs);self.assertIsNotNone(fitted);self.assertEqual(len(fitted['models']),4)
        for p in pairs:self.assertEqual(g.guarded_render(p['input'],fitted)[0],p['output'])

    def test_cycle_angle_tie_rejects_original_success(self):
        x=[[0]*9 for _ in range(9)]
        for r,c in [(1,2),(1,5),(3,2),(3,3),(4,3)]:x[r][c]=2
        self.assertIsNotNone(g.render_sparse_octilinear_point_graph_completion(x)[0])
        self.assertEqual(g.certify_model(x,{})[1]['failure'],'cycle_polar_ray_tie')
    def test_cycle_centroid_rejects_original_success(self):
        x=[[0]*10 for _ in range(10)]
        for r,c in [(1,1),(1,5),(5,5),(5,1),(3,3)]:x[r][c]=2
        self.assertIsNotNone(g.render_sparse_octilinear_point_graph_completion(x)[0])
        self.assertEqual(g.certify_model(x,{})[1]['failure'],'cycle_centroid_point')
    def test_models_are_not_native_support(self):
        material=g.疎点転写教材(self.pairs);machine=HDS学習実行系(最小支持数=3)
        task={'train':self.pairs,'test':[]}
        record=候補機構を学習(machine,task,(),'ARC疎点graph転写',material.候補)
        self.assertEqual(record['現在観測数'],3);self.assertEqual(record['事前観測数'],0)
        self.assertTrue(record['採用可']);self.assertTrue(record['同値採用']);self.assertEqual(record['隔離数'],0)
        self.assertEqual(len(material.記録()['全教師共通規則表']['models']),4)
    def test_runtime_unresolved_and_conflict_hold(self):
        known=board([(3,3),(3,8),(6,8)],(2,2));unknown=board([(3,3),(3,8),(6,8)],(4,2))
        result=課題を解く({'train':self.pairs,'test':[{'input':known},{'input':unknown}]},[])
        self.assertEqual([r['answer']for r in result['results']],[None,None]);self.assertEqual(result['minimum_support'],3)
    def test_runtime_rejects_ids_and_test_targets(self):
        task={'train':self.pairs,'test':[],'task_id':'forbidden'}
        with self.assertRaises(ValueError):課題を解く(task,[])
        task={'train':self.pairs,'test':[self.pairs[0]]}
        with self.assertRaises(ValueError):課題を解く(task,[])

if __name__=='__main__':unittest.main()
