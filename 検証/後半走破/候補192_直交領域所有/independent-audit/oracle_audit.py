import sys,importlib.util,json,itertools,time
from pathlib import Path
import numpy as np
root=Path('/workspace/scratch/7408259c1ab2')
sys.path.insert(0,str(root/'arc2-current107/source'))
spec=importlib.util.spec_from_file_location('audited_kernel',root/'proposal192-r2-outline-cleanup-20261008/source/接続/ARC2/直交領域所有核.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def padding(a):
 h,w=a.shape;p=np.zeros((h+2,w+2),dtype=int);p[1:-1,1:-1]=a
 for c in range(w):
  start=min(max(c-1,0),w-3)
  p[0,c+1]=int(sum(a[0,start:start+3])>=2);p[-1,c+1]=int(sum(a[-1,start:start+3])>=2)
 for r in range(h):
  start=min(max(r-1,0),h-3)
  p[r+1,0]=int(sum(a[start:start+3,0])>=2);p[r+1,-1]=int(sum(a[start:start+3,-1])>=2)
 for r,c,ri,ci in [(0,0,1,1),(0,w+1,1,w),(h+1,0,h,1),(h+1,w+1,h,w)]:
  p[r,c]=int(p[r,ci]+p[ri,c]+p[ri,ci]>=2)
 return p

def energies(a,states):
 p=padding(a); ps=np.repeat(p[None],len(states),axis=0);ps[:,1:-1,1:-1]=states
 # A vertex has one turn for 1/3 occupied quadrants, two for alternating quadrants.
 z=ps[:,:-1,:-1];x=ps[:,:-1,1:];y=ps[:,1:,:-1];v=ps[:,1:,1:]
 count=z+x+y+v
 turns=((count==1)|(count==3)).astype(int)+2*((z==v)&(x==y)&(z!=x))
 return (states!=a).sum(axis=(1,2))+turns.sum(axis=(1,2))

start=time.time();states=np.array(list(itertools.product([0,1],repeat=9)),dtype=int).reshape(-1,3,3)
summary={'kernel_sha256':'943acdb273c66b56f2103cb86038b523b32847594c34335f9ed781d0fe8e8a02','oracle_checks':0,'unique':0,'ties':0,'fractional_first_lp':0,'incomplete':0,'errors':[]}
for idx,a in enumerate(states):
 costs=energies(a,states); opt=int(costs.min()); inds=np.flatnonzero(costs==opt)
 lp,li=m.regularize_with_boundary(a.tolist(),relax=True)
 assert li['objective']<=opt+1e-6,(idx,'invalid lower bound',li,opt)
 summary['fractional_first_lp']+=not li['integral']
 if li['integral']:assert costs[np.flatnonzero(np.all(states==lp,axis=(1,2)))[0]]==opt
 try: out,info=m.unique_region(a.tolist())
 except m.SearchIncomplete as e: summary['incomplete']+=1;summary['errors'].append([idx,'incomplete',str(e)]);continue
 if len(inds)==1:
  summary['unique']+=1
  if out!=states[inds[0]].tolist():summary['errors'].append([idx,'wrong unique',out,states[inds[0]].tolist()])
 else:
  summary['ties']+=1
  if out is not None:summary['errors'].append([idx,'false unique',out,len(inds)])
 summary['oracle_checks']+=1
summary['oracle_seconds']=time.time()-start
print(json.dumps(summary),flush=True)
(root/'proposal192-r2-outline-cleanup-20261008/independent-audit/oracle-results.json').write_text(json.dumps(summary,indent=2))
teachers=json.loads((root/'arc2-current99/teachers-only/71e489b6.json').read_text())['train']
start=time.time();model=m.直交領域所有教材(teachers)
results={'models':model.models,'record':model.記録(),'teacher_matches':[]}
for p in teachers:
 out,info=model.候補(p['input']);results['teacher_matches'].append(out==p['output'])
results['seconds']=time.time()-start
print(json.dumps(results),flush=True)
(root/'proposal192-r2-outline-cleanup-20261008/independent-audit/teacher-results.json').write_text(json.dumps(results,indent=2))
