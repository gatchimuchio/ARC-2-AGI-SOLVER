"""NEW small teacher/contrast check. Execute only in the lead's serial slot.

Reads the isolated teachers and candidate source, and imports accepted primitives
from --base. No query, solutions, score artifacts, broad search, or fixture sweep.
"""
from __future__ import annotations
import argparse
import importlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).resolve().parent / "標識二領域資料"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, default=ROOT)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(args.base.resolve()))
    old = load('接続.ARC2.四欄反復旧対照', DATA / '四欄反復旧実装.py')
    core = load('接続.ARC2.標識二領域再構成', args.base/'接続/ARC2/標識二領域再構成.py')
    candidate = load('接続.ARC2.四欄反復再構成検査', args.base/'接続/ARC2/四欄反復教材.py')
    train = json.loads((DATA/'teachers.json').read_text())['train']
    before = deepcopy(train)
    previous, old_record = old.fit_teachers(train)
    assert previous is None and old_record['failure'] == 'teacher_mismatch'
    actions, fit = core.fit_teachers(train)
    assert actions, fit
    assert len(fit['action_trials']) == len(core.ACTIONS)
    assert all(len(row['teachers']) == len(train) for row in fit['action_trials'])
    assert all(row['record']['complete'] for trial in fit['action_trials'] for row in trial['teachers'])
    material = candidate.四欄反復教材(train)
    teacher_records = []
    for pair in train:
        out, detail = material.候補(pair['input'], None)
        assert out == pair['output'], detail
        teacher_records.append({'exact': True, 'record': detail})
    assert train == before

    # One NEW bent-wall contrast made from the fourth public training input.
    # The expected destination below is literal, reviewed before execution.
    bent = deepcopy(train[3]['input'])
    for r in range(5):
        for c in range(5): bent[r+1][c+1] = 0
    wall = {(2,0), (2,1), (3,2), (3,3), (3,4)}
    for r, c in wall | {(0,2)}: bent[r+1][c+1] = 1
    expected = deepcopy(bent)
    for r, line in enumerate(('20002', '02020', '33200', '00320', '00300')):
        expected[r+1][19:24] = list(map(int, line))
    bent_before = deepcopy(bent)
    bent_out, bent_record = material.候補(bent, None)
    assert bent_out == expected, bent_record
    assert bent == bent_before
    assert all(row['record']['view']['view'] == 'regional' for row in bent_record['action_returns'])
    assert all(not row['record']['view']['straight_inventory'] for row in bent_record['action_returns'])

    # Existing straight inventory retains its multiple-divider hold branch.
    multiple = deepcopy(train[3]['input'])
    for r in range(5): multiple[r+1][3] = 1
    held, multiple_record = material.候補(multiple, None)
    assert held is None
    assert all(row['record']['view']['failure'] == 'multiple_straight_dividers'
               for row in multiple_record['action_returns'])

    # Reuse an existing ordinary four-field positive; no new positive generator.
    controls = load('four_field_existing_controls', args.base/'検証/四欄反復回帰.py')
    original_train = controls.examples()
    with patch.object(core, 'fit_teachers', side_effect=AssertionError('new fallback entered old positive')):
        prior = old.四欄反復教材(original_train)
        current = candidate.四欄反復教材(original_train)
        assert vars(prior) == vars(current) == {'適合': True}
        assert prior.記録() == current.記録()
        for pair in original_train:
            assert prior.候補(pair['input'], None) == current.候補(pair['input'], None)
    with patch.object(core, 'fit_teachers', side_effect=AssertionError('new fallback entered old invalid path')):
        for bad in ([], [train[0]], [train[0], train[0]]):
            assert vars(candidate.四欄反復教材(bad)) == vars(old.四欄反復教材(bad))
    incomplete = {'failure': 'teacher_mismatch', 'complete': False,
                  'teacher_records': [{'exact': False, 'record': {}} for pair in train]}
    with patch.object(candidate, 'fit_teachers', return_value=(None, incomplete)):
        with patch.object(core, 'fit_teachers', side_effect=AssertionError('new fallback entered incomplete path')):
            assert vars(candidate.四欄反復教材(train)) == {'適合': False}
    with patch.object(candidate, 'fit_teachers', side_effect=MemoryError('ordinary interruption')):
        try: candidate.四欄反復教材(train)
        except MemoryError: pass
        else: raise AssertionError('old exception swallowed')
    original_render = core.render
    calls = [0]
    def interrupted_once(grid, action):
        calls[0] += 1
        if calls[0] == 1:
            return None, {'complete': False, 'failure': 'ordinary_partial_return'}
        return original_render(grid, action)
    with patch.object(core, 'render', side_effect=interrupted_once):
        incomplete_actions, incomplete_fit = core.fit_teachers(train)
        assert not incomplete_actions and incomplete_fit['complete'] is False
        assert incomplete_fit['failure'] == 'incomplete_teacher_fit'
    result = {'label': 'NEW reconstruction; not historical recovery',
              'previous_teacher_fit': False, 'current_teacher_exact': len(train),
              'actions_declared': [list(a) for a in core.ACTIONS],
              'retained_actions': [list(a) for a in actions],
              'bent_wall_contrast_exact': True, 'multiple_straight_hold': True,
              'old_positive_and_failure_paths_preserved': True,
              'train_only': True, 'teacher_fit': fit, 'teacher_predictions': teacher_records,
              'bent_wall_prediction': bent_record, 'multiple_straight_prediction': multiple_record}
    output_dir = Path(tempfile.mkdtemp(prefix='new075-regression-'))
    result.update(successful=True, tests_run=8, artifact_directory=str(output_dir), count_scope='Eight existing ordinary check groups: full teachers, bent wall, multiple divider, old positive, invalid teachers, incomplete old fit, old exception, incomplete new action')
    (output_dir/'verification-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in (
        'teacher_fit','teacher_predictions','bent_wall_prediction','multiple_straight_prediction')},ensure_ascii=False))


if __name__ == '__main__':
    main()
