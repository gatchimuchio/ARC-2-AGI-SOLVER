"""Input-only bounded series composition. Caller configures accepted imports.
No filesystem reads, workspace bootstrap, task IDs or answer-dependent routing.
"""
from collections import Counter,defaultdict
from fractions import Fraction
from itertools import groupby,product
from math import isqrt,lcm
from 接続.ARC2.既存領域転写 import mixed_region_dicts_for_grid
from 接続.ARC2.既存物体特徴 import color_component_dicts_for_grid
from 接続.ARC2.既存側周期 import minimal_period

def endpoint_roots(values,target):
 """All integer roots of observed quadratic endpoint minus target.
 None denotes an identically zero equation; empty set denotes no roots.
 """
 if len(values)<3:return set()
 differences=[b-a for a,b in zip(values,values[1:])]
 second=[b-a for a,b in zip(differences,differences[1:])]
 if len(set(second))!=1:return set()
 a=second[0];b=2*differences[0]-a;c=2*(values[0]-target)
 if a==0:
  if b==0:return None if c==0 else set()
  return {-c//b} if (-c)%b==0 else set()
 discriminant=b*b-4*a*c
 if discriminant<0:return set()
 root=isqrt(discriminant)
 if root*root!=discriminant:return set()
 return {v//(2*a) for v in (-b-root,-b+root) if v%(2*a)==0}

def polynomial(values,n):
 differences=[b-a for a,b in zip(values,values[1:])]
 second=[b-a for a,b in zip(differences,differences[1:])]
 if len(values)<3 or len(set(second))!=1:return None
 return values[0]+n*differences[0]+n*(n-1)//2*second[0]

def sequence_laws(values):
 if len(values)<3:return []
 d=[b-a for a,b in zip(values,values[1:])];dd=[b-a for a,b in zip(d,d[1:])];laws=[]
 if len(set(dd))==1:laws.append(('quadratic',values[0],d[0],dd[0]))
 for p in range(1,len(d)):
  if all(v==d[i%p] for i,v in enumerate(d)):laws.append(('periodic_difference',values[0],tuple(d[:p])))
 return laws

def sequence_value(law,n):
 if law[0]=='quadratic':return law[1]+n*law[2]+n*(n-1)//2*law[3]
 d=law[2];q,r=divmod(n,len(d));return law[1]+q*sum(d)+sum(d[:r])

def ceildiv(a,b):return -((-a)//b)

def intersect_intervals(xs,ys):
 out=[]
 for a,b in xs:
  for c,d in ys:
   lo=max(a,c);hi=d if b is None else b if d is None else min(b,d)
   if hi is None or lo<=hi:out.append((lo,hi))
 return out

def nonnegative_intervals(a,b,c,lo):
 """All integers q>=lo with a*q*q+b*q+c>=0, without floating roots."""
 if a==0:
  if b==0:return [(lo,None)] if c>=0 else []
  if b>0:return [(max(lo,ceildiv(-c,b)),None)]
  hi=c//(-b);return [(lo,hi)] if lo<=hi else []
 if a<0:
  a,b,c=-a,-b,-c;D=b*b-4*a*c
  if D<0:return []
  t=isqrt(D);low=max(lo,ceildiv(-t-b,2*a));hi=(t-b)//(2*a)
  return [(low,hi)] if low<=hi else []
 D=b*b-4*a*c
 if D<=0:return [(lo,None)]
 t=isqrt(D-1);badlo=ceildiv(-t-b,2*a);badhi=(t-b)//(2*a)
 if badlo>badhi:return [(lo,None)]
 out=[]
 if lo<badlo:out.append((lo,badlo-1))
 out.append((max(lo,badhi+1),None));return out

def containing_indices(laws,window,source_count):
 period=1
 for law in laws:
  if law[0]=='periodic_difference':period=lcm(period,len(law[2]))
 indices=set();unbounded=False
 for residue in range(period):
  lo=max(0,ceildiv(source_count-residue,period));intervals=[(lo,None)]
  for axis,law in enumerate(laws):
   vals=[sequence_value(law,period*q+residue) for q in range(3)]
   a=vals[2]-2*vals[1]+vals[0];b=2*(vals[1]-vals[0])-a;c=2*vals[0]
   # Work with doubled coordinates to keep every coefficient integral.
   sign=-1 if axis<2 else 1
   intervals=intersect_intervals(intervals,nonnegative_intervals(sign*a,sign*b,sign*(c-2*window[axis]),lo))
  for low,hi in intervals:
   if hi is None:unbounded=True
   else:indices.update(period*q+residue for q in range(low,hi+1))
 return sorted(indices),unbounded

def observe(g):
 counts=Counter(v for row in g for v in row)
 if not counts:return []
 modes=[v for v,n in counts.items() if n==max(counts.values())]
 if len(modes)!=1:return []
 bg=modes[0];comps=mixed_region_dicts_for_grid(g,bg,False);roles=[]
 for color in sorted({v for row in g for v in row}-{bg}):
  markers=[c for c in comps if c['colors']==[color]]
  if len(markers)!=2 or any(c['size']!=3 or (c['bbox'][2]-c['bbox'][0]+1,c['bbox'][3]-c['bbox'][1]+1)!=(2,2) for c in markers):continue
  body=[c for c in comps if c not in markers]
  if any(color in c['colors'] for c in body):continue
  body=sorted(body,key=lambda c:c['bbox'][1]);boxes=[list(c['bbox']) for c in body]
  if len(body)<3 or any(a['bbox'][3]>=b['bbox'][1] for a,b in zip(body,body[1:])):continue
  cells=[p for c in markers for p in c['cells']];window=[min(r for r,c in cells),min(c for r,c in cells),max(r for r,c in cells),max(c for r,c in cells)]
  laws=[sequence_laws([b[i] for b in boxes]) for i in range(4)]
  future=[];unbounded=False
  for combination in product(*laws):
   indices,infinite=containing_indices(combination,window,len(body));unbounded|=infinite
   for n in indices:
    box=[sequence_value(law,n) for law in combination]
    record={'series_index_1based':n+1,'predicted_bbox':box,'window_shape':[window[2]-window[0]+1,window[3]-window[1]+1]}
    if record not in future:future.append(record)
  roles.append({'background':bg,'marker_color':color,'marker_window':window,'body_bboxes':boxes,'body_palettes':[list(c['colors']) for c in body],'future_geometric_roles':future,'unbounded_geometry':unbounded,'endpoint_law_counts':[len(v) for v in laws]})
 return roles

def radial_predict(g,role,transpose=False):
 if len(role['future_geometric_roles'])!=1:return None,{'failure':'geometry_not_unique'}
 bg=role['background'];marker=role['marker_color'];by_radius=defaultdict(set);steps=set();observed=[]
 for box in role['body_bboxes']:
  r,c,y,x=box;patch=[row[c:x+1]for row in g[r:y+1]]
  if transpose:patch=[list(row) for row in zip(*patch)]
  ph,pw=len(patch),len(patch[0]);center=(ph-1)//2
  if ph%2!=1:return None,{'failure':'no_integral_center'}
  palette=set(v for row in patch for v in row)-{bg};parts=[]
  for color in sorted(palette):
   for comp in color_component_dicts_for_grid(patch,color,False):
    a,b,d,e=comp['bbox'];mid=(a+d)//2
    if (d-a)%2:return None,{'failure':'component_center_not_integral'}
    descriptor=(color,tuple(sorted((rr-mid,cc)for rr,cc in comp['cells'])))
    parts.append((mid-center,descriptor))
  if len(parts)<1:return None,{'failure':'no_components'}
  positions=sorted(pos for pos,desc in parts)
  if len(set(positions))!=len(positions):return None,{'failure':'multiple_components_per_layer'}
  if len(positions)>1:
   gaps={b-a for a,b in zip(positions,positions[1:])}
   if len(gaps)!=1:return None,{'failure':'nonuniform_layers'}
   steps.update(gaps)
  if positions!=sorted(-p for p in positions):return None,{'failure':'asymmetric_layer_inventory'}
  for pos,desc in parts:by_radius[abs(pos)].add(desc)
  observed.append({'box':box,'positions':positions})
 if len(steps)!=1:return None,{'failure':'no_unique_observed_layer_step'}
 step=next(iter(steps));radii=sorted(by_radius)
 if radii!=list(range(0,max(radii)+1,step))or any(len(v)!=1 for v in by_radius.values()):return None,{'failure':'radial_roles_conflict'}
 descriptors=[next(iter(by_radius[k])) for k in radii]
 # Component geometry and pigment are independent observable periodic channels.
 colors=minimal_period([(d[0],)for d in descriptors]);masks=minimal_period([d[1]for d in descriptors])
 # Replay the factorized program over every complete observed source, including
 # background cells, before allowing any extrapolation.
 for box in role['body_bboxes']:
  a,b,d,e=box;source=[row[b:e+1] for row in g[a:d+1]]
  if transpose:source=[list(row) for row in zip(*source)]
  sh,sw=len(source),len(source[0]);sc=(sh-1)//2
  extent=max(abs(dr) for desc in descriptors for dr,dc in desc[1]);radius=sc-extent
  if radius<0 or radius%step:return None,{'failure':'source_layer_extent_mismatch'}
  replay=[[bg]*sw for _ in range(sh)]
  for pos in range(-radius,radius+1,step):
   k=abs(pos)//step;color=colors[k%len(colors)][0];mask=masks[k%len(masks)]
   for dr,dc in mask:
    rr=sc+pos+dr
    if not(0<=rr<sh and 0<=dc<sw):return None,{'failure':'source_replay_bounds'}
    if replay[rr][dc] not in (bg,color):return None,{'failure':'source_replay_conflict'}
    replay[rr][dc]=color
  if replay!=source:return None,{'failure':'source_replay_mismatch'}
 future=role['future_geometric_roles'][0];r,c,y,x=future['predicted_bbox'];h,w=y-r+1,x-c+1
 if transpose:h,w=w,h
 if h%2!=1:return None,{'failure':'future_center_not_integral','source_fitted':True}
 center=(h-1)//2;extent=max(abs(dr)for d in descriptors for dr,dc in d[1]);radius=center-extent
 if radius<0 or radius%step:return None,{'failure':'future_extent_not_layer_aligned','source_fitted':True}
 out=[[bg]*w for _ in range(h)];occupied={}
 for pos in range(-radius,radius+1,step):
  k=abs(pos)//step;color=colors[k%len(colors)][0];mask=masks[k%len(masks)]
  for dr,dc in mask:
   rr=center+pos+dr
   if not(0<=rr<h and 0<=dc<w):return None,{'failure':'out_of_bounds','source_fitted':True}
   if (rr,dc)in occupied and occupied[rr,dc]!=color:return None,{'failure':'ink_conflict','source_fitted':True}
   occupied[rr,dc]=color;out[rr][dc]=color
 if transpose:out=[list(row) for row in zip(*out)]
 a,b,d,e=role['marker_window'];out=[row[b-c:e-c+1]for row in out[a-r:d-r+1]]
 return out,{'source_fitted':True,'layer_step':step,'color_period':colors,'mask_period':masks,'source_layer_counts':[len(o['positions'])for o in observed],'future_layer_count':2*(radius//step)+1,'future_bbox':future['predicted_bbox'],'complete_source_ownership':True,'source_replays':len(role['body_bboxes'])}

def crop(g,b):
 r,c,y,x=b
 return [row[c:x+1] for row in g[r:y+1]]
def rot(g):return [list(row) for row in zip(*g[::-1])]
def transform(g,k,flip):
 for _ in range(k):g=rot(g)
 return [row[::-1] for row in g] if flip else g

def inverse(g,k,flip):
 if flip:g=[row[::-1] for row in g]
 for _ in range((-k)%4):g=rot(g)
 return g

def runs(row):
 r=[(c,len(list(v))) for c,v in groupby(row)]
 return tuple(c for c,n in r),tuple(n for c,n in r)

def encode_row(row,fixed_width):
 return (tuple(row),(1,)*len(row)) if fixed_width else runs(row)

def affine(points):
 """Unique observed affine function; a constant domain permits only constant extension."""
 table={}
 for x,y in points:
  if x in table and table[x]!=y:return None
  table[x]=y
 xs=sorted(table)
 a=Fraction(table[xs[-1]]-table[xs[0]],xs[-1]-xs[0]) if len(xs)>1 else Fraction(0)
 b=table[xs[0]]-a*xs[0]
 return (a,b) if all(a*x+b==y for x,y in table.items()) else None

def axis_models(g,role,transpose=False):
 future=role['future_geometric_roles']
 if len(future)!=1:return [],{'failure':'future_role_not_unique'}
 bg=role['background'];patches=[crop(g,b) for b in role['body_bboxes']]
 if transpose:patches=[[list(row) for row in zip(*p)] for p in patches]
 fixed_width=len({len(p[0]) for p in patches})==1
 palettes=[set(v for row in p for v in row)-{bg} for p in patches]
 mono=all(len(p)==1 for p in palettes)
 period=minimal_period([(next(iter(p)),) for p in palettes]) if mono else None
 words=[];observations={}
 for patch in patches:
  word=[];w=len(patch[0])
  for row in patch:
   sig,lens=encode_row([int(v!=bg) for v in row] if mono else row,fixed_width)
   word.append(sig)
   observations.setdefault(sig,[]).append((w,lens))
  words.append(word)
 rules={}
 for sig,samples in observations.items():
  rules[sig]=[affine([(w,lens[j]) for w,lens in samples]) for j in range(len(sig))]
  if None in rules[sig]:return [],{'failure':'non_affine_row_runs'}
 # Exhaustive within the source-witnessed grammar: a nonempty repeat core in
 # every source, at least two copies in one source, positive affine growth.
 first=words[0];models=[]
 for a in range(len(first)):
  for b in range(len(first)-a):
   for p in range(1,len(first)-a-b+1):
    prefix=first[:a];suffix=first[len(first)-b:] if b else [];unit=first[a:a+p]
    counts=[]
    for word in words:
     middle=len(word)-a-b
     if middle<=0 or middle%p:break
     k=middle//p
     if word!=prefix+unit*k+suffix:break
     counts.append(k)
    if len(counts)!=len(words) or max(counts)<2:continue
    if any(b<=a for a,b in zip(counts,counts[1:])):continue
    for growth in sequence_laws(counts):models.append((prefix,unit,suffix,growth))
 outputs=[];incomplete=0;records=[]
 box=future[0]['predicted_bbox'];n=future[0]['series_index_1based']-1
 h,w=box[2]-box[0]+1,box[3]-box[1]+1
 if transpose:h,w=w,h
 unresolved_width=any(len({v[0] for v in samples})==1 and samples[0][0]!=w for samples in observations.values())
 for pre,unit,suf,growth in models:
  count=Fraction(sequence_value(growth,n))
  if unresolved_width:incomplete+=1;continue
  if count.denominator!=1 or count<1:incomplete+=1;continue
  word=pre+unit*int(count)+suf;patch=[];valid=len(word)==h
  for sig in word:
   lens=[a*w+b for a,b in rules[sig]]
   if any(v.denominator!=1 or v<1 for v in lens) or sum(lens)!=w:valid=False;break
   row=[c for c,v in zip(sig,lens) for _ in range(int(v))]
   if mono:row=[period[n%len(period)][0] if c else bg for c in row]
   patch.append(row)
  if not valid:incomplete+=1;continue
  if transpose:patch=[list(row) for row in zip(*patch)]
  a,b,d,e=role['marker_window'];out=crop(patch,[a-box[0],b-box[1],d-box[0],e-box[1]])
  outputs.append(out)
  records.append({'prefix_rows':len(pre),'period_rows':len(unit),'suffix_rows':len(suf),'source_repeat_counts':[sequence_value(growth,i) for i in range(len(words))],'future_repeat_count':int(count)})
 return outputs,{'fitted_models':len(models),'incomplete_models':incomplete,'models':records,'row_symbols':len(rules),'monochrome':mono}

def centered_row_models(g,role,transpose=False):
 future=role['future_geometric_roles'][0];bg=role['background'];patches=[crop(g,b) for b in role['body_bboxes']]
 if transpose:patches=[[list(row) for row in zip(*p)] for p in patches]
 parity={(len(p)-1)%2 for p in patches}
 if len(parity)!=1:return [],{'failure':'center_parity_changes'}
 parity=next(iter(parity));fixed_width=len({len(p[0]) for p in patches})==1;palettes=[set(v for row in p for v in row)-{bg} for p in patches]
 mono=all(len(p)==1 for p in palettes);pigment=minimal_period([(next(iter(p)),) for p in palettes]) if mono else None
 table={};observations={};source_rows=[]
 for patch in patches:
  ph,pw=len(patch),len(patch[0]);symbols=[]
  for r,row in enumerate(patch):
   sig,lens=encode_row([int(v!=bg) for v in row] if mono else row,fixed_width);q=(abs(2*r-(ph-1))-parity)//2
   if q in table and table[q]!=sig:return [],{'failure':'radial_row_symbol_conflict'}
   table[q]=sig;observations.setdefault(sig,[]).append((pw,lens));symbols.append(sig)
  source_rows.append(symbols)
 if sorted(table)!=list(range(len(table))):return [],{'failure':'radial_row_gap'}
 rules={}
 for sig,samples in observations.items():
  rules[sig]=[affine([(w,lens[j]) for w,lens in samples]) for j in range(len(sig))]
  if None in rules[sig]:return [],{'failure':'radial_row_width_conflict'}
 periods=[p for p in range(1,len(table)//2+1) if all(table[q]==table[q%p] for q in table)]
 # Full source replay through these symbol/width channels, including background.
 for patch in patches:
  ph,pw=len(patch),len(patch[0])
  for r,row in enumerate(patch):
   q=(abs(2*r-(ph-1))-parity)//2;sig=table[q]
   lengths=[a*pw+b for a,b in rules[sig]]
   replay=[v for v,length in zip(sig,lengths) for _ in range(int(length))]
   expected=[int(v!=bg) for v in row] if mono else row
   if replay!=expected:return [],{'failure':'radial_row_source_replay'}
 box=future['predicted_bbox'];h,w=box[2]-box[0]+1,box[3]-box[1]+1
 if transpose:h,w=w,h
 n=future['series_index_1based']-1;outputs=[];incomplete=0
 unresolved_width=any(len({v[0] for v in samples})==1 and samples[0][0]!=w for samples in observations.values())
 for p in periods:
  if unresolved_width or (h-1)%2!=parity:incomplete+=1;continue
  patch=[];valid=True
  for r in range(h):
   q=(abs(2*r-(h-1))-parity)//2;sig=table[q%p];lengths=[a*w+b for a,b in rules[sig]]
   if any(v.denominator!=1 or v<1 for v in lengths) or sum(lengths)!=w:valid=False;break
   row=[v for v,length in zip(sig,lengths) for _ in range(int(length))]
   if mono:row=[pigment[n%len(pigment)][0] if v else bg for v in row]
   patch.append(row)
  if not valid:incomplete+=1;continue
  if transpose:patch=[list(row) for row in zip(*patch)]
  a,b,d,e=role['marker_window'];outputs.append(crop(patch,[a-box[0],b-box[1],d-box[0],e-box[1]]))
 return outputs,{'fitted_models':len(periods),'incomplete_models':incomplete,'periods':periods,'source_radius_symbols':len(table),'center_parity':parity,'source_replays':len(patches)}

def folded_strip_models(g,role,transpose=False):
 bg=role['background'];patches=[crop(g,b) for b in role['body_bboxes']]
 if transpose:patches=[[list(row) for row in zip(*p)] for p in patches]
 parities={(len(p)-1)%2 for p in patches}
 if len(parities)!=1:return [],{'failure':'strip_center_parity_changes'}
 parity=next(iter(parities));folded=[]
 for patch in patches:
  if patch!=patch[::-1]:return [],{'failure':'strip_not_reflection_symmetric'}
  folded.append(patch[len(patch)//2:])
 widths=[len(p[0]) for p in folded];outputs=[];records=[];incomplete=0
 for width in range(1,min(widths)+1):
  if any(w%width for w in widths):continue
  samples=[];bounds={};valid=True
  for n,patch in enumerate(folded):
   for j in range(len(patch[0])//width):
    cells=[(r,c,patch[r][j*width+c]) for r in range(len(patch)) for c in range(width) if patch[r][j*width+c]!=bg]
    if not cells:valid=False;break
    lo=min(r for r,c,v in cells);hi=max(r for r,c,v in cells)
    if j in bounds and bounds[j]!=(lo,hi):valid=False;break
    bounds[j]=(lo,hi);samples.append((n,j,[[patch[r][j*width+c] for c in range(width)] for r in range(lo,hi+1)]))
  if not valid or sorted(bounds)!=list(range(len(bounds))) or len(bounds)<3:continue
  lows=affine([(j,v[0]) for j,v in bounds.items()]);heights={hi-lo+1 for lo,hi in bounds.values()}
  if lows is None or lows[0].denominator!=1 or lows[0]<=0 or len(heights)!=1:continue
  stride,origin=map(int,lows);height=next(iter(heights));cores=[tile for n,j,tile in samples if j==0]
  if len(cores)!=len(patches):continue
  core_colors=[set(v for row in tile for v in row)-{bg} for tile in cores]
  if any(len(v)!=1 for v in core_colors):continue
  masks=[[[int(v!=bg) for v in row] for row in tile] for tile in cores]
  if any(mask!=masks[0] for mask in masks):continue
  pigments=minimal_period([(next(iter(v)),) for v in core_colors]);cycle=[v[0] for v in pigments]
  outer=[(n,j,tile) for n,j,tile in samples if j>0]
  if len({j for n,j,tile in outer})<2:continue
  phases={};outermask=[[int(v!=bg) for v in row] for row in outer[0][2]]
  for rr in range(height):
   for cc in range(width):
    vals=[(n-j,tile[rr][cc]) for n,j,tile in outer]
    if any(int(v!=bg)!=outermask[rr][cc] for k,v in vals):valid=False;break
    if outermask[rr][cc]:
     allowed=[phase for phase in range(len(cycle)) if all(cycle[(k+phase)%len(cycle)]==v for k,v in vals)]
     if not allowed:valid=False;break
     phases[rr,cc]=allowed
  if not valid:continue
  def build(n,h,w):
   if w%width or (h-1)%2!=parity:return None
   count=w//width
   if count<1 or origin+stride*(count-1)+height!=(h+1)//2:return None
   half=[[bg]*w for _ in range((h+1)//2)]
   for j in range(count):
    for rr in range(height):
     for cc in range(width):
      r=origin+stride*j+rr;c=width*j+cc
      if not(0<=r<len(half)):return None
      if j==0:values={cycle[n%len(cycle)]} if masks[0][rr][cc] else {bg}
      else:values={cycle[(n-j+phase)%len(cycle)] for phase in phases[rr,cc]} if outermask[rr][cc] else {bg}
      if len(values)!=1:return None
      half[r][c]=next(iter(values))
   return [half[(abs(2*r-(h-1))-parity)//2][:] for r in range(h)]
  # Validate the whole raster, including gaps/background, before retaining.
  if any(build(n,len(p),len(p[0]))!=p for n,p in enumerate(patches)):continue
  future=role['future_geometric_roles'][0];box=future['predicted_bbox'];h,w=box[2]-box[0]+1,box[3]-box[1]+1
  if transpose:h,w=w,h
  patch=build(future['series_index_1based']-1,h,w)
  record={'strip_width':width,'strip_height':height,'radial_stride':stride,'radial_origin':origin,'pigment_cycle':cycle,'outer_cell_phases':[[r,c,p] for (r,c),p in sorted(phases.items())],'source_replays':len(patches)}
  if patch is None:incomplete+=1;record['future_failure']=True
  else:
   if transpose:patch=[list(row) for row in zip(*patch)]
   a,b,d,e=role['marker_window'];outputs.append(crop(patch,[a-box[0],b-box[1],d-box[0],e-box[1]]))
  records.append(record)
 return outputs,{'fitted_models':len(records),'incomplete_models':incomplete,'models':records}

def predict(g,with_evidence=False):
 if not g or not g[0] or any(len(row)!=len(g[0]) for row in g):
  report={'status':'HOLD','failure':'invalid_grid','fitted_predictions':0,'incomplete_models':0,'distinct_predictions':0,'views':[]}
  return (None,report) if with_evidence else None
 outputs=[];evidence=[];incomplete=0
 for k in range(4):
  for flip in (False,True):
   view=transform(g,k,flip);roles=observe(view)
   for role in roles:
    if role.get('unbounded_geometry') or len(role['future_geometric_roles'])!=1:
     incomplete+=int(role.get('unbounded_geometry',False) or len(role['future_geometric_roles'])>1);continue
    for transpose in (False,True):
     axis,record=axis_models(view,role,transpose)
     incomplete+=record.get('incomplete_models',0)
     outputs.extend(inverse(out,k,flip) for out in axis)
     evidence.append({'rotation':k,'reflection':flip,'internal_transpose':transpose,'family':'axis','record':record})
     centered,record=centered_row_models(view,role,transpose)
     incomplete+=record.get('incomplete_models',0)
     outputs.extend(inverse(out,k,flip) for out in centered)
     evidence.append({'rotation':k,'reflection':flip,'internal_transpose':transpose,'family':'centered_rows','record':record})
     strips,record=folded_strip_models(view,role,transpose)
     incomplete+=record.get('incomplete_models',0)
     outputs.extend(inverse(out,k,flip) for out in strips)
     evidence.append({'rotation':k,'reflection':flip,'internal_transpose':transpose,'family':'folded_strips','record':record})
    for transpose in (False,True):
     radial,record=radial_predict(view,role,transpose)
     if radial is not None:outputs.append(inverse(radial,k,flip))
     elif record.get('source_fitted',False):incomplete+=1
     evidence.append({'rotation':k,'reflection':flip,'internal_transpose':transpose,'family':'radial','record':record})
 distinct={tuple(map(tuple,out)) for out in outputs}
 out=[list(row) for row in next(iter(distinct))] if len(distinct)==1 and not incomplete else None
 report={'status':'EMIT' if out is not None else 'HOLD','fitted_predictions':len(outputs),'incomplete_models':incomplete,'distinct_predictions':len(distinct),'views':evidence}
 return (out,report) if with_evidence else out

def fit(teachers):
 """Fit only an all-teacher contract; never select a model by teacher success."""
 if not teachers or any(predict(p['input'])!=p['output'] for p in teachers):return None
 return {'kind':'observed_series_composition','version':4}
