"""Public replay of nine frozen view groups and one ordinary old-positive group.

Defaults are this checkout and the adjacent teacher-only data. No query is read.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument('--teachers', type=Path, default=Path(__file__).resolve().parent / '多類枠倍率置換資料/teachers-only.json')
args = parser.parse_args()
root = args.root.resolve()
sys.path.insert(0, str(root))
from 接続.ARC2 import 多類枠倍率置換 as p
from 接続.ARC2 import 倍率置換教材 as family
old = p.strict
teacher_bytes = args.teachers.read_bytes()
assert hashlib.sha256(teacher_bytes).hexdigest() == '84b7afad0044fdf920a5e42fe42efc8b7dfefc0b74d270e180c801d91db40cd0'
teachers = json.loads(teacher_bytes)['a251c730']['train']
core_source = (root / '接続/ARC2/多類枠倍率置換.py').read_text()
strict_source = (root / '接続/ARC2/厳格枠倍率置換.py').read_text()
assert hashlib.sha256(core_source.replace('from . import 厳格枠倍率置換 as strict', 'import strict081 as strict').encode()).hexdigest() == '78ad6e66079bbeaaa60c76bd68b18c41b97e0146fd4856c7414ff6151aeb43c9'
assert hashlib.sha256(strict_source.replace('from . import ', 'from 接続.ARC2 import ').replace('from .', 'from 接続.ARC2.').encode()).hexdigest() == '37533f5e86f3aafad37b44185531fe0c449bfe1ce792c863f906a580df034ae9'
models, fitted = p.fit_teachers(teachers)
assert p.fit_teachers is old.fit_teachers
assert p.MODELS is old.MODELS and p.CROPS is old.CROPS
assert models == (('repeated', 'marker', 'border'),)
results = []
family_view = family.倍率置換教材(teachers)
assert family_view.適合 is False and family_view.枠モデル群 == models
assert family_view.枠適合記録['complete'] is True
assert len(family_view.枠適合記録['raw_records']) == len(teachers)
assert all(r['failure'] == 'primitive_group_count_not_two'
           for r in family_view.枠適合記録['raw_records'])

def bound(grid):
    answer = family_view.候補(grid, None)
    assert answer == p.render(grid, models)
    return answer

for i, teacher in enumerate(teachers):
    actual = bound(teacher['input'])
    assert actual == old.render(teacher['input'], models)
    assert actual[0] == teacher['output']
    results.append({'name': f'teacher_{i}', 'exact': True, 'record_unchanged': True})


def example(markers=((5, 5, 2), (12, 8, 2), (18, 5, 3)), second_repeated=True):
    grid = [[0] * 30 for _ in range(26)]
    def frame(box, border, background):
        r0, c0, r1, c1 = box
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                grid[r][c] = border if r in (r0, r1) or c in (c0, c1) else background
    frame((1, 1, 24, 12), 9, 1)
    frame((1, 16, 24, 28), 6, 4)
    shapes = {2: ((0, 0, 2), (-1, 0, 8), (-1, 1, 8)),
              3: ((0, 0, 3), (1, 0, 7), (1, -1, 7), (-1, 0, 7))}
    sources = [(5, 20, 2), (11, 20, 2), (17, 24, 3)]
    if second_repeated:
        sources.append((21, 20, 3))
    for r, c, color in sources:
        for dr, dc, value in shapes[color]:
            grid[r + dr][c + dc] = value
    for r, c, color in markers:
        grid[r][c] = color
    # Independent known-shape construction, not a call to proposal/motif helpers.
    expected = [row[:] for row in grid]
    for r, c, color in sources:
        for dr, dc, value in shapes[color]:
            expected[r + dr][c + dc] = 4
        expected[r][c] = color
    for r, c, color in markers:
        for dr, dc, value in shapes[color]:
            expected[r + dr][c + dc] = value
    return grid, expected


grid, expected = example()
old_out, old_record = old.render(grid, models)
assert old_out is None and p._zero_view_gap(old_record)
actual, detail = bound(grid)
assert actual == [row[1:13] for row in expected[1:25]]
assert detail['full_grid_count'] == 1
assert p.render(grid, [('repeated', 'both', 'whole_input')])[0] == expected
results.append({'name': 'two_class_swap_exact', 'passed': True,
                'old_zero_view': True, 'class_matchings': [v['matching_count'] for v in detail['views']],
                'whole_input_exact': True})

# A third atomic color has no whole exemplar class: never discard it.
unowned = [row[:] for row in grid]
unowned[22][9] = 5
actual, detail = bound(unowned)
assert actual is None and detail['failure'] == 'retained_model_has_no_output'
assert any(x.get('failure') == 'no_complete_class_matching' for x in detail['rejected_pairs'])
results.append({'name': 'unmatched_class_hold', 'passed': True, 'failure': detail['failure']})

# Repeated support is required for each class, not merely the whole frame.
unsupported, _ = example(second_repeated=False)
actual, detail = bound(unsupported)
assert actual is None and detail['failure'] == 'retained_model_has_no_output'
results.append({'name': 'per_class_repeated_support_hold', 'passed': True, 'failure': detail['failure']})

# Inputs are separate components, but simultaneous outputs clash at (8, 6).
collision, _ = example(markers=((9, 5, 2), (7, 6, 3)))
actual, detail = bound(collision)
assert actual is None and detail['failure'] == 'retained_view_unresolved'
assert any(a['record'].get('failure') == 'different_class_proposals_overlap'
           for v in detail['views'] for a in v['normalizations'])
results.append({'name': 'different_class_collision_hold', 'passed': True, 'failure': detail['failure']})

# Both compound classes contain both marker colors. Keep both whole matchings.
ambiguous, _ = example()
for r in range(2, 24):
    for c in range(17, 28):
        ambiguous[r][c] = 4
glyphs = [((0, 0, 2), (0, 1, 8), (1, 0, 3)),
          ((0, 0, 2), (1, 0, 7), (1, 1, 3), (2, 0, 7))]
for shape, origins in zip(glyphs, [((4, 20), (9, 20)), ((15, 23), (20, 20))]):
    for r, c in origins:
        for dr, dc, value in shape:
            ambiguous[r + dr][c + dc] = value
actual, detail = bound(ambiguous)
assert actual is None and detail['failure'] == 'retained_full_grids_disagree'
assert detail['full_grid_count'] == 2
assert [v['matching_count'] for v in detail['views']] == [2]
results.append({'name': 'all_class_matchings_full_grid_hold', 'passed': True,
                'matchings': 2, 'full_grid_count': 2, 'failure': detail['failure']})

# Old action-bearing successes, support HOLD and boundary HOLD return verbatim.
single = [row[:] for row in teachers[0]['input']]
for r in range(8, 11):
    for c in range(5, 8):
        single[r][c] = 1
assert bound(single) == old.render(single, models)
assert bound(single)[0] is None
results.append({'name': 'old_single_exemplar_hold_unchanged', 'passed': True})
boundary = [row[:] for row in teachers[0]['input']]
frames = old.frames(boundary)
marker = next(f for f in frames if f['role'] == 'marker')
(r, c), color = next(iter(marker['payload'].items()))
boundary[r][c] = marker['background']
boundary[marker['bbox'][0] + 1][c] = color
before = old.render(boundary, models)
assert before[0] is None and before[1]['failure'] == 'retained_view_unresolved'
assert bound(boundary) == before
results.append({'name': 'old_unresolved_boundary_unchanged', 'passed': True})


# Existing ordinary positive fixture from 倍率置換回帰.py, without HDS changes.
A = ((1, 1, 1), (None, 2, None))
B = ((None, 2, None), (3, 3, 3))
def place(items):
    result = [[0] * 28 for _ in range(24)]
    for pattern, scale, top, left in items:
        for r, row in enumerate(pattern):
            for c, value in enumerate(row):
                if value is None:
                    continue
                for dr in range(scale):
                    for dc in range(scale):
                        result[top + r * scale + dr][left + c * scale + dc] = value
    return result
positive_pairs = [
    {'input': place([(A, 1, 2, 2), (B, 2, 10, 10)]),
     'output': place([(B, 1, 3, 2), (A, 2, 8, 10)])},
    {'input': place([(A, 2, 1, 2), (B, 1, 12, 16), (A, 1, 15, 3)]),
     'output': place([(B, 2, 3, 2), (A, 1, 11, 16), (B, 1, 16, 3)])},
]
positive = family.倍率置換教材(positive_pairs)
assert positive.__dict__ == {'適合': True}
assert positive.記録() == {'全教師再現': True}
for pair in positive_pairs:
    assert positive.候補(pair['input'], None) == family.guarded_render(pair['input'])
    assert positive.候補(pair['input'], None)[0] == pair['output']
results.append({'name': 'old_positive_state_output_record_delegation', 'passed': True})
assert len(results) == 10
print(json.dumps({'tests_run': len(results), 'successful': True,
                  'all_successful': True, 'checks': results}, ensure_ascii=False))
