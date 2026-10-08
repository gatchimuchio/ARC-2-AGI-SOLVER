"""Teacher-only and compact synthetic independent audit; no original tasks."""
import copy, hashlib, itertools, json, sys
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from 接続.ARC2 import 全panel端連鎖核 as c
from 接続.ARC2.全panel端連鎖教材 import 全panel端連鎖教材
SRC = ROOT/'接続/ARC2/全panel端連鎖核.py'
assert hashlib.sha256(SRC.read_bytes()).hexdigest() == '091f639523ddedc4bd11b222e7e931a1defb19e38ebd6173b5abf6b37fd1cdbb'

def roles(g):
    h,w=len(g),len(g[0]); result=[]
    for sep in set(sum(g, [])):
        rr=[r for r in range(h) if set(g[r])=={sep}]
        cc=[col for col in range(w) if {g[r][col] for r in range(h)}=={sep}]
        if not rr and not cc: continue
        if 0 in rr or h-1 in rr or 0 in cc or w-1 in cc: continue
        runs=[]
        for inds in (rr,cc):
            for _,group in itertools.groupby(enumerate(inds),lambda x:x[1]-x[0]): runs.append(len(list(group)))
        if len(set(runs))!=1: continue
        def chunks(n,excluded):
            return [list(group) for excluded_flag,group in itertools.groupby(range(n),lambda i:i in excluded) if not excluded_flag]
        rs=chunks(h,rr); cs=chunks(w,cc)
        pp=[[[g[r][col] for col in cols] for r in rows] for rows in rs for cols in cs]
        if len(pp)<2 or len({(len(p),len(p[0])) for p in pp})!=1: continue
        palettes=[set(sum(p,[])) for p in pp]
        if any(len(s)!=2 or sep in s for s in palettes): continue
        for bg in set.intersection(*palettes):
            connected=True
            for p in pp:
                cells={(r,col) for r in range(len(p)) for col in range(len(p[0])) if p[r][col]!=bg}
                seen={next(iter(cells))}; todo=list(seen)
                while todo:
                    r,col=todo.pop()
                    for nxt in ((r-1,col),(r+1,col),(r,col-1),(r,col+1)):
                        if nxt in cells and nxt not in seen: seen.add(nxt);todo.append(nxt)
                if seen!=cells: connected=False;break
            if not connected: continue
            for axis in (0,1):
                port=[]
                for p in pp:
                    q=p if axis==0 else list(map(list,zip(*p)))
                    a=frozenset(i for i,v in enumerate(q[0]) if v!=bg)
                    b=frozenset(i for i,v in enumerate(q[-1]) if v!=bg)
                    if any(row[0]!=bg or row[-1]!=bg for row in q) or not (a or b):break
                    port.append((a,b))
                else:result.append(dict(separator=sep,background=bg,gap=runs[0],axis=axis,panels=pp,ports=port,panel_shape=(len(pp[0]),len(pp[0][0]))))
    return result

def oracle(g):
    rr=roles(g); outputs=set(); counts=[]
    if not rr:return None,counts
    for role in rr:
        pp=role['panels'];ports=role['ports']; local=set();count=0
        for order in itertools.permutations(range(len(pp))):
            if ports[order[0]][0] or ports[order[-1]][1]:continue
            if any(not ports[a][1] or ports[a][1]!=ports[b][0] for a,b in zip(order,order[1:])):continue
            seq=[pp[i] if role['axis']==0 else list(map(list,zip(*pp[i]))) for i in order]
            out=[]
            for p in seq:
                if out:out += [[role['separator']]*len(p[0]) for _ in range(role['gap'])]
                out += p
            if role['axis']==1:out=list(map(list,zip(*out)))
            count+=1
            local.add(tuple(map(tuple,out)) if len(out)<=30 and len(out[0])<=30 else None)
        counts.append(count)
        if len(local)!=1 or None in local:return None,counts
        outputs|=local
    return ([list(row) for row in next(iter(outputs))] if len(outputs)==1 else None),counts

def pack(pp, gap=1):
    out=[[] for _ in pp[0]]
    for k,p in enumerate(pp):
        for r,row in enumerate(p):out[r]+=([5]*gap if k else [])+row
    return out

def panel(bits,color=1,col=1,width=3):
    return [[color if bit and j==col else 0 for j in range(width)] for bit in bits]

teachers=json.loads((SRC.parent/'teachers-only.json').read_text())
checks=0

def check(g,expected='oracle'):
    global checks
    orig=copy.deepcopy(g)
    ref,counts=oracle(g); actual,cert=c.render(g)
    assert actual==ref,(g,actual,ref)
    assert g==orig
    # Normalized role inventory independently agrees, without relying on order.
    norm=lambda rs:sorted((r['separator'],r['background'],r['gap'],r['axis'],tuple(r['ports'])) for r in rs)
    assert norm(c.views(g))==norm(roles(g))
    if actual is not None:assert sorted(x['complete_paths'] for x in cert['roles'])==sorted(counts)
    if expected!='oracle':assert actual==expected
    checks+=1

model=c.fit(teachers);assert model==c.Fit()
for t in teachers:
    check(t['input'],t['output'])
    assert c.predict(model,t['input'])[0]==t['output']
# 27 three-panel arrangements span zero, one, and multiple eligible chains.
patterns=[(0,1,1),(1,1,1),(1,1,0)]
for bits in itertools.product(patterns,repeat=3):check(pack([panel(b,i+1) for i,b in enumerate(bits)]))
# Duplicate identities, distinguishable ambiguity, exact occupancy mismatch.
s,m,e=[panel(b,i+1) for i,b in enumerate(patterns)]
for pp in ([s,m,m,e],[s,m,panel(patterns[1],4),e],
           [panel(patterns[0],1,1,5),panel(patterns[2],2,3,5)]):check(pack(pp))
# Thickness/axis and output ARC bounds (input remains <=30x30).
check(pack([e,s,m],2))
check(list(map(list,zip(*pack([e,s,m],2)))))
long=lambda bits,color:[[0,color if b else 0,0] for b in bits]
check(pack([long([0]+[1]*10,1),long([1]*11,2),long([1]*10+[0],3)]),None)
# Explicit malformed structure: transverse port, disconnected body, unequal panels.
q=pack([s,m,e]);q[0][1]=1;check(q)
q=pack([s,m,e]);q[0][0]=1;check(q)
q=pack([s,m,e]);q=[row+[0] for row in q];check(q)
for operation in (lambda:c.render(teachers[0]['input'],max_nodes=0),lambda:c.fit(teachers,max_nodes=0),lambda:c.predict(model,teachers[0]['input'],max_nodes=0)):
    try:operation()
    except c.SearchIncomplete:pass
    else:raise AssertionError('SearchIncomplete swallowed')
# Inject role collections solely to isolate conservative aggregation logic.
role=c.views(pack([s,m,e]))[0]
fail=copy.deepcopy(role);fail['ports']=[(frozenset({1}),frozenset({1}))]*3
other=copy.deepcopy(role);other['separator']=9
for rr in ([role,fail],[fail,role],[role,other],[other,role]):
    with patch.object(c,'views',return_value=rr):assert c.render([[0]])[0] is None
with patch.object(c,'views',return_value=[role,copy.deepcopy(role)]):assert c.render([[0]])[0] is not None
# Fit is exact teacher validation, not exemplar storage.
assert c.fit([]) is None
bad=copy.deepcopy(teachers);bad[0]['output'][0][0]=(bad[0]['output'][0][0]+1)%10
assert c.fit(bad) is None
assert c.predict(None,teachers[0]['input'])[0] is None
assert c.predict(c.Fit('other'),teachers[0]['input'])[0] is None
boundary=全panel端連鎖教材(teachers)
assert boundary.記録()['事前支持数']==0 and boundary.記録()['全教師再現']
for pair in teachers: assert boundary.候補(pair['input'],{})[0]==pair['output']
with patch.object(c,'fit',side_effect=c.SearchIncomplete('injected')):
    try: 全panel端連鎖教材(teachers)
    except c.SearchIncomplete: pass
    else: raise AssertionError('fit exception swallowed')
with patch.object(c,'predict',side_effect=c.SearchIncomplete('injected')):
    try: boundary.候補(teachers[0]['input'],{})
    except c.SearchIncomplete: pass
    else: raise AssertionError('query exception swallowed')
print(json.dumps({'successful':True,'tests_run':checks+len(teachers)+3+5+4+1+len(teachers)+2,'oracle_grid_cases':checks,'teacher_cases':len(teachers),'source_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest()},indent=2))
