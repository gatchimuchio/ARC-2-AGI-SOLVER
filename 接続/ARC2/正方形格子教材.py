"""全seed整合格子写像の新しい組合せ。既存component/square/D4のみ再利用。"""
from __future__ import annotations
from collections import Counter
from .既存物体特徴 import color_component_dicts_for_grid
from .既存正方形座標 import solid_square_component, d4_motif_transform_coord
MODELS=tuple(f'rot{angle}{suffix}' for angle in (0,90,180,270) for suffix in ('','_flip_h'))

def parse_input(grid):
    if not isinstance(grid,list) or not 1<=len(grid)<=30 or not all(isinstance(row,list) for row in grid):
        return None,{'failure':'invalid_grid'}
    width=len(grid[0])
    if not 1<=width<=30 or any(len(row)!=width for row in grid) or any(type(v)is not int or not 0<=v<=9 for row in grid for v in row):
        return None,{'failure':'invalid_grid'}
    counts=Counter(v for row in grid for v in row)
    leaders=[c for c,n in counts.items() if n==max(counts.values())]
    if len(leaders)!=1:return None,{'failure':'background_tie'}
    bg=leaders[0]
    comps=[c for color in sorted(counts) if color!=bg for c in color_component_dicts_for_grid(grid,color,False)]
    comps.sort(key=lambda c:(c['bbox'],c['color']))
    if not comps or not all(solid_square_component(c) for c in comps):return None,{'failure':'not_all_solid_squares'}
    sizes=sorted({c['bbox'][2]-c['bbox'][0]+1 for c in comps})
    if len(sizes)!=2:return None,{'failure':'not_two_square_sizes','sizes':sizes}
    a,b=sizes
    small=[c for c in comps if c['bbox'][2]-c['bbox'][0]+1==a]
    big=[c for c in comps if c['bbox'][2]-c['bbox'][0]+1==b]
    if len(big)<2:return None,{'failure':'too_few_seeds','seed_count':len(big)}
    axes=[sorted({c['bbox'][axis]for c in small})for axis in (0,1)]
    pitches=[]
    for values in axes:
        diffs={y-x for x,y in zip(values,values[1:])}
        if len(values)<2 or len(diffs)!=1:return None,{'failure':'source_axis_not_uniform','axes':axes}
        pitches.append(next(iter(diffs)))
    pattern=[((c['bbox'][0]-axes[0][0])//pitches[0],(c['bbox'][1]-axes[1][0])//pitches[1],c['color'])for c in small]
    seeds=[(c['bbox'][0],c['bbox'][1],c['color'])for c in big]
    parsed={'background':bg,'small_side':a,'large_side':b,'source_pitch':pitches,
            'pattern_shape':[len(axes[0]),len(axes[1])],'pattern':pattern,'seeds':seeds,
            'source_cells':set().union(*(c['cells']for c in small))}
    rec={k:v for k,v in parsed.items()if k!='source_cells'}
    rec.update(source_count=len(small),seed_count=len(big),component_count=len(comps))
    return parsed,rec

def seed_parameters(parsed,model):
    h,w=parsed['pattern_shape']
    pattern=[(*d4_motif_transform_coord(h,w,model,r,c),color)for r,c,color in parsed['pattern']]
    lookup={(r,c):color for r,c,color in pattern}
    first_r,first_c,first_color=parsed['seeds'][0]
    params=set()
    for pitch in range(parsed['large_side'],31):
        for r,c,color in pattern:
            if color!=first_color:continue
            dr,dc=first_r-pitch*r,first_c-pitch*c
            valid=True
            for sr,sc,scolor in parsed['seeds']:
                qr,rr=divmod(sr-dr,pitch);qc,rc=divmod(sc-dc,pitch)
                if rr or rc or lookup.get((qr,qc))!=scolor:
                    valid=False;break
            if valid:params.add((pitch,dr,dc))
    return pattern,sorted(params)

def render_parameter(grid,parsed,pattern,param):
    pitch,dr,dc=param;b=parsed['large_side'];bg=parsed['background']
    h,w=len(grid),len(grid[0]);proposals={}
    for r,c,color in pattern:
        row,col=dr+pitch*r,dc+pitch*c
        if row<0 or col<0 or row+b>h or col+b>w:
            return None,{'failure':'out_of_bounds','origin':[row,col]}
        for rr in range(row,row+b):
            for cc in range(col,col+b):
                cell=(rr,cc)
                if cell in parsed['source_cells']:return None,{'failure':'source_overlap','cell':[rr,cc]}
                if cell in proposals and proposals[cell]!=color:return None,{'failure':'proposal_colour_conflict','cell':[rr,cc]}
                if grid[rr][cc] not in (bg,color):return None,{'failure':'foreground_change','cell':[rr,cc]}
                proposals[cell]=color
    output=[row[:]for row in grid]
    for (r,c),color in proposals.items():output[r][c]=color
    if any(grid[r][c]!=bg and output[r][c]!=grid[r][c]for r in range(h)for c in range(w)):
        return None,{'failure':'foreground_not_preserved'}
    return output,{'proposal_cells':len(proposals),'added_cells':sum(output[r][c]!=grid[r][c]for r in range(h)for c in range(w))}

def render_model(grid,model):
    if model not in MODELS:return None,{'failure':'invalid_model'}
    parsed,rec=parse_input(grid)
    if parsed is None:return None,rec
    pattern,params=seed_parameters(parsed,model)
    rec=dict(rec,model=model,seed_parameters=[list(p)for p in params],seed_parameter_count=len(params))
    if not params:return None,dict(rec,failure='no_seed_consistent_parameters')
    outputs={};details=[];failures=0
    for param in params:
        output,detail=render_parameter(grid,parsed,pattern,param)
        details.append(dict(detail,parameter=list(param)))
        if output is None:failures+=1
        else:outputs[tuple(map(tuple,output))]=output
    rec.update(parameter_records=details,failed_parameters=failures,distinct_output_count=len(outputs))
    if failures:return None,dict(rec,failure='seed_consistent_parameter_failed')
    if len(outputs)!=1:return None,dict(rec,failure='seed_parameter_grids_disagree')
    output=next(iter(outputs.values()))
    if output==grid:return None,dict(rec,failure='consensus_no_change')
    return output,rec

def fit_models(train):
    if len(train)<2:return None,{'failure':'too_few_teachers'}
    keys=[tuple(map(tuple,p['input']))for p in train]
    if len(set(keys))!=len(keys):return None,{'failure':'duplicate_teacher_inputs'}
    retained=[];records={};model_fits={}
    for model in MODELS:
        observations=[];fits=[]
        for pair in train:
            output,record=render_model(pair['input'],model)
            observations.append(record);fits.append(output is not None and output==pair['output'])
        records[model]=observations;model_fits[model]=fits
        if all(fits):retained.append(model)
    rec={'models':retained,'teacher_records':records,'pair_fits':model_fits}
    return (tuple(retained)if retained else None),rec

def consensus(grid,models):
    if not models:return None,{'failure':'no_fitted_models'}
    results=[render_model(grid,model)for model in models]
    rec={'models':list(models),'model_records':[r for _,r in results]}
    if any(out is None for out,_ in results):return None,dict(rec,failure='retained_model_unresolved')
    first=results[0][0]
    if any(out!=first for out,_ in results):return None,dict(rec,failure='retained_model_grids_disagree')
    return first,rec

class 正方形格子教材:
    def __init__(self, 教師群):
        self.モデル, _ = fit_models(教師群)

    def 候補(self, 格子, _policy):
        if not self.モデル:
            return None, {"failure": "全教師を再現する正方形格子写像なし"}
        return consensus(格子, self.モデル)

    def 記録(self):
        return {"全教師共通モデル": list(self.モデル or ())}
