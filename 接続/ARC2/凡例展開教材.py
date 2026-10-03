"""全roleと全tile積を証明し、元格子だけを同じHDSへ渡す。"""
from __future__ import annotations
from collections import Counter
from .既存凡例展開 import _legend_token_macro_parse,_legend_token_macro_render

def valid_grid(grid):
    return(isinstance(grid,list)and 1<=len(grid)<=30 and isinstance(grid[0],list)and 1<=len(grid[0])<=30
           and all(isinstance(row,list)and len(row)==len(grid[0])and all(type(v)is int and 0<=v<=9 for v in row)for row in grid))

def original_render(grid):
    try:return _legend_token_macro_render(grid)
    except(IndexError,KeyError,TypeError,ValueError)as error:return None,{'failure':'original_parse_exception','type':type(error).__name__}

def guarded_render(grid):
    if not valid_grid(grid):return None,{'failure':'invalid_arc_grid'}
    counts=Counter(v for row in grid for v in row);leaders=[v for v,n in counts.items()if n==max(counts.values())]
    if len(leaders)!=1:return None,{'failure':'background_tie'}
    bg=leaders[0];h,w=len(grid),len(grid[0]);raw_rows=[]
    for r,row in enumerate(grid):
        values=[v for v in row if v!=bg]
        if len(values)>=2 and len(set(values))==1:raw_rows.append((r,values[0]))
    if len(raw_rows)<2 or len({c for r,c in raw_rows})!=1:return None,{'failure':'raw_separator_role_not_unique','raw_rows':[list(x)for x in raw_rows]}
    first,sep=raw_rows[0];second=raw_rows[1][0]
    try:parsed,rejection=_legend_token_macro_parse(grid)
    except(IndexError,KeyError,TypeError,ValueError)as error:return None,{'failure':'original_parse_exception','type':type(error).__name__}
    if parsed is None:return None,{'failure':'original_parse_unresolved','raw_record':rejection}
    n=parsed['glyph_size'];side=n*n;marker_row=parsed['marker_row'];templates=parsed['template_records'];maps=parsed['map_records'];palette=parsed['output_colors']
    if n!=first or second-first-1!=n or parsed['background']!=bg or parsed['separator_color']!=sep:
        return None,{'failure':'original_band_roles_disagree'}
    if not 1<=side<=30:return None,{'failure':'output_shape_out_of_arc_bounds','side':side}
    starts=[t['slot_start']for t in templates];occupied_cols=set()
    if len(starts)<2 or len(starts)!=len(maps):return None,{'failure':'incomplete_slots'}
    for start in starts:
        if type(start)is not int or start<0 or start+n>w:return None,{'failure':'slot_out_of_bounds','start':start}
        cols=set(range(start,start+n))
        if cols&occupied_cols:return None,{'failure':'slot_overlap'}
        occupied_cols.update(cols)
    raw_cols=[]
    for c in range(w):
        values=[grid[r][c]for r in range(n)if grid[r][c]!=bg]
        if values and set(values)=={sep}:raw_cols.append(c)
    patterns={};expected_maps=[]
    for template,map_record in zip(templates,maps):
        start=template['slot_start'];pattern=tuple(tuple(grid[r][c]for c in range(start,start+n))for r in range(n));colours={v for row in pattern for v in row if v!=bg}
        if len(colours)!=1 or sep in colours:return None,{'failure':'template_role_failed'}
        key=next(iter(colours))
        if key in patterns or key!=template['key_color']or pattern!=template['pattern']:return None,{'failure':'original_template_disagrees'}
        patterns[key]=pattern
        cells=tuple((r,c)for r in range(n)for c in range(n)if grid[first+1+r][start+c]!=bg)
        colors={grid[first+1+r][start+c]for r,c in cells}
        if len(colors)!=1:return None,{'failure':'map_role_failed'}
        token=next(iter(colors));expected_map={'slot_start':start,'token_color':token,'cells':cells}
        if expected_map!=map_record:return None,{'failure':'original_map_disagrees'}
        expected_maps.append(expected_map)
    if parsed['templates']!=patterns or {m['token_color']for m in maps}!=set(patterns):return None,{'failure':'token_dictionary_not_bijective'}
    marker_candidates=[]
    for r in range(second+1,h):
        values=[]
        for start in starts:
            colors={grid[r][c]for c in range(start,start+n)if grid[r][c]!=bg}
            if len(colors)!=1:break
            values.append(next(iter(colors)))
        if len(values)==len(starts):marker_candidates.append((r,values))
    if len(marker_candidates)!=1 or marker_candidates[0][0]!=marker_row:return None,{'failure':'marker_row_not_unique'}
    expected_palette={t['key_color']:v for t,v in zip(templates,marker_candidates[0][1])}
    if len(set(expected_palette.values()))!=len(starts)or palette!=expected_palette:return None,{'failure':'palette_role_failed'}
    slot_cells={(r,c)for start in starts for r in list(range(n))+list(range(first+1,second))+[marker_row]for c in range(start,start+n)}
    structural_cells={(r,c)for r,row in enumerate(grid)for c,v in enumerate(row)if v==sep and(r in {a for a,b in raw_rows}or c in raw_cols)}
    foreground={(r,c)for r,row in enumerate(grid)for c,v in enumerate(row)if v!=bg}
    if foreground-(slot_cells|structural_cells):return None,{'failure':'unowned_foreground','cells':[list(p)for p in sorted(foreground-(slot_cells|structural_cells))]}
    owners={};placement_records=[];expected_counts=Counter()
    for m in maps:
        token=m['token_color'];colour=palette[token];pixels=sum(v!=bg for row in patterns[token]for v in row)
        for pos in m['cells']:
            if pos in owners:return None,{'failure':'macro_position_overlap','macro_cell':list(pos)}
            if not(0<=pos[0]<n and 0<=pos[1]<n):return None,{'failure':'macro_position_out_of_bounds'}
            owners[pos]=token;expected_counts[colour]+=pixels
            placement_records.append({'token_color':token,'output_color':colour,'macro_cell':list(pos),'changed_cell_count':pixels})
    expected=[[bg]*side for _ in range(side)]
    for r in range(side):
        for c in range(side):
            token=owners.get((r//n,c//n))
            if token is not None and patterns[token][r%n][c%n]!=bg:expected[r][c]=palette[token]
    if Counter(v for row in expected for v in row if v!=bg)!=expected_counts:return None,{'failure':'output_colour_multiplicity_failed'}
    raw,raw_record=original_render(grid)
    if raw is None:return None,{'failure':'original_renderer_unresolved','raw_record':raw_record}
    expected_record={'renderer_case':'legend_token_macro_composer','legend_token_macro_background_color':bg,'legend_token_macro_separator_color':sep,'legend_token_macro_glyph_size':n,'legend_token_macro_template_count':len(patterns),'legend_token_macro_map_count':len(maps),'legend_token_macro_marker_row':marker_row,'legend_token_macro_output_shape':[side,side],'legend_token_macro_event_count':sum(expected_counts.values()),'legend_token_macro_placement_records':placement_records}
    if raw!=expected or raw_record!=expected_record:return None,{'failure':'original_grid_or_record_disagreement'}
    return raw,{'raw_record':raw_record,'raw_separator_rows':[list(x)for x in raw_rows],'raw_separator_columns':raw_cols,'slot_starts':starts,'input_foreground_pixels':len(foreground),'structural_separator_pixels':len(structural_cells),'active_macro_cells':len(owners),'inactive_macro_cells':n*n-len(owners),'output_foreground_pixels':sum(expected_counts.values()),'output_colour_counts':[[c,v]for c,v in sorted(expected_counts.items())],'checked_output_cells':side*side}

def fit_teachers(teachers):
    if len(teachers)<2 or any(not valid_grid(p['input'])or not valid_grid(p['output'])for p in teachers):return False,{'failure':'insufficient_or_invalid_teachers'}
    if len({tuple(map(tuple,p['input']))for p in teachers})!=len(teachers):return False,{'failure':'duplicate_teacher_inputs'}
    raw=[original_render(p['input'])for p in teachers];record={'raw_pair_fits':[o is not None and o==p['output']for(o,r),p in zip(raw,teachers)],'raw_records':[r for o,r in raw]}
    if not all(record['raw_pair_fits']):return False,dict(record,failure='original_teacher_reproduction_failed')
    guarded=[guarded_render(p['input'])for p in teachers];record['teacher_records']=[r for o,r in guarded]
    if any(o is None or o!=p['output']for(o,r),p in zip(guarded,teachers)):return False,dict(record,failure='teacher_certificate_failed')
    return True,record

class 凡例展開教材:
    def __init__(self, 教師群):
        self.適合, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if not self.適合:
            return None, {"failure": "全教師を再現する凡例token展開なし"}
        return guarded_render(格子)

    def 記録(self):
        return {"全教師共通凡例展開": self.適合}
