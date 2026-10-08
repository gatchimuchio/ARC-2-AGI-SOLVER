import ast,copy,hashlib,importlib.util,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
source=ROOT/'接続/ARC2/観測成長/growth_series.py';base=ROOT/'検証/後半走破/候補164_観測成長/history/candidate164/growth_series.py.txt'
sha=hashlib.sha256(source.read_bytes()).hexdigest();assert sha=='6b2139090fb1d2f94412bc8b330f33ed4868a03c1736f3a6f8ab3448ee99faaa'
spec=importlib.util.spec_from_file_location('audit166',source);s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
a={n.name:n for n in ast.parse(base.read_text()).body if isinstance(n,ast.FunctionDef)};b={n.name:n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef)}
unchanged=[k for k in a if ast.dump(a[k])==ast.dump(b[k])];assert set(a)-set(unchanged)=={'predict','fit'}
report={'source_sha256':sha,'unchanged_functions':unchanged,'fit_metadata_exception':'version 3 to 4'}
# Direct geometric role construction, independent of model fitting and source inspection.
def case(width=3,height=2,stride=3,parity=0,target=7,origin=1,diagonal=False):
 cycle=(2,6,9)
 def patch(n):
  count=6*(n+1) if diagonal else n+1;w=count if diagonal else width*count
  rad=count if diagonal else origin+stride*(count-1)+height
  h=2*rad-1+parity;out=[[0]*w for _ in range(h)]
  for r in range(h):
   radius=(abs(2*r-h+1)-parity)//2
   for c in range(w):
    if diagonal:
     if radius==c:out[r][c]=2
    else:
     j,cc=divmod(c,width);rr=radius-origin-stride*j
     if 0<=rr<height and (cc==0 or rr==height-1):out[r][c]=cycle[(n if j==0 else n-j+cc)%3]
  return out
 ps=[patch(n) for n in range(5)];g=[[0]*(sum(len(p[0])+2 for p in ps)) for _ in range(max(map(len,ps)))];boxes=[];x=0
 for p in ps:
  for r,row in enumerate(p):g[r][x:x+len(row)]=row
  boxes.append([0,x,len(p)-1,x+len(p[0])-1]);x+=len(p[0])+2
 expected=patch(target);h,w=len(expected),len(expected[0]);role={'background':0,'body_bboxes':boxes,'marker_window':[1,1,h-2,w-2],'future_geometric_roles':[{'series_index_1based':target+1,'predicted_bbox':[0,0,h-1,w-1]}]}
 return g,role,[row[1:-1] for row in expected[1:-1]]
checks=0
for parity in (0,1):
 for width,height,stride in ((2,3,2),(3,2,3)):
  for target in (5,8):
   g,role,want=case(width,height,stride,parity,target)
   out,ev=s.folded_strip_models(g,role);assert out and all(o==want for o in out) and ev['incomplete_models']==0,(width,height,stride,parity,target,ev)
   checks+=1
   trans=lambda p:[list(row) for row in zip(*p)]
   rt=copy.deepcopy(role)
   for key in ('body_bboxes',):rt[key]=[[b,a,d,c] for a,b,c,d in role[key]]
   a,b,c,d=role['marker_window'];rt['marker_window']=[b,a,d,c]
   a,b,c,d=role['future_geometric_roles'][0]['predicted_bbox'];rt['future_geometric_roles'][0]['predicted_bbox']=[b,a,d,c]
   out,ev=s.folded_strip_models(trans(g),rt,True);assert out and all(o==trans(want) for o in out);checks+=1
report['independent_strip_cropped_transpose_cases']=checks
# Multiple valid widths must all survive (no minimum-width selector).
g,role,want=case(diagonal=True);out,ev=s.folded_strip_models(g,role)
assert [m['strip_width'] for m in ev['models']]==[1,2,3,6] and len(out)==4 and all(o==want for o in out)
report['all_fitting_widths']=[m['strip_width'] for m in ev['models']]
# Alter only future dimensions: retained failures cannot disappear.
g,role,want=case();failures={}
for label,axis,amount in [('parity',2,1),('width',3,1),('radial_extent',2,2)]:
 bad=copy.deepcopy(role);bad['future_geometric_roles'][0]['predicted_bbox'][axis]+=amount
 out,ev=s.folded_strip_models(g,bad);assert not out and ev['incomplete_models']==ev['fitted_models']>0;failures[label]=True
report['retained_future_failures']=failures
# Reflection, seed color/mask, and outer phase contradictions reject source fit.
corruptions=[]
for which in ('reflection','seed','outer'):
 bad=copy.deepcopy(g);box=role['body_bboxes'][2];a,b,c,d=box
 if which=='reflection':bad[a][b]=7
 else:
  col=b if which=='seed' else b+3
  rows=[r for r in range(a,c+1) if bad[r][col]!=0];r=rows[0];bad[r][col]=7;bad[c-r][col]=7
 out,ev=s.folded_strip_models(bad,role);assert not out and ev.get('fitted_models',0)==0,(which,ev);corruptions.append(which)
report['source_corruptions_rejected']=corruptions
teachers=json.loads((ROOT/'検証/観測成長資料/teachers-only.json').read_text());assert len(teachers)==3
assert all(s.predict(s.transform(p['input'],k,f))==s.transform(p['output'],k,f) for p in teachers for k in range(4) for f in (False,True))
report['teacher_D4']='24/24'
# Any strip failure or disagreement holds even while old families succeed.
old=s.folded_strip_models
s.folded_strip_models=lambda *args,**kwargs:([],{'fitted_models':1,'incomplete_models':1})
out,ev=s.predict(teachers[0]['input'],True);assert out is None and ev['incomplete_models']>0 and ev['fitted_predictions']>0
s.folded_strip_models=lambda *args,**kwargs:([[[9]]],{'fitted_models':1,'incomplete_models':0})
out,ev=s.predict(teachers[0]['input'],True);assert out is None and ev['distinct_predictions']>1
s.folded_strip_models=old
report['aggregate_failure_and_disagreement_hold']=True
assert hashlib.sha256(source.read_bytes()).hexdigest()==sha
report.update(status='PASS',successful=True,tests_run=checks+1+len(failures)+len(corruptions)+24+2);print(json.dumps(report))
