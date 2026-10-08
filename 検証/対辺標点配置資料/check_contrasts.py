"""Authorized teachers plus ordinary contrasts; no official query or scorer."""
import copy
import hashlib
import inspect
import json
import resource
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import paired_border_partial_view as m

resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
HERE = Path(__file__).parent
EXPECTED_CORE = 'dbc768521416ada613a7a41aeb394a38f3ec63f17b89cd69bd221aaeffb04e55'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(HERE/'frozen126.py') == EXPECTED_CORE
teachers = json.loads((HERE/'teachers-only.json').read_text())['train']
started = time.process_time()
assert m.fit is m.core.fit and m.act is m.core.act
programs, fit_record = m.fit(teachers)
assert len(programs) == 4 and fit_record['program_count'] == 8
checks = []

for i, teacher in enumerate(teachers):
    assert m.consensus(teacher['input'], programs) == m.core.consensus(teacher['input'], programs)
    assert m.consensus(teacher['input'], programs)[0] == teacher['output']
    for program in m.PROGRAMS:
        assert m.render(teacher['input'], program) == m.core.render(teacher['input'], program)
    checks.append(dict(name='teacher_'+str(i+1)+'_all_program_record_parity', passed=True))

teacher_result = dict(teachers_exact=3, teachers_total=3, program_count=8,
                      retained_programs=programs, exact_fit_and_act_aliases=True,
                      all_program_output_and_record_parity=True)
(HERE/'teacher-result.json').write_text(json.dumps(teacher_result, indent=2)+'\n')

# Freeze source and callable API immediately after the authorized teacher check.
# The remaining checks exercise this already frozen code without editing it.
frozen_files = ('frozen126.py', 'paired_border_partial_view.py',
                'teachers-only.json', 'check_contrasts.py')
freeze = dict(candidate='NEW129', accepted_head='a6849619', accepted_result='93/128',
              status='frozen_teacher_complete_before_contrasts',
              frozen_at_utc=datetime.now(timezone.utc).isoformat(),
              source_sha256=sha(HERE/'paired_border_partial_view.py'),
              frozen126_sha256=EXPECTED_CORE,
              files={name: sha(HERE/name) for name in frozen_files},
              api={name: str(inspect.signature(getattr(m, name)))
                   for name in ('fit', 'act', 'parse', 'render', 'consensus')},
              retained_programs=programs, official_query_read=False,
              official_solutions_read=False, scoring_run=False,
              exposure=['Parent-reported frozen126 input-only HOLD reasons: '
                        'unpaired_or_blank_perimeter and no_corner_frame_or_blank_interior.',
                        'Parent-reported input-only observation: unrelated colors absent '
                        'from source masks break opposite-edge equality; an unrelated '
                        'corner decoration breaks corner uniformity. No targets or scores.'])
(HERE/'freeze.json').write_text(json.dumps(freeze, indent=2)+'\n')


def expect(name, grid, expected=None, failure=None):
    out, record = m.consensus(grid, programs)
    assert out == expected, (name, record)
    if failure is not None:
        assert record.get('failure') == failure, (name, record)
    checks.append(dict(name=name, passed=True, failure=record.get('failure')))


# Both edits use a color absent from the first teacher's complete source masks.
base = teachers[0]
opposite = copy.deepcopy(base['input'])
opposite[9][-1] = 5
expected = copy.deepcopy(base['output'])
expected[9][-1] = 5
assert not m.core.parse(opposite)[0]
expect('unrelated_opposite_decoration_stays_static', opposite, expected)

decorated = copy.deepcopy(opposite)
decorated[0][4] = 5
expected_corner = copy.deepcopy(expected)
expected_corner[0][4] = 5
roles, record = m.parse(decorated)
assert len(roles) == 2 and {role['frame'] for role in roles} == {3, 5}
for role in roles:
    assert (0, 4, 5) in role['static_perimeter']
    assert (9, 17, 5) in role['static_perimeter']
    assert set(role['masks']) == {4, 7}
for orientation in m.ROTATIONS:
    transform = lambda grid: m.core.transform_grid_by_name(grid, orientation)
    expect('unrelated_corner_all_frames_'+orientation, transform(decorated), transform(expected_corner))

# A relevant key on either member of an opposite pair must still be paired.
for name, row, col, color in (('left', 4, 4, 5), ('right', 4, 17, 5),
                             ('top', 0, 9, 5), ('bottom', 11, 9, 5)):
    grid = copy.deepcopy(decorated)
    grid[row][col] = color
    roles, record = m.parse(grid)
    assert not roles and any(p.get('failure') == 'unpaired_source_key' for p in record['probes'])
    expect('applicable_key_conflict_'+name, grid, failure='retained_program_failed')

corner_key = copy.deepcopy(decorated)
corner_key[0][4] = 4
roles, record = m.parse(corner_key)
assert not roles and any(p.get('failure') == 'ambiguous_source_key_corner' for p in record['probes'])
expect('source_key_corner_holds', corner_key, failure='retained_program_failed')

# Old structural roles prohibit fallback, including old action failure.
crossing = copy.deepcopy(base['input'])
crossing[4][4] = crossing[4][-1] = 3
crossing[1][4] = crossing[1][-1] = 4
assert m.core.parse(crossing)[0]
with patch.object(m, '_partial_parse', side_effect=AssertionError('forbidden fallback')):
    assert m.consensus(crossing, programs) == m.core.consensus(crossing, programs)
    assert m.consensus(crossing, programs)[0] is None
checks.append(dict(name='old_action_failure_delegates_unchanged', passed=True))

disagreement = copy.deepcopy(base['input'])
for row in disagreement:
    row[:3] = [0]*3
for r in range(3):
    disagreement[r][:3] = [7]*3
for r, row in enumerate([[0, 4, 0], [4, 4, 4], [0, 4, 0]]):
    disagreement[r+8][:3] = row
with patch.object(m, '_partial_parse', side_effect=AssertionError('forbidden fallback')):
    assert m.consensus(disagreement, programs) == m.core.consensus(disagreement, programs)
    assert m.consensus(disagreement, programs)[1]['failure'] == 'program_grid_disagreement'
checks.append(dict(name='old_program_ambiguity_delegates_unchanged', passed=True))

# No frame is discarded because it fails or disagrees during the exact action.
for first, second, expected_failure in (
        (None, expected_corner, 'retained_role_failed'),
        (expected_corner, base['output'], 'role_grid_disagreement')):
    with patch.object(m, 'act', side_effect=[(first, {}), (second, {})]) as action:
        out, record = m.render(decorated, programs[0])
        assert out is None and action.call_count == 2
        assert record['failure'] == expected_failure
checks.append(dict(name='all_frame_actions_reduce_failures_and_disagreement', passed=True))

with patch.object(m, 'render', side_effect=[(None, {}), (expected_corner, {})]) as render:
    out, record = m.consensus(decorated, programs[:2])
    assert out is None and render.call_count == 2
checks.append(dict(name='all_retained_programs_finish_after_failure', passed=True))

assert all(sha(HERE/name) == digest for name, digest in freeze['files'].items())
result = dict(all_passed=True, checks=checks, cpu_seconds=time.process_time()-started,
              max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              source_still_matches_freeze=True, retained_programs=programs)
(HERE/'contrast-result.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
