"""Strict target-free marker-channel endpoints; frozen geometry, complete models and conservation certificates."""
import sys
import time
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from . import 標識水路候補 as core

PROGRAMS = tuple((program,) for program in core.PROGRAMS)
INVARIANT_PROOF_SHA256 = '57d4f73fcf6915f3945a78883b559d77081aa698dfc051b6187b8b0cc5e01774'

def valid_grid(grid):
    return (type(grid) is list and 1 <= len(grid) <= 30 and type(grid[0]) is list
            and 1 <= len(grid[0]) <= 30 and all(type(row) is list and len(row) == len(grid[0])
            and all(type(v) is int and 0 <= v <= 9 for v in row) for row in grid))
RESOURCE_ERRORS = (MemoryError, RecursionError, TimeoutError)
PREFIX_NAMES = frozenset(('BBox', 'Cell', 'ComponentRecord', 'DELTAS', 'DIAGONAL_DIRECTIONS', 'DIRECTIONS', 'Grid', 'GridKey', 'MODEL_KEYS', 'ORTHOGONAL_DELTAS', 'ORTHOGONAL_DIRECTIONS', 'PHASES', 'PROGRAMS', 'RESOURCE_ERRORS', '_', '_col', '_color', '_placed', '_policy', '_row', '_step', 'a', 'accepted', 'active', 'active_code', 'active_side', 'after', 'assigned_colored_holes', 'assignment', 'b', 'background', 'background_cells', 'background_color', 'barriers', 'bbox', 'bbox_area', 'bbox_shape', 'beam_event_count', 'before_row', 'best', 'best_cell', 'bg', 'body', 'body_cells', 'body_height', 'body_width', 'border', 'border_colors', 'border_values', 'bottom', 'bounds', 'c', 'candidate', 'candidates', 'cell', 'cells', 'center', 'changed', 'changed_cols', 'code', 'col', 'col0', 'col1', 'col_delta', 'col_max', 'col_min', 'color', 'color_counts', 'colored', 'colored_bbox', 'colored_centroids', 'colored_col0', 'colored_col1', 'colored_hole', 'colored_holes', 'colored_index', 'colored_region', 'colored_regions', 'colored_row0', 'colored_row1', 'colored_shape', 'colors', 'colour', 'colours', 'cols', 'column', 'columns', 'component', 'component_area', 'component_height', 'component_records', 'component_width', 'components', 'conflict', 'conflicts', 'contacts', 'control', 'control_height', 'costs', 'count', 'counts', 'crop', 'cs', 'current_col', 'current_row', 'cw', 'd', 'dc', 'deltas', 'density', 'destinations', 'detail', 'diagnostic', 'direction', 'directions', 'distance', 'dr', 'e', 'end', 'entry', 'erased', 'errors', 'evidence', 'expected', 'expected_changed', 'expected_record', 'expected_shape', 'exterior', 'failure', 'failures', 'fg', 'fill_length', 'final_counts', 'first', 'first_seen', 'fits', 'fitted', 'flank_cells', 'flank_values', 'footprint', 'foreground', 'foreign', 'front', 'g', 'gaps', 'grid', 'grouped', 'groups', 'guarded', 'guide', 'guide_candidates', 'guide_color', 'h', 'height', 'hi', 'hit_col', 'hit_color', 'hit_colors', 'hit_row', 'hits', 'hole', 'hole_cells', 'hole_color', 'hole_count', 'hole_map', 'holes', 'i', 'ih', 'include_diagonal', 'index', 'initial', 'initial_state', 'initial_states', 'is_solid_rectangle', 'item', 'key', 'kind', 'lane', 'lanes', 'launch', 'launches', 'leaders', 'left', 'left_active', 'left_code', 'legend', 'limit', 'line', 'line_index', 'line_records', 'lo', 'local', 'm', 'mapping_records', 'marker', 'marker_cells', 'marker_color', 'marker_colors', 'marker_column', 'marker_columns', 'marker_components', 'mask', 'max_col', 'max_row', 'maximum', 'merge', 'min_col', 'min_row', 'model', 'models', 'modes', 'n', 'nc', 'neighbor', 'next_cell', 'next_col', 'next_row', 'non_background_values', 'normalized', 'normalized_shape', 'nr', 'o', 'obj', 'obstacle_cells', 'obstacles', 'offset', 'open_sides', 'original_counts', 'other_col', 'out', 'output', 'output_candidates', 'outputs', 'owned', 'owner', 'p', 'paint', 'paint_col', 'paint_row', 'pair', 'pairs', 'palette', 'panel', 'panel_records', 'panel_start', 'panel_width', 'panels', 'parse_record', 'parsed', 'passthrough', 'payload_color', 'payload_colors', 'period_length', 'period_sample', 'phase', 'phase_semantics', 'piece', 'piece_col', 'piece_index', 'piece_placements', 'piece_row', 'pieces', 'placed', 'placements', 'placements_by_cell', 'plain_regions', 'point', 'policy', 'preserved', 'program', 'proposal', 'proposals', 'proposed', 'prototype', 'prototypes', 'q', 'queue', 'r', 'rail', 'raw', 'rays', 'reason', 'rec', 'recolored_cells', 'recolored_components', 'record', 'record_color', 'records', 'region', 'regions', 'rel_col', 'rel_row', 'remaining', 'removed_cells', 'removed_components', 'required_rows', 'result', 'results', 'rh', 'right', 'right_active', 'right_code', 'role', 'roles', 'row', 'row0', 'row1', 'row_delta', 'row_max', 'row_min', 'row_records', 'rows', 'run', 'runs', 's', 'sb', 'sc', 'second', 'seed', 'seed_cells', 'seed_col', 'seed_color', 'seed_colour', 'seed_height', 'seed_index', 'seed_records', 'seed_row', 'seed_width', 'seeds', 'seen', 'seen_states', 'selected', 'self', 'separator', 'separator_col', 'separator_color', 'separator_record', 'sequence', 'shape', 'side', 'sides', 'size', 'sorted_cells', 'source', 'source_background', 'source_cells', 'source_col', 'source_height', 'source_piece_count', 'source_row', 'source_width', 'special', 'split_mode', 'split_specs', 'squares', 'sr', 'sright', 'stack', 'start', 'state', 'state_limit', 'states', 'stats', 'suffix', 't', 'target_color', 'target_row', 'teachers', 'template', 'template_background', 'template_bbox', 'template_cells', 'template_centroids', 'template_col', 'template_col0', 'template_col1', 'template_colors', 'template_height', 'template_hole', 'template_holes', 'template_index', 'template_region', 'template_row', 'template_row0', 'template_row1', 'template_shape', 'template_width', 'terminal', 'terminals', 'termination', 'terrain', 'touches_bbox', 'touches_border', 'trace', 'traces', 'travel', 'trial', 'trials', 'turn', 'turn_by_color', 'turn_by_colour', 'turn_records', 'turns', 'unique', 'unseen', 'used', 'used_mask', 'v', 'valid', 'vals', 'value', 'values', 'w', 'wall', 'wall_color', 'width', 'word', 'x', 'y', '教師群', '格子'))
HELPER_FILES = frozenset((core.__file__, core.valid_grid.__code__.co_filename, core.line_cells.__code__.co_filename, core.merge_proposals.__code__.co_filename, core.body_components.__code__.co_filename, core.add.__code__.co_filename, core.within.__code__.co_filename))

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

def safe_inner_diagnostic(error):
    try:
        return getattr(error, 'evaluation_diagnostic', None)
    except BaseException:
        return None

def report_exception(error, observer, stage, **context):
    # Attach the original and complete wrapper prefixes BEFORE optional diagnostics or observers.
    fallback = {'kind': stage, 'exception': type(error).__name__, 'semantic_HOLD': False,
                'resource_failure': isinstance(error, RESOURCE_ERRORS),
                'original_exception': error, 'inner_diagnostic': safe_inner_diagnostic(error),
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
        self.active_location = None
    def check(self):
        if time.monotonic() > self.deadline:
            raise TimeoutError('whole call wall budget exhausted')
    def trace(self, frame, event, arg):
        if frame.f_code.co_filename not in HELPER_FILES:
            return None
        self.active_location = {'source': frame.f_code.co_filename, 'function': frame.f_code.co_name, 'line': frame.f_lineno}
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
        self.active_location = None
        sys.settrace(self.trace)
        return self
    def __exit__(self, *unused):
        sys.settrace(self.previous)


def valid_model(model):
    return type(model) is tuple and len(model) == 1 and type(model[0]) is str and model in PROGRAMS

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

def teacher_row(index, pair, output, detail):
    return {'teacher_index': index, 'output': output, 'record': detail,
            'exact': output is not None and detail.get('status') == 'complete' and output == pair['output']}

def render_row(output, detail):
    return {'output': output, 'record': detail}


def state_observer(observer):
    if observer is None:
        return None
    def observe(event):
        frame = sys._getframe(1)
        while frame is not None and not (frame.f_code.co_filename == core.__file__ and frame.f_code.co_name == 'render'):
            frame = frame.f_back
        location = None if frame is None else {'source': frame.f_code.co_filename, 'function': frame.f_code.co_name, 'line': frame.f_lineno}
        observer(dict(event, source_location=location, prefix_kind='completed_observation_not_resumable_state'))
    return observe

def color_counts(grid):
    counts = Counter(v for row in grid for v in row)
    return [counts[color] for color in range(10)]

def conservation_certificate(teachers, witnesses, active, observer, budget):
    # Caller owns both buffers, so later interruption preserves all completed witnesses.
    for index, pair in enumerate(teachers):
        active.clear()
        active.update(teacher_index=index, input=pair['input'], target=pair['output'], phase='before_counts')
        budget.check()
        inp, target = pair['input'], pair['output']
        active['phase'] = 'input_counts'
        ic = color_counts(inp)
        active['phase'] = 'target_counts'
        oc = color_counts(target)
        active['phase'] = 'complete_witness_construction'
        ishape, oshape = [len(inp),len(inp[0])], [len(target),len(target[0])]
        witnesses.append({'teacher_index':index, 'input':inp, 'target':target,
                          'input_shape':ishape, 'target_shape':oshape,
                          'input_color_counts_0_to_9':ic, 'target_color_counts_0_to_9':oc,
                          'shape_equal':ishape == oshape, 'counts_equal':ic == oc,
                          'differing_colors':[{'color':c,'input_count':ic[c],'target_count':oc[c]} for c in range(10) if ic[c] != oc[c]]})
        active.clear()
        emit(observer, 'conservation_teacher_witness', witness=witnesses[-1])
    return {'proof_sha256':INVARIANT_PROOF_SHA256, 'necessary_only':True,
            'successful_render_invariant':'same canvas shape and complete 10-color counts',
            'witnesses':witnesses,
            'violating_teacher_indices':[w['teacher_index'] for w in witnesses if not w['shape_equal'] or not w['counts_equal']]}


def render(grid, model, observer=None, budget=None, state_limit=None):
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
            output, detail = core.render(grid, model[0], state_observer(observer), state_limit)
            raw_pending = True
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
                active_source_location=getattr(control,'active_location',None),
                raw_return_pending=raw_pending, pending_output=output if raw_pending else None,
                pending_detail=detail if raw_pending else None,
                secondary_exception=caught if caught is not error else None)
        except BaseException:
            pass
        if error is caught:
            raise
        raise error.with_traceback(getattr(control,'original_traceback',None))


def fit(teachers, observer=None, budget=None):
    models = []; records = []; calls = []; active = None; validation = None; certificate = None; symbolic = []; witnesses = []; certificate_active = {}
    output = detail = None; raw_pending = False
    try:
        budget = budget if budget is not None else Budget()
        budget.check()
        valid, validation = validate_teachers(teachers)
        budget.check()
        emit(observer, 'teacher_validation', valid=valid, record=validation)
        if not valid:
            return (), validation
        certificate = conservation_certificate(teachers, witnesses, certificate_active, observer, budget)
        emit(observer, 'conservation_certificate', certificate=certificate)
        if certificate['violating_teacher_indices']:
            for model_index, model in enumerate(PROGRAMS):
                for index in range(len(teachers)):
                    budget.check()
                    row = {'model_index': model_index, 'model': model, 'teacher_index': index,
                           'execution': 'symbolically_unexecuted', 'globally_refuted': True,
                           'per_call_refuted': index in certificate['violating_teacher_indices'],
                           'violation_witness_indices': certificate['violating_teacher_indices'],
                           'proof_sha256': INVARIANT_PROOF_SHA256}
                    symbolic.append(row)
                    emit(observer, 'symbolic_teacher_call', **row)
            record = dict(validation, failure='teacher_conservation_impossibility', proof_rejected=True,
                          conservation_certificate=certificate, symbolic_teacher_calls=symbolic,
                          model_returns=[], evaluated_teacher_calls=0,
                          symbolic_unexecuted_teacher_calls=len(symbolic),
                          symbolically_completed_fit_teacher_indices=list(range(len(teachers))),
                          retained_count=0, logical_domain_complete=True)
            budget.check()
            emit(observer, 'teacher_fit_completed', models=(), record=record)
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
        record = dict(validation, model_returns=records, evaluated_teacher_calls=len(PROGRAMS)*len(teachers),
                      retained_count=len(models), logical_domain_complete=True, proof_rejected=False,
                      conservation_certificate=certificate, symbolic_teacher_calls=[],
                      symbolic_unexecuted_teacher_calls=0, symbolically_completed_fit_teacher_indices=[])
        if not models:
            record['failure'] = 'no_all_teacher_model'
        emit(observer, 'teacher_fit_completed', models=tuple(models), record=record)
        return tuple(models), record
    except BaseException as error:
        try:
            report_exception(error, observer, 'fit_exception', validation=validation,
                             conservation_certificate=certificate, completed_symbolic_teacher_calls=symbolic,
                             completed_conservation_witnesses=witnesses, active_conservation_teacher=certificate_active,
                             completed_model_returns=records, completed_teacher_returns=calls,
                             active_call=active, raw_return_pending=raw_pending,
                             pending_output=output if raw_pending else None,
                             pending_detail=detail if raw_pending else None)
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
        reason = ('no_retained_models' if not rows else 'retained_model_failed' if any(row['output'] is None or row['detail'].get('status') != 'complete' for row in rows)
                  else 'retained_models_disagree' if any(row['output'] != rows[0]['output'] for row in rows) else None)
        budget.check()
        record = {'returns': rows}
        if reason:
            record['failure'] = reason
        output = None if reason else deepcopy(rows[0]['output'])
        emit(observer, 'retained_consensus', output=output, record=record)
        return output, record
    except BaseException as error:
        try:
            report_exception(error, observer, 'prediction_exception', completed_model_returns=rows,
                             active_model=active, raw_return_pending=raw_pending,
                             pending_output=output if raw_pending else None,
                             pending_detail=detail if raw_pending else None)
        except BaseException:
            pass
        raise

@dataclass(frozen=True, init=False, slots=True)
class 標識水路教材:
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
            except BaseException:
                pass
            raise
    def 候補(self, grid, policy, 観測=None):
        return predict(grid, self.モデル群, 観測)
    def 記録(self):
        return {'保持候補': list(self.モデル群), '保持候補数': len(self.モデル群),
                '教師数': self.教師数, '異入力数': self.異入力数,
                '教師fit最小数': 2, '不足理由': self.不足理由}
