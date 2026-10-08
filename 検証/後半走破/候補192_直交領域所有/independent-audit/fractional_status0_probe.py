exec(open('/workspace/scratch/7408259c1ab2/proposal192-r2-outline-cleanup-20261008/independent-audit/oracle_audit.py').read().split('start=time.time();states=')[0])
from types import SimpleNamespace
real=m.milp
calls=[]
def fake_solver(cost,**kw):
 # Feasible convex combination: all-zero 5x5 grid and center-one grid.
 # Both use the fixed all-zero border. Only the no-good solve remains real.
 if len(cost)==25+16*16 and len(kw['constraints'].lb)==80:
  x=np.zeros(len(cost));x[12]=0.25
  for r in range(4):
   for c in range(4):
    start=25+16*(4*r+c);positions=[5*r+c,5*r+c+1,5*(r+1)+c,5*(r+1)+c+1]
    if 12 in positions:x[start]=0.75;x[start+(1<<positions.index(12))]=0.25
    else:x[start]=1
  calls.append({'relax':bool(np.all(kw['integrality']==0)),'fractional_mock':True})
  return SimpleNamespace(status=0,x=x,fun=float(cost@x),mip_gap=0,mip_dual_bound=float(cost@x),message='mock status0 fractional feasible')
 calls.append({'real_exclusion':True})
 return real(cost,**kw)
m.milp=fake_solver
try:
 out,info=m.unique_region([[0]*3 for _ in range(3)])
 result={'accepted':out is not None,'out':out,'info':info,'calls':calls}
except m.SearchIncomplete as error:
 result={'accepted':False,'exception':'SearchIncomplete','message':str(error),'calls':calls}
assert result.get('exception')=='SearchIncomplete' and 'nonintegral_milp_result' in result['message'],result
print(json.dumps(result,indent=2))
(root/'proposal192-r2-outline-cleanup-20261008/independent-audit/fractional-probe-results.json').write_text(json.dumps(result,indent=2))
