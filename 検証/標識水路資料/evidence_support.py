"""Exact AST evidence-support subset; no full120 runner or official-input loader."""
import dataclasses,enum,errno,gzip,json,os,pathlib,traceback
from collections import Counter,deque

VERSION = 'fresh-local70-candidate044-preflight-v1'

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

RAW_FIELDS = frozenset(('models','records','calls','active','validation','certificate','symbolic','witnesses','certificate_active','output','detail','raw_pending','rows','record','proposals','destinations','trace','launches','launch','p','d','color','seen','result','direct','teachers','pair','index','model_index','model','grid','program','fallback','context','exception_prefix','original','caught','error'))

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
            try: locals_out[name]=serial(frame.f_locals[name])
            except BaseException as secondary: unavailable[name]=safe_exception(secondary)
        frames.append({'source':frame.f_code.co_filename,'function':frame.f_code.co_name,
                       'line':tb.tb_lineno,'locals':locals_out,'unserializable_locals':unavailable})
        tb=tb.tb_next
    return {'scope':'new prospective traceback capture, never historical recovery',
            'primary_exception':safe_exception(error),'frames':frames,
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
