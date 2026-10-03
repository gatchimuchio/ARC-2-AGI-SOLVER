"""全row/全ring保存と元符号規約・native盤面支持の回帰。"""
import unittest
from unittest.mock import patch
from pathlib import Path
import sys
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 帯輪郭教材 as g
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,課題を解く

def stripes(sequence,width=5):return [[color]*width for color in sequence]

class Controls(unittest.TestCase):
    def test_unit_rings_keep_internal_repetition(self):
        x=stripes([2,2,4,4,1,1]);out,r=g.guarded_render(x)
        self.assertEqual(r['unit_ring_count'],5);self.assertEqual(len(out),10)
        self.assertEqual([out[d][d]for d in range(5)],[2,2,4,4,1]);self.assertEqual(r['output_cells'],100)
    def test_terminal_run_removes_only_one_row(self):
        x=stripes([7,2,2,2,2]);out,r=g.guarded_render(x)
        self.assertEqual(r['raw_record']['ring_colors'],[7,2,2,2]);self.assertEqual(r['terminal_rows_removed'],1)
        self.assertEqual(out[3][3],2);self.assertEqual(out[4][4],2)
    def test_width_only_checks_uniformity(self):
        a,_=g.guarded_render(stripes([1,3,4,4],2));b,_=g.guarded_render(stripes([1,3,4,4],29));self.assertEqual(a,b)
    def test_no_background_or_frequency_role(self):
        x=stripes([2,2,4,4]);out,_=g.guarded_render(x);self.assertIsNotNone(out)
        self.assertEqual([out[d][d]for d in range(3)],[2,2,4])
    def test_minimum_domain(self):
        for x in [stripes([1,1]),stripes([1,2,2],1)]:self.assertIsNone(g.guarded_render(x)[0])
        out,r=g.guarded_render(stripes([1,2,2],2));self.assertEqual(len(out),4);self.assertEqual(r['center_shape'],[2,2])
    def test_arc_output_boundary(self):
        self.assertEqual(len(g.guarded_render(stripes([1]*16))[0]),30)
        self.assertIsNone(g.guarded_render(stripes([1]*17))[0])
    def test_nonuniform_row_no_partial_result(self):
        x=stripes([1,2,2]);x[1][-1]=5;self.assertIsNone(g.guarded_render(x)[0])
    def test_terminal_mismatch_no_alternative(self):
        self.assertIsNone(g.guarded_render(stripes([1,2,3]))[0])
    def test_invalid_arc_grid(self):
        for x in [[],[[1],[]],[[True]],[[10]],[[0]*31]*3]:self.assertIsNone(g.guarded_render(x)[0])
    def test_source_grid_and_record_only(self):
        raw=g.render_stripe_sequence_nested_square_frames
        for corrupt_record in [False,True]:
            def changed(x):
                out,r=raw(x)
                if corrupt_record:r=dict(r,ring_count=999)
                else:out[1][2]=9
                return out,r
            with patch.object(g,'render_stripe_sequence_nested_square_frames',changed):self.assertIsNone(g.guarded_render(stripes([1,2,2]))[0])
    def test_teacher_whole_fit_and_duplicate_rejection(self):
        pairs=[{'input':stripes(s,w),'output':g.guarded_render(stripes(s,w))[0]}for s,w in [([1,3,3],3),([2,2,4,4],5)]]
        self.assertTrue(g.fit_teachers(pairs)[0]);self.assertFalse(g.fit_teachers([pairs[0],pairs[0]])[0])
        pairs[1]['output'][0][0]=8;self.assertFalse(g.fit_teachers(pairs)[0])
    def test_color_permutation_equivariance(self):
        x=stripes([0,1,1,3,3]);mapping={0:9,1:0,3:7};out,_=g.guarded_render(x)
        y=[[mapping[v]for v in row]for row in x];self.assertEqual(g.guarded_render(y)[0],[[mapping[v]for v in row]for row in out])

    def test_native_support_counts_two_boards(self):
        pairs=[{'input':stripes(s,w),'output':g.guarded_render(stripes(s,w))[0]}for s,w in [([1,3,3],3),([2,2,4,4],5)]]
        material=g.帯輪郭教材(pairs)
        for minimum,admitted in [(2,True),(3,False)]:
            machine=HDS学習実行系(最小支持数=minimum);record=候補機構を学習(machine,{'train':pairs,'test':[]},(),'ARC帯列square輪郭',material.候補)
            self.assertEqual(record['現在観測数'],2);self.assertEqual(record['事前観測数'],0);self.assertTrue(record['採用可'])
            self.assertEqual(record['同値採用'],admitted);self.assertEqual(record['隔離数'],0)
    def test_native_queries_use_same_grid_and_hold(self):
        pairs=[{'input':stripes(s,w),'output':g.guarded_render(stripes(s,w))[0]}for s,w in [([1,3,3],3),([2,2,4,4],5)]]
        x=stripes([7,0,1,1],7);bad=stripes([7,0,1],7)
        result=課題を解く({'train':pairs,'test':[{'input':x},{'input':bad}]},[])
        self.assertEqual(result['minimum_support'],2);self.assertEqual(result['results'][0]['answer'],g.guarded_render(x)[0]);self.assertIsNone(result['results'][1]['answer'])
    def test_runtime_rejects_id_and_answer(self):
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[],'task_id':'forbidden'},[])
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[{'input':[[0]],'output':[[0]]}]},[])

if __name__=='__main__':unittest.main()
