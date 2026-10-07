"""Strict target-free congruent-body directed ports; both connectivity programs and all D4 alternatives remain."""
import sys
from collections import Counter
import time
from copy import deepcopy
from dataclasses import dataclass
from . import 合同物体出口候補 as core

PROGRAMS = tuple((p,) for p in core.PROGRAMS)

def valid_grid(grid):
    return (type(grid) is list and 1 <= len(grid) <= 30 and type(grid[0]) is list
            and 1 <= len(grid[0]) <= 30 and all(type(row) is list and len(row) == len(grid[0])
            and all(type(v) is int and 0 <= v <= 9 for v in row) for row in grid))
RESOURCE_ERRORS = (MemoryError, RecursionError, TimeoutError, core.BudgetExhausted)
PREFIX_NAMES = frozenset(('grid','connectivity','budget','rec','h','w','counts','modes','bg','components',
    'owner','cue_at','index','comp','raw','r','c','dr','dc','normals','cue','crop','body','own','bodies','cues',
    'foreground','maps','source','target','pair','target_cells','transform','comparison','transformed','match',
    'scan','sh','sw','lr','lc','odr','odc','factor','transforms','alt','ar','ac','nr','nc','cue_proposals','item',
    'factors','valid','cells','ns','proposed','cid','p','conflicts','output','key','background_color',
    'include_diagonal','height','width','directions','seen','records','row','col','queue','color_counts',
    'current_row','current_col','color','row_delta','col_delta','next_row','next_col','next_cell','record'))
HELPER_FILES = frozenset((core.__file__, core.mixed_region_dicts_for_grid.__code__.co_filename,
                         core.d4_motif_transform_coord.__code__.co_filename, core.clone_grid.__code__.co_filename))


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
        if frame.f_code.co_filename in HELPER_FILES:
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
    """Whole-call deadline and prospective exception evidence, without changing geometry AST."""
    def __init__(self, seconds=60):
        self.deadline = time.monotonic() + seconds
        self.previous = None
        self.original_error = None
        self.original_traceback = None
        self.exception_prefix = []
    def check(self):
        if time.monotonic() > self.deadline:
            raise TimeoutError('whole call wall budget exhausted')
    def trace(self, frame, event, arg):
        if frame.f_code.co_filename not in HELPER_FILES:
            return None
        if event == 'exception':
            error = arg[1]
            if not isinstance(error, (StopIteration, GeneratorExit)):
                if self.original_error is None:
                    self.original_error = error
                    self.original_traceback = arg[2]
                if error is self.original_error:
                    self.exception_prefix.append({'function': frame.f_code.co_name, 'line': frame.f_lineno,
                        'locals': {key:value for key,value in frame.f_locals.items() if key in PREFIX_NAMES}})
        try:
            self.check()
        except BaseException as error:
            if self.original_error is None:
                self.original_error = error
                self.original_traceback = error.__traceback__
            self.exception_prefix.append({'function':frame.f_code.co_name,'line':frame.f_lineno,
                'locals':{key:value for key,value in frame.f_locals.items() if key in PREFIX_NAMES}})
            raise
        return self.trace
    def __enter__(self):
        self.check()
        self.previous = sys.gettrace()
        self.original_error = None
        self.original_traceback = None
        self.exception_prefix = []
        sys.settrace(self.trace)
        return self
    def __exit__(self, *unused):
        sys.settrace(self.previous)


def valid_model(model):
    return type(model) is tuple and len(model) == 1 and type(model[0]) is int and model in PROGRAMS

def valid_models(models):
    return (type(models) is tuple and all(valid_model(model) for model in models)
            and models == tuple(model for model in PROGRAMS if model in models))


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
    if record['distinct_input_count'] != len(teachers):
        return False, dict(record, failure='duplicate_or_conflicting_teacher_input')
    if record['distinct_input_count'] < 2:
        return False, dict(record, failure='too_few_distinct_teacher_inputs')
    return True, record

def teacher_necessity_certificate(index, pair):
    """Necessary conditions of every successful source render; never constructs a model."""
    grid, target = pair['input'], pair['output']
    shape = (len(grid), len(grid[0]))
    target_shape = (len(target), len(target[0]))
    counts = Counter(value for row in grid for value in row)
    modes = sorted(value for value, count in counts.items() if count == max(counts.values()))
    same_shape = shape == target_shape
    applicable = same_shape and len(modes) == 1
    changes = []
    if applicable:
        background = modes[0]
        changes = [{'cell': [r,c], 'input': value, 'output': target[r][c]}
                   for r,row in enumerate(grid) for c,value in enumerate(row)
                   if value != background and value != target[r][c]]
    # A successful C4 or C8 render needs a border singleton cue. Every
    # C8 singleton is also orthogonally isolated, irrespective of its color.
    border_cue_applicable = len(modes) == 1
    border_cue_candidates = None
    if border_cue_applicable:
        background = modes[0]
        h, w = shape
        border_cue_candidates = [[r, c] for r, row in enumerate(grid)
            for c, value in enumerate(row)
            if value != background and (r in (0, h - 1) or c in (0, w - 1))
            and all(not (0 <= r + dr < h and 0 <= c + dc < w)
                    or grid[r + dr][c + dc] == background
                    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    violations = []
    if not same_shape:
        violations.append('shape_change')
    if changes:
        violations.append('original_foreground_changed')
    if border_cue_applicable and not border_cue_candidates:
        violations.append('no_possible_border_singleton_cue')
    return {'teacher_index': index, 'complete': True, 'input_shape': shape, 'output_shape': target_shape,
            'shape_equal': same_shape, 'input_background_candidates': modes,
            'input_background': modes[0] if len(modes) == 1 else None,
            'foreground_check_applicable': applicable, 'foreground_changes': changes,
            'border_cue_check_applicable': border_cue_applicable,
            'orthogonally_isolated_border_foreground': border_cue_candidates,
            'violations': violations, 'all_programs_necessarily_fail': bool(violations)}

def teacher_necessities(teachers, observer, budget):
    records = []; active = None; certificate = None; raw_pending = False
    try:
        for index,pair in enumerate(teachers):
            budget.check(); active = index; certificate = None; raw_pending = False
            certificate = teacher_necessity_certificate(index,pair); raw_pending = True
            records.append(certificate); raw_pending = False
            emit(observer, 'teacher_necessity_completed', record=certificate)
            active = None
        budget.check()
        return records
    except BaseException as error:
        try:
            report_exception(error, observer, 'teacher_necessity_exception', completed_certificates=records,
                             active_teacher_index=active, raw_certificate_pending=raw_pending,
                             pending_certificate=certificate if raw_pending else None)
        except BaseException as reporting_error:
            # Diagnostics and metadata allocation must never replace the primary.
            try:
                error.evaluation_reporting_failure = reporting_error
            except BaseException:
                pass
        raise


def teacher_row(index, pair, output, detail):
    return {'teacher_index': index, 'output': output, 'record': detail,
            'exact': output is not None and output == pair['output']}

def render_row(output, detail):
    return {'output': output, 'record': detail}

def render(grid, model, observer=None, budget=None, operation_budget=200000, fault=None):
    output = detail = None; raw_pending = False; control = budget
    try:
        control = budget if budget is not None else Budget()
        control.check()
        if not valid_grid(grid):
            return None, {'failure':'invalid_grid', 'complete':True, 'status':'HOLD'}
        if not valid_model(model):
            return None, {'failure':'invalid_model', 'complete':True, 'status':'HOLD'}
        with control:
            emit(observer, 'render_start', model=model, input=grid)
            output, detail = core.render(grid, model[0], budget=operation_budget, fault=fault)
            raw_pending = True
            if not detail['complete']:
                # The exact prototype catches ordinary errors. Recover its original exception,
                # traceback and live operation prefixes from the prospective trace boundary.
                error = control.original_error
                if error is None:
                    error = RuntimeError('incomplete prototype return without captured exception')
                raise error.with_traceback(control.original_traceback)
            row = render_row(output, detail)
            emit(observer, 'render_completed', model=model, **row)
            control.check()
            return output, detail
    except BaseException as caught:
        # If prototype repr/diagnostic creation raised a secondary error, retain the original.
        original = getattr(control, 'original_error', None)
        error = original if original is not None else caught
        try:
            report_exception(error, observer, 'render_exception', model=model,
                prototype_record=detail, prospective_geometry_prefix=getattr(control,'exception_prefix',[]),
                raw_return_pending=raw_pending, pending_output=output if raw_pending else None,
                pending_detail=detail if raw_pending else None,
                secondary_exception=caught if caught is not error else None)
        except BaseException as reporting_error:
            # Diagnostics and metadata allocation must never replace the primary.
            try:
                error.evaluation_reporting_failure = reporting_error
            except BaseException:
                pass
        if error is caught:
            raise
        raise error.with_traceback(getattr(control,'original_traceback',None))


def fit(teachers, observer=None, budget=None):
    models = []; records = []; calls = []; active = None; validation = None; certificates = None
    output = detail = None; raw_pending = False
    try:
        budget = budget if budget is not None else Budget()
        budget.check()
        valid, validation = validate_teachers(teachers)
        budget.check()
        emit(observer, 'teacher_validation', valid=valid, record=validation)
        if not valid:
            return (), validation
        certificates = teacher_necessities(teachers, observer, budget)
        if not all(row['complete'] for row in certificates):
            raise RuntimeError('incomplete necessary-condition certificate')
        if any(row['all_programs_necessarily_fail'] for row in certificates):
            record = dict(validation, teacher_necessity_certificates=certificates, model_returns=[],
                          evaluated_teacher_calls=0, symbolic_unexecuted_teacher_calls=len(PROGRAMS)*len(teachers),
                          symbolic_model_teacher_pairs=[[m,i] for m in range(len(PROGRAMS)) for i in range(len(teachers))],
                          retained_count=0, logical_domain_complete=True, proof_complete=True,
                          failure='teacher_output_necessity_impossible')
            emit(observer, 'teacher_fit_proven_empty', models=(), record=record)
            budget.check()
            return (), record
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
        record = dict(validation, teacher_necessity_certificates=certificates, model_returns=records,
                      symbolic_unexecuted_teacher_calls=0, evaluated_teacher_calls=len(PROGRAMS)*len(teachers),
                      retained_count=len(models), logical_domain_complete=True)
        if not models:
            record['failure'] = 'no_all_teacher_model'
        emit(observer, 'teacher_fit_completed', models=tuple(models), record=record)
        return tuple(models), record
    except BaseException as error:
        try:
            report_exception(error, observer, 'fit_exception', validation=validation,
                             teacher_necessity_certificates=certificates,
                             completed_model_returns=records, completed_teacher_returns=calls,
                             active_call=active, raw_return_pending=raw_pending,
                             pending_output=output if raw_pending else None,
                             pending_detail=detail if raw_pending else None)
        except BaseException as reporting_error:
            # Diagnostics and metadata allocation must never replace the primary.
            try:
                error.evaluation_reporting_failure = reporting_error
            except BaseException:
                pass
        raise

def predict(grid, models, observer=None, budget=None):
    rows = []; active = None; output = detail = None; raw_pending = False
    try:
        budget = budget if budget is not None else Budget()
        budget.check()
        if not valid_grid(grid):
            return None, {'failure': 'invalid_grid', 'returns': []}
        if not valid_models(models):
            return None, {'failure': 'invalid_retained_state', 'returns': []}
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
            # Diagnostics and metadata allocation must never replace the primary.
            try:
                error.evaluation_reporting_failure = reporting_error
            except BaseException:
                pass
        raise

@dataclass(frozen=True, init=False, slots=True)
class 合同物体出口教材:
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
                # Diagnostics and metadata allocation must never replace the primary.
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
