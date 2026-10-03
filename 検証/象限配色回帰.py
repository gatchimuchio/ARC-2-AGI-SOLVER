"""四象限の固定符号・全座標証明とnative支持の回帰。"""
from copy import deepcopy
import unittest
from unittest.mock import patch
from pathlib import Path
import sys
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 象限配色教材 as g
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,課題を解く

def board(n, height, width, palette, template, count_color=1):
    grid = [[0] * (2*n) for _ in range(2*n)]
    for index in range(height):grid[index//n][index%n] = count_color
    for index in range(width):grid[index//n][n+index%n] = count_color
    for r in range(n):
        for c in range(n):
            grid[n+r][c] = palette[r][c]
            grid[n+r][n+c] = template[r][c]
    return grid


def examples():
    return [
        {'input':board(2,3,2,[[3,3],[3,3]],[[2,0],[0,2]]),
         'output':[[2,3],[3,2],[2,3]]},
        {'input':board(2,3,4,[[3,4],[5,6]],[[2,0],[0,2]]),
         'output':[[2,3,2,4],[3,2,4,2],[2,5,2,6]]},
        {'input':board(2,3,3,[[3,4],[5,6]],[[0,0],[0,0]]),
         'output':[[3,4,3],[5,6,5],[3,4,3]]},
        {'input':board(1,1,1,[[3]],[[2]]), 'output':[[2]]},
        {'input':board(2,1,3,[[0,0],[0,0]],[[2,0],[0,2]]),
         'output':[[2,0,2]]},
    ]


class Controls(unittest.TestCase):
    def test_five_synthetic_teachers(self):
        data=examples()
        model,record=g.fit_teachers(data)
        self.assertIsNotNone(model)
        self.assertEqual(len(record['teacher_records']),5)
        self.assertEqual([x['output_cells'] for x in record['teacher_records']],[6,12,9,1,3])

    def test_three_modes_and_partial_tiles(self):
        modes=[]
        for pair in examples():
            y,record=g.guarded_render(pair['input'])
            self.assertEqual(y,pair['output'])
            modes.append(record['raw_record']['quadrant_template_payload_mode'])
            self.assertEqual(record['template_owned_output_cells']+record['palette_owned_output_cells'],record['output_cells'])
        self.assertEqual(modes[:3],['scalar_palette','cellwise_payload','blank_template_payload'])

    def test_nonzero_color_permutations(self):
        permutation=[0,9,8,7,6,5,4,3,2,1]
        change=lambda grid:[[permutation[v] for v in row] for row in grid]
        for pair in examples():self.assertEqual(g.guarded_render(change(pair['input']))[0],change(pair['output']))

    def test_extent_positions_and_colors_only_count(self):
        pair=examples()[1];x=deepcopy(pair['input'])
        x[0][0],x[1][1]=0,8
        x[0][1]=6;x[0][2]=4;x[1][2]=7
        self.assertEqual(g.guarded_render(x)[0],pair['output'])

    def test_zero_is_not_a_permutable_background(self):
        pair=examples()[4]
        x=[[8 if v==0 else v for v in row] for row in pair['input']]
        y,record=g.guarded_render(x)
        self.assertIsNotNone(y)
        self.assertEqual(record['extent_counts'],[4,4])
        self.assertNotEqual([len(y),len(y[0])],[1,3])

    def test_uniform_and_blank_mode_priority(self):
        x=board(2,1,2,[[3,3],[3,3]],[[0,0],[0,0]])
        y,record=g.guarded_render(x)
        self.assertEqual(y,[[3,3]])
        self.assertEqual(record['raw_record']['quadrant_template_payload_mode'],'blank_template_payload')

    def test_no_transparent_stencil_cells(self):
        x=board(2,3,2,[[3,4],[5,6]],[[2,2],[2,2]])
        y,record=g.guarded_render(x)
        self.assertEqual(y,[[2,2],[2,2],[2,2]])
        self.assertEqual(record['palette_owned_output_cells'],0)
        self.assertEqual(record['independent_formula_palette_positions'],[])

    def test_unused_palette_elements_are_not_claimed_as_copied(self):
        x=board(2,1,1,[[3,4],[5,6]],[[0,2],[2,2]])
        self.assertEqual(g.guarded_render(x)[0],[[3]])
        x[3][1]=9
        self.assertEqual(g.guarded_render(x)[0],[[3]])

    def test_all_zero_palette_and_palette_template_alias(self):
        for palette in [[[0,0],[0,0]],[[2,0],[3,2]]]:
            x=board(2,3,4,palette,[[2,0],[0,2]])
            self.assertIsNotNone(g.guarded_render(x)[0])

    def test_output_thirty_passes_31_and_max225_hold(self):
        for count in [30,31,225]:
            n=6 if count<225 else 15
            x=board(n,count,count,[[3]*n for _ in range(n)],[[2 if r==c else 0 for c in range(n)]for r in range(n)])
            if count==30:
                y,record=g.guarded_render(x);self.assertEqual([len(y),len(y[0])],[30,30]);self.assertEqual(record['output_cells'],900)
            else:
                with patch.object(g,'_quadrant_template_palette_render',side_effect=AssertionError('unbounded renderer called')):
                    y,record=g.guarded_render(x)
                self.assertIsNone(y);self.assertEqual(record['failure'],'output_extent_outside_arc')

    def test_zero_extents_hold(self):
        for height,width in [(0,2),(2,0),(0,0)]:
            x=board(2,height,width,[[3,3],[3,3]],[[2,0],[0,2]])
            self.assertIsNone(g.guarded_render(x)[0])

    def test_odd_nonsquare_invalid_and_noop(self):
        for x in [[],[[True]],[[0]*31],[[0]]*31,[[1],[2,3]],[[1]*3 for _ in range(3)],[[1]*4 for _ in range(2)]]:
            self.assertIsNone(g.guarded_render(x)[0])
        x=[[1]*4 for _ in range(4)]
        self.assertEqual(g.guarded_render(x)[1]['failure'],'original_renderer_failed')

    def test_original_grid_cannot_be_replaced(self):
        x=examples()[0]['input'];old=g._quadrant_template_palette_render
        def changed(grid):
            y,record=old(grid);y[0][0]=(y[0][0]+1)%10;return y,record
        with patch.object(g,'_quadrant_template_palette_render',changed):
            self.assertEqual(g.guarded_render(x)[1]['failure'],'original_grid_disagrees')

    def test_original_record_is_exact(self):
        x=examples()[0]['input'];old=g._quadrant_template_palette_render
        def changed(grid):
            y,record=old(grid);record['extra']='mutation';return y,record
        with patch.object(g,'_quadrant_template_palette_render',changed):
            self.assertEqual(g.guarded_render(x)[1]['failure'],'original_record_disagrees')

    def test_original_failure_cannot_be_rescued(self):
        with patch.object(g,'_quadrant_template_palette_render',return_value=(None,{'failure':'forced'})):
            self.assertEqual(g.guarded_render(examples()[0]['input'])[1]['failure'],'original_renderer_failed')

    def test_raw_all_teacher_fit_precedes_proof(self):
        pairs=examples()[:2];pairs[1]['output'][0][0]=9
        with patch.object(g,'guarded_render',side_effect=AssertionError('proof before raw fit')):
            model,record=g.fit_teachers(pairs)
        self.assertIsNone(model);self.assertEqual(record['failure'],'raw_teacher_mismatch')

    def test_teacher_raw_fit_can_render_maximum_before_rejecting(self):
        n=15
        palette=[[3]*n for _ in range(n)]
        template=[[2 if r==c else 0 for c in range(n)] for r in range(n)]
        pairs=[{'input':board(n,225,width,palette,template),'output':[[9]]} for width in [225,224]]
        raw=g._quadrant_template_palette_render
        shapes=[]
        def tracked(grid):
            result,record=raw(grid);shapes.append([len(result),len(result[0])]);return result,record
        with patch.object(g,'_quadrant_template_palette_render',tracked), patch.object(g,'guarded_render',side_effect=AssertionError('proof before raw fit')):
            model,record=g.fit_teachers(pairs)
        self.assertIsNone(model)
        self.assertEqual(record['failure'],'raw_teacher_mismatch')
        self.assertEqual(shapes,[[225,225],[225,224]])

    def test_minimum_and_distinct_teachers(self):
        self.assertEqual(g.fit_teachers(examples()[:1])[1]['failure'],'too_few_teachers')
        pair=examples()[0]
        self.assertEqual(g.fit_teachers([pair,deepcopy(pair)])[1]['failure'],'duplicate_teacher_inputs')
        self.assertIsNotNone(g.fit_teachers(examples())[0])


    def test_native_support_counts_teacher_boards_only(self):
        train=examples();material=g.象限配色教材(train)
        self.assertEqual(vars(material),{'適合':True})
        for minimum,admitted in [(3,True),(6,False)]:
            machine=HDS学習実行系(最小支持数=minimum)
            record=候補機構を学習(machine,{'train':train,'test':[]},(),'ARC象限配色タイル',material.候補)
            self.assertEqual(record['現在観測数'],5)
            self.assertEqual(record['事前観測数'],0)
            self.assertEqual(record['同値採用'],admitted)
            self.assertEqual(record['隔離数'],0)

    def test_native_unresolved_is_whole_hold(self):
        train=examples();x=train[0]['input']
        result=課題を解く({'train':train,'test':[{'input':x},{'input':[[0]]}]},[])
        self.assertEqual(result['results'][0]['answer'],train[0]['output'])
        self.assertIsNone(result['results'][1]['answer'])

    def test_identifier_and_test_target_rejected(self):
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[],'task_id':'forbidden'},[])
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[{'input':[[0]],'output':[[0]]}]},[])


if __name__=='__main__':unittest.main()
