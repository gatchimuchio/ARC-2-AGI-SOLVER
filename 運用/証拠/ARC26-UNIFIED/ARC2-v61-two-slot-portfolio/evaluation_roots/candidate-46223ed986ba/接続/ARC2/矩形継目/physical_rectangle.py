"""Input-first rigid rectangular ownership extension; frozen old paths preserved."""
from dataclasses import dataclass
from collections import Counter
from . import anchored_rectangle as base
from . import seam_rectangle as legacy
from .physical_rectangle_view import observe
from .propagated_rectangle import seam_assemble
from .seam_rectangle import certify_contacts
PRIOR='preserve_rectangular_C8_physical_piece_then_double_wall_seam'
@dataclass(frozen=True)
class State:
    programs: tuple=(PRIOR,)
def physical_predict(state,grid,*,budget=base.LIMIT):
    if not isinstance(state,State) or state.programs!=(PRIOR,):
        return None,{'status':'HOLD','failure':'invalid_state'}
    if type(budget)is not int or not 1<=budget<=base.LIMIT:
        return None,{'status':'HOLD','failure':'invalid_budget'}
    meter=base.WorkBudget(budget);role_returns=[]
    try:
        roles,observation=observe(grid,meter)
        if not roles:return None,{'status':'HOLD','failure':'no_structural_role','observation':observation}
        for role in roles:
            _,geometry=seam_assemble(grid,role,meter)
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



def predict(state,grid,*,budget=base.LIMIT):
    if not isinstance(state,State) or state.programs!=(PRIOR,):
        return None,{'status':'HOLD','failure':'invalid_state'}
    old,record=legacy.predict(legacy.State(),grid,budget=budget)
    if record.get('failure')!='no_structural_role':return old,record
    out,new=physical_predict(state,grid,budget=budget)
    return out,dict(new,legacy_record=record)

def fit(teachers):
    if not isinstance(teachers,(list,tuple)) or len(teachers)<2:
        return None,{'status':'HOLD','failure':'insufficient_teachers'}
    if any(not isinstance(p,dict) or not base.valid_grid(p.get('input')) or not base.valid_grid(p.get('output')) for p in teachers):
        return None,{'status':'HOLD','failure':'invalid_teacher'}
    if len({tuple(map(tuple,p['input'])) for p in teachers})!=len(teachers):
        return None,{'status':'HOLD','failure':'duplicate_teacher'}
    # Every old/new renderer conserves all piece colors, erases exactly the
    # three marker pixels, and adds exactly three background pixels, on the
    # unchanged canvas. A violation proves teacher fit impossible before CSP.
    necessary=[]
    for p in teachers:
        x,y=p['input'],p['output']
        a=Counter(v for row in x for v in row);b=Counter(v for row in y for v in row)
        delta={c:b[c]-a[c] for c in set(a)|set(b) if b[c]!=a[c]}
        same_shape=len(x)==len(y) and len(x[0])==len(y[0])
        marker=[c for c,d in delta.items() if d==-3 and a[c]==3 and b[c]==0]
        background=[c for c,d in delta.items() if d==3]
        necessary.append(dict(same_shape=same_shape,color_delta=dict(delta),
            qualified=same_shape and len(delta)==2 and len(marker)==len(background)==1))
    state=State();returns=[]
    for p,certificate in zip(teachers,necessary):
        old,record=legacy.predict(legacy.State(),p['input'])
        if record.get('failure')!='no_structural_role':
            returns.append((old,record))
        elif not certificate['qualified']:
            returns.append((None,dict(status='HOLD',complete=True,
                failure='teacher_render_invariant_impossible',
                necessary_certificate=certificate,legacy_record=record)))
        else:
            returns.append(predict(state,p['input']))
    exact=[out==p['output'] for p,(out,r) in zip(teachers,returns)]
    status='RESOURCE_INCOMPLETE' if any(r['status']=='RESOURCE_INCOMPLETE' for out,r in returns) else 'FIT' if all(exact) else 'HOLD'
    return (state if all(exact) else None),dict(status=status,fixed_prior=PRIOR,fitted_parameters=[],
        teacher_exact=exact,all_teacher_returns=[r for out,r in returns])
