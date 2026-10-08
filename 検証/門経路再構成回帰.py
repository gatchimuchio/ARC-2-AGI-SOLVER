"""Ordinary teacher and contrast checks. Run only in the lead's serial slot."""
import ast
import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from 接続.ARC2 import 門経路再構成候補 as candidate
from 接続.ARC2 import 距離回収教材 as wrapper

DATA = Path(__file__).resolve().parent / '門経路再構成資料'
BASE = DATA / 'reference'


def run():
    checks = []
    def check(name, value):
        checks.append({'name': name, 'passed': bool(value)})
        assert value, name

    train = json.loads((DATA / 'teachers.json').read_text())['train']
    saved = copy.deepcopy(train)
    models, record = candidate.fit(train)
    check('all_finite_candidates_complete', record.get('complete') and
          record.get('candidate_count') == 24 * 8 * 4)
    check('teacher_fit_nonempty', bool(models))
    material = wrapper.距離回収教材(train)
    check('exact_old_color_failure_selects_new_fit',
          not material.モデル群 and candidate.thaw(material.門経路モデル群) == models)
    for i, pair in enumerate(train):
        output, detail = material.候補(pair['input'], {})
        check('teacher_exact_' + str(i), output == pair['output'])
        check('all_fitted_alternatives_retained_' + str(i),
              len(detail['retained_results']) == len(models))
        if i == 0:
            check('material_in_flat_path_stays_fixed', all(
                any(p.get('stationary') == 'no_directional_extent' and p['material_count']
                    for p in result['detail']['paths'])
                for result in detail['retained_results']))
    check('teachers_immutable', train == saved)
    changed = copy.deepcopy(train)
    changed[0]['output'][0][0] = 0
    check('contradictory_teacher_rejected', not candidate.fit(changed)[0])
    branch = copy.deepcopy(train[0]['input'])
    branch[1][1] = 8
    check('branch_contrast_hold', material.候補(branch, {})[0] is None)
    check('invalid_grid_hold', material.候補([[1], []], {})[0] is None)
    alternatives = copy.deepcopy(models)
    alternatives[0]['direction'] = [-x for x in alternatives[0]['direction']]
    check('failing_or_disagreeing_alternative_not_dropped',
          candidate.consensus(train[0]['input'], models + alternatives)[0] is None)

    # A palette permutation checks that runtime role colors are teacher-fitted.
    remap = lambda grid: [[(v + 1) % 10 for v in row] for row in grid]
    recolored = [{'input': remap(p['input']), 'output': remap(p['output'])} for p in train]
    recolored_material = wrapper.距離回収教材(recolored)
    check('recolored_teacher_fit_and_predictions', all(
        recolored_material.候補(p['input'], {})[0] == p['output'] for p in recolored))

    # The old functions and primitive source remain unchanged.
    def functions(path):
        return {n.name: ast.dump(n, include_attributes=False)
                for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}
    relative = Path('接続/ARC2/距離回収教材.py')
    check('old_fit_and_exhaustive_query_functions_unchanged',
          functions(BASE / relative) == functions(ROOT / relative))
    relative = Path('接続/ARC2/距離回収候補.py')
    check('old_distance_core_bytes_unchanged',
          (BASE / relative).read_bytes() == (ROOT / relative).read_bytes())

    with patch.object(candidate, 'fit', side_effect=AssertionError('unexpected fallback')):
        for diagnostic in ({'failure': 'old_ambiguous'}, {'failure': 'old_error'},
                           {'failure': 'union_not_five_role_colors', 'complete': False},
                           {'failure': 'invalid_teachers'}, {}):
            with patch.object(wrapper, '距離回収をfit', return_value=([], diagnostic)):
                old = wrapper.距離回収教材(train)
                check('old_nonexact_failure_preserved_' + str(diagnostic),
                      old.候補(train[0]['input'], {}) ==
                      wrapper.全距離モデルを照会(train[0]['input'], []))
        old_model = {'roles': dict(zip(wrapper.core.ROLE_NAMES, range(5))), 'shape': [3, 3],
                     'parameters': {k: values[0] for k, values in wrapper.core.AXES.items()}}
        with patch.object(wrapper, '距離回収をfit', return_value=([old_model], {})):
            old = wrapper.距離回収教材(train)
            check('old_positive_models_and_query_route_preserved',
                  old.展開モデル() == [old_model] and not old.門経路モデル群 and
                  old.候補(train[0]['input'], {}) ==
                  wrapper.全距離モデルを照会(train[0]['input'], [old_model]))

    report = {'kind': 'new_reconstruction_teacher_checks', 'checks': checks,
              'teacher_count': len(train), 'fit': record, 'models': models,
              'teacher_file_sha256': hashlib.sha256((DATA / 'teachers.json').read_bytes()).hexdigest(),
              'query_inputs_or_solutions_read': False}
    out = Path(tempfile.mkdtemp(prefix='new066-regression-'))
    (out / 'new-reconstruction-teacher-checks.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'successful': True, 'tests_run': len(checks), 'retained_models': len(models), 'artifact_directory': str(out), 'provenance': 'NEW066 reconstruction'}, ensure_ascii=False))


if __name__ == '__main__':
    run()
