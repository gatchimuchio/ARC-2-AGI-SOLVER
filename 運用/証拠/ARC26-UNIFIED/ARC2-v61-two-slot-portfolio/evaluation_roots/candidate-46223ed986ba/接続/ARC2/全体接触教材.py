"""Strict target-free whole-body contact fitting; all role and law alternatives remain."""
import sys
import time
from copy import deepcopy
from dataclasses import dataclass
from . import 全体接触候補 as core

GEOMETRY_CODES = (core.parse.__code__, core.execute.__code__)
PROGRAMS = core.PROGRAMS
valid_grid = core.valid_grid
RESOURCE_ERRORS = (MemoryError, RecursionError, TimeoutError)
PREFIX_NAMES = frozenset(('grid','program','role','counts','modes','bg','palette','locations','trials','roles',
    'trial','tail','head','body','port','point','source_directions','view','components','bodies','failures',
    'index','component','cells','exit_cells','payload','normals','record','source_cells','owned','foreground',
    'direction','normal_tuple','h','w','body_at','pending','visited','activated','paint','states','exits',
    'revisits','activations','state','cell','d','hit','next_states','b','outgoing','emitted','successor',
    'output','preserved','r','c','dr','dc'))

def emit(observer, kind, **record):
    if observer is not None:
        observer({'kind': kind, **record})

def safe_message(error):
    try:
        return str(error)
    except BaseException:
        return '<exception message unavailable>'

def geometry_prefix(error):
    rows = []
    tb = error.__traceback__
    while tb:
        frame = tb.tb_frame
        if frame.f_code in GEOMETRY_CODES:
            rows.append({'function': frame.f_code.co_name, 'line': tb.tb_lineno,
                         'locals': {key: value for key, value in frame.f_locals.items() if key in PREFIX_NAMES}})
        tb = tb.tb_next
    return rows

def diagnostic_record(fallback):
    # Separate construction point for testing failure while preserving the raw prefix.
    return dict(fallback, message=safe_message(fallback['original_exception']))

def report_exception(error, observer, stage, **context):
    # Attach the original and complete wrapper prefixes BEFORE optional diagnostics or observers.
    fallback = {'kind': stage, 'exception': type(error).__name__, 'semantic_HOLD': False,
                'resource_failure': isinstance(error, RESOURCE_ERRORS),
                'original_exception': error, 'inner_diagnostic': getattr(error, 'evaluation_diagnostic', None),
                **context}
    try:
        error.evaluation_diagnostic = fallback
        error.evaluation_original_traceback = error.__traceback__
    except BaseException:
        pass
    try:
        fallback['geometry_prefix'] = geometry_prefix(error)
    except BaseException as secondary:
        fallback['geometry_prefix_capture_failed'] = type(secondary).__name__
    try:
        diagnostic = diagnostic_record(fallback)
        error.evaluation_diagnostic = diagnostic
    except BaseException as secondary:
        fallback['diagnostic_construction_failure'] = type(secondary).__name__
        diagnostic = fallback
    try:
        emit(observer, 'evaluation_exception', diagnostic=diagnostic)
    except BaseException:
        pass

class Budget:
    """Whole-call wall budget; no structural hypotheses are pruned at exhaustion."""
    def __init__(self, seconds=60):
        self.deadline = time.monotonic() + seconds
        self.previous = None
    def check(self):
        if time.monotonic() > self.deadline:
            raise TimeoutError('whole call wall budget exhausted')
    def trace(self, frame, event, arg):
        if frame.f_code.co_filename == core.__file__:
            self.check()
            return self.trace
        return None
    def __enter__(self):
        self.check()
        self.previous = sys.gettrace()
        sys.settrace(self.trace)
        return self
    def __exit__(self, *unused):
        sys.settrace(self.previous)


def valid_model(model):
    return (type(model) is tuple and len(model) == 2
            and all(type(x) is str for x in model) and model in PROGRAMS)

def valid_models(models):
    return (type(models) is tuple and all(valid_model(model) for model in models)
            and len(set(models)) == len(models))

def validate_teachers(teachers):
    record = {'teacher_count': 0, 'distinct_input_count': 0, 'teacher_fit_minimum': 2}
    if type(teachers) not in (list, tuple):
        return False, dict(record, failure='invalid_teacher_container')
    record['teacher_count'] = len(teachers)
    # Validate the complete pair and every grid before hashing or key construction.
    if any(type(pair) is not dict or set(pair) != {'input', 'output'}
           or not valid_grid(pair['input']) or not valid_grid(pair['output']) for pair in teachers):
        return False, dict(record, failure='invalid_teacher_pair')
    record['distinct_input_count'] = len({tuple(map(tuple, pair['input'])) for pair in teachers})
    if record['distinct_input_count'] < 2:
        return False, dict(record, failure='too_few_distinct_teacher_inputs')
    return True, record

def teacher_row(index, pair, output, detail):
    return {'teacher_index': index, 'output': output, 'record': detail,
            'exact': output is not None and output == pair['output']}

def role_row(index, role, output, detail):
    return {'role_index': index, 'output': output, 'detail': detail}

def render(grid, model, observer=None, budget=None):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_grid', 'returns': []}
    if not valid_model(model):
        return None, {'failure': 'invalid_model', 'returns': []}
    budget = budget if budget is not None else Budget()
    roles = []; record = None; rows = []; index = None; role = None
    output = detail = None; raw_pending = False
    try:
        with budget:
            emit(observer, 'render_start', model=model, input=grid)
            roles, record = core.parse(grid)
            emit(observer, 'parse_completed', model=model, record=record)
            for index, role in enumerate(roles):
                budget.check(); raw_pending = False; output = detail = None
                output, detail = core.execute(grid, role, model); raw_pending = True
                row = role_row(index, role, output, detail)
                rows.append(row); raw_pending = False
                emit(observer, 'role_completed', model=model, **row)
            record['returns'] = rows
            if not rows:
                record['failure'] = 'no_structural_role'; output = None
            elif any(row['output'] is None for row in rows):
                record['failure'] = 'retained_role_failed'; output = None
            elif any(row['output'] != rows[0]['output'] for row in rows):
                record['failure'] = 'retained_roles_disagree'; output = None
            else:
                output = rows[0]['output']
            budget.check()
            return output, record
    except BaseException as error:
        try:
            report_exception(error, observer, 'render_exception', model=model, parsed_roles=roles,
                             parse_record=record, completed_role_returns=rows, active_role_index=index,
                             active_role=role, raw_return_pending=raw_pending,
                             pending_output=output if raw_pending else None,
                             pending_detail=detail if raw_pending else None)
        except BaseException as reporting_error:
            try:
                error.evaluation_reporting_failure = reporting_error
            except BaseException:
                pass
        raise

def fit(teachers, observer=None, budget=None):
    models = []; records = []; calls = []; active = None; validation = None
    output = detail = None; raw_pending = False
    budget = budget if budget is not None else Budget()
    try:
        valid, validation = validate_teachers(teachers)
        emit(observer, 'teacher_validation', valid=valid, record=validation)
        if not valid:
            return (), validation
        for model_index, model in enumerate(PROGRAMS):
            calls = []
            for index, pair in enumerate(teachers):
                budget.check(); active = {'model_index': model_index, 'model': model, 'teacher_index': index}
                output = detail = None; raw_pending = False
                emit(observer, 'model_teacher_start', **active)
                output, detail = render(pair['input'], model, observer, budget); raw_pending = True
                row = teacher_row(index, pair, output, detail)
                calls.append(row); raw_pending = False
                emit(observer, 'model_teacher_return', model_index=model_index, model=model, **row)
                active = None
            exact = all(row['exact'] for row in calls)
            result = {'model_index': model_index, 'model': model, 'returns': calls, 'all_exact': exact}
            records.append(result)
            if exact:
                models.append(model)
            calls = []; active = None
            emit(observer, 'model_completed', record=result)
        budget.check()
        record = dict(validation, model_returns=records, evaluated_teacher_calls=len(PROGRAMS)*len(teachers),
                      retained_count=len(models), logical_domain_complete=True)
        if not models:
            record['failure'] = 'no_all_teacher_model'
        emit(observer, 'teacher_fit_completed', models=tuple(models), record=record)
        return tuple(models), record
    except BaseException as error:
        try:
            report_exception(error, observer, 'fit_exception', validation=validation,
                             completed_model_returns=records, completed_teacher_returns=calls,
                             active_call=active, raw_return_pending=raw_pending,
                             pending_output=output if raw_pending else None,
                             pending_detail=detail if raw_pending else None)
        except BaseException as reporting_error:
            try:
                error.evaluation_reporting_failure = reporting_error
            except BaseException:
                pass
        raise

def predict(grid, models, observer=None, budget=None):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_grid', 'returns': []}
    if not valid_models(models):
        return None, {'failure': 'invalid_retained_state', 'returns': []}
    budget = budget if budget is not None else Budget()
    rows = []; active = None; output = detail = None; raw_pending = False
    try:
        for model in models:
            budget.check(); active = model; output = detail = None; raw_pending = False
            output, detail = render(grid, model, observer, budget); raw_pending = True
            row = {'model': model, 'output': output, 'detail': detail}
            rows.append(row); raw_pending = False; active = None
            emit(observer, 'retained_model_return', **row)
        reason = ('no_retained_models' if not rows else 'retained_model_failed' if any(row['output'] is None for row in rows)
                  else 'retained_models_disagree' if any(row['output'] != rows[0]['output'] for row in rows) else None)
        budget.check()
        record = {'returns': rows}
        if reason:
            record['failure'] = reason
        output = None if reason else core.clone_grid(rows[0]['output'])
        emit(observer, 'retained_consensus', output=output, record=record)
        return output, record
    except BaseException as error:
        try:
            report_exception(error, observer, 'prediction_exception', completed_model_returns=rows,
                             active_model=active, raw_return_pending=raw_pending,
                             pending_output=output if raw_pending else None,
                             pending_detail=detail if raw_pending else None)
        except BaseException as reporting_error:
            try:
                error.evaluation_reporting_failure = reporting_error
            except BaseException:
                pass
        raise

@dataclass(frozen=True, init=False, slots=True)
class 全体接触教材:
    モデル群: tuple
    教師数: int
    異入力数: int
    不足理由: str | None
    def __init__(self, 教師群, 監査=None, 観測=None):
        models = (); record = None
        try:
            models, record = fit(教師群, 観測)
            object.__setattr__(self, 'モデル群', models)
            object.__setattr__(self, '教師数', record['teacher_count'])
            object.__setattr__(self, '異入力数', record['distinct_input_count'])
            object.__setattr__(self, '不足理由', record.get('failure'))
            if 監査 is not None:
                監査.update(deepcopy(record))
        except BaseException as error:
            try:
                report_exception(error, 観測, 'state_entry_exception', completed_fit=record, completed_models=models)
            except BaseException as reporting_error:
                try:
                    error.evaluation_reporting_failure = reporting_error
                except BaseException:
                    pass
            raise
    def 候補(self, grid, policy, 観測=None):
        return predict(grid, self.モデル群, 観測)
    def 記録(self):
        return {'保持候補': list(self.モデル群), '保持候補数': len(self.モデル群),
                '教師数': self.教師数, '異入力数': self.異入力数,
                '教師fit最小数': 2, '不足理由': self.不足理由}
