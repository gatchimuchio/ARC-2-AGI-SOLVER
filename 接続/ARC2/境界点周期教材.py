"""Strict immutable adapter for the complete frozen eight-model point-period grammar."""
from copy import deepcopy
from dataclasses import dataclass
from . import 境界点周期候補 as core

valid_grid = core.valid_grid

def emit(observer, kind, **values):
    if observer is not None:
        observer(deepcopy({'kind':kind, **values}))

def validate_teachers(teachers):
    record={'teacher_count':0, 'teacher_fit_minimum':2, 'declared_models':len(core.PROGRAMS)}
    if type(teachers) not in (list, tuple):
        return False, dict(record, failure='invalid_teacher_container')
    record['teacher_count']=len(teachers)
    if any(type(pair) is not dict or set(pair)!={'input','output'}
           or not valid_grid(pair['input']) or not valid_grid(pair['output']) for pair in teachers):
        return False, dict(record, failure='invalid_teacher_pair')
    if len(teachers)<2:
        return False, dict(record, failure='too_few_distinct_teachers')
    if len({tuple(map(tuple,p['input'])) for p in teachers})!=len(teachers):
        return False, dict(record, failure='duplicate_teacher_inputs')
    return True, record

class _Trace:
    def __init__(self, observer, stage):
        self.observer,self.stage=observer,stage
        self.completed_models,self.current_returns,self.active=[],[],None
    def begin(self, index, model):
        self.current_returns=[]
        emit(self.observer,'model_start',model_index=index,model=model)
    def render(self, grid, model, teacher_index=None, target=None):
        self.active={'model':model,'teacher_index':teacher_index,'input':grid}
        emit(self.observer,'render_start',**self.active)
        output,detail=core.render(grid,dict(zip(core.MODEL_KEYS,model)))
        row={'model':model,'teacher_index':teacher_index,'input':grid,'output':output,'record':detail}
        if teacher_index is not None:row.update(target=target,exact=output==target)
        self.current_returns.append(deepcopy(row));self.active=None
        emit(self.observer,'render_return',**row)
        return output,detail
    def complete(self, row):
        self.completed_models.append(deepcopy(row));self.current_returns=[]
        emit(self.observer,'model_completed',record=row)
    def exception(self, error, resource):
        emit(self.observer,'evaluation_exception',stage=self.stage,exception=type(error).__name__,
             message=str(error),resource_failure=resource,semantic_HOLD=False,
             completed_model_prefix=self.completed_models,current_model_return_prefix=self.current_returns,
             active_call=self.active)

def fit(teachers, observer=None):
    valid,record=validate_teachers(teachers)
    emit(observer,'teacher_validation',valid=valid,record=record)
    if not valid:return (),record
    trace=_Trace(observer,'teacher_fit');retained=[];completed=0
    try:
        for index,model in enumerate(core.PROGRAMS):
            trace.begin(index,model);trials=[]
            for i,pair in enumerate(teachers):
                output,detail=trace.render(pair['input'],model,i,pair['output'])
                trials.append({'teacher':i,'input':pair['input'],'target':pair['output'],
                               'output':output,'exact':output==pair['output'],'record':detail})
            accepted=all(t['exact'] for t in trials)
            row={'model':dict(zip(core.MODEL_KEYS,model)),'accepted':accepted,'teachers':trials}
            trace.complete(row);completed+=1
            if accepted:retained.append(model)
        record.update(evaluated_models=completed,evaluated_teacher_returns=completed*len(teachers),
                      retained_count=len(retained),failure=None if retained else 'no_model_fits_all_teachers')
        emit(observer,'teacher_fit_completed',models=retained,record=record)
        return tuple(retained),record
    except (MemoryError,RecursionError,TimeoutError) as error:
        trace.exception(error,True)
        raise
    except Exception as error:
        trace.exception(error,False)
        raise

def predict(grid, models, observer=None):
    if not valid_grid(grid):
        record={'failure':'invalid_grid','returns':[]}
        emit(observer,'retained_consensus',output=None,record=record)
        return None,record
    trace=_Trace(observer,'prediction');returns=[]
    try:
        for index,model in enumerate(models):
            trace.begin(index,model);output,detail=trace.render(grid,model)
            row={'model':model,'output':output,'record':detail}
            returns.append(row);trace.complete(row)
        record={'models':models,'returns':returns}
        if not returns:record['failure']='no_fitted_models'
        elif any(r['output'] is None for r in returns):record['failure']='model_failure'
        elif any(r['output']!=returns[0]['output'] for r in returns):record['failure']='model_disagreement'
        output=None if 'failure' in record else returns[0]['output']
        emit(observer,'retained_consensus',output=output,record=record)
        return output,record
    except (MemoryError,RecursionError,TimeoutError) as error:
        trace.exception(error,True)
        raise
    except Exception as error:
        trace.exception(error,False)
        raise

@dataclass(frozen=True, init=False, slots=True)
class 境界点周期教材:
    モデル群: tuple
    教師数: int
    適合数: int
    不足理由: str | None
    def __init__(self, 教師群, 監査=None, 観測=None):
        models,record=fit(教師群,観測)
        object.__setattr__(self,'モデル群',models)
        object.__setattr__(self,'教師数',record['teacher_count'])
        object.__setattr__(self,'適合数',len(models))
        object.__setattr__(self,'不足理由',record.get('failure'))
        if 監査 is not None:監査.update(deepcopy(record))
    def 候補(self, 格子, policy, 観測=None):
        return predict(格子,self.モデル群,観測)
    def 記録(self):
        return {'保持候補':[list(m) for m in self.モデル群],'保持候補数':self.適合数,
                '教師数':self.教師数,'教師fit最小数':2,'不足理由':self.不足理由,
                '合意条件':'全保持モデルを完走し全盤面一致。資源例外は観測prefixとともに伝播。',
                '固定prior':'唯一最多背景・全4方位/全色役割/全同色点対を列挙・raw方位一意・境界同色2点の距離周期・位相終端・全8文法。教師観測後に外部設計した有限prior。'}
