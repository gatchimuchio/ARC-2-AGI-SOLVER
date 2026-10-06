"""Teacher-only candidate031. Finite grammar is 00-prospective-grammar.json."""
from collections import Counter
from itertools import combinations
from 接続.ARC2.既存物体特徴 import color_components
from 接続.ARC2.既存枠計数 import perimeter_cells
from 接続.ARC2.既存正方形座標 import d4_motif_transform_coord
from 接続.ARC2.既存疎点転写 import shifted_sparse_point_mask
ACTIONS=('copy_exact_mask_preserve_frame','copy_exact_mask_replace_owned_frame')
MODELS=tuple(a+'__'+b for a in ACTIONS for b in ('require_every_corner','only_marked_corners'))
class Hold(Exception): pass

def norm(point,sy,sx):
    transform={(1,1):'rot0',(1,-1):'rot0_flip_h',(-1,1):'rot180_flip_h',(-1,-1):'rot180'}[sy,sx]
    return d4_motif_transform_coord(1,1,transform,*point)

def frame_roles(g,bg,trace):
    h,w=len(g),len(g[0]); roles=[]
    for f in sorted(set(sum(g,[]))-{bg}):
        cells={(r,c) for r,row in enumerate(g) for c,v in enumerate(row) if v==f}
        rr=Counter(r for r,c in cells); cc=Counter(c for r,c in cells)
        rs=[-1]+[r for r in range(h) if rr[r]>=2]+[h]
        cs=[-1]+[c for c in range(w) if cc[c]>=2]+[w]
        rec={'frame_color':f,'row_domain':rs,'col_domain':cs,'rectangles':[],'covers':[]}; trace.append(rec)
        candidates=[]
        for r0,r1 in combinations(rs,2):
            for c0,c1 in combinations(cs,2):
                box=(r0,c0,r1,c1); entry={'bbox':box}; rec['rectangles'].append(entry)
                if r1-r0<2 or c1-c0<2:
                    entry['failure']='empty_geometric_interior'; continue
                visr=[r for r in (r0,r1) if 0<=r<h]; visc=[c for c in (c0,c1) if 0<=c<w]
                if not visr or not visc:
                    entry['failure']='no_two_adjacent_visible_sides';continue
                sides=[{(r,c) for c in range(max(0,c0),min(w-1,c1)+1)} for r in visr]+[{(r,c) for r in range(max(0,r0),min(h-1,r1)+1)} for c in visc]
                if any(len(side&cells)<2 for side in sides):
                    entry['failure']='side_lacks_two_frame_witnesses';continue
                per={p for p in perimeter_cells(box) if 0<=p[0]<h and 0<=p[1]<w}
                if any(g[r][c]==bg for r,c in per):
                    entry['failure']='background_perimeter_gap';continue
                if any(r0<r<r1 and c0<c<c1 for r,c in cells):
                    entry['failure']='interior_contains_frame_color';continue
                entry['candidate_index']=len(candidates); entry['frame_support']=sorted(per&cells)
                candidates.append({'bbox':box,'perimeter':per,'support':per&cells})
        nodes=0
        def visit(covered,owned,chosen):
            nonlocal nodes
            nodes+=1
            if nodes>100000:raise Hold('exact_cover_resource_limit')
            if covered==cells:
                rec['covers'].append(chosen);return
            p=min(cells-covered)
            for idx,can in enumerate(candidates):
                if p in can['support'] and not (can['perimeter']&owned):
                    visit(covered|can['support'],owned|can['perimeter'],chosen+[idx])
        visit(set(),set(),[]);rec['cover_nodes']=nodes
        for indices in rec['covers']:
            roles.append({'color':f,'frames':[candidates[i] for i in indices],'candidate_indices':indices})
    return roles

def render(g,model):
    record={'model':model,'frame_roles':[],'decoration_components':[],'output':None}
    try:
        if model not in MODELS:raise Hold('unknown_model')
        action,activation=model.split('__')
        if not isinstance(g,list) or not 1<=len(g)<=30 or not isinstance(g[0],list) or not 1<=len(g[0])<=30 or any(not isinstance(row,list) or len(row)!=len(g[0]) or any(type(v)!=int or not 0<=v<=9 for v in row) for row in g):raise Hold('invalid_arc_grid')
        h,w=len(g),len(g[0]);counts=Counter(sum(g,[]));top=counts.most_common()
        if len(top)>1 and top[0][1]==top[1][1]:raise Hold('background_tie')
        bg=top[0][0];record['background']=bg
        roles=frame_roles(g,bg,record['frame_roles']);record['raw_role_count']=len(roles)
        if len(roles)!=1:raise Hold('frame_color_or_cover_not_unique')
        role=roles[0];f=role['color'];frames=role['frames'];record['frame_color']=f;record['frames']=[x['bbox'] for x in frames]
        for comp in color_components(g,f,include_diagonal=True):
            owners=[i for i,frame in enumerate(frames) if comp['cells']<=frame['perimeter']]
            if len(owners)!=1:raise Hold('whole_frame_component_ownership')
        corners=[]
        for fi,frame in enumerate(frames):
            r0,c0,r1,c1=frame['bbox']
            corners.extend({'point':(r,c),'sign':(sy,sx),'frame':fi} for r,sy in [(r0,1),(r1,-1)] for c,sx in [(c0,1),(c1,-1)] if 0<=r<h and 0<=c<w)
        patches={i:[] for i in range(len(corners))}
        for color in sorted(set(sum(g,[]))-{bg,f}):
            for comp in color_components(g,color,include_diagonal=True):
                entry={'color':color,'cells':sorted(comp['cells']),'pixel_corner_candidates':[]};record['decoration_components'].append(entry)
                owners=set()
                for r,c in sorted(comp['cells']):
                    ds=[max(abs(r-z['point'][0]),abs(c-z['point'][1])) for z in corners]
                    found=[i for i,d in enumerate(ds) if d==min(ds)]
                    entry['pixel_corner_candidates'].append([r,c,found])
                    if len(found)!=1:raise Hold('decoration_nearest_corner_tie')
                    owners.add(found[0])
                if len(owners)!=1:raise Hold('whole_decoration_component_crosses_corners')
                owner=next(iter(owners)); entry['owner']=owner
                cr,cc=corners[owner]['point'];sy,sx=corners[owner]['sign']
                entry['local_mask']=sorted(norm((r-cr,c-cc),sy,sx) for r,c in comp['cells'])
                patches[owner].append(entry)
        record['corners']=corners
        if any(len(p)>1 for p in patches.values()):raise Hold('corner_has_multiple_whole_decorations')
        if activation=='require_every_corner' and any(not p for p in patches.values()):raise Hold('corner_not_exactly_one_whole_decoration')
        record['inactive_corners']=[i for i,p in patches.items() if not p]
        active={i:p for i,p in patches.items() if p}
        complete=[e[0] for e in active.values() if len(e[0]['cells'])>1]
        record['complete_samples']=[e['owner'] for e in complete]
        if not complete:raise Hold('no_complete_sample')
        masks={tuple(e['local_mask']) for e in complete}
        if len(masks)!=1:raise Hold('complete_samples_disagree')
        mask=set(next(iter(masks)));record['common_mask']=sorted(mask)
        if any(not set(e[0]['local_mask'])<=mask for e in active.values()):raise Hold('singleton_not_subset')
        proposals={};record['proposals']=[]
        for ci,corner in enumerate(corners):
            if ci not in active:continue
            color=patches[ci][0]['color'];r,c=corner['point'];sy,sx=corner['sign']
            local={norm(p,sy,sx) for p in mask}
            target=shifted_sparse_point_mask(local,r,c,h,w)
            if target is None:raise Hold('whole_mask_out_of_bounds')
            for rr,cc in sorted(target):
                if (rr,cc) in proposals:raise Hold('different_corner_proposal_ownership_overlap')
                if any(i!=corner['frame'] and (rr,cc) in fr['perimeter'] for i,fr in enumerate(frames)):raise Hold('foreign_frame_perimeter')
                old=g[rr][cc]
                if old==f and (action=='copy_exact_mask_preserve_frame' or (rr,cc) not in frames[corner['frame']]['perimeter']):raise Hold('frame_preservation')
                if old not in {bg,f,color}:raise Hold('known_decoration_conflict')
                proposals[rr,cc]=(color,ci)
                record['proposals'].append([rr,cc,color,ci])
        out=[row[:] for row in g]
        for (r,c),(color,ci) in proposals.items():out[r][c]=color
        if out==g:raise Hold('no_change')
        record['output']=out;record['status']='PASS';record['changed_count']=sum(a!=b for x,y in zip(g,out) for a,b in zip(x,y));return out,record
    except Hold as e:
        record['status']='HOLD';record['failure']=str(e);return None,record
