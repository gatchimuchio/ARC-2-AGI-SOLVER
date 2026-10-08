"""Strict crop-shaped teachers; explicit finite-exception prior, empty family prior."""
from copy import deepcopy
from .周期枠位相 import Candidate, observe
from .二軸補完教材 import valid_grid
PRIOR='Default continuous phase outside the complete teacher-observed nonzero-residual parity-context set; native correction within it. Unknown raw keys remain HOLD. This finite-exception prior is not a native prediction or physical law.'
def valid_teachers(teachers):
 if type(teachers) is not list or len(teachers)<2:return False
 seen=set()
 for pair in teachers:
  if type(pair) is not dict or not valid_grid(pair.get('input')) or not valid_grid(pair.get('output')):return False
  key=tuple(map(tuple,pair['input']))
  if key in seen:return False
  seen.add(key)
 return True
class 周期枠位相教材(Candidate):
 def __init__(self,teachers):
  if not valid_teachers(teachers):
   super().__init__([]);self.failure='invalid_teachers'
  else:super().__init__(teachers)
 def predict(self,grid,policy='prior'):
  if not valid_grid(grid):return None,{'status':'HOLD','failure':'invalid_grid'}
  return super().predict(grid,policy)
 def 学習する(self,machine,_observation=None):
  if self.failure:return
  if machine.最小支持数<self.machine.最小支持数:self.failure='native_support_below_default';return
  for row in self.observations:
   machine.実行(observe({k:v for k,v in row.items() if k!='identity'}))
  self.machine=machine
 def 候補(self,grid,_policy=None):return self.predict(grid,'prior')
 def 記録(self):
  return {'事前支持数':0,'保持候補数':0 if self.failure else 1,'failure':self.failure,'physical_observations':len(self.observations),'failure_contexts':sorted(getattr(self,'failure_contexts',set())),'teacher_exact':deepcopy(getattr(self,'teacher_exact',{})),'prior':PRIOR,'raw_unknown_context_policy':'HOLD','risk':'HIGH OVERFIT RISK; corrected context appears in one teacher frame'}
