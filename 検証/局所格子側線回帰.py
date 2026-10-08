#!/usr/bin/env python3
"""Portable teacher/ordinary checks only. No query, scorer, or native run."""
import contextlib
import io
import json
import resource
import runpy
import sys
import traceback
from pathlib import Path

resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
sys.dont_write_bytecode = True
fixtures = Path(__file__).resolve().parent/'局所格子側線資料'
summary = dict(successful=False, tests_run=0, checks=[])
try:
    for name in ('check_teachers.py', 'check_contrasts.py', 'check_local_scenes.py', 'check_binding.py'):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            runpy.run_path(str(fixtures/name), run_name='__main__')
        result = json.loads(output.getvalue().splitlines()[-1])
        assert type(result['successful']) is bool and type(result['tests_run']) is int
        assert result['successful'], name
        summary['tests_run'] += result['tests_run']
        summary['checks'].append(dict(file=name, tests_run=result['tests_run']))
    summary['successful'] = True
except BaseException as error:
    summary.update(error=type(error).__name__, message=str(error))
    traceback.print_exc()
print(json.dumps(summary))
raise SystemExit(0 if summary['successful'] else 1)
