"""Local rail/chain ownership and nearest-component contour draping.
Explicit priors: monochrome C8 objects; straight border rail; its endpoint
owns a lateral chain; nearest forward passive component; near-side profile;
unit-speed interpolation and post-profile diagonal; chain cell count, clipping.
No task identifiers, file I/O, fixed colors, stored teacher grids or answers.
"""
from collections import Counter
from itertools import product
from 接続.ARC2.既存物体特徴 import color_components
from 接続.ARC2.境界点周期候補 import valid_grid
D4=((-1,0),(1,0),(0,-1),(0,1))
def dot(a,b):return a[0]*b[0]+a[1]*b[1]
def sub(a,b):return (a[0]-b[0],a[1]-b[1])
def add(a,b,k=1):return (a[0]+k*b[0],a[1]+k*b[1])
def roles(g):
 if not valid_grid(g):return None,'invalid_grid'
 counts=Counter(v for row in g for v in row);mx=max(counts.values())
 if sum(v==mx for v in counts.values())!=1:return None,'background_tie'
 bg=max(counts,key=counts.get);obs=[];h,w=len(g),len(g[0])
 for color in sorted(counts.keys()-{bg}):
  for o in color_components(g,color,True):obs.append({'color':color,'cells':set(o['cells'])})
 rails=[]
 for i,o in enumerate(obs):
  cells=o['cells']
  if len(cells)<2:continue
  rs={r for r,c in cells};cs={c for r,c in cells}
  if len(rs)==1 and len(cells)==max(cs)-min(cs)+1:
   for edge,forward in [(0,(0,1)),(w-1,(0,-1))]:
    if any(c==edge for r,c in cells):rails.append((i,max(cells,key=lambda p:dot(p,forward)),forward))
  if len(cs)==1 and len(cells)==max(rs)-min(rs)+1:
   for edge,forward in [(0,(1,0)),(h-1,(-1,0))]:
    if any(r==edge for r,c in cells):rails.append((i,max(cells,key=lambda p:dot(p,forward)),forward))
 if not rails:return None,'no_border_rail'
 groups=[]
 for ri,end,f in rails:
  options=[]
  for side in [(-f[1],f[0]),(f[1],-f[0])]:
   anchor=add(end,side)
   for ci,o in enumerate(obs):
    if ci==ri or anchor not in o['cells'] or len(o['cells'])<2:continue
    # Whole local chain is behind the free rail end and on one lateral side.
    if not all(dot(sub(p,end),f)<=0 and dot(sub(p,end),side)>0 for p in o['cells']):continue
    contacts={(r+dr,c+dc) for r,c in o['cells'] for dr,dc in D4}&obs[ri]['cells']
    # A chain may touch the rail along its near-end extent, but owns its free endpoint.
    if end not in contacts:continue
    options.append((ri,ci,anchor,f,side))
  if not options:continue
  groups.append(options)
 if not groups:return None,'no_rail_chain_pair'
 return (bg,obs,groups),None

def render(g,metric='chebyshev',interpolation='early'):
 parsed,fail=roles(g)
 if fail:return None,{'failure':fail,'candidates':[]}
 bg,obs,groups=parsed;h,w=len(g),len(g[0]);records=[];outs=[];failed=False
 for assignment in product(*groups):
  used=[x for a in assignment for x in a[:2]]
  if len(set(used))!=len(used):
   records.append({'failure':'ownership_overlap'});failed=True;continue
  target_options=[]
  for ri,ci,anchor,f,side in assignment:
   candidates=[]
   for ti,o in enumerate(obs):
    if ti in used:continue
    coords=[(dot(sub(p,anchor),f),dot(sub(p,anchor),side)) for p in o['cells']]
    if min(t for t,s in coords)<=0:continue
    dist=min(max(abs(p[0]-anchor[0]),abs(p[1]-anchor[1])) if metric=='chebyshev' else (p[0]-anchor[0])**2+(p[1]-anchor[1])**2 for p in o['cells'])
    candidates.append((dist,ti,coords))
   if not candidates:target_options.append([]);continue
   best=min(x[0] for x in candidates);target_options.append([x for x in candidates if x[0]==best])
  if any(not ts for ts in target_options):records.append({'failure':'no_forward_target'});failed=True;continue
  for targets in product(*target_options):
   out=[row[:] for row in g];rec={'chains':[]};writes={};bad=None
   for ri,ci,anchor,f,side in assignment:
    for r,c in obs[ci]['cells']:out[r][c]=bg
   for (ri,ci,anchor,f,side),(dist,ti,coords) in zip(assignment,targets):
    profile={}
    for t,s in coords:profile[t]=max(profile.get(t,s+1),s+1)
    lo,hi=min(profile),max(profile);b=profile[lo]
    if set(profile)!=set(range(lo,hi+1)) or abs(b)>lo or any(abs(profile[t]-profile[t-1])>1 for t in range(lo+1,hi+1)):
     bad='non_unit_profile';break
    points=[]
    for t in range(len(obs[ci]['cells'])):
     if t<lo:
      mag=min(abs(b),t) if interpolation=='early' else max(0,abs(b)-(lo-t))
      s=mag*(1 if b>=0 else -1)
     elif t<=hi:s=profile[t]
     else:s=profile[hi]-(t-hi)
     points.append(add(add(anchor,f,t),side,s))
    for p in points:
     r,c=p
     if 0<=r<h and 0<=c<w:
      color=obs[ci]['color']
      if out[r][c]!=bg or p in writes:bad='collision';break
      writes[p]=color
    rec['chains'].append({'rail':ri,'chain':ci,'target':ti,'anchor':anchor,'source_count':len(obs[ci]['cells']),'logical_count':len(points),'clipped_count':sum(not(0<=r<h and 0<=c<w) for r,c in points),'points':points})
    if bad:break
   if bad:rec['failure']=bad;failed=True
   else:
    for (r,c),color in writes.items():out[r][c]=color
    outs.append(out)
   records.append(rec)
 if failed:return None,{'failure':'retained_candidate_failure','candidates':records}
 if not outs:return None,{'failure':'no_candidate','candidates':records}
 if any(o!=outs[0] for o in outs):return None,{'failure':'candidate_disagreement','candidates':records}
 return outs[0],{'failure':None,'candidates':records}

MODELS=tuple((m,p) for m in ('chebyshev','euclidean_squared') for p in ('early','late'))
def fit(train):
 if not train:return None
 models=[]
 for m,p in MODELS:
  results=[render(e['input'],m,p)[0] for e in train]
  if all(o==e['output'] for o,e in zip(results,train)):models.append((m,p))
 return {'version':1,'models':models} if models else None

def predict(g,state):
 if not state or state.get('version')!=1:return None,{'failure':'not_fitted'}
 all_results=[render(g,*model) for model in state['models']]
 outputs=[x[0] for x in all_results]
 if not outputs or any(o is None for o in outputs):return None,{'failure':'retained_model_failure','models':all_results}
 if any(o!=outputs[0] for o in outputs):return None,{'failure':'model_disagreement','models':all_results}
 return outputs[0],{'failure':None,'models':all_results}
