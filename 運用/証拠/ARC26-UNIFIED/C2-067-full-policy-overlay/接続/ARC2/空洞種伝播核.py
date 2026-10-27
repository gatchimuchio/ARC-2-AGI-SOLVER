"""空洞の局所所有・囲まれた種・遮蔽交差の既存成分合成。

候補124の完全source復元ではなく、既存成分/穴/競合mergeを用いた再構成。
外部I/O、課題識別子、固定色役割、固定出力、教師状態保持なし。
"""
from collections import Counter, deque
from 接続.ARC2.境界点周期候補 import merge_proposals, valid_grid
from 接続.ARC2.既存物体特徴 import color_components,dominant_background_for_grid
from 接続.ARC2.既存穴充填 import _orthogonal_components
D4=((-1,0),(1,0),(0,-1),(0,1))
def objects(g):
 h,w=len(g),len(g[0]);bg=dominant_background_for_grid(g);objs=[]
 for color in sorted(set(sum(g,[]))-{bg}):
  for ob in color_components(g,color,True):
   cells=ob['cells']; r0,c0,r1,c1=ob['bbox']; holes=[]
   for reg in _orthogonal_components({(r,c) for r in range(r0,r1+1) for c in range(c0,c1+1)}-cells):
    if any((r==r0 and r0>0) or (r==r1 and r1<h-1) or(c==c0 and c0>0)or(c==c1 and c1<w-1) for r,c in reg):continue
    boundary={(r+dr,c+dc) for r,c in reg for dr,dc in D4}&cells
    holes.append({'cells':reg,'boundary':boundary,'colors':sorted({g[r][c] for r,c in reg})})
   ob['holes']=holes;objs.append(ob)
 return bg,objs
D8=tuple((r,c) for r in (-1,0,1) for c in (-1,0,1) if r or c)
def near(a,b):
 return any((r+dr,c+dc) in b for r,c in a for dr,dc in D8)
def render(g):
 if not valid_grid(g):return None,{'failure':'invalid_grid'}
 counts=Counter(v for row in g for v in row)
 if sum(n==max(counts.values()) for n in counts.values())!=1:return None,{'failure':'background_tie'}
 bg,obs=objects(g);cav=[];seeds=[];used=set();wires=[]
 for ob in obs:
  for hole in ob['holes']:
   if hole['colors']==[bg]:
    cav.append(hole);used|=hole['boundary']
   elif len(hole['cells'])==1 and len(hole['colors'])==1:
    seeds.append((next(iter(hole['cells'])),hole['colors'][0],ob['cells']))
 for ob in obs:
  remain=ob['cells']-used
  if not remain:continue
  # Retain original same-color connected components after local physical ownership.
  mask=[[1 if (r,c) in remain else 0 for c in range(len(g[0]))] for r in range(len(g))]
  wires.extend(x['cells'] for x in color_components(mask,1,True))
 adjacency={i:set() for i in range(len(cav)+len(wires))}
 for i,hole in enumerate(cav):
  for j,wire in enumerate(wires,len(cav)):
   if near(hole['boundary'],wire):adjacency[i].add(j);adjacency[j].add(i)
 # A foreign wire can occupy the one-cell overlap of two fragments of
 # the same colored wire. This is a relation between existing wire nodes.
 crossings=[]
 halo={}
 colors=[]
 for i,wire in enumerate(wires):
  r,c=next(iter(wire));colors.append(g[r][c])
  for r,c in wire:
   for dr,dc in D8:halo.setdefault((r+dr,c+dc),set()).add(i)
 crossing_pairs={}
 for k,foreign in enumerate(wires):
  for point in sorted(foreign):
   groups={}
   for i in halo.get(point,()):
    if colors[i]!=colors[k]:groups.setdefault(colors[i],set()).add(i)
   for color,owners in groups.items():
    if len(owners)>2:return None,{'failure':'ambiguous_crossing','point':point,'fragments':sorted(owners)}
    if len(owners)==2:
     pair=tuple(sorted(owners));crossing_pairs.setdefault(pair,[]).append(point)
 for (i,j),witnesses in sorted(crossing_pairs.items()):
  u,v=i+len(cav),j+len(cav);adjacency[u].add(v);adjacency[v].add(u)
  crossings.append((i,j,witnesses))
 if not seeds or not cav:return None,{'failure':'missing_socket_or_cavity'}
 paint={i:set() for i in range(len(cav))}
 for point,color,owner in seeds:
  queue=deque(j for j,wire in enumerate(wires,len(cav)) if point not in wire and bool(wire&owner));seen=set(queue)
  while queue:
   n=queue.popleft()
   if n<len(cav):paint[n].add(color)
   for m in adjacency[n]-seen:seen.add(m);queue.append(m)
 writes=[]
 for i,cs in paint.items():
  if len(cs)>1:return None,{'failure':'conflicting_seeds','cavity':i,'colors':sorted(cs)}
  if cs:
   color=next(iter(cs))
   for r,c in cav[i]['cells']:writes.append((r,c,color))
 out,merge=merge_proposals(g,writes)
 return out,{'merge':merge,'crossings':crossings,'seeds':[(p,c) for p,c,o in seeds],'cavities':len(cav),'paint':{i:sorted(cs) for i,cs in paint.items()}}

MODEL=('socket_cavity_wire',1)
def fit(teachers):
 if not teachers:return (),{'failure':'no_teachers'}
 results=[render(t['input']) for t in teachers]
 exact=[o==t['output'] and o!=t['input'] for (o,_),t in zip(results,teachers)]
 return ((MODEL,) if all(exact) else ()),{'teacher_exact':exact,'results':[r for _,r in results]}
def predict(g,models):
 if not models or any(tuple(m)!=MODEL for m in models):return None,{'failure':'no_teacher_fitted_model'}
 return render(g)
