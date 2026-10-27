"""Compose existing object extraction, congruence, and lossless edge placement.
No task identifiers, output constants, teacher access in render, or query fitting.
"""
from collections import Counter
from itertools import product
from copy import deepcopy
from 接続.ARC2.既存物体特徴 import color_components
from 接続.ARC2.既存正方形座標 import d4_motif_transform_coord
from 接続.ARC2.物体端投射 import 配置する

GROUPS = {'identity': ('rot0',), 'rotations': tuple('rot'+str(r) for r in (0,90,180,270)),
          'd4': tuple('rot'+str(r)+s for r in (0,90,180,270) for s in ('','_flip_h'))}
PROGRAMS = tuple(product((4,8), GROUPS, (False,True), ('vertical','horizontal'), ('top','bottom')))

def valid(g):
    return isinstance(g,list) and 1<=len(g)<=30 and all(isinstance(r,list) and 1<=len(r)<=30 and len(r)==len(g[0]) and all(type(c)is int and 0<=c<=9 for c in r) for r in g)

def render(grid, model):
    record={'model':model,'objects':[],'pairs':[],'complete':False}
    try:
        if not valid(grid) or model not in PROGRAMS:
            record.update(complete=True,failure='invalid_input_or_program');return None,record
        connectivity,group,colored,axis,peer_side=model
        g=deepcopy(grid) if axis=='vertical' else [list(x) for x in zip(*grid)]
        counts=Counter(c for r in g for c in r)
        modes=sorted(c for c,n in counts.items() if n==max(counts.values()))
        record['backgrounds']=modes
        if len(modes)!=1:
            record.update(complete=True,failure='ambiguous_background');return None,record
        bg=modes[0]
        objects=[]
        for c in sorted(counts):
            if c!=bg: objects.extend(color_components(g,c,include_diagonal=connectivity==8))
        objects.sort(key=lambda o:(o['bbox'],o['color']))
        record['objects']=[dict(color=o['color'],bbox=o['bbox'],cells=sorted(o['cells'])) for o in objects]
        if not objects:
            record.update(complete=True,failure='no_objects');return None,record
        peer=[False]*len(objects)
        for i,a in enumerate(objects):
            r0,c0,r1,c1=a['bbox'];h,w=r1-r0+1,c1-c0+1
            for j,b in enumerate(objects):
                if i==j: continue
                target={(r-b['bbox'][0],c-b['bbox'][1]) for r,c in b['cells']}
                comparisons=[]
                entry={'source':i,'target':j,'comparisons':comparisons}
                record['pairs'].append(entry)
                for t in GROUPS[group]:
                    shape={d4_motif_transform_coord(h,w,t,r-r0,c-c0) for r,c in a['cells']}
                    match=shape==target and (not colored or a['color']==b['color'])
                    comparisons.append({'transform':t,'matches':match})
                    peer[i]=peer[i] or match
        sides=[peer_side if p else ('bottom' if peer_side=='top' else 'top') for p in peer]
        record.update(peer_roles=peer,sides=sides)
        out=配置する(g,objects,sides)
        if out is not None and axis=='horizontal':out=[list(x) for x in zip(*out)]
        record.update(complete=True,failure=None if out is not None else 'placement_collision_or_loss')
        return out,record
    except BaseException as e:
        e.peer_edge_record=record
        raise

def fit(teachers,observer=None):
    records=[];models=[]
    if not isinstance(teachers,list) or len(teachers)<2 or any(not isinstance(p,dict) or not valid(p.get('input')) or not valid(p.get('output')) for p in teachers):
        return (),{'complete':True,'failure':'invalid_or_insufficient_teachers','models':records}
    if len({tuple(map(tuple,p['input'])) for p in teachers})<2:
        return (),{'complete':True,'failure':'insufficient_distinct_teachers','models':records}
    try:
        for m in PROGRAMS:
            entry={'model':m,'returns':[]};records.append(entry)
            for p in teachers:
                out,detail=render(p['input'],m)
                row={'output':out,'record':detail,'exact':out==p['output']}
                entry['returns'].append(row)
                if observer:observer(row)
            entry['eligible']=all(r['exact'] for r in entry['returns'])
            if entry['eligible']:models.append(m)
        return tuple(models),{'complete':True,'models':records,'retained_count':len(models)}
    except BaseException as e:
        e.peer_edge_fit_prefix=records
        raise

def predict(grid,models,observer=None):
    rows=[]
    if not isinstance(models,tuple) or not models or any(m not in PROGRAMS for m in models) or len(set(models))!=len(models):
        return None,{'complete':True,'failure':'invalid_or_empty_model_set','returns':rows}
    try:
        for m in models:
            out,detail=render(grid,m);row={'model':m,'output':out,'record':detail};rows.append(row)
            if observer:observer(row)
        reason='retained_model_failed' if any(r['output'] is None for r in rows) else 'retained_models_disagree' if any(r['output']!=rows[0]['output'] for r in rows) else None
        return (None if reason else deepcopy(rows[0]['output'])),{'complete':True,'failure':reason,'returns':rows}
    except BaseException as e:
        e.peer_edge_predict_prefix=rows
        raise
