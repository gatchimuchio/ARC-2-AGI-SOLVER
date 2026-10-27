"""Teacher-fitted marker ownership, simultaneous region transfer, and optional cue turn.
No task identifiers or target-dependent parsing. See evidence.md for finite priors.
"""
from dataclasses import dataclass, asdict
from itertools import product
from 接続.ARC2.既存物体特徴 import color_components
from 接続.ARC2.既存格子操作 import transform_grid_by_name

DIRS = ((-1,0),(0,1),(1,0),(0,-1))
TURNS = ('identity','rot90','rot180','rot270')

@dataclass(frozen=True)
class Model:
    marker: int
    turn_color: int | None
    turns: tuple

@dataclass(frozen=True)
class Fitted:
    models: tuple

def valid(g):
    return isinstance(g,list) and 1<=len(g)<=30 and isinstance(g[0],list) and 1<=len(g[0])<=30 and all(isinstance(row,list) and len(row)==len(g[0]) and all(type(v)is int and 0<=v<10 for v in row) for row in g)

def bbox(cells):
    return min(r for r,c in cells),min(c for r,c in cells),max(r for r,c in cells),max(c for r,c in cells)

def host(g,cells):
    a,b,z,y=bbox(cells)
    colors={g[r][c] for r in range(a,z+1) for c in range(b,y+1) if (r,c) not in cells}
    return next(iter(colors)) if len(colors)==1 else None

def parse(g,marker,turn_color):
    if not valid(g): return [],'invalid_grid'
    h,w=len(g),len(g[0]); marked={(r,c) for r in range(h) for c in range(w) if g[r][c]==marker}
    if not marked:return [],'no_markers'
    arrows=[]
    for r in range(h):
      for c in range(w):
       for dr,dc in DIRS:
        arms={(r+dr,c+dc),(r-dc,c+dr),(r+dc,c-dr)}
        cells=arms|{(r,c)}
        if not arms<=marked or not all(0<=a<h and 0<=b<w for a,b in cells):continue
        background=host(g,cells)
        if background is None or background==marker:continue
        arrows.append((cells, cells&marked,(r,c),(dr,dc),background,g[r][c] if g[r][c]!=marker else background))
    covers=[];incomplete=False;nodes=0
    def visit(remaining,used,chosen):
      nonlocal incomplete,nodes
      nodes+=1
      if nodes>50000 or len(covers)>256:incomplete=True;return
      if not remaining:covers.append(chosen);return
      p=min(remaining)
      for arrow in arrows:
       if p in arrow[1] and arrow[1]<=remaining and not arrow[0]&used:
        visit(remaining-arrow[1],used|arrow[0],chosen+[arrow])
    visit(marked,set(),[])
    if incomplete:return [],'resource_incomplete'
    cues=[]
    if turn_color is not None:
      for comp in color_components(g,turn_color,include_diagonal=False):
       cells=set(comp['cells']); a,b,z,y=bbox(cells)
       if z-a!=y-b or z-a<1:continue
       for corner,(rr,cc) in enumerate(((a,b),(a,y),(z,y),(z,b))):
        if cells!={(rr,c)for c in range(b,y+1)}|{(r,cc)for r in range(a,z+1)}:continue
        background=host(g,cells)
        if background is not None and background not in (marker,turn_color):cues.append((cells,corner,background))
      if len(cues)>1:return [],'multiple_turn_cues'
    scenes=[]
    for arrows in covers:
      erased=set().union(*(a[0] for a in arrows))
      if any(c[0]&erased for c in cues):return [],'eligible_cover_cue_overlap'
      clean=[row[:] for row in g]
      for cells,_,_,_,background,_ in arrows:
       for r,c in cells:clean[r][c]=background
      for cells,_,background in cues:
       for r,c in cells:clean[r][c]=background
      regions=[]; owners={}
      for color in sorted(set(v for row in clean for v in row)):
       for comp in color_components(clean,color,include_diagonal=False):
        i=len(regions);regions.append((color,tuple(sorted(comp['cells']))));owners.update({p:i for p in comp['cells']})
      assignments={};records=[];failure=None
      for cells,_,center,direction,background,payload in arrows:
       own=owners[center]
       if any(owners[p]!=own for p in cells):failure='eligible_cover_ownership_failure';break
       dr,dc=direction;r,c=center
       while 0<=r<h and 0<=c<w and owners[(r,c)]==own:r+=dr;c+=dc
       if not(0<=r<h and 0<=c<w):failure='eligible_cover_ray_out_of_bounds';break
       target=owners[(r,c)]
       if target in assignments and assignments[target]!=payload:failure='eligible_cover_assignment_conflict';break
       assignments[target]=payload;records.append((center,direction,own,target,payload))
      if failure:return [],failure
      output=[row[:]for row in clean]
      for i,color in assignments.items():
       for r,c in regions[i][1]:output[r][c]=color
      scenes.append({'output':output,'corner':cues[0][1] if cues else None,'roles':{'arrows':sorted(records),'cue':(tuple(sorted(cues[0][0])),cues[0][1],cues[0][2]) if cues else None,'regions':regions}})
    return scenes,None if scenes else 'no_complete_scene'

def render(g,model):
    scenes,reason=parse(g,model.marker,model.turn_color)
    if not scenes:return None,{'reason':reason}
    returns=[transform_grid_by_name(s['output'],TURNS[0 if s['corner'] is None else model.turns[s['corner']]])for s in scenes]
    if any(s['roles']!=scenes[0]['roles'] for s in scenes):return None,{'reason':'role_disagreement'}
    if any(o!=returns[0]for o in returns):return None,{'reason':'output_disagreement'}
    return returns[0],{'roles':scenes[0]['roles'],'scene_count':len(scenes)}

def fit_teachers(teachers):
    if not isinstance(teachers,list) or len(teachers)<2 or any(not valid(p.get('input')) or not valid(p.get('output')) for p in teachers):return None,{'reason':'invalid_teachers'}
    if len({tuple(map(tuple,p['input']))for p in teachers})!=len(teachers):return None,{'reason':'duplicate_inputs'}
    retained=[];parse_records=[]
    for marker in range(10):
      for turn_color in (None,)+tuple(c for c in range(10)if c!=marker):
       parsed=[parse(p['input'],marker,turn_color)for p in teachers]
       parse_records.append({'marker':marker,'turn_color':turn_color,'scenes':[len(s)for s,r in parsed],'failures':[r for s,r in parsed]})
       if any(r=='resource_incomplete'for s,r in parsed):return None,{'reason':'resource_incomplete'}
       if any(not s for s,r in parsed):continue
       for turns in product(range(4),repeat=4) if turn_color is not None else [(0,0,0,0)]:
        okay=True
        for pair,(scenes,_)in zip(teachers,parsed):
         if any(s['roles']!=scenes[0]['roles'] for s in scenes):okay=False;break
         if any(transform_grid_by_name(s['output'],TURNS[0 if s['corner'] is None else turns[s['corner']]])!=pair['output']for s in scenes):okay=False;break
        if okay:retained.append(Model(marker,turn_color,turns))
    return (Fitted(tuple(retained))if retained else None),{'retained_models':[asdict(m)for m in retained],'parse_records':parse_records,'complete':True}

def predict(g,fitted):
    if not isinstance(fitted,Fitted)or not fitted.models:return None,{'reason':'no_models'}
    results=[render(g,m)for m in fitted.models]
    if any(o is None for o,r in results):return None,{'reason':'retained_model_failure','returns':results}
    if any(r['roles']!=results[0][1]['roles']for o,r in results):return None,{'reason':'retained_role_disagreement'}
    if any(o!=results[0][0]for o,r in results):return None,{'reason':'retained_output_disagreement'}
    return results[0][0],{'model_count':len(results),'roles':results[0][1]['roles']}
