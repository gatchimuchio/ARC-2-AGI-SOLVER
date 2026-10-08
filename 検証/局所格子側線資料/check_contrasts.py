"""Ordinary equivariances, incomplete ownership, and failure-first consensus."""
import json
import resource
import sys
from pathlib import Path
import os
import tempfile
from copy import deepcopy

resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
OUT = Path(os.environ.get('ARC134_EVIDENCE_DIR', tempfile.mkdtemp(prefix='arc134-check-')))
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(BASE.parents[1]))
from 接続.ARC2 import 局所格子側線候補 as candidate

teachers = json.loads((BASE/'teachers-only.json').read_text())['train']
model = (0, 1, 3, 'ends', 1)
results = []


def check(name, passed, **record):
    results.append(dict(name=name, passed=passed, **record))
    assert passed, name


def rotate(grid):
    return [list(row) for row in zip(*grid[::-1])]


rotated = [{key: rotate(value) for key, value in pair.items()} for pair in teachers]
check('rotation_with_changed_checkerboard_phase',
      all(candidate.predict(p['input'], [model])[0] == p['output'] for p in rotated))
palette = {0: 6, 1: 9, 3: 2, 8: 7, 2: 4, 4: 5}
recoloured = [{key: [[palette[v] for v in row] for row in value] for key, value in pair.items()}
              for pair in teachers]
models, fitted = candidate.fit(recoloured)
check('bijective_palette_remapping_and_refit', models == ((6, 9, 2, 'ends', 1),)
      and all(candidate.predict(p['input'], models)[0] == p['output'] for p in recoloured),
      retained_models=models, declared_models=len(fitted['declared_models']))

for name, cell, colour, expected in [
        ('broken_side_bar', (8, 8), 1, 'side_not_complete_monochrome_bar'),
        ('broken_frame', (8, 6), 1, 'incomplete_lattice_rectangle_frame'),
        ('unowned_payload', (0, 0), 7, 'no_complete_local_scene_ownership')]:
    grid = deepcopy(teachers[0]['input'])
    grid[cell[0]][cell[1]] = colour
    output, record = candidate.render(grid, model)
    check(name, output is None and record.get('failure') == expected
          and (name != 'unowned_payload' or record['strict_boundary']['failure'] == 'unowned_active_cells'),
          failure=record.get('failure'))

output, record = candidate.predict(teachers[0]['input'], [model, (0, 1, 3, 'ends', -1)])
check('one_retained_failure_holds_everything', output is None
      and record.get('failure') == 'retained_model_failed' and len(record['returns']) == 2)
output, record = candidate.predict(teachers[0]['input'], [model, (0, 1, 3, 'all', 1)])
check('different_full_grids_hold_everything', output is None
      and record.get('failure') == 'retained_model_disagreement' and len(record['returns']) == 2)

engine = candidate.execute_graph


def resource_failure(*args, **kwargs):
    raise MemoryError('deliberate ordinary propagation check')


candidate.execute_graph = resource_failure
propagated = False
try:
    candidate.predict(teachers[0]['input'], [model])
except MemoryError:
    propagated = True
finally:
    candidate.execute_graph = engine
check('resource_exception_is_not_semantic_hold', propagated)
(OUT/'contrast-result.json').write_text(json.dumps(results, indent=2)+'\n')
print(json.dumps(dict(successful=True, tests_run=len(results))))
