"""Strict immutable all-program fitting around the frozen whole-chart full-footprint renderer."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from . import 全足跡整列候補 as core
from .全足跡整列候補 import valid_grid
PROGRAMS=('ascending_full_footprints',)
RESOURCE_ERRORS=(MemoryError,RecursionError,TimeoutError)

def emit(observer,kind,**values):
    if observer is not None:observer(deepcopy({'kind':kind,**values}))

def report_exception(observer,error,kind,**values):
    diagnostic={'kind':kind,'exception':type(error).__name__,'message':str(error),
                'resource_failure':isinstance(error,RESOURCE_ERRORS),'semantic_HOLD':False,**values}
    previous=getattr(error,'evaluation_diagnostic',None)
    if previous is not None:diagnostic['inner_diagnostic']=previous
    try:error.evaluation_diagnostic=diagnostic
    except BaseException:pass
    try:emit(observer,kind,**{k:v for k,v in diagnostic.items() if k!='kind'})
    except BaseException as reporting_error:
        try:error.add_note('Diagnostic observer failed: '+type(reporting_error).__name__)
        except BaseException:pass

def exception_prefix(error):
    frames=[];tb=error.__traceback__
    while tb:
        frame=tb.tb_frame
        if frame.f_code.co_filename==core.render.__code__.co_filename:
            entry={'function':frame.f_code.co_name,'line':tb.tb_lineno}
            for key in ('grid','background','foreground','extent','colors','cells_by_color','components','raw','roles','row','axis','axis_cells','bars','owned','used_columns','color','component','cells','top','bottom','left','right','errors','rectangle','columns','record','failures','role','actions','detail','counts','backgrounds','bg','tokens','footprints','expected_tokens','expected_footprints','sorted_footprints','result','old_cells','proposals','out','affected'):
                if key in frame.f_locals:entry[key]=frame.f_locals[key]
            frames.append(entry)
        tb=tb.tb_next
    return frames

def render(grid,program,observer=None):
    if type(program) is not str or program not in PROGRAMS:
        record={'failure':'invalid_fixed_program','status':'HOLD'}
        emit(observer,'program_return',program=program,input=grid,output=None,record=record)
        return None,record
    completed=None
    try:
        output,record=core.render(grid)
        completed={'program':program,'input':grid,'output':output,'record':record}
        emit(observer,'program_return',**completed)
        return output,record
    except BaseException as error:
        prefix=None;prefix_failure=None
        try:prefix=exception_prefix(error)
        except BaseException as capture_error:prefix_failure=type(capture_error).__name__
        report_exception(observer,error,'search_exception',completed_program_return=completed,
                         completed_resource_prefix=prefix,resource_prefix_captured=prefix_failure is None,
                         resource_prefix_failure=prefix_failure)
        raise

def gridkey(grid):return tuple(tuple(row) for row in grid)

def validate_teachers(teachers):
    record={'teacher_count':0,'distinct_input_count':0,'teacher_fit_minimum':2,'declared_programs':len(PROGRAMS)}
    if type(teachers) not in (list,tuple):return False,dict(record,failure='invalid_teacher_container')
    record['teacher_count']=len(teachers)
    if any(type(p) is not dict or set(p)!={'input','output'} or not valid_grid(p['input']) or not valid_grid(p['output']) for p in teachers):
        return False,dict(record,failure='invalid_teacher_pair')
    record['distinct_input_count']=len({gridkey(p['input']) for p in teachers})
    if record['distinct_input_count']<2:return False,dict(record,failure='too_few_distinct_teacher_inputs')
    return True,record

def fit(teachers,observer=None):
    valid,record=validate_teachers(teachers);emit(observer,'teacher_validation',valid=valid,record=record)
    if not valid:return (),record
    returns=[];models=[];active=None;calls=[]
    try:
        for program in PROGRAMS:
            calls=[];emit(observer,'program_start',program=program)
            for index,pair in enumerate(teachers):
                active={'program':program,'teacher_index':index,'input':pair['input']}
                output,detail=render(pair['input'],program,observer)
                row={'teacher_index':index,'input':pair['input'],'target':pair['output'],'output':output,'record':detail,'exact':output is not None and output==pair['output']}
                calls.append(row);active=None;emit(observer,'teacher_return',program=program,**row)
            result={'program':program,'teachers':calls,'all_exact':all(row['exact'] for row in calls)}
            returns.append(result);calls=[]
            if result['all_exact']:models.append(program)
            emit(observer,'program_completed',**result)
        retained=tuple(models)
        record.update(program_returns=returns,evaluated_programs=len(returns),evaluated_teacher_returns=sum(len(x['teachers']) for x in returns),retained_count=len(retained))
        if not retained:record['failure']='no_all_teacher_model'
        emit(observer,'teacher_fit_completed',models=retained,record=record)
        return retained,record
    except BaseException as error:
        report_exception(observer,error,'evaluation_exception',stage='fit',completed_program_returns=returns,
                         completed_teacher_returns=calls,active_call=active)
        raise

def predict(grid,models,observer=None):
    if not valid_grid(grid):
        record={'failure':'invalid_arc_grid','status':'HOLD','returns':[]};emit(observer,'retained_consensus',output=None,record=record);return None,record
    if type(models) is not tuple or any(type(p) is not str or p not in PROGRAMS for p in models) or len(set(models))!=len(models):
        record={'failure':'invalid_retained_state','status':'HOLD','returns':[]}
        emit(observer,'retained_consensus',output=None,record=record);return None,record
    returns=[];active=None
    try:
        for program in models:
            active={'program':program,'input':grid}
            output,detail=render(grid,program,observer)
            row={'program':program,'output':output,'record':detail};returns.append(row);active=None
            emit(observer,'retained_program_return',**row)
        record={'models':models,'returns':returns}
        if not returns:record['failure']='no_fitted_models'
        elif any(row['output'] is None for row in returns):record['failure']='retained_program_failed'
        elif any(row['output']!=returns[0]['output'] for row in returns):record['failure']='retained_program_conflict'
        output=None if 'failure' in record else returns[0]['output'];record['status']='HOLD' if output is None else 'complete'
        emit(observer,'retained_consensus',output=output,record=record);return output,record
    except BaseException as error:
        report_exception(observer,error,'evaluation_exception',stage='prediction',completed_program_returns=returns,active_call=active)
        raise

@dataclass(frozen=True,init=False,slots=True)
class 全足跡整列教材:
    モデル群: tuple
    教師数: int
    異入力数: int
    適合数: int
    不足理由: str | None
    def __init__(self,教師群,監査=None,観測=None):
        models,record=fit(教師群,観測)
        object.__setattr__(self,'モデル群',models);object.__setattr__(self,'教師数',record['teacher_count'])
        object.__setattr__(self,'異入力数',record['distinct_input_count']);object.__setattr__(self,'適合数',len(models))
        object.__setattr__(self,'不足理由',record.get('failure'))
        if 監査 is not None:監査.update(deepcopy(record))
    def 候補(self,grid,policy,観測=None):return predict(grid,self.モデル群,観測)
    def 記録(self):
        return {'保持候補':list(self.モデル群),'保持候補数':self.適合数,'教師数':self.教師数,'異入力数':self.異入力数,
                '教師fit最小数':2,'不足理由':self.不足理由,'合意条件':'全保持programが完走し全出力一致。未完資源と例外はprefix保存後に伝播。'}
