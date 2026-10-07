"""現在教師の全共有命令表を完走探索する新しい記号interpreter。"""
from __future__ import annotations
from collections import Counter

ORDERS=tuple((major,row_reverse,col_reverse)for major in('rows','columns')
             for row_reverse in(False,True)for col_reverse in(False,True))
DIRECTIONS={'L':(0,-1),'R':(0,1),'D':(1,0)}
SEARCH_BUDGET=100000


def valid_grid(grid):
    return (isinstance(grid,list)and 1<=len(grid)<=30 and isinstance(grid[0],list)
            and 1<=len(grid[0])<=30 and all(isinstance(row,list)and len(row)==len(grid[0])
            and all(type(v)is int and 0<=v<=9 for v in row)for row in grid))


def parse_input(grid):
    if not valid_grid(grid):return None,{'failure':'invalid_grid'}
    height,width=len(grid),len(grid[0]);counts=Counter(v for row in grid for v in row)
    modes=sorted(v for v,n in counts.items()if n==max(counts.values()))
    record={'input_shape':[height,width],'background_candidates':modes}
    if len(modes)!=1:return None,{**record,'failure':'background_tie'}
    background=modes[0]
    separators=[{'column':c,'colour':grid[0][c]}for c in range(1,width-1)
                if grid[0][c]!=background and all(row[c]==grid[0][c]for row in grid)]
    record.update(background=background,raw_separators=separators)
    if len(separators)!=1:return None,{**record,'failure':'separator_not_unique'}
    separator=separators[0]['column']
    if height%4!=3 or separator%4!=3:return None,{**record,'failure':'not_three_cell_glyph_lattice'}
    if any(grid[r][c]!=background for r in range(height)for c in range(separator)if r%4==3 or c%4==3):
        return None,{**record,'failure':'nonblank_instruction_gaps'}
    canvas=[row[separator+1:]for row in grid]
    starts=[[r,c,v]for r,row in enumerate(canvas)for c,v in enumerate(row)if v!=background]
    record.update(canvas_shape=[height,width-separator-1],start_candidates=starts)
    if len(starts)!=1 or starts[0][0]!=0:return None,{**record,'failure':'canvas_not_one_top_start'}
    instructions=[];foreground=0
    for gr,top in enumerate(range(0,height,4)):
        for gc,left in enumerate(range(0,separator,4)):
            tile=[row[left:left+3]for row in grid[top:top+3]]
            colours=sorted({v for row in tile for v in row if v!=background})
            if len(colours)!=1:return None,{**record,'failure':'empty_or_multicolour_instruction','instruction_position':[gr,gc]}
            mask=''.join('1'if v!=background else'0'for row in tile for v in row)
            cells=mask.count('1');foreground+=cells
            instructions.append({'row':gr,'column':gc,'mask':mask,'colour':colours[0],'foreground_cells':cells})
    program_shape=[(height+1)//4,(separator+1)//4]
    glyph_cells=9*len(instructions);gap_cells=height*separator-glyph_cells
    canvas_cells=height*(width-separator-1)
    if glyph_cells+gap_cells+height+canvas_cells!=height*width:
        return None,{**record,'failure':'input_ownership_failed'}
    record.update(program_shape=program_shape,instructions=instructions,instruction_count=len(instructions),
                  glyph_cells=glyph_cells,instruction_foreground_cells=foreground,gap_cells=gap_cells,
                  separator_cells=height,canvas_cells=canvas_cells)
    return {'background':background,'canvas':canvas,'start':starts[0],
            'program_shape':program_shape,'instructions':instructions},record


def ordered_instructions(parsed,order_id):
    major,row_reverse,col_reverse=ORDERS[order_id]
    height,width=parsed['program_shape']
    rows=list(range(height-1,-1,-1))if row_reverse else list(range(height))
    cols=list(range(width-1,-1,-1))if col_reverse else list(range(width))
    positions=([(r,c)for r in rows for c in cols]if major=='rows'else[(r,c)for c in cols for r in rows])
    return [parsed['instructions'][r*width+c]for r,c in positions]


def render_parsed(parsed,model):
    if not isinstance(model,(tuple,list))or len(model)!=2:return None,{'failure':'invalid_model'}
    order_id,rule_entries=model
    if type(order_id)is not int or not 0<=order_id<len(ORDERS)or not isinstance(rule_entries,(list,tuple)):
        return None,{'failure':'invalid_model'}
    rules={}
    for entry in rule_entries:
        if not isinstance(entry,(tuple,list))or len(entry)!=3:return None,{'failure':'invalid_model'}
        mask,direction,length=entry
        if (not isinstance(mask,str)or len(mask)!=9 or set(mask)-{'0','1'}or '1'not in mask
                or not isinstance(direction,str)or direction not in DIRECTIONS or type(length)is not int or not 1<=length<=30 or mask in rules):
            return None,{'failure':'invalid_model'}
        rules[mask]=(direction,length)
    height,width=len(parsed['canvas']),len(parsed['canvas'][0]);output=[row[:]for row in parsed['canvas']]
    sr,sc,start_colour=parsed['start'];cursor=(sr,sc);owned={(sr,sc)};steps=[];expected_colours=Counter({start_colour:1})
    sequence=ordered_instructions(parsed,order_id)
    for index,instruction in enumerate(sequence):
        mask=instruction['mask']
        if mask not in rules:return None,{'failure':'unknown_glyph','instruction_index':index,'mask':mask,'order_id':order_id}
        direction,length=rules[mask];dr,dc=DIRECTIONS[direction];start=(cursor[0]+1,cursor[1])
        cells=[(start[0]+step*dr,start[1]+step*dc)for step in range(length)]
        if any(not(0<=r<height and 0<=c<width)for r,c in cells):
            return None,{'failure':'command_out_of_bounds','instruction_index':index,'order_id':order_id,'start':list(start),'direction':direction,'length':length}
        if len(set(cells))!=len(cells)or set(cells)&owned:
            return None,{'failure':'command_overlap','instruction_index':index,'order_id':order_id}
        for r,c in cells:output[r][c]=instruction['colour']
        expected_colours[instruction['colour']]+=len(cells);owned.update(cells);cursor=cells[-1]
        steps.append({'instruction_position':[instruction['row'],instruction['column']],'mask':mask,
            'colour':instruction['colour'],'direction':direction,'length':length,
            'start':list(start),'end':list(cursor),'cells':[list(p)for p in cells]})
    expected_colours[parsed['background']]+=height*width-len(owned)
    actual_colours=Counter(v for row in output for v in row)
    if +expected_colours!=actual_colours or output[sr][sc]!=start_colour or len(steps)!=len(parsed['instructions']):
        return None,{'failure':'output_ownership_failed'}
    return output,{'order_id':order_id,'order':list(ORDERS[order_id]),'steps':steps,'instruction_count':len(steps),
        'painted_cells':len(owned)-1,'start_cells':1,'unchanged_background_cells':height*width-len(owned),
        'output_shape':[height,width],'output_colour_counts':[[v,n]for v,n in sorted(actual_colours.items())]}


def render_model(grid,model):
    parsed,record=parse_input(grid)
    if parsed is None:return None,record
    output,execution=render_parsed(parsed,model)
    return output,{**record,'execution':execution,**({'failure':execution['failure']}if output is None else{})}


def fit_models(train,budget=SEARCH_BUDGET):
    if not isinstance(train,list)or len(train)<2:return None,{'failure':'too_few_teachers','complete':True}
    if any(not isinstance(p,dict)or not valid_grid(p.get('input'))or not valid_grid(p.get('output'))for p in train):
        return None,{'failure':'invalid_teachers','complete':True}
    keys=[tuple(map(tuple,p['input']))for p in train]
    if len(set(keys))!=len(keys):return None,{'failure':'duplicate_teacher_inputs','complete':True}
    if type(budget)is not int or budget<0:return None,{'failure':'invalid_search_budget','complete':False}
    parsed_pairs=[parse_input(p['input'])for p in train];records=[r for _,r in parsed_pairs]
    if any(p is None for p,_ in parsed_pairs):return None,{'failure':'teacher_input_contract','complete':True,'teacher_parse_records':records}
    parsed=[p for p,_ in parsed_pairs]
    for data,pair in zip(parsed,train):
        canvas=data['canvas'];target=pair['output'];r,c,colour=data['start']
        if len(canvas)!=len(target)or len(canvas[0])!=len(target[0])or target[r][c]!=colour:
            return None,{'failure':'teacher_canvas_mismatch','complete':True,'teacher_parse_records':records}
    work=0;models=set();first_model_work=None;completed_orders=[]
    class BudgetExceeded(Exception):pass
    def spend(amount=1):
        nonlocal work
        work+=amount
        if work>budget:raise BudgetExceeded
    def visit(order_id,teacher_index,step_index,cursor,canvas,occupied,rules,sequences):
        nonlocal first_model_work
        spend()
        if teacher_index==len(train):
            spend(1+len(rules))
            model=(order_id,tuple((mask,*command)for mask,command in sorted(rules.items())))
            models.add(model)
            if first_model_work is None:first_model_work=work
            return
        target=train[teacher_index]['output'];sequence=sequences[teacher_index];height,width=len(canvas),len(canvas[0])
        if cursor[0]+len(sequence)-step_index>=height:return
        if step_index==len(sequence):
            if canvas!=target:return
            next_teacher=teacher_index+1
            if next_teacher==len(train):
                visit(order_id,next_teacher,0,None,None,None,rules,sequences)
            else:
                data=parsed[next_teacher];sr,sc,_=data['start']
                visit(order_id,next_teacher,0,(sr,sc),[row[:]for row in data['canvas']],{(sr,sc)},rules,sequences)
            return
        instruction=sequence[step_index];mask=instruction['mask'];known=mask in rules
        options=[rules[mask]]if known else[(direction,n)for direction in DIRECTIONS for n in range(1,31)]
        for direction,length in options:
            spend();dr,dc=DIRECTIONS[direction];start=(cursor[0]+1,cursor[1])
            cells=[(start[0]+step*dr,start[1]+step*dc)for step in range(length)]
            if any(not(0<=r<height and 0<=c<width)for r,c in cells):continue
            if set(cells)&occupied or any(target[r][c]!=instruction['colour']for r,c in cells):continue
            next_canvas=[row[:]for row in canvas]
            for r,c in cells:next_canvas[r][c]=instruction['colour']
            endpoint=cells[-1]
            if any(next_canvas[r]!=target[r]for r in range(endpoint[0]+1)):continue
            next_rules=rules if known else{**rules,mask:(direction,length)}
            visit(order_id,teacher_index,step_index+1,endpoint,next_canvas,occupied|set(cells),next_rules,sequences)
    try:
        for order_id in range(len(ORDERS)):
            sequences=[ordered_instructions(data,order_id)for data in parsed]
            sr,sc,_=parsed[0]['start']
            visit(order_id,0,0,(sr,sc),[row[:]for row in parsed[0]['canvas']],{(sr,sc)},{},sequences)
            completed_orders.append(order_id)
    except BudgetExceeded:
        return None,{'failure':'search_budget_incomplete','complete':False,'budget':budget,'work_units':work,
                     'completed_orders':completed_orders,'models_found_before_stop':len(models),
                     'first_model_work_units':first_model_work,'teacher_parse_records':records}
    result=sorted(models)
    record={'complete':True,'budget':budget,'work_units':work,'completed_orders':completed_orders,
            'retained_model_count':len(result),'first_model_work_units':first_model_work,'teacher_parse_records':records}
    if not result:return None,{**record,'failure':'no_shared_program_model'}
    return result,record


def consensus(grid,models):
    parsed,record=parse_input(grid)
    if parsed is None:return None,record
    if not isinstance(models,(list,tuple))or not models:return None,{**record,'failure':'no_retained_models'}
    outputs=[];executions=[]
    for index,model in enumerate(models):
        output,execution=render_parsed(parsed,model);executions.append(execution)
        if output is None:return None,{**record,'failure':'retained_model_failed','failed_model_index':index,'model_records':executions}
        outputs.append(output)
    if any(output!=outputs[0]for output in outputs[1:]):
        return None,{**record,'failure':'retained_model_grids_disagree','model_records':executions}
    return outputs[0],{**record,'retained_model_count':len(models),'model_records':executions}


class 記号命令教材:
    def __init__(self, 教師群):
        models, old_fit_record = fit_models(教師群)
        self.モデル = tuple(models) if models is not None else ()
        if models is None:
            from .枠局所命令接続 import fit_after_complete_instruction_no_fit
            state, _ = fit_after_complete_instruction_no_fit(教師群, models, old_fit_record)
            if state is not None:
                self.枠局所命令 = state

    def 候補(self, 格子, _policy):
        if not self.モデル:
            if getattr(self, "枠局所命令", None) is not None:
                from .枠局所命令接続 import render_embedded
                return render_embedded(格子)
            return None, {"failure": "全教師を再現する完走命令表なし"}
        return consensus(格子, self.モデル)

    def 記録(self):
        if getattr(self, "枠局所命令", None) is not None:
            return {"完走適合model数": 0, "読取順序": [], "埋込枠局所命令": True}
        return {"完走適合model数": len(self.モデル), "読取順序": sorted({m[0] for m in self.モデル})}
