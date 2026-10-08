#!/usr/bin/env python3
"""NEW ordinary teacher/contrast check; never reads task queries or solutions."""
import argparse
import copy
import importlib
import json
from pathlib import Path
import sys
import types

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "平行線基準長資料"


def package(name, paths):
    module = types.ModuleType(name)
    module.__path__ = [str(path) for path in paths]
    sys.modules[name] = module
    return importlib.import_module(name + '.疎点転写教材')


def horizontal(lengths):
    grid = [[0] * 10 for _ in range(10)]
    for i, length in enumerate(lengths):
        for c in range(1, length + 1):
            grid[1 + 2 * i][c] = i + 1
    return grid


def sparse_pair(size, first, last):
    source = [[0] * size for _ in range(size)]
    target = copy.deepcopy(source)
    source[first[0]][first[1]] = source[last[0]][last[1]] = 2
    dr = (last[0] > first[0]) - (last[0] < first[0])
    dc = (last[1] > first[1]) - (last[1] < first[1])
    for step in range(max(abs(last[0] - first[0]), abs(last[1] - first[1])) + 1):
        target[first[0] + dr * step][first[1] + dc * step] = 2
    return {'input': source, 'output': target}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    old = package('_new072_baseline', [DATA / 'reference', args.base / '接続/ARC2'])
    new = package('_new072_candidate', [args.base / '接続/ARC2'])
    core = importlib.import_module('_new072_candidate.平行線基準長候補')
    teachers = json.loads((DATA / 'teachers.json').read_text())['train']
    before = copy.deepcopy(teachers)
    previous = old.疎点転写教材(teachers)
    current = new.疎点転写教材(teachers)
    previous_matches = [previous.候補(pair['input'], {})[0] == pair['output'] for pair in teachers]
    current_matches = [current.候補(pair['input'], {})[0] == pair['output'] for pair in teachers]
    assert current_matches == [True] * len(teachers)
    assert teachers == before and current.モデル is None and current.長さ参照モデル is not None
    assert old.fit_teachers(teachers)[1]['policy_record']['failure'] == 'sparse_point_train_not_expansive'
    passed = ['all_three_isolated_teachers', 'completed_original_no_fit_trigger']

    def predict(grid):
        return current.候補(grid, {})

    grid = horizontal([2, 4, 4, 6])
    output, record = predict(grid)
    assert output == horizontal([4, 4, 4, 4])
    assert len(record['reference_identities']) == 2 and record['interpretation_count'] == 2
    passed.append('even_tied_reference_identities_retained')
    output, record = predict(horizontal([2, 3, 4, 6]))
    assert output is None and record['failure'] == 'length_reference_whole_grids_disagree'
    passed.append('even_reference_disagreement_holds')
    grid = horizontal([4, 4, 4, 4])
    output, record = predict(grid)
    assert output == grid and len(record['endpoint_planes']) == 2
    assert record['interpretation_count'] == 4
    passed.append('both_common_endpoint_planes_retained')
    malformed = horizontal([2, 4, 4, 6])
    malformed[2][1] = 1
    output, record = predict(malformed)
    assert output is None and record['failure'] == 'component_is_not_full_line'
    passed.append('whole_non_line_component_holds')
    clipped = [[0] * 8 for _ in range(8)]
    for color, end, length in [(1, (7, 3), 2), (2, (5, 5), 5), (3, (3, 7), 2)]:
        for step in range(length):
            clipped[end[0] - step][end[1] - step] = color
    output, record = predict(clipped)
    assert output is None and record['failure'] == 'reference_copy_failed'
    passed.append('failed_out_of_bounds_copy_holds')

    positive = [sparse_pair(7, (2, 1), (2, 5)), sparse_pair(8, (1, 3), (5, 3))]
    baseline_positive = old.疎点転写教材(positive)
    candidate_positive = new.疎点転写教材(positive)
    assert baseline_positive.モデル is not None
    assert baseline_positive.記録() == candidate_positive.記録()
    assert candidate_positive.長さ参照モデル is None
    for pair in positive + [sparse_pair(8, (1, 1), (5, 5))]:
        expected = baseline_positive.候補(pair['input'], {})
        assert expected[0] == pair['output']
        assert candidate_positive.候補(pair['input'], {}) == expected
    passed.append('old_successful_fit_and_full_render_records_unchanged')
    wrong_shape = copy.deepcopy(positive)
    wrong_shape[0]['output'].pop()
    rejected = new.疎点転写教材(wrong_shape)
    assert rejected.モデル is None and rejected.長さ参照モデル is None
    passed.append('other_original_no_fit_does_not_open_fallback')

    def fail(*args, **kwargs):
        raise RuntimeError('intentional_contrast_exception')

    original_fit = new.fit_teachers
    new.fit_teachers = fail
    try:
        try:
            new.疎点転写教材(teachers)
        except RuntimeError as error:
            assert str(error) == 'intentional_contrast_exception'
        else:
            raise AssertionError('original fit exception swallowed')
    finally:
        new.fit_teachers = original_fit
    original_copy = core.shifted_sparse_point_mask
    core.shifted_sparse_point_mask = fail
    try:
        try:
            predict(horizontal([2, 4, 4, 6]))
        except RuntimeError as error:
            assert str(error) == 'intentional_contrast_exception'
        else:
            raise AssertionError('copy exception swallowed')
    finally:
        core.shifted_sparse_point_mask = original_copy
    passed.append('fit_and_copy_exceptions_propagate')
    summary = {'status': 'NEW_RECONSTRUCTION_CHECK_PASS', 'successful': True, 'tests_run': len(passed), 'passed': passed,
               'teacher_previous': previous_matches, 'teacher_current': current_matches,
               'teacher_exact_delta': sum(current_matches) - sum(previous_matches),
               'scope': 'isolated train pairs and new ordinary contrasts only; no query score'}
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    main()
