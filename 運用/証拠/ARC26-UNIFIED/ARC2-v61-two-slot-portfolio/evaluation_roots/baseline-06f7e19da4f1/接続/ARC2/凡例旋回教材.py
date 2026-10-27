"""全辞書・全body役割・有限4軌道を証明して元格子だけを同じHDSへ渡す。"""
from __future__ import annotations
from collections import Counter
from .既存凡例旋回 import _legend_guided_turning_corridor_render

def valid_grid(grid):
    return(isinstance(grid,list)and 1<=len(grid)<=30 and isinstance(grid[0],list)and 1<=len(grid[0])<=30
           and all(isinstance(row,list)and len(row)==len(grid[0])and all(type(v)is int and 0<=v<=9 for v in row)for row in grid))

def body_components(body,background):
    unseen={(r,c)for r,row in enumerate(body)for c,v in enumerate(row)if v!=background};result=[]
    while unseen:
        first=min(unseen);unseen.remove(first);colour=body[first[0]][first[1]];cells={first};stack=[first]
        while stack:
            r,c=stack.pop()
            for dr,dc in[(1,0),(-1,0),(0,1),(0,-1)]:
                q=r+dr,c+dc
                if q in unseen and body[q[0]][q[1]]==colour:unseen.remove(q);cells.add(q);stack.append(q)
        result.append({'color':colour,'cells':cells,'bbox':(min(r for r,c in cells),min(c for r,c in cells),max(r for r,c in cells),max(c for r,c in cells))})
    return result

def trace_ray(body,background,size,initial,turn_by_colour,obstacles):
    h,w=len(body),len(body[0]);direction,r,c=initial;seen=set();paint=set();turns=[];states=[];deltas=((-1,0),(0,1),(1,0),(0,-1));limit=4*h*w
    for _ in range(limit):
        state=(direction,r,c)
        if state in seen:return None,{'failure':'trajectory_cycle'}
        seen.add(state);states.append(list(state))
        if not(0<=r and 0<=c and r+size<=h and c+size<=w):return None,{'failure':'trajectory_current_out_of_bounds'}
        footprint={(a,b)for a in range(r,r+size)for b in range(c,c+size)}
        if footprint&set(obstacles):return None,{'failure':'trajectory_current_obstacle_overlap'}
        paint.update((a,b)for a,b in footprint if body[a][b]==background)
        dr,dc=deltas[direction];nr,nc=r+dr,c+dc
        if not(0<=nr and 0<=nc and nr+size<=h and nc+size<=w):
            return paint,{'states':states,'state_count':len(seen),'state_space_bound':4*(h-size+1)*(w-size+1),'turns':turns,'termination':'body_bounds','paint_cells':len(paint)}
        hits={obstacles[(a,b)]for a in range(nr,nr+size)for b in range(nc,nc+size)if(a,b)in obstacles}
        if len(hits)>1:return None,{'failure':'trajectory_multicolour_hit','colours':sorted(hits)}
        if hits:
            colour=next(iter(hits));turn=turn_by_colour.get(colour)
            if turn not in('left','right'):return None,{'failure':'trajectory_unresolved_turn'}
            direction=(direction+(-1 if turn=='left'else 1))%4;turns.append({'hit_color':colour,'turn':turn,'row':r,'col':c,'direction_after_turn':direction})
        else:r,c=nr,nc
    return None,{'failure':'trajectory_incomplete_at_original_limit'}

def guarded_render(grid):
    if not valid_grid(grid):return None,{'failure':'invalid_arc_grid'}
    ih,w=len(grid),len(grid[0])
    if ih<=6 or w<12 or w%6:return None,{'failure':'fixed_dictionary_shape_required'}
    control=grid[:6];body=grid[6:];h=len(body);counts=Counter(v for row in control for v in row);leaders=[v for v,n in counts.items()if n==max(counts.values())]
    if len(leaders)!=1:return None,{'failure':'guide_mode_tie'}
    guide=leaders[0];turns={};panels=[]
    for left in range(0,w,6):
        border={(r,c)for r in range(6)for c in range(left,left+6)if r in(0,5)or c in(left,left+5)}
        if any(grid[r][c]!=guide for r,c in border):return None,{'failure':'dictionary_border_disagrees'}
        active=[(r,c,grid[r][c])for r in range(1,5)for c in range(left+1,left+5)if grid[r][c]!=0]
        colours={v for r,c,v in active};columns={c-left for r,c,v in active}
        if len(active)!=4 or len(colours)!=1 or len(columns)!=1:return None,{'failure':'dictionary_key_bar_unresolved'}
        colour=next(iter(colours));column=next(iter(columns))
        if column not in(1,4)or colour==guide or colour in turns:return None,{'failure':'dictionary_key_role_unresolved'}
        expected={(r,left+column)for r in range(1,5)}
        if {(r,c)for r,c,v in active}!=expected:return None,{'failure':'dictionary_key_coverage_failed'}
        turns[colour]='left'if column==1 else'right';panels.append({'panel_start':left,'marker_color':colour,'marker_column':column,'turn':turns[colour]})
    counts=Counter(v for row in body for v in row);leaders=[v for v,n in counts.items()if n==max(counts.values())]
    if len(leaders)!=1:return None,{'failure':'body_background_tie'}
    bg=leaders[0]
    if bg in turns:return None,{'failure':'body_background_key_alias'}
    components=body_components(body,bg);seeds=[];obstacles={};owned=set()
    for component in components:
        colour=component['color'];cells=component['cells'];r,c,bottom,right=component['bbox'];rh,cw=bottom-r+1,right-c+1
        if cells!={(a,b)for a in range(r,bottom+1)for b in range(c,right+1)}:return None,{'failure':'body_component_not_rectangle'}
        if colour in turns:obstacles.update({cell:colour for cell in cells})
        elif rh==cw and rh>=2:seeds.append(component)
        else:return None,{'failure':'body_component_unowned'}
        if owned&cells:return None,{'failure':'body_components_overlap'}
        owned.update(cells)
    foreground={(r,c)for r,row in enumerate(body)for c,v in enumerate(row)if v!=bg}
    if owned!=foreground:return None,{'failure':'body_foreground_coverage_failed'}
    if len(seeds)!=1 or not obstacles:return None,{'failure':'body_seed_or_obstacles_unresolved','seed_count':len(seeds)}
    seed=seeds[0];sr,sc,sb,sright=seed['bbox'];size=sb-sr+1;seed_colour=seed['color'];initial=[(0,sr-size,sc),(1,sr,sc+size),(2,sr+size,sc),(3,sr,sc-size)]
    for direction,r,c in initial:
        if not(0<=r and 0<=c and r+size<=h and c+size<=w):return None,{'failure':'initial_block_out_of_bounds','direction':direction,'anchor':[r,c]}
        if any((a,b)in obstacles for a in range(r,r+size)for b in range(c,c+size)):return None,{'failure':'initial_block_obstacle_overlap','direction':direction,'anchor':[r,c]}
    proposals=set();rays=[];turn_records=[]
    for initial_state in initial:
        paint,record=trace_ray(body,bg,size,initial_state,turns,obstacles)
        if paint is None:return None,dict(record,initial_direction=initial_state[0])
        if record['state_count']>record['state_space_bound']:return None,{'failure':'state_space_bound_exceeded'}
        proposals.update(paint);rays.append(record);turn_records.extend(record['turns'])
    expected=[list(row)for row in body]
    for r,c in proposals:
        if body[r][c]!=bg:return None,{'failure':'proposal_overwrites_foreground'}
        expected[r][c]=seed_colour
    raw,record=_legend_guided_turning_corridor_render(grid)
    if raw is None:return None,{'failure':'original_renderer_unresolved','raw_record':record}
    expected_record={'renderer_case':'legend_guided_turning_corridor','legend_corridor_guide_color':guide,'legend_corridor_panel_records':panels,'legend_corridor_background_color':bg,'legend_corridor_seed_color':seed_colour,'legend_corridor_seed_bbox':[sr,sc,sb,sright],'legend_corridor_obstacle_colors':sorted(set(obstacles.values())),'legend_corridor_turn_records':turn_records,'legend_corridor_event_count':len(proposals),'legend_corridor_input_shape':[ih,w],'legend_corridor_output_shape':[h,w]}
    if raw!=expected or record!=expected_record:return None,{'failure':'original_grid_or_record_disagreement'}
    if any(raw[r][c]!=body[r][c]for r in range(h)for c in range(w)if(r,c)not in proposals):return None,{'failure':'outside_proposal_changed'}
    return raw,{'raw_record':record,'dictionary_cells':6*w,'body_foreground_cells':len(foreground),'obstacle_components':len(components)-1,'seed_pixels':len(seed['cells']),'initial_blocks':[list(s)for s in initial],'rays':rays,'proposal_union':len(proposals),'proposal_sum':sum(r['paint_cells']for r in rays),'preserved_body_cells':h*w-len(proposals),'unused_dictionary_colours':sorted(set(turns)-set(obstacles.values()))}

def fit_teachers(teachers):
    if len(teachers)<2 or any(not valid_grid(p['input'])or not valid_grid(p['output'])for p in teachers):return None,{'failure':'insufficient_or_invalid_teachers'}
    if len({tuple(map(tuple,p['input']))for p in teachers})!=len(teachers):return None,{'failure':'duplicate_teacher_inputs'}
    raw=[_legend_guided_turning_corridor_render(p['input'])for p in teachers];fits=[o is not None and o==p['output']for(o,r),p in zip(raw,teachers)];record={'raw_pair_fits':fits,'raw_records':[r for o,r in raw]}
    if not all(fits):return None,dict(record,failure='original_teacher_reproduction_failed')
    guarded=[guarded_render(p['input'])for p in teachers];record['teacher_records']=[r for o,r in guarded]
    if any(o is None or o!=p['output']for(o,r),p in zip(guarded,teachers)):return None,dict(record,failure='teacher_certificate_failed')
    return {'program':'legend_guided_turning_corridor'},record

class 凡例旋回教材:
    def __init__(self, 教師群):
        self.規約, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if self.規約 is None:
            return None, {"failure": "全教師を再現する凡例旋回なし"}
        return guarded_render(格子)

    def 記録(self):
        return {"全教師共通凡例旋回規約": self.規約}
