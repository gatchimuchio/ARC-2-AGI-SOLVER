"""NEW034 adapter reconstruction; original packaged034 bytes are unavailable.

Teacher fitter is unchanged strict032. Only query parsing selects whole mask.
Every retained strict032 alternative remains mandatory for whole-output consensus.
"""
from . import 周期模様窓教材 as strict
from .周期模様窓基底教材 import *
from .全体模様窓視点 import parse_whole

fit = strict.fit

def render(grid,spec):
    if not valid_grid(grid):return {'status':'failure','reason':'invalid_arc_grid','output':None}
    if not valid_spec(spec):return {'status':'failure','reason':'invalid_model_spec','output':None}
    role,reason=parse_whole(grid)
    return apply(role,reason,spec)

def predict(grid,models,observer=None):
    trace={'program_returns':[],'output':None};index=None;parsed=[];pending=None;result=None
    if not valid_grid(grid):return None,dict(trace,failure='invalid_arc_grid')
    if not valid_models(models):return None,dict(trace,failure='invalid_model_group')
    try:
        role,reason=parse_whole(grid);parsed=[{'role':role,'reason':reason}]
        for index,model in enumerate(models):
            pending=None;result=None;result=apply(role,reason,model[1:])
            pending={'model_index':model[0],'return':result,'row_committed':False,'action_executed':role is not None}
            trace['program_returns'].append({'model_index':model[0],'return':result});pending['row_committed']=True
            emit(observer,{'kind':'retained_model_return',**trace['program_returns'][-1]})
        pending=None;result=None
        if not models:trace['failure']='no_teacher_fit_model'
        elif any(r['return']['status']!='success' or not valid_grid(r['return']['output']) for r in trace['program_returns']):trace['failure']='retained_model_failed'
        elif any(r['return']['output']!=trace['program_returns'][0]['return']['output'] for r in trace['program_returns']):trace['failure']='retained_model_outputs_disagree'
        else:trace['output']=trace['program_returns'][0]['return']['output']
        emit(observer,{'kind':'retained_consensus','record':trace})
        return trace['output'],trace
    except BaseException as error:
        try:
            attach_exception(error,{'stage':'predict','exception':type(error).__name__,'message':str(error),'retained_index':index,
                'parsed_inputs':parsed,'program_returns':trace['program_returns'],'completed_returns':len(trace['program_returns']),'pending_return':pending,'raw_pending_return':result,'planned_returns':len(models),'semantic_HOLD':False},observer)
        except BaseException:pass
        raise


@dataclass(frozen=True,init=False,slots=True)
class 全体模様窓教材:
    モデル群:tuple
    教師数:int
    不足理由:str|None
    def __init__(self,教師群,監査=None,観測=None):
        models,record=fit(教師群,観測)
        object.__setattr__(self,'モデル群',models);object.__setattr__(self,'教師数',record['teacher_count']);object.__setattr__(self,'不足理由',record.get('failure'))
        if 監査 is not None:監査.update(record)
    def 候補(self,格子,_policy,観測=None):return predict(格子,self.モデル群,観測)
    def 展開モデル(self):return [{'model_index':m[0],'spec':dict(zip(FIELDS,m[1:]))} for m in self.モデル群]
    def 記録(self):return {'保持候補数':len(self.モデル群),'保持候補':self.展開モデル(),'教師数':self.教師数,'教師fit最小数':2,'不足理由':self.不足理由,'固定prior':'NEW reconstructed034: strict032 finite alternatives; complete foreground whole-mask query view'}
