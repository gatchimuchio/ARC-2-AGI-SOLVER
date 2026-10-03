"""全記号・共有命令表の完走探索と全model合意/native支持の回帰。"""
from pathlib import Path
from copy import deepcopy
from itertools import product
import sys
import unittest
根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 記号命令教材 as g
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習,課題を解く

A='010101010'
B='101010101'
C='110011100'


def direct_execution(parsed,model):
    order,entries=model;rules={m:(d,n)for m,d,n in entries}
    major='rows'if order<4 else'columns';reverse_row=bool((order%4)//2);reverse_col=bool(order%2)
    row_sign=-1 if reverse_row else 1;col_sign=-1 if reverse_col else 1
    instructions=sorted(parsed['instructions'],key=lambda x:
        (row_sign*x['row'],col_sign*x['column'])if major=='rows'else(col_sign*x['column'],row_sign*x['row']))
    output=[row[:]for row in parsed['canvas']];r,c,_=parsed['start'];used={(r,c)}
    for instruction in instructions:
        direction,length=rules[instruction['mask']];r+=1;cells=[]
        for k in range(length):
            rr=r+(k if direction=='D'else 0);cc=c+(-k if direction=='L'else k if direction=='R'else 0)
            if not(0<=rr<len(output)and 0<=cc<len(output[0]))or(rr,cc)in used:return None
            cells.append((rr,cc))
        for rr,cc in cells:output[rr][cc]=instruction['colour'];used.add((rr,cc))
        r,c=cells[-1]
    return output


def case(program=None,rules=None,order=0,start_column=3,canvas_width=8,background=0,separator_colour=9,start_colour=5):
    program=program if program is not None else[[(A,1),(B,1)]]
    rules=rules if rules is not None else{A:('R',2),B:('L',2)}
    rows,cols=len(program),len(program[0]);height=4*rows-1;left_width=4*cols-1
    grid=[[background]*(left_width+1+canvas_width)for _ in range(height)]
    instructions=[]
    for r in range(height):grid[r][left_width]=separator_colour
    for r,row in enumerate(program):
        for c,(mask,colour)in enumerate(row):
            for k,bit in enumerate(mask):
                if bit=='1':grid[4*r+k//3][4*c+k%3]=colour
            instructions.append({'row':r,'column':c,'mask':mask,'colour':colour})
    grid[0][left_width+1+start_column]=start_colour
    parsed={'canvas':[row[left_width+1:]for row in grid],'start':[0,start_column,start_colour],'instructions':instructions}
    model=(order,tuple((m,*v)for m,v in sorted(rules.items())))
    return {'input':grid,'output':direct_execution(parsed,model)}


def exhaustive_models(train):
    parsed=[g.parse_input(p['input'])[0]for p in train]
    if any(p is None for p in parsed):return set()
    masks=sorted({x['mask']for p in parsed for x in p['instructions']})
    domain=[(d,n)for d in('L','R','D')for n in range(1,31)];found=set()
    for order in range(8):
        for choices in product(domain,repeat=len(masks)):
            model=(order,tuple((mask,*choice)for mask,choice in zip(masks,choices)))
            if all(direct_execution(p,model)==pair['output']for p,pair in zip(parsed,train)):found.add(model)
    return found


def examples():
    return [case(program=[[(A,1),(B,2)]],start_column=2),
            case(program=[[(A,1),(B,2)]],start_column=3),
            case(program=[[(A,1)],[(B,2)]],start_column=3)]


class Controls(unittest.TestCase):
    def test_generated_three_teacher_complete_shared_models(self):
        train=examples();models,record=g.fit_models(train)
        self.assertIsNotNone(models);self.assertTrue(record['complete'])
        self.assertEqual(record['completed_orders'],list(range(8)))
        for pair in train:self.assertEqual(g.consensus(pair['input'],models)[0],pair['output'])

    def test_all_model_set_matches_two_glyph_full_cartesian_oracle(self):
        train=[case(start_column=2),case(start_column=3)]
        models,record=g.fit_models(train);self.assertTrue(record['complete'])
        self.assertEqual(set(models),exhaustive_models(train));self.assertEqual(len(models),8)

    def test_one_glyph_length_one_all_direction_and_order_aliases_retained(self):
        train=[case(program=[[(A,1)]],rules={A:('D',1)},start_column=c)for c in [2,3]]
        models,record=g.fit_models(train);self.assertEqual(len(models),24)
        self.assertEqual(set(models),exhaustive_models(train))
        self.assertEqual({m[0]for m in models},set(range(8)))
        self.assertEqual({m[1][0][1]for m in models},{'L','R','D'})
        query=case(program=[[(A,7)]],rules={A:('D',1)},start_column=1)
        output,r=g.consensus(query['input'],models);self.assertEqual(output,query['output']);self.assertEqual(r['retained_model_count'],24)

    def test_teacher_order_changes_work_not_complete_model_set(self):
        train=[case(start_column=2),case(start_column=3)]
        a,ar=g.fit_models(train);b,br=g.fit_models(train[::-1]);self.assertTrue(ar['complete']and br['complete'])
        self.assertEqual(a,b)

    def test_exact_search_budget_and_one_unit_short(self):
        train=[case(start_column=2),case(start_column=3)]
        models,record=g.fit_models(train);needed=record['work_units']
        exact,r=g.fit_models(train,budget=needed);self.assertTrue(r['complete']);self.assertEqual(exact,models)
        missing,r=g.fit_models(train,budget=needed-1);self.assertIsNone(missing);self.assertFalse(r['complete'])
        self.assertEqual(r['failure'],'search_budget_incomplete')

    def test_budget_stop_after_first_model_never_admits_partial_set(self):
        train=[case(start_column=2),case(start_column=3)];models,record=g.fit_models(train)
        partial,r=g.fit_models(train,budget=record['first_model_work_units'])
        self.assertIsNone(partial);self.assertFalse(r['complete']);self.assertGreater(r['models_found_before_stop'],0)

    def test_train_equivalent_orders_disagree_on_new_program(self):
        train=[case(start_column=2),case(start_column=3)];models,_=g.fit_models(train)
        query=case(program=[[(A,1),(A,1)]],rules={A:('R',2)},start_column=3,canvas_width=10)
        output,record=g.consensus(query['input'],models);self.assertIsNone(output)
        self.assertEqual(record['failure'],'retained_model_grids_disagree')

    def test_one_out_of_bounds_model_vetoes_others_that_succeed(self):
        train=[case(start_column=2),case(start_column=3)];models,_=g.fit_models(train)
        query=case(program=[[(A,1),(A,1)]],rules={A:('R',2)},start_column=0,canvas_width=10)
        outcomes=[g.render_model(query['input'],model)[0]for model in models]
        self.assertTrue(any(x is None for x in outcomes));self.assertTrue(any(x is not None for x in outcomes))
        output,record=g.consensus(query['input'],models);self.assertIsNone(output);self.assertEqual(record['failure'],'retained_model_failed')

    def test_unknown_glyph_vetoes_prediction(self):
        models,_=g.fit_models([case(start_column=2),case(start_column=3)])
        query=case(program=[[(C,1)]],rules={C:('D',1)})
        output,record=g.consensus(query['input'],models);self.assertIsNone(output)
        self.assertEqual(record['model_records'][-1]['failure'],'unknown_glyph')

    def test_all_eight_reading_orders_as_models(self):
        program=[[(A,1),(B,2)],[(C,3),(A,4)]];rules={A:('R',1),B:('L',1),C:('D',1)}
        for order in range(8):
            pair=case(program=program,rules=rules,order=order)
            model=(order,tuple((m,*v)for m,v in sorted(rules.items())))
            output,record=g.render_model(pair['input'],model);self.assertEqual(output,pair['output'])
            self.assertEqual(record['execution']['instruction_count'],4)

    def test_same_glyph_different_colours_and_start_colour_alias(self):
        program=[[(A,2)],[(A,7)]];rules={A:('D',2)}
        train=[case(program=program,rules=rules,start_column=c,start_colour=2)for c in [2,3]]
        models,record=g.fit_models(train);self.assertIsNotNone(models)
        query=case(program=[[(A,8)],[(A,1)]],rules=rules,start_column=4,start_colour=8)
        output,r=g.consensus(query['input'],models);self.assertEqual(output,query['output'])
        self.assertEqual(dict(r['model_records'][0]['output_colour_counts'])[8],3)

    def test_arbitrary_masks_and_colour_permutation(self):
        program=[[('111111111',1),('000010000',2)],[('100000001',3),(C,4)]]
        rules={mask:('D',1)for row in program for mask,colour in row};pair=case(program=program,rules=rules)
        model=(0,tuple((m,*v)for m,v in sorted(rules.items())))
        for shift in range(10):
            x=[[(v+shift)%10 for v in row]for row in pair['input']]
            y=[[(v+shift)%10 for v in row]for row in pair['output']]
            self.assertEqual(g.render_model(x,model)[0],y)

    def test_adjacent_same_colour_steps_are_not_merged(self):
        pair=case();model=(0,((A,'R',2),(B,'L',2)))
        output,record=g.render_model(pair['input'],model);self.assertEqual(output,pair['output'])
        self.assertEqual(record['execution']['instruction_count'],2)
        self.assertEqual(record['execution']['painted_cells'],4)

    def test_non_square_narrow_canvas_and_unpainted_tail(self):
        program=[[(A,1)],[(A,1)],[(A,1)]];rules={A:('D',1)}
        pair=case(program=program,rules=rules,canvas_width=1,start_column=0)
        output,record=g.render_model(pair['input'],(0,((A,'D',1),)));self.assertEqual(output,pair['output'])
        self.assertEqual(record['execution']['output_shape'],[11,1])
        self.assertEqual(record['execution']['unchanged_background_cells'],7)

    def test_maximum_input_width_and_length30_out_of_bounds(self):
        pair=case(program=[[(A,1)]],rules={A:('R',26)},canvas_width=26,start_column=0)
        self.assertEqual(len(pair['input'][0]),30)
        self.assertEqual(g.render_model(pair['input'],(0,((A,'R',26),)))[0],pair['output'])
        out,record=g.render_model(pair['input'],(0,((A,'R',30),)))
        self.assertIsNone(out);self.assertEqual(record['failure'],'command_out_of_bounds')

    def test_extra_raw_separator_not_deleted_for_bad_canvas(self):
        pair=case(canvas_width=10);x=pair['input']
        for row in x:row[16]=8
        parsed,record=g.parse_input(x);self.assertIsNone(parsed)
        self.assertEqual(record['failure'],'separator_not_unique');self.assertEqual(len(record['raw_separators']),2)

    def test_gaps_empty_multicolour_and_wrong_lattice(self):
        base=case(program=[[(A,1)],[(B,2)]],rules={A:('D',1),B:('D',1)})['input']
        x=deepcopy(base);x[3][0]=3;self.assertEqual(g.parse_input(x)[1]['failure'],'nonblank_instruction_gaps')
        x=deepcopy(base)
        for r in range(3):
            for c in range(3):x[r][c]=0
        self.assertEqual(g.parse_input(x)[1]['failure'],'empty_or_multicolour_instruction')
        x=deepcopy(base);x[0][1]=3;self.assertEqual(g.parse_input(x)[1]['failure'],'empty_or_multicolour_instruction')
        x=deepcopy(base);x.append([0,0,0,9]+[0]*(len(x[0])-4))
        self.assertEqual(g.parse_input(x)[1]['failure'],'not_three_cell_glyph_lattice')

    def test_non_top_or_multiple_start_and_background_tie(self):
        for multiple in [False,True]:
            x=case()['input'];x[1][11]=5
            if not multiple:x[0][11]=0
            self.assertEqual(g.parse_input(x)[1]['failure'],'canvas_not_one_top_start')
        self.assertEqual(g.parse_input([[0,1],[1,0]])[1]['failure'],'background_tie')

    def test_every_input_and_output_cell_owned_once(self):
        pair=case();out,record=g.render_model(pair['input'],(0,((A,'R',2),(B,'L',2))))
        self.assertEqual(out,pair['output'])
        self.assertEqual(record['glyph_cells']+record['gap_cells']+record['separator_cells']+record['canvas_cells'],len(pair['input'])*len(pair['input'][0]))
        execution=record['execution'];cells=[tuple(p)for step in execution['steps']for p in step['cells']]
        self.assertEqual(len(cells),len(set(cells)));self.assertNotIn((0,3),cells)
        self.assertEqual(execution['painted_cells']+execution['start_cells']+execution['unchanged_background_cells'],len(out)*len(out[0]))

    def test_invalid_commands_grids_and_whole_teacher_mismatch(self):
        x=case()['input']
        for entry in [(A,'U',2),(A,'D',0),(A,'D',31),(A,[],1),(A,'D',True)]:
            self.assertEqual(g.render_model(x,(0,(entry,)))[1]['failure'],'invalid_model')
        for grid in [[],[[]],[[True]],[[10]],[[0],[0,1]],[[0]*31],[[0]for _ in range(31)]]:
            self.assertEqual(g.parse_input(grid)[1]['failure'],'invalid_grid')
        train=[case(start_column=2),case(start_column=3)];train[1]['output'][2][0]=3
        models,record=g.fit_models(train);self.assertIsNone(models);self.assertTrue(record['complete'])

    def test_minimum_distinct_teachers_and_detached_table(self):
        train=[case(start_column=2),case(start_column=3)];models,_=g.fit_models(train);saved=deepcopy(models)
        self.assertEqual(g.fit_models(train[:1])[1]['failure'],'too_few_teachers')
        self.assertEqual(g.fit_models([train[0],deepcopy(train[0])])[1]['failure'],'duplicate_teacher_inputs')
        before=g.consensus(case(start_column=4,canvas_width=10)['input'],models)
        train[0]['input'][:]=[[0]];train[0]['output'][:]=[[0]]
        self.assertEqual(models,saved)
        self.assertEqual(g.consensus(case(start_column=4,canvas_width=10)['input'],models),before)


    def test_native_support_counts_three_boards_not_models_or_commands(self):
        train=examples();material=g.記号命令教材(train)
        self.assertEqual(set(vars(material)),{'モデル'})
        self.assertTrue(all(isinstance(model,tuple) and isinstance(model[1],tuple) for model in material.モデル))
        for minimum,admitted in [(3,True),(4,False)]:
            machine=HDS学習実行系(最小支持数=minimum)
            rec=候補機構を学習(machine,{'train':train,'test':[]},(),'ARC記号命令列',material.候補)
            self.assertEqual(rec['現在観測数'],3);self.assertEqual(rec['事前観測数'],0)
            self.assertEqual(rec['同値採用'],admitted);self.assertEqual(rec['隔離数'],0)

    def test_native_hold_and_detached_abstract_table(self):
        train=examples();material=g.記号命令教材(train)
        query=case(program=[[(A,1)],[(B,2)]],start_column=4,canvas_width=10)
        train[0]['input'][:]=[[0]];train[0]['output'][:]=[[0]]
        self.assertEqual(material.候補(query['input'],None)[0],query['output'])
        result=課題を解く({'train':examples(),'test':[{'input':query['input']},{'input':[[0]]}]},[])
        self.assertEqual(result['results'][0]['answer'],query['output'])
        self.assertIsNone(result['results'][1]['answer'])

    def test_identifier_and_test_output_are_rejected(self):
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[],'task_id':'forbidden'},[])
        with self.assertRaises(ValueError):課題を解く({'train':[],'test':[{'input':[[0]],'output':[[0]]}]},[])

if __name__=='__main__':unittest.main()
