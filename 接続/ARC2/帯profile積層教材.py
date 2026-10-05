"""Immutable activation of one fixed band-profile rule; no learned relation parameters."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
import sys
from . import 帯profile積層候補 as core

RULE = ('interior_spanning_band_column_convex_translation_chains_nonflat_root_flat_terminal_v1',)
PROGRAMS = (RULE,)
valid_grid = core.valid_grid
RESOURCE_ERRORS = (MemoryError, RecursionError, TimeoutError)

def emit(observer, kind, **values):
    if observer is not None:
        observer(deepcopy({'kind':kind, **values}))

def validate_teachers(teachers):
    record={'teacher_count':0,'distinct_input_count':0,'teacher_fit_minimum':2,
            'declared_programs':1,'learned_parameter_count':0,'fit_kind':'fixed_rule_activation'}
    if type(teachers) not in (list,tuple):
        return False,dict(record,failure='invalid_teacher_container')
    record['teacher_count']=len(teachers)
    if any(type(pair) is not dict or set(pair)!={'input','output'}
           or not valid_grid(pair['input']) or not valid_grid(pair['output']) for pair in teachers):
        return False,dict(record,failure='invalid_teacher_pair')
    # Every shape and value is validated before any key/hash construction.
    record['distinct_input_count']=len({core.gridkey(pair['input']) for pair in teachers})
    if record['distinct_input_count']<2:
        return False,dict(record,failure='too_few_distinct_teacher_inputs')
    return True,record

class SearchTrace:
    """Observe call boundaries without modifying any frozen semantic function AST."""
    def __init__(self,observer):
        self.observer=observer;self.cursors={};self.exceptional=set();self.completed_return=None
        self.codes={fn.__code__ for fn in (core.enumerate_roles,core.solve_role,core.infer)}
        for code in tuple(self.codes):
            self.codes.update(c for c in code.co_consts if hasattr(c,'co_code') and c.co_name in ('extend','cover'))
    def flush(self,record):
        cursors=self.cursors.setdefault(id(record),{})
        for field in ('slots','chain_prefixes','chains','cover_trials','arrangements'):
            values=record.get(field,[]);start=cursors.get(field,0)
            if len(values)>start:
                emit(self.observer,'search_prefix',role_id=record['role_id'],field=field,start=start,
                     end=len(values),completed_entries=values[start:])
                cursors[field]=len(values)
    def __call__(self,frame,event,arg):
        if frame.f_code not in self.codes:return None
        frame.f_trace_lines=False;frame.f_trace_opcodes=False
        if event=='exception':self.exceptional.add(id(frame))
        elif event=='return' and id(frame) not in self.exceptional:
            name=frame.f_code.co_name
            if name in ('extend','cover'):self.flush(frame.f_locals['record'])
            elif name=='solve_role':
                self.flush(arg);emit(self.observer,'role_completed',record=arg)
            elif name=='enumerate_roles':emit(self.observer,'roles_enumerated',roles=arg[0],diagnostics=arg[1])
        return self
    def exception_prefix(self,error):
        # A failed call's complete mutable prefixes remain in its traceback frames.
        frames=[];seen=set();tb=error.__traceback__
        while tb:
            frame=tb.tb_frame;loc=frame.f_locals;name=frame.f_code.co_name
            if frame.f_code in self.codes:
                entry={'function':name,'line':tb.tb_lineno}
                for key in ('record','roles','diagnostics','chains'):
                    if key in loc and id(loc[key]) not in seen:
                        entry[key]=loc[key];seen.add(id(loc[key]))
                for key in ('chosen','chosen_ids','placements','used','occupied','side','col','width','slot_id','start','ci','row','step','trial'):
                    if key in loc:entry['active_'+key]=loc[key]
                frames.append(entry)
            tb=tb.tb_next
        return frames

def report_exception(observer,error,kind,**values):
    # A failed observer/storage sink cannot be guaranteed to preserve evidence.
    # Keep the original exception distinct even if its diagnostic emission fails.
    try:
        emit(observer,kind,exception=type(error).__name__,message=str(error),
             resource_failure=isinstance(error,RESOURCE_ERRORS),semantic_HOLD=False,**values)
    except BaseException as reporting_error:
        try:error.add_note('Diagnostic observer failed: '+type(reporting_error).__name__)
        except BaseException:pass

def render(grid,observer=None):
    trace=SearchTrace(observer);previous=sys.gettrace()
    if observer is not None:sys.settrace(trace)
    try:
        output,record=core.infer(grid)
        # Keep the complete raw return before any detached observer copy begins.
        trace.completed_return={'program':RULE,'input':grid,'output':output,'record':record}
        if observer is not None:sys.settrace(previous)
        emit(observer,'program_return',**trace.completed_return)
        return output,record
    except BaseException as error:
        sys.settrace(previous)
        prefix_failure=None
        try:prefix=trace.exception_prefix(error)
        except BaseException as prefix_error:
            prefix=None;prefix_failure=type(prefix_error).__name__
            try:error.add_note('Raw search prefix capture failed: '+prefix_failure)
            except BaseException:pass
        report_exception(observer,error,'search_exception',
                         completed_resource_prefix=prefix,resource_prefix_captured=prefix_failure is None,
                         resource_prefix_failure=prefix_failure,completed_program_return=trace.completed_return)
        raise
    finally:
        if observer is not None:sys.settrace(previous)

def conservation_proof(teachers):
    """Necessary invariants of every successful frozen renderer, not a selector."""
    witnesses=[]
    for index,pair in enumerate(teachers):
        source,target=pair['input'],pair['output']
        source_counts=core.Counter(v for row in source for v in row)
        target_counts=core.Counter(v for row in target for v in row)
        source_shape=[len(source),len(source[0])];target_shape=[len(target),len(target[0])]
        counts=[{'color':color,'input_count':source_counts[color],
                 'target_count':target_counts[color],
                 'target_minus_input':target_counts[color]-source_counts[color]} for color in range(10)]
        witnesses.append({'teacher_index':index,'input_shape':source_shape,'target_shape':target_shape,
                          'input_area':sum(source_counts.values()),'target_area':sum(target_counts.values()),
                          'shape_equal':source_shape==target_shape,'all_color_counts':counts,
                          'color_counts_equal':source_counts==target_counts,
                          'mismatching_colors':[r['color'] for r in counts if r['target_minus_input']!=0]})
    failing=[r['teacher_index'] for r in witnesses if not r['shape_equal'] or not r['color_counts_equal']]
    return {'proof_kind':'whole_fixed_rule_fit_necessary_conservation',
            'necessary_invariants':['input_canvas_shape','exact_all_color_pixel_counts'],
            'all_teacher_witnesses':witnesses,'violating_teacher_indices':failing,
            'whole_program_impossible':bool(failing),'all_arithmetic_complete':True,
            'justification':'solve_role renders the original canvas shape, checks exact Counter equality before admission, and restores a transposed axis. No successful infer grid can violate these invariants.'}


def fit(teachers,observer=None):
    valid,record=validate_teachers(teachers)
    emit(observer,'teacher_validation',valid=valid,record=record)
    if not valid:return (),record
    returns=[];active=None
    try:
        proof=conservation_proof(teachers)
        record['conservation_proof']=proof
        emit(observer,'conservation_proof',proof=proof)
        if proof['whole_program_impossible']:
            skipped=[{'teacher_index':index,'program':RULE,'execution':'unexecuted',
                      'renderer_executed':False,'reason':'whole_fixed_rule_fit_impossible_by_conservation',
                      'witness_teacher_indices':proof['violating_teacher_indices']} for index in range(len(teachers))]
            record.update(evaluated_programs=0,evaluated_teacher_returns=0,symbolically_rejected_programs=1,
                          retained_count=0,teacher_returns=[],unexecuted_teacher_renders=skipped,
                          failure='fixed_rule_fit_impossible_by_conservation')
            emit(observer,'program_symbolically_rejected',program=RULE,execution='symbolic',
                 renderer_executed=False,proof=proof,unexecuted_teacher_renders=skipped)
            for skipped_return in skipped:emit(observer,'teacher_render_unexecuted',**skipped_return)
            emit(observer,'teacher_fit_completed',models=(),record=record)
            return (),record
        emit(observer,'program_start',program=RULE,learned_parameter_count=0)
        for index,pair in enumerate(teachers):
            active={'teacher_index':index,'input':pair['input']}
            output,detail=render(pair['input'],observer)
            row={'teacher_index':index,'input':pair['input'],'target':pair['output'],
                 'output':output,'record':detail,'exact':output is not None and output==pair['output']}
            returns.append(row);active=None;emit(observer,'teacher_return',**row)
        retained=PROGRAMS if all(row['exact'] for row in returns) else ()
        record.update(evaluated_programs=1,evaluated_teacher_returns=len(returns),retained_count=len(retained),
                      teacher_returns=returns,failure=None if retained else 'fixed_rule_does_not_fit_all_teachers')
        emit(observer,'program_completed',program=RULE,accepted=bool(retained),teachers=returns)
        emit(observer,'teacher_fit_completed',models=retained,record=record)
        return retained,record
    except BaseException as error:
        report_exception(observer,error,'evaluation_exception',stage='teacher_fit',
                         completed_teacher_returns=returns,active_call=active)
        raise

def predict(grid,models,observer=None):
    if not valid_grid(grid):
        record={'failure':'invalid_arc_grid','returns':[]}
        emit(observer,'retained_consensus',output=None,record=record);return None,record
    returns=[];active=None
    try:
        for program in models:
            if program!=RULE:raise ValueError('unknown fixed rule activation')
            active={'program':program,'input':grid}
            output,detail=render(grid,observer)
            row={'program':program,'output':output,'record':detail};returns.append(row);active=None
            emit(observer,'retained_program_return',**row)
        record={'models':models,'returns':returns,'learned_parameter_count':0}
        if not returns:record['failure']='no_fitted_models'
        elif any(row['output'] is None for row in returns):record['failure']='whole_program_failure'
        elif any(row['output']!=returns[0]['output'] for row in returns):record['failure']='whole_program_disagreement'
        output=None if 'failure' in record else returns[0]['output']
        emit(observer,'retained_consensus',output=output,record=record);return output,record
    except BaseException as error:
        report_exception(observer,error,'evaluation_exception',stage='prediction',
                         completed_program_returns=returns,active_call=active)
        raise

@dataclass(frozen=True,init=False,slots=True)
class 帯profile積層教材:
    モデル群: tuple
    教師数: int
    異入力数: int
    適合数: int
    不足理由: str | None
    def __init__(self,教師群,監査=None,観測=None):
        models,record=fit(教師群,観測)
        object.__setattr__(self,'モデル群',models)
        object.__setattr__(self,'教師数',record['teacher_count'])
        object.__setattr__(self,'異入力数',record['distinct_input_count'])
        object.__setattr__(self,'適合数',len(models))
        object.__setattr__(self,'不足理由',record.get('failure'))
        if 監査 is not None:監査.update(deepcopy(record))
    def 候補(self,grid,policy,観測=None):
        return predict(grid,self.モデル群,観測)
    def 記録(self):
        return {'保持候補':[list(m) for m in self.モデル群],'保持候補数':self.適合数,
                '教師数':self.教師数,'異入力数':self.異入力数,'教師fit最小数':2,
                '学習関係parameter数':0,'fit種別':'固定規則の全教師適合によるactivation',
                '不足理由':self.不足理由,'合意条件':'全背景/軸/帯役割と全slot/chain/全在庫配置を保持。全役割完走かつ全完成盤面一致。資源例外はprefixを保存して伝播。'}
