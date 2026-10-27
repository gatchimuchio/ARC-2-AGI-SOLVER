"""全役割と元best全配置を証明し、元格子のみを同じHDSへ渡す。"""
from __future__ import annotations
from collections import Counter
from itertools import permutations,product
from .既存接触配置 import mixed_region_dicts_for_grid,_chiral_payload_slot_groups,_chiral_payload_candidates,_chiral_payload_slot_render

PROOF_STATE_LIMIT=100000

def valid_grid(grid):
    return(isinstance(grid,list)and 1<=len(grid)<=30 and isinstance(grid[0],list)and 1<=len(grid[0])<=30
           and all(isinstance(row,list)and len(row)==len(grid[0])and all(type(v)is int and 0<=v<=9 for v in row)for row in grid))

def certified_groups(grid):
    if not valid_grid(grid):return None,{'failure':'invalid_arc_grid'}
    counts=Counter(v for row in grid for v in row);leaders=[v for v,n in counts.items()if n==max(counts.values())]
    if len(leaders)!=1:return None,{'failure':'background_tie'}
    bg=leaders[0];regions=mixed_region_dicts_for_grid(grid,bg,True);payload_cells=[];groups=[]
    for region in regions:
        cells=set(region['cells']);colors=region['color_counts']
        if len(colors)==2 and min(colors.values())>=2:payload_cells.append(frozenset(cells))
        elif len(colors)==1:groups.append((next(iter(colors)),cells))
        else:return None,{'failure':'unassigned_foreground_component'}
    if not payload_cells or not groups:return None,{'failure':'missing_payload_or_slot'}
    # Synchronous closure over all currently adjacent groups, without placement evidence.
    rounds=0
    while True:
        parent=list(range(len(groups)))
        def root(i):
            while parent[i]!=i:i=parent[i]
            return i
        boxes=[(min(r for r,c in cells),min(c for r,c in cells),max(r for r,c in cells),max(c for r,c in cells))for color,cells in groups]
        for i,(color,cells)in enumerate(groups):
            for j in range(i+1,len(groups)):
                if color!=groups[j][0]:continue
                a,b=boxes[i],boxes[j];rg=max(a[0]-b[2]-1,b[0]-a[2]-1,0);cg=max(a[1]-b[3]-1,b[1]-a[3]-1,0)
                if max(rg,cg)<=1:parent[root(j)]=root(i)
        merged={}
        for i,(color,cells)in enumerate(groups):
            k=root(i)
            if k not in merged:merged[k]=(color,set())
            merged[k][1].update(cells)
        if len(merged)==len(groups):break
        groups=list(merged.values());rounds+=1
    parsed=_chiral_payload_slot_groups(grid)
    if parsed is None:return None,{'failure':'original_groups_unresolved'}
    raw_bg,payloads,slots=parsed
    if raw_bg!=bg or {frozenset(p['cells'])for p in payloads}!=set(payload_cells):
        return None,{'failure':'original_payload_groups_disagree'}
    if {(s['color'],frozenset(s['cells']))for s in slots}!={(color,frozenset(cells))for color,cells in groups}:
        return None,{'failure':'original_slot_closure_disagrees'}
    all_cells=[set(p['cells'])for p in payloads]+[set(s['cells'])for s in slots]
    foreground={(r,c)for r,row in enumerate(grid)for c,v in enumerate(row)if v!=bg}
    if set().union(*all_cells)!=foreground or sum(map(len,all_cells))!=len(foreground):
        return None,{'failure':'foreground_ownership_failed'}
    return parsed,{'background':bg,'physical_regions':len(regions),'payload_count':len(payloads),'slot_group_count':len(slots),'closure_rounds':rounds,'foreground_pixels':len(foreground)}

def assignment_grid(grid,parsed,selected):
    bg,payloads,slots=parsed;h,w=len(grid),len(grid[0]);slot_cells=set().union(*(s['cells']for s in slots));occupied=set();expected=[[bg]*w for _ in range(h)]
    if len(selected)!=len(payloads):return None,'incomplete_assignment'
    for r,c in slot_cells:expected[r][c]=grid[r][c]
    expected_counts=Counter(grid[r][c]for r,c in slot_cells)
    for payload,candidate in zip(payloads,selected):
        r0,c0,r1,c1=payload['bbox'];ph,pw=r1-r0+1,c1-c0+1;index=candidate['transform_index'];tr,tc=candidate['target_origin'];colors=payload['colors']
        if type(index)is not int or not 0<=index<8:return None,'invalid_transform'
        mapped={}
        for r,c in payload['cells']:
            u,v=r-r0,c-c0
            dr,dc=((u,v),(v,ph-1-u),(ph-1-u,pw-1-v),(pw-1-v,u),(u,pw-1-v),(ph-1-u,v),(v,u),(pw-1-v,ph-1-u))[index]
            value=grid[r][c]
            if index>=4:value=colors[1]if value==colors[0]else colors[0]
            mapped[(tr+dr,tc+dc)]=value;expected_counts[value]+=1
        cells=set(mapped)
        if mapped!=candidate['mapped']or cells!=set(candidate['cells'])or len(cells)!=len(payload['cells']):return None,'payload_transform_disagrees'
        if any(not(0<=r<h and 0<=c<w)for r,c in cells):return None,'payload_out_of_bounds'
        if cells&slot_cells:return None,'slot_overwrite'
        if cells&occupied:return None,'payload_overlap'
        occupied.update(cells)
        for(r,c),v in mapped.items():expected[r][c]=v
    actual=Counter(v for row in expected for v in row if v!=bg)
    if actual!=expected_counts:return None,'pixel_accounting_failed'
    source_cells=set().union(*(p['cells']for p in payloads));changed_scope=source_cells|occupied
    if any(expected[r][c]!=v for r,row in enumerate(grid)for c,v in enumerate(row)if(r,c)not in changed_scope):return None,'outside_changed'
    return expected,None

def bounded_certificate(grid):
    parsed,role_record=certified_groups(grid)
    if parsed is None:return None,role_record
    bg,payloads,slots=parsed;h,w=len(grid),len(grid[0]);used=0;complete_count=0;best_count=0;pair_records=[];pair_options={};best_score=None;best_grid=None;best_record=None;bad_best=[];disagree=False
    def charge(n):
        nonlocal used
        used+=n
        if used>PROOF_STATE_LIMIT:raise OverflowError('proof_budget')
    try:
        for i,payload in enumerate(payloads):
            r0,c0,r1,c1=payload['bbox'];ph,pw=r1-r0+1,c1-c0+1
            trials=4*max(0,h-ph+1)*max(0,w-pw+1)+4*max(0,h-pw+1)*max(0,w-ph+1)
            for j,slot in enumerate(slots):
                charge(trials)
                candidates=_chiral_payload_candidates(grid,payload,slot,bg)
                best=max((q['contact_count']for q in candidates),default=None)
                options=[];seen=set()
                for q in candidates:
                    if q['contact_count']!=best:continue
                    key=(q['transform_index'],tuple(q['target_origin']),tuple(sorted(q['mapped'].items())))
                    if key not in seen:seen.add(key);options.append(q)
                pair_options[i,j]=options
                pair_records.append({'payload':i,'slot':j,'placement_trials':trials,'legal_candidates':len(candidates),'max_contact':best,'retained_placements':len(options)})
        # Count every permutation prefix, including assignments with a missing pair.
        n=len(slots);charge(1);prefixes=1
        for depth in range(1,n+1):prefixes*=n-depth+1;charge(prefixes)
        for assignment in permutations(range(n)):
            options=[pair_options[i,j]for i,j in enumerate(assignment)]
            if any(not q for q in options):continue
            # Every product-choice prefix and completed selection counts, even if invalid.
            charge(1);prefixes=1
            for q in options:prefixes*=len(q);charge(prefixes)
            for selected in product(*options):
                complete_count+=1;score=sum(q['contact_count']for q in selected)
                if best_score is not None and score<best_score:continue
                if best_score is None or score>best_score:
                    best_score=score;best_count=0;best_grid=None;best_record=None;bad_best=[];disagree=False
                best_count+=1;expected,issue=assignment_grid(grid,parsed,selected)
                if issue:bad_best.append(issue)
                else:
                    if best_grid is None:best_grid=expected
                    elif best_grid!=expected:disagree=True
                if best_record is None:
                    best_record={'renderer_case':'chiral_payload_slot_transfer','payload_count':len(payloads),'slot_group_count':n,'assignment_score':score,'assignment':list(assignment),'transform_indices':[q['transform_index']for q in selected],'reflection_role_swap_count':sum(q['reflection_role_swap']for q in selected),'event_count':sum(len(p['cells'])for p in payloads)}
    except OverflowError:
        return None,{'failure':'certificate_budget_exhausted','states':used,'limit':PROOF_STATE_LIMIT,'complete_assignments_before_stop':complete_count,'exhausted':False}
    record={'roles':role_record,'pairs':pair_records,'states':used,'limit':PROOF_STATE_LIMIT,'complete_assignments':complete_count,'best_assignments':best_count,'best_score':best_score,'exhausted':True}
    if best_score is None:return None,dict(record,failure='no_complete_assignment')
    if bad_best:return None,dict(record,failure='invalid_best_assignment',best_failures=sorted(set(bad_best)))
    if disagree:return None,dict(record,failure='best_assignment_grids_disagree')
    return(best_grid,best_record),record

def guarded_render(grid):
    certified,record=bounded_certificate(grid)
    if certified is None:return None,record
    expected,expected_record=certified
    raw,raw_record=_chiral_payload_slot_render(grid)
    if raw is None:return None,dict(record,failure='original_renderer_unresolved',raw_record=raw_record)
    if raw!=expected or raw_record!=expected_record:return None,dict(record,failure='original_grid_or_record_disagreement')
    return raw,dict(record,raw_record=raw_record)

def fit_teachers(teachers):
    if len(teachers)<2 or any(not valid_grid(p['input'])or not valid_grid(p['output'])for p in teachers):return False,{'failure':'insufficient_or_invalid_teachers'}
    if len({tuple(map(tuple,p['input']))for p in teachers})!=len(teachers):return False,{'failure':'duplicate_teacher_inputs'}
    raw=[_chiral_payload_slot_render(p['input'])for p in teachers]
    record={'raw_pair_fits':[out is not None and out==p['output']for(out,_),p in zip(raw,teachers)],'raw_records':[r for _,r in raw]}
    if not all(record['raw_pair_fits']):return False,dict(record,failure='original_teacher_reproduction_failed')
    guarded=[guarded_render(p['input'])for p in teachers];record['teacher_records']=[r for _,r in guarded]
    if any(out is None or out!=p['output']for(out,_),p in zip(guarded,teachers)):return False,dict(record,failure='teacher_certificate_failed')
    return True,record

class 接触配置教材:
    def __init__(self, 教師群):
        self.適合, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if not self.適合:
            return None, {"failure": "全教師を再現するD4接触配置なし"}
        return guarded_render(格子)

    def 記録(self):
        return {"全教師共通接触配置": self.適合}
