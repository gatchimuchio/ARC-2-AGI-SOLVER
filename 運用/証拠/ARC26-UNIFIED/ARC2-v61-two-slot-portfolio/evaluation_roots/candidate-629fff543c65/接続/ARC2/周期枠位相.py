"""Bounded period-relative geometry phase repair; teachers only fit.
Features fixed: (row span % palette period, column span % palette period).
Raw policy: unknown key HOLD. Prior policy: default continuous phase outside
complete learned residual-nonzero context set. This is finite-exception induction.
"""
from . import 周期枠基底 as legacy
from hds学習系統 import HDS学習実行系, 最小排気系
from hds学習系統.型 import 学習入力, 観測事実
BOUNDARY='Period-relative rectangular frame hidden phase v1'
def observe(row):
 return 学習入力(原入力=dict(row),対象系境界=BOUNDARY,観測群=tuple(観測事実((k,),v,'列') for k,v in row.items()))
def context(frame):
 b=frame['box'];p=len(frame['palette']);return ((b[2]-b[0])%p,(b[3]-b[1])%p)
def native(machine,key):
 result=machine.照会(observe({'period_relative_spans':key}));state=最小排気系().排出する(result).状態
 values=[p.予測値 for p in result.予測群 if p.結果経路==('context_action',)]
 record={'state':state,'values':values,'reasons':result.断定保留理由群}
 if state!='出力' or not values or any(type(v)!=tuple or len(v)!=2 or v[0]!=key or type(v[1])!=int or v!=values[0] for v in values):return None,record
 return values[0][1],record
class Candidate:
 def __init__(self,teachers):
  self.machine=HDS学習実行系();self.observations=[];self.interpretations=[];self.failure=None;self.labels={};physical={}
  for ti,pair in enumerate(teachers):
   roles=list(legacy.roles(pair['input']))
   if not roles:self.failure='teacher_roles';return
   for ri,role in enumerate(roles):
    inner=role['inner'];out=pair['output']
    if len(out)!=inner[2]-inner[0]+1 or any(len(row)!=inner[3]-inner[1]+1 for row in out):self.failure='teacher_output_shape';return
    for fi,frame in enumerate(role['frames']):
     key=context(frame);pal=frame['palette'];p=len(pal)
     for r,c in sorted(legacy.perimeter_cells(frame['box'])&legacy.box_cells(inner)):
      value=out[r-inner[0]][c-inner[1]];base=frame['phase'][(r+c)%p]
      residual=(pal.index(value)-pal.index(base))%p if value in pal else None
      row={'teacher':ti,'cell':(r,c),'role':ri,'frame':fi,'context':key,'residual':residual};self.interpretations.append(row)
      physical.setdefault((ti,r,c),set()).add((key,residual))
      self.labels.setdefault(key,set()).add(residual)
  if any(len(v)!=1 or next(iter(v))[1] is None for v in physical.values()):self.failure='ambiguous_physical_ownership';return
  if any(len(v)!=1 or None in v for v in self.labels.values()):self.failure='context_phase_conflict';return
  for identity,values in sorted(physical.items()):
   key,residual=next(iter(values));row={'period_relative_spans':key,'context_action':(key,residual)}
   self.observations.append({'identity':identity,**row});self.machine.実行(observe(row))
  self.failure_contexts={k for k,v in self.labels.items() if next(iter(v))!=0}
  self.native_checks={k:native(self.machine,k) for k in self.labels}
  if any(value!=next(iter(self.labels[key])) for key,(value,record) in self.native_checks.items()):self.failure='native_relation_not_admitted';return
  self.teacher_exact={policy:[self.predict(pair['input'],policy)[0]==pair['output'] for pair in teachers] for policy in ('raw','prior')}
  if not all(all(v) for v in self.teacher_exact.values()):self.failure='teacher_full_grid_reconstruction_failed'
 def predict(self,grid,policy='prior'):
  if self.failure:return None,{'status':'HOLD','failure':self.failure}
  if self.machine._係争中原理群():return None,{'status':'HOLD','failure':'native_quarantine'}
  outputs=[];records=[]
  for role in legacy.roles(grid):
   repaired=dict(role);repaired['frames']=[]
   for frame in role['frames']:
    key=context(frame);action,record=native(self.machine,key)
    if policy=='prior' and key not in self.failure_contexts:
     if key in self.labels and action is None:return None,{'status':'HOLD','failure':'known_key_lost_native_support'}
     action=0
    records.append({'context':key,'action':action,'native':record})
    if action is None:return None,{'status':'HOLD','failure':'unknown_or_conflicting_context','records':records}
    p=len(frame['palette'])
    if not 0<=action<p:return None,{'status':'HOLD','failure':'action_outside_period'}
    updated=dict(frame);updated['phase']={k:frame['palette'][(frame['palette'].index(v)+action)%p] for k,v in frame['phase'].items()}
    repaired['frames'].append(updated)
   out,detail=legacy.render_role(grid,repaired,'continuous')
   if out is None:return None,{'status':'HOLD','failure':'renderer_conflict','detail':detail}
   outputs.append(out)
  if not outputs or any(o!=outputs[0] for o in outputs):return None,{'status':'HOLD','failure':'all_role_consensus'}
  return outputs[0],{'status':'OK','policy':policy,'records':records}
