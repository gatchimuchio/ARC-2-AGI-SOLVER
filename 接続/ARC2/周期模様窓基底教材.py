"""Strict finite periodic-motif fitting, complete alternatives, lossless traces."""
from copy import deepcopy
from dataclasses import dataclass
from . import 周期模様窓候補 as core

FIELDS=('extent','window','center','transform','phase','overlay','base_ink','highlight')
ENUMS=(('motif5plus1','input3minus2'),('motif2','input'),('floor','ceil'),core.TRANSFORMS,('window','canvas'),('tile','scale2'))
SPECS=tuple(tuple(m[k] for k in FIELDS) for m in core.models())

def valid_grid(grid):
    return (type(grid) is list and 1<=len(grid)<=30 and type(grid[0]) is list and 1<=len(grid[0])<=30
            and all(type(row) is list and len(row)==len(grid[0]) and all(type(v) is int and 0<=v<=9 for v in row) for row in grid))

def valid_spec(spec):
    return (type(spec) is tuple and len(spec)==8 and all(type(v) is str and v in allowed for v,allowed in zip(spec[:6],ENUMS))
            and all(type(v) is int and 0<=v<=9 for v in spec[6:]) and spec[6]!=spec[7])

def validate_teachers(teachers):
    record={'teacher_fit_minimum':2,'teacher_count':0}
    if type(teachers) not in (list,tuple):return False,dict(record,failure='invalid_teacher_container')
    record['teacher_count']=len(teachers)
    if any(type(p) is not dict or set(p)!={'input','output'} or not valid_grid(p['input']) or not valid_grid(p['output']) for p in teachers):return False,dict(record,failure='invalid_teacher_pair')
    if len(teachers)<2:return False,dict(record,failure='too_few_distinct_teachers')
    if len({tuple(map(tuple,p['input'])) for p in teachers})!=len(teachers):return False,dict(record,failure='duplicate_teacher_inputs')
    return True,record

def emit(observer,event):
    if observer is not None:observer(deepcopy(event))

def geometry_prefix(error):
    frames=[];tb=error.__traceback__
    keys=('mask','mh','mw','ih','iw','oh','ow','wh','ww','top','left','ar','ac','tr','tc','r','c','out','pattern','cells','row','col','row_delta','col_delta','components','seen')
    while tb:
        frame=tb.tb_frame
        if frame.f_code.co_name in ('action','parse','scaled_pattern_cells','extract_motif_components','pattern_from_component'):
            frames.append({'function':frame.f_code.co_name,'line':tb.tb_lineno,'locals':{k:deepcopy(frame.f_locals[k]) for k in keys if k in frame.f_locals}})
        tb=tb.tb_next
    return frames

def attach_exception(error,diagnostic,observer):
    try:error.evaluation_diagnostic=diagnostic
    except BaseException as secondary:
        try:diagnostic['attachment_error']={'exception':type(secondary).__name__,'message':str(secondary)}
        except BaseException:pass
    try:diagnostic['geometry_prefix']=geometry_prefix(error)
    except BaseException:diagnostic['geometry_prefix_capture_failed']=True
    try:emit(observer,dict(kind='evaluation_exception',diagnostic=diagnostic))
    except BaseException as secondary:
        try:diagnostic['observer_reporting_error']={'exception':type(secondary).__name__,'message':str(secondary)}
        except BaseException:pass

def freeze_value(v):
    if type(v) is dict:return tuple((k,freeze_value(x)) for k,x in v.items())
    if type(v) in (list,tuple):return tuple(freeze_value(x) for x in v)
    return v

class Returns:
    def __init__(self,observer):self.pool=[];self.index={};self.observer=observer
    def add(self,result):
        key=freeze_value(result)
        if key not in self.index:
            ref=len(self.pool);self.index[key]=ref;self.pool.append(result)
            emit(self.observer,{'kind':'return_pool_entry','return_ref':ref,'return':result})
        return self.index[key]

def apply(role,reason,spec):
    if role is None:return {'status':'failure','reason':reason,'output':None}
    return core.action(role,dict(zip(FIELDS,spec)))

def render(grid,spec):
    if not valid_grid(grid):return {'status':'failure','reason':'invalid_arc_grid','output':None}
    if not valid_spec(spec):return {'status':'failure','reason':'invalid_model_spec','output':None}
    role,reason=core.parse(grid)
    return apply(role,reason,spec)

def fit(teachers,observer=None):
    valid,record=validate_teachers(teachers)
    emit(observer,{'kind':'teacher_validation','valid':valid,'record':record})
    if not valid:return (),record
    parsed=[];completed=[];rows=[];retained=[];pool=Returns(observer);model_index=teacher_index=None;pending=None;result=None
    try:
        for teacher_index,pair in enumerate(teachers):
            role,reason=core.parse(pair['input']);parsed.append({'role':role,'reason':reason})
            emit(observer,{'kind':'teacher_parsed','teacher_index':teacher_index,**parsed[-1]})
        for model_index,spec in enumerate(SPECS):
            exacts=[]
            for teacher_index,pair in enumerate(teachers):
                pending=None;result=None;parse=parsed[teacher_index];result=apply(parse['role'],parse['reason'],spec)
                pending={'model_index':model_index,'teacher_index':teacher_index,'return':result,'row_committed':False,'action_executed':parse['role'] is not None}
                exact=result['status']=='success' and valid_grid(result['output']) and result['output']==pair['output']
                row={'model_index':model_index,'teacher_index':teacher_index,'return_ref':pool.add(result),'full_grid_fit':exact,
                     'parse_reused':True,'action_executed':parse['role'] is not None}
                rows.append(row);pending['row_committed']=True;exacts.append(exact)
                emit(observer,{'kind':'model_teacher_return',**row})
            pending=None;result=None
            completed.append({'model_index':model_index,'teacher_exacts':exacts,'retained':all(exacts)})
            if all(exacts):retained.append((model_index,)+spec)
            emit(observer,{'kind':'model_completed',**completed[-1]})
    except BaseException as error:
        try:
            attach_exception(error,{'stage':'fit','exception':type(error).__name__,'message':str(error),'model_index':model_index,'teacher_index':teacher_index,
                'parsed_teachers':parsed,'return_pool':pool.pool,'model_teacher_returns':rows,'completed_models':completed,'retained_prefix':tuple(retained),
                'completed_returns':len(rows),'pending_return':pending,'raw_pending_return':result,'planned_returns':len(SPECS)*len(teachers),'semantic_HOLD':False},observer)
        except BaseException:pass
        raise
    record.update(program_count=len(SPECS),complete_program_teacher_evaluations=len(rows),actual_parse_invocations=len(parsed),
        actual_action_invocations=sum(r['action_executed'] for r in rows),retained_count=len(retained),parsed_teachers=parsed,
        return_pool=pool.pool,model_teacher_returns=rows,completed_models=completed,failure=None if retained else 'no_model_fits_all_teachers')
    return tuple(retained),record

def valid_models(models):
    return (type(models) is tuple and all(type(m) is tuple and len(m)==9 and type(m[0]) is int and 0<=m[0]<len(SPECS)
            and valid_spec(m[1:]) and SPECS[m[0]]==m[1:] for m in models) and len(set(models))==len(models))

def predict(grid,models,observer=None):
    trace={'program_returns':[],'output':None};index=None;parsed=[];pending=None;result=None
    if not valid_grid(grid):return None,dict(trace,failure='invalid_arc_grid')
    if not valid_models(models):return None,dict(trace,failure='invalid_model_group')
    try:
        role,reason=core.parse(grid);parsed=[{'role':role,'reason':reason}]
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
class 周期模様窓教材:
    モデル群:tuple
    教師数:int
    不足理由:str|None
    def __init__(self,教師群,監査=None,観測=None):
        models,record=fit(教師群,観測)
        object.__setattr__(self,'モデル群',models);object.__setattr__(self,'教師数',record['teacher_count']);object.__setattr__(self,'不足理由',record.get('failure'))
        if 監査 is not None:監査.update(record)
    def 候補(self,格子,_policy,観測=None):return predict(格子,self.モデル群,観測)
    def 展開モデル(self):return [{'model_index':m[0],'spec':dict(zip(FIELDS,m[1:]))} for m in self.モデル群]
    def 記録(self):return {'保持候補数':len(self.モデル群),'保持候補':self.展開モデル(),'教師数':self.教師数,'教師fit最小数':2,'不足理由':self.不足理由,'固定prior':'finite motif extent/window/center/D4/phase/overlay hypotheses; preserve every alternative'}
