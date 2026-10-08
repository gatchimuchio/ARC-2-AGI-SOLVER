"""Ordinary synthetic scenes only; no query, target, or evaluator access."""
import hashlib
import json
import resource
import sys
from copy import deepcopy
from pathlib import Path
import os
import tempfile

resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
OUT = Path(os.environ.get('ARC134_EVIDENCE_DIR', tempfile.mkdtemp(prefix='arc134-check-')))
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(BASE.parents[1]))
from 接続.ARC2 import 局所格子側線候補 as candidate

MODEL = (0, 1, 3, 'ends', 1)
results = []


def check(name, passed, **record):
    results.append(dict(name=name, passed=bool(passed), **record))
    assert passed, name


def blank(h=30, w=30):
    return [[0 if (r+c) % 2 else 1 for c in range(w)] for r in range(h)]


def put_frame(grid, bounds, colour, sides):
    u0, v0, u1, v1 = bounds
    for u in range(u0, u1+1):
        for v in range(v0, v1+1):
            if u in (u0, u1) or v in (v0, v1):
                r, c = u+v, u-v
                assert grid[r][c] == 1
                grid[r][c] = colour
    for side, cells, normal in candidate._side_specs(bounds):
        if side not in sides:
            continue
        for u, v in cells:
            r, c = u+v, u-v
            if 0 <= r < len(grid) and 0 <= c < len(grid[0]):
                assert grid[r][c] in (1, sides[side])
                grid[r][c] = sides[side]


def two_frames(clipped=False):
    grid = blank()
    put_frame(grid, (6, -1, 8, 1), 3, {'u_low': 8, 'v_low': 8})
    bounds = (23, 2, 25, 4) if clipped else (21, -1, 23, 1)
    put_frame(grid, bounds, 8, {'u_high': 4, 'v_high': 4})
    return grid


teachers = json.loads((BASE/'teachers-only.json').read_text())['train']
old_models, old_fit = candidate.strict.fit(teachers)
models, fitting = candidate.fit(teachers)
check('strict_fit_and_all_teacher_model_returns_unchanged',
      models == old_models and fitting == old_fit and candidate.fit is candidate.strict.fit)
check('strict_teacher_render_records_unchanged',
      all(candidate.render(t['input'], m) == candidate.strict.render(t['input'], m)
          for t in teachers for m in [(0, 1, 3, mode, sign)
                                      for mode in ('ends', 'all') for sign in (-1, 1)]))

for name, cell, colour in [('broken_side', (8, 8), 1), ('broken_frame', (8, 6), 1)]:
    grid = deepcopy(teachers[0]['input'])
    grid[cell[0]][cell[1]] = colour
    check(name+'_preserves_strict_failure', candidate.render(grid, MODEL)
          == candidate.strict.render(grid, MODEL))

grid = two_frames()
old, boundary = candidate.strict.render(grid, MODEL)
output, record = candidate.render(grid, MODEL)
graph = record['view_and_graph']
check('all_differently_coloured_frames_with_cross_object_colour_reuse',
      old is None and boundary['failure'] == 'unowned_active_cells'
      and output is not None and graph['cover_count'] == 1
      and len(graph['mandatory_frames']) == 2
      and len(graph['ownership_covers'][0]) == 4,
      output=output, record=record)
check('original_model_and_explicit_local_role_maps',
      record['model'] == list(MODEL)
      and [f['local_role_map']['frame'] for f in graph['mandatory_frames']]
      == [{'input': 3, 'fitted': 3}, {'input': 8, 'fitted': 3}])
check('complete_global_foreground_preservation',
      graph['owned_pixel_count'] == 900 and graph['preserved_foreground']
      and all(output[r][c] == grid[r][c] for r in range(30) for c in range(30)
              if grid[r][c] != 1))

rotated = [list(row) for row in zip(*grid[::-1])]
expected_rotated = [list(row) for row in zip(*output[::-1])]
check('local_scene_rotation_equivariance', candidate.render(rotated, MODEL)[0] == expected_rotated)
palette = {0: 6, 1: 9, 3: 2, 8: 7, 2: 4, 4: 5}
recoloured = [[palette[c] for c in row] for row in grid]
expected_recoloured = [[palette[c] for c in row] for row in output]
check('local_scene_bijective_palette_equivariance',
      candidate.render(recoloured, (6, 9, 2, 'ends', 1))[0] == expected_recoloured)

clipped = two_frames(clipped=True)
clipped_output, clipped_record = candidate.render(clipped, MODEL)
clipped_graph = clipped_record['view_and_graph']
missing = clipped_graph['offcanvas_source_obligations']
check('clipped_sources_have_nonentry_proofs_and_no_fabricated_states',
      clipped_output is not None and len(missing) == 2
      and all(p['cannot_enter_canvas'] and not p['observed'] and not p['executed'] for p in missing)
      and len(clipped_graph['initial']) == 6,
      record=clipped_record)
expected_initial = []
for source_id, candidate_id in enumerate(clipped_graph['ownership_covers'][0]):
    bar = clipped_graph['candidate_bars'][candidate_id]
    dr, dc = bar['normal']
    for r, c in (bar['full_cells'][0], bar['full_cells'][-1]):
        if 0 <= r < 30 and 0 <= c < 30:
            expected_initial.append([source_id, r+dr, c+dc, dr, dc, bar['colour']])
check('clipping_keeps_true_full_bar_endpoints', clipped_graph['initial'] == expected_initial)

unsafe, unsafe_record = candidate.render(clipped, (0, 1, 3, 'ends', -1))
check('unobserved_inward_source_holds_before_graph',
      unsafe is None and unsafe_record['failure'] == 'unobserved_source_may_enter_canvas'
      and len(unsafe_record['offcanvas_source_obligations']) == 2
      and 'initial' not in unsafe_record, record=unsafe_record)

all_output, all_record = candidate.render(clipped, (0, 1, 3, 'all', 1))
check('all_emission_accounts_for_every_missing_source',
      all_output is not None and len(all_record['view_and_graph']['offcanvas_source_obligations']) == 2
      and len(all_record['view_and_graph']['initial']) == 10)

ambiguous = blank()
put_frame(ambiguous, (6, -1, 8, 1), 3, {'u_high': 8, 'v_low': 8})
put_frame(ambiguous, (10, -1, 12, 1), 2, {'u_low': 8, 'v_high': 4})
engine = candidate.execute_graph


def forbidden_graph(*args, **kwargs):
    raise AssertionError('ambiguous ownership must not execute')


candidate.execute_graph = forbidden_graph
try:
    ambiguous_output, ambiguous_record = candidate.render(ambiguous, MODEL)
finally:
    candidate.execute_graph = engine
check('all_ownership_covers_retained_and_ambiguity_holds_before_execution',
      ambiguous_output is None and ambiguous_record['failure'] == 'ambiguous_local_scene_ownership'
      and ambiguous_record['cover_count'] == 2, record=ambiguous_record)

no_bar = blank()
put_frame(no_bar, (6, -1, 8, 1), 3, {'u_low': 8, 'v_low': 8})
put_frame(no_bar, (21, -1, 23, 1), 2, {})
no_bar_output, no_bar_record = candidate.render(no_bar, MODEL)
check('frame_without_source_is_not_silently_skipped',
      no_bar_output is None and no_bar_record['failure'] == 'no_complete_local_scene_ownership'
      and len(no_bar_record['mandatory_frames']) == 2)

partial = two_frames()
partial[23][25] = 1
partial_output, partial_record = candidate.render(partial, MODEL)
check('partial_oncanvas_side_is_not_canvas_clipping',
      partial_output is None and partial_record['failure'] == 'no_complete_local_scene_ownership')

unowned = deepcopy(teachers[0]['input'])
unowned[0][0] = 7
unowned_output, unowned_record = candidate.render(unowned, MODEL)
check('isolated_payload_remains_hold_with_original_boundary',
      unowned_output is None and unowned_record['failure'] == 'no_complete_local_scene_ownership'
      and unowned_record['strict_boundary']['failure'] == 'unowned_active_cells')

colliding = blank()
put_frame(colliding, (6, -1, 8, 1), 3, {'u_high': 8})
put_frame(colliding, (13, -1, 15, 1), 2, {'v_high': 4})
collision_output, collision_record = candidate.render(colliding, MODEL)
check('global_graph_preserves_cross_object_causal_collisions',
      collision_output is None and collision_record['view_and_graph']['failure'] == 'causal_collision'
      and collision_record['view_and_graph']['failed_states'], record=collision_record)

consensus, consensus_record = candidate.predict(grid, [MODEL, (0, 1, 3, 'ends', -1)])
check('every_retained_model_survives_and_failure_holds',
      consensus is None and consensus_record['failure'] == 'retained_model_failed'
      and len(consensus_record['returns']) == 2)


def memory_failure(*args, **kwargs):
    raise MemoryError('ordinary propagation test')


candidate.execute_graph = memory_failure
propagated = False
try:
    candidate.predict(grid, [MODEL])
except MemoryError:
    propagated = True
finally:
    candidate.execute_graph = engine
check('local_graph_resource_errors_propagate', propagated)

report = dict(scope='teacher-derived and ordinary synthetic contrasts only',
              source_sha256=hashlib.sha256((BASE.parents[1]/'接続/ARC2/局所格子側線候補.py').read_bytes()).hexdigest(),
              checks=results)
(OUT/'local-scene-result.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(dict(successful=True, tests_run=len(results))))
