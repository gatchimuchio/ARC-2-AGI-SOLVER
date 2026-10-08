"""Pure input geometric probe. No teacher loading inside predictor."""
from collections import Counter
from fractions import Fraction
from math import gcd, floor

def roles(g):
 h,w=len(g),len(g[0]); bg=Counter(v for row in g for v in row).most_common(1)[0][0]
 out=[]
 for wall in sorted(set(sum(g,[]))-{bg}):
  cores=[]; covered=set(); valid=True
  for color in sorted(set(sum(g,[]))-{bg,wall}):
   cells={(r,c) for r in range(h) for c in range(w) if g[r][c]==color}
   # multiple disconnected same-color cores are a rejected limitation of this probe
   t=min(r for r,c in cells); b=max(r for r,c in cells); l=min(c for r,c in cells); z=max(c for r,c in cells)
   if cells!={(r,c) for r in range(t,b+1) for c in range(l,z+1)}:valid=False;break
   ring={(r,c) for r in range(max(0,t-1),min(h,b+2)) for c in range(max(0,l-1),min(w,z+2))}-cells
   if any(g[r][c] not in (bg,wall) for r,c in ring):valid=False;break
   covered|={p for p in ring if g[p[0]][p[1]]==wall}
   holes=[(p,(-1 if p[0]<t else 1 if p[0]>b else 0,-1 if p[1]<l else 1 if p[1]>z else 0)) for p in sorted(ring) if g[p[0]][p[1]]==bg]
   cores.append((color,(t,l,b,z),holes))
  if valid and cores and covered=={(r,c) for r in range(h) for c in range(w) if g[r][c]==wall}:out.append((bg,wall,cores))
 return out

def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def add(a,b):return tuple(x+y for x,y in zip(a,b))
def prim(v):
 d=gcd(*map(abs,v));return tuple(x//d for x in v) if d else (0,0)
def step(v,n):
 m=max(map(abs,v));return tuple((1 if x>=0 else -1)*(n*abs(x)//m) for x in v)
def render(g, suppression=False, reverse=False, event_ties=None):
 rr=roles(g)
 if len(rr)!=1:return None,{'failure':'roles','roles':rr}
 bg,wall,cores=rr[0];h,w=len(g),len(g[0]); bundles=[];trace=[];out=[row[:] for row in g]
 for color,box,holes in cores:
  for p,v in holes:bundles.append({'v':v,'lanes':[(p,color)],'past':[]})
 if reverse:bundles.reverse()
 tie_choices=[]
 def pos(lane,v,n):return add(lane[0],step(v,n))
 def bounded(p):return 0<=p[0]<h and 0<=p[1]<w
 for it in range(100):
  events=[]
  for i,a in enumerate(bundles):
   for j,b in enumerate(bundles[i+1:],i+1):
    va,vb=a['v'],b['v'];den=cross(va,vb)
    if not den or prim(add(va,vb))==(0,0):continue
    for la in a['lanes']:
     for lb in b['lanes']:
      d=tuple(y-x for x,y in zip(la[0],lb[0]));ta=Fraction(cross(d,vb),den);tb=Fraction(cross(d,va),den)
      if ta<=0 or tb<=0:continue
      meet=tuple(Fraction(x)+ta*y for x,y in zip(la[0],va))
      if not bounded(meet):continue
      # Last discrete point strictly before the continuous intersection.
      sa=ta*max(map(abs,va));sb=tb*max(map(abs,vb));na=(sa.numerator-1)//sa.denominator;nb=(sb.numerator-1)//sb.denominator
      events.append((max(sa,sb),sa+sb,i,j,na,nb,meet))
  if not events:break
  score=min((e[0],e[1]) for e in events)
  tied=sorted(e for e in events if (e[0],e[1])==score)
  tie_choices.append(len(tied))
  choice=(event_ties or {}).get(it,0)
  ev=tied[choice];_,_,i,j,na,nb,meet=ev;a,b=bundles[i],bundles[j]
  v=prim(add(a['v'],b['v']));lanes=[];past=a['past']+b['past']
  for bundle,n in ((a,na),(b,nb)):
   for lane in bundle['lanes']:
    past += [(pos(lane,bundle['v'],k),lane[1]) for k in range(n)]
    lanes.append((pos(lane,bundle['v'],n),lane[1]))
  trace.append({'event':str(ev),'incoming':[a['v'],b['v']],'outgoing':v,'lanes':lanes})
  bundles=[x for k,x in enumerate(bundles) if k not in(i,j)]+[{'v':v,'lanes':lanes,'past':past}]
 else:return None,{'failure':'event_cycle','trace':trace}
 conflicts=[]
 for b in bundles:
  painted=list(b['past'])
  for lane in b['lanes']:
   for k in range(100):
    p=pos(lane,b['v'],k)
    if not bounded(p):break
    painted.append((p,lane[1]))
  for (r,c),color in painted:
   if not bounded((r,c)):continue
   if out[r][c] not in(bg,color):conflicts.append(((r,c),out[r][c],color))
   out[r][c]=color
 return out,{'trace':trace,'conflicts':conflicts,'roles':rr,'tie_choices':tie_choices}
