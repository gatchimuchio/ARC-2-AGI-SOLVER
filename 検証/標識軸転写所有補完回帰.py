"""Focused teacher/synthetic checks; no query loader, scorer, or HDS execution."""
import sys
sys.dont_write_bytecode = True
import ast
import copy
import dataclasses
import gzip
import hashlib
import importlib
import json
import tempfile
import types
from pathlib import Path

PAYLOAD = Path(__file__).resolve().parents[1]
BASE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else PAYLOAD
OUT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path(tempfile.mkdtemp(prefix='anchor-support-regression-'))
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(BASE / 'HDS/学習系統/v0.4.2'))


def load(name, roots, strict=False):
    package = types.ModuleType(name)
    package.__path__ = [str(root / '接続/ARC2') for root in roots]
    sys.modules[name] = package
    if strict:
        path = roots[-1] / '接続/ARC2/標識軸転写教材.py'
        source = path.read_text()
        addition = ("            if output is None:\n"
                    "                from .標識軸転写所有補完 import complete_failed_render\n"
                    "                output, detail = complete_failed_render(grid, program, output, detail)\n")
        source = source.replace(addition, '', 1)
        if hashlib.sha256(source.encode()).hexdigest() != 'f86c8faa6dca389e18f92c76bcceee445f867bd26941d47cf5a219b705bc2cdd':
            raise AssertionError('original strict adapter reference differs')
        module_name = name + '.標識軸転写教材'
        module = types.ModuleType(module_name)
        module.__package__ = name
        sys.modules[module_name] = module
        exec(compile(source, str(path), 'exec'), module.__dict__)
        return module
    return importlib.import_module(name + '.標識軸転写教材')


candidate = load('_anchor_support_candidate', [PAYLOAD, BASE])
baseline = load('_anchor_support_baseline', [BASE], strict=True)
extension = importlib.import_module('_anchor_support_candidate.標識軸転写所有補完')
checks = []


def check(name, passed):
    if not passed:
        raise AssertionError(name)
    checks.append(name)


def save(name, record):
    encoded = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    (OUT / (name + '.json.gz')).write_bytes(gzip.compress(encoded, compresslevel=1, mtime=0))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def main():
    teachers = json.loads((BASE / '検証/標識軸転写資料/original/teachers.json').read_text())['train']
    before = copy.deepcopy(teachers)
    audit_old, audit_new = {}, {}
    old = baseline.標識軸転写教材(teachers, 監査=audit_old)
    new = candidate.標識軸転写教材(teachers, 監査=audit_new)
    check('strict fit audit and immutable fitted state unchanged',
          audit_old == audit_new and dataclasses.asdict(old) == dataclasses.asdict(new))
    check('both fitted C4/C8 hypotheses retained',
          len(new.モデル群) == 2 and {m[3] for m in new.モデル群} == {4, 8})
    check('all 720 teacher evaluations completed', audit_new['complete_program_teacher_evaluations'] == 720)
    save('teacher-fit', {'old': audit_old, 'new': audit_new, 'models': new.モデル群})
    for index, teacher in enumerate(teachers):
        raw, current = old.候補(teacher['input'], {}), new.候補(teacher['input'], {})
        check('teacher output and complete default record parity ' + str(index),
              canonical(raw) == canonical(current) and current[0] == teacher['output'])
        save('teacher-' + str(index), {'baseline': raw, 'candidate': current})
    check('teacher inputs unchanged', teachers == before)

    # Reuse only the existing independent D4 oracle and generic fixture constructor.
    source = gzip.decompress((BASE / '検証/標識軸転写資料/validate_prototype.py.gz').read_bytes()).decode()
    tree = ast.parse(source)
    definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name in ('independent_transform', 'fixture')]
    namespace = {'copy': copy, 'core': candidate.core}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), '<existing-synthetic-fixtures>', 'exec'), namespace)
    fixture = namespace['fixture']

    def run(name, grid):
        before_grid, before_models = copy.deepcopy(grid), new.モデル群
        raw, current = old.候補(grid, {}), new.候補(grid, {})
        save(name, {'input': grid, 'baseline': raw, 'candidate': current})
        check(name + ' input and fitted hypotheses unchanged', grid == before_grid and new.モデル群 is before_models)
        return raw, current

    connected, expected = fixture('rot90', marker_shape=((0, 0), (0, 1)), target=(20, 20))
    raw, current = run('old-connected-success', connected)
    check('old successful output and complete record unchanged',
          raw[0] == expected and canonical(raw) == canonical(current))

    diagonal, expected = fixture('identity', marker_shape=((0, 0), (1, 1)), target=(20, 20))
    raw, current = run('whole-diagonal-support', diagonal)
    check('fragmented support completes without replacing C4', raw[0] is None and current[0] == expected
          and current[1]['program_returns'][0]['program']['object_connectivity'] == 4)
    check('successful C8 return exactly preserved inside completion',
          canonical(raw[1]['program_returns'][1]) == canonical(current[1]['program_returns'][1]))
    check('both role orders retain their complete ownership cover',
          all(v['complete_cover_count'] == 1 for v in current[1]['program_returns'][0]['detail']['views']))

    spaced, expected = fixture('rot90', marker_shape=((0, 0), (2, 2)), target=(20, 20))
    raw, current = run('whole-spaced-support', spaced)
    check('ownership follows exact support rather than diagonal adjacency',
          raw[0] is None and current[0] == expected
          and all(x['output'] is None for x in raw[1]['program_returns'])
          and all(x['detail'].get('input_view_extension') == 'complete_marker_support_ownership'
                  for x in current[1]['program_returns']))

    extra = copy.deepcopy(diagonal)
    extra[25][5] = 9
    raw, current = run('unowned-extra-marker', extra)
    check('uncovered marker remains HOLD', raw[0] is None and current[0] is None)

    mismatch = copy.deepcopy(diagonal)
    mismatch[21][21], mismatch[21][22] = 0, 9
    raw, current = run('wrong-complete-support', mismatch)
    check('wrong complete support remains HOLD', raw[0] is None and current[0] is None)

    multi, _ = fixture('identity', glyph=(3, 3), marker_shape=((0, 0), (1, 1)), target=(20, 20))
    _, role_record = candidate.core.render(multi, dict(new.展開モデル()[0]['program'], object_connectivity=8))
    object_cells = role_record['views'][0]['roles']['objects'][0]['cells']
    for r, c in object_cells:
        multi[r][c + 10] = multi[r][c]
    multi[20][8] = multi[21][9] = 9
    raw, current = run('all-bijections-same-output', multi)
    check('all same-output complete assignments retained', raw[0] is None and current[0] is not None
          and all(len(c['assignments']) == 2 for v in current[1]['program_returns'][0]['detail']['views']
                  for c in v['cover_returns'] if c['admitted']))

    asymmetric = copy.deepcopy(multi)
    asymmetric[4][14] = 0
    raw, current = run('all-bijections-conflicting-output', asymmetric)
    check('conflicting complete assignments block output', current[0] is None
          and any(c.get('failure') == 'complete_assignment_outputs_disagree'
                  for v in current[1]['program_returns'][0]['detail']['views'] for c in v['cover_returns']))

    # A cover can be structurally admissible even when its renderer fails.
    collision = copy.deepcopy(multi)
    collision[20][8] = collision[21][9] = 0
    collision[20][17] = collision[21][18] = 9
    raw, current = run('complete-assignment-collision', collision)
    check('failed complete assignment is retained and blocks output', current[0] is None
          and any(c['admitted'] and c.get('failure') == 'complete_assignment_failed'
                  for v in current[1]['program_returns'][0]['detail']['views'] for c in v['cover_returns']))

    # One scoped interruption verifies the new completion boundary does not turn
    # a budget failure into structural impossibility or a semantic HOLD.
    original_assignments = candidate.core.all_assignments
    def interrupted(*args, **kwargs):
        raise TimeoutError('scoped ownership-completion interruption')
    candidate.core.all_assignments = interrupted
    try:
        new.候補(diagonal, {})
        raise AssertionError('budget exception swallowed')
    except TimeoutError as error:
        partial = error.partial_full_return
        check('budget failure propagates with incomplete cover record',
              partial['resource_exception'] == 'TimeoutError'
              and partial['views'][0]['cover_returns'][-1]['complete'] is False)
        save('completion-interruption', partial)
    finally:
        candidate.core.all_assignments = original_assignments

    source_files = [PAYLOAD / '接続/ARC2/標識軸転写教材.py',
                    PAYLOAD / '接続/ARC2/標識軸転写所有補完.py', Path(__file__).resolve()]
    return {'successful': True, 'checks': checks, 'query_calls': 0,
            'teacher_count': len(teachers), 'retained_models': new.モデル群,
            'source_sha256': {str(p.relative_to(PAYLOAD)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in source_files}, 'artifact_directory': str(OUT)}


try:
    result = main()
except BaseException as error:
    import traceback
    result = {'successful': False, 'checks': checks, 'exception': type(error).__name__,
              'error': str(error), 'traceback': traceback.format_exc(), 'query_calls': 0,
              'artifact_directory': str(OUT)}
(OUT / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False))
raise SystemExit(0 if result['successful'] else 1)
