#!/usr/bin/env python3
"""Portable candidate150 teacher/ordinary and conservative-cover checks."""
import json,runpy,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
from 接続.ARC2 import 領域指令核 as core
from 接続.ARC2.領域指令教材 import 領域指令教材,fit
D=ROOT/'検証/領域指令資料'
checks=[]
def check(name, value):
    assert value,name
    checks.append(name)
check('frozen_corrected_core',hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest()=='a3568dd28202b318494f843b5f882cf5a283e3e4f7c3b2e9bc3d87e73f0f4b88')
# Keep prior test body and all existing contrasts. Suppress only its console report.
import contextlib,io
with contextlib.redirect_stdout(io.StringIO()): ordinary=runpy.run_path(str(D/'ordinary_checks.py'))
checks.extend(ordinary['checks'])
teachers=json.loads((D/'teachers-only.json').read_text())
audit={};candidate=領域指令教材(teachers,audit);fitted,record=core.fit_teachers(teachers)
check('fit_api_parity',candidate.fitted==fitted and audit==record)
for i,p in enumerate(teachers):
    check('adapter_teacher_parity_'+str(i),candidate.候補(p['input'],{})==core.predict(p['input'],fitted))
check('empty_prior',candidate.記録()['事前支持数']==0)
# Concrete proofs reject dimensions outside identity/quarter-turn and novel colors.
for name, output in [('shape', [[2]]),('palette', [[8 for v in row]for row in teachers[0]['output']])]:
    import copy
    altered=copy.deepcopy(teachers);altered[0]['output']=output
    if name=='palette':
        absent=set(range(10))-set(v for row in altered[0]['input']for v in row)
        color=min(absent);altered[0]['output']=[[color for v in row]for row in teachers[0]['output']]
    ff,rr=fit(altered)
    check('proven_impossibility_'+name,ff is None and rr.get('necessity_guard',{}).get('all_models_impossible') is True)
    check('unpruned_no_fit_'+name,core.fit_teachers(altered)[0] is None)
g=json.loads((D/'synthetic-cover-regression.json').read_text())
old=core.DIRS;core.DIRS=((0,-1),(0,1),(-1,0),(1,0));cap={}
def trace(frame,event,arg):
    if frame.f_code is core.parse.__code__ and event=='return':cap['scenes_before_failure']=len(frame.f_locals.get('scenes',[]))
    return trace
sys.settrace(trace)
try: scenes,reason=core.parse(g,1,9)
finally:sys.settrace(None);core.DIRS=old
check('later_cover_failure_discards_prior_success',cap.get('scenes_before_failure')==1 and not scenes and reason=='eligible_cover_ray_out_of_bounds')
conflict=[[2]*4+[6]*3+[4]*4 for _ in range(7)]
for r,x in [(1,2),(2,3),(3,2),(3,8),(4,7),(5,8)]:conflict[r][x]=1
conflict[2][2]=7;conflict[4][8]=8
check('conflicting_assignments_hold',core.parse(conflict,1,9)==([], 'eligible_cover_assignment_conflict'))
check('conflicting_assignments_predict_hold',candidate.候補(conflict,{})[0] is None)
old=core.render
for error in (MemoryError,RuntimeError):
    def fail(*args,error=error,**kwargs):raise error('injected')
    core.render=fail
    try:
        try:candidate.候補(teachers[0]['input'],{})
        except error:check(error.__name__+'_propagates',True)
        else:raise AssertionError('swallowed exception')
    finally:core.render=old
print(json.dumps(dict(successful=True,tests_run=len(checks),checks=checks)))
