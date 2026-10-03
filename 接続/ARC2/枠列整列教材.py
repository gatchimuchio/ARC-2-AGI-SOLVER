"""全policy・全区間・全tile保存を証明して元格子だけを同じHDSへ渡す。"""
from __future__ import annotations
from collections import Counter
from .既存枠列整列 import _framed_tile_inventory,_framed_tile_lane_assignments,_framed_tile_group_relinearization_render,_framed_tile_group_relinearization_policy

def valid_grid(grid):
    return(isinstance(grid,list)and 1<=len(grid)<=30 and isinstance(grid[0],list)and 1<=len(grid[0])<=30
           and all(isinstance(row,list)and len(row)==len(grid[0])and all(type(v)is int and 0<=v<=9 for v in row)for row in grid))

def certify_lanes(group,side,n):
    required=[set()for _ in group];edges=[]
    for i,a in enumerate(group):
        for j,b in enumerate(group[i+1:],i+1):
            if max(a['row'],b['row'])>min(a['row']+n-1,b['row']+n-1):continue
            if a['col']==b['col']:return None,{'failure':'same_column_interval_overlap'}
            left,right=(i,j)if a['col']<b['col']else(j,i)
            required[left].add(0 if side=='L'else 1);required[right].add(1 if side=='L'else 0);edges.append([i,j])
    if any(len(values)>1 for values in required):return None,{'failure':'interval_constraints_conflict'}
    lanes=[next(iter(values))if values else 0 for values in required]
    return lanes,{'interval_edges':edges,'isolated_default_indices':[i for i,v in enumerate(required)if not v]}

def guarded_render(grid,policy):
    if not valid_grid(grid):return None,{'failure':'invalid_arc_grid'}
    if not isinstance(policy,dict):return None,{'failure':'missing_policy'}
    shape=policy.get('tile_shape');sides=policy.get('side_by_outer');margin=policy.get('lane_edge_offset')
    if not(isinstance(shape,list)and len(shape)==2 and type(shape[0])is int and shape[0]==shape[1]and 3<=shape[0]<=8 and type(margin)is int and margin>=0 and isinstance(sides,dict)):
        return None,{'failure':'invalid_learned_policy'}
    counts=Counter(v for row in grid for v in row);leaders=[v for v,n in counts.items()if n==max(counts.values())]
    if len(leaders)!=1:return None,{'failure':'background_tie'}
    bg=leaders[0];n=shape[0];h,w=len(grid),len(grid[0]);raw_bg,tiles=_framed_tile_inventory(grid,(n,n))
    if raw_bg is None:return None,{'failure':'original_inventory_unresolved','raw_record':tiles}
    if raw_bg!=bg:return None,{'failure':'background_disagrees'}
    outer_colors=sorted({t['outer_color']for t in tiles})
    if set(sides)!={str(c)for c in outer_colors}or sorted(sides.values())!=['L','R']:return None,{'failure':'learned_side_roles_disagree'}
    source_cells=set();source_counts=Counter()
    for tile in tiles:
        top,left=tile['row'],tile['col'];outer,inner=tile['outer_color'],tile['inner_color']
        own={(top+r,left+c)for r in range(n)for c in range(n)}
        if set(tile['cells'])!=own or source_cells&own:return None,{'failure':'source_tile_ownership_failed'}
        if outer==inner or bg in(outer,inner):return None,{'failure':'invalid_tile_palette'}
        for r in range(n):
            for c in range(n):
                expected=outer if r in(0,n-1)or c in(0,n-1)else inner
                if not(0<=top+r<h and 0<=left+c<w)or grid[top+r][left+c]!=expected:return None,{'failure':'source_tile_pixels_disagree'}
                source_counts[expected]+=1
        source_cells.update(own)
    foreground={(r,c)for r,row in enumerate(grid)for c,v in enumerate(row)if v!=bg}
    if source_cells!=foreground:return None,{'failure':'foreground_coverage_failed'}
    if 4*n+2*margin>w:return None,{'failure':'four_lane_bounds_failed'}
    output=[[bg]*w for _ in range(h)];occupied=set();lane_records=[];group_records=[];destination_writes_changed=0;unmoved=0
    for color in outer_colors:
        side=sides[str(color)];group=sorted([t for t in tiles if t['outer_color']==color],key=lambda t:(t['row'],t['col']))
        lanes,record=certify_lanes(group,side,n)
        if lanes is None:return None,dict(record,outer_color=color)
        if lanes!=_framed_tile_lane_assignments(group,side,n):return None,{'failure':'original_lane_list_disagrees'}
        group_records.append({'outer_color':color,'side':side,**record,'lanes':lanes})
        for tile,lane in zip(group,lanes):
            top,left=tile['row'],tile['col'];target=(margin+lane*n)if side=='L'else(w-n-margin-lane*n)
            dest={(top+r,target+c)for r in range(n)for c in range(n)}
            if any(not(0<=r<h and 0<=c<w)for r,c in dest):return None,{'failure':'destination_out_of_bounds'}
            if occupied&dest:return None,{'failure':'destination_tile_overlap'}
            occupied.update(dest);unmoved+=target==left
            for r in range(n):
                for c in range(n):
                    v=grid[top+r][left+c];output[top+r][target+c]=v;destination_writes_changed+=v!=grid[top+r][target+c]
            lane_records.append({'outer_color':color,'inner_color':tile['inner_color'],'source_anchor':[top,left],'target_anchor':[top,target],'lane':lane})
    if len(occupied)!=len(source_cells)or Counter(v for row in output for v in row)!=counts:return None,{'failure':'tile_colour_conservation_failed'}
    if any(output[r][c]!=v for r,row in enumerate(grid)for c,v in enumerate(row)if(r,c)not in(source_cells|occupied)):return None,{'failure':'outside_cells_changed'}
    raw,raw_record=_framed_tile_group_relinearization_render(grid,policy)
    if raw is None:return None,{'failure':'original_renderer_unresolved','raw_record':raw_record}
    expected_record={'renderer_case':'framed_tile_group_relinearization','framed_tile_relinearization_background':bg,'framed_tile_relinearization_tile_shape':[n,n],'framed_tile_relinearization_event_count':len(tiles),'framed_tile_relinearization_changed_cell_count':destination_writes_changed,'framed_tile_relinearization_lane_records':lane_records,'framed_tile_relinearization_input_shape':[h,w],'framed_tile_relinearization_output_shape':[h,w]}
    if raw!=output or raw_record!=expected_record:return None,{'failure':'original_grid_or_record_disagreement'}
    return raw,{'raw_record':raw_record,'groups':group_records,'processed_tiles':len(tiles),'unmoved_tiles':unmoved,'foreground_pixels':len(source_cells),'destination_writes_changed':destination_writes_changed,'whole_grid_changed_cells':sum(a!=b for x,y in zip(grid,raw)for a,b in zip(x,y)),'foreground_colour_counts':[[c,v]for c,v in sorted(source_counts.items())]}

def fit_teachers(teachers):
    if len(teachers)<2 or any(not valid_grid(p['input'])or not valid_grid(p['output'])for p in teachers):return None,{'failure':'insufficient_or_invalid_teachers'}
    if len({tuple(map(tuple,p['input']))for p in teachers})!=len(teachers):return None,{'failure':'duplicate_teacher_inputs'}
    candidates=[];attempts=[]
    for size in range(3,9):
        policy=_framed_tile_group_relinearization_policy(teachers,(size,size));attempt={'size':size,'policy':policy}
        if policy is not None:
            raw=[_framed_tile_group_relinearization_render(p['input'],policy)for p in teachers]
            attempt['raw_pair_fits']=[o is not None and o==p['output']for(o,r),p in zip(raw,teachers)];attempt['raw_records']=[r for o,r in raw]
            if all(attempt['raw_pair_fits']):candidates.append(policy)
        attempts.append(attempt)
    record={'raw_policy_count':len(candidates),'attempts':attempts}
    if len(candidates)!=1:return None,dict(record,failure='raw_teacher_policy_not_unique')
    policy=candidates[0];guarded=[guarded_render(p['input'],policy)for p in teachers];record['teacher_records']=[r for o,r in guarded]
    if any(o is None or o!=p['output']for(o,r),p in zip(guarded,teachers)):return None,dict(record,failure='teacher_certificate_failed')
    return policy,record

class 枠列整列教材:
    def __init__(self, 教師群):
        self.規約, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if self.規約 is None:
            return None, {"failure": "全教師を再現する枠tile整列なし"}
        return guarded_render(格子, self.規約)

    def 記録(self):
        return {"全教師共有枠列規約": self.規約}
