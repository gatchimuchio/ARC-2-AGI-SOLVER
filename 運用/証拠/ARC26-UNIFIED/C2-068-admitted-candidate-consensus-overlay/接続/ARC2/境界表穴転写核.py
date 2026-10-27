"""Input-only outer-edge key lane, C8 object ownership and C4 cavity composition.
Explicit prior: key lane is the two-lane table side nearest a canvas edge.
No identifiers, source paths, teacher pixels, or query answers in runtime.
"""
from collections import Counter
from 接続.ARC2.既存領域転写 import mixed_region_dicts_for_grid
from 接続.ARC2.既存物体特徴 import color_components
from 接続.ARC2.既存穴充填 import _orthogonal_components
from 接続.ARC2.境界点周期候補 import valid_grid, merge_proposals
MODEL=('outer_edge_key_lane',1)

def render(g):
 if not valid_grid(g):return None,{'failure':'invalid_grid'}
 h,w=len(g),len(g[0]);counts=Counter(x for row in g for x in row)
 bgs=[v for v,n in counts.items() if n==max(counts.values())]
 if len(bgs)!=1:return None,{'failure':'background_tie'}
 bg=bgs[0];tables=[]
 for ob in mixed_region_dicts_for_grid(g,bg,True):
  r0,c0,r1,c1=ob['bbox'];rh,cw=r1-r0+1,c1-c0+1
  if ob['size']!=rh*cw or len(ob['colors'])<2:continue
  lanes=[]
  if rh==2:
   lanes.extend([(r0,[(g[r0][c],g[r1][c]) for c in range(c0,c1+1)],'top'),(h-1-r1,[(g[r1][c],g[r0][c]) for c in range(c0,c1+1)],'bottom')])
  if cw==2:
   lanes.extend([(c0,[(g[r][c0],g[r][c1]) for r in range(r0,r1+1)],'left'),(w-1-c1,[(g[r][c1],g[r][c0]) for r in range(r0,r1+1)],'right')])
  if lanes:tables.append((ob,[lane for lane in lanes if lane[0]==min(x[0] for x in lanes)]))
 if not tables:return None,{'failure':'no_two_lane_table'}
 outputs=[];records=[];failed=False
 for table,lanes in tables:
  for dist,pairs,side in lanes:
   mapping={};err=None;writes=[];owners=[]
   for k,v in pairs:
    if k in mapping and mapping[k]!=v:err='conflicting_key'
    mapping[k]=v
   for color in sorted(counts.keys()-{bg}):
    for ob in color_components(g,color,True):
     if ob['cells'] & set(table['cells']):continue
     if color not in mapping:continue
     r0,c0,r1,c1=ob['bbox'];holes=[]
     for reg in _orthogonal_components({(r,c) for r in range(r0,r1+1) for c in range(c0,c1+1)}-ob['cells']):
      if any(r in (r0,r1) or c in (c0,c1) for r,c in reg):continue
      if any(g[r][c]!=bg for r,c in reg):err='foreign_cavity_occupant';continue
      holes.extend(reg)
     owners.append({'color':color,'bbox':ob['bbox'],'holes':sorted(holes),'value':mapping[color]})
     writes.extend((r,c,mapping[color]) for r,c in holes)
   out,merge=merge_proposals(g,writes)
   if out is None:err='merge_failure'
   rec={'table_bbox':table['bbox'],'side':side,'edge_distance':dist,'mapping':mapping,'owners':owners,'failure':err,'merge':merge};records.append(rec)
   if err:failed=True
   else:outputs.append(out)
 if failed:return None,{'failure':'retained_role_failure','roles':records}
 if not outputs or any(x!=outputs[0] for x in outputs):return None,{'failure':'retained_role_disagreement','roles':records}
 return outputs[0],{'roles':records}

def fit(teachers):
 if not isinstance(teachers,list) or len(teachers)<2:return (),{'failure':'teacher_contract'}
 if any(not isinstance(t,dict) or not valid_grid(t.get('input')) or not valid_grid(t.get('output')) for t in teachers):return (),{'failure':'teacher_contract'}
 if len({tuple(map(tuple,t['input'])) for t in teachers})<2:return (),{'failure':'teacher_contract'}
 results=[render(t['input']) for t in teachers]
 exact=[y==t['output'] and y!=t['input'] for t,(y,_) in zip(teachers,results)]
 return ((MODEL,) if all(exact) else ()),{'teacher_exact':exact,'results':[d for _,d in results]}

def predict(g,models):
 if not models or any(tuple(m)!=MODEL for m in models):return None,{'failure':'no_fitted_model'}
 return render(g)
