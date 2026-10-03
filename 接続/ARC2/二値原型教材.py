"""全D4・二配色・全crop位置の合意を証明し、元格子だけをHDSへ渡す。"""
from __future__ import annotations
from .既存二値原型 import infer_dihedral_binary_template_policy,render_dihedral_binary_pattern_completion

def valid_grid(grid):
    return(isinstance(grid,list)and 1<=len(grid)<=30 and isinstance(grid[0],list)and 1<=len(grid[0])<=30
           and all(isinstance(row,list)and len(row)==len(grid[0])and all(type(v)is int and 0<=v<=9 for v in row)for row in grid))

def enumerate_surfaces(grid,template):
    if not valid_grid(grid):return None,{'failure':'invalid_arc_grid'}
    if not(isinstance(template,list)and len(template)==20 and all(isinstance(row,list)and len(row)==20 and all(type(v)is int and v in(0,1)for v in row)for row in template)):
        return None,{'failure':'invalid_fixed20_binary_template'}
    if {v for row in template for v in row}!={0,1}:return None,{'failure':'template_not_two_colours'}
    colours=sorted({v for row in grid for v in row})
    if len(colours)!=2:return None,{'failure':'input_not_two_colours'}
    h,w=len(grid),len(grid[0]);current=[row[:]for row in template];surfaces={};origins_checked=0;physical_models=0
    for rotation in range(4):
        for flipped in(False,True):
            oriented=[row[::-1]if flipped else row[:]for row in current]
            name='rot'+str(rotation*90)+('_flip_h'if flipped else'')
            for zero,one in[colours,colours[::-1]]:
                physical_models+=1;surface=[[zero if bit==0 else one for bit in row]for row in oriented];positions=[]
                for top in range(max(0,21-h)):
                    for left in range(max(0,21-w)):
                        origins_checked+=1
                        if all(grid[r][c]==surface[top+r][left+c]for r in range(h)for c in range(w)):positions.append([top,left])
                if positions:
                    key=tuple(map(tuple,surface));entry=surfaces.setdefault(key,{'surface':surface,'matches':[]});entry['matches'].append({'transform':name,'zero_color':zero,'one_color':one,'placements':positions})
        current=[[current[19-c][r]for c in range(20)]for r in range(20)]
    return list(surfaces.values()),{'physical_models_checked':physical_models,'crop_origins_checked':origins_checked,'distinct_matching_surfaces':len(surfaces)}

def guarded_render(grid,template):
    candidates,enumeration=enumerate_surfaces(grid,template)
    if candidates is None:return None,enumeration
    if len(candidates)!=1:return None,dict(enumeration,failure='complete_surface_not_unique')
    candidate=candidates[0];surface=candidate['surface'];h,w=len(grid),len(grid[0])
    for match in candidate['matches']:
        for top,left in match['placements']:
            if not(0<=top<=20-h and 0<=left<=20-w)or any(grid[r][c]!=surface[top+r][left+c]for r in range(h)for c in range(w)):
                return None,{'failure':'observed_crop_disagrees'}
    first=candidate['matches'][0];raw,record=render_dihedral_binary_pattern_completion(grid,template)
    if raw is None:return None,{'failure':'original_renderer_unresolved','raw_record':record}
    expected_record={'renderer_case':'dihedral_binary_pattern_completion','dihedral_template_shape':[20,20],'dihedral_transform':first['transform'],'dihedral_zero_color':first['zero_color'],'dihedral_one_color':first['one_color'],'dihedral_placement_count':len(first['placements']),'dihedral_first_placement':first['placements'][0],'dihedral_observed_shape':[h,w],'dihedral_observed_cell_count':h*w,'dihedral_completed_cell_count':400-h*w}
    if raw!=surface or record!=expected_record:return None,{'failure':'original_grid_or_record_disagreement'}
    if not valid_grid(raw)or{v for row in raw for v in row}!={v for row in grid for v in row}:return None,{'failure':'output_palette_or_grid_disagrees'}
    placements=sorted({tuple(p)for m in candidate['matches']for p in m['placements']})
    return raw,{'raw_record':record,**enumeration,'physical_matches':candidate['matches'],'distinct_crop_placements':[list(p)for p in placements],'observed_cells':h*w,'stored_template_bits':400}

def fit_teachers(teachers):
    if len(teachers)<2 or any(not valid_grid(p['input'])or not valid_grid(p['output'])for p in teachers):return None,{'failure':'insufficient_or_invalid_teachers'}
    if len({tuple(map(tuple,p['input']))for p in teachers})!=len(teachers):return None,{'failure':'duplicate_teacher_inputs'}
    policy,inference=infer_dihedral_binary_template_policy(teachers)
    if policy is None:return None,{'failure':'original_template_inference_failed','inference':inference}
    template=[row[:]for row in policy['dihedral_binary_template']]
    raw=[render_dihedral_binary_pattern_completion(p['input'],template)for p in teachers];fits=[o is not None and o==p['output']for(o,r),p in zip(raw,teachers)];record={'raw_policy':policy,'raw_pair_fits':fits,'raw_records':[r for o,r in raw]}
    if not all(fits):return None,dict(record,failure='original_teacher_reproduction_failed')
    guarded=[guarded_render(p['input'],template)for p in teachers];record['teacher_records']=[r for o,r in guarded]
    if any(o is None or o!=p['output']for(o,r),p in zip(guarded,teachers)):return None,dict(record,failure='teacher_certificate_failed')
    return template,record

class 二値原型教材:
    def __init__(self, 教師群):
        self.原型, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if self.原型 is None:
            return None, {"failure": "全教師を再現する現在課題の二値原型なし"}
        return guarded_render(格子, self.原型)

    def 記録(self):
        return {"現在教師からの原型": self.原型 is not None,
                "原型寸法": [20, 20] if self.原型 is not None else None,
                "記憶bit数": 400 if self.原型 is not None else 0}
