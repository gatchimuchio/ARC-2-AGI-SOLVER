"""Input-first physical ownership view.

Explicit additional prior: every filled rectangular mixed-C8 physical component,
and every rectangular leaf reached during decomposition, is indivisible.
Only nonrectangular bodies are split using frozen155's double-frame-band
predicate. All recursive cut alternatives are retained. No assembly result,
output color arrangement, score, or ranking influences this observation.
"""
from dataclasses import dataclass
from collections import Counter
from itertools import product
from . import anchored_rectangle as base
from .seam_rectangle import certify_contacts

PRIOR='rectangular_physical_body_indivisibility'
@dataclass(frozen=True)
class State:
    programs: tuple=(PRIOR,)


def partitions(cells,border,meter):
    memo={};cut_records=[]
    def visit(body):
        key=tuple(sorted(body));meter.charge(1,'partition_node')
        if key in memo:return memo[key]
        r0=min(p[0] for p in body);r1=max(p[0] for p in body)
        c0=min(p[1] for p in body);c1=max(p[1] for p in body)
        if len(body)==(r1-r0+1)*(c1-c0+1):
            memo[key]=((key,),);return memo[key]
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

