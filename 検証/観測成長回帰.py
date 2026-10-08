import sys,json,hashlib,importlib.util,copy,itertools
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
source=ROOT/'接続/ARC2/観測成長/growth_series.py'
assert hashlib.sha256(source.read_bytes()).hexdigest()=='6b2139090fb1d2f94412bc8b330f33ed4868a03c1736f3a6f8ab3448ee99faaa'
spec=importlib.util.spec_from_file_location('audited',source);s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
report={}
# Only authorized three teachers.
teachers=json.loads((ROOT/'検証/観測成長資料/teachers-only.json').read_text())
assert len(teachers)==3
checks=[s.predict(s.transform(p['input'],k,f))==s.transform(p['output'],k,f) for p in teachers for k in range(4) for f in (False,True)]
assert all(checks);report['teacher_D4']={'passed':sum(checks),'total':len(checks)}
# Compact exact inequality controls: all signs, perfect and non-perfect roots, large integers.
coeffs=[(0,0,0),(0,0,-1),(0,3,-7),(0,-3,7),(1,-6,9),(1,-6,8),(1,-6,7),(-1,6,-9),(-1,6,-8),(-1,6,-7),(2,1,-19),(-2,-1,19),(1,0,1),(-1,0,-1),(1,-2*10**18,10**36-4),(-1,2*10**18,-10**36+4)]
total=0
for a,b,c in coeffs:
 for lo in (0,2,5):
  intervals=s.nonnegative_intervals(a,b,c,lo)
  points=set(range(lo,40))|{10**18+d for d in range(-5,6)}
  for q in points:
   if q<lo:continue
   assert any(x<=q and (y is None or q<=y) for x,y in intervals)==(a*q*q+b*q+c>=0),(a,b,c,lo,q,intervals)
   total+=1
report['inequality_point_checks']=total
# Independent containment oracle, mixed periods with LCM six and a finite linear envelope.
laws=(('periodic_difference',0,(1,-2)),('quadratic',0,1,0),('periodic_difference',20,(1,-1,0)),('quadratic',7,1,0))
win=[3,17,15,19]
indices,ub=s.containing_indices(laws,win,3)
want=[n for n in range(3,18) if all(v<=w if a<2 else v>=w for a,(v,w) in enumerate(zip([s.sequence_value(l,n) for l in laws],win)))]
assert indices==want and not ub
report['LCM6_containment']={'indices':indices,'oracle':want}
# No hidden index cap: a singleton future index far beyond an ordinary search horizon.
N=10**9
laws=(('quadratic',0,0,0),('quadratic',0,1,0),('quadratic',10,0,0),('quadratic',2,1,0))
assert s.containing_indices(laws,[2,N,8,N+2],3)==([N],False)
report['billionth_index_exact']=True
laws=(('quadratic',0,0,0),('quadratic',0,3,-2),('quadratic',10,0,0),('quadratic',1,3,-2))
assert s.containing_indices(laws,[2,3,5,4],0)==([1,3],False)
report['multiple_finite_indices_retained']=True
# Every witnessed difference period, not the shortest alone.
ls=s.sequence_laws([0,2,4,6,8,10]);assert len(ls)==5 and [len(l[2]) for l in ls[1:]]==[1,2,3,4]
assert [l[0] for l in s.sequence_laws([0,2,5])]==['quadratic']
assert s.sequence_laws([0,2,5,7,10])==[('periodic_difference',0,(2,3))]
report['all_witnessed_laws']=True
# Centered row parity, source symmetry, literal fixed-width symbols, and all eligible periods.
def role_case(even=False,constant=False):
 heights=[6,10,14] if even else [5,9,13]
 patterns=[(1,0,0),(1,1,0)]
 patch=lambda h:[[2*v for v in ((1,1,1) if constant else patterns[(abs(2*r-(h-1))-((h-1)%2))//2%2])] for r in range(h)]
 g=[[0]*15 for _ in range(max(heights))];boxes=[]
 for i,h in enumerate(heights):
  p=patch(h);c=i*5
  for r,row in enumerate(p):g[r][c:c+3]=row
  boxes.append([0,c,h-1,c+2])
 h=18 if even else 17
 role={'background':0,'marker_color':5,'body_bboxes':boxes,'marker_window':[1,1,h-2,2],'future_geometric_roles':[{'series_index_1based':4,'predicted_bbox':[0,0,h-1,2]}]}
 return g,role,[row[1:3] for row in patch(h)[1:-1]]
for even in (False,True):
 g,role,want=role_case(even)
 outs,ev=s.centered_row_models(g,role);assert outs and all(o==want for o in outs) and ev['incomplete_models']==0
 bad=copy.deepcopy(role);bad['future_geometric_roles'][0]['predicted_bbox'][2]+=1
 outs,ev=s.centered_row_models(g,bad);assert not outs and ev['incomplete_models']==ev['fitted_models']>0
 wide=copy.deepcopy(role);wide['future_geometric_roles'][0]['predicted_bbox'][3]+=1
 outs,ev=s.centered_row_models(g,wide);assert not outs and ev['incomplete_models']==ev['fitted_models']>0
 badg=copy.deepcopy(g);badg[0][0]=0
 outs,ev=s.centered_row_models(badg,role);assert not outs and ev.get('failure')=='radial_row_symbol_conflict'
g,role,want=role_case(constant=True);outs,ev=s.centered_row_models(g,role);assert ev['periods']==[1,2,3] and len(outs)==3
report['centered_controls']={'odd_even_parity':True,'width_failure_retained':True,'asymmetry_rejected':True,'all_periods':[1,2,3],'literal_distinct_rows':True}
# Real successful teacher with added retained failures must globally HOLD, no emitted partial result.
g=teachers[0]['input'];old=s.radial_predict
s.radial_predict=lambda *args,**kwargs:(None,{'source_fitted':True,'failure':'audit_unfamiliar_failure'})
o,e=s.predict(g,True);assert o is None and e['incomplete_models']>0;s.radial_predict=old
old=s.observe
for mode in ('unbounded','multiple'):
 def observed(grid):
  roles=old(grid)
  for r in roles:
   if mode=='unbounded':r['unbounded_geometry']=True
   elif r['future_geometric_roles']:r['future_geometric_roles'].append(dict(r['future_geometric_roles'][0],series_index_1based=999))
  return roles
 s.observe=observed;o,e=s.predict(g,True);assert o is None and e['incomplete_models']>0
s.observe=old
report['global_HOLD_controls']=['unfamiliar_source_fitted_failure','unbounded_with_finite_record','multiple_indices']
report['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
report['status']='PASS'

from unittest.mock import patch
from 接続.ARC2.観測成長教材 import 観測成長教材
from 接続.ARC2.観測成長 import growth_series as api
boundary=観測成長教材(teachers)
assert boundary.記録()['事前支持数']==0 and boundary.記録()['全教師再現']
assert set(vars(boundary))=={'fitted','teacher_count'}
assert boundary.fitted=={'kind':'observed_series_composition','version':4}
for p in teachers:assert boundary.候補(p['input'],{})[0]==p['output']
for model in ({'kind':'observed_series_composition','version':3},None,{}, {'kind':'other','version':3},{'kind':'observed_series_composition','version':2}):
 with patch.object(api,'fit',return_value=model):
  invalid=観測成長教材(teachers)
 with patch.object(api,'predict',side_effect=AssertionError('ungated prediction')):
  assert invalid.候補(teachers[0]['input'],{})[0] is None
  assert invalid.記録()['全教師再現'] is False
for stage in ('fit','predict'):
 for err in (RuntimeError('fault'),MemoryError('memory')):
  with patch.object(api,stage,side_effect=err):
   try:
    if stage=='fit':観測成長教材(teachers)
    else:boundary.候補(teachers[0]['input'],{})
   except type(err):pass
   else:raise AssertionError('exception swallowed')
assert api.fit([]) is None
bad=copy.deepcopy(teachers);bad[0]['output']=[[9]];assert api.fit(bad) is None
report.update(successful=True,tests_run=report['inequality_point_checks']+24+25)
print(json.dumps(report))
