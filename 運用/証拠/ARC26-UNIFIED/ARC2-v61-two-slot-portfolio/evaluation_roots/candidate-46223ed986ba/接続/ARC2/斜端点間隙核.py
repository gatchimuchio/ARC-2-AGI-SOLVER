"""Local interrupted-endpoint ownership for diagonal strokes.
Reuses existing component/segment/direction primitives. A cardinal strand may own a diagonal stroke only at a shared endpoint
whose forward cardinal neighbor is immediately empty. Unowned diagonal deletion is an explicit optional prior; conservative
handling of attached unowned strokes is HOLD.
"""
from collections import Counter
from 接続.ARC2.既存物体特徴 import color_components
from 接続.ARC2.既存領域転写 import ORTHOGONAL_DIRECTIONS
from 接続.ARC2.既存疎点転写 import straight_octilinear_segment
from 接続.ARC2.十字曲線教材 import valid_grid


def inspect(grid):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_grid'}
    counts=Counter(v for row in grid for v in row)
    if len(counts)!=2 or len([v for v,n in counts.items() if n==max(counts.values())])!=1:
        return None, {'failure':'two_colors_unique_background_required'}
    bg=max(counts,key=counts.get); fg=next(v for v in counts if v!=bg)
    components=color_components(grid,fg,False)
    support=set().union(*(c['cells'] for c in components))
    adjacency={p:set() for p in support}
    for r,c in support:
        for dr,dc in ((1,1),(1,-1)):
            q=r+dr,c+dc
            if q in support and (r+dr,c) not in support and (r,c+dc) not in support:
                adjacency[(r,c)].add(q); adjacency[q].add((r,c))
    unseen={p for p,ns in adjacency.items() if ns}; strokes=[]
    while unseen:
        todo=[min(unseen)]; cells=set()
        while todo:
            p=todo.pop()
            if p in cells: continue
            cells.add(p); todo.extend(adjacency[p]-cells)
        unseen-=cells
        endpoints=sorted(p for p in cells if len(adjacency[p])==1)
        if len(endpoints)!=2 or any(len(adjacency[p])>2 for p in cells) or straight_octilinear_segment(*endpoints)!=cells:
            return None,{'failure':'nonlinear_diagonal_component','cells':sorted(cells)}
        strokes.append((cells,endpoints))
    if not strokes: return None,{'failure':'no_slanted_strokes'}
    return (bg,fg,support,strokes),{'component_sizes':[c['size'] for c in components]}


def candidates(grid,support,cells,endpoints):
    h,w=len(grid),len(grid[0]); all_candidates=[]
    for root in endpoints:
        tip=next(p for p in endpoints if p!=root)
        signs=((tip[0]>root[0])-(tip[0]<root[0]),(tip[1]>root[1])-(tip[1]<root[1]))
        # Ownership is local to the shared diagonal/cardinal endpoint.
        # All input foreground remains present in support, including junctions.
        for axis in (0,1):
            step=(signs[0],0) if axis==0 else (0,signs[1])
            reverse=(root[0]-step[0],root[1]-step[1])
            forward=(root[0]+step[0],root[1]+step[1])
            if reverse not in support or reverse in cells-{root} or forward in support:
                continue
            gap=[];p=forward
            while 0<=p[0]<h and 0<=p[1]<w and p not in support:
                gap.append(p);p=p[0]+step[0],p[1]+step[1]
            if p not in support or p in cells or not gap: continue
            all_candidates.append({'root':root,'axis':axis,'gap':gap,'erase':sorted(cells-{root})})
    return all_candidates


def render(grid,policy='hold_attached'):
    if policy not in ('hold_attached','delete_unowned'):
        return None, {'failure':'unknown_policy'}
    parsed,record=inspect(grid)
    if parsed is None: return None,record
    bg,fg,support,strokes=parsed; removed=set();added=set(); traces=[]; failure=None
    for cells,endpoints in strokes:
        choices=candidates(grid,support,cells,endpoints)
        retained=choices
        signatures={(tuple(x['erase']),tuple(x['gap'])) for x in retained}
        trace={'cells':sorted(cells),'candidates':choices,'retained':retained}
        if not choices:
            attachments=[p for p in cells if any((p[0]+dr,p[1]+dc) in support-cells for dr,dc in ORTHOGONAL_DIRECTIONS)]
            trace['attachments']=attachments
            if attachments and policy=='hold_attached': failure='attached_stroke_without_supported_gap'
            else: removed|=cells
        elif len(signatures)!=1:
            failure='contact_candidates_disagree'
        else:
            er,gap=next(iter(signatures));removed.update(er);added.update(gap)
        traces.append(trace)
    record.update(strokes=traces,policy=policy)
    if failure: return None,dict(record,failure=failure)
    if removed&added: return None,dict(record,failure='write_conflict')
    out=[row[:] for row in grid]
    for r,c in removed:out[r][c]=bg
    for r,c in added:out[r][c]=fg
    return out,dict(record,removed=sorted(removed),added=sorted(added),failure=None)


def fit(teachers):
    evidence=[];models=[]
    for policy in ('hold_attached','delete_unowned'):
        trials=[render(pair['input'],policy) for pair in teachers]
        fits=[out==pair['output'] for (out,_),pair in zip(trials,teachers)]
        evidence.append({'policy':policy,'teacher_fit':fits,'records':[r for _,r in trials]})
        if all(fits):models.append(policy)
    return {'version':1,'policies':models},evidence


def predict(grid,model):
    if type(model)!=dict or model.get('version')!=1 or not model.get('policies') or any(p not in ('hold_attached','delete_unowned') for p in model['policies']):
        return None,{'failure':'invalid_or_empty_model'}
    trials=[render(grid,p) for p in model['policies']]
    if any(out is None for out,_ in trials):return None,{'failure':'retained_failure','records':[r for _,r in trials]}
    if any(out!=trials[0][0] for out,_ in trials):return None,{'failure':'retained_disagreement','records':[r for _,r in trials]}
    return trials[0][0],{'failure':None,'records':[r for _,r in trials]}
