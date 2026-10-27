"""Pure binary region regularization experiment; explicit additional corner prior.
No task identity, filesystem, HDS or scoring dependency.
"""
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import coo_matrix
from 接続.ARC2.既存穴輪郭 import EIGHT_DELTAS

def regularize(grid,weight=1,time_limit=30,exclude=None,fixed_border=False,relax=False):
 a=np.array(grid,dtype=int);h,w=a.shape;N=h*w; blocks=(h-1)*(w-1);nv=N+16*blocks
 cost=np.zeros(nv); cost[:N]=1-2*a.ravel()
 rr=[];cc=[];vv=[];lo=[];hi=[]
 def eq(items,value):
  i=len(lo);lo.append(value);hi.append(value)
  for j,v in items:rr.append(i);cc.append(j);vv.append(v)
 for r in range(h-1):
  for c in range(w-1):
   start=N+16*(r*(w-1)+c)
   eq([(start+k,1) for k in range(16)],1)
   for j,p in enumerate((r*w+c,r*w+c+1,(r+1)*w+c,(r+1)*w+c+1)):
    eq([(p,1)]+[(start+k,-1) for k in range(16) if (k>>j)&1],0)
   for k in range(16):
    count=k.bit_count();cost[start+k]=weight*(1 if count in (1,3) else 2 if k in (6,9) else 0)
 if exclude is not None:
  old=np.array(exclude).ravel();i=len(lo);lo.append(1-int(old.sum()));hi.append(np.inf)
  for p,v in enumerate(old):rr.append(i);cc.append(p);vv.append(1-2*v)
 mat=coo_matrix((vv,(rr,cc)),shape=(len(lo),nv)).tocsc()
 lower=np.zeros(nv);upper=np.ones(nv)
 if fixed_border:
  for r in range(h):
   for c in range(w):
    if r in (0,h-1) or c in (0,w-1):lower[r*w+c]=upper[r*w+c]=a[r,c]
 # HiGHS official threads option is forwarded by SciPy 1.17; preserve its warning.
 # Single worker limits address-space reservation; objective/certification unchanged.
 res=milp(cost,integrality=np.zeros(nv) if relax else np.r_[np.ones(N),np.zeros(nv-N)],bounds=Bounds(lower,upper),constraints=LinearConstraint(mat,lo,hi),options={'time_limit':time_limit,'mip_rel_gap':0,'threads':1})
 if res.status!=0:return None,{'status':int(res.status),'message':res.message}
 if res.x is None or not np.all(np.isfinite(res.x)) or not np.isfinite(res.fun):
  return None,{'status':'invalid_numeric_result'}
 residual=max(float(np.max(np.maximum(np.array(lo)-mat@res.x,0))),float(np.max(np.maximum(mat@res.x-np.array(hi),0))),float(np.max(np.maximum(lower-res.x,0))),float(np.max(np.maximum(res.x-upper,0))))
 gap=getattr(res,'mip_gap',None)
 dual=getattr(res,'mip_dual_bound',None)
 if not relax and (gap is None or dual is None or not np.isfinite(dual) or abs(float(res.fun)-float(dual))>1e-6):
  return None,{'status':'uncertified_milp_bound','gap':gap,'dual_bound':dual}
 if residual>1e-7 or (gap is not None and (not np.isfinite(gap) or gap>1e-9)):
  return None,{'status':'uncertified_numeric_result','residual':residual,'gap':gap}
 out=np.rint(res.x[:N]).astype(int).reshape(h,w).tolist()
 integral=bool(np.all(np.abs(res.x[:N]-np.rint(res.x[:N]))<1e-7))
 if not relax and not integral:
  return None,{'status':'nonintegral_milp_result'}
 if integral:
  exact=float(np.sum(a!=np.array(out)))
  for r in range(h-1):
   for c in range(w-1):
    k=out[r][c]+2*out[r][c+1]+4*out[r+1][c]+8*out[r+1][c+1]
    exact+=weight*(1 if k.bit_count() in (1,3) else 2 if k in (6,9) else 0)
  if abs(exact-float(res.fun+a.sum()))>1e-6:
   return None,{'status':'rounded_objective_mismatch'}
 return out,{'status':0,'objective':float(res.fun+a.sum()),'changed':int(np.sum(a!=np.array(out))),'integral':bool(np.all(np.abs(res.x[:N]-np.rint(res.x[:N]))<1e-7)),'residual':residual,'mip_gap':gap,'numeric_tolerance':1e-7,'relaxation':relax}

def render(grid,clean,background=0,field=1,outline=7):
 h,w=len(grid),len(grid[0]);target={(r,c) for r in range(h) for c in range(w) if grid[r][c]==background and clean[r][c]==field}
 erase={(r,c) for r in range(h) for c in range(w) if grid[r][c]==field and clean[r][c]==background}
 out=[row[:] for row in grid];border=set()
 for r,c in erase:out[r][c]=background
 for r,c in target:
  for dr,dc in EIGHT_DELTAS:
   rr,cc=r+dr,c+dc
   if 0<=rr<h and 0<=cc<w and (rr,cc) not in target:border.add((rr,cc))
 for r,c in border:out[r][c]=outline
 return out,{'target':sorted(target),'erase':sorted(erase),'collision':sorted(erase&border)}


def regularize_with_boundary(grid,weight=1,exclude=None,relax=False):
 a=np.array(grid,dtype=int);h,w=a.shape
 if min(h,w)<3:return None,{'failure':'insufficient_boundary_support'}
 padded=np.pad(a,1,mode='edge')
 def smooth(line):
  n=len(line)
  return np.array([sum(line[max(0,min(i-1,n-3)):max(0,min(i-1,n-3))+3])>=2 for i in range(n)],dtype=int)
 padded[0,1:-1]=smooth(a[0]);padded[-1,1:-1]=smooth(a[-1])
 padded[1:-1,0]=smooth(a[:,0]);padded[1:-1,-1]=smooth(a[:,-1])
 for r,c,r1,c1 in ((0,0,1,1),(0,-1,1,-2),(-1,0,-2,1),(-1,-1,-2,-2)):
  vals=[padded[r,c1],padded[r1,c],padded[r1,c1]];padded[r,c]=sum(vals)>=2
 excluded=None
 if exclude is not None:
  excluded=padded.copy();excluded[1:-1,1:-1]=exclude;excluded=excluded.tolist()
 clean,info=regularize(padded.tolist(),weight=weight,fixed_border=True,exclude=excluded,relax=relax)
 return (np.array(clean)[1:-1,1:-1].tolist() if clean else None),info

class SearchIncomplete(RuntimeError):
    pass


def valid_grid(grid):
    return (isinstance(grid,list) and 3 <= len(grid) <= 30 and
            isinstance(grid[0],list) and 3 <= len(grid[0]) <= 30 and
            all(isinstance(row,list) and len(row)==len(grid[0]) and
                all(type(v) is int and 0 <= v <= 9 for v in row) for row in grid))


def unique_region(grid):
    clean, first = regularize_with_boundary(grid,relax=True)
    if clean is not None and not first["integral"]:
        clean, first=regularize_with_boundary(grid)
    if clean is None or not first.get('integral',False):
        raise SearchIncomplete(str(first))
    second, other = regularize_with_boundary(grid, exclude=clean,relax=True)
    if second is not None and other["objective"] <= first["objective"]+1e-6:
        second,other=regularize_with_boundary(grid,exclude=clean)
        if second is not None and not other.get('integral',False):
            raise SearchIncomplete(str(other))
    if second is None:
        raise SearchIncomplete(str(other))
    if other['objective'] <= first['objective'] + 1e-6:
        return None, {'failure':'multiple_minimum_region_ownerships','first':first,'other':other}
    return clean, {'first':first,'other':other}


def apply_roles(grid, roles):
    if not valid_grid(grid) or len(roles)!=3 or len(set(roles))!=3:
        return None, {'failure':'invalid_grid_or_roles'}
    background, field, outline = roles
    if {v for row in grid for v in row} != {background,field}:
        return None, {'failure':'unexpected_input_palette'}
    binary = [[int(v==field) for v in row] for row in grid]
    clean, proof = unique_region(binary)
    if clean is None:
        return None, proof
    result, ownership = render(binary,clean)
    if ownership['collision']:
        return None, {'failure':'erase_outline_ownership_collision', 'ownership':ownership}
    if not ownership['target'] or not ownership['erase']:
        return None, {'failure':'both_defect_roles_required'}
    palette={0:background,1:field,7:outline}
    return [[palette[v] for v in row] for row in result], {'proof':proof,'ownership':ownership}


class 直交領域所有教材:
    """追加prior: 単位編集費＋単位直交曲がり費、沿辺三セル多数外挿。"""
    def __init__(self, teachers):
        self.models=[]
        if not teachers or any(not valid_grid(p.get('input')) or not valid_grid(p.get('output')) or
                len(p['input'])!=len(p['output']) or len(p['input'][0])!=len(p['output'][0]) for p in teachers):
            return
        colors=sorted({v for p in teachers for row in p['input'] for v in row})
        novel=sorted({v for p in teachers for row in p['output'] for v in row}-set(colors))
        if len(colors)!=2 or len(novel)!=1:
            return
        # Geometry is color-complement invariant, so solve once per teacher.
        regions=[]
        for p in teachers:
            b=[[int(v==colors[1]) for v in row] for row in p['input']]
            clean, proof=unique_region(b)
            if clean is None:return
            regions.append((b,clean))
        for reverse in (False,True):
            roles=(*((colors[1],colors[0]) if reverse else colors),novel[0])
            passed=True
            for p,(b,clean) in zip(teachers,regions):
                if reverse:
                    b=[[1-v for v in row] for row in b];clean=[[1-v for v in row] for row in clean]
                out,own=render(b,clean)
                palette={0:roles[0],1:roles[1],7:roles[2]}
                out=[[palette[v] for v in row] for row in out]
                if own['collision'] or not own['target'] or not own['erase'] or out!=p['output']:
                    passed=False;break
            if passed:self.models.append(roles)

    def 候補(self, grid, _policy=None):
        if not self.models:return None,{'failure':'no_teacher_fit'}
        results=[apply_roles(grid,roles) for roles in self.models]
        if any(out is None for out,info in results):return None,{'failure':'retained_model_failure','records':[info for out,info in results]}
        if any(out!=results[0][0] for out,info in results):return None,{'failure':'retained_model_disagreement'}
        return results[0][0],{'models':self.models,'records':[info for out,info in results]}

    def 記録(self):
        return {'models':self.models,'prior':'unit_edit_plus_orthogonal_turns_with_edge_majority3','version':1}
