"""全成分の移動・元component別gapを証明して、元出力を同じHDSへ渡す。"""
from __future__ import annotations
from collections import Counter
from .既存区切投射 import (infer_separator_projection_policy, render_separator_aligned_zero_projection,
    full_height_color_columns, color_components, separator_projection_component_record)

def valid_grid(grid):
    return (isinstance(grid,list)and 1<=len(grid)<=30 and isinstance(grid[0],list)
            and 1<=len(grid[0])<=30 and all(isinstance(row,list)and len(row)==len(grid[0])
            and all(type(v)is int and 0<=v<=9 for v in row)for row in grid))

def guarded_render(grid,policy):
    if not valid_grid(grid):return None,{'failure':'invalid_arc_grid'}
    if set(policy)!={'separator_color','movable_color','target_color'} or any(type(v)is not int or not 0<=v<=9 for v in policy.values()) or len(set(policy.values()))!=3:
        return None,{'failure':'invalid_roles'}
    counts=Counter(v for row in grid for v in row);leaders=[c for c,n in counts.items()if n==max(counts.values())]
    if len(leaders)!=1:return None,{'failure':'background_tie'}
    background=leaders[0];separator=policy['separator_color'];movable=policy['movable_color'];target=policy['target_color']
    if background in policy.values()or set(counts)!={background,separator,movable}:
        return None,{'failure':'input_role_palette_violation','background':background,'palette':sorted(counts)}
    columns=[c for c in full_height_color_columns(grid)if c['color']!=background]
    if len(columns)!=1 or columns[0]['color']!=separator:
        return None,{'failure':'raw_separator_not_unique','columns':columns}
    col=columns[0]['col'];height,width=len(grid),len(grid[0])
    if not 0<col<width-1:return None,{'failure':'separator_not_internal','column':col}
    components=color_components(grid,movable)
    if not components or any(c['bbox'][3]>=col for c in components):
        return None,{'failure':'all_movable_components_must_be_left'}
    source=set().union(*(c['cells']for c in components));expected=[row[:]for row in grid]
    for r,c in source:expected[r][c]=background
    moved=set();projection_rows=set();component_records=[];proof_components=[]
    for component in components:
        shift=col-1-component['bbox'][3];cells={(r,c+shift)for r,c in component['cells']}
        if shift<0 or any(not(0<=r<height and 0<=c<col)for r,c in cells):
            return None,{'failure':'translation_out_of_bounds'}
        if len(cells)!=component['size'] or moved&cells:
            return None,{'failure':'component_pixel_collision'}
        if any(expected[r][c]not in (background,movable)for r,c in cells):
            return None,{'failure':'translation_protected_collision'}
        moved.update(cells);rows=[]
        for r in sorted({r for r,c in cells}):
            cols=sorted(c for rr,c in cells if rr==r)
            if col-1 in cols and cols!=list(range(cols[0],col)):
                rows.append(r);projection_rows.add(r)
        component_records.append(separator_projection_component_record(component,shift))
        proof_components.append({'input_size':component['size'],'shift':shift,'moved_cells':sorted(cells),'gap_rows':rows})
    for r,c in moved:expected[r][c]=movable
    projections={(r,c)for r in projection_rows for c in range(col+1,width)}
    if any(expected[r][c]not in(background,target)for r,c in projections):
        return None,{'failure':'projection_protected_collision'}
    for r,c in projections:expected[r][c]=target
    if len(moved)!=len(source)or sum(v==movable for row in expected for v in row)!=len(source):
        return None,{'failure':'movable_pixel_count_changed'}
    operations=source|moved|projections
    if any(expected[r][col]!=grid[r][col]for r in range(height)):
        return None,{'failure':'separator_changed'}
    if any(expected[r][c]!=grid[r][c]for r in range(height)for c in range(width)if(r,c)not in operations):
        return None,{'failure':'outside_operation_changed'}
    raw,raw_record=render_separator_aligned_zero_projection(grid,**policy)
    expected_record={'renderer_case':'separator_aligned_zero_projection','background':background,'separator_color':separator,'separator_col':col,
                     'movable_color':movable,'target_color':target,'component_records':component_records,
                     'moved_cell_count':len(moved),'projection_row_count':len(projection_rows)}
    if raw is None:return None,{'failure':'original_renderer_unresolved','raw_record':raw_record}
    if raw!=expected or raw_record!=expected_record:return None,{'failure':'source_output_or_record_disagreement'}
    return raw,{'raw_record':raw_record,'components':proof_components,'source_pixels':len(source),'moved_pixels':len(moved),
                'projection_rows':sorted(projection_rows),'projection_cells':len(projections),'preserved_outside_operations':height*width-len(operations),
                'changed_pixels':sum(a!=b for ar,br in zip(grid,raw)for a,b in zip(ar,br))}

def fit_teachers(teachers):
    if len(teachers)<2 or any(not valid_grid(p['input'])or not valid_grid(p['output'])for p in teachers):
        return None,{'failure':'insufficient_or_invalid_teachers'}
    if len({tuple(map(tuple,p['input']))for p in teachers})!=len(teachers):return None,{'failure':'duplicate_teacher_inputs'}
    policy,role_record=infer_separator_projection_policy(teachers)
    record={'raw_policy':policy,'role_record':role_record}
    if policy is None:return None,dict(record,failure='raw_roles_unresolved')
    raw=[render_separator_aligned_zero_projection(p['input'],**policy)for p in teachers]
    record['raw_records']=[r for _,r in raw];record['raw_pair_fits']=[out is not None and out==p['output']for(out,_),p in zip(raw,teachers)]
    if not all(record['raw_pair_fits']):return None,dict(record,failure='raw_teacher_reproduction_failed')
    checked=[guarded_render(p['input'],policy)for p in teachers];record['teacher_records']=[r for _,r in checked]
    if any(out is None or out!=p['output']for(out,_),p in zip(checked,teachers)):
        return None,dict(record,failure='teacher_certificate_failed')
    return policy,record

class 区切投射教材:
    def __init__(self, 教師群):
        self.役割, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if self.役割 is None:
            return None, {"failure": "全教師を再現する区切投射役割なし"}
        return guarded_render(格子, self.役割)

    def 記録(self):
        return {"全教師共通役割": self.役割}
