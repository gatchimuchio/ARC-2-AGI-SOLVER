"""New input wall-profile completion with fixed terminal plateaus and column occlusion."""

from collections import Counter, defaultdict

DIRECTIONS=("south","north","east","west")

def runs(xs):
 out=[]
 for x in sorted(xs):
  if not out or x>out[-1][-1]+1:out.append([x])
  else:out[-1].append(x)
 return out

def c8_components(cells):
 left=set(cells);out=[]
 while left:
  seed=min(left);left.remove(seed);seen={seed};q=[seed]
  while q:
   t,x=q.pop()
   for dt in [-1,0,1]:
    for dx in [-1,0,1]:
     p=(t+dt,x+dx)
     if p in left:left.remove(p);seen.add(p);q.append(p)
  out.append(sorted(seen))
 return out

def c4_components(cells):
 left=set(cells);out=[]
 while left:
  seed=min(left);left.remove(seed);seen={seed};q=[seed]
  while q:
   t,x=q.pop()
   for dt,dx in [(1,0),(-1,0),(0,1),(0,-1)]:
    p=(t+dt,x+dx)
    if p in left:left.remove(p);seen.add(p);q.append(p)
  out.append(sorted(seen))
 return out

def adj(a,b):return bool(a and b and min(abs(x-y) for x in a for y in b)<=1)

def normalized(r,c,d,H,W):
 return {'south':(r,c),'north':(H-1-r,c),'east':(c,r),'west':(W-1-c,r)}[d]

def original(t,x,d,H,W):
 return {'south':(t,x),'north':(H-1-t,x),'east':(x,t),'west':(x,W-1-t)}[d]

def plateaus(rail,side):
 out=[]
 for t,xs in sorted(rail.items()):
  b=max(xs) if side=='left' else min(xs)
  if out and out[-1]['inner_boundary_x']==b and out[-1]['t_end']+1==t:
   out[-1]['t_end']=t;out[-1]['length']+=1
  else:out.append({'inner_boundary_x':b,'t_start':t,'t_end':t,'length':1})
 return out

def describe_all_interpretations(g,c,d,bg):
 H,W=len(g),len(g[0]);T,X=(H,W) if d in ['north','south'] else(W,H)
 cells=sorted(normalized(r,col,d,H,W) for r in range(H) for col in range(W) if g[r][col]==c);byrow=defaultdict(list)
 for t,x in cells:byrow[t].append(x)
 first,last=min(byrow),max(byrow);rrows={t:runs(byrow.get(t,[])) for t in range(first,last+1)}
 failures=[];completed=[];states=[]
 if len(rrows[first])!=1:failures.append('cap is not one positive-length continuous run')
 if last==first or len(rrows.get(first+1,[]))!=2:failures.append('row immediately after cap does not contain exactly two runs with positive gap')
 if not failures:
  left,right=rrows[first+1]
  if not adj(byrow[first],left) or not adj(byrow[first],right):failures.append('first left/right rail does not touch cap by C8')
  else:states=[{'left':{first+1:left},'right':{first+1:right},'ended':set(),'assignment_trace':[]}]
 for t in range(first+2,last+1):
  rr=rrows[t];nextstates=[]
  for state in states:
   if len(rr)==2:
    if state['ended']:failures.append(f't={t}: disappeared rail would resume')
    elif not all(adj(state[side].get(t-1,[]),rr[j]) for j,side in enumerate(['left','right'])):failures.append(f't={t}: paired runs fail their respective previous-rail C8 connection')
    else:
     ns={'left':dict(state['left']),'right':dict(state['right']),'ended':set(),'assignment_trace':list(state['assignment_trace'])}
     ns['left'][t]=rr[0];ns['right'][t]=rr[1];nextstates.append(ns)
   elif len(rr)==1:
    for side,other in [('left','right'),('right','left')]:
     if side in state['ended']:continue
     reasons=[]
     if not adj(state[side].get(t-1,[]),rr[0]):reasons.append('surviving run lacks previous-row C8 connection')
     if other not in state['ended']:
      previous=state[other].get(t-1,[])
      boundary=(max(previous) if other=='left' else min(previous)) if previous else None
      if boundary!=(0 if other=='left' else X-1):reasons.append('opposite disappearing rail inner boundary is not at its lateral canvas edge')
     if reasons:failures.append(f't={t}: assign lone run to {side}: '+', '.join(reasons));continue
     ns={'left':dict(state['left']),'right':dict(state['right']),'ended':set(state['ended'])|{other},'assignment_trace':list(state['assignment_trace'])+[{'t':t,'lone_run_owner':side,'absent_rail':other}]}
     ns[side][t]=rr[0];nextstates.append(ns)
   else:failures.append(f't={t}: wall row has {len(rr)} runs; zero or more than two is invalid')
  states=nextstates
 for j,state in enumerate(states):
  both=sorted(set(state['left'])&set(state['right']));interior={(t,x) for t in both for x in range(max(state['left'][t])+1,min(state['right'][t]))}
  owned={(first,x) for x in byrow[first]}|{(t,x) for side in ['left','right'] for t,xs in state[side].items() for x in xs}
  local=[]
  if owned!=set(cells):local.append('not all wall cells owned exactly once')
  if len(c8_components(cells))!=1:local.append('wall union is not one C8 component')
  if not interior or len(c4_components(interior))!=1:local.append('observed two-rail interior is not one nonempty C4 component')
  if local:failures.extend(f'complete branch {j}: '+x for x in local);continue
  rails={}
  for side in ['left','right']:
   rs=state[side];end=max(rs);inner=max(rs[end]) if side=='left' else min(rs[end]);pp=plateaus(rs,side)
   rails[side]={'row_run_spans':[[t,min(xs),max(xs)] for t,xs in sorted(rs.items())],'maximal_inner_boundary_plateaus':pp,'terminal_t':end,'terminal_inner_boundary_x':inner,'ends_before_other_rail':end<last,'terminal_inner_boundary_is_own_canvas_edge':inner==(0 if side=='left' else X-1),'no_reappearance':True}
  paints=[]
  for pc in sorted(set(sum(g,[]))):
   if pc==c:continue
   pcs={normalized(r,col,d,H,W) for r in range(H) for col in range(W) if g[r][col]==pc};inside=len(pcs&interior)
   paints.append({'paint_color':pc,'whole_color_cell_count':len(pcs),'inside_both_observed_rails_count':inside,'outside_both_observed_rails_count':len(pcs)-inside,'whole_color_contained':inside==len(pcs),'paint_background_alias_distinct':bg is not None and pc!=bg,'paint_wall_alias_distinct':True,'joint_role_compatible_before_tail':bg is not None and c!=bg and pc!=bg and inside==len(pcs)})
  completed.append({'rail_interpretation_index':len(completed),'lone_run_assignment_trace':state['assignment_trace'],'rails':rails,'observed_two_rail_t_rows':both,'whole_observed_interior_C4_components':1,'whole_observed_interior_cell_count':len(interior),'all_wall_cells_owned_exactly_once':True,'all_distinct_other_color_paint_candidates':paints})
 return {'wall_color':c,'direction':d,'normalized_shape':[T,X],'wall_background_alias_distinct':bg is not None and c!=bg,'alias_failure':'wall equals background' if c==bg else('background is not unique' if bg is None else None),'all_wall_row_run_spans':[[t,[[min(xs),max(xs)] for xs in rrows[t]]] for t in range(first,last+1)],'cap_t':first,'complete_rail_interpretation_count':len(completed),'complete_rail_interpretations':completed,'failed_branch_reasons':sorted(set(failures)),'distinct_other_color_candidates_even_when_geometry_invalid':[{'paint_color':pc,'paint_background_alias_distinct':bg is not None and pc!=bg,'paint_wall_alias_distinct':True} for pc in sorted(set(sum(g,[]))) if pc!=c]}

def valid_grid(grid):
    return(isinstance(grid,list)and 1<=len(grid)<=30 and isinstance(grid[0],list)
           and 1<=len(grid[0])<=30 and all(isinstance(row,list)and len(row)==len(grid[0])
           and all(type(v)is int and 0<=v<=9 for v in row)for row in grid))


def parse_input(grid):
    if not valid_grid(grid):return None,{'failure':'invalid_arc_grid'}
    counts=Counter(v for row in grid for v in row);modes=sorted(v for v,n in counts.items()if n==max(counts.values()))
    record={'input_shape':[len(grid),len(grid[0])],'background_candidates':modes}
    if len(modes)!=1:return None,{**record,'failure':'background_tie'}
    bg=modes[0];candidates=[describe_all_interpretations(grid,colour,direction,bg)for colour in sorted(counts)for direction in DIRECTIONS]
    roles=[];references=[]
    for index,candidate in enumerate(candidates):
        for interpretation in candidate['complete_rail_interpretations']:
            for cue in interpretation['all_distinct_other_color_paint_candidates']:
                if not cue['joint_role_compatible_before_tail']:continue
                roles.append({'background_color':bg,'wall_color':candidate['wall_color'],'direction':candidate['direction'],
                              'rail_interpretation_index':interpretation['rail_interpretation_index'],'paint_color':cue['paint_color']})
                references.append((index,interpretation))
    record.update(background=bg,raw_wall_direction_candidates=candidates,raw_roles=roles,raw_role_count=len(roles))
    if len(roles)!=1:return None,{**record,'failure':'joint_role_not_unique'}
    index,interpretation=references[0];candidate=candidates[index]
    return {**roles[0],'height':len(grid),'width':len(grid[0]),'normalized_shape':candidate['normalized_shape'],
            'cap_t':candidate['cap_t'],'rails':interpretation['rails'],'record':record},record


def terminal_parameters(parsed):
    parameters={};failures=[]
    for side,sign in(('left',-1),('right',1)):
        rail=parsed['rails'][side];last_two=rail['maximal_inner_boundary_plateaus'][-2:]
        if(len(last_two)!=2 or last_two[0]['length']!=last_two[1]['length']
           or last_two[1]['inner_boundary_x']-last_two[0]['inner_boundary_x']!=sign):
            failures.append({'side':side,'last_two':last_two});continue
        parameters[side]={'period':last_two[1]['length'],'terminal_t':rail['terminal_t'],
                          'terminal_inner_boundary_x':rail['terminal_inner_boundary_x'],'outward_sign':sign,
                          'observed':tuple((t,last if side=='left'else first)for t,first,last in rail['row_run_spans'])}
    if failures:return None,{'failure':'terminal_plateau_not_periodic','invalid_rails':failures}
    return parameters,{'terminal_parameters':parameters}


def render(grid):
    parsed,record=parse_input(grid)
    if parsed is None:return None,{**record,'terminal_checked':False}
    parameters,terminal=terminal_parameters(parsed);record={**record,**terminal,'terminal_checked':True}
    if parameters is None:return None,record
    output=[row[:]for row in grid];bg=parsed['background_color'];wall=parsed['wall_color'];paint=parsed['paint_color']
    T,X=parsed['normalized_shape'];H,W=parsed['height'],parsed['width'];direction=parsed['direction'];observed={side:dict(parameters[side]['observed'])for side in parameters}
    shadow=set();painted=[];shadowed_bg=[];encounters=[];domains=[];domain_cells=set()
    for t in range(parsed['cap_t']+1,T):
        bounds={}
        for side in('left','right'):
            item=parameters[side]
            if t<=item['terminal_t']:
                if t not in observed[side]:return None,{**record,'failure':'missing_observed_rail_row'}
                bounds[side]=observed[side][t]
            else:
                q=t-item['terminal_t'];bounds[side]=item['terminal_inner_boundary_x']+item['outward_sign']*(1+(q-1)//item['period'])
        if bounds['left']>=bounds['right']:return None,{**record,'failure':'virtual_boundaries_not_ordered'}
        xs=[x for x in range(X)if bounds['left']<x<bounds['right']];domains.append({'t':t,'left':bounds['left'],'right':bounds['right'],'columns':xs})
        for x in xs:
            r,c=original(t,x,direction,H,W);value=grid[r][c];domain_cells.add((r,c))
            if value==wall:return None,{**record,'failure':'wall_inside_fill_domain'}
            if value not in(bg,paint,wall):
                encounters.append({'original':[r,c],'normalized':[t,x],'colour':value,'already_shadowed':x in shadow});shadow.add(x)
        for x in xs:
            r,c=original(t,x,direction,H,W)
            if grid[r][c]!=bg:continue
            if x in shadow:shadowed_bg.append((r,c))
            else:output[r][c]=paint;painted.append((r,c))
    foreground={(r,c)for r,row in enumerate(grid)for c,v in enumerate(row)if v!=bg}
    if any(output[r][c]!=grid[r][c]for r,c in foreground):return None,{**record,'failure':'original_foreground_changed'}
    actual_changes={(r,c)for r,row in enumerate(grid)for c,v in enumerate(row)if output[r][c]!=v}
    if actual_changes!=set(painted):return None,{**record,'failure':'changed_cell_ownership_failed'}
    before=Counter(v for row in grid for v in row);expected=before.copy();expected[bg]-=len(painted);expected[paint]+=len(painted);after=Counter(v for row in output for v in row)
    if after!=expected:return None,{**record,'failure':'colour_count_invariant_failed'}
    return output,{**record,'failure':None,'domain_rows':domains,'domain_cell_count':len(domain_cells),
                   'painted_bg_cells':sorted(painted),'painted_cell_count':len(painted),'shadowed_bg_cells':sorted(shadowed_bg),
                   'shadowed_bg_count':len(shadowed_bg),'obstacle_encounters':encounters,'shadow_columns':sorted(shadow),
                   'foreground_preserved_count':len(foreground),'background_outside_domain_count':sum(v==bg and(r,c)not in domain_cells for r,row in enumerate(grid)for c,v in enumerate(row)),
                   'before_colour_counts':sorted(before.items()),'after_colour_counts':sorted(after.items()),'output_shape':[H,W]}


def fit_teachers(train):
    if len(train)<2:return False,{'failure':'too_few_teachers','records':[]}
    keys=[tuple(map(tuple,pair['input']))for pair in train]
    if len(set(keys))!=len(keys):return False,{'failure':'duplicate_teacher_input','records':[]}
    records=[];matches=[]
    for pair in train:
        output,record=render(pair['input']);records.append(record);matches.append(output is not None and output==pair['output'])
    return all(matches),{'teacher_matches':matches,'records':records}


class 開口壁教材:
    def __init__(self, 教師群):
        self.適合, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if not self.適合:
            return None, {"failure": "全教師を再現する開口壁充填なし"}
        return render(格子)

    def 記録(self):
        return {"適合": self.適合}
