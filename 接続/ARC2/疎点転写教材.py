"""全教師適合表を保持し、元の疎点転写出力だけを同じHDSへ渡す。"""
from __future__ import annotations
from collections import Counter,defaultdict
from itertools import product
from .既存疎点転写 import (sparse_point_color_points,sparse_point_base_shape,sparse_point_incident_shape,
    shifted_sparse_point_mask,sparse_point_rule_key,sparse_point_copy_defaults,
    infer_sparse_octilinear_point_graph_policy,render_sparse_octilinear_point_graph_completion)
TABLE_BUDGET=4096

def valid_grid(grid):
    return(isinstance(grid,list)and 1<=len(grid)<=30 and isinstance(grid[0],list)and 1<=len(grid[0])<=30
           and all(isinstance(row,list)and len(row)==len(grid[0])and all(type(v)is int and 0<=v<=9 for v in row)for row in grid))

def inspect_input(grid):
    if not valid_grid(grid):return None,{'failure':'invalid_arc_grid'}
    counts=Counter(v for row in grid for v in row);leaders=[v for v,n in counts.items()if n==max(counts.values())]
    if len(leaders)!=1:return None,{'failure':'background_tie'}
    bg=leaders[0];points=sparse_point_color_points(grid,bg);height,width=len(grid),len(grid[0]);active=sum(map(len,points.values()))
    if not points or active>25:return None,{'failure':'original_point_domain','active':active}
    bases={};infos={};base_proposals=defaultdict(set);base_records=[]
    for color,ps in points.items():
        if len(ps)<2:continue
        mask,info=sparse_point_base_shape(ps);bases[color]=mask;infos[color]=info
        if info['kind']=='closed_cycle':
            n=len(ps);sr=sum(r for r,c in ps);sc=sum(c for r,c in ps);vectors=[(n*r-sr,n*c-sc)for r,c in sorted(ps)]
            if (0,0)in vectors:return None,{'failure':'cycle_centroid_point','color':color}
            if any(a*d==b*c and a*c+b*d>0 for i,(a,b)in enumerate(vectors)for c,d in vectors[i+1:]):
                return None,{'failure':'cycle_polar_ray_tie','color':color}
        if not ps<=mask:return None,{'failure':'base_lost_input_points','color':color}
        for p in mask:base_proposals[p].add(color)
        base_records.append({'color':color,'kind':info['kind'],'input_points':len(ps),'base_pixels':len(mask)})
    if not bases:return None,{'failure':'no_base_source'}
    conflicts=[(p,sorted(v))for p,v in sorted(base_proposals.items())if len(v)>1]
    if conflicts:return None,{'failure':'base_colour_conflict','conflicts':conflicts}
    occupied=set(base_proposals);singletons=[]
    for color,ps in sorted(points.items()):
        if len(ps)!=1:continue
        singleton=next(iter(ps));anchors=[]
        for source,source_points in sorted(points.items()):
            if len(source_points)<2:continue
            for anchor in sorted(source_points):
                dr,dc=singleton[0]-anchor[0],singleton[1]-anchor[1]
                if max(abs(dr),abs(dc))<=1:anchors.append((source,anchor,dr,dc))
        if len(anchors)!=1:return None,{'failure':'physical_anchor_not_unique','color':color,'anchor_count':len(anchors)}
        source,anchor,dr,dc=anchors[0];kind=infos[source]['kind'];masks={}
        for typ,mask in [('full',bases[source]),('incident',sparse_point_incident_shape(infos[source],anchor))]:
            shifted=shifted_sparse_point_mask(mask,dr,dc,height,width)
            if shifted is None:return None,{'failure':'copy_type_out_of_bounds','color':color,'type':typ}
            masks[typ]=(shifted-occupied)|{singleton}
        singletons.append({'color':color,'source_color':source,'anchor':anchor,'offset':(dr,dc),'source_kind':kind,
                           'key':sparse_point_rule_key(dr,dc,kind),'masks':masks})
    record={'background':bg,'active_points':active,'bases':base_records,'singleton_count':len(singletons),
            'observed_keys':sorted({s['key']for s in singletons})}
    return {'background':bg,'points':points,'bases':bases,'base_proposals':base_proposals,'singletons':singletons},record

def certify_model(grid,rules):
    if not valid_grid(grid):return None,{'failure':'invalid_arc_grid'}
    defaults=sparse_point_copy_defaults(rules)
    raw,raw_record=render_sparse_octilinear_point_graph_completion(grid,rules,sparse_point_copy_defaults=defaults)
    if raw is None:return None,{'failure':'original_model_unresolved','raw_record':raw_record}
    parsed,record=inspect_input(grid)
    if parsed is None:return None,record
    proposals=defaultdict(set,{p:set(v)for p,v in parsed['base_proposals'].items()});singletons=[];observations=[];resolutions=[]
    for s in parsed['singletons']:
        if s['key']in rules:
            typ=rules[s['key']];resolution='exact_rule'
        elif s['masks']['full']==s['masks']['incident']:
            typ='full';resolution='input_mask_agreement'
        elif s['source_kind']in defaults:
            typ=defaults[s['source_kind']];resolution='table_derived_default'
        else:return None,dict(record,failure='unresolved_copy_type',color=s['color'],key=s['key'])
        if typ not in s['masks']:return None,dict(record,failure='invalid_rule_type')
        mask=s['masks'][typ]
        for p in mask:proposals[p].add(s['color'])
        observations.append({'rule_key':s['key'],'copy_type':typ})
        singletons.append({'color':s['color'],'copy_type':typ,'source_color':s['source_color'],'source_kind':s['source_kind'],
                           'offset':list(s['offset']),'cell_count':len(mask)})
        resolutions.append({'color':s['color'],'key':s['key'],'resolution':resolution,'type':typ})
    conflicts=[(p,sorted(v))for p,v in sorted(proposals.items())if len(v)>1]
    if conflicts:return None,dict(record,failure='simultaneous_colour_conflict',conflicts=conflicts)
    bg=parsed['background'];expected=[[bg for _ in row]for row in grid]
    for (r,c),values in proposals.items():expected[r][c]=next(iter(values))
    if any(expected[r][c]!=v for r,row in enumerate(grid)for c,v in enumerate(row)if v!=bg):
        return None,dict(record,failure='original_foreground_overwritten')
    expected_record={'renderer_case':'sparse_octilinear_point_graph_completion','sparse_point_background_color':bg,
                     'sparse_point_color_count':len(parsed['points']),'sparse_point_source_color_count':len(parsed['bases']),
                     'sparse_point_rule_observations':observations,'sparse_point_singleton_records':singletons,
                     'sparse_point_singleton_copy_count':len(singletons),'sparse_point_edge_cell_count':sum(map(len,parsed['bases'].values())),
                     'sparse_point_completed_cell_count':len(proposals)-record['active_points']}
    if raw!=expected or raw_record!=expected_record:return None,dict(record,failure='original_grid_or_record_disagreement')
    record.update(raw_record=raw_record,resolutions=resolutions,added_pixels=len(proposals)-record['active_points'])
    return raw,record

def fit_teachers(teachers):
    if len(teachers)<2 or any(not valid_grid(p['input'])or not valid_grid(p['output'])for p in teachers):
        return None,{'failure':'insufficient_or_invalid_teachers'}
    if len({tuple(map(tuple,p['input']))for p in teachers})!=len(teachers):return None,{'failure':'duplicate_teacher_inputs'}
    policy,policy_record=infer_sparse_octilinear_point_graph_policy(teachers);record={'raw_policy':policy,'policy_record':policy_record}
    if policy is None:return None,dict(record,failure='original_policy_unresolved')
    rules=policy['sparse_point_copy_rules'];defaults=policy['sparse_point_copy_defaults']
    raw=[render_sparse_octilinear_point_graph_completion(p['input'],rules,sparse_point_copy_defaults=defaults)for p in teachers]
    record['raw_records']=[r for _,r in raw];record['raw_pair_fits']=[out is not None and out==p['output']for(out,_),p in zip(raw,teachers)]
    if not all(record['raw_pair_fits']):return None,dict(record,failure='original_teacher_reproduction_failed')
    inspections=[inspect_input(p['input'])for p in teachers];record['input_records']=[r for _,r in inspections]
    if any(x is None for x,_ in inspections):return None,dict(record,failure='teacher_input_certificate_failed')
    keys=sorted({s['key']for parsed,_ in inspections for s in parsed['singletons']});total=2**len(keys)
    record.update(observed_keys=keys,table_count=total,table_budget=TABLE_BUDGET)
    if set(keys)!=set(rules):return None,dict(record,failure='original_observed_key_coverage_disagreement')
    if total>TABLE_BUDGET:return None,dict(record,failure='table_enumeration_budget_exceeded',enumeration_complete=False)
    models=[]
    for values in product(('full','incident'),repeat=len(keys)):
        table=dict(zip(keys,values));table_defaults=sparse_point_copy_defaults(table)
        if all(render_sparse_octilinear_point_graph_completion(p['input'],table,sparse_point_copy_defaults=table_defaults)[0]==p['output']for p in teachers):
            models.append(table)
    record.update(enumeration_complete=True,models=models,defaults=[sparse_point_copy_defaults(m)for m in models])
    if not models or rules not in models:return None,dict(record,failure='original_policy_missing_from_models')
    certified=[]
    for table in models:
        results=[certify_model(p['input'],table)for p in teachers];certified.append([r for _,r in results])
        if any(out is None or out!=p['output']for(out,_),p in zip(results,teachers)):
            return None,dict(record,failure='retained_teacher_model_certificate_failed',certificate_records=certified)
    record['teacher_model_records']=certified
    return {'original_rules':rules,'models':models},record

def guarded_render(grid,fitted):
    if not valid_grid(grid):return None,{'failure':'invalid_arc_grid'}
    models=fitted.get('models',[]);original=fitted.get('original_rules')
    if not models or len(models)>TABLE_BUDGET or original not in models:return None,{'failure':'invalid_fitted_models'}
    original_grid,original_record=render_sparse_octilinear_point_graph_completion(grid,original,sparse_point_copy_defaults=sparse_point_copy_defaults(original))
    if original_grid is None:return None,{'failure':'original_learned_renderer_unresolved','raw_record':original_record}
    results=[certify_model(grid,table)for table in models];record={'model_count':len(models),'model_records':[r for _,r in results]}
    if any(out is None for out,_ in results):return None,dict(record,failure='retained_model_unresolved')
    if any(out!=original_grid for out,_ in results):return None,dict(record,failure='retained_model_grids_disagree')
    record['added_pixels']=results[0][1]['added_pixels']
    return original_grid,record

class 疎点転写教材:
    def __init__(self, 教師群):
        self.モデル, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if self.モデル is None:
            return None, {"failure": "全教師を再現する疎点転写規則なし"}
        return guarded_render(格子, self.モデル)

    def 記録(self):
        return {"全教師共通規則表": self.モデル}
