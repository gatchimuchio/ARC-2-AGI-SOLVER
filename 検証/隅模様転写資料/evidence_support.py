"""Exact evidence-support function subset from the sealed031 harness."""
import dataclasses,enum,gzip,hashlib,json,os,pathlib
from collections import deque


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

def sha(path):
    digest = hashlib.sha256()
    with pathlib.Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

RAW_FIELDS = frozenset(('models','records','calls','active','validation','certificate','symbolic','witnesses','certificate_active','output','detail','raw_pending','rows','record','proposals','destinations','trace','launches','launch','p','d','color','seen','result','direct','teachers','pair','index','model_index','model','grid','program','fallback','context','exception_prefix','original','caught','error','certificates','probes','returns','completed','prefix','remaining','components','role_certificates','nodes','covered','owned','chosen','candidates','rec','cells','rr','cc','rs','cs','roles','patches','active','complete','masks','mask','corners','frames','frame','g','target','background','bg','out','ci','corner','local'))

def capture_raw_exception(error, seen=None):
    """Prospective only: capture traceback locals even when the frozen reporter fails entirely.

    Includes completed model/teacher/witness buffers and pending raw return locals.
    Unsupported opaque locals are named explicitly rather than repr'd or silently claimed.
    """
    seen=set() if seen is None else seen
    if id(error) in seen:return {"exception_context_cycle":True}
    seen.add(id(error))
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
            'context':capture_raw_exception(error.__context__, seen) if error.__context__ is not None and error.__context__ is not error else None,
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
