"""Small ordinary checks for the existing-family binding; no native/query use."""
import json
import resource
import sys
from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path

resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parents[1]))
from 接続.ARC2 import 色線反射合成教材 as bound

checks = []


def check(name, value):
    assert value, name
    checks.append(name)


old_teachers = []
for h, w in ((7, 11), (6, 10)):
    grid = [[0]*w for _ in range(h)]
    for r, c in ((h-1, w-1), (h-2, w-1), (h-1, w-2)):
        grid[r][c] = 1
    old_teachers.append(dict(input=grid, output=deepcopy(grid)))

old_events, new_events = [], []
old_models, old_record = bound.legacy.fit(old_teachers, old_events.append)
new_models, new_record = bound.fit(old_teachers, new_events.append)
check('old_positive_models_fit_records_and_observers_exact',
      bool(old_models) and old_models == new_models and old_record == new_record
      and old_events == new_events)
old_class = bound.legacy.色線反射教材(old_teachers)
new_class = bound.色線反射教材(old_teachers)
check('old_positive_class_record_and_prediction_exact',
      old_class.記録() == new_class.記録()
      and all(old_class.候補(t['input'], {}) == new_class.候補(t['input'], {})
              for t in old_teachers))

for malformed in (None, [], [old_teachers[0]], [old_teachers[0], old_teachers[0]]):
    assert bound.fit(malformed) == bound.legacy.fit(malformed)
check('old_validation_failures_exact', True)

teachers = json.loads((BASE/'teachers-only.json').read_text())['train']
models, record = bound.fit(teachers)
strict_models, strict_record = bound.lattice.strict.fit(teachers)
check('actual_old_no_source_boundary_and_original_strict_fit',
      models == strict_models == ((0, 1, 3, 'ends', 1),)
      and record['lattice_fit'] == strict_record
      and record['legacy_fit']['evaluated_models'] == 8
      and record['legacy_fit']['evaluated_teacher_returns'] == 16
      and len(record['legacy_boundary']['teachers']) == 2)
check('bound_new_teacher_predictions_exact',
      all(bound.predict(t['input'], models)[0] == t['output'] for t in teachers))
fitted = bound.色線反射教材(teachers)
immutable = False
try:
    fitted.モデル群 = ()
except FrozenInstanceError:
    immutable = True
check('new_fitted_state_remains_immutable', immutable)

old_fit, lattice_fit = bound.legacy.fit, bound.lattice.fit
incomplete = dict(teacher_count=2, teacher_fit_minimum=2, declared_models=8,
                  evaluated_models=8, evaluated_teacher_returns=15,
                  retained_count=0, failure='no_model_fits_all_teachers')


def forbidden_fit(*args, **kwargs):
    raise AssertionError('new fit must not run')


bound.legacy.fit = lambda *args, **kwargs: ((), deepcopy(incomplete))
bound.lattice.fit = forbidden_fit
try:
    incomplete_return = bound.fit(teachers)
finally:
    bound.legacy.fit, bound.lattice.fit = old_fit, lattice_fit
check('incomplete_old_fit_cannot_open_new_view', incomplete_return == ((), incomplete))

negative = []
for n, cell in ((5, (1, 1)), (7, (2, 2))):
    grid = [[0]*n for _ in range(n)]
    grid[cell[0]][cell[1]] = 1
    negative.append(dict(input=grid, output=deepcopy(grid)))
bound.lattice.fit = forbidden_fit
try:
    negative_models, negative_record = bound.fit(negative)
finally:
    bound.lattice.fit = lattice_fit
guard = negative_record['lattice_view_guard']
check('necessary_common_spacer_guard_records_every_teacher_and_zero_new_renders',
      not negative_models and guard['logical_no_fit']
      and guard['new_render_calls'] == 0 and len(guard['teachers']) == 2
      and guard['common_spacer_colours'] == [])

unrecognized = []
for n in (6, 8):
    grid = [[0]*n for _ in range(n)]
    for r, c in ((1, 1), (1, 2), (2, 1), (2, 2)):
        grid[r][c] = 1
    unrecognized.append(dict(input=grid, output=deepcopy(grid)))
check('unrecognized_old_role_failure_does_not_open_new_view',
      bound.fit(unrecognized) == bound.legacy.fit(unrecognized))


def interrupted(*args, **kwargs):
    raise MemoryError('ordinary binding error propagation')


bound.legacy.fit = interrupted
raised = False
try:
    bound.fit(teachers)
except MemoryError:
    raised = True
finally:
    bound.legacy.fit = old_fit
check('old_fit_error_propagates_without_fallback', raised)

strict_render = bound.lattice.strict.render
bound.lattice.strict.render = interrupted
raised = False
try:
    bound.fit(teachers)
except MemoryError:
    raised = True
finally:
    bound.lattice.strict.render = strict_render
check('new_strict_fit_error_propagates', raised)

print(json.dumps(dict(successful=True, tests_run=len(checks), passed_cases=checks)))
