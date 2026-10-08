"""Teacher-fitted finite length exceptions over visible material, with native HDS.

Prior selection is explicitly separate from native known-key prediction and
from default continuation. Unknown native contexts never masquerade as learned.
"""
from pathlib import Path
import sys,itertools
from . import 可視材例外核 as core
SOURCE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(SOURCE/'HDS/学習系統/v0.4.2'))
from hds学習系統 import HDS学習実行系, 最小排気系
from hds学習系統.型 import 学習入力,観測事実
BOUNDARY='ARC finite visible-post-length exception context v1'
def observe(row):
 return 学習入力(原入力=dict(row),対象系境界=BOUNDARY,観測群=tuple(観測事実((k,),v,'列') for k,v in row.items()))
class Candidate:
 __slots__ = ('failure','fit_complete','observations','machine','_frozen_raw','_frozen_selected','_frozen_mapping')
 @property
 def raw_mappings(self):return [dict(m) for m in self._frozen_raw]
 @property
 def selected(self):return [dict(m) for m in self._frozen_selected]
 @property
 def mapping(self):return dict(self._frozen_mapping)
 def __init__(self,teachers):
  self.fit_complete=False;self.failure=None;self.observations=[];self._frozen_raw=();self._frozen_selected=();self._frozen_mapping=();raw_mappings=[];self.machine=HDS学習実行系()
  for ti,pair in enumerate(teachers):
   payload,rec=core.parse_input(pair['input'])
   if payload is None:self.failure='teacher_parse';return
   for p in payload['pieces'].values():
    if p['kind']=='post':self.observations.append({'teacher':ti,'post':p['id'],'original_visible_post_length':p['visible_length']})
  keys=sorted({o['original_visible_post_length'] for o in self.observations})
  # Finite resource gate: no partial fit or best-so-far publication.
  if len(keys)>8:self.failure='length_context_work_cap';return
  for bits in itertools.product((False,True),repeat=len(keys)):
   mapping=dict(zip(keys,bits))
   runs=[core.render(pair['input'],material_bits=mapping) for pair in teachers]
   incomplete=next((rec.get('failure') for _,rec in runs if rec.get('failure') in ('contact_work_incomplete','invalid_work_limit','input_interpretation_exception','contact_evaluation_exception')),None)
   if incomplete:
    self.failure='teacher_fit_incomplete:'+incomplete
    return
   if all(out==pair['output'] for (out,_),pair in zip(runs,teachers)):raw_mappings.append(mapping)
  self.fit_complete=True
  if not raw_mappings:self.failure='length_vocabulary_teacher_conflict';return
  minimum=min(sum(m.values()) for m in raw_mappings)
  selected=[m for m in raw_mappings if sum(m.values())==minimum]
  self._frozen_raw=tuple(tuple(sorted(m.items())) for m in raw_mappings)
  self._frozen_selected=tuple(tuple(sorted(m.items())) for m in selected)
  if len(selected)!=1:self.failure='minimum_exception_prior_tie';return
  self._frozen_mapping=tuple(sorted(selected[0].items()))
  # Exactly one physical observation per original post. No resampling or aliases.
  for o in self.observations:
   k=o['original_visible_post_length'];o['context_action']=(k,self.mapping[k])
   self.machine.実行(observe({name:value for name,value in o.items() if name not in ('teacher','post')}))
 def native(self,key):
  r=self.machine.照会(observe({'original_visible_post_length':key}))
  vals=[p.予測値 for p in r.予測群 if p.結果経路==('context_action',)]
  status=最小排気系().排出する(r).状態
  valid=(status=='出力' and vals and all(type(v)==tuple and len(v)==2 and type(v[0])==int and v[0]==key and type(v[1])==bool and v==vals[0] for v in vals))
  return (vals[0][1] if valid else None),{'state':status,'values':vals,'reasons':r.断定保留理由群}
 def predict(self,grid,*,default_continuation=False):
  if self.failure:return None,{'status':'HOLD','failure':self.failure,'fit_complete':self.fit_complete,'resource_incomplete':self.failure=='length_context_work_cap' or self.failure.startswith('teacher_fit_incomplete:'),'partial_fit_discarded':not self.fit_complete,'fit_context_limit':8}
  if self.machine._係争中原理群():return None,{'status':'HOLD','failure':'native_quarantine'}
  payload,rec=core.parse_input(grid)
  if payload is None:return None,{'status':'HOLD','failure':'input_parse','parse':rec}
  keys=sorted({p['visible_length'] for p in payload['pieces'].values() if p['kind']=='post'})
  mapping={};native={};unknown=[]
  for k in keys:
   bit,record=self.native(k);native[k]=record
   if bit is None:
    if k in self.mapping:return None,{'status':'HOLD','failure':'known_context_native_hold','native':native}
    if record['values'] or record['state']!='断定保留' or tuple(record['reasons'])!=('現行暫定原理の適用に必要な観測が不足している',):
     return None,{'status':'HOLD','failure':'native_hold_not_missing_context','native':native}
    unknown.append(k)
    if not default_continuation:continue
    bit=False
   mapping[k]=bit
  record={'native':native,'unknown_contexts':unknown,'native_status':'HOLD' if unknown else 'OUTPUT','explicit_default_continuation':default_continuation,'selected_mapping':self.mapping,'raw_mappings':self.raw_mappings,'physical_truth_claim':False}
  if unknown and not default_continuation:return None,{**record,'status':'HOLD','failure':'unknown_key'}
  out,render=core.render(grid,material_bits=mapping)
  raw=[core.render(grid,material_bits=m)[0] for m in self.raw_mappings]
  record.update(status='OK' if out is not None else 'HOLD',render=render,raw_output_consensus=not unknown and all(x is not None and x==raw[0] for x in raw),raw_unknown_key_hold=bool(unknown))
  return out,record
