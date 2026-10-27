"""Diagnostic geometry composition only; explicit role arguments; no solver registration."""
from 接続.ARC2.既存種境界 import NEIGHBORS_4
from 接続.ARC2.二軸補完教材 import valid_grid
D=tuple(NEIGHBORS_4)
def plus(p,d): return p[0]+d[0],p[1]+d[1]

def paths(g,bg,repair,control):
 h,w=len(g),len(g[0]);inside=lambda p:0<=p[0]<h and 0<=p[1]<w
 colors={v for row in g for v in row}-{bg,repair,control}
 masks={v:{(r,c) for r in range(h) for c in range(w) if g[r][c]==v} for v in colors}
 marker_owners=[]
 for r in range(h):
  for c in range(w):
   if g[r][c]!=repair:continue
   owners={g[q[0]][q[1]] for d in D if inside(q:=plus((r,c),d))}&colors
   if len(owners)!=1:return None,{'failure':'marker_owner_not_unique','cell':(r,c),'owners':sorted(owners)}
   v=next(iter(owners));masks[v].add((r,c));marker_owners.append(((r,c),v))
 for v,S in masks.items():
  # Simultaneous one-cell axis completion, not a recursive expansion.
  add=set()
  for r in range(h):
   for c in range(w):
    if g[r][c]==control:continue
    if any(plus((r,c),d) in S and plus((r,c),(-d[0],-d[1])) in S and all(sum(plus(q,e) in S for e in D)<=1 for q in [plus((r,c),d),plus((r,c),(-d[0],-d[1]))]) for d in D):add.add((r,c))
  S.update(add)
 gap_fills=fill_unique_collinear_gaps(g,masks,bg)
 return masks,{'marker_owners':marker_owners,'long_gap_fills':gap_fills}

def controls(g,masks,control):
 h,w=len(g),len(g[0]);inside=lambda p:0<=p[0]<h and 0<=p[1]<w
 records=[];ops=[];footprints=[]
 for r in range(h):
  for c in range(w):
   if g[r][c]!=control:continue
   cue=(r,c);candidates=[]
   for v,S in masks.items():
    for d in D:
     bend=plus(cue,d)
     if bend not in S:continue
     nbr=[e for e in D if plus(bend,e) in S]
     # Cue must oppose one arm of an elbow, never a straight transit cell.
     if len(nbr)==2 and (sum(nbr[0][i]*nbr[1][i] for i in range(2))==0) and d in nbr:
      candidates.append((v,bend,d))
   records.append({'cue':cue,'candidates':candidates})
   if len(candidates)!=1:return None,{'failure':'control_bend_owner_not_unique','controls':records}
   ops.append(candidates[0])
 result={v:set(S) for v,S in masks.items()}
 for v,bend,d in ops:
  # Remove full old arm component after cutting the bend; stop at its boundary.
  S=masks[v];todo=[plus(bend,d)];removed=set()
  while todo:
   p=todo.pop()
   if p in removed or p==bend or p not in S:continue
   removed.add(p);todo.extend(plus(p,e) for e in D)
  result[v]-=removed
  extended=set()
  p=plus(bend,(-d[0],-d[1]))
  while inside(p):result[v].add(p);extended.add(p);p=plus(p,(-d[0],-d[1]))
  footprints.append({'color':v,'bend':bend,'removed':sorted(removed),'extended':sorted(extended)})
 return result,{'controls':records,'footprints':footprints}

def complete_path(S):
 if not S:return False
 degrees=[sum(plus(p,d) in S for d in D) for p in S]
 if degrees.count(1)!=2 or any(x not in (1,2) for x in degrees):return False
 seen=set();todo=[next(iter(S))]
 while todo:
  p=todo.pop()
  if p in seen:continue
  seen.add(p);todo.extend(q for d in D if (q:=plus(p,d)) in S and q not in seen)
 return seen==S


def _components(S):
 remaining=set(S);result=[]
 while remaining:
  root=min(remaining);remaining.remove(root);component={root};todo=[root]
  while todo:
   r,c=todo.pop()
   for d in D:
    q=plus((r,c),d)
    if q in remaining:
     remaining.remove(q);component.add(q);todo.append(q)
  result.append(component)
 return result


def complete_path_union(S):
 """Accept one or more disjoint simple paths, rejecting branches and loops."""
 if not S:return False
 for component in _components(S):
  degrees=[sum(plus(p,d) in component for d in D) for p in component]
  if degrees.count(1)!=2 or any(degree not in (1,2) for degree in degrees):
   return False
 return True


def fill_unique_collinear_gaps(g,masks,bg):
 """Join separate path endpoints only across unique, background-only straight gaps."""
 additions={color:set() for color in masks}
 for color,support in masks.items():
  endpoints={p for p in support
             if sum(plus(p,d) in support for d in D)==1}
  if len(endpoints)<2:continue
  component_index={p:i for i,component in enumerate(_components(support))
                   for p in component}
  options={p:set() for p in endpoints}
  for p in endpoints:
   for q in endpoints:
    if p>=q or component_index[p]==component_index[q]:continue
    if p[0]==q[0]:
     step=1 if q[1]>p[1] else -1
     gap=[(p[0],col) for col in range(p[1]+step,q[1],step)]
    elif p[1]==q[1]:
     step=1 if q[0]>p[0] else -1
     gap=[(row,p[1]) for row in range(p[0]+step,q[0],step)]
    else:
     continue
    if len(gap)<2 or any(g[row][col]!=bg for row,col in gap):continue
    options[p].add(q);options[q].add(p)
  pairs=set()
  for p,neighbors in options.items():
   if len(neighbors)!=1:continue
   q=next(iter(neighbors))
   if options.get(q)=={p}:pairs.add(tuple(sorted((p,q))))
  for p,q in pairs:
   if p[0]==q[0]:
    step=1 if q[1]>p[1] else -1
    additions[color].update((p[0],col)
                            for col in range(p[1]+step,q[1],step))
   else:
    step=1 if q[0]>p[0] else -1
    additions[color].update((row,p[1])
                            for row in range(p[0]+step,q[0],step))
 for color,cells in additions.items():masks[color].update(cells)
 return {color:sorted(cells) for color,cells in additions.items() if cells}

