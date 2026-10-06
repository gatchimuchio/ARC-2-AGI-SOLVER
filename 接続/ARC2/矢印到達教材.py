"""Strict finite arrow pulses: complete input-only parse and whole-model consensus."""
from copy import deepcopy
from dataclasses import dataclass
import time
from . import 矢印到達候補 as core

# Every scalar of every model remains explicit; no teacher-derived constant occurs here.
PROGRAMS = tuple((m.distance, m.scope, m.single_color, m.multiple_color) for m in core.all_models())
RESOURCE_ERRORS = (MemoryError, RecursionError, TimeoutError)
HELPER_FILES = frozenset((core.__file__, core.color_components.__code__.co_filename,
                         core.shifted_sparse_point_mask.__code__.co_filename))
PREFIX_NAMES = frozenset(('grid','model','scene','counts','modes','snapshot','background','actors','covered',
    'foreground','color','component','cells','roles','tip','direction','mask','i','arm_a','arm_b','height',
    'width','ownership','arrivals','receiver_cells','endpoints','actor','dr','dc','shifted','point','receiver',
    'footprint','output','painted','receivers','r','c','queue','seen','components','key','directions','row','col',
    'current_row','current_col','next_row','next_col','next_cell','row_delta','col_delta','shifted_row','shifted_col'))

def valid_grid(grid):
    return (type(grid) is list and 1 <= len(grid) <= 30 and type(grid[0]) is list
            and 1 <= len(grid[0]) <= 30 and all(type(row) is list and len(row) == len(grid[0])
            and all(type(v) is int and 0 <= v <= 9 for v in row) for row in grid))

def valid_model(model):
    return (type(model) is tuple and len(model) == 4 and type(model[0]) is int
            and 1 <= model[0] <= 29 and type(model[1]) is str and model[1] in core.SCOPES
            and type(model[2]) is int and 0 <= model[2] <= 9
            and type(model[3]) is int and 0 <= model[3] <= 9)

def valid_models(models):
    if type(models) is not tuple or not all(valid_model(m) for m in models):
        return False
    # All validation precedes hashing; preserve full original enumeration order and no duplicates.
    chosen = set(models)
    return len(chosen) == len(models) and models == tuple(m for m in PROGRAMS if m in chosen)

def emit(observer, kind, **record):
    if observer is not None:
        observer({'kind': kind, **record})

def safe_message(error):
    try: return str(error)
    except BaseException: return '<exception message unavailable>'

def geometry_prefix(error):
    rows=[];tb=error.__traceback__
    while tb:
        frame=tb.tb_frame
        if frame.f_code.co_filename in HELPER_FILES:
            rows.append({'function':frame.f_code.co_name,'line':tb.tb_lineno,
                         'locals':{k:v for k,v in frame.f_locals.items() if k in PREFIX_NAMES}})
        tb=tb.tb_next
    return rows

def diagnostic_record(fallback):
    return dict(fallback,message=safe_message(fallback['original_exception']))

def report_exception(error, observer, stage, **context):
    fallback={'kind':stage,'exception':type(error).__name__,'semantic_HOLD':False,
              'resource_failure':isinstance(error,RESOURCE_ERRORS),'original_exception':error,
              'inner_diagnostic':getattr(error,'evaluation_diagnostic',None),**context}
    try:
        error.evaluation_diagnostic=fallback;error.evaluation_original_traceback=error.__traceback__
    except BaseException: pass
    try: fallback['geometry_prefix']=geometry_prefix(error)
    except BaseException as secondary: fallback['geometry_prefix_capture_failed']=type(secondary).__name__
    try:
        diagnostic=diagnostic_record(fallback);error.evaluation_diagnostic=diagnostic
    except BaseException as secondary:
        fallback['diagnostic_construction_failure']=type(secondary).__name__;diagnostic=fallback
    try: emit(observer,'evaluation_exception',diagnostic=diagnostic)
    except BaseException: pass

class EnumerationBudgetExceeded(TimeoutError):
    pass

class Budget:
    def __init__(self,seconds=60): self.deadline=time.monotonic()+seconds
    def check(self):
        if time.monotonic()>self.deadline: raise TimeoutError('whole call wall budget exhausted')

def validate_teachers(teachers):
    record={'teacher_count':0,'distinct_input_count':0,'teacher_fit_minimum':2}
    if type(teachers) not in (list,tuple): return False,dict(record,failure='invalid_teacher_container')
    record['teacher_count']=len(teachers)
    if any(type(pair) is not dict or set(pair)!={'input','output'}
           or not valid_grid(pair['input']) or not valid_grid(pair['output']) for pair in teachers):
        return False,dict(record,failure='invalid_teacher_pair')
    record['distinct_input_count']=len({tuple(map(tuple,p['input'])) for p in teachers})
    if record['distinct_input_count']!=len(teachers): return False,dict(record,failure='duplicate_or_conflicting_teacher_input')
    if record['distinct_input_count']<2: return False,dict(record,failure='too_few_distinct_teacher_inputs')
    return True,record

def parse(grid,observer=None,budget=None):
    scene=detail=None;raw_pending=False
    try:
        budget=budget if budget is not None else Budget();budget.check()
        if not valid_grid(grid): return None,{'status':'HOLD','reason':'invalid_grid'}
        scene,detail=core.parse_input(grid);raw_pending=True
        emit(observer,'parse_return',scene=scene,record=detail);budget.check()
        return scene,detail
    except BaseException as error:
        try:
            report_exception(error,observer,'parse_exception',raw_return_pending=raw_pending,
                             pending_scene=scene if raw_pending else None,pending_detail=detail if raw_pending else None)
        except BaseException: pass
        raise

def render_row(output,detail): return {'output':output,'record':detail}
def teacher_row(index,pair,output,detail):
    return {'teacher_index':index,'output':output,'record':detail,'exact':output is not None and output==pair['output']}

def execute_scene(scene,model,observer=None,budget=None):
    output=detail=None;raw_pending=False
    try:
        budget=budget if budget is not None else Budget();budget.check()
        if not valid_model(model): return None,{'status':'HOLD','reason':'invalid_model'}
        output,detail=core.render_scene(scene,core.Model(*model));raw_pending=True
        row=render_row(output,detail)
        emit(observer,'render_completed',model=model,**row);budget.check()
        return output,detail
    except BaseException as error:
        try:
            report_exception(error,observer,'render_exception',model=model,raw_return_pending=raw_pending,
                             pending_output=output if raw_pending else None,pending_detail=detail if raw_pending else None)
        except BaseException: pass
        raise

def model_row(roles,execution):
    return {'status':execution['status'],'roles':roles,'execution':execution}

def render(grid,model,observer=None,budget=None):
    output=execution=roles=None;raw_pending=False
    try:
        budget=budget if budget is not None else Budget();budget.check()
        if not valid_model(model): return None,{'status':'HOLD','reason':'invalid_model'}
        scene,roles=parse(grid,observer,budget)
        if scene is None: return None,roles
        output,execution=execute_scene(scene,model,observer,budget);raw_pending=True
        detail=model_row(roles,execution)
        return output,detail
    except BaseException as error:
        try:
            report_exception(error,observer,'render_model_exception',model=model,raw_return_pending=raw_pending,
                             pending_output=output if raw_pending else None,pending_execution=execution if raw_pending else None,completed_roles=roles)
        except BaseException: pass
        raise

def fit(teachers,observer=None,budget=None):
    models=[];records=[];calls=[];parsed=[];parse_records=[];active=None;validation=None
    output=detail=None;scene=None;raw_pending=False;parse_pending=False;required_calls=None
    try:
        budget=budget if budget is not None else Budget();budget.check()
        valid,validation=validate_teachers(teachers);budget.check()
        emit(observer,'teacher_validation',valid=valid,record=validation)
        if not valid: return (),validation
        required_calls=len(PROGRAMS)*len(teachers)
        # The grammar parses inputs independently of model and output. Complete every parse first.
        for index,pair in enumerate(teachers):
            active={'teacher_index':index,'phase':'proof_parse'};parse_pending=False
            emit(observer,'parse_start',teacher_index=index)
            scene,detail=parse(pair['input'],observer,budget);parse_pending=True
            parsed.append(scene);parse_records.append({'teacher_index':index,'record':detail})
            parse_pending=False;active=None
            emit(observer,'parse_completed',teacher_index=index,scene=scene,record=detail)
        rejected=[i for i,s in enumerate(parsed) if s is None]
        if rejected:
            record=dict(validation,failure='model_independent_parse_rejection',proof_rejected=True,
                rejected_teacher_indices=rejected,teacher_parse_records=parse_records,
                proof_parse_calls=len(parsed),evaluated_teacher_calls=0,
                symbolic_unexecuted_teacher_calls=len(PROGRAMS)*len(teachers),
                declared_model_count=len(PROGRAMS),model_returns=[],retained_count=0,logical_domain_complete=True)
            emit(observer,'empty_fit_domain_proof',record=record)
            budget.check();emit(observer,'teacher_fit_completed',models=(),record=record)
            return (),record
        if required_calls > core.FIT_BUDGET:
            raise EnumerationBudgetExceeded('enumeration_budget: required '+str(required_calls)+' exceeds '+str(core.FIT_BUDGET)+'; zero model-teacher actions executed')
        for model_index,model in enumerate(PROGRAMS):
            calls=[]
            for index,(pair,scene) in enumerate(zip(teachers,parsed)):
                budget.check();active={'model_index':model_index,'model':model,'teacher_index':index}
                output=detail=None;raw_pending=False
                emit(observer,'model_teacher_start',**active)
                output,detail=execute_scene(scene,model,observer,budget);raw_pending=True
                row=teacher_row(index,pair,output,detail);calls.append(row);raw_pending=False
                emit(observer,'model_teacher_return',model_index=model_index,model=model,**row)
                active=None
            exact=all(row['exact'] for row in calls)
            result={'model_index':model_index,'model':model,'returns':calls,'all_exact':exact}
            records.append(result)
            if exact: models.append(model)
            calls=[];active=None;emit(observer,'model_completed',record=result)
        budget.check()
        record=dict(validation,teacher_parse_records=parse_records,proof_parse_calls=len(parsed),
            evaluated_teacher_calls=len(PROGRAMS)*len(teachers),symbolic_unexecuted_teacher_calls=0,
            declared_model_count=len(PROGRAMS),model_returns=records,retained_count=len(models),logical_domain_complete=True)
        if not models: record['failure']='no_all_teacher_model'
        emit(observer,'teacher_fit_completed',models=tuple(models),record=record)
        return tuple(models),record
    except BaseException as error:
        try:
            report_exception(error,observer,'fit_exception',validation=validation,
                completed_parse_records=parse_records,completed_scenes=parsed,active_call=active,
                required_calls=required_calls,enumeration_budget=core.FIT_BUDGET,
                committed_model_count=len(records),current_teacher_row_count=len(calls),
                raw_parse_pending=parse_pending,pending_scene=scene if parse_pending else None,
                completed_model_returns=records,completed_teacher_returns=calls,raw_return_pending=raw_pending,
                pending_output=output if raw_pending else None,pending_detail=detail if raw_pending or parse_pending else None)
        except BaseException: pass
        raise

def predict(grid,models,observer=None,budget=None):
    rows=[];active=None;output=detail=None;raw_pending=False
    try:
        budget=budget if budget is not None else Budget();budget.check()
        if not valid_grid(grid): return None,{'failure':'invalid_grid','returns':[]}
        if not valid_models(models): return None,{'failure':'invalid_retained_state','returns':[]}
        for model in models:
            active=model;output=detail=None;raw_pending=False
            output,detail=render(grid,model,observer,budget);raw_pending=True
            row={'model':model,'output':output,'detail':detail};rows.append(row);raw_pending=False;active=None
            emit(observer,'retained_model_return',**row)
        reason=('no_retained_models' if not rows else 'retained_model_failed' if any(r['output'] is None for r in rows)
                else 'retained_role_disagreement' if any(r['detail']['roles']!=rows[0]['detail']['roles'] for r in rows)
                else 'retained_models_disagree' if any(r['output']!=rows[0]['output'] for r in rows) else None)
        budget.check();record={'returns':rows}
        if reason: record['failure']=reason
        output=None if reason else deepcopy(rows[0]['output'])
        emit(observer,'retained_consensus',output=output,record=record)
        return output,record
    except BaseException as error:
        try:
            report_exception(error,observer,'prediction_exception',completed_model_returns=rows,active_model=active,
                raw_return_pending=raw_pending,pending_output=output if raw_pending else None,pending_detail=detail if raw_pending else None)
        except BaseException: pass
        raise

@dataclass(frozen=True,init=False,slots=True)
class 矢印到達教材:
    モデル群: tuple
    教師数: int
    異入力数: int
    不足理由: str | None
    def __init__(self,教師群,監査=None,観測=None):
        models=();record=None
        try:
            models,record=fit(教師群,観測)
            object.__setattr__(self,'モデル群',models);object.__setattr__(self,'教師数',record['teacher_count'])
            object.__setattr__(self,'異入力数',record['distinct_input_count']);object.__setattr__(self,'不足理由',record.get('failure'))
            if 監査 is not None: 監査.update(record)
        except BaseException as error:
            try:
                report_exception(error,観測,'state_entry_exception',completed_fit=record,completed_models=models)
            except BaseException: pass
            raise
    def 候補(self,grid,policy,観測=None): return predict(grid,self.モデル群,観測)
    def 記録(self):
        return {'保持候補':list(self.モデル群),'保持候補数':len(self.モデル群),'教師数':self.教師数,
                '異入力数':self.異入力数,'教師fit最小数':2,'不足理由':self.不足理由}
