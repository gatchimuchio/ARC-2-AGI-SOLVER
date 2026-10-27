"""全pixel所有と旧格子・全文記録を証明する軸投射教材。"""
from __future__ import annotations
from collections import Counter
from . import 既存軸投射 as source

def valid_grid(grid):
    return (isinstance(grid,list)and 1<=len(grid)<=30 and isinstance(grid[0],list)
            and 1<=len(grid[0])<=30 and all(isinstance(row,list)and len(row)==len(grid[0])
            and all(type(v)is int and 0<=v<=9 for v in row)for row in grid))

def guarded_render(grid):
    if not valid_grid(grid):return None,{'failure':'invalid_grid'}
    raw,old_record=source.render_edge_marker_axis_projection(grid)
    if raw is None:return None,{'failure':'original_renderer_failed','original':old_record}
    roles,role_failure=source.infer_edge_marker_axis_roles(grid)
    if roles is None:return None,{'failure':'original_roles_failed','original':old_record,'roles':role_failure}
    base={'original':old_record}
    counts=Counter(v for row in grid for v in row);mode=max(counts.values())
    if sum(n==mode for n in counts.values())!=1:return None,{**base,'failure':'background_tie'}
    background=roles['background'];marker=roles['marker_color'];colour=roles['object_color']
    height,width=len(grid),len(grid[0]);vcol=roles['vertical_axis_col'];hrow=roles['horizontal_axis_row']
    vside=roles['vertical_marker_side'];hside=roles['horizontal_marker_side']
    objects={(r,c)for r,row in enumerate(grid)for c,v in enumerate(row)if v==colour}
    markers={(r,c)for r,row in enumerate(grid)for c,v in enumerate(row)if v==marker}
    if (len({background,marker,colour})!=3 or set(counts)!={background,marker,colour}
            or objects!=set(roles['object_cells'])or len(markers)!=roles['marker_cell_count']):
        return None,{**base,'failure':'input_role_coverage_failed'}
    if any(r in(0,height-1)or c in(0,width-1)for r,c in objects):
        return None,{**base,'failure':'object_boundary_contact'}
    axis={(r,c)for r,c in objects if(vcol is not None and c==vcol)or(hrow is not None and r==hrow)}
    segments=set();witnesses={}
    if vcol is not None:
        positions=sorted(r for r,c in objects if c==vcol)
        if not positions:return None,{**base,'failure':'vertical_axis_without_object_witness'}
        witnesses['vertical']=positions
        span=range(0,positions[-1]+1)if vside=='top'else range(positions[0],height)
        segments.update((r,vcol)for r in span)
    if hrow is not None:
        positions=sorted(c for r,c in objects if r==hrow)
        if not positions:return None,{**base,'failure':'horizontal_axis_without_object_witness'}
        witnesses['horizontal']=positions
        span=range(0,positions[-1]+1)if hside=='left'else range(positions[0],width)
        segments.update((hrow,c)for c in span)
    if not markers.issubset(segments)or not axis.issubset(segments):
        return None,{**base,'failure':'axis_ownership_failed'}
    groups={};erased=set()
    for r,c in sorted(objects-axis):
        side_r=('top'if r<hrow else'bottom')if hrow is not None else vside
        side_c=('left'if c<vcol else'right')if vcol is not None else hside
        if vcol is not None and hrow is not None and side_r!=vside and side_c!=hside:
            erased.add((r,c))
        else:groups.setdefault((side_r,side_c),set()).add((r,c))
    owned=set(axis)|erased
    for cells in groups.values():
        if owned&cells:return None,{**base,'failure':'source_partition_overlap'}
        owned.update(cells)
    if owned!=objects:return None,{**base,'failure':'source_partition_incomplete'}
    projected=set();group_records=[];proof_groups=[]
    for key,cells in sorted(groups.items(),key=lambda item:(str(item[0][0]),str(item[0][1]))):
        side_r,side_c=key
        r0=min(r for r,c in cells);r1=max(r for r,c in cells);c0=min(c for r,c in cells);c1=max(c for r,c in cells)
        dr=-r0 if side_r=='top'else height-1-r1 if side_r=='bottom'else 0
        dc=-c0 if side_c=='left'else width-1-c1 if side_c=='right'else 0
        destinations={(r+dr,c+dc)for r,c in cells}
        if len(destinations)!=len(cells):return None,{**base,'failure':'group_translation_not_injective'}
        if any(not(0<=r<height and 0<=c<width)for r,c in destinations):
            return None,{**base,'failure':'projected_cell_out_of_bounds'}
        if any((vcol is not None and ((c<vcol)!=(side_c=='left')or c==vcol))
               or(hrow is not None and ((r<hrow)!=(side_r=='top')or r==hrow))for r,c in destinations):
            return None,{**base,'failure':'projected_cell_leaves_halfplane'}
        if destinations&projected or destinations&segments:
            return None,{**base,'failure':'destination_ownership_overlap'}
        projected.update(destinations)
        group_records.append({'row_side':side_r,'col_side':side_c,'source_bbox':[r0,c0,r1,c1],'cell_count':len(cells)})
        proof_groups.append({'sides':[side_r,side_c],'source_cells':[list(p)for p in sorted(cells)],
                             'shift':[dr,dc],'destinations':[list(p)for p in sorted(destinations)]})
    output_objects=projected|axis
    if len(output_objects)!=len(objects)-len(erased):return None,{**base,'failure':'retained_object_count_failed'}
    expected=[[background]*width for _ in range(height)]
    for r,c in segments:expected[r][c]=marker
    for r,c in output_objects:expected[r][c]=colour
    expected_record={'renderer_case':'edge_marker_axis_projection','background':background,'axis_marker_color':marker,
        'axis_object_color':colour,'vertical_axis_col':vcol,'vertical_marker_side':vside,
        'horizontal_axis_row':hrow,'horizontal_marker_side':hside,
        'object_bbox':[min(r for r,c in objects),min(c for r,c in objects),max(r for r,c in objects),max(c for r,c in objects)],
        'axis_segment_cell_count':len(segments),'axis_projected_cell_count':len(output_objects),
        'axis_projection_group_count':len(groups),'axis_skipped_cell_count':len(erased),'projection_groups':group_records}
    if raw!=expected:return None,{**base,'failure':'original_grid_disagrees'}
    if old_record!=expected_record:return None,{**base,'failure':'original_record_disagrees'}
    output_counts=Counter(v for row in raw for v in row)
    if output_counts[colour]!=len(output_objects)or output_counts[marker]!=len(segments-axis):
        return None,{**base,'failure':'output_colour_count_failed'}
    return raw,{**base,'certificate':{'input_object_count':len(objects),'original_axis_cells':[list(p)for p in sorted(axis)],
        'erased_cells':[list(p)for p in sorted(erased)],'groups':proof_groups,'axis_witnesses':witnesses,
        'axis_segment_cells':[list(p)for p in sorted(segments)],'actual_marker_cells':len(segments-axis),
        'output_object_count':len(output_objects),'output_colour_counts':[[v,n]for v,n in sorted(output_counts.items())]}}

def fit_teachers(train):
    if not isinstance(train,list)or len(train)<2:return None,{'failure':'too_few_teachers'}
    if any(not isinstance(pair,dict)or not valid_grid(pair.get('input'))or not valid_grid(pair.get('output'))for pair in train):
        return None,{'failure':'invalid_teachers'}
    keys=[tuple(map(tuple,pair['input']))for pair in train]
    if len(set(keys))!=len(keys):return None,{'failure':'duplicate_teacher_inputs'}
    originals=[]
    for pair in train:
        raw,record=source.render_edge_marker_axis_projection(pair['input'])
        originals.append({'exact':raw==pair['output'],'record':record})
    if not all(r['exact']for r in originals):return None,{'failure':'original_teacher_mismatch','original_records':originals}
    records=[]
    for pair in train:
        output,record=guarded_render(pair['input']);records.append({'exact':output==pair['output'],'record':record})
    if not all(r['exact']for r in records):return None,{'failure':'proof_teacher_mismatch','original_records':originals,'teacher_records':records}
    return {'renderer':'edge_axis_projection'},{'original_records':originals,'teacher_records':records}

class 軸投射教材:
    def __init__(self, 教師群):
        model, _ = fit_teachers(教師群)
        self.適合 = model is not None

    def 候補(self, 格子, _policy):
        if not self.適合:
            return None, {"failure": "全教師を再現する軸投射なし"}
        return guarded_render(格子)

    def 記録(self):
        return {"全教師の軸投射再現": self.適合}
