"""全raw帯・全外側図形の所有と投射を証明し元格子だけをHDSへ渡す。"""
from __future__ import annotations
from collections import Counter
from .既存帯図形投射 import horizontal_band_glyph_bands,render_horizontal_band_glyph_projector,color_components

def valid_grid(grid):
    return(isinstance(grid,list)and 1<=len(grid)<=30 and isinstance(grid[0],list)and 1<=len(grid[0])<=30
           and all(isinstance(row,list)and len(row)==len(grid[0])and all(type(v)is int and 0<=v<=9 for v in row)for row in grid))

def raw_band_runs(grid,background):
    rows=[]
    for r,row in enumerate(grid):
        edge=row[0];inside=set(row[1:-1])
        if edge==background or row[-1]!=edge or len(inside)!=1:continue
        fill=next(iter(inside))
        if fill in(background,edge):continue
        rows.append({'row':r,'fill_color':fill,'edge_color':edge})
    runs=[]
    for row in rows:
        if runs and row['row']==runs[-1]['row_max']+1 and row['fill_color']==runs[-1]['fill_color']and row['edge_color']==runs[-1]['edge_color']:
            runs[-1]['row_max']=row['row']
        else:runs.append({'row_min':row['row'],'row_max':row['row'],'fill_color':row['fill_color'],'edge_color':row['edge_color']})
    return runs

def guarded_render(grid):
    if not valid_grid(grid):return None,{'failure':'invalid_arc_grid'}
    h,w=len(grid),len(grid[0])
    if w<5:return None,{'failure':'original_width_domain'}
    counts=Counter(v for row in grid for v in row);leaders=[v for v,n in counts.items()if n==max(counts.values())]
    if len(leaders)!=1:return None,{'failure':'background_tie'}
    bg=leaders[0];bands=raw_band_runs(grid,bg)
    if not bands:return None,{'failure':'no_raw_bands'}
    if any(b['row_max']-b['row_min']+1<3 for b in bands):return None,{'failure':'short_raw_band','raw_bands':bands}
    fills=[b['fill_color']for b in bands]
    if len(set(fills))!=len(fills):return None,{'failure':'raw_fill_roles_not_unique','raw_bands':bands}
    if horizontal_band_glyph_bands(grid)!=bands:return None,{'failure':'original_band_inventory_disagrees'}
    band_rows={r for b in bands for r in range(b['row_min'],b['row_max']+1)};band_by_fill={b['fill_color']:b for b in bands};by_colour={};source_cells=set();source_components=[]
    for colour in sorted(set(counts)-{bg}):
        by_colour[colour]=color_components(grid,colour,include_diagonal=False)
        for component in by_colour[colour]:
            cells=set(component['cells']);inside={p for p in cells if p[0]in band_rows};outside=cells-inside
            if inside and outside:return None,{'failure':'component_straddles_band','colour':colour,'bbox':list(component['bbox'])}
            if not outside:continue
            if colour not in band_by_fill:return None,{'failure':'unmapped_source_colour','colour':colour}
            band=band_by_fill[colour];r0,c0,r1,c1=component['bbox']
            if r1>=band['row_min']:return None,{'failure':'source_not_strictly_above_band','colour':colour,'bbox':list(component['bbox'])}
            if r1-r0+1>band['row_max']-band['row_min']+1:return None,{'failure':'source_taller_than_band','colour':colour,'bbox':list(component['bbox'])}
            if len(cells)!=component['size']or source_cells&cells:return None,{'failure':'source_component_ownership_failed'}
            source_cells.update(cells);source_components.append(component)
    foreground={(r,c)for r,row in enumerate(grid)for c,v in enumerate(row)if r not in band_rows and v!=bg}
    if source_cells!=foreground:return None,{'failure':'source_coverage_failed'}
    if not source_components:return None,{'failure':'no_source_components'}
    proposals={};records=[];projected_sum=0;duplicate_count=0
    for band in bands:
        colour=band['fill_color'];edge=band['edge_color']
        for component in by_colour[colour]:
            cells=set(component['cells'])
            if any(r in band_rows for r,c in cells):continue
            r0,c0,r1,c1=component['bbox'];delta=band['row_max']-r1;top=r0+delta
            for r,c in cells:
                target=(r+delta,c)
                if not(band['row_min']<=target[0]<=band['row_max']and 0<c<w-1):return None,{'failure':'projection_outside_band_interior','target':list(target)}
                if target in proposals:
                    if proposals[target]!=edge:return None,{'failure':'projection_colours_conflict'}
                    duplicate_count+=1
                proposals[target]=edge;projected_sum+=1
            records.append({'fill_color':colour,'edge_color':edge,'source_bbox':[r0,c0,r1,c1],'target_bbox':[top,c0,r1+delta,c1],'cell_count':component['size']})
    if projected_sum!=len(source_cells):return None,{'failure':'projection_source_count_disagrees'}
    expected=[list(row)for row in grid]
    for r,c in source_cells:expected[r][c]=bg
    for(r,c),colour in proposals.items():expected[r][c]=colour
    raw,record=render_horizontal_band_glyph_projector(grid)
    if raw is None:return None,{'failure':'original_renderer_unresolved','raw_record':record}
    expected_record={'renderer_case':'horizontal_band_glyph_projector','band_glyph_band_count':len(bands),'band_glyph_source_component_count':len(records),'band_glyph_projected_cell_count':projected_sum,'bands':bands,'source_component_records':records}
    if raw!=expected or record!=expected_record:return None,{'failure':'original_grid_or_record_disagreement'}
    if any(raw[r][c]!=grid[r][c]for r in range(h)for c in range(w)if(r,c)not in source_cells and(r,c)not in proposals):return None,{'failure':'outside_cells_changed'}
    return raw,{'raw_record':record,'background':bg,'all_raw_bands':bands,'source_components':len(records),'source_cells':len(source_cells),'proposal_sum':projected_sum,'proposal_union':len(proposals),'duplicate_same_colour_proposals':duplicate_count,'preserved_cells':h*w-len(source_cells)-len(proposals),'whole_grid_changed_cells':sum(a!=b for x,y in zip(grid,raw)for a,b in zip(x,y))}

def fit_teachers(teachers):
    if len(teachers)<2 or any(not valid_grid(p['input'])or not valid_grid(p['output'])for p in teachers):return None,{'failure':'insufficient_or_invalid_teachers'}
    if len({tuple(map(tuple,p['input']))for p in teachers})!=len(teachers):return None,{'failure':'duplicate_teacher_inputs'}
    raw=[render_horizontal_band_glyph_projector(p['input'])for p in teachers];fits=[o is not None and o==p['output']for(o,r),p in zip(raw,teachers)];record={'raw_pair_fits':fits,'raw_records':[r for o,r in raw]}
    if not all(fits):return None,dict(record,failure='original_teacher_reproduction_failed')
    guarded=[guarded_render(p['input'])for p in teachers];record['teacher_records']=[r for o,r in guarded]
    if any(o is None or o!=p['output']for(o,r),p in zip(guarded,teachers)):return None,dict(record,failure='teacher_certificate_failed')
    return {'program':'horizontal_band_glyph_projector'},record

class 帯図形教材:
    def __init__(self, 教師群):
        self.規約, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if self.規約 is None:
            return None, {"failure": "全教師を再現する帯図形投射なし"}
        return guarded_render(格子)

    def 記録(self):
        return {"全教師共通帯図形規約": self.規約}
