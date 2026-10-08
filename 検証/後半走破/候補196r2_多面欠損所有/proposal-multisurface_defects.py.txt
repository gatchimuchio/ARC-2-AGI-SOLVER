"""Compose accepted binary region ownership with opposite-surface hole outlines.
The ownership prior is inherited unchanged; no task or evaluator dependency.
"""
from 接続.ARC2.直交領域所有核 import unique_region, valid_grid
from 接続.ARC2.既存穴輪郭 import EIGHT_DELTAS


def apply_model(grid, model):
    if not valid_grid(grid) or not isinstance(model,dict) or set(model)!={'background','marker','version'} or model['version']!=1:
        return None, {'failure':'invalid_grid_or_model'}
    bg,marker=model['background'],model['marker']
    if type(bg) is not int or type(marker) is not int or not 0<=bg<=9 or not 0<=marker<=9 or bg==marker:
        return None, {'failure':'invalid_roles'}
    colors=sorted({v for row in grid for v in row})
    if bg not in colors or marker in colors or len(colors)!=3:
        return None, {'failure':'unexpected_palette'}
    surfaces=[v for v in colors if v!=bg]
    results=[]
    for color in surfaces:
        mask,proof=unique_region([[int(v==color) for v in row] for row in grid])
        results.append((color,mask,proof))
    if any(mask is None for color,mask,proof in results):
        return None, {'failure':'nonunique_surface','records':[proof for color,mask,proof in results]}
    h,w=len(grid),len(grid[0]);clean=[[bg]*w for row in grid]
    for r in range(h):
        for c in range(w):
            owners=[color for color,mask,proof in results if mask[r][c]]
            if len(owners)>1:return None, {'failure':'overlapping_surface_ownership'}
            if owners:clean[r][c]=owners[0]
    holes={(r,c):clean[r][c] for r in range(h) for c in range(w) if grid[r][c]==bg and clean[r][c]!=bg}
    surplus=[(r,c) for r in range(h) for c in range(w) if grid[r][c]!=bg and grid[r][c]!=clean[r][c]]
    if not holes or not surplus:return None, {'failure':'both_defects_required'}
    if set(holes.values())!=set(surfaces):return None, {'failure':'missing_surface_hole_witness'}
    paint={}
    for (r,c),owner in holes.items():
        opposite=next(v for v in surfaces if v!=owner)
        for dr,dc in EIGHT_DELTAS:
            rr,cc=r+dr,c+dc
            if 0<=rr<h and 0<=cc<w and (rr,cc) not in holes:
                paint.setdefault((rr,cc),set()).add(opposite)
    if any(len(v)!=1 for v in paint.values()):return None, {'failure':'conflicting_outline_ownership'}
    if set(surplus)&set(paint):return None, {'failure':'surplus_outline_ownership_collision'}
    out=[row[:] for row in clean]
    for (r,c),values in paint.items():out[r][c]=next(iter(values))
    for r,c in holes:out[r][c]=marker
    return out, {'surfaces':surfaces,'proofs':[proof for color,mask,proof in results],
                 'holes':[[r,c,owner] for (r,c),owner in sorted(holes.items())],
                 'surplus':surplus,'outline_count':len(paint)}


def fit_teachers(teachers):
    if not isinstance(teachers,list) or len(teachers)<2:return []
    if any(not isinstance(p,dict) or not valid_grid(p.get('input')) or not valid_grid(p.get('output')) or
           len(p['input'])!=len(p['output']) or len(p['input'][0])!=len(p['output'][0]) for p in teachers):return []
    if len({tuple(tuple(row) for row in p['input']) for p in teachers})!=len(teachers):return []
    palettes=[{v for row in p['input'] for v in row} for p in teachers]
    novel=[{v for row in p['output'] for v in row}-colors for p,colors in zip(teachers,palettes)]
    if any(len(v)!=3 for v in palettes) or any(len(v)!=1 for v in novel):return []
    markers=set.intersection(*novel);backgrounds=set.intersection(*palettes)
    models=[]
    for bg in sorted(backgrounds):
        for marker in sorted(markers):
            model={'background':bg,'marker':marker,'version':1}
            results=[apply_model(p['input'],model) for p in teachers]
            if all(out==p['output'] for p,(out,info) in zip(teachers,results)):models.append(model)
    return models


def predict(grid,models):
    if not isinstance(models,list) or not models:return None, {'failure':'no_teacher_fit'}
    results=[apply_model(grid,model) for model in models]
    if any(out is None for out,info in results):
        return None, {'failure':'retained_model_failure','records':[info for out,info in results]}
    if any(out!=results[0][0] for out,info in results):return None, {'failure':'retained_model_disagreement'}
    return results[0][0], {'models':models,'records':[info for out,info in results]}
