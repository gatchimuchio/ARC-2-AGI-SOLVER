"""Strict immutable all-program fitting around the AST-identical corner patch renderer."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from . import 隅模様転写候補 as core

PROGRAMS=core.MODELS
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
        if frame.f_code.co_filename==core.__file__:
            entry={'function':frame.f_code.co_name,'line':tb.tb_lineno}
            for key in ('g','model','record','h','w','bg','roles','f','frames','corners','patches','active','complete','masks','mask','proposals','out','ci','corner','local','target','cells','rr','cc','rs','cs','rec','candidates','box','entry','visr','visc','sides','per','nodes','covered','owned','chosen','idx','can','indices'):
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
        with CompletionObserver(observer,program):
            output,record=core.render(grid,program)
        completed={'program':program,'input':grid,'output':output,'record':record}
        emit(observer,'program_return',**completed)
        if record.get('failure')=='exact_cover_resource_limit':
            raise ExactCoverResourceLimit('prototype exact-cover node limit 100000 exceeded')
        return output,record
    except BaseException as error:
        prefix=None;prefix_failure=None
        try:prefix=exception_prefix(error)
        except BaseException as capture_error:prefix_failure=type(capture_error).__name__
        report_exception(observer,error,'search_exception',completed_program_return=completed,
                         completed_resource_prefix=prefix,resource_prefix_captured=prefix_failure is None,
                         resource_prefix_failure=prefix_failure)
        raise


class ExactCoverResourceLimit(TimeoutError):
    """Preserve the prototype raw return but classify an exhausted bound as incomplete."""

def valid_grid(grid):
    return (type(grid) is list and 1<=len(grid)<=30 and type(grid[0]) is list and
            1<=len(grid[0])<=30 and all(type(row) is list and len(row)==len(grid[0]) and
            all(type(v) is int and 0<=v<=9 for v in row) for row in grid))

class CompletionObserver:
    """Observe immutable completed rectangle chunks without editing semantic ASTs.

    Trace callbacks only export already completed records. The final partial
    chunk remains in traceback locals on Python exceptions, even observer=None.
    """
    def __init__(self,observer,program):self.observer=observer;self.program=program;self.rec=None;self.sent=0;self.closed=False
    def __enter__(self):
        import sys
        self.previous=sys.gettrace()
        if self.observer is not None:sys.settrace(self.trace)
        return self
    def __exit__(self,*args):
        import sys
        if self.observer is not None:sys.settrace(self.previous)
    def flush(self,record,final=False):
        entries=record['rectangles'];end=len(entries)
        if final or end-self.sent>=256:
            if end>self.sent:
                emit(self.observer,'rectangle_prefix_completed',program=self.program,frame_color=record['frame_color'],start=self.sent,rectangles=entries[self.sent:end])
                self.sent=end
    def trace(self,frame,event,arg):
        if frame.f_code.co_filename!=core.__file__:return None
        if frame.f_code.co_name!='frame_roles':return None
        if event=='line':
            loc=frame.f_locals;record=loc.get('rec')
            if record is None:return self.trace
            if record is not self.rec:self.rec=record;self.sent=0;self.closed=False
            line=frame.f_lineno
            if line in RECTANGLE_COMPLETION_LINES:self.flush(record,final=line in RECTANGLE_ENUMERATION_END_LINES)
            if 'cover_nodes' in record and not self.closed:
                self.flush(record,True);emit(self.observer,'frame_color_completed',program=self.program,frame_color=record['frame_color'],row_domain=record['row_domain'],col_domain=record['col_domain'],rectangle_count=len(record['rectangles']),covers=record['covers'],cover_nodes=record['cover_nodes']);self.closed=True
        return self.trace

# Exact source-line observation locations are derived from the frozen source,
# never from grids, task identifiers, target outputs, or fitted models.
import inspect
RECTANGLE_COMPLETION_LINES=frozenset(i for i,line in enumerate(inspect.getsourcelines(core.frame_roles)[0],inspect.getsourcelines(core.frame_roles)[1]) if 'box=(r0,c0,r1,c1)' in line or 'nodes=0' in line)

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
class 隅模様転写教材:
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

RECTANGLE_ENUMERATION_END_LINES=frozenset(i for i,line in enumerate(inspect.getsourcelines(core.frame_roles)[0],inspect.getsourcelines(core.frame_roles)[1]) if 'nodes=0' in line)
