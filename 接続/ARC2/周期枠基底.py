"""Reconstruction using accepted geometry helpers; not recovered prior source.
Hypothesis: complete hidden rectangular corners by same-row corner motif transfer.
Visible cells are never repainted; monochrome/alternating edge prior is explicit.
"""
from collections import Counter
from 接続.ARC2.既存枠計数 import color_components, perimeter_cells
from 接続.ARC2.既存側周期 import component_bbox
from 接続.ARC2.既存配置展開 import crop_bbox

def box_cells(b):
 return {(r,c) for r in range(b[0],b[2]+1) for c in range(b[1],b[3]+1)}

def roles(g):
 counts=Counter(v for row in g for v in row); largest=max(counts.values())
 for bg,n in sorted(counts.items()):
  if n!=largest:continue
  for color in sorted(counts):
   if color==bg:continue
   for comp in color_components(g,color):
    b=comp['bbox']; r0,c0,r1,c1=b
    if r1-r0<2 or c1-c0<2 or comp['cells']!=perimeter_cells(b):continue
    inner=(r0+1,c0+1,r1-1,c1-1); fills={g[r][c] for r,c in box_cells(inner)}
    if len(fills)!=1:continue
    hidden=box_cells(b); visible={(r,c) for r,row in enumerate(g) for c,v in enumerate(row) if (r,c) not in hidden and v!=bg}
    # Adjacent palette graph joins alternating colors, while repeated monochrome
    # fragments join by color. Separate decoration palettes stay separate.
    palettes={g[r][c]:{g[r][c]} for r,c in visible}
    for r,c in visible:
     for q in ((r+1,c),(r,c+1)):
      if q in visible:
       a,z=g[r][c],g[q[0]][q[1]]; union=palettes[a]|palettes[z]
       for v in union:palettes[v]=union
    groups=sorted({tuple(sorted(s)) for s in palettes.values()}); frames=[]; invalid=False
    for palette in groups:
     pts={(r,c) for r,c in visible if g[r][c] in palette}; fb=component_bbox(pts); edge=perimeter_cells(fb)
     if not(edge&hidden):continue
     if not pts==edge-hidden or len(palette)>2:invalid=True;break
     # Existing old continuous alternation hypothesis is first checked on input.
     phases={}
     for r,c in pts:phases.setdefault((r+c)%len(palette),set()).add(g[r][c])
     if len(phases)!=len(palette) or any(len(s)!=1 for s in phases.values()):invalid=True;break
     frames.append({'box':fb,'palette':palette,'phase':{k:next(iter(v)) for k,v in phases.items()}})
    if not invalid and frames:yield {'background':bg,'border':color,'fill':next(iter(fills)),'window':b,'inner':inner,'hidden':hidden,'frames':frames}

def render_role(g,role,mode):
 out=[[role['fill'] for _ in row] for row in g]; assigned={}; diagnostics=[]
 for f in role['frames']:
  b=f['box']; r0,c0,r1,c1=b; p=len(f['palette']); hidden=role['hidden']; corners={(r0,c0),(r0,c1),(r1,c0),(r1,c1)}; hc=corners&hidden
  anchors=[]
  for r,c in sorted(hc):
   source=(r,c0+c1-c) if mode=='horizontal' else (r0+r1-r,c) if mode=='vertical' else (r0+r1-r,c0+c1-c)
   if mode!='continuous':
    if source in hidden:return None,{'failure':'corner_source_hidden'}
    anchors.append(((r,c),g[source[0]][source[1]]))
  for r,c in perimeter_cells(b)&hidden:
   values={value if p==1 else f['palette'][1-f['palette'].index(value)] if (abs(r-ar)+abs(c-ac))%2 else value for (ar,ac),value in anchors if r==ar or c==ac}
   if not values:values={f['phase'][(r+c)%p]}
   if len(values)!=1:return None,{'failure':'corner_proposals_disagree'}
   value=next(iter(values))
   if (r,c) in assigned and assigned[r,c]!=value:return None,{'failure':'frame_ownership_conflict'}
   assigned[r,c]=value;out[r][c]=value
  diagnostics.append({'box':b,'hidden_corners':sorted(hc),'anchors':anchors})
 return crop_bbox(out,role['inner']),{'frames':diagnostics}
