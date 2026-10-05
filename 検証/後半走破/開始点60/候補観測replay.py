"""Separate frozen-code observational replay; no solver/scorer files are changed."""
from __future__ import annotations
import argparse
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()

def child(root):
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (10, 11))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    task = json.load(sys.stdin)
    if set(task) != {'train', 'test'} or any(set(pair) != {'input'} for pair in task['test']):
        raise ValueError('Only train pairs and test input grids are allowed')
    opens = []
    def access_audit(event, args):
        if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = str(Path(os.fsdecode(args[0])).resolve())
        if '/data/evaluation/' in path or 'solutions' in Path(path).name:
            raise PermissionError('observational child may not read evaluation source or solutions')
        if path.endswith(('.json', '.jsonl')):
            opens.append(path)
    sys.addaudithook(access_audit)
    sys.path[:0] = [str(root), str(root / 'HDS/学習系統/v0.4.2')]
    from 接続.ARC2 import HDS接続 as bridge
    calls = []
    phase = {'value': 'teacher_fit_or_initialization'}
    def wrap(fn, owner):
        def observed(*args, **kwargs):
            grid_position = 1 if isinstance(owner, type) else 0
            input_grid = args[grid_position]
            before_hash = digest(input_grid)
            event = {'sequence': len(calls), 'phase': phase['value'],
                     'callable': (owner.__name__ if isinstance(owner, type) else owner),
                     'input_sha256_before': before_hash}
            try:
                result = fn(*args, **kwargs)
            except BaseException as exc:
                calls.append({**event, 'input_sha256_after': digest(input_grid),
                              'exception': {'type': type(exc).__name__, 'message': str(exc)}})
                raise
            candidate, detail = result
            calls.append({**event, 'input_sha256_after': digest(input_grid),
                          'candidate_is_none': candidate is None,
                          'candidate_sha256': None if candidate is None else digest(candidate),
                          'detail': deepcopy(detail)})
            return result
        return observed
    wrapped = set()
    for name, value in list(vars(bridge).items()):
        if isinstance(value, type) and hasattr(value, '候補') and value not in wrapped:
            value.候補 = wrap(value.候補, value)
            wrapped.add(value)
        elif name in ('_template_hole_pack_render', '_nested_panel_relation_render',
                      '_dual_region_hole_palette_render', '辺対応候補'):
            setattr(bridge, name, wrap(value, name))
    original_teach = bridge.候補機構を学習
    def teach(*args, **kwargs):
        phase['value'] = 'teacher_reproduction'
        result = original_teach(*args, **kwargs)
        phase['value'] = 'between_families_or_query'
        return result
    bridge.候補機構を学習 = teach
    failed = False
    try:
        result = bridge.課題を解く(task, bridge.事前教材を読む())
        envelope = {'result': result}
    except BaseException as exc:
        failed = True
        envelope = {'error': 'observer_runtime_exception',
                    'exception': {'type': type(exc).__name__, 'message': str(exc),
                                  'traceback': traceback.format_exc()}}
    print(json.dumps({**envelope, 'calls': calls,
                      'allowed_data_opens': sorted(set(opens)),
                      'input_contract': {'top_level': sorted(task),
                                         'test_keys': [sorted(x) for x in task['test']],
                                         'task_id_present': False,
                                         'canonical_python_audited_evaluation_opens_blocked': True,
                                         'os_filesystem_isolation': False}},
                     ensure_ascii=False))
    if failed:
        raise SystemExit(1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--runtime', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    if args.runtime:
        child(root)
        return
    assert args.output and args.baseline
    args.output.mkdir(exist_ok=False)
    old = json.loads(args.baseline.read_text())
    old_records = {x['task_id']: x for x in old['execution']}
    tasks = []
    for file in sorted((root / '入力/公式ソース/ARC-AGI-2/data/evaluation').glob('*.json')):
        original = json.loads(file.read_text())
        tasks.append((file.stem, {'train': original['train'],
                                 'test': [{'input': pair['input']} for pair in original['test']]}))
    assert len(tasks) == 120 and sum(len(t['test']) for _, t in tasks) == 167
    code_manifest = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for d in ('HDS', '接続') for p in sorted((root / d).rglob('*.py'))}
    freeze = {'code': code_manifest, 'observer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'sanitized_tasks_sha256': digest(tasks), 'baseline_sha256': hashlib.sha256(args.baseline.read_bytes()).hexdigest()}
    (args.output / 'freeze.json').write_text(json.dumps(freeze, ensure_ascii=False, indent=2))
    started = time.monotonic()
    def run(item):
        task_id, task = item
        try:
            p = subprocess.run([sys.executable, __file__, '--root', str(root), '--runtime'],
                               input=json.dumps(task), text=True, capture_output=True, timeout=60,
                               env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            if p.returncode:
                try:
                    partial = json.loads(p.stdout)
                except json.JSONDecodeError:
                    partial = {}
                return {'task_id': task_id, 'error': 'runtime_exit', 'returncode': p.returncode,
                        'stderr': p.stderr, 'stdout': p.stdout, 'partial_diagnostics': partial}
            result = json.loads(p.stdout)
            previous = {k: v for k, v in old_records[task_id].items()
                        if k not in ('task_id', 'test_count', 'unanswered', 'correct_examples')}
            return {'task_id': task_id, **result, 'exact_result_equal': result['result'] == previous}
        except subprocess.TimeoutExpired:
            return {'task_id': task_id, 'error': 'wall_limit'}
    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(run, tasks))
    raw = ''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in records).encode()
    compressed = gzip.compress(raw, mtime=0)
    (args.output / 'raw.jsonl.gz').write_bytes(compressed)
    failures = [dict(task_id=x['task_id'], error=x.get('error'), returncode=x.get('returncode'))
                for x in records if 'error' in x]
    summary = {'tasks': len(records), 'examples': 167,
               'exact_results_equal': sum(x.get('exact_result_equal', False) for x in records),
               'changed_results': [x['task_id'] for x in records if x.get('exact_result_equal') is False],
               'resource_or_runtime_failures': failures,
               'calls': sum(len(x.get('calls', [])) for x in records),
               'raw_sha256': hashlib.sha256(raw).hexdigest(), 'raw_bytes': len(raw),
               'gzip_sha256': hashlib.sha256(compressed).hexdigest(), 'gzip_bytes': len(compressed),
               'lossless_verified': gzip.decompress(compressed) == raw,
               'code_unchanged': all(hashlib.sha256((root / p).read_bytes()).hexdigest() == h
                                     for p, h in code_manifest.items()),
               'seconds': time.monotonic() - started,
               'scope': 'Returned candidate diagnostics only. Not a trace of all unexposed internal hypotheses. Separate replay, not original historical observation.'}
    (args.output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False))

if __name__ == '__main__':
    main()
