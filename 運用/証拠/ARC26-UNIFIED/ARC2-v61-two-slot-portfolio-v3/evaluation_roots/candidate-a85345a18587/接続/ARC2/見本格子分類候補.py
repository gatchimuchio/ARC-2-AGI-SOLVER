"""Frozen finite example-grid classifier. Pure geometry and direct existing helpers."""
from __future__ import annotations
import itertools
from collections import Counter
from functools import lru_cache
import hashlib
import json
from math import comb, perm
from . import 既存領域転写 as regions
from . import 既存物体特徴 as features
from .既存形状色転写 import canonical_shape

def _observe(observer, kind, **value):
    if observer is not None:
        observer({'kind': kind, **value})

FEATURES=('colored_exact','shape_exact','colored_d4','shape_d4','color_histogram','palette','colored_nine_features','nine_features')
MODELS=tuple(itertools.product(('C4','C8'),FEATURES,('set_membership','injective_multiset'),('any_complete_line','exactly_one_complete_line','nonempty_collinear'),('on_success','always'),('tight_bbox','bbox_halo','lattice_halo')))

def rot(g): return [list(r) for r in zip(*g[::-1])]
def transform(g,n):
    for _ in range(n):g=rot(g)
    return g

def runs(values):
    ans=[]
    for x in sorted(set(values)):
        if ans and x==ans[-1][1]+1:ans[-1][1]=x
        else:ans.append([x,x])
    return ans

def regular_axis(bands):
    if len(bands)<2:return None
    sizes={b-a+1 for a,b in bands};gaps={c-b-1 for (_,b),(c,_) in zip(bands,bands[1:])}
    if len(sizes)!=1 or len(gaps)!=1:return None
    gap=next(iter(gaps))
    return gap//2 if gap>0 and gap%2==0 else None

@lru_cache(maxsize=128)
def parse_cached(key,connectivity):
    grid=[list(r) for r in key]
    if not grid or not grid[0] or len(grid)>30 or len(grid[0])>30 or any(len(r)!=len(grid[0]) for r in grid):return None,{'failure':'invalid_grid'}
    if any(type(v)is not int or not 0<=v<=9 for r in grid for v in r):return None,{'failure':'invalid_values'}
    counts=Counter(v for r in grid for v in r);bs=[v for v,n in counts.items() if n==max(counts.values())]
    if len(bs)!=1:return None,{'failure':'background_tie','candidates':bs}
    bg=bs[0];role_candidates=[];attempts=[]
    for orientation in range(4):
        g=transform(grid,orientation);h,w=len(g),len(g[0])
        lines=[r for r,row in enumerate(g) if len(set(row))==1 and row[0]!=bg]
        rec={'orientation':orientation,'separators':lines}
        if len(lines)!=2 or g[lines[0]][0]!=g[lines[1]][0]:
            attempts.append({**rec,'failure':'separator_role'});continue
        a,b=lines
        if a==0 or b==h-1 or b-a<2 or any(v!=bg for row in g[b+1:] for v in row):
            attempts.append({**rec,'failure':'outer_band_roles'});continue
        refgrid=g[:a];body=g[a+1:b]
        refs=regions.mixed_region_dicts_for_grid(refgrid,bg,include_diagonal=connectivity=='C8')
        objs=regions.mixed_region_dicts_for_grid(body,bg,include_diagonal=connectivity=='C8')
        if not refs or not objs:
            attempts.append({**rec,'failure':'empty_reference_or_body'});continue
        refbands=runs(r for o in refs for r,c in o['cells'])
        if len(refbands)!=1:
            attempts.append({**rec,'failure':'reference_not_single_row'});continue
        rb=runs(r+a+1 for o in objs for r,c in o['cells']);cb=runs(c for o in objs for r,c in o['cells'])
        rp,cp=regular_axis(rb),regular_axis(cb)
        if rp is None or cp is None:
            attempts.append({**rec,'failure':'nonregular_lattice','row_bands':rb,'column_bands':cb});continue
        slot_objects={};bad=False
        for obj in objs:
            obj=dict(obj);obj['cells']=[(r+a+1,c)for r,c in obj['cells']]
            r0,c0,r1,c1=obj['bbox'];obj['bbox']=(r0+a+1,c0,r1+a+1,c1)
            placements=[(ri,ci) for ri,(r0,r1) in enumerate(rb) for ci,(c0,c1) in enumerate(cb) if all(r0<=r<=r1 and c0<=c<=c1 for r,c in obj['cells'])]
            if len(placements)!=1 or placements[0] in slot_objects:bad=True
            else:slot_objects[placements[0]]=obj
        if bad or len(slot_objects)!=len(rb)*len(cb):
            attempts.append({**rec,'failure':'component_slot_ownership','components':len(objs),'lattice_slots':len(rb)*len(cb)});continue
        if rb[0][0]-rp<=a or rb[-1][1]+rp>=b or cb[0][0]-cp<0 or cb[-1][1]+cp>=w:
            attempts.append({**rec,'failure':'halo_bounds'});continue
        foreground={(r,c)for r,row in enumerate(g) for c,v in enumerate(row) if v!=bg}
        owned={(r,c)for o in refs for r,c in o['cells']}|{(r,c)for o in slot_objects.values()for r,c in o['cells']}|{(r,c)for r in lines for c in range(w)}
        if foreground!=owned:
            attempts.append({**rec,'failure':'foreground_ownership'});continue
        p={'grid':g,'orientation':orientation,'background':bg,'separators':lines,'references':refs,'objects':slot_objects,'row_bands':rb,'column_bands':cb,'halo':[rp,cp]}
        role_candidates.append(p);attempts.append({**rec,'success':True,'reference_count':len(refs),'object_count':len(objs),'lattice_shape':[len(rb),len(cb)],'foreground_owned':len(owned)})
    if len(role_candidates)!=1:return None,{'failure':'role_ambiguity_or_absence','role_count':len(role_candidates),'attempts':attempts}
    return role_candidates[0],{'attempts':attempts,'role_count':1}

def parse(grid,connectivity='C8'):return parse_cached(tuple(map(tuple,grid)),connectivity)

def signature(g,obj,feature):
    cells=obj['cells'];r0,c0,_,_=obj['bbox'];norm=tuple(sorted((r-r0,c-c0,g[r][c])for r,c in cells));mask=tuple((r,c)for r,c,v in norm)
    if feature=='colored_exact':return norm
    if feature=='shape_exact':return mask
    if feature=='shape_d4':return canonical_shape(mask)
    if feature=='colored_d4':
        variants=[]
        for swap,sr,sc in itertools.product((False,True),(-1,1),(-1,1)):
            x=[(sr*(c if swap else r),sc*(r if swap else c),v)for r,c,v in norm];mr=min(r for r,c,v in x);mc=min(c for r,c,v in x)
            variants.append(tuple(sorted((r-mr,c-mc,v)for r,c,v in x)))
        return min(variants)
    if feature=='color_histogram':return tuple(sorted(Counter(g[r][c]for r,c in cells).items()))
    if feature=='palette':return tuple(sorted({g[r][c]for r,c in cells}))
    vals=tuple(features.edge_pack_component_feature(obj))
    return (tuple(sorted(Counter(g[r][c]for r,c in cells).items())),vals)if feature=='colored_nine_features' else vals

def selections(p,feature,policy,observer=None):
    g=p['grid'];rk=[signature(g,o,feature)for o in p['references']];ok={s:signature(g,o,feature)for s,o in p['objects'].items()};matches=[[s for s,k in ok.items()if k==r]for r in rk]
    if policy=='set_membership':return [frozenset(s for ss in matches for s in ss)],{'reference_matches':matches}
    sets={frozenset()}
    _observe(observer,'allocation_search_start',reference_matches=matches,completed_reference_prefix=0,selected_sets=[[]])
    for ss in matches:
        sets={used|{s}for used in sets for s in ss if s not in used}
        _observe(observer,'allocation_search_step',selected_sets=[sorted(s)for s in sorted(sets,key=lambda z:sorted(z))])
    return sorted(sets,key=lambda z:sorted(z)),{'reference_matches':matches,'allocation_output_sets':len(sets)}

def is_line(selected,nr,nc,condition):
    lines=[frozenset((r,c)for c in range(nc))for r in range(nr)]+[frozenset((r,c)for r in range(nr))for c in range(nc)]
    if condition=='any_complete_line':return any(x<=selected for x in lines)
    if condition=='exactly_one_complete_line':return sum(x==selected for x in lines)==1
    return bool(selected)and(len({r for r,c in selected})==1 or len({c for r,c in selected})==1)

def proposal(p,selected,condition,top,region):
    g=p['grid'];h,w=len(g),len(g[0]);bg=p['background'];a,b=p['separators'];mark=set();fail=set();nr,nc=len(p['row_bands']),len(p['column_bands']);success=is_line(selected,nr,nc,condition)
    for s in selected:
        r0,c0,r1,c1=p['objects'][s]['bbox'];rp,cp=p['halo']
        if region=='lattice_halo':
            r0,r1=p['row_bands'][s[0]];c0,c1=p['column_bands'][s[1]]
        if region!='tight_bbox':r0-=rp;r1+=rp;c0-=cp;c1+=cp
        mark|={(r,c)for r in range(r0,r1+1)for c in range(c0,c1+1)if g[r][c]==bg}
    if success or top=='always':mark|={(r,c)for r in range(a)for c in range(w)if g[r][c]==bg}
    status={(r,c)for r in range(b+1,h)for c in range(w)if g[r][c]==bg}
    if success:mark|=status
    else:fail|=status
    return mark,fail,success

def _allocation_witness_output(grid,p,selected,condition,top,region,colors):
    """The original allocation renderer, including full inverse transformation."""
    mark,fail,success=proposal(p,selected,condition,top,region);out=[r[:]for r in p['grid']]
    for r,c in mark:out[r][c]=colors[0]
    for r,c in fail:out[r][c]=colors[1]
    output=transform(out,(-p['orientation'])%4)
    detail={'selected':sorted(selected),'success':success,'mark_cells':len(mark),'failure_cells':len(fail)}
    bg=p['background']
    if any(v!=bg and output[r][c]!=v for r,row in enumerate(grid)for c,v in enumerate(row)):
        return None,{**detail,'failure':'foreground_changed'}
    return output,detail

def _identical_match_disagreement(grid,p,feature,policy,condition,top,region,colors,observer=None):
    """Two complete counterexamples can refute consensus, never establish it."""
    if policy!='injective_multiset':return None
    g=p['grid'];rk=[signature(g,o,feature)for o in p['references']]
    ok={s:signature(g,o,feature)for s,o in p['objects'].items()}
    matches=[tuple(sorted(s for s,k in ok.items()if k==r))for r in rk]
    if not matches or any(ss!=matches[0]for ss in matches):return None
    slots=matches[0];m=len(matches);n=len(slots)
    if n<m+1:return None
    domain={'reference_count':m,'admissible_slot_count':n,'admissible_slots':slots,
            'selected_set_count':comb(n,m),'ordered_allocation_count':perm(n,m)}
    _observe(observer,'allocation_proof_start',domain=domain)
    mappings=(slots[:m],slots[:m-1]+(slots[m],));witnesses=[]
    for mapping in mappings:
        valid=(len(mapping)==m and len(set(mapping))==m
               and all(slot in matches[i]for i,slot in enumerate(mapping)))
        if not valid:return None
        output,detail=_allocation_witness_output(grid,p,frozenset(mapping),condition,top,region,colors)
        witness={'assignments':tuple((i,slot)for i,slot in enumerate(mapping)),
                 'complete_injection_valid':valid,'output':output,'record':detail,
                 'output_sha256':None if output is None else hashlib.sha256(json.dumps(output,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()}
        witnesses.append(witness)
        _observe(observer,'allocation_witness_return',witness_index=len(witnesses)-1,witness=witness)
    if any(w['output']is None for w in witnesses)or witnesses[0]['output']==witnesses[1]['output']:
        _observe(observer,'allocation_proof_fallback',reason='no_complete_output_disagreement',witnesses=witnesses)
        return None
    left,right=(w['output']for w in witnesses)
    difference=next({'row':r,'column':c,'first':left[r][c],'second':right[r][c]}
                    for r in range(len(left))for c in range(len(left[r]))if left[r][c]!=right[r][c])
    proof={'kind':'two_complete_injective_outputs_disagree','domain':domain,'witnesses':witnesses,
           'differing_cell':difference,'evaluated_selected_sets':2,'evaluated_ordered_allocations':2,
           'unexecuted_selected_sets':domain['selected_set_count']-2,
           'unexecuted_ordered_allocations':domain['ordered_allocation_count']-2,
           'success_established':False}
    _observe(observer,'allocation_disagreement_proved',proof=proof)
    return {'reference_matches':matches,'allocation_output_sets':domain['selected_set_count'],
            'allocations':[w['record']for w in witnesses],'allocation_disagreement_proof':proof}

def render(grid,model,colors,observer=None):
    _observe(observer,'render_start',model=model,colors=colors)
    conn,feature,policy,condition,top,region=model;p,rec=parse(grid,conn)
    if p is None:return None,rec
    proof=_identical_match_disagreement(grid,p,feature,policy,condition,top,region,colors,observer=observer)
    if proof is not None:return None,{**rec,**proof,'failure':'allocation_disagreement'}
    choices,match=selections(p,feature,policy,observer=observer);outputs=[];details=[]
    for selected in choices:
        mark,fail,success=proposal(p,selected,condition,top,region);out=[r[:]for r in p['grid']]
        for r,c in mark:out[r][c]=colors[0]
        for r,c in fail:out[r][c]=colors[1]
        outputs.append(transform(out,(-p['orientation'])%4));details.append({'selected':sorted(selected),'success':success,'mark_cells':len(mark),'failure_cells':len(fail)})
        _observe(observer,'allocation_return',allocation_index=len(outputs)-1,output=outputs[-1],record=details[-1])
    rec={**rec,**match,'allocations':details}
    if not outputs:return None,{**rec,'failure':'no_injective_allocation'}
    if any(o!=outputs[0]for o in outputs):return None,{**rec,'failure':'allocation_disagreement'}
    out=outputs[0];bg=p['background']
    if any(v!=bg and out[r][c]!=v for r,row in enumerate(grid)for c,v in enumerate(row)):return None,{**rec,'failure':'foreground_changed'}
    return out,{**rec,'foreground_preserved':True}

def fit(train,observer=None):
    records=[];retained=[]
    for model in MODELS:
        _observe(observer,'model_start',model=model,model_index=len(records))
        color_sets=[set(),set()];parameter_failures=[];parameter_observations=[]
        for i,pair in enumerate(train):
            _observe(observer,'parameter_teacher_start',teacher_index=i)
            p,rec=parse(pair['input'],model[0])
            if p is None:
                parameter_failures.append({'teacher':i,**rec});parameter_observations.append({'teacher':i,**rec});_observe(observer,'parameter_teacher_return',record=parameter_observations[-1]);continue
            expected=transform(pair['output'],p['orientation']);choices,_=selections(p,model[1],model[2],observer=observer)
            if not choices:parameter_failures.append({'teacher':i,'failure':'no_injective_allocation'})
            observed=[]
            for choice in choices:
                mark,fail,_=proposal(p,choice,*model[3:])
                local=[sorted({expected[r][c]for r,c in cells})for cells in (mark,fail)]
                observed.append({'selected':sorted(choice),'paint_color_sets':local})
                for j,cs in enumerate(local):color_sets[j].update(cs)
                _observe(observer,'parameter_allocation_return',allocation_index=len(observed)-1,record=observed[-1])
            parameter_observations.append({'teacher':i,'choices':observed})
            _observe(observer,'parameter_teacher_return',record=parameter_observations[-1])
        colors=tuple(next(iter(s))if len(s)==1 else None for s in color_sets)
        teachers=[]
        for pair in train:
            if None in colors:out=None;rec={'failure':'paint_parameters_unresolved','observed_color_sets':[sorted(s)for s in color_sets]}
            else:out,rec=render(pair['input'],model,colors,observer=observer)
            teachers.append({'exact':out==pair['output'],'output':out,'record':rec})
            _observe(observer,'model_teacher_return',teacher_index=len(teachers)-1,result=teachers[-1])
        fits=not parameter_failures and all(x['exact']for x in teachers)
        records.append({'model':model,'colors':colors,'fit':fits,'parameter_failures':parameter_failures,'parameter_observations':parameter_observations,'teachers':teachers})
        if fits:retained.append({'model':model,'colors':colors})
        _observe(observer,'model_completed',record=records[-1])
    return retained,records

def consensus(grid,retained):
    returns=[render(grid,tuple(m['model']),tuple(m['colors']))for m in retained]
    if not returns:return None,{'failure':'no_models'}
    if any(out is None for out,rec in returns):return None,{'failure':'retained_model_unresolved','returns':[{'output':o,'record':r}for o,r in returns]}
    if any(out!=returns[0][0]for out,rec in returns):return None,{'failure':'retained_model_disagreement','returns':[{'output':o,'record':r}for o,r in returns]}
    return returns[0][0],{'agreed_models':len(returns),'foreground_preserved':True}
