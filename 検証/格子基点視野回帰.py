"""Portable source-only checks. Prints one JSON line; writes no artifacts."""
import argparse
import importlib.util
import io
import json
import resource
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode = True
resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 ** 2, 512 * 1024 ** 2))
parser = argparse.ArgumentParser()
parser.add_argument('--source-root', type=Path)
args = parser.parse_args()
overlay = Path(__file__).resolve().parents[1]
root = args.source_root.resolve() if args.source_root else overlay
sys.path[:0] = [str(root), str(root / 'HDS/学習系統/v0.4.2')]
import 接続.ARC2 as package
package.__path__ = [str(overlay / '接続/ARC2')] + list(package.__path__)
from 接続.ARC2 import 格子基点視野 as subject
from 接続.ARC2 import 格子基点複製接続 as adapter
strict = subject.strict
teachers = json.loads(Path(__file__).with_name('格子基点教師.json').read_text())
model, record = subject.fit(teachers)
if not subject.fit is strict.fit:
    raise AssertionError()
if not (model, record) == strict.fit(teachers):
    raise AssertionError()
checks = []
for i, pair in enumerate(teachers):
    actual = subject.consensus(pair['input'], model)
    if not actual == strict.consensus(pair['input'], model):
        raise AssertionError()
    if not actual[0] == pair['output']:
        raise AssertionError()
    checks.append(dict(case='teacher_' + str(i), exact_grid_and_record_parity=True))

def independent_case():
    inp = [[0] * 19 for _ in range(19)]
    for i in range(19):
        inp[9][i] = inp[i][9] = 6
    for r, c in ((4, 4), (0, 12), (18, 8), (10, 10)):
        inp[r][c] = 7
    inp[3][4] = 3
    inp[4][5] = inp[4][6] = 8
    expected = [row[:] for row in inp]
    expected[0][10] = expected[0][11] = 8
    expected[11][10] = 3
    return (inp, expected)
inp, expected = independent_case()
strict_out, strict_record = strict.consensus(inp, model)
if not strict_out is None:
    raise AssertionError()
out, record = subject.consensus(inp, model)
if not out == expected:
    raise AssertionError(record)
ledger = record['policy_records'][0]['roles'][0]['viewport_placements']
if not len(ledger) == 4:
    raise AssertionError()
if not sum((len(p['complete_cells']) for p in ledger)) == 16:
    raise AssertionError()
if not sum((len(p['visible_cells']) for p in ledger)) == 10:
    raise AssertionError()
if not sum((len(p['outside_cells']) for p in ledger)) == 6:
    raise AssertionError()
checks.append(dict(case='independent_chamber_crop', complete=16, visible=10, invisible=6))
rotated_in = strict.transform_grid_by_name(inp, 'rot90')
rotated_out = strict.transform_grid_by_name(expected, 'rot90')
if not subject.consensus(rotated_in, model)[0] == rotated_out:
    raise AssertionError()
checks.append(dict(case='rotated_chamber_crop_exact'))
mapping = {v: (3 * v + 2) % 10 for v in range(10)}
recolored_in = [[mapping[v] for v in row] for row in inp]
recolored_out = [[mapping[v] for v in row] for row in expected]
if not subject.consensus(recolored_in, model)[0] == recolored_out:
    raise AssertionError()
checks.append(dict(case='recolored_chamber_crop_exact'))
scaled = [row[:] for row in inp]
scaled[0][12] = 0
for r in (0, 1):
    for c in (14, 15):
        scaled[r][c] = 7
scaled_expected = [row[:] for row in scaled]
for r in (0, 1):
    for c in (10, 11, 12, 13):
        scaled_expected[r][c] = 8
scaled_expected[11][10] = 3
if not subject.consensus(scaled, model)[0] == scaled_expected:
    raise AssertionError()
checks.append(dict(case='complete_scaled_copy_then_crop_exact'))
pair = dict(input=inp, output=expected)
other = dict(input=recolored_in, output=recolored_out)
if not subject.fit([pair, other]) == strict.fit([pair, other]):
    raise AssertionError()
if not subject.fit([pair, other])[0] is None:
    raise AssertionError()
checks.append(dict(case='strict_fit_domain_unchanged'))
out, record = subject.consensus(inp, {'policies': [(True, True), (False, True)]})
if not (out is None and record['failure'] == 'policy_full_grid_disagreement'):
    raise AssertionError()
if not record['evaluated_policy_count'] == 2:
    raise AssertionError()
checks.append(dict(case='all_retained_policies_kept_after_crop', evaluated=2))
noninteger = [row[:] for row in teachers[1]['input']]
for r, c in ((5, 21), (6, 20), (6, 21)):
    noninteger[r][c] = 4
if not subject.consensus(noninteger, model) == strict.consensus(noninteger, model):
    raise AssertionError()
if not subject.consensus(noninteger, model)[0] is None:
    raise AssertionError()
checks.append(dict(case='non_boundary_failure_delegated_unchanged'))
if not not subject.boundary_role({'failure': 'incomplete_role_render', 'failures': [{'tile': 1, 'failures': ['foreground_collision', 'placement_outside_tile']}]}):
    raise AssertionError()
checks.append(dict(case='mixed_collision_boundary_failure_cannot_enable_crop'))
original = subject.crop_grid

def raise_failure(*args):
    raise MemoryError('injected crop allocation failure')
subject.crop_grid = raise_failure
try:
    subject.consensus(inp, model)
except MemoryError as error:
    if not str(error) == 'injected crop allocation failure':
        raise AssertionError()
else:
    raise AssertionError('resource failure was swallowed')
finally:
    subject.crop_grid = original
checks.append(dict(case='crop_resource_failure_propagates'))
spec = importlib.util.spec_from_file_location('existing_anchor_source_contrasts', root / '検証/基点複製回帰.py')
existing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(existing)
names = [name for name in unittest.defaultTestLoader.getTestCaseNames(existing.Controls) if not name.startswith('test_native_') and name != 'test_no_identifier_or_target_input']
suite = unittest.TestSuite((existing.Controls(name) for name in names))
stream = io.StringIO()
result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
if not result.wasSuccessful():
    raise AssertionError(stream.getvalue())
if not (result.testsRun == len(names) and result.testsRun > 0):
    raise AssertionError()
source_tests = result.testsRun
old_teachers = [existing.teacher(), existing.teacher(True)]
old = adapter.legacy.基点複製教材(old_teachers)
with patch.object(subject, 'fit', side_effect=AssertionError('positive old fit must not fall back')):
    same = adapter.基点複製教材(old_teachers)
if not (same.適合 is True and same.記録() == old.記録()):
    raise AssertionError()
checks.append(dict(case='old_positive_fit_and_record_preserved'))
with patch.object(subject, 'consensus', side_effect=AssertionError('old prediction must not fall back')):
    for inp in [existing.sample(), existing.sample(True), [[0, 1], [2, 3]]]:
        if not same.候補(inp, ()) == old.候補(inp, ()):
            raise AssertionError()
checks.append(dict(case='old_positive_outputs_and_holds_preserved'))
material = adapter.基点複製教材(teachers)
if not (material.適合 is False and material.格子モデル == model):
    raise AssertionError()
for pair in teachers:
    if not material.候補(pair['input'], ()) == subject.consensus(pair['input'], model):
        raise AssertionError()
boundary_input, boundary_expected = independent_case()
if not material.候補(boundary_input, ())[0] == boundary_expected:
    raise AssertionError()
checks.append(dict(case='completed_no_fit_extends_existing_family'))
with patch.object(subject, 'fit', side_effect=AssertionError('invalid/duplicate teachers cannot fall back')):
    for pairs in [[], [teachers[0]], [teachers[0], teachers[0]]]:
        actual = adapter.基点複製教材(pairs)
        original = adapter.legacy.基点複製教材(pairs)
        if not actual.記録() == original.記録():
            raise AssertionError()
        if not actual.候補(teachers[0]['input'], ()) == original.候補(teachers[0]['input'], ()):
            raise AssertionError()
checks.append(dict(case='invalid_and_duplicate_teacher_boundaries_preserved'))
_, completed = adapter.legacy.fit_teachers(teachers)
if not adapter.completed_no_fit(teachers, False, completed):
    raise AssertionError()
blocked = [{'failure': 'teacher_certificate_failed'}, {**completed, 'raw_records': completed['raw_records'][:1]}, {**completed, 'raw_pair_fits': [False]}, {**completed, 'raw_records': [{'failure': 'resource_limit'}] * len(teachers)}, {**completed, 'raw_records': [{'failure': 'incomplete_search'}] * len(teachers)}, {**completed, 'raw_records': [None] * len(teachers)}, {**completed, 'complete': False}]
with patch.object(subject, 'fit', side_effect=AssertionError('incomplete or resource result cannot fall back')):
    for detail in blocked:
        with patch.object(adapter.legacy, 'fit_teachers', return_value=(False, detail)):
            actual = adapter.基点複製教材(teachers)
            if not actual.格子モデル is None:
                raise AssertionError()
checks.append(dict(case='certificate_incomplete_and_resource_results_block_fallback', blocked=len(blocked)))
for error_type in (RuntimeError, MemoryError):
    with patch.object(adapter.legacy, 'fit_teachers', side_effect=error_type('legacy failure')):
        try:
            adapter.基点複製教材(teachers)
        except error_type as error:
            if not str(error) == 'legacy failure':
                raise AssertionError()
        else:
            raise AssertionError('legacy exception was swallowed')
    with patch.object(subject, 'fit', side_effect=error_type('extension failure')):
        try:
            adapter.基点複製教材(teachers)
        except error_type as error:
            if not str(error) == 'extension failure':
                raise AssertionError()
        else:
            raise AssertionError('extension exception was swallowed')
checks.append(dict(case='legacy_and_extension_exceptions_propagate'))
print(json.dumps({'tests_run': len(checks) + source_tests, 'successful': True}, separators=(',', ':')))
