"""Declared finite-exception/default-continuation prior, not a physical law.

The prior preserves proposal190's admit-all default except at complete observed
scene-cardinality signatures refuted by teacher corner-port observations. Native
HDS learns actions on the derived membership Boolean, never an unseen raw key.
"""
import types
from . import 結合光線核 as legacy
from .標識経路層教材 import valid_teachers
from .二軸補完教材 import valid_grid
from hds学習系統 import HDS学習実行系, 最小排気系
from hds学習系統.型 import 学習入力, 観測事実

def corner(v): return all(v)
def render_admitted(grid,admissions):
 parsed=legacy.roles(grid)
 if len(parsed)!=1:return None,{'failure':'roles'}
 bg,wall,cores=parsed[0];i=iter(admissions)
 filtered=[(color,box,[(p,v) for p,v in holes if not corner(v) or next(i)]) for color,box,holes in cores]
 scope=dict(legacy.render.__globals__);scope['roles']=lambda g:[(bg,wall,filtered)]
 renderer=types.FunctionType(legacy.render.__code__,scope,legacy.render.__name__,legacy.render.__defaults__)
 return renderer(grid)
BOUNDARY='ARC finite-exception corner-port continuation v1'
PRIOR='Preserve the existing admit-all default except for complete observed scene-cardinality signatures with negative teacher corner-port labels; reject inconsistent labels; carry this finite exception set to all input contexts.'
FEATURE='matches_learned_failure_context_set'
def observe(row):
 return 学習入力(原入力=dict(row),対象系境界=BOUNDARY,観測群=tuple(観測事実((k,),v,'列') for k,v in row.items()))
class 有限例外光線教材:
 def __init__(self,teachers):
  self.machine=HDS学習実行系();self.observations=[];self.failure=None;self.teacher_exact=[];self.blocked_contexts=frozenset()
  if not valid_teachers(teachers):self.failure='invalid_teachers';return
  labels_by_context={}
  for ti,pair in enumerate(teachers):
   rr=legacy.roles(pair['input'])
   if len(rr)!=1:self.failure='teacher_roles';return
   bg,wall,cores=rr[0];labels=[];context=len(cores)
   for color,box,holes in cores:
    for p,v in holes:
     if corner(v):
      value=pair['output'][p[0]][p[1]]
      if value not in (color,bg):self.failure='ambiguous_teacher_port_label';return
      admitted=value==color;labels.append(admitted)
      labels_by_context.setdefault(context,set()).add(admitted)
      self.observations.append({'teacher':ti,'scene_emitter_cardinality':context,'admit':admitted})
   if render_admitted(pair['input'],labels)[0]!=pair['output']:
    self.failure='teacher_full_grid_reconstruction_failed';return
  if any(len(values)!=1 for values in labels_by_context.values()):
   self.failure='contradictory_complete_observed_context';return
  self.blocked_contexts=frozenset(r['scene_emitter_cardinality'] for r in self.observations if not r['admit'])
  # Prior-derived feature; exactly one submission per real observed port.
  for row in self.observations:
   blocked=row['scene_emitter_cardinality'] in self.blocked_contexts
   self.machine.実行(observe({FEATURE:blocked,'context_action':(blocked,row['admit'])}))
  for pair in teachers:
   out,record=self.predict(pair['input']);self.teacher_exact.append(out==pair['output'])
  if not all(self.teacher_exact):self.failure='native_hds_not_teacher_complete'
 def predict(self,grid):
  if not valid_grid(grid):return None,{'status':'HOLD','failure':'invalid_grid'}
  if self.failure:return None,{'status':'HOLD','failure':self.failure}
  rr=legacy.roles(grid)
  if len(rr)!=1:return None,{'status':'HOLD','failure':'roles'}
  cores=rr[0][2];context=len(cores);blocked=context in self.blocked_contexts
  admissions=[];records=[]
  for color,box,holes in cores:
   for p,v in holes:
    if not corner(v):continue
    result=self.machine.照会(observe({FEATURE:blocked}))
    values=[p.予測値 for p in result.予測群 if p.結果経路==('context_action',)]
    status=最小排気系().排出する(result).状態
    records.append({'state':status,'values':values,'hold_reasons':result.断定保留理由群})
    if status!='出力' or not values or any(type(x)!=tuple or len(x)!=2 or type(x[0])!=bool or x[0]!=blocked or type(x[1])!=bool or x!=values[0] for x in values):
     return None,{'status':'HOLD','failure':'unknown_or_conflicting_native_admission','raw_context':context,'derived_context':blocked,'native':records}
    admissions.append(values[0][1])
  out,detail=render_admitted(grid,admissions)
  return out,{'status':'OK' if out is not None else 'HOLD','raw_context':context,'derived_context':blocked,'blocked_contexts':sorted(self.blocked_contexts),'admissions':admissions,'native':records,'renderer':detail}

 def 学習する(self,machine,_observation=None):
  """Bind physical observations to the same unchanged native admission HDS."""
  if self.failure:return
  if machine.最小支持数 < self.machine.最小支持数:
   self.failure='native_support_below_object_default';return
  for row in self.observations:
   blocked=row['scene_emitter_cardinality'] in self.blocked_contexts
   machine.実行(observe({FEATURE:blocked,'context_action':(blocked,row['admit'])}))
  self.machine=machine
 def 候補(self,grid,_policy=None):return self.predict(grid)
 def 記録(self):
  return {'事前支持数':0,'保持候補数':0 if self.failure else 1,'failure':self.failure,'physical_observations':len(self.observations),'blocked_contexts':sorted(self.blocked_contexts),'teacher_exact':self.teacher_exact,'prior':PRIOR,'risk':'HIGH OVERFIT RISK; not physically established or teacher-unique'}
