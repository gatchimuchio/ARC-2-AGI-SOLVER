"""全raw役割と全配置を証明し、元格子だけを同じHDSへ渡す。"""
from __future__ import annotations
from collections import Counter,defaultdict
import math
from .既存基点複製 import color_components,component_shape,render_anchored_singleton_motif_tiler

def valid_grid(grid):
    return(isinstance(grid,list)and 1<=len(grid)<=30 and isinstance(grid[0],list)and 1<=len(grid[0])<=30
           and all(isinstance(row,list)and len(row)==len(grid[0])and all(type(v)is int and 0<=v<=9 for v in row)for row in grid))

def raw_roles(grid,background):
    colors=sorted({v for row in grid for v in row if v!=background})
    components={c:color_components(grid,c,include_diagonal=True)for c in colors};roles=[]
    for source in colors:
        motifs=[c for c in components[source]if c['size']>1];anchors=[c for c in components[source]if c['size']==1]
        if len(motifs)!=1 or len(anchors)!=1:continue
        for marker in colors:
            if marker==source or not components[marker]or any(c['size']!=1 for c in components[marker]):continue
            roles.append({'source_color':source,'marker_color':marker,'motif':motifs[0],
                          'anchor':next(iter(anchors[0]['cells'])),
                          'marker_cells':sorted(next(iter(c['cells']))for c in components[marker])})
    return roles

def guarded_render(grid):
    if not valid_grid(grid):return None,{'failure':'invalid_arc_grid'}
    counts=Counter(v for row in grid for v in row);leaders=[v for v,n in counts.items()if n==max(counts.values())]
    if len(leaders)!=1:return None,{'failure':'background_tie'}
    bg=leaders[0];roles=raw_roles(grid,bg)
    if len(roles)!=1:return None,{'failure':'raw_role_count_not_one','raw_role_count':len(roles)}
    role=roles[0];source,marker=role['source_color'],role['marker_color'];motif=role['motif'];anchor=tuple(role['anchor']);markers=[tuple(p)for p in role['marker_cells']];own=set(map(tuple,motif['cells']));instructions={anchor}|set(markers)
    foreground={(r,c)for r,row in enumerate(grid)for c,v in enumerate(row)if v!=bg}
    if set(counts)!={bg,source,marker}or own&instructions or own|instructions!=foreground:
        return None,{'failure':'foreground_role_coverage_failed'}
    if len(set(markers))!=len(markers)or anchor in markers:return None,{'failure':'layout_points_not_distinct'}
    h,w=len(grid),len(grid[0]);r0,c0,r1,c1=motif['bbox'];th,tw=component_shape(motif)
    mask={(r-r0,c-c0)for r,c in own};deltas=[(r-anchor[0],c-anchor[1])for r,c in markers]
    raw_steps=[math.gcd(*(abs(d[i])for d in deltas))for i in range(2)];steps=[v or 1 for v in raw_steps]
    normalized=[]
    for dr,dc in deltas:
        if dr%steps[0]or dc%steps[1]:return None,{'failure':'noninteger_normalized_coordinate'}
        normalized.append((dr//steps[0],dc//steps[1]))
    if len(set(normalized))!=len(normalized)or(0,0)in normalized:return None,{'failure':'normalized_points_not_distinct'}
    origins=[(r0,c0)]+[(r0+nr*th,c0+nc*tw)for nr,nc in normalized];occupied_boxes=set();proposals=defaultdict(set)
    for index,(top,left)in enumerate(origins):
        if top<0 or left<0 or top+th>h or left+tw>w:
            return None,{'failure':'projected_bbox_out_of_bounds','placement_index':index,'origin':[top,left]}
        box={(r,c)for r in range(top,top+th)for c in range(left,left+tw)}
        if occupied_boxes&box:return None,{'failure':'projected_bbox_overlap'}
        occupied_boxes.update(box);color=marker if index==0 else source
        for dr,dc in mask:proposals[(top+dr,left+dc)].add(color)
    conflicts=[(p,sorted(v))for p,v in sorted(proposals.items())if len(v)>1]
    if conflicts:return None,{'failure':'simultaneous_colour_conflict','conflicts':conflicts}
    expected=[[bg]*w for _ in range(h)]
    for(r,c),values in proposals.items():expected[r][c]=next(iter(values))
    output_counts=Counter(v for row in expected for v in row)
    if output_counts[source]!=len(markers)*len(own)or output_counts[marker]!=len(own):return None,{'failure':'motif_colour_multiplicity_failed'}
    raw,raw_record=render_anchored_singleton_motif_tiler(grid)
    if raw is None:return None,{'failure':'original_renderer_unresolved','raw_record':raw_record}
    expected_record={'renderer_case':'anchored_singleton_motif_tiler','background':bg,'anchored_source_color':source,
        'anchored_marker_color':marker,'anchored_source_bbox':list(motif['bbox']),'anchored_anchor_cell':list(anchor),
        'anchored_motif_shape':[th,tw],'anchored_row_step':steps[0],'anchored_col_step':steps[1],
        'anchored_marker_count':len(markers),'anchored_placement_count':len(markers),'anchored_placements':[list(p)for p in origins[1:]]}
    if raw!=expected or raw_record!=expected_record:return None,{'failure':'original_grid_or_record_disagreement'}
    return raw,{'raw_record':raw_record,'raw_role_count':len(roles),'input_foreground_pixels':len(foreground),
        'motif_pixels':len(own),'instruction_point_count':len(instructions),'normalized_marker_coordinates':[list(p)for p in normalized],
        'zero_axes':[i for i,v in enumerate(raw_steps)if v==0],'projected_bbox_count':len(origins),
        'source_output_pixels':output_counts[source],'marker_output_pixels':output_counts[marker],
        'instruction_cells_now_background':sum(raw[r][c]==bg for r,c in instructions)}

def fit_teachers(teachers):
    if len(teachers)<2 or any(not valid_grid(p['input'])or not valid_grid(p['output'])for p in teachers):
        return False,{'failure':'insufficient_or_invalid_teachers'}
    if len({tuple(map(tuple,p['input']))for p in teachers})!=len(teachers):return False,{'failure':'duplicate_teacher_inputs'}
    raw=[render_anchored_singleton_motif_tiler(p['input'])for p in teachers]
    record={'raw_pair_fits':[out is not None and out==p['output']for(out,_),p in zip(raw,teachers)],'raw_records':[r for _,r in raw]}
    if not all(record['raw_pair_fits']):return False,dict(record,failure='original_teacher_reproduction_failed')
    guarded=[guarded_render(p['input'])for p in teachers];record['teacher_records']=[r for _,r in guarded]
    if any(out is None or out!=p['output']for(out,_),p in zip(guarded,teachers)):
        return False,dict(record,failure='teacher_certificate_failed')
    return True,record

class 基点複製教材:
    def __init__(self, 教師群):
        self.適合, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if not self.適合:
            return None, {"failure": "全教師を再現する基点motif展開なし"}
        return guarded_render(格子)

    def 記録(self):
        return {"全教師共通基点展開": self.適合}
