#!/usr/bin/env python3
"""Portable existing teacher/ordinary checks; no query, scorer, or native run."""
import hashlib
import json
from pathlib import Path
import resource
import sys
import time
import traceback

resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from 接続.ARC2 import 連結箱参照核 as core
from 接続.ARC2 import 連結箱参照候補 as api
from 接続.ARC2.連結箱参照教材 import 連結箱参照教材

DATA = Path(__file__).resolve().parent/'連結箱参照資料'
summary = dict(successful=False, tests_run=0, checks=[])
started = time.process_time()


def require(condition, name):
    if not condition:
        raise AssertionError(name)


def passed(name):
    summary['tests_run'] += 1
    summary['checks'].append(dict(name=name, passed=True))


try:
    pins = json.loads((DATA/'source-fixture-pins.json').read_text())
    for path, name in ((Path(core.__file__), 'renderer_sha256'), (Path(api.__file__), 'api_sha256'),
                       (DATA/'teachers-only.json', 'teachers_sha256'),
                       (DATA/'ordinary-fixtures.json', 'ordinary_fixtures_sha256'),
                       (DATA/'retained-state.json', 'retained_state_sha256')):
        require(hashlib.sha256(path.read_bytes()).hexdigest() == pins[name], name)
    teachers = json.loads((DATA/'teachers-only.json').read_text())['train']
    fixtures = json.loads((DATA/'ordinary-fixtures.json').read_text())
    expected_state = json.loads((DATA/'retained-state.json').read_text())
    audit = {}
    candidate = 連結箱参照教材(teachers, audit)
    state, fit_record = api.fit(teachers)
    require(state == expected_state, 'same_retained_state')
    require(audit == fit_record, 'adapter_delegates_complete_fit_unchanged')
    require(fit_record['materialized_return_count'] == len(core.PROGRAMS)*len(teachers),
            'all_program_teacher_returns_materialized')
    for i, pair in enumerate(teachers):
        output, record = candidate.候補(pair['input'], {})
        require(output == pair['output'], 'teacher_full_grid_'+str(i))
        require((output, record) == api.predict(pair['input'], state), 'teacher_api_record_parity')
        passed('teacher_full_grid_'+str(i))
    for fixture in fixtures:
        output, record = candidate.候補(fixture['input'], {})
        require(output == fixture['expected'], fixture['name'])
        require((output, record) == api.predict(fixture['input'], state), 'contrast_api_record_parity')
        passed(fixture['name'])
    original_merge = core.merge_proposals
    for error_type in (MemoryError, RuntimeError):
        def fail(*args, error_type=error_type, **kwargs):
            raise error_type('injected contrast failure')
        core.merge_proposals = fail
        escaped = False
        try:
            candidate.候補(fixtures[0]['input'], {})
        except error_type:
            escaped = True
        finally:
            core.merge_proposals = original_merge
        require(escaped, error_type.__name__+'_propagation')
        passed(error_type.__name__+'_propagation')
    summary.update(successful=True, retained_state=state,
                   materialized_teacher_returns=fit_record['materialized_return_count'])
except BaseException as error:
    summary.update(error=type(error).__name__, message=str(error))
    traceback.print_exc()
summary.update(cpu_seconds=time.process_time()-started,
               maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
print(json.dumps(summary))
raise SystemExit(0 if summary['successful'] else 1)
