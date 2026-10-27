"""Teacher-gated wire endpoint composition with forced two-port cover turns.

Pure candidate reconstruction, not byte-identical recovery of prior 125.
Uses existing component extraction, straight segment and conflict-merge actions.
No external I/O, task identifiers, target access, or stored grids.
"""
from collections import Counter
from itertools import permutations
from 接続.ARC2.既存物体特徴 import color_components
from 接続.ARC2.既存疎点転写 import straight_octilinear_segment
from 接続.ARC2.境界点周期候補 import merge_proposals, valid_grid
D=((-1,0),(0,1),(1,0),(0,-1))
FULL=frozenset((r,c) for r in range(-1,2) for c in range(-1,2))
DIAMOND=frozenset(D)
CROSS=frozenset([(0,0),(-1,-1),(-1,1),(1,-1),(1,1)])
def add(a,b):return a[0]+b[0],a[1]+b[1]
def neg(a):return -a[0],-a[1]
def glyphs(g,bg,structural):
 result={};covered=set()
 for color in set(v for row in g for v in row)-{bg}-set(structural):
  for component in color_components(g,color,include_diagonal=True):
   pts=set(map(tuple,component['cells']));rs=[r for r,c in pts];cs=[c for r,c in pts]
   if max(rs)-min(rs)!=2 or max(cs)-min(cs)!=2:return None
   center=(min(rs)+1,min(cs)+1);shape=frozenset((r-center[0],c-center[1])for r,c in pts)
   if shape not in (FULL,DIAMOND,CROSS):return None
   result[center]=(color,'sink' if shape==CROSS else 'source');covered|=pts
 return result

def cover_pairs(ports,pts,policy,elbow):
 unused=set(ports);pairs=[]
 if policy=='straight':
  for p,d in sorted(ports):
   if (p,d) not in unused:continue
   matches=[]
   for q,e in unused:
    segment=straight_octilinear_segment(p,q)
    if e==neg(d) and q!=p and (p[0]==q[0]or p[1]==q[1]) and segment is not None and segment-{p,q}<=pts:matches.append((q,e))
   if len(matches)>1:return None
   if matches:
    other=matches[0];unused.remove((p,d));unused.remove(other);pairs.append(((p,d),other))
 else:
  for a,b in ((D[0],D[2]),(D[1],D[3])):
   left=sorted(x for x in unused if x[1]==a);right=sorted(x for x in unused if x[1]==b)
   if len(left)==len(right):
    for x,y in zip(left,right):pairs.append((x,y));unused.remove(x);unused.remove(y)
 if unused and elbow and len(unused)==2:
  (p,d),(q,e)=sorted(unused)
  if d[0]*e[0]+d[1]*e[1]!=0:return None
  bend=(p[0],q[1]) if d[1] else (q[0],p[1])
  first=straight_octilinear_segment(p,bend);second=straight_octilinear_segment(q,bend)
  if (first is None or second is None or not first-{p}<=pts or not second-{q}<=pts
      or (bend[0]-p[0])*d[0]+(bend[1]-p[1])*d[1]<=0
      or (bend[0]-q[0])*e[0]+(bend[1]-q[1])*e[1]<=0):return None
  pairs.append(((p,d),(q,e)));unused.clear()
 return None if unused else pairs

def render(g,model,elbow=True):
 if not valid_grid(g):return None,{'failure':'invalid_grid'}
 bg,line,bridge,cover,policy=model;h,w=len(g),len(g[0])
 markers=glyphs(g,bg,(line,bridge,cover))
 if not markers:return None,{'failure':'glyph_roles'}
 wire={(r,c) for r,row in enumerate(g)for c,v in enumerate(row)if v in(line,bridge)}
 if not wire:return None,{'failure':'no_wire'}
 jumps={};cover_records=[]
 for cc in color_components(g,cover):
  pts=set(map(tuple,cc['cells']));rs=[r for r,c in pts];cs=[c for r,c in pts]
  if len(pts)!=(max(rs)-min(rs)+1)*(max(cs)-min(cs)+1):return None,{'failure':'cover_not_rectangle'}
  ports=[]
  for p in sorted(wire):
   for d in D:
    # Tangential adjacency alone is not an entering wire. A wire may turn at
    # the cover edge, or terminate immediately at a source glyph.
    if add(p,d)in pts and (add(p,neg(d))in wire or sum(add(p,e)in wire for e in D)<=1):ports.append((p,d))
  pairs=cover_pairs(ports,pts,policy,elbow)
  if not ports or pairs is None:return None,{'failure':'incomplete_cover_pairing','ports':ports,'cover':sorted(pts)}
  cover_records.append({'ports':ports,'pairs':pairs})
  for (p,d),(q,e)in pairs:
   if (p,d)in jumps or(q,e)in jumps:return None,{'failure':'cover_port_conflict'}
   jumps[p,d]=(q,neg(e));jumps[q,e]=(p,neg(d))
 def neighbors(p):return [d for d in D if add(p,d)in wire or(p,d)in jumps]
 endpoints={}
 for p in sorted(wire):
  nb=neighbors(p)
  if len(nb)not in(1,2,4):return None,{'failure':'wire_degree','point':p,'degree':len(nb)}
  if len(nb)==1:
   # The open side is determined by a known glyph when the last wire cell
   # abuts a cover; otherwise use the opposite of the sole entering edge.
   choices=[c for c in markers if abs(c[0]-p[0])+abs(c[1]-p[1])==2 and (c[0]==p[0]or c[1]==p[1])]
   if len(choices)>1:return None,{'failure':'ambiguous_endpoint_glyph'}
   center=choices[0]if choices else add(p,(-2*nb[0][0],-2*nb[0][1]))
   if not (1<=center[0]<h-1 and 1<=center[1]<w-1):return None,{'failure':'endpoint_outside'}
   endpoints[p]=(nb[0],center)
 if len(endpoints)<2 or len({x[1]for x in endpoints.values()})!=len(endpoints):return None,{'failure':'endpoint_count'}
 if not set(markers)<=set(x[1]for x in endpoints.values()):return None,{'failure':'unattached_glyph'}
 paths={};visited=set();used_half_edges=set()
 for start,(d,center)in endpoints.items():
  p=start;seen=set()
  while (p,d)not in seen:
   seen.add((p,d));used_half_edges.add((p,d));visited.add(p)
   q,nd=jumps[p,d]if(p,d)in jumps else(add(p,d),d)
   if q not in wire:return None,{'failure':'broken_wire'}
   p=q;visited.add(p)
   nb=[e for e in neighbors(p)if e!=neg(nd)]
   if not nb:
    if p not in endpoints:return None,{'failure':'nonterminal_stop'}
    paths[start]=p;break
   if len(nb)==1:d=nb[0]
   elif len(nb)==3 and nd in nb:d=nd
   else:return None,{'failure':'ambiguous_crossing'}
  else:return None,{'failure':'wire_cycle'}
 if (visited!=wire or used_half_edges!={(p,d)for p in wire for d in neighbors(p)}
     or any(paths.get(q)!=p or p==q for p,q in paths.items())):return None,{'failure':'incomplete_reversible_traces'}
 writes=[];handled=set();links=[]
 for p,q in paths.items():
  if p in handled:continue
  handled|={p,q};a=endpoints[p][1];b=endpoints[q][1];ma=markers.get(a);mb=markers.get(b)
  if ma is None and mb is None:return None,{'failure':'unlabelled_path'}
  if ma and mb and (ma[0]!=mb[0]or ma[1]==mb[1]):return None,{'failure':'endpoint_labels_conflict'}
  color=(ma or mb)[0];ra=ma[1]if ma else('sink'if mb[1]=='source'else'source');rb=mb[1]if mb else('sink'if ra=='source'else'source')
  for center,role in((a,ra),(b,rb)):
   mask=DIAMOND if role=='source'else CROSS
   for dr,dc in FULL:
    r,c=add(center,(dr,dc))
    if g[r][c]not in(bg,color):return None,{'failure':'endpoint_write_collision'}
    writes.append((r,c,color if(dr,dc)in mask else bg))
  links.append((a,b,color,ra,rb))
 out,record=merge_proposals(g,writes)
 return out,{'covers':cover_records,'links':links,'merge':record}

def fit(teachers):
 if not teachers:return (),{'failure':'no_teachers'}
 palettes=set(v for t in teachers for row in t['input']for v in row);backgrounds=[];structural=set()
 for t in teachers:
  g=t['input'];counts=Counter(v for row in g for v in row);m=max(counts.values());b=[c for c,n in counts.items()if n==m]
  if len(b)!=1:return (),{'failure':'background_tie'}
  backgrounds.append(b[0])
  for color in counts.keys()-{b[0]}:
   if glyphs([[v if v==color else b[0]for v in row]for row in g],b[0],())is None:structural.add(color)
 if len(set(backgrounds))!=1 or len(structural)!=3:return (),{'failure':'structural_palette'}
 models=[];trials=[]
 for roles in permutations(sorted(structural)):
  for policy in('straight','ordered_opposite'):
   model=(backgrounds[0],*roles,policy);results=[render(t['input'],model)for t in teachers]
   exact=[o==t['output']for(o,_),t in zip(results,teachers)];trials.append({'model':model,'teacher_exact':exact,'failures':[r.get('failure')for _,r in results]})
   if all(exact):models.append(model)
 return tuple(models),{'trials':trials}

def predict(g,models):
 if not models:return None,{'failure':'no_teacher_fitted_model'}
 results=[render(g,m)for m in models]
 if any(o is None for o,r in results):return None,{'failure':'retained_model_failed','results':results}
 if any(o!=results[0][0]for o,r in results):return None,{'failure':'retained_model_disagreement','results':results}
 return results[0][0],{'results':results,'model_count':len(models)}
