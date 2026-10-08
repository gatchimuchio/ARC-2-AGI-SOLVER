"""Teacher-only proposal: corner-pinned rectangular assembly.

Fixed new prior: an exterior three-cell L (a 2x2 square minus one corner)
marks the fixed corner of one whole rectangular piece. Translate every whole
piece, without rotation/reflection/overlap, to tile one rectangle whose entire
outer perimeter is the host-corner color. Erase the marker and old locations.
Fitted parameters: none; fit certifies this declared program on every teacher.
Accepted reuse: mixed-C8 ownership, bbox observations, grid validation, budget.
No production registration or protected edits.
"""
from dataclasses import dataclass
from collections import Counter
from 接続.ARC2.標点組立教材 import mixed_c8, valid_grid, WorkBudget, BudgetIncomplete

PRIOR = 'corner_L_anchor_translation_uniform_perimeter'
LIMIT = 100000

@dataclass(frozen=True)
class State:
    programs: tuple = (PRIOR,)


def observe(grid):
    if not valid_grid(grid):
        return (), {'failure': 'invalid_grid'}
    colors = sorted({v for row in grid for v in row})
    roles = []
    for marker in colors:
        cells = {(r,c) for r,row in enumerate(grid) for c,v in enumerate(row) if v == marker}
        if len(cells) != 3:
            continue
        r0,c0 = min(r for r,c in cells),min(c for r,c in cells)
        square = {(r0+dr,c0+dc) for dr in (0,1) for dc in (0,1)}
        if not cells < square:
            continue
        corner = next(iter(square-cells))
        sr = 1 if corner[0] == r0+1 else -1
        sc = 1 if corner[1] == c0+1 else -1
        border = grid[corner[0]][corner[1]]
        for background in colors:
            if background in (marker,border):
                continue
            payload = [[background if v == marker else v for v in row] for row in grid]
            pieces = mixed_c8(payload,background)
            if len(pieces) < 2:
                continue
            if any(p['area'] != (p['bbox'][2]-p['bbox'][0]+1)*(p['bbox'][3]-p['bbox'][1]+1) for p in pieces):
                continue
            host = []
            for p in pieces:
                top,left,bottom,right = p['bbox']
                if corner == (top if sr == 1 else bottom,left if sc == 1 else right):
                    host.append(p['component_index'])
            if len(host) != 1:
                continue
            owned = {(r,c) for p in pieces for r,c,v in p['cells']}
            foreground = {(r,c) for r,row in enumerate(grid) for c,v in enumerate(row) if v != background}
            if owned & cells or owned | cells != foreground:
                raise ValueError('ownership_failure')
            roles.append(dict(background=background,marker=marker,border=border,
                              anchor=corner,signs=(sr,sc),host=host[0],pieces=pieces))
    return tuple(roles), {'role_count':len(roles)}


def assemble(grid, role, meter):
    """Enumerate all area-factor canvases and every exact rectangular tiling.

    Pruning only enforces declared geometry/color constraints. A failed canvas
    is not a failed interpretation: all canvases jointly define this CSP. All
    completed feasible assemblies are retained and must agree.
    """
    gh,gw=len(grid),len(grid[0]); pieces=role['pieces']
    area=sum(p['area'] for p in pieces)
    host=role['host']; anchor=role['anchor']; sr,sc=role['signs']
    border=role['border']; bg=role['background']
    models=[]; shapes=[]
    source_counts=Counter(v for p in pieces for r,c,v in p['cells'])
    normalized=[]
    for p in pieces:
        r0,c0,r1,c1=p['bbox']
        normalized.append((r1-r0+1,c1-c0+1,tuple((r-r0,c-c0,v) for r,c,v in p['cells'])))
    def feasible(i,r,c,h,w,occupied):
        meter.charge(1,'placement')
        ph,pw,cells=normalized[i]
        if r<0 or c<0 or r+ph>h or c+pw>w:return None
        moved=tuple((r+dr,c+dc,v) for dr,dc,v in cells)
        if any((rr,cc) in occupied for rr,cc,v in moved):return None
        if any(v!=border for rr,cc,v in moved if rr in (0,h-1) or cc in (0,w-1)):return None
        return moved
    for h in range(1,gh+1):
        meter.charge(1,'shape')
        if area%h:continue
        w=area//h
        if w>gw:continue
        top=anchor[0] if sr==1 else anchor[0]-h+1
        left=anchor[1] if sc==1 else anchor[1]-w+1
        if top<0 or left<0 or top+h>gh or left+w>gw:continue
        ph,pw,_=normalized[host]
        hr=0 if sr==1 else h-ph; hc=0 if sc==1 else w-pw
        shapes.append([h,w])
        first=feasible(host,hr,hc,h,w,set())
        if first is None:continue
        def visit(occupied,remaining,paint,placements):
            meter.charge(1,'node')
            if not remaining:
                if len(occupied)!=area:raise ValueError('coverage_failure')
                if Counter(v for r,c,v in paint)!=source_counts:raise ValueError('color_accounting_failure')
                out=[[bg]*gw for _ in range(gh)]
                for r,c,v in paint:out[top+r][left+c]=v
                models.append((tuple(map(tuple,out)),tuple(placements)))
                return
            r,c=next((r,c) for r in range(h) for c in range(w) if (r,c) not in occupied)
            for i in remaining:
                moved=feasible(i,r,c,h,w,occupied)
                if moved is not None:
                    visit(occupied|{(r,c) for r,c,v in moved},tuple(j for j in remaining if j!=i),paint+moved,placements+((i,r,c),))
        visit({(r,c) for r,c,v in first},tuple(i for i in range(len(pieces)) if i!=host),first,((host,hr,hc),))
    outputs={m[0] for m in models}
    record={'role':{k:v for k,v in role.items() if k!='pieces'},'piece_count':len(pieces),
            'candidate_shapes':shapes,'feasible_arrangements':len(models),'distinct_outputs':len(outputs),
            'placements':[m[1] for m in models]}
    if not models:return None,{**record,'failure':'no_complete_assembly'}
    if len(outputs)!=1:return None,{**record,'failure':'assembly_disagreement'}
    return next(iter(outputs)),record


def predict(state,grid,*,budget=LIMIT):
    if not isinstance(state,State) or state.programs!=(PRIOR,):
        return None,{'status':'HOLD','failure':'invalid_frozen_state'}
    if type(budget)is not int or not 1<=budget<=LIMIT:
        return None,{'status':'HOLD','failure':'invalid_budget'}
    roles,observation=observe(grid)
    if not roles:return None,{'status':'HOLD','observation':observation,'failure':'no_structural_role'}
    meter=WorkBudget(budget); returns=[]
    try:
        for role in roles:
            returns.append(assemble(grid,role,meter))
    except BudgetIncomplete:
        return None,{'status':'RESOURCE_INCOMPLETE','failure':'budget_incomplete','complete':False,'work':meter.used}
    record={'status':'HOLD','complete':True,'observation':observation,'work':meter.used,
            'all_role_returns':[r for out,r in returns]}
    if any(out is None for out,r in returns):
        return None,{**record,'failure':'retained_role_failed'}
    outputs={out for out,r in returns}
    if len(outputs)!=1:return None,{**record,'failure':'retained_role_disagreement'}
    return [list(row) for row in next(iter(outputs))],{**record,'status':'CANDIDATE'}


def fit(teachers):
    if not isinstance(teachers,(list,tuple)) or len(teachers)<2:
        return None,{'status':'HOLD','failure':'insufficient_teachers'}
    if any(not isinstance(p,dict) or not valid_grid(p.get('input')) or not valid_grid(p.get('output')) for p in teachers):
        return None,{'status':'HOLD','failure':'invalid_teacher'}
    if len({tuple(map(tuple,p['input'])) for p in teachers})!=len(teachers):
        return None,{'status':'HOLD','failure':'duplicate_teachers'}
    state=State(); returns=[predict(state,p['input']) for p in teachers]
    fits=[out==p['output'] for p,(out,r) in zip(teachers,returns)]
    record={'status':('RESOURCE_INCOMPLETE' if any(r.get('status')=='RESOURCE_INCOMPLETE' for out,r in returns) else 'FIT' if all(fits) else 'HOLD'),'fixed_prior':PRIOR,
            'fitted_parameters':[],'teacher_exact':fits,'all_teacher_returns':[r for out,r in returns]}
    return (state if all(fits) else None),record
