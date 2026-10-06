"""Reviewed observation support only; no official authority loader or full120 runner."""
import sys
sys.dont_write_bytecode=True
RUNTIME_ROOTS=()
CONTROL_SCRIPT=None

import argparse

from collections import Counter, deque

import dataclasses

import errno

import enum

import gzip

import hashlib

import importlib

import json

import os

import pathlib

import resource

import signal

import subprocess

import tempfile

import time

import traceback

import types

import zlib

PROGRAM_COUNT = 4

LIMITS = {'cpu_seconds': 10, 'address_space_MiB': 512, 'wall_seconds': 60}

VERSION = 'fresh-local73-candidate035-reconstructed-preflight-v1'

def safe_exception(error):
    result = {'type': type(error).__name__, 'module': type(error).__module__}
    try:
        result['message'] = str(error)
    except BaseException as secondary:
        result.update(message='<exception message unavailable>',
                      message_capture_failure=type(secondary).__name__)
    return result

def serial_key(value):
    if type(value) is tuple:
        return ['tuple', [serial_key(item) for item in value]]
    if value is None or type(value) in (str,int,float,bool):
        return [type(value).__name__, value]
    raise TypeError('unsupported typed dictionary key ' + type(value).__name__)

def serial(value):
    if isinstance(value, BaseException):
        return safe_exception(value)
    if isinstance(value, enum.Enum):
        return serial(value.value)
    if dataclasses.is_dataclass(value):
        return {field.name: serial(getattr(value, field.name))
                for field in dataclasses.fields(value)}
    if isinstance(value, dict):
        if all(type(key) is str for key in value):
            return {key: serial(item) for key, item in value.items()}
        return {'__arc2_typed_mapping__': [{'key': serial_key(key), 'value': serial(item)} for key,item in value.items()]}
    if isinstance(value, (list, tuple, deque)):
        return [serial(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [serial(item) for item in sorted(value, key=repr)]
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise TypeError('unserializable ' + type(value).__name__)

def encoded(value):
    return json.dumps(serial(value), ensure_ascii=False,
                      allow_nan=False, separators=(',', ':')).encode('utf-8')

def enforce_whole_child_budget(row,cpu_seconds,wall_seconds):
    cpu_exceeded=cpu_seconds>LIMITS['cpu_seconds']
    wall_exceeded=wall_seconds>LIMITS['wall_seconds']
    row.update(actual_child_process_cpu_seconds=cpu_seconds,parent_wall_seconds=wall_seconds,
               cpu_budget_exceeded=cpu_exceeded,whole_wall_budget_exceeded=wall_exceeded)
    if cpu_exceeded or wall_exceeded:
        row['completion_before_whole_child_budget_override']={k:row.get(k)for k in('completed','disposition','semantic_HOLD','all_exact','resource_failure')}
        row.update(completed=False,semantic_HOLD=False,all_exact=False,resource_failure=True,disposition='resource_incomplete')
    return row

def sha(path):
    digest = hashlib.sha256()
    with pathlib.Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

RAW_FIELDS = frozenset(('models','records','calls','active','validation','certificate','symbolic','witnesses','certificate_active','output','detail','raw_pending','rows','record','proposals','destinations','trace','launches','launch','p','d','color','seen','result','direct','teachers','pair','index','model_index','model','grid','program','fallback','context','exception_prefix','original','caught','error','certificates','certificate','raw_pending','rec','components','owner','cue_at','raw','normals','cue','crop','body','own','bodies','cues','foreground','maps','source','target','target_cells','transform','comparison','transformed','match','scan','sh','sw','lr','lc','odr','odc','factor','transforms','alt','ar','ac','nr','nc','cue_proposals','item','factors','valid','cells','ns','proposed','cid','conflicts','queue','color_counts','current_row','current_col','directions','seen','background','counts','modes','changes','violations','pending_output','pending_detail','raw_pending','audit','returns','fitted','expected','events','state','event','fit_replays'))

RAW_FIELDS = RAW_FIELDS | frozenset(('DIRECTIONS', 'GEOMETRY_CODES', 'PREFIX_NAMES', 'PROGRAMS', 'RESOURCE_ERRORS', '_', 'activated', 'activations', 'active', 'audit', 'b', 'bg', 'bodies', 'body', 'body_at', 'budget', 'c', 'calls', 'cell', 'cells', 'component', 'components', 'contact_policy', 'contiguous', 'coordinates', 'count', 'counts', 'd', 'dc', 'detail', 'diagnostic', 'direction', 'dr', 'emitted', 'exact', 'exit_cells', 'exits', 'expected', 'failures', 'fallback', 'fitted', 'foreground', 'frame', 'h', 'head', 'hit', 'inactive_policy', 'index', 'input_grid', 'k', 'key', 'l', 'locations', 'model', 'model_index', 'models', 'modes', 'next_states', 'normal', 'normal_tuple', 'normals', 'on_face', 'outgoing', 'output', 'owned', 'p', 'paint', 'pair', 'palette', 'payload', 'pending', 'point', 'port', 'preserved', 'primary', 'r', 'raw_pending', 'reason', 'record', 'records', 'result', 'revisits', 'role', 'roles', 'row', 'rows', 'secondary', 'source_cells', 'source_directions', 'state', 'states', 'successor', 't', 'tail', 'tb', 'trial', 'trials', 'v', 'valid', 'valid_grid', 'validation', 'value', 'view', 'visited', 'w', 'x', 'y', 'モデル群', '不足理由', '教師数', '異入力数'))

HELPER_TRAVERSAL_FIELDS = frozenset(('colour','first','q','stack','unseen'))

RAW_FIELDS = RAW_FIELDS | HELPER_TRAVERSAL_FIELDS

def capture_raw_exception(error):
    """Prospective only: capture traceback locals even when the frozen reporter fails entirely.

    Includes completed model/teacher/witness buffers and pending raw return locals.
    Unsupported opaque locals are named explicitly rather than repr'd or silently claimed.
    """
    frames=[]; tb=error.__traceback__
    while tb is not None:
        frame=tb.tb_frame; locals_out={}; unavailable={}; local_types={}; item_types={}
        filename=pathlib.Path(frame.f_code.co_filename).resolve()
        # Capture selected runtime data; record every intentional omission explicitly.
        runtime_frame=(filename==pathlib.Path(__file__).resolve()
                       or any(root in filename.parents for root in RUNTIME_ROOTS))
        control_transport_frame=(filename==CONTROL_SCRIPT and frame.f_code.co_name=='traced')
        selected_names=RAW_FIELDS if runtime_frame else ('raw_pending','_name') if control_transport_frame else ()
        for name in selected_names:
            if name not in frame.f_locals: continue
            value = frame.f_locals[name]
            local_types[name] = type(value).__module__ + '.' + type(value).__name__
            if type(value) in (list,tuple,set,frozenset,deque):
                item_types[name] = sorted({type(item).__module__ + '.' + type(item).__name__ for item in value})
            try: locals_out[name]=serial(value)
            except BaseException as secondary: unavailable[name]=safe_exception(secondary)
        frames.append({'source':frame.f_code.co_filename,'function':frame.f_code.co_name,
                       'line':tb.tb_lineno,'locals':locals_out,'unserializable_locals':unavailable,
                       'local_python_types':local_types,'local_item_python_types':item_types,
                       'omitted_runtime_local_names':sorted(set(frame.f_locals)-set(selected_names)) if runtime_frame else [],
                       'runtime_omission_reason':'names outside the fixed data-prefix policy; callable, observer, budget and frame objects are not claimed as captured state',
                       'locals_capture_scope':'frozen_runtime_or_transport'if runtime_frame else'control_transport_pending_return_only'if control_transport_frame else'nonruntime_location_only',
                       'omitted_nonruntime_local_names':[]if runtime_frame else sorted(set(frame.f_locals)-set(selected_names))})
        tb=tb.tb_next
    return {'scope':'new prospective traceback capture, never historical recovery',
            'primary_exception':safe_exception(error),'frames':frames,
            'reporting_failure':safe_exception(error.evaluation_reporting_failure) if getattr(error,'evaluation_reporting_failure',None) is not None else None,
            'context':capture_raw_exception(error.__context__) if error.__context__ is not None and error.__context__ is not error else None,
            'semantic_HOLD':False,'resource_failure':isinstance(error,(MemoryError,RecursionError,TimeoutError))}

def write(path, value):
    """Durably replace a whole record; a failed write never creates a completion."""
    path = pathlib.Path(path)
    data = encoded(value) + b'\n'
    if path.suffix == '.gz':
        data = gzip.compress(data, compresslevel=1, mtime=0)
    temporary = path.with_name(path.name + '.pending-' + str(os.getpid()))
    with temporary.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)

class Journal:
    """One fsynced gzip member per event, with an explicit pending event suffix."""
    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.file = self.path.open('xb', buffering=0)
        self.counts = Counter()
        self.pending = []
        self.failure = None
        self.context = {'audit_phase': 'load'}
        self.sequence = 0

    def set_context(self, phase, **values):
        self.context = {'audit_phase': phase, **values}

    def __call__(self, event):
        event = {**event, **self.context, 'audit_sequence': self.sequence}
        self.pending.append(event)
        if self.failure is not None:
            raise self.failure
        try:
            data = gzip.compress(encoded(event) + b'\n', compresslevel=1, mtime=0)
            view = memoryview(data)
            while view:
                count = self.file.write(view)
                if not count:
                    raise OSError(errno.EIO, 'journal short write')
                view = view[count:]
            os.fsync(self.file.fileno())
        except BaseException as error:
            self.failure = error
            raise
        self.pending.pop(0)
        self.sequence += 1
        self.counts[event['kind']] += 1

    def close(self):
        try:
            os.fsync(self.file.fileno())
        finally:
            self.file.close()

def install_call_observers(module, journal):
    """Observe exact parse/execute/render returns without substituting any value."""
    sequence = 0
    def wrap(owner, name, operation):
        original = getattr(owner, name)
        def observed(*args, **kwargs):
            nonlocal sequence
            call_id = sequence; sequence += 1
            input_grid = args[0]
            journal({'kind': 'core_' + operation + '_start', 'call_id': call_id,
                     'input': input_grid, 'positional_context': args[1:3] if operation=='execute' else args[1:2] if operation=='render' else ()})
            raw_pending = original(*args, **kwargs)
            journal({'kind': 'core_' + operation + '_return', 'call_id': call_id,
                     'raw_output': raw_pending[0], 'raw_detail': raw_pending[1]})
            return raw_pending
        setattr(owner, name, observed)
    wrap(module.core, 'parse', 'parse')
    wrap(module.core, 'execute', 'execute')
    wrap(module, 'render', 'render')

def validate_completion(detail):
    if type(detail) is not dict or detail.get('version') != VERSION:
        raise ValueError('invalid completion object/version')
    for key in ('completed', 'semantic_HOLD', 'resource_failure'):
        if type(detail.get(key)) is not bool:
            raise ValueError('invalid completion field: ' + key)
    if detail.get('disposition') not in ('FIT', 'proven_empty_fit', 'logical_HOLD', 'resource_incomplete', 'exception'):
        raise ValueError('invalid completion disposition')
    if detail['completed']:
        if detail['disposition'] in ('exception', 'resource_incomplete') or detail['resource_failure']:
            raise ValueError('failure masquerades as completion')
        if not detail.get('runtime_unchanged') or detail.get('trace_incomplete') or detail.get('secondary_errors'):
            raise ValueError('incomplete evidence masquerades as completion')
        if type(detail.get('teacher_count')) is not int or type(detail.get('teacher_returns')) is not list:
            raise ValueError('missing teacher completion records')
        if [row.get('teacher_index') for row in detail['teacher_returns']] != list(range(detail['teacher_count'])):
            raise ValueError('missing or reordered teacher return')
        if not isinstance(detail.get('fit'), dict) or not isinstance(detail.get('models'), list):
            raise ValueError('missing fit/model completion record')
        if type(detail.get('all_exact')) is not bool or type(detail.get('proof_rejected')) is not bool:
            raise ValueError('missing exact/proof status')
        for key in ('fit_parse_calls', 'evaluated_teacher_calls', 'symbolic_unexecuted_teacher_calls'):
            if type(detail.get(key)) is not int or detail[key] < 0:
                raise ValueError('missing actual/symbolic call count: ' + key)
    elif detail['semantic_HOLD']:
        raise ValueError('incomplete run cannot be semantic HOLD')

def read_completion(path, timed_out, returncode, parent_wall_seconds=None):
    path = pathlib.Path(path)
    exceeded = parent_wall_seconds is not None and parent_wall_seconds > LIMITS['wall_seconds']
    resource_incomplete = bool(timed_out or returncode < 0 or exceeded)
    base = {'completed': False, 'disposition': 'resource_incomplete' if resource_incomplete else 'exception',
            'semantic_HOLD': False, 'all_exact': False, 'resource_failure': resource_incomplete,
            'parent_wall_budget_exceeded': exceeded}
    record_path = path
    if not path.exists():
        fallback = path.with_name(path.name + '.failure.json')
        if fallback.exists():
            record_path = fallback
        else:
            return {**base, 'completion_record_missing': True}
    try:
        with (gzip.open(record_path, 'rt') if record_path.suffix == '.gz' else record_path.open()) as stream:
            detail = json.load(stream)
        validate_completion(detail)
        row = {key: value for key, value in detail.items()
               if key not in ('fit', 'teacher_returns', 'completed_teacher_returns',
                              'completed_fit_record', 'evaluation_diagnostic', 'pending_event_suffix', 'raw_exception_evidence')}
        row['completion_record_sha256'] = sha(record_path)
        row['completion_record_bytes'] = record_path.stat().st_size
        row['pending_event_suffix_count'] = len(detail.get('pending_event_suffix', []))
        if timed_out or returncode != 0 or exceeded or record_path != path:
            row['completion_record_before_exit_override'] = {
                key: row.get(key) for key in ('completed', 'disposition', 'semantic_HOLD', 'all_exact', 'resource_failure')}
            resource_incomplete |= bool(row.get('resource_failure'))
            row.update(completed=False, all_exact=False, semantic_HOLD=False,
                       disposition='resource_incomplete' if resource_incomplete else 'exception',
                       resource_failure=resource_incomplete)
        row['parent_wall_budget_exceeded'] = exceeded
        return row
    except (OSError, EOFError, ValueError, UnicodeError, TypeError, KeyError) as error:
        return {**base, 'completion_record_unreadable': True,
                'completion_read_exception': type(error).__name__,
                'completion_read_message': safe_exception(error)['message'],
                'completion_record_sha256': sha(record_path), 'completion_record_bytes': record_path.stat().st_size}

def compact_pairs(ordinals, teacher_count):
    """Lossless model-major matrix: ordinal = model_index * teacher_count + teacher_index."""
    ordered = sorted(set(ordinals))
    ranges = []
    for value in ordered:
        if ranges and ranges[-1][1] == value:
            ranges[-1][1] += 1
        else:
            ranges.append([value, value + 1])
    return {'encoding': 'model-major-half-open-ordinal-ranges-v1',
            'model_count': PROGRAM_COUNT, 'teacher_count': teacher_count,
            'count': len(ordered), 'ranges': ranges}

def read_journal(path, teacher_count):
    path = pathlib.Path(path)
    counts, operation_counts = Counter(), Counter()
    started, completed, models, predictions, prediction_starts, zero_predictions = [], [], [], [], [], []
    pending_core, active = {}, None
    proof = None
    committed_compressed = committed_decoded = events = 0
    parse_completed, fit_complete = [], False
    conservation_witnesses, symbolic_calls = [], []
    necessity_records=[]
    stream_error = None
    if path.exists():
        with path.open('rb') as source:
            buffer = b''
            exhausted = False
            while not exhausted or buffer:
                decompressor = zlib.decompressobj(31)
                decoded = bytearray()
                member_compressed = 0
                try:
                    while not decompressor.eof:
                        if not buffer:
                            buffer = source.read(65536)
                            if not buffer:
                                exhausted = True
                                break
                        chunk = decompressor.decompress(buffer)
                        decoded.extend(chunk)
                        used = len(buffer) - len(decompressor.unused_data)
                        member_compressed += used
                        buffer = decompressor.unused_data
                    if not decompressor.eof:
                        break
                    entries = [json.loads(line) for line in decoded.splitlines()]
                    if len(entries) != 1 or type(entries[0]) is not dict or type(entries[0].get('kind')) is not str:
                        raise ValueError('journal member must contain exactly one event')
                    event = entries[0]
                    if event.get('audit_sequence') != events:
                        raise ValueError('journal sequence gap or duplicate')
                    kind, phase = event['kind'], event.get('audit_phase')
                    if kind in ('model_teacher_start', 'model_teacher_return'):
                        model, teacher = event['model_index'], event['teacher_index']
                        if type(model) is not int or type(teacher) is not int or not (0 <= model < PROGRAM_COUNT and 0 <= teacher < teacher_count):
                            raise ValueError('out-of-domain model/teacher reference')
                    if kind in ('teacher_prediction_start', 'teacher_prediction_completed'):
                        if type(event.get('teacher_index')) is not int or not 0 <= event['teacher_index'] < teacher_count:
                            raise ValueError('out-of-domain teacher reference')
                    if kind.startswith('core_'):
                        operation = kind.split('_')[1]
                        key = (operation, event['call_id'])
                        operation_counts[(phase, kind)] += 1
                        if kind.endswith('_start'):
                            if key in pending_core:
                                raise ValueError('duplicate core call start')
                            pending_core[key] = event
                        elif kind.endswith('_return'):
                            if key not in pending_core:
                                raise ValueError('core return without start')
                            del pending_core[key]
                    if kind == 'model_teacher_start':
                        active = event
                        started.append(event['model_index'] * teacher_count + event['teacher_index'])
                    elif kind == 'model_teacher_return':
                        completed.append(event['model_index'] * teacher_count + event['teacher_index'])
                        active = None
                    elif kind == 'model_completed':
                        models.append(event['record']['model_index'])
                    elif kind == 'parse_completed':
                        parse_completed.append(event['model'])
                    elif kind == 'teacher_fit_completed':
                        fit_complete = True
                    elif kind == 'teacher_prediction_start':
                        prediction_starts.append(event['teacher_index'])
                    elif kind == 'teacher_prediction_completed':
                        predictions.append(event['teacher_index'])
                        if event['retained_model_count'] == 0:
                            zero_predictions.append(event['teacher_index'])
                    counts[kind] += 1
                    events += 1
                    committed_compressed += member_compressed
                    committed_decoded += len(decoded)
                except (zlib.error, ValueError, UnicodeError, KeyError, TypeError) as error:
                    stream_error = safe_exception(error)
                    break
    universe = set(range(PROGRAM_COUNT * teacher_count))
    started_set, completed_set = set(started), set(completed)
    symbolic = False
    row = {
        'journal_sha256': sha(path) if path.exists() else None,
        'complete_event_prefix_count': events, 'event_prefix_counts': dict(counts),
        'completed_event_bytes': committed_decoded,
        'complete_compressed_event_prefix_bytes': committed_compressed,
        'incomplete_compressed_suffix_bytes': path.stat().st_size - committed_compressed if path.exists() else 0,
        'journal_parse_failure': stream_error, 'journal_missing': not path.exists(),
        'planned_model_teacher_pairs': compact_pairs(universe, teacher_count),
        'started_model_teacher_pairs': compact_pairs(started_set, teacher_count),
        'completed_model_teacher_pairs': compact_pairs(completed_set, teacher_count),
        'unexecuted_model_teacher_pairs': compact_pairs(universe - started_set - completed_set, teacher_count),
        'incomplete_model_teacher_pairs': compact_pairs(started_set - completed_set, teacher_count),
        'unexecuted_or_incomplete_model_teacher_pairs': compact_pairs(universe - completed_set, teacher_count),
        'symbolic_unexecuted_model_teacher_pairs': compact_pairs(universe if symbolic else (), teacher_count),
        'actual_started_program_teacher_calls': len(started),
        'actual_completed_program_teacher_calls': len(completed),
        'completed_model_prefix_count': len(models),
        'completed_model_indices': models, 'completed_conservation_teacher_indices': conservation_witnesses,
        'symbolic_call_ordinals': symbolic_calls,
        'completed_parse_count': len(parse_completed), 'active_fit_call': active,
        'pending_actual_core_calls': list(pending_core.values()),
        'completed_fit_teacher_indices': [teacher for teacher in range(teacher_count)
                                         if all(model * teacher_count + teacher in completed_set for model in range(PROGRAM_COUNT))],
        'symbolically_completed_fit_teacher_indices': list(range(teacher_count)) if symbolic else [],
        'symbolic_fit_proof': proof, 'symbolic_fit_proof_valid':symbolic, 'teacher_fit_completed_event': fit_complete,
        'started_prediction_teacher_indices': prediction_starts,
        'completed_prediction_teacher_indices': predictions,
        'zero_model_teacher_prediction_indices': zero_predictions,
        'duplicate_started_model_teacher_pairs': len(started) != len(started_set),
        'duplicate_completed_model_teacher_pairs': len(completed) != len(completed_set),
        'all_completed_references_resolvable': stream_error is None and completed_set.issubset(started_set),
    }
    for label, phase, operation in (('fit_parse', 'fit', 'parse'), ('fit_render', 'fit', 'render'),
                                    ('prediction_parse', 'prediction', 'parse'), ('prediction_render', 'prediction', 'render'),
                                    ('fit_execute', 'fit', 'execute'), ('prediction_execute', 'prediction', 'execute')):
        for status, ending in (('started', 'start'), ('completed', 'return')):
            row['actual_' + status + '_' + label + '_calls'] = operation_counts[(phase, 'core_' + operation + '_' + ending)]
    return row
