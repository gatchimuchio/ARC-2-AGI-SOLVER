"""New teacher-authorized static comb placement and pin interval clipping."""
from collections import Counter
from .既存順位着色 import same_color_components_4

INWARD=((1,0),(0,-1),(-1,0),(0,1))

def valid_grid(grid):
    return(isinstance(grid,list)and 1<=len(grid)<=30 and isinstance(grid[0],list)and 1<=len(grid[0])<=30
           and all(isinstance(row,list)and len(row)==len(grid[0])and all(type(v)is int and 0<=v<=9 for v in row)for row in grid))

def raw_frames(grid,background):
    frames=[]
    for colour in sorted({v for row in grid for v in row}-{background}):
        for original in same_color_components_4(grid,colour):
            cells=set(original);r0=min(r for r,c in cells);r1=max(r for r,c in cells);c0=min(c for r,c in cells);c1=max(c for r,c in cells)
            if r1-r0<2 or c1-c0<2:continue
            sides=[{(r0,c)for c in range(c0,c1+1)},{(r,c1)for r in range(r0,r1+1)},{(r1,c)for c in range(c0,c1+1)},{(r,c0)for r in range(r0,r1+1)}]
            missing=[side-cells for side in sides];incomplete=[i for i,part in enumerate(missing)if part]
            if len(incomplete)!=1:continue
            side=incomplete[0];gap=sorted(missing[side]);axis=[p[1]if side%2==0 else p[0]for p in gap]
            if axis!=list(range(min(axis),max(axis)+1)):continue
            if any(r in(r0,r1)and c in(c0,c1)for r,c in gap):continue
            frames.append({'colour':colour,'bbox':[r0,c0,r1,c1],'open_side':side,'gap':gap,'cells':sorted(cells)})
    return frames

def input_role(grid,background,frame,tooth_direction):
    colour=frame['colour'];r0,c0,r1,c1=frame['bbox'];a=INWARD[frame['open_side']];b=tooth_direction
    corners=[(r,c)for r in(r0,r1)for c in(c0,c1)]
    umin=min(r*a[0]+c*a[1]for r,c in corners);umax=max(r*a[0]+c*a[1]for r,c in corners)
    vmin=min(r*b[0]+c*b[1]for r,c in corners);vmax=max(r*b[0]+c*b[1]for r,c in corners)
    foreground={(r,c)for r,row in enumerate(grid)for c,v in enumerate(row)if v!=background}
    other={p for p in foreground if grid[p[0]][p[1]]!=colour}
    if not other or any(not(r0<r<r1 and c0<c<c1)for r,c in other):return None,'coloured_content_not_all_inside'
    if any(grid[r][c]!=background for r,c in frame['gap']):return None,'opening_not_background'
    source={p for p in foreground if not(r0<=p[0]<=r1 and c0<=p[1]<=c1)}
    if not source or any(grid[r][c]!=colour for r,c in source):return None,'outside_not_base_source'
    components=same_color_components_4(grid,colour)
    if sum(set(part)==source for part in components)!=1:return None,'source_not_whole_component'
    if any(r*a[0]+c*a[1]>=umin for r,c in source):return None,'source_not_open_side_exterior'
    uv={(r*a[0]+c*a[1],r*b[0]+c*b[1])for r,c in source}
    low=min(v for u,v in uv);left=min(u for u,v in uv);right=max(u for u,v in uv)
    baseline={(u,low)for u in range(left,right+1)}
    if not baseline<=uv:return None,'source_baseline_incomplete'
    teeth=[]
    for u in range(left,right+1):
        vs=sorted(v for col,v in uv if col==u)
        if vs!=list(range(low,max(vs)+1)):return None,'source_tooth_not_contiguous'
        if len(vs)>1:teeth.append({'u':u,'top':max(vs),'height':len(vs)-1})
    if not teeth or any(y['u']-x['u']<=1 for x,y in zip(teeth,teeth[1:])):return None,'source_teeth_unresolved'
    gap_min=min(r*b[0]+c*b[1]for r,c in frame['gap'])
    if low!=gap_min:return None,'baseline_gap_misaligned'
    pins=[];stems=set();pin_cells=set();pin_columns=set()
    for pin_colour in sorted({grid[r][c]for r,c in other}):
        for part in same_color_components_4(grid,pin_colour):
            cells=set(part)
            us={r*a[0]+c*a[1]for r,c in cells};vs=sorted(r*b[0]+c*b[1]for r,c in cells)
            if len(us)!=1 or vs!=list(range(min(vs),max(vs)+1)):return None,'pin_not_contiguous_line'
            u=next(iter(us))
            if u in pin_columns:return None,'several_pins_on_one_column'
            pin_columns.add(u)
            stem={(u*a[0]+v*b[0],u*a[1]+v*b[1])for v in range(max(vs)+1,vmax)}
            if any(grid[r][c]!=colour for r,c in stem):return None,'pin_stem_not_complete'
            pins.append({'colour':pin_colour,'u':u,'low':min(vs),'high':max(vs),'cells':cells,'stem':stem})
            stems|=stem;pin_cells|=cells
    inside_base={(r,c)for r in range(r0+1,r1)for c in range(c0+1,c1)if grid[r][c]==colour}
    if inside_base!=stems:return None,'interior_base_not_all_stems'
    boundary={(r,c)for r in range(r0,r1+1)for c in range(c0,c1+1)if r in(r0,r1)or c in(c0,c1)}-set(map(tuple,frame['gap']))
    if source|boundary|stems|pin_cells!=foreground:return None,'foreground_role_coverage_failed'
    pins.sort(key=lambda x:x['u'])
    return {'background':background,'frame':frame,'a':a,'b':b,'umin':umin,'umax':umax,'vmin':vmin,'vmax':vmax,'source':source,'baseline_v':low,'teeth':teeth,'pins':pins,'pin_cells':pin_cells,'stems':stems,'boundary':boundary},None

def parse_input(grid):
    if not valid_grid(grid):return None,{'failure':'invalid_arc_grid'}
    counts=Counter(v for row in grid for v in row);modes=sorted(v for v,n in counts.items()if n==max(counts.values()))
    if len(modes)!=1:return None,{'failure':'background_mode_tie','candidates':modes}
    background=modes[0];raw=raw_frames(grid,background);roles=[];attempts=[]
    for i,frame in enumerate(raw):
        ar,ac=INWARD[frame['open_side']]
        for b in((-ac,ar),(ac,-ar)):
            role,failure=input_role(grid,background,frame,b)
            attempts.append({'raw_frame_index':i,'tooth_direction':b,'failure':failure})
            if role is not None:roles.append(role)
    record={'background':background,'raw_frames':raw,'role_attempts':attempts,'input_role_count':len(roles)}
    if len(roles)!=1:return None,dict(record,failure='joint_input_role_not_unique')
    role=roles[0]
    record['role']={'frame_bbox':role['frame']['bbox'],'frame_colour':role['frame']['colour'],'inward':role['a'],'tooth_direction':role['b'],'source_cells':sorted(role['source']),'baseline_v':role['baseline_v'],'teeth':role['teeth'],'pins':[dict(pin,cells=sorted(pin['cells']),stem=sorted(pin['stem']))for pin in role['pins']],'frame_boundary':sorted(role['boundary']),'stems':sorted(role['stems'])}
    role['record']=record
    return role,record

def render_parsed(grid,role):
    record={'parse':role['record']};teeth=role['teeth'];pins=role['pins'];a=role['a'];b=role['b'];base=role['frame']['colour']
    if len(teeth)!=len(pins):return None,dict(record,failure='all_teeth_pins_count_mismatch')
    shifts={pin['u']-tooth['u']for pin,tooth in zip(pins,teeth)}
    if len(shifts)!=1:return None,dict(record,failure='tooth_pin_translation_not_shared')
    shift=next(iter(shifts));target={(r+shift*a[0],c+shift*a[1])for r,c in role['source']}
    r0,c0,r1,c1=role['frame']['bbox']
    if any(not(r0<r<r1 and c0<c<c1)for r,c in target):return None,dict(record,failure='whole_comb_target_outside_frame')
    if any(grid[r][c]==base for r,c in target):return None,dict(record,failure='comb_target_hits_original_base')
    if any(grid[r][c]!=role['background']and(r,c)not in role['pin_cells']for r,c in target):return None,dict(record,failure='comb_target_unowned_stationary_overlap')
    paint={};moves=[];clipped=Counter();kept=Counter()
    for pin,tooth in zip(pins,teeth):
        advance=max(0,tooth['top']+1-pin['low']);translated={(r+advance*b[0],c+advance*b[1])for r,c in pin['cells']}
        visible={p for p in translated if r0<p[0]<r1 and c0<p[1]<c1};lost=translated-visible
        if any(r*b[0]+c*b[1]<role['vmax']for r,c in lost):return None,dict(record,failure='pin_clip_not_at_ceiling')
        if visible&target or any(p in paint for p in visible):return None,dict(record,failure='simultaneous_proposal_conflict')
        if any(grid[r][c]!=role['background']and(r,c)not in(pin['cells']|pin['stem'])for r,c in visible):return None,dict(record,failure='pin_overwrites_another_owner')
        paint.update({p:pin['colour']for p in visible});kept[pin['colour']]+=len(visible);clipped[pin['colour']]+=len(lost)
        moves.append({'colour':pin['colour'],'u':pin['u'],'tooth_top':tooth['top'],'advance':advance,'source':sorted(pin['cells']),'translated':sorted(translated),'visible':sorted(visible),'clipped':sorted(lost)})
    stem_overwritten=set(paint)&role['stems']
    out=[row[:]for row in grid]
    for r,c in role['source']|role['pin_cells']:out[r][c]=role['background']
    for r,c in target:out[r][c]=base
    for(r,c),colour in paint.items():out[r][c]=colour
    after=Counter(v for row in out for v in row);before=Counter(v for row in grid for v in row)
    if any(after[c]!=n for c,n in kept.items()):return None,dict(record,failure='pin_visible_colour_count_failed')
    for c in {p['colour']for p in pins}:
        if after[c]!=kept[c]or before[c]!=kept[c]+clipped[c]:return None,dict(record,failure='pin_retained_clipped_coverage_failed')
    if after[base]!=before[base]-len(stem_overwritten):return None,dict(record,failure='base_colour_count_failed')
    owned=role['source']|role['pin_cells']|target|set(paint)
    if any(out[r][c]!=grid[r][c]for r,row in enumerate(grid)for c in range(len(row))if(r,c)not in owned):return None,dict(record,failure='unaffected_cell_changed')
    if any(out[r][c]!=grid[r][c]for r,c in role['boundary']|set(map(tuple,role['frame']['gap']))):return None,dict(record,failure='frame_or_opening_changed')
    return out,dict(record,translation=[shift*a[0],shift*a[1]],comb_source_cells=len(role['source']),comb_target_cells=len(target),target=sorted(target),pin_moves=moves,pin_count=len(pins),pin_source_cells=len(role['pin_cells']),pin_visible_cells=len(paint),pin_clipped_cells=sum(clipped.values()),stem_overwritten_cells=sorted(stem_overwritten),before_colour_counts=sorted(before.items()),after_colour_counts=sorted(after.items()),protected_cells=len(grid)*len(grid[0])-len(owned),changed_cells=sum(out[r][c]!=grid[r][c]for r,row in enumerate(grid)for c in range(len(row))))

def render(grid):
    role,record=parse_input(grid)
    if role is None:return None,record
    return render_parsed(grid,role)

def fit_teachers(teachers):
    if len(teachers)<2 or any(not valid_grid(p['input'])or not valid_grid(p['output'])for p in teachers):return False,{'failure':'insufficient_or_invalid_teachers'}
    if len({tuple(map(tuple,p['input']))for p in teachers})!=len(teachers):return False,{'failure':'duplicate_teacher_inputs'}
    attempts=[render(p['input'])for p in teachers];fits=[out is not None and out==p['output']for(out,_),p in zip(attempts,teachers)]
    record={'pair_fits':fits,'teacher_records':[r for out,r in attempts]}
    return all(fits),record if all(fits)else dict(record,failure='teacher_reproduction_failed')


class 櫛配置教材:
    def __init__(self, 教師群):
        self.適合, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if not self.適合:
            return None, {"failure": "全教師を再現する櫛配置押上げなし"}
        return render(格子)

    def 記録(self):
        return {"適合": self.適合}
