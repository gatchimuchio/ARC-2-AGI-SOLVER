"""Pinned observation support; no official authority loader or full120 runner."""
import sys
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
import ast
S=pathlib.Path(__file__).resolve().parents[2]
F=pathlib.Path(__file__).resolve().parent
DEPLOYMENT_PIN_PATH=F/'dependency-pins.json.gz'
REPOSITORY_ROOT=S
ADMIN_CHECKS=[]
def readpins():return json.loads(gzip.decompress(DEPLOYMENT_PIN_PATH.read_bytes()))
def pincheck(name,value):
    if not value:raise AssertionError(name)
    ADMIN_CHECKS.append(name)
def verify_lock(root=S,expected_sha256=None):
    if expected_sha256 is not None:pincheck('deployment-pin-identity',sha(DEPLOYMENT_PIN_PATH)==expected_sha256)
    pins=readpins()
    for name,digest in pins['payload_pins'].items():pincheck('payload:'+name,sha(S/name)==digest)
    for name,digest in pins['base_source_pins'].items():pincheck('base:'+name,sha(REPOSITORY_ROOT/name)==digest)
    nodes={n.name:ast.dump(n,include_attributes=False)for n in ast.parse((REPOSITORY_ROOT/'接続/ARC2/HDS接続.py').read_bytes()).body if isinstance(n,ast.FunctionDef)and n.name in pins['native_bridge_ast']}
    pincheck('native-helper-ASTs',nodes==pins['native_bridge_ast'])
    return pins
PROGRAM_COUNT = 23040
LIMITS = {'cpu_seconds': 10, 'address_space_MiB': 512, 'wall_seconds': 60}
VERSION = 'fresh-local70-candidate034-necessity-proof-preflight-v1'
PLAIN_EVENT_KINDS=frozenset(('core_parse_start','core_parse_return','whole_parse_start','whole_parse_return','apply_start','apply_return','action_start','action_return','proof_teacher_parsed','teacher_validation','teacher_parsed','teacher_fit_proven_empty','return_pool_entry','model_teacher_return','model_completed','teacher_prediction_start','teacher_prediction_completed','retained_model_return','retained_consensus','teacher_necessity_witness','model_necessity_certificate','symbolic_model_teacher_slot','necessity_fit_completed','necessity_exact_fallback_completed'))
PLAIN_SCALARS=(str,int,float,bool,type(None))
RAW_FIELDS = frozenset(('models','records','calls','active','validation','certificate','symbolic','witnesses','certificate_active','output','detail','raw_pending','rows','record','proposals','destinations','trace','launches','launch','p','d','color','seen','result','direct','teachers','pair','index','model_index','model','grid','program','fallback','context','exception_prefix','original','caught','error','teacher_index','identity','call_id','scope','spec','parsed','completed','retained','pool','pending','raw_role','raw_reason','exact','exacts','raw_pending','role','reason','mask','cells','represented','expected','reconstructed','pre_parsed','witness_records','certificates','actual_rows','symbolic_slots','certificate_rows','pending_certificate','fallback_models','fallback_record','fallback_started','fallback_returned','previous_diagnostic','slot','symbolic_committed','witnesses','certificate','phase'))

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

def plain_json(value):
    kind=type(value)
    if kind in PLAIN_SCALARS:return True
    if kind in(list,tuple):return all(type(item)in PLAIN_SCALARS or plain_json(item)for item in value)
    if kind is dict:return all(type(key)is str and(type(item)in PLAIN_SCALARS or plain_json(item))for key,item in value.items())
    return False

def encoded_journal(event):
    if type(event)is dict and event.get('kind')in PLAIN_EVENT_KINDS and plain_json(event):
        try:
            return json.dumps(event,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')
        except (TypeError,ValueError):
            pass
    return encoded(event)

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

def capture_raw_exception(error):
    """Prospective only: capture traceback locals even when the frozen reporter fails entirely.

    Includes completed model/teacher/witness buffers and pending raw return locals.
    Unsupported opaque locals are named explicitly rather than repr'd or silently claimed.
    """
    frames=[]; tb=error.__traceback__
    while tb is not None:
        frame=tb.tb_frame; locals_out={}; unavailable={}
        for name in RAW_FIELDS:
            if name not in frame.f_locals: continue
            try:
                value=frame.f_locals[name]
                locals_out[name]=serial(value.pool if name=='pool' and hasattr(value,'pool') else value)
            except BaseException as secondary: unavailable[name]=safe_exception(secondary)
        frames.append({'source':frame.f_code.co_filename,'function':frame.f_code.co_name,
                       'line':tb.tb_lineno,'locals':locals_out,'unserializable_locals':unavailable})
        tb=tb.tb_next
    return {'scope':'new prospective traceback capture, never historical recovery',
            'primary_exception':safe_exception(error),'frames':frames,
            'semantic_HOLD':False,'resource_failure':isinstance(error,(MemoryError,RecursionError,TimeoutError))}

def encoded_record(value):
    """Lossless ordinary-record path; exact non-JSON types use the old encoder."""
    try:
        ordinary = plain_json(value)
    except (RecursionError, MemoryError):
        ordinary = False
    if ordinary:
        try:
            return json.dumps(value, ensure_ascii=False, allow_nan=False,
                              separators=(',', ':')).encode('utf-8')
        except (TypeError, ValueError):
            pass
    return encoded(value)


def write(path, value):
    """Durably replace a whole record; a failed write never creates a completion."""
    path = pathlib.Path(path)
    data = encoded_record(value) + b'\n'
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

def vmhwm(pid='self'):
    try:
        for line in pathlib.Path('/proc/' + str(pid) + '/status').read_text().splitlines():
            if line.startswith('VmHWM:'):
                return int(line.split()[1])
    except (OSError, ValueError):
        pass
    return None

def is_resource_error(error, core=None):
    return (isinstance(error, (MemoryError, RecursionError, TimeoutError))
            or (core is not None and isinstance(error, getattr(core, 'BudgetIncomplete', ())))
            or bool(getattr(error, 'evaluation_diagnostic', {}).get('resource_failure')))

def failure_class(error):
    if is_resource_error(error):
        return 'resource'
    if isinstance(error, OSError) and error.errno in (errno.ENOSPC, errno.EDQUOT, errno.EIO, errno.EROFS):
        return 'storage'
    return 'runtime'

def safe_traceback(error):
    try: return ''.join(traceback.format_exception(type(error),error,error.__traceback__))
    except BaseException:
        return '\n'.join(str(f['source'])+':'+str(f['line'])+' '+f['function'] for f in capture_raw_exception(error)['frames'])

def add_failure(result, error, phase, secondary=False):
    captured = safe_exception(error)
    entry = {'phase': phase, 'exception': captured['type'],
             'message': captured['message'], 'failure_class': failure_class(error),
             'traceback': safe_traceback(error)}
    if 'message_capture_failure' in captured:
        entry['message_capture_failure'] = captured['message_capture_failure']
    if secondary or result.get('exception'):
        result.setdefault('secondary_errors', []).append(entry)
    if not result.get('exception'):
        result.update(exception=entry['exception'], message=entry['message'],
                      traceback=entry['traceback'], failed_phase=phase,
                      failure_class=entry['failure_class'])
    if result.get('completed'):
        result['completion_before_failure'] = {
            key: result.get(key) for key in ('completed', 'disposition', 'semantic_HOLD', 'all_exact')}
    resource_failure = bool(result.get('resource_failure') or is_resource_error(error))
    result.update(completed=False, semantic_HOLD=False, all_exact=False,
                  resource_failure=resource_failure,
                  disposition='resource_incomplete' if resource_failure else 'exception')
    return result

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
            data = gzip.compress(encoded_journal(event) + b'\n', compresslevel=1, mtime=0)
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

def close_journal(journal, result):
    if journal.failure is not None:
        add_failure(result, journal.failure, 'journal_event_write', secondary=True)
    if journal.pending:
        result['pending_event_suffix'] = journal.pending
        result['trace_incomplete'] = True
    try:
        journal.close()
    except BaseException as error:
        add_failure(result, error, 'journal_close', secondary=True)
        result['trace_incomplete'] = True
    result['event_counts'] = dict(journal.counts)
    result['durable_event_prefix_count'] = journal.sequence
    return result

def minimal_failure_record(result):
    keys = ('version', 'teacher_count', 'completed', 'disposition', 'semantic_HOLD',
            'resource_failure', 'all_exact', 'exception', 'message', 'traceback',
            'failed_phase', 'failure_class', 'secondary_errors', 'wall_seconds',
            'process_cpu_seconds', 'ru_maxrss_KiB', 'VmHWM_KiB', 'event_counts',
            'durable_event_prefix_count', 'runtime_lock_sha256_before',
            'runtime_lock_sha256_after', 'runtime_unchanged', 'completion_before_failure')
    return {**{key: result[key] for key in keys if key in result},
            'trace_incomplete': True, 'completion_fallback': True,
            'detail_unavailable_in_fallback': True,
            'pending_event_suffix_count': len(result.get('pending_event_suffix', []))}

def persist_result(path, result):
    """Preserve a primary evaluation failure if storage/serialization also fails."""
    try:
        write(path, result)
        return True
    except BaseException as error:
        add_failure(result, error, 'completion_write', secondary=True)
        result['trace_incomplete'] = True
    fallback = minimal_failure_record(result)
    try:
        write(path.with_name(path.name + '.failure.json'), fallback)
    except BaseException as error:
        add_failure(result, error, 'completion_fallback_write', secondary=True)
        fallback = minimal_failure_record(result)
    try:
        os.write(2, encoded({'preflight_failure_record': fallback}) + b'\n')
    except BaseException as error:
        add_failure(result, error, 'completion_stderr_write', secondary=True)
    return False

def install_call_observers(module, journal, teacher_count):
    """Observe unchanged calls; every result is returned by identity without rerender."""
    counts=Counter(); indexes={spec:i for i,spec in enumerate(module.SPECS)}
    original_parse=module.core.parse
    def parse(*args,**kwargs):
        call_id=counts['parse'];counts['parse']+=1
        caller=pathlib.Path(sys._getframe(1).f_code.co_filename).name
        scope={'周期模様窓教材.py':'fit_domain_proof','周期模様窓基底教材.py':'fit_parse_reuse','全体模様窓視点.py':'whole_view_strict_check'}.get(caller,'other')
        if caller=='周期模様窓必要条件教材.py':scope={'strict_prepass':'necessity_strict_prepass','strict_second_parse_and_witness':'necessity_second_parse'}.get(sys._getframe(1).f_locals.get('phase'),'necessity_other')
        journal({'kind':'core_parse_start','call_id':call_id,'parse_scope':scope})
        raw_pending=original_parse(*args,**kwargs)
        journal({'kind':'core_parse_return','call_id':call_id,'parse_scope':scope,'raw_role':raw_pending[0],'raw_reason':raw_pending[1]})
        return raw_pending
    module.core.parse=parse
    original_whole=module.parse_whole
    def whole(*args,**kwargs):
        call_id=counts['whole'];counts['whole']+=1
        journal({'kind':'whole_parse_start','call_id':call_id})
        raw_pending=original_whole(*args,**kwargs)
        journal({'kind':'whole_parse_return','call_id':call_id,'raw_role':raw_pending[0],'raw_reason':raw_pending[1]})
        return raw_pending
    module.parse_whole=whole
    original_action=module.core.action
    def action(*args,**kwargs):
        identity=journal.active_apply
        journal({'kind':'action_start',**identity})
        raw_pending=original_action(*args,**kwargs)
        journal({'kind':'action_return',**identity,'raw_return':raw_pending})
        return raw_pending
    module.core.action=action
    original_apply=module.apply
    def apply(role,reason,spec):
        call_id=counts['apply'];counts['apply']+=1
        identity={'call_id':call_id,'model_index':indexes[spec],'action_executed':role is not None}
        if journal.context['audit_phase']=='fit':
            identity['teacher_index']=counts['fit_apply']%teacher_count;counts['fit_apply']+=1
        journal({'kind':'apply_start',**identity})
        journal.active_apply=identity
        raw_pending=original_apply(role,reason,spec)
        journal({'kind':'apply_return',**identity,**({'raw_action_return_ref':call_id}if role is not None else {'raw_return':raw_pending})})
        return raw_pending
    module.apply=apply
    module.strict._base.apply=apply
    module.necessity.apply=apply

def child(index, output, root=S, expected_lock_sha256=None):
    start = time.monotonic()
    root, output = pathlib.Path(root).resolve(), pathlib.Path(output).resolve()
    result = {'version': VERSION, 'teacher_count': None, 'completed': False,
              'disposition': 'exception', 'semantic_HOLD': False, 'resource_failure': False}
    journal = module = None
    direct, record = [], {}
    phase = 'limits'
    try:
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        def alarm_handler(*unused):
            raise TimeoutError('60 second total child wall budget')
        signal.signal(signal.SIGALRM, alarm_handler)
        signal.setitimer(signal.ITIMER_REAL, 60)
        phase = 'journal_setup'
        journal = Journal(output / f'{index:03}.events.jsonl.gz')
        phase = 'load'
        verify_lock(root, expected_lock_sha256)
        result['runtime_lock_sha256_before'] = sha(DEPLOYMENT_PIN_PATH)
        authority = json.load(sys.stdin)
        if type(authority) is not dict or set(authority) != {'train'}:
            raise ValueError('train-only child authority required')
        teachers = authority['train']
        if type(teachers) is not list or any(type(pair) is not dict or set(pair) != {'input', 'output'} for pair in teachers):
            raise ValueError('train-only teacher pairs required')
        result['teacher_count'] = len(teachers)
        sys.path.insert(0, str(REPOSITORY_ROOT))
        sys.path.insert(0,str(S))
        module = importlib.import_module('接続.ARC2.全体模様窓必要条件教材')
        if len(module.SPECS)!=PROGRAM_COUNT or tuple(tuple(m[k] for k in module.FIELDS) for m in module.core.models())!=module.SPECS:
            raise RuntimeError('full frozen program domain changed')
        install_call_observers(module, journal, len(teachers))
        phase = 'fit'
        journal.set_context('fit')
        obj = module.全体模様窓必要条件教材(teachers, record, journal)
        actual_fit_parse_calls = journal.counts.get('core_parse_return', 0)
        phase = 'teacher_reproduction'
        for teacher_index, pair in enumerate(teachers):
            journal.set_context('prediction', audit_prediction_teacher_index=teacher_index)
            journal({'kind': 'teacher_prediction_start', 'teacher_index': teacher_index,
                     'retained_model_count': len(obj.モデル群)})
            output_grid, detail = obj.候補(pair['input'], {}, journal)
            row = {'teacher_index': teacher_index, 'input': pair['input'], 'target': pair['output'],
                   'output': output_grid, 'record': detail,
                   'retained_model_count': len(obj.モデル群),
                   'exact': output_grid is not None and output_grid == pair['output']}
            direct.append(row)
            journal({'kind': 'teacher_prediction_completed', **row})
        disposition = ('FIT' if obj.モデル群 else 'proven_empty_fit'
                       if record.get('fit_domain_proof',{}).get('disposition')=='proven_empty' else 'logical_HOLD')
        result.update(completed=True, disposition=disposition,
                      semantic_HOLD=not bool(obj.モデル群), resource_failure=False,
                      evaluated_teacher_calls=record.get('complete_program_teacher_evaluations',0),
                      symbolic_unexecuted_teacher_calls=record.get('unexecuted_program_teacher_evaluations',0),
                      proof_rejected=record.get('fit_domain_proof',{}).get('disposition')=='proven_empty',
                      fit_parse_calls=actual_fit_parse_calls,
                      necessity_certificate_evaluations=record.get('certificate_evaluations',0),
                      necessity_model_refutations=sum(bool(c['refuting_teacher_indices'])for c in record.get('model_necessity_certificates',[])),
                      original_strict_fit_executed=record.get('original_strict_fit_executed',False),
                      models=obj.モデル群, fit=record, teacher_returns=direct,
                      all_exact=bool(obj.モデル群) and all(row['exact'] for row in direct))
    except BaseException as error:
        raw = capture_raw_exception(error)
        try:
            write(output / f'{index:03}.exception-raw.json.gz', raw)
        except BaseException as secondary:
            result['raw_exception_persistence_failure'] = safe_exception(secondary)
        result['raw_exception_evidence'] = raw
        add_failure(result, error, phase)
        result.update(completed_teacher_returns=direct, completed_fit_record=record,
                      evaluation_diagnostic=getattr(error, 'evaluation_diagnostic', None))
    finally:
        try:
            verify_lock(root, result.get('runtime_lock_sha256_before') or expected_lock_sha256)
            result['runtime_lock_sha256_after'] = sha(DEPLOYMENT_PIN_PATH)
            result['runtime_unchanged'] = result.get('runtime_lock_sha256_before') == result['runtime_lock_sha256_after']
        except BaseException as error:
            add_failure(result, error, 'runtime_after_check', secondary=True)
            result['runtime_unchanged'] = False
        if journal is not None:
            close_journal(journal, result)
        usage = resource.getrusage(resource.RUSAGE_SELF)
        result.update(wall_seconds=time.monotonic() - start,
                      process_cpu_seconds=usage.ru_utime + usage.ru_stime,
                      ru_maxrss_KiB=usage.ru_maxrss, VmHWM_KiB=vmhwm())
        persisted = persist_result(output / f'{index:03}.record.json.gz', result)
        try:
            public = {key: value for key, value in result.items()
                      if key not in ('fit', 'teacher_returns', 'completed_teacher_returns',
                                     'completed_fit_record', 'evaluation_diagnostic', 'pending_event_suffix', 'raw_exception_evidence')}
            print(encoded(public).decode('utf-8'), flush=True)
        except BaseException as error:
            add_failure(result, error, 'stdout_write', secondary=True)
            persist_result(output / f'{index:03}.record.json.gz', result)
        signal.setitimer(signal.ITIMER_REAL, 0)
    return 0 if persisted and result.get('completed') else 2

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

def ordered_domain():
    from itertools import product
    return tuple(p for p in product(('motif5plus1','input3minus2'),('motif2','input'),('floor','ceil'),
        ('identity','rot90','rot180','rot270','flip_h','flip_v','transpose','anti_transpose'),
        ('window','canvas'),('tile','scale2'),range(10),range(10))if p[-2]!=p[-1])

def check_model_certificate(certificate,witnesses,domain):
    m=certificate['model_index'];spec=certificate['spec'];rows=certificate['teacher_witnesses']
    if type(m)is not int or not 0<=m<PROGRAM_COUNT or tuple(spec)!=domain[m]:raise ValueError('certificate domain identity changed')
    if len(rows)!=len(witnesses):raise ValueError('certificate teacher coverage changed')
    refuting=[]
    for t,(row,w)in enumerate(zip(rows,witnesses)):
        if row['model_index']!=m or row['teacher_witness_ref']!=t or row['necessary_only']is not True:raise ValueError('certificate witness link')
        if not w['complete']:
            if row['status']!='inconclusive'or row['refuted']is not False:raise ValueError('incomplete witness refuted model')
            continue
        role=w['role'];colors=sorted({v for r in w['target']for v in r});target_shape=[len(w['target']),len(w['target'][0])]
        if colors!=w['target_colors']or target_shape!=w['target_shape']:raise ValueError('teacher target witness mismatch')
        allowed=sorted({role['background'],spec[6],spec[7]});missing=[v for v in colors if v not in allowed]
        mh,mw=len(role['mask']),len(role['mask'][0])
        if spec[3]in('rot90','rot270','transpose','anti_transpose'):mh,mw=mw,mh
        shape=[5*mh+1,5*mw+1]if spec[0]=='motif5plus1'else[3*role['input_shape'][0]-2,3*role['input_shape'][1]-2]
        mismatch=shape!=target_shape;refuted=bool(missing or mismatch)
        if(row.get('allowed_colors')!=allowed or row.get('target_colors')!=colors or row.get('missing_target_colors')!=missing
           or row.get('transformed_mask_shape')!=[mh,mw]or row.get('expected_output_shape')!=shape
           or row.get('target_shape')!=target_shape or row.get('shape_mismatch')is not mismatch
           or row.get('refuted')is not refuted or row.get('status')!=('refuted'if refuted else'not_refuted')):raise ValueError('certificate necessary arithmetic differs')
        if refuted:refuting.append(t)
    if certificate['refuting_teacher_indices']!=refuting:raise ValueError('model refutation links differ')
    return refuting

def read_journal(path,teacher_count):
    path=pathlib.Path(path);counts=Counter();ops=Counter();pending={};returned_actions=set();started=[];core_done=[];declared=[];symbolic=[];models=[];pred=[];pred_starts=[];zero=[];proof=None;events=compressed=decoded_bytes=0;failure=None
    witnesses=[];certificate_refutations=[];domain=ordered_domain();exact_fallback=False
    if path.exists():
        with path.open('rb')as stream:
            buffer=b'';eof=False
            while buffer or not eof:
                z=zlib.decompressobj(31);decoded=bytearray();used_total=0
                try:
                    while not z.eof:
                        if not buffer:
                            buffer=stream.read(65536)
                            if not buffer:eof=True;break
                        decoded.extend(z.decompress(buffer));used_total+=len(buffer)-len(z.unused_data);buffer=z.unused_data
                    if not z.eof:break
                    lines=decoded.splitlines()
                    if len(lines)!=1:raise ValueError('one event per complete member required')
                    e=json.loads(lines[0]);k=e['kind'];phase=e.get('audit_phase')
                    if e['audit_sequence']!=events:raise ValueError('journal sequence gap')
                    counts[k]+=1;ops[(phase,k)]+=1
                    if k=='teacher_necessity_witness':
                        w=e['witness']
                        if w['teacher_index']!=len(witnesses):raise ValueError('witness order changed')
                        witnesses.append(w)
                    elif k=='model_necessity_certificate':
                        c=e['certificate']
                        if c['model_index']!=len(certificate_refutations)or len(witnesses)!=teacher_count:raise ValueError('certificate order/teacher closure')
                        certificate_refutations.append(check_model_certificate(c,witnesses,domain))
                    elif k=='symbolic_model_teacher_slot':
                        m,t=e['model_index'],e['teacher_index']
                        if type(m)is not int or type(t)is not int or not(0<=m<len(certificate_refutations)and 0<=t<teacher_count):raise ValueError('symbolic slot identity')
                        refs=certificate_refutations[m]
                        if(not refs or e['model_certificate_ref']!=m or e['refuting_teacher_indices']!=refs
                           or e['action_executed']is not False or e['actual_return_known']is not False
                           or any(key in e for key in('output','return','return_ref'))
                           or e['exactness']!=('proven_not_exact'if t in refs else'unknown_model_refuted_elsewhere')):raise ValueError('invalid symbolic slot claim')
                        symbolic.append(m*teacher_count+t)
                    elif k=='necessity_exact_fallback_completed':exact_fallback=True
                    if k=='action_return':returned_actions.add(e['call_id'])
                    if k=='apply_return'and e.get('action_executed'):
                        if e.get('raw_action_return_ref')!=e['call_id']or e['call_id']not in returned_actions:raise ValueError('apply lacks actual return')
                    if k in('core_parse_start','core_parse_return','whole_parse_start','whole_parse_return','action_start','action_return','apply_start','apply_return'):
                        op=k.rsplit('_',1)[0];key=(op,e['call_id'])
                        if k.endswith('start'):
                            if key in pending:raise ValueError('duplicate call start')
                            pending[key]=e
                        else:
                            if key not in pending:raise ValueError('return without start')
                            del pending[key]
                        if phase=='fit'and op=='apply':
                            m,t=e['model_index'],e['teacher_index']
                            if type(m)is not int or type(t)is not int or not(0<=m<PROGRAM_COUNT and 0<=t<teacher_count):raise ValueError('invalid actual slot')
                            if m<len(certificate_refutations)and certificate_refutations[m]:raise ValueError('refuted model actually executed')
                            (started if k.endswith('start')else core_done).append(m*teacher_count+t)
                    if k=='model_teacher_return':
                        m,t=e['model_index'],e['teacher_index']
                        if type(m)is not int or type(t)is not int or not(0<=m<PROGRAM_COUNT and 0<=t<teacher_count):raise ValueError('invalid row identity')
                        declared.append(m*teacher_count+t)
                    elif k=='model_completed':models.append(e['model_index'])
                    elif k=='teacher_fit_proven_empty':proof=e['record']
                    elif k=='teacher_prediction_start':
                        pred_starts.append(e['teacher_index'])
                        if e['retained_model_count']==0:zero.append(e['teacher_index'])
                    elif k=='teacher_prediction_completed':pred.append(e['teacher_index'])
                    events+=1;compressed+=used_total;decoded_bytes+=len(decoded)
                except BaseException as error:failure=safe_exception(error);break
    universe=set(range(PROGRAM_COUNT*teacher_count));done=set(declared);symbols=set(symbolic);valid_proof=False
    if proof is not None:
        p=proof.get('parsed_teachers',[]);f=proof.get('fit_domain_proof',{});u=proof.get('unexecuted_domain',{})
        valid_proof=(f.get('disposition')=='proven_empty'and[x.get('teacher_index')for x in p]==list(range(teacher_count))and f.get('failed_teacher_indices')==[x['teacher_index']for x in p if x['role']is None]and bool(f.get('failed_teacher_indices'))and proof.get('program_count')==PROGRAM_COUNT and proof.get('complete_program_teacher_evaluations')==proof.get('actual_action_invocations')==0 and proof.get('unexecuted_program_teacher_evaluations')==PROGRAM_COUNT*teacher_count and u.get('model_index_start')==0 and u.get('model_index_stop_exclusive')==PROGRAM_COUNT and u.get('teacher_indices')==list(range(teacher_count))and u.get('action_calls_executed')is False and u.get('rendered_returns')is False and not started and not declared and not symbolic)
    licensed={m*teacher_count+t for m,refs in enumerate(certificate_refutations)if refs for t in range(teacher_count)}
    if valid_proof:licensed=universe
    covered=done|symbols
    row={'journal_sha256':sha(path)if path.exists()else None,'complete_event_prefix_count':events,'event_prefix_counts':dict(counts),'completed_event_bytes':decoded_bytes,'complete_compressed_event_prefix_bytes':compressed,'incomplete_compressed_suffix_bytes':path.stat().st_size-compressed if path.exists()else 0,'journal_parse_failure':failure,'journal_missing':not path.exists(),'pending_actual_core_calls':list(pending.values()),'completed_program_indices':models,'completed_prediction_teacher_indices':pred,'started_prediction_teacher_indices':pred_starts,'zero_model_teacher_prediction_indices':zero,'completed_fit_teacher_indices':[t for t in range(teacher_count)if all(m*teacher_count+t in covered for m in range(PROGRAM_COUNT))],'symbolically_completed_fit_teacher_indices':list(range(teacher_count))if valid_proof else [],'symbolic_fit_proof_valid':valid_proof,'duplicate_completed_model_teacher_pairs':len(done)!=len(declared)or len(symbols)!=len(symbolic)or bool(done&symbols)or len(started)!=len(set(started))or len(core_done)!=len(set(core_done)),'actual_started_program_teacher_calls':len(started),'actual_completed_program_teacher_calls':len(declared),'started_model_teacher_pairs':compact_pairs(started,teacher_count),'core_completed_model_teacher_pairs':compact_pairs(core_done,teacher_count),'unexecuted_model_teacher_pairs':compact_pairs(universe-set(started),teacher_count),'incomplete_model_teacher_pairs':compact_pairs(set(started)-done,teacher_count),'core_pending_model_teacher_pairs':compact_pairs(set(started)-set(core_done),teacher_count),'core_return_without_teacher_record_pairs':compact_pairs(set(core_done)-done,teacher_count),'completed_model_teacher_pairs':compact_pairs(done,teacher_count),'symbolic_model_teacher_pairs':compact_pairs(symbols,teacher_count),'accounted_model_teacher_pairs':compact_pairs(covered,teacher_count),'proof_licensed_model_teacher_pairs':compact_pairs(licensed,teacher_count),'proof_licensed_but_uncommitted_pairs':compact_pairs(licensed-symbols if not valid_proof else set(),teacher_count),'unclassified_unexecuted_pairs':compact_pairs(universe-set(started)-licensed,teacher_count),'completed_model_certificates':len(certificate_refutations),'verified_model_refutations':sum(bool(x)for x in certificate_refutations),'verified_teacher_witness_count':len(witnesses),'exact_strict_fallback_completed':exact_fallback}
    for phase in('fit','prediction'):
        for operation,event_name in[('parse','core_parse'if phase=='fit'else'whole_parse'),('render','apply'),('action','action'),('strict_parse','core_parse')]:
            for status,ending in[('started','start'),('completed','return')]:row['actual_'+status+'_'+phase+'_'+operation+'_calls']=ops[(phase,event_name+'_'+ending)]
    return row

def reconcile_receipt(row,teacher_count,lock_digest):
    errors=[]
    if row.get('completed'):
        if row.get('journal_parse_failure')or row.get('journal_missing')or row.get('incomplete_compressed_suffix_bytes'):errors.append('journal incomplete')
        if row.get('runtime_lock_sha256_before')!=lock_digest or row.get('runtime_lock_sha256_after')!=lock_digest:errors.append('runtime identity changed')
        if row['pending_actual_core_calls']or row['incomplete_model_teacher_pairs']['count']:errors.append('pending core/row call')
        if row['duplicate_completed_model_teacher_pairs']:errors.append('duplicate/overlapping logical slots')
        if row['completed_prediction_teacher_indices']!=list(range(teacher_count)):errors.append('teacher prediction coverage')
        if row.get('proof_rejected'):
            if not row['symbolic_fit_proof_valid']or row['symbolic_unexecuted_teacher_calls']!=PROGRAM_COUNT*teacher_count or row['evaluated_teacher_calls']!=0:errors.append('global proof accounting')
        else:
            if row['accounted_model_teacher_pairs']['count']!=PROGRAM_COUNT*teacher_count or row['completed_program_indices']!=list(range(PROGRAM_COUNT)):errors.append('logical domain incomplete')
            if row['completed_model_certificates']!=PROGRAM_COUNT or row['verified_teacher_witness_count']!=teacher_count:errors.append('certificate domain incomplete')
            if row['evaluated_teacher_calls']!=row['completed_model_teacher_pairs']['count']or row['symbolic_unexecuted_teacher_calls']!=row['symbolic_model_teacher_pairs']['count']:errors.append('actual/symbolic completion mismatch')
            if row['core_completed_model_teacher_pairs']['count']!=row['completed_model_teacher_pairs']['count']:errors.append('actual return/row mismatch')
            if row['necessity_model_refutations']!=row['verified_model_refutations']:errors.append('model refutation count mismatch')
        if row.get('fit_parse_calls')!=row['actual_completed_fit_parse_calls']:errors.append('parse accounting mismatch')
    row['receipt_consistency_failures']=errors
    if errors:row.update(completed=False,semantic_HOLD=False,all_exact=False,disposition='exception')
    return row
