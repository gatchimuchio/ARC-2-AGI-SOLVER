import sys,json,random,hashlib,copy,ast
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from 接続.ARC2.矩形継目 import seam_rectangle as m
from 接続.ARC2.矩形継目教材 import 矩形継目教材
from 接続.ARC2 import 矩形継目教材 as adapter
base=m.base
checks=[]
def ck(name,ok,detail=None):
 assert ok,(name,detail)
 checks.append(dict(name=name,passed=True,detail=detail))
hashes={'接続/ARC2/矩形継目/seam_rectangle.py':'1e7d97da06e3c72808147c0e6e4fedd0956798733dfd3f605954695836f6d0c4','接続/ARC2/矩形継目/anchored_rectangle.py':'3b25da045f96cb799a4d84c0c4159fd3b39e34214212f72936ea5b87940e4ad7'}
def source_hash(p):
 return hashlib.sha256((ROOT/p).read_bytes().replace(b'from . import anchored_rectangle as base',b'import anchored_rectangle as base')).hexdigest()
for p,h in hashes.items():ck('initial_hash_'+p,source_hash(p)==h)
def oracle(grid,role):
 gh,gw=len(grid),len(grid[0]); pieces=role['pieces']; host=role['host'];sr,sc=role['signs'];ar,ac=role['anchor'];border=role['border'];area=sum(p['area'] for p in pieces)
 norm=[]
 for p in pieces:
  r,c,R,C=p['bbox'];norm.append((R-r+1,C-c+1,[(rr-r,cc-c,v) for rr,cc,v in p['cells']]))
 found=set();outs=set()
 for h in range(1,gh+1):
  for w in range(1,gw+1):
   if h*w!=area:continue
   top=ar if sr==1 else ar-h+1;left=ac if sc==1 else ac-w+1
   if not(0<=top<=gh-h and 0<=left<=gw-w):continue
   order=[host]+[i for i in range(len(pieces)) if i!=host]
   def visit(k,paint,pos):
    if k==len(order):
     if len(paint)!=area:return
     found.add((h,w,tuple(sorted(pos))))
     g=[[role['background']]*gw for _ in range(gh)]
     for (r,c),v in paint.items():g[top+r][left+c]=v
     outs.add(tuple(map(tuple,g)));return
    i=order[k];ph,pw,cells=norm[i]
    coords=[(0 if sr==1 else h-ph,0 if sc==1 else w-pw)] if k==0 else [(r,c) for r in range(h-ph+1) for c in range(w-pw+1)]
    for r,c in coords:
     if r<0 or c<0 or r+ph>h or c+pw>w:continue
     moved={(r+dr,c+dc):v for dr,dc,v in cells}
     if set(moved)&set(paint):continue
     if any(v!=border for (rr,cc),v in moved.items() if rr==0 or rr==h-1 or cc==0 or cc==w-1):continue
     visit(k+1,{**paint,**moved},pos+[(i,r,c)])
   visit(0,{},[])
 return found,outs
def seam_oracle(role,positions):
 rects=[]
 for i,r,c in positions:
  p=role['pieces'][i];r0,c0,r1,c1=p['bbox'];vals={(rr-r0+r,cc-c0+c):v for rr,cc,v in p['cells']}
  rects.append((r,c,r+r1-r0+1,c+c1-c0+1,vals))
 # Compute the full shared interval analytically per pair of rectangles.
 for i,(r,c,R,C,vals) in enumerate(rects):
  for s,t,S,T,other in rects[i+1:]:
   profiles=None
   if R==s or S==r:
    lo,hi=max(c,t),min(C,T)
    if lo<hi:
     ra,rb=(R-1,s) if R==s else (r,S-1)
     profiles=([vals[ra,x] for x in range(lo,hi)],[other[rb,x] for x in range(lo,hi)])
   if C==t or T==c:
    lo,hi=max(r,s),min(R,S)
    if lo<hi:
     ca,cb=(C-1,t) if C==t else (c,T-1)
     profiles=([vals[x,ca] for x in range(lo,hi)],[other[x,cb] for x in range(lo,hi)])
   if profiles:
    a,b=profiles
    if a!=b and set(a)!={role['border']} and set(b)!={role['border']}:return False
 return True
pairs=json.loads((ROOT/'検証/矩形継目資料/teachers-only.json').read_text())
state,rec=m.fit(pairs);ck('teachers_exact',state is not None and rec['status']=='FIT')
for idx,p in enumerate(pairs):
 a,b=copy.deepcopy(p['input']),copy.deepcopy(p['output'])
 for flip in range(2):
  for rot in range(4):
   out,r=m.predict(state,a);ck(f'teacher_{idx}_d4_{flip}_{rot}',out==b)
   a=[list(x) for x in zip(*a[::-1])];b=[list(x) for x in zip(*b[::-1])]
  a=[row[::-1] for row in a];b=[row[::-1] for row in b]
 out,r=m.predict(state,p['input']);work=r['work']
 for budget in range(1,work):
  o,q=m.predict(state,p['input'],budget=budget)
  ck(f'teacher_{idx}_budget_{budget}',o is None and q['status']=='RESOURCE_INCOMPLETE' and not q['complete'])
 ck(f'teacher_{idx}_exact_budget',m.predict(state,p['input'],budget=work)[0]==p['output'])
# Deliberately alternating wall pixels is not a whole-wall interval.
for name,a,b,want in [('equal',[2,3,2],[2,3,2],True),('wall_a',[1,1,1],[2,3,4],True),('wall_b',[2,3,4],[1,1,1],True),('alternating_walls',[1,2,1],[2,1,2],False),('partial_match',[2,3,2],[2,4,2],False)]:
 role={'border':1,'pieces':[{'bbox':[0,0,2,0],'cells':[[r,0,v] for r,v in enumerate(a)]},{'bbox':[5,7,7,7],'cells':[[r+5,7,v] for r,v in enumerate(b)]}]}
 ok,records,_=m.certify_contacts(role,[(0,0,0),(1,0,1)],base.WorkBudget(base.LIMIT));ck(name,ok==want and len(records)==1)
rng=random.Random(154);stats={'cases':0,'geometry':0,'seam_valid':0,'seam_invalid':0,'ambiguous':0}
for case in range(360):
 gh,gw=rng.randint(2,6),rng.randint(2,6);pieces=[]
 if case<180:
  for i in range(rng.randint(2,5)):
   ph,pw=rng.randint(1,3),rng.randint(1,3)
   pieces.append(dict(component_index=i,area=ph*pw,bbox=[0,0,ph-1,pw-1],cells=[[r,c,1 if rng.random()<.8 else rng.choice([2,3])] for r in range(ph) for c in range(pw)]))
  sr,sc=rng.choice([-1,1]),rng.choice([-1,1]);anchor=(rng.randrange(gh),rng.randrange(gw));host=rng.randrange(len(pieces))
 else:
  gh,gw=rng.randint(3,5),rng.randint(3,5);rects=[(0,0,gh,gw)]
  for _ in range(rng.randint(1,4)):
   choices=[i for i,(r,c,h,w) in enumerate(rects) if h>1 or w>1]
   if not choices:break
   r,c,h,w=rects.pop(rng.choice(choices))
   if h>1 and (w==1 or rng.randrange(2)):
    k=rng.randrange(1,h);rects.extend([(r,c,k,w),(r+k,c,h-k,w)])
   else:
    k=rng.randrange(1,w);rects.extend([(r,c,h,k),(r,c+k,h,w-k)])
  sr,sc=rng.choice([-1,1]),rng.choice([-1,1]);anchor=(0 if sr==1 else gh-1,0 if sc==1 else gw-1)
  host=next(i for i,(r,c,h,w) in enumerate(rects) if r<=anchor[0]<r+h and c<=anchor[1]<c+w)
  for i,(r,c,h,w) in enumerate(rects):
   pieces.append(dict(component_index=i,area=h*w,bbox=[0,0,h-1,w-1],cells=[[dr,dc,1 if r+dr in (0,gh-1) or c+dc in (0,gw-1) or case%3==0 else rng.choice([1,2,3])] for dr in range(h) for dc in range(w)]))
 role=dict(background=0,marker=9,border=1,anchor=anchor,signs=(sr,sc),host=host,pieces=pieces);g=[[0]*gw for _ in range(gh)]
 models,_=oracle(g,role);expected={p for h,w,p in models if seam_oracle(role,p)};outputs=set()
 for h,w,positions in models:
  if positions not in expected:continue
  top=anchor[0] if sr==1 else anchor[0]-h+1;left=anchor[1] if sc==1 else anchor[1]-w+1;out=[[0]*gw for _ in range(gh)]
  for i,r,c in positions:
   p=pieces[i];r0,c0,_,_=p['bbox']
   for rr,cc,v in p['cells']:out[top+r+rr-r0][left+c+cc-c0]=v
  outputs.add(tuple(map(tuple,out)))
 with patch.object(base,'observe',return_value=((role,),{'role_count':1})):
  out,rec=m.predict(state,g)
 rr=rec['all_role_returns'][0];actual={tuple(sorted(tuple(p) for p in x['placements'])) for x in rr['all_proposals'] if x['seam_qualified']}
 ck(f'oracle_{case}',len(rr['all_proposals'])==len(models) and actual==expected and rr['feasible_count']==len(expected) and rr['distinct_outputs']==len(outputs) and (out is not None)==(len(outputs)==1) and (out is None or tuple(map(tuple,out)) in outputs))
 stats['cases']+=1;stats['geometry']+=len(models);stats['seam_valid']+=len(expected);stats['seam_invalid']+=len(models)-len(expected);stats['ambiguous']+=len(outputs)>1
# Public parser remains a direct use of unchanged base observe.
for g in [None,[],[[True]],[[0],[0,1]],[[10]],[[0]*4 for _ in range(4)]]:
 ck('unchanged_no_role_'+repr(g),not base.observe(g)[0] and m.predict(state,g)[1]['failure']=='no_structural_role')
# Real exhaustive arrangement blowup must never leak a partial result.
g=[[0]*30 for _ in range(10)]
for i in range(10):g[2][2+2*i]=1
for r,c in [(1,1),(1,2),(2,1)]:g[r][c]=9
out,r=m.predict(state,g);ck('real_default_exhaustion',out is None and r['status']=='RESOURCE_INCOMPLETE' and not r['complete'])
g2=g+[[0]*30];s,r=m.fit([{'input':g,'output':g},{'input':g2,'output':g2}]);ck('fit_exhaustion_propagates',s is None and r['status']=='RESOURCE_INCOMPLETE')
# Later-role failure and later exhaustion override earlier success.
role=base.observe(pairs[0]['input'])[0][0];geom=base.assemble(pairs[0]['input'],role,base.WorkBudget(base.LIMIT))[1]
for label,second,want in [('failed',{'placements':[]},'HOLD'),('agree',geom,'CANDIDATE')]:
 with patch.object(base,'observe',return_value=((role,role),{})),patch.object(base,'assemble',side_effect=[(None,geom),(None,second)]):
  o,r=m.predict(state,pairs[0]['input']);ck('retained_role_'+label,r['status']==want and len(r['all_role_returns'])==2)
with patch.object(base,'observe',return_value=((role,role),{})),patch.object(base,'assemble',side_effect=[(None,geom),base.BudgetIncomplete()]):
 o,r=m.predict(state,pairs[0]['input']);ck('later_exhaustion',o is None and r['status']=='RESOURCE_INCOMPLETE')
for p,h in hashes.items():ck('final_hash_'+p,source_hash(p)==h)
boundary=矩形継目教材(pairs)
ck('empty_prior',boundary.記録()['事前支持数']==0 and boundary.記録()['全教師再現'])
for i,pair in enumerate(pairs):ck('adapter_teacher_'+str(i),boundary.候補(pair['input'],{})[0]==pair['output'])
for stage in ('fit','predict'):
 with patch.object(adapter.api,stage,return_value=(None,{'status':'RESOURCE_INCOMPLETE','complete':False})):
  try:
   if stage=='fit':矩形継目教材(pairs)
   else:boundary.候補(pairs[0]['input'],{})
  except base.BudgetIncomplete:ck('adapter_'+stage+'_resource',True)
  else:raise AssertionError('resource swallowed')
try:矩形継目教材([{'input':g,'output':g},{'input':g2,'output':g2}])
except base.BudgetIncomplete:ck('adapter_real_fit_resource',True)
else:raise AssertionError('real resource swallowed')
print(json.dumps(dict(successful=True,tests_run=len(checks),stats=stats)))
