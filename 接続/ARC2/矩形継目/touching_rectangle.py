"""Double-wall ownership view composed with frozen154 seam assembly.

New explicit fixed prior: saturate cuts between adjacent complete monochrome
frame bands, with non-frame payload on both sides. Every saturated ownership is
retained; it qualifies geometrically only if all leaves are filled rectangles.
No output, assembly success, or ranking participates in the split relation.
"""
from dataclasses import dataclass
from collections import Counter
from itertools import product
from . import anchored_rectangle as base
from .seam_rectangle import certify_contacts

PRIOR='double_wall_saturation_then_anchored_rectangle_seam_or_wall'
@dataclass(frozen=True)
class State:
    programs: tuple=(PRIOR,)


def partitions(cells,border,meter):
    memo={};cut_records=[]
    def visit(body):
        key=tuple(sorted(body));meter.charge(1,'partition_node')
        if key in memo:return memo[key]
        branches=[]
        for axis in (0,1):
            meter.charge(len(body),'partition_bands')
            bands={}
            for p in body:bands.setdefault(p[axis],[]).append(p)
            lo=min(bands);hi=max(bands)
            for cut in range(lo,hi):
                a=bands.get(cut,[]);b=bands.get(cut+1,[])
                meter.charge(1+len(a)+len(b),'partition_cut')
                if not a or not b:continue
                if not all(p[2]==border for p in a+b):continue
                meter.charge(len(body),'partition_split')
                low=frozenset(p for p in body if p[axis]<=cut)
                high=body-low
                if not any(p[2]!=border for p in low) or not any(p[2]!=border for p in high):continue
                # Adjacent walls must actually share a positive side interval.
                if not ({p[1-axis] for p in a}&{p[1-axis] for p in b}):continue
                cut_records.append(dict(body=key,axis=axis,cut=cut))
                for lp in visit(low):
                    for hp in visit(high):
                        meter.charge(1,'partition_product')
                        branches.append(tuple(sorted(lp+hp)))
        if not branches:branches=[(key,)]
        memo[key]=tuple(sorted(set(branches)))
        return memo[key]
    return visit(frozenset(tuple(p) for p in cells)),cut_records


def observe(grid,meter):
    if not base.valid_grid(grid):return (),{'failure':'invalid_grid'}
    colors=sorted({v for row in grid for v in row});roles=[];probes=[]
    for marker in colors:
        marker_cells={(r,c) for r,row in enumerate(grid) for c,v in enumerate(row) if v==marker}
        if len(marker_cells)!=3:continue
        r0,c0=min(r for r,c in marker_cells),min(c for r,c in marker_cells)
        square={(r0+dr,c0+dc) for dr in (0,1) for dc in (0,1)}
        if not marker_cells<square:continue
        corner=next(iter(square-marker_cells));border=grid[corner[0]][corner[1]]
        sr=1 if corner[0]==r0+1 else -1;sc=1 if corner[1]==c0+1 else -1
        for bg in colors:
            if bg in (marker,border):continue
            payload=[[bg if v==marker else v for v in row] for row in grid]
            components=base.mixed_c8(payload,bg)
            decompositions=[];all_cuts=[]
            for p in components:
                pp,cuts=partitions(p['cells'],border,meter)
                decompositions.append(pp);all_cuts+=cuts
            probe=dict(background=bg,marker=marker,physical_components=len(components),
                       cuts=all_cuts,ownerships=[])
            probes.append(probe)
            seen=set()
            for alternatives in product(*decompositions):
                meter.charge(1,'ownership_product')
                bodies=tuple(sorted(body for parts in alternatives for body in parts))
                if bodies in seen:continue
                seen.add(bodies);pieces=[];invalid=[]
                for i,body in enumerate(bodies):
                    top,left=min(r for r,c,v in body),min(c for r,c,v in body)
                    bottom,right=max(r for r,c,v in body),max(c for r,c,v in body)
                    if len(body)!=(bottom-top+1)*(right-left+1):invalid.append(i)
                    pieces.append(dict(component_index=i,bbox=(top,left,bottom,right),
                                       area=len(body),cells=body,color_counts=dict(Counter(v for r,c,v in body))))
                qualification=dict(piece_count=len(pieces),nonrectangular_leaves=invalid)
                probe['ownerships'].append(qualification)
                if invalid or len(pieces)<2:continue
                host=[i for i,p in enumerate(pieces) if corner==(p['bbox'][0] if sr==1 else p['bbox'][2],p['bbox'][1] if sc==1 else p['bbox'][3])]
                qualification['host_count']=len(host)
                if len(host)!=1:continue
                owned={(r,c) for p in pieces for r,c,v in p['cells']}
                foreground={(r,c) for r,row in enumerate(grid) for c,v in enumerate(row) if v!=bg}
                if len(owned)!=sum(p['area'] for p in pieces) or owned&marker_cells or owned|marker_cells!=foreground:
                    raise ValueError('ownership_failure')
                roles.append(dict(background=bg,marker=marker,border=border,anchor=corner,
                                  signs=(sr,sc),host=host[0],pieces=pieces))
    return tuple(roles),dict(role_count=len(roles),probes=probes)


def predict(state,grid,*,budget=base.LIMIT):
    if not isinstance(state,State) or state.programs!=(PRIOR,):
        return None,{'status':'HOLD','failure':'invalid_state'}
    if type(budget)is not int or not 1<=budget<=base.LIMIT:
        return None,{'status':'HOLD','failure':'invalid_budget'}
    meter=base.WorkBudget(budget);role_returns=[]
    try:
        roles,observation=observe(grid,meter)
        if not roles:return None,{'status':'HOLD','failure':'no_structural_role','observation':observation}
        for role in roles:
            _,geometry=base.assemble(grid,role,meter)
            candidates=[];feasible=[]
            for placements in geometry['placements']:
                accepted,contacts,painted=certify_contacts(role,placements,meter)
                candidates.append(dict(placements=placements,contacts=contacts,seam_qualified=accepted))
                if not accepted:continue
                h=max(r for r,c in painted)+1;w=max(c for r,c in painted)+1
                sr,sc=role['signs'];ar,ac=role['anchor']
                top=ar if sr==1 else ar-h+1;left=ac if sc==1 else ac-w+1
                out=[[role['background']]*len(grid[0]) for _ in grid]
                for (r,c),v in painted.items():out[top+r][left+c]=v
                feasible.append(tuple(map(tuple,out)))
            grids=set(feasible)
            failure=('no_seam_qualified_assembly' if not feasible else
                     'seam_qualified_outputs_disagree' if len(grids)!=1 else None)
            role_returns.append((next(iter(grids)) if len(grids)==1 else None,
                                 dict(geometry=geometry,all_proposals=candidates,
                                      feasible_count=len(feasible),distinct_outputs=len(grids),failure=failure)))
    except base.BudgetIncomplete:
        return None,{'status':'RESOURCE_INCOMPLETE','failure':'budget_incomplete','complete':False,'work':meter.used}
    rec=dict(status='HOLD',complete=True,work=meter.used,observation=observation,
             all_role_returns=[r for out,r in role_returns])
    if any(out is None for out,r in role_returns):return None,dict(rec,failure='retained_role_failed')
    grids={out for out,r in role_returns}
    if len(grids)!=1:return None,dict(rec,failure='retained_role_disagreement')
    return [list(row) for row in next(iter(grids))],dict(rec,status='CANDIDATE')


def fit(teachers):
    if not isinstance(teachers,(list,tuple)) or len(teachers)<2:
        return None,{'status':'HOLD','failure':'insufficient_teachers'}
    if any(not isinstance(p,dict) or not base.valid_grid(p.get('input')) or not base.valid_grid(p.get('output')) for p in teachers):
        return None,{'status':'HOLD','failure':'invalid_teacher'}
    if len({tuple(map(tuple,p['input'])) for p in teachers})!=len(teachers):
        return None,{'status':'HOLD','failure':'duplicate_teacher'}
    state=State();returns=[predict(state,p['input']) for p in teachers]
    exact=[out==p['output'] for p,(out,r) in zip(teachers,returns)]
    status='RESOURCE_INCOMPLETE' if any(r['status']=='RESOURCE_INCOMPLETE' for out,r in returns) else 'FIT' if all(exact) else 'HOLD'
    return (state if all(exact) else None),dict(status=status,fixed_prior=PRIOR,fitted_parameters=[],
        teacher_exact=exact,all_teacher_returns=[r for out,r in returns])
