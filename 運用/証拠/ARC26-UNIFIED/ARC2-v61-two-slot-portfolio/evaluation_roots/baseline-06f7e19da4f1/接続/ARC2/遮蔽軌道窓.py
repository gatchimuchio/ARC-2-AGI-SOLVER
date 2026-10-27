"""Pure masked view of the accepted two-axis completion, with local orbit binding.

No dataset access. Reconstructs the unavailable old rectangular-mask wrapper.
New prior: an unwitnessed rectangular set of folded orbits is a translated copy
of an observed local rectangle. All inclusion-maximal contexts and all matching
donors must agree. Size, phase, displacement, palette and axes are not constants.
"""
from 接続.ARC2.二軸補完教材 import valid_grid, fit_teachers, guarded_render
from 接続.ARC2.既存配置展開 import crop_bbox


def observe(grid):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_grid'}
    roles=[]
    for color in sorted({v for row in grid for v in row}):
        cells=[(r,c) for r,row in enumerate(grid) for c,v in enumerate(row) if v==color]
        a=min(r for r,c in cells); b=max(r for r,c in cells)
        l=min(c for r,c in cells); u=max(c for r,c in cells)
        if b>a and u>l and len(cells)==(b-a+1)*(u-l+1):
            roles.append((color,(a,l,b,u)))
    if len(roles)!=1:
        return None, {'failure':'mask_role_not_unique','roles':roles}
    mask,box=roles[0]
    colors=sorted({v for row in grid for v in row}-{mask})
    if len(colors)<2:
        return None, {'failure':'insufficient_pattern_colors'}
    encode={v:i+1 for i,v in enumerate(colors)}
    g=[[0 if v==mask else encode[v] for v in row] for row in grid]
    return (g,box,{v:k for k,v in encode.items()},mask), {'mask':mask,'bbox':box}


def local_bind(fold):
    """Complete one rectangular unwitnessed support; retain every maximal context."""
    h,w=len(fold),len(fold[0]); missing=[(r,c) for r,row in enumerate(fold) for c,v in enumerate(row) if v==0]
    if not missing:return {}, {'contexts':[],'missing':[]}
    a=min(r for r,c in missing); b=max(r for r,c in missing)
    l=min(c for r,c in missing); u=max(c for r,c in missing)
    if len(missing)!=(b-a+1)*(u-l+1):
        return None,{'failure':'unwitnessed_support_not_rectangular','missing':missing}
    boxes={}
    for dr in range(1-h,h):
        for dc in range(1-w,w):
            valid=[[False]*w for _ in range(h)]
            for r in range(max(0,-dr),min(h,h-dr)):
                for c in range(max(0,-dc),min(w,w-dc)):
                    donor=fold[r+dr][c+dc]
                    valid[r][c]=donor!=0 and (fold[r][c]==0 or fold[r][c]==donor)
            if not all(valid[r][c] for r,c in missing):continue
            values=tuple(fold[r+dr][c+dc] for r,c in missing)
            for top in range(a+1):
                column=[True]*w
                for bottom in range(top,h):
                    column=[x and y for x,y in zip(column,valid[bottom])]
                    if bottom<b:continue
                    if not all(column[l:u+1]):break
                    left=l;right=u
                    while left>0 and column[left-1]:left-=1
                    while right+1<w and column[right+1]:right+=1
                    if (bottom-top+1)*(right-left+1)==len(missing):continue
                    box=(top,left,bottom,right)
                    boxes.setdefault(box,[]).append((dr,dc,values))
    maximal=[b for b in boxes if not any(a!=b and a[0]<=b[0] and a[1]<=b[1] and a[2]>=b[2] and a[3]>=b[3] for a in boxes)]
    records=[{'bbox':box,'donors':[{'shift':(dr,dc),'values':values} for dr,dc,values in boxes[box]]} for box in sorted(maximal)]
    outputs={values for box in maximal for dr,dc,values in boxes[box]}
    all_contexts=[{'bbox':box,
        'covered_left_range':[box[1],l], 'covered_right_range':[u,box[3]],
        'exclude_empty_context_bbox':(a,l,b,u),
        'donors':[{'shift':(dr,dc),'values':values} for dr,dc,values in boxes[box]],
        'retained_maximal':box in maximal} for box in sorted(boxes)]
    record={'missing':missing,'matching_context_count':len(boxes),
            'all_matching_contexts_compressed':all_contexts,'contexts':records,
            'enumeration_complete':True,
            'compression':'all left/right subrectangles in recorded inclusive ranges; empty context excluded; a strict horizontal extension dominates its subrectangles'}
    if len(outputs)!=1:
        return None,dict(record,failure='maximal_contexts_missing_or_disagree')
    return dict(zip(missing,next(iter(outputs)))),record


def render_encoded(grid,axes,bind=False):
    old,old_record=guarded_render(grid,axes)
    if old is not None or not bind or old_record.get('failure')!='orbit_without_original_witness':
        return old,{'original':old_record}
    h,w=len(grid),len(grid[0]); ar,ac=axes
    if ar<h-1 or ac<w-1:
        return None,{'failure':'fold_has_negative_coordinates','original':old_record}
    fh,fw=ar//2+1,ac//2+1
    fold=[[0]*fw for _ in range(fh)]; sources={}
    for r,row in enumerate(grid):
        for c,v in enumerate(row):
            p=(min(r,ar-r),min(c,ac-c))
            if v:
                if fold[p[0]][p[1]] not in (0,v):
                    return None,{'failure':'known_orbit_conflict','cell':p}
                fold[p[0]][p[1]]=v;sources.setdefault(p,[]).append((r,c,v))
    binding,local=local_bind(fold)
    record={'original':old_record,'fold':fold,'local':local,
            'original_witnesses':[{'orbit':p,'sources':v} for p,v in sorted(sources.items())]}
    if binding is None:return None,dict(record,failure='local_orbit_binding_failed')
    out=[row[:] for row in grid]
    for r,row in enumerate(grid):
        for c,v in enumerate(row):
            p=(min(r,ar-r),min(c,ac-c))
            if not v:out[r][c]=fold[p[0]][p[1]] or binding[p]
    # Reapply the original renderer to the original mask with only newly bound
    # orbits seeded; existing witnessed cells/values are never overwritten.
    seeded=[row[:] for row in grid]
    for r,row in enumerate(grid):
        for c,v in enumerate(row):
            p=(min(r,ar-r),min(c,ac-c))
            if not v and p in binding:seeded[r][c]=binding[p]
    if any(v==0 for row in seeded for v in row):
        checked,guard=guarded_render(seeded,axes);record['seeded_guard']=guard
        if checked!=out:return None,dict(record,failure='original_guard_disagrees')
    if any(v==0 for row in out for v in row):raise AssertionError('incomplete_binding')
    record['bound_orbits']=[{'orbit':p,'value':v} for p,v in sorted(binding.items())]
    return out,record


def predict(grid,model):
    if not isinstance(model,dict) or model.get('version')!=1:
        return None,{'failure':'no_teacher_model'}
    role,rec=observe(grid)
    if role is None:return None,rec
    encoded,box,decode,mask=role
    out,detail=render_encoded(encoded,model['axes'],bind=True)
    rec['completion']=detail
    if out is None:return None,rec
    return [[decode[v] for v in row] for row in crop_bbox(out,box)],rec


def fit(train):
    if not isinstance(train,list) or len(train)<2:return None,{'failure':'too_few_teachers'}
    converted=[]
    for pair in train:
        if not isinstance(pair,dict) or not valid_grid(pair.get('output')):
            return None,{'failure':'invalid_teacher'}
        role,rec=observe(pair.get('input'))
        if role is None:return None,rec
        encoded,box,decode,mask=role;a,l,b,u=box
        if len(pair['output'])!=b-a+1 or len(pair['output'][0])!=u-l+1:
            return None,{'failure':'output_not_mask_crop'}
        encode={v:k for k,v in decode.items()};full=[row[:] for row in encoded]
        for r,row in enumerate(pair['output']):
            for c,v in enumerate(row):
                if v not in encode:return None,{'failure':'output_color_not_observed'}
                full[a+r][l+c]=encode[v]
        converted.append({'input':encoded,'output':full})
    axes,rec=fit_teachers(converted)
    if axes is None:return None,{'failure':'existing_two_axis_fit_failed','axis_fit':rec}
    model={'version':1,'axes':axes['axes']}
    records=[]
    for pair in train:
        out,detail=predict(pair['input'],model);records.append({'exact':out==pair['output'],'detail':detail})
    if not all(x['exact'] for x in records):return None,{'failure':'teacher_mismatch','teachers':records}
    return model,{'axis_fit':rec,'teachers':records,'prior':'all inclusion-maximal observed translation contexts agree on unwitnessed folded orbits'}
