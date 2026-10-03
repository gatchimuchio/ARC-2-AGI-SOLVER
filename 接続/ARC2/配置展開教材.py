"""全component所有と全block対応を証明し元格子を同じHDSへ渡す。"""
from __future__ import annotations
from collections import Counter
from .既存配置展開 import foreground_mixed_components,crop_bbox,render_layout_mask_macro_tile_expander

def valid_grid(grid):
    return(isinstance(grid,list)and 1<=len(grid)<=30 and isinstance(grid[0],list)and 1<=len(grid[0])<=30
           and all(isinstance(row,list)and len(row)==len(grid[0])and all(type(v)is int and 0<=v<=9 for v in row)for row in grid))

def guarded_render(grid):
    if not valid_grid(grid):return None,{'failure':'invalid_arc_grid'}
    raw,raw_record=render_layout_mask_macro_tile_expander(grid)
    if raw is None:return None,{'failure':'original_renderer_unresolved','raw_record':raw_record}
    counts=Counter(v for row in grid for v in row);leaders=[v for v,n in counts.items()if n==max(counts.values())]
    if len(leaders)!=1:return None,{'failure':'background_tie'}
    bg=leaders[0];components=foreground_mixed_components(grid,bg)
    if len(components)!=2:return None,{'failure':'foreground_component_count_not_two'}
    groups=[set(map(tuple,c['cells']))for c in components]
    foreground={(r,c)for r,row in enumerate(grid)for c,v in enumerate(row)if v!=bg}
    if groups[0]&groups[1]or groups[0]|groups[1]!=foreground:return None,{'failure':'foreground_coverage_failed'}
    pairs=[]
    for mi,m in enumerate(components):
        for li,l in enumerate(components):
            if mi!=li and len(set(m['colors']))>=2 and len(set(l['colors']))==1 and l['colors'][0]not in set(m['colors']):pairs.append((mi,li))
    if len(pairs)!=1:return None,{'failure':'raw_roles_not_unique'}
    mi,li=pairs[0];motif,layout=components[mi],components[li]
    for i,component in enumerate(components):
        r0,c0,r1,c1=component['bbox']
        contained={(r,c)for r in range(r0,r1+1)for c in range(c0,c1+1)if grid[r][c]!=bg}
        if contained!=groups[i]:return None,{'failure':'foreign_foreground_in_bbox','role':'motif'if i==mi else'layout'}
    tile=crop_bbox(grid,motif['bbox']);mask=crop_bbox(grid,layout['bbox']);th,tw=len(tile),len(tile[0]);lh,lw=len(mask),len(mask[0]);lc=layout['colors'][0]
    if any(v not in {bg,lc}for row in mask for v in row):return None,{'failure':'layout_nonbinary_cells'}
    oh,ow=th*lh,tw*lw
    if not(1<=oh<=30 and 1<=ow<=30):return None,{'failure':'output_outside_arc_bounds'}
    expected=[[None]*ow for _ in range(oh)];coverage=set();active=[]
    for lr in range(lh):
        for ll in range(lw):
            enabled=mask[lr][ll]==lc
            if enabled:active.append([lr,ll])
            for tr in range(th):
                for tc in range(tw):
                    p=(lr*th+tr,ll*tw+tc)
                    if p in coverage:return None,{'failure':'block_overlap'}
                    coverage.add(p);expected[p[0]][p[1]]=tile[tr][tc]if enabled else bg
    if len(coverage)!=oh*ow or len(active)!=len(groups[li]):return None,{'failure':'layout_or_output_coverage_failed'}
    tile_counts=Counter(v for row in tile for v in row if v!=bg)
    expected_counts={c:n*len(active)for c,n in tile_counts.items()}
    if dict(Counter(v for row in expected for v in row if v!=bg))!=expected_counts:return None,{'failure':'motif_colour_multiplicity_failed'}
    expected_record={'renderer_case':'layout_mask_macro_tile_expander','background':bg,'macro_background_color':bg,
        'macro_motif_bbox':list(motif['bbox']),'macro_layout_bbox':list(layout['bbox']),'macro_tile_shape':[th,tw],
        'macro_layout_shape':[lh,lw],'macro_tiled_shape':[oh,ow],'macro_layout_color':lc,
        'macro_active_cell_count':len(active),'macro_motif_colors':motif['colors']}
    if raw!=expected or raw_record!=expected_record:return None,{'failure':'original_grid_or_record_disagreement'}
    return raw,{'raw_record':raw_record,'foreground_component_count':2,'input_foreground_pixels':len(foreground),
        'active_layout_cells':active,'inactive_layout_cell_count':lh*lw-len(active),'tile_cell_count':th*tw,
        'output_cell_count':len(coverage),'motif_foreground_counts':sorted(tile_counts.items()),
        'output_foreground_counts':sorted(expected_counts.items())}

def fit_teachers(teachers):
    if len(teachers)<2 or any(not valid_grid(p['input'])or not valid_grid(p['output'])for p in teachers):
        return False,{'failure':'insufficient_or_invalid_teachers'}
    if len({tuple(map(tuple,p['input']))for p in teachers})!=len(teachers):return False,{'failure':'duplicate_teacher_inputs'}
    raw=[render_layout_mask_macro_tile_expander(p['input'])for p in teachers]
    record={'raw_pair_fits':[out is not None and out==p['output']for(out,_),p in zip(raw,teachers)],'raw_records':[r for _,r in raw]}
    if not all(record['raw_pair_fits']):return False,dict(record,failure='original_teacher_reproduction_failed')
    guarded=[guarded_render(p['input'])for p in teachers];record['teacher_records']=[r for _,r in guarded]
    if any(out is None or out!=p['output']for(out,_),p in zip(guarded,teachers)):
        return False,dict(record,failure='teacher_certificate_failed')
    return True,record

class 配置展開教材:
    def __init__(self, 教師群):
        self.適合, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if not self.適合:
            return None, {"failure": "全教師を再現する配置mask展開なし"}
        return guarded_render(格子)

    def 記録(self):
        return {"全教師共通配置積": self.適合}
