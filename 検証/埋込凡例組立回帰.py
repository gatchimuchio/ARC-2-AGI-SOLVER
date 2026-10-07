"""Portable two-teacher/six-check probe; stdout is one JSON line, no file writes."""
import argparse
import json
from pathlib import Path
import resource
import sys

resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
sys.dont_write_bytecode = True
parser = argparse.ArgumentParser()
parser.add_argument('--base', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
# Namespace-package overlay discovery, not function or class import rebinding.
# Deployment needs no --base; preparation can reuse unchanged accepted helpers.
if args.base is not None:
    sys.path.insert(0, str(args.base.resolve()))
sys.path.insert(0, str(root))
from 接続.ARC2 import 埋込凡例組立候補 as view
from 接続.ARC2 import 標点組立教材 as marked

pairs = json.loads((root/'検証/埋込配色組立/train-pairs.json').read_text())
assert len(pairs) == 2
policy, fit = view.fit_teachers(pairs)
assert policy is not None and fit['teacher_consensus_matches'] == [True, True]
adapted = marked.標点組立教材(pairs)
assert adapted.共有縦横比 is None and adapted.配色規則 == policy
assert marked.fit_teachers(pairs)[1]['failure'] == 'teacher_raw_role_failed'
tests_run = 0
for pair in pairs:
    expected = pair['output']
    assert view.render(pair['input'], policy)[0] == expected
    assert adapted.候補(pair['input'], None)[0] == expected
    tests_run += 1

# 1. Bijective color change, including background.
permutation = {i: (i+3) % 10 for i in range(10)}
for pair in pairs:
    changed = [[permutation[v] for v in row] for row in pair['input']]
    expected = [[permutation[v] for v in row] for row in pair['output']]
    assert view.render(changed, policy)[0] == expected
    assert adapted.候補(changed, None)[0] == expected
tests_run += 1

# 2. Source translation in a larger background canvas.
grid = pairs[0]['input']
padded = [[0]*24 for _ in range(23)]
for r, row in enumerate(grid):
    padded[r+1][2:22] = row
assert view.render(padded, policy)[0] == pairs[0]['output']
assert adapted.候補(padded, None)[0] == pairs[0]['output']
tests_run += 1

# 3. Extra foreground remains owned and blocks the four-piece view.
extra = [row[:] for row in grid]
extra[19][19] = 6
assert view.render(extra, policy)[0] is None
assert adapted.候補(extra, None)[0] is None
tests_run += 1

# 4. All competing complete alternatives survive; disagreement blocks output.
candidates, _ = view.enumerate_models(grid, (1, 1))
all_models = tuple(model for model, values in candidates.items() if values)
output, record = view.render(grid, {'aspect': (1, 1), 'models': all_models})
assert output is None and record['failure'] == 'full_grids_disagree'
assert record['full_grid_count'] > 1
tests_run += 1

# 5. Resource/runtime failure propagates through the view and adapter boundary.
try:
    view.fit_teachers(pairs, budget=1)
except view.AssemblyIncomplete as error:
    assert error.record['failure'] == 'search_budget_incomplete'
    try:
        marked._completed_original_no_fit({'failure': 'teacher_assembly_or_equality_failed',
                                           'searches': [error.record]})
    except marked.ExistingAssemblyIncomplete:
        pass
    else:
        raise AssertionError('adapter_enabled_after_incomplete_original_search')
else:
    raise AssertionError('budget_failure_swallowed')
tests_run += 1

# 6. The original complete marker-assembly positive delegates unchanged.
original_pairs = []
for pair in pairs:
    role = view.observe_roles(pair['input'])[0]
    parsed = view.marker_view(pair['input'], role, 0)
    expected, record = marked.search_assemblies(parsed, (1, 1))
    assert expected is not None and record['complete']
    marked_grid = [row[:] for row in pair['input']]
    for r, c, _ in role['palette_cells']:
        marked_grid[r][c] = role['body']
    r, c = view.corner_cells(role['host_bbox'])[0]
    marked_grid[r][c] = role['palette'][0][0]
    original_pairs.append({'input': marked_grid, 'output': expected})
original = marked.既存標点組立教材(original_pairs)
wrapped = marked.標点組立教材(original_pairs)
assert wrapped.共有縦横比 == original.共有縦横比 == (1, 1)
assert wrapped.__dict__ == original.__dict__ == {'共有縦横比': (1, 1)}
assert wrapped.記録() == original.記録()
for pair in original_pairs:
    assert wrapped.候補(pair['input'], None) == original.候補(pair['input'], None)
tests_run += 1
print(json.dumps({'tests_run': tests_run, 'successful': True}, separators=(',', ':')))
