"""Synthetic grids and labelled injected controls for support constraints."""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / "HDS/学習系統/v0.4.2")]
from 接続.ARC2 import 支持構造教材 as probe
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 課題を解く
registered = []


def check(name, kind='synthetic_grid'):
    def decorator(fn):
        registered.append((name, fn))
        return fn
    return decorator


def digest(x):
    return sha256(json.dumps(x, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def table(height=9, width=11, cue=2, left=2, right=3, beam=4, background=0):
    """Independent one-bridge construction with four-cell floor posts."""
    top, lc, rc = (height - 4, 2, width - 3)
    g = [[background] * width for _ in range(height)]
    expected = deepcopy(g)
    g[0][0] = expected[0][0] = cue
    for r in range(top, height):
        g[r][lc], g[r][rc] = (left, right)
        if left != cue:
            expected[r][lc] = left
        if right != cue:
            expected[r][rc] = right
    for c in range(lc + 1, rc):
        g[top][c] = beam
        if beam != cue:
            expected[height - 1 if cue in (left, right) else top][c] = beam
    return (g, expected)

def stack(cue=2, expose_endpoints=False):
    """Distinct 14x15 nested three-level construction; no teacher grid copied."""
    g = [[0] * 15 for _ in range(14)]
    g[0][0] = cue
    for left, right, top, bottom, lc, rc, beam in [(2, 12, 10, 13, 2, 3, 4), (4, 10, 6, 9, 5, 6, 7), (6, 8, 3, 5, 8, 9, 1)]:
        for r in range(top, bottom + 1):
            g[r][left], g[r][right] = (lc, rc)
        for c in range(left + 1, right):
            g[top][c] = beam
    if expose_endpoints:
        for c in (6, 8):
            for r in range(7, 10):
                g[r][c] = 1
    return g

def cycle(cue=9):
    g = [[0] * 14 for _ in range(12)]
    g[0][0] = cue
    for r in range(8, 12):
        g[r][2], g[r][11] = (2, 3)
    for c in range(3, 11):
        g[8][c] = 7
    for r in range(3, 8):
        g[r][5] = 7
    return g

def transform(g, rotation=0, reflected=False):
    out = [row[::-1] for row in g] if reflected else deepcopy(g)
    for _ in range(rotation):
        out = [list(row) for row in zip(*out[::-1])]
    return out

def summary(rec):
    geom = rec.get('geometry', {})
    return {'failure': rec.get('failure'), 'complete': rec.get('complete'), 'work': rec.get('work'), 'rounds': len(rec.get('rounds', [])), 'changed_cell_count': rec.get('changed_cell_count'), 'removed_pieces': rec.get('removed_pieces'), 'material_count': geom.get('material_count'), 'hidden_count': geom.get('hidden_count'), 'visible_scene_count': geom.get('visible_scene_count'), 'raw_count': rec.get('parse', {}).get('raw_count')}

def no_completion(out, rec):
    if not out is None:
        raise AssertionError()
    if not rec.get('complete') is not True:
        raise AssertionError()
    for forbidden in ('answer', 'least_fixed_point_rows', 'geometry', 'changed_cells', 'changed_cell_count'):
        if not forbidden not in rec:
            raise AssertionError((forbidden, rec.get('failure')))

@check('strict_arc_validation')
def strict_arc():
    base, _ = table()
    invalid = [None, [], [[]], [[0], [0, 1]], ((0, 0),), [[True]], [[1.0]], [[-1]], [[10]], [[0] * 31], [[0] for _ in range(31)], [['0']], [tuple([0])]]
    for g in invalid:
        payload, rec = probe.parse_input(g)
        if not (payload is None and rec['failure'] == 'invalid_arc_grid'):
            raise AssertionError()
        out, rendered = probe.render(g)
        no_completion(out, rendered)
    if not probe.valid_grid(base):
        raise AssertionError()
    return {'invalid_cases': len(invalid)}

@check('work_limit_validation')
def bad_budgets():
    g, _ = table()
    limits = [-1, probe.WORK_LIMIT + 1, True, 1.0, '10', None]
    for limit in limits:
        out, rec = probe.render(g, work_limit=limit)
        if not (out is None and rec['failure'] == 'invalid_work_limit'):
            raise AssertionError()
    return {'invalid_limits': len(limits)}

@check('modal_background_tie_hold')
def bg_tie():
    out, rec = probe.render([[0, 1], [1, 0]])
    no_completion(out, rec)
    if not rec['parse']['failure'] == 'background_not_unique':
        raise AssertionError()
    return summary(rec)

@check('no_match_cue_is_identity')
def no_match():
    g, expected = table(cue=9)
    out, rec = probe.render(g)
    if not (out == expected == g and rec['complete'] and (not rec['removed_pieces'])):
        raise AssertionError()
    return summary(rec)

@check('delete_one_original_endpoint')
def delete_one():
    g, expected = table(cue=2)
    out, rec = probe.render(g)
    if not out == expected:
        raise AssertionError()
    beam_terms = [term for row in rec['rounds'] for eq in row['terms'] for term in eq['all_terms'] if term.get('source') == 'original_endpoint_side']
    if not (beam_terms and all((not x['both_original_endpoints_survive'] for x in beam_terms))):
        raise AssertionError()
    return summary(rec)

@check('delete_both_original_endpoints')
def delete_both():
    g, expected = table(cue=2, right=2)
    out, rec = probe.render(g)
    if not (out == expected and len(rec['removed_pieces']) == 2):
        raise AssertionError()
    return summary(rec)

@check('delete_beam_body_only')
def delete_body():
    g, expected = table(cue=4)
    out, rec = probe.render(g)
    if not (out == expected and len(rec['surviving_pieces']) == 2):
        raise AssertionError()
    return summary(rec)

@check('delete_all_material_preserves_cue')
def delete_all():
    g, expected = table(cue=2, left=2, right=2, beam=2)
    out, rec = probe.render(g)
    if not (out == expected and rec['surviving_pieces'] == []):
        raise AssertionError()
    if not rec['geometry']['material_count'] == rec['geometry']['visible_scene_count'] == 0:
        raise AssertionError()
    if not sum((v != 0 for row in out for v in row)) == 1:
        raise AssertionError()
    return summary(rec)

@check('nonzero_background_and_foreground_zero')
def nonzero_bg():
    g, expected = table(cue=0, left=0, right=3, beam=4, background=8)
    out, rec = probe.render(g)
    if not (out == expected and rec['parse']['background'] == 8 and (out[0][0] == 0)):
        raise AssertionError()
    return summary(rec)

@check('d4_equivariance_eight_variants')
def d4():
    g, expected = table()
    records = []
    for reflected in (False, True):
        for rotation in range(4):
            out, rec = probe.render(transform(g, rotation, reflected))
            if not out == transform(expected, rotation, reflected):
                raise AssertionError()
            records.append({'reflected': reflected, 'quarter_turns': rotation, **summary(rec)})
    return records

@check('palette_equivariance')
def palette():
    g, expected = table()
    mapping = {0: 6, 2: 0, 3: 8, 4: 1}
    remap = lambda a: [[mapping.get(v, v) for v in row] for row in a]
    out, rec = probe.render(remap(g))
    if not out == remap(expected):
        raise AssertionError()
    return summary(rec)

@check('dimension_variants')
def sizes():
    records = []
    for height, width in [(8, 10), (11, 14), (16, 19)]:
        g, expected = table(height, width)
        out, rec = probe.render(g)
        if not out == expected:
            raise AssertionError()
        records.append({'shape': [height, width], **summary(rec)})
    return records

@check('unstable_input_rejected')
def unstable():
    g = [[0] * 13 for _ in range(9)]
    g[0][0] = 9
    for r in range(3, 6):
        g[r][2], g[r][8] = (2, 3)
    for c in range(3, 8):
        g[3][c] = 4
    for r in (7, 8):
        g[r][10] = 6
    payload, parsed = probe.parse_input(g)
    if not (payload is not None and parsed['details']['type_holds']):
        raise AssertionError()
    out, rec = probe.render(g)
    no_completion(out, rec)
    if not rec['failure'] == 'source_not_stable':
        raise AssertionError()
    return summary(rec)

@check('zero_or_multiple_floor_edges_hold')
def floor_cases():
    g, _ = table()
    none = deepcopy(g)
    none[-1] = [0] * len(g[0])
    multi = deepcopy(g)
    multi[-1][-2:] = [3, 3]
    records = []
    for variant in (none, multi):
        out, rec = probe.render(variant)
        no_completion(out, rec)
        if not rec['parse']['failure'] == 'raw_cue_floor_not_unique':
            raise AssertionError()
        records.append(summary(rec))
    return records

@check('missing_original_endpoint_post_hold')
def missing_endpoint():
    g, _ = table()
    for r in range(5, 9):
        g[r][2] = 0
    payload, rec = probe.parse_input(g)
    if not (payload is None and rec['failure'] == 'whole_scene_type_failed'):
        raise AssertionError()
    if not any((x['code'] == 'beam_endpoint_not_a_post' for x in rec['details']['type_failures'])):
        raise AssertionError()
    return {'failure': rec['failure'], 'raw_count': rec['raw_count']}

def ambiguous_grid():
    g, _ = table(width=13)
    g[0][0] = 0
    g[1][1], g[2][11] = (8, 9)
    return g

@check('two_raw_cues_hold_before_types')
def ambiguous():
    payload, rec = probe.parse_input(ambiguous_grid())
    if not (payload is None and rec['raw_count'] == 2 and (not rec['type_entered'])):
        raise AssertionError()
    return {'raw_count': rec['raw_count'], 'type_entered': rec['type_entered'], 'candidates': rec['raw_candidates']}

@check('raw_two_one_mock_type_success_still_hold', 'patched_type_oracle_unit')
def mock_ambiguity():
    g = ambiguous_grid()
    payload, rec = probe.parse_input(g)
    calls = []

    def mock_type(scene, h, w):
        calls.append(1)
        return {'type_holds': (1, 1) in scene}
    fg = {(r, c): v for r, row in enumerate(g) for c, v in enumerate(row) if v}
    hypothetical = [mock_type({p: v for p, v in fg.items() if p != tuple(c['cue'])}, len(g), len(g[0]))['type_holds'] for c in rec['raw_candidates'] if c['eligible']]
    if not sum(hypothetical) == 1:
        raise AssertionError()
    calls.clear()
    with patch.object(probe, 'detailed_type', mock_type):
        payload, checked = probe.parse_input(g)
    if not (payload is None and checked['raw_count'] == 2 and (not calls)):
        raise AssertionError()
    return {'hypothetical_type_outcomes': hypothetical, 'actual_type_calls': len(calls), 'limitation': 'A real second whole-C4 singleton necessarily remains an untypable singleton after choosing the first. Exactly one real successful type is impossible under this endpoint rule, so this is a mock late-selection control.'}

@check('retain_inconvenient_disconnected_foreground')
def retain_all():
    g, _ = table(cue=9)
    g[3][5] = 6
    payload, rec = probe.parse_input(g)
    if not (payload is None and rec['failure'] == 'whole_scene_type_failed'):
        raise AssertionError()
    if not rec['details']['visible_scene_count'] == sum((v != 0 for row in g for v in row)) - 1:
        raise AssertionError()
    if not any(([3, 5] in b['body_cells'] for b in rec['details']['beams'])):
        raise AssertionError()
    return {'failure': rec['failure'], 'visible_scene_count': rec['details']['visible_scene_count']}

@check('same_colour_dependency_cycle_terminates')
def same_cycle():
    g = cycle()
    payload, _ = probe.parse_input(g)
    cyclic_edges = [(n, lower) for n, p in payload['pieces'].items() if p['kind'] == 'post' for lower in p['lower_beams'] if n in payload['pieces'][lower]['original_endpoint_post_ids']]
    if not cyclic_edges:
        raise AssertionError()
    out, rec = probe.render(g)
    if not (out == g and rec['complete']):
        raise AssertionError()
    moved, moving_rec = probe.render(cycle(cue=2))
    if not (moved is not None and moving_rec['complete']):
        raise AssertionError()
    return {'retained_cycles': cyclic_edges, 'no_match': summary(rec), 'deletion': summary(moving_rec)}

@check('all_lower_constraints_survive_nearest_deletion')
def lower_constraints():
    g = stack(cue=7)
    payload, _ = probe.parse_input(g)
    p = next((p for p in payload['pieces'].values() if p['kind'] == 'post' and p['column'] == 6 and (p['top'] == 3)))
    if not len(p['lower_beams']) == 2:
        raise AssertionError()
    out, rec = probe.render(g)
    if not out is not None:
        raise AssertionError()
    remaining = [n for n in p['lower_beams'] if n in rec['surviving_pieces']]
    if not (len(remaining) == 1 and payload['pieces'][remaining[0]]['row'] == 10):
        raise AssertionError()
    if not rec['least_fixed_point_rows'][p['id']] == 7:
        raise AssertionError()
    original_terms = next((x['all_terms'] for x in rec['source_stability_terms'] if x['piece'] == p['id']))
    if not set(p['lower_beams']) <= {x['source'] for x in original_terms}:
        raise AssertionError()
    beam = next((p for p in payload['pieces'].values() if p['kind'] == 'beam' and p['row'] == 3))
    if not len(beam['lower_beams']) == 2:
        raise AssertionError()
    return {'post': p['id'], 'all_original_lower_beams': p['lower_beams'], 'remaining_lower': remaining, **summary(rec)}

@check('latent_exposure_visible_material_accounting')
def latent_exposure():
    g = stack(cue=7, expose_endpoints=True)
    expected = deepcopy(g)
    for c in range(5, 10):
        expected[6][c] = 0
    expected[6][6], expected[6][8] = (8, 9)
    out, rec = probe.render(g)
    if not out == expected:
        raise AssertionError()
    geom = rec['geometry']
    if not rec['source_material_count'] - rec['removed_material_count'] == geom['material_count']:
        raise AssertionError()
    if not geom['material_count'] == geom['visible_scene_count'] + geom['hidden_count']:
        raise AssertionError()
    for colour, material in geom['material_by_colour'].items():
        if not material == geom['hidden_by_colour'].get(colour, 0) + geom['visible_by_colour'].get(colour, 0):
            raise AssertionError()
    if not sum((v == 8 for row in out for v in row)) == sum((v == 8 for row in g for v in row)) + 1:
        raise AssertionError()
    if not sum((v == 9 for row in out for v in row)) == sum((v == 9 for row in g for v in row)) + 1:
        raise AssertionError()
    return {'input_hash': digest(g), 'expected_hash': digest(expected), **summary(rec)}

@check('budget_zero_exact_and_one_short')
def boundary_budget():
    g = stack()
    expected, full = probe.render(g)
    if not expected is not None:
        raise AssertionError()
    exact, rec = probe.render(g, work_limit=full['work'])
    if not (exact == expected and rec['complete'] and (rec['work'] == full['work'])):
        raise AssertionError()
    records = []
    for limit in (0, full['work'] - 1):
        out, short = probe.render(g, work_limit=limit)
        no_completion(out, short)
        if not (short['failure'] == 'contact_work_incomplete' and short['partial_state_discarded']):
            raise AssertionError()
        if not short['work'] == limit:
            raise AssertionError()
        records.append({'limit': limit, **summary(short)})
    return {'exact_budget': full['work'], 'vetoed': records}

@check('unfinished_after_stationary_coordinates_no_completed_answer')
def partial_stationary():
    g = stack()
    expected, full = probe.render(g)
    candidates = [r for i, r in enumerate(full['rounds'][:-1]) if any((r['rows'][n] == r['next_rows'][n] for n in r['rows'])) and any((r['rows'][n] != r['next_rows'][n] for n in r['rows'])) and (full['rounds'][i + 1]['potential_increase'] > 0)]
    if not candidates:
        raise AssertionError()
    limit = candidates[0]['work_after'] + 1
    out, rec = probe.render(g, work_limit=limit)
    no_completion(out, rec)
    if not (rec['failure'] == 'contact_work_incomplete' and rec['rounds']):
        raise AssertionError()
    return {'budget': limit, 'diagnostic_rounds_retained': len(rec['rounds']), 'accepted_fields_absent': True, **summary(rec)}

@check('final_geometry_collision_bounds_cue_upward_veto', 'patched_payload_unit')
def geometry_vetoes():
    g, _ = table(cue=9)
    base, _ = probe.parse_input(g)
    posts = [n for n, p in base['pieces'].items() if p['kind'] == 'post']
    beam = next((n for n, p in base['pieces'].items() if p['kind'] == 'beam'))
    cases = []
    for mode in ('post_post', 'beam_beam', 'beam_post_interior', 'bounds', 'cue', 'upward'):
        payload, rows = (deepcopy(base), dict(base['original_rows']))
        if mode == 'post_post':
            payload['pieces'][posts[1]]['column'] = payload['pieces'][posts[0]]['column']
        elif mode == 'beam_beam':
            payload['pieces']['B_extra'] = {**deepcopy(payload['pieces'][beam]), 'id': 'B_extra'}
            rows['B_extra'] = rows[beam]
            payload['original_rows']['B_extra'] = rows[beam]
        elif mode == 'beam_post_interior':
            payload['pieces'][beam]['body_columns'] = [payload['pieces'][posts[0]]['column']]
            rows[beam] += 1
        elif mode == 'bounds':
            rows[posts[0]] = payload['height'] - 1
        elif mode == 'cue':
            payload['cue'] = (rows[posts[0]], payload['pieces'][posts[0]]['column'])
        else:
            rows[posts[0]] -= 1
        out, rec = probe.final_geometry(payload, set(payload['pieces']), rows)
        if not (out is None and rec['failures']):
            raise AssertionError()
        wanted = 'forbidden_material_collision' if mode in ('post_post', 'beam_beam', 'beam_post_interior') else 'upward_motion' if mode == 'upward' else 'bounds_or_cue_collision'
        if not any((x['failure'] == wanted for x in rec['failures'])):
            raise AssertionError()
        cases.append({'mode': mode, 'failures': rec['failures']})
    return cases

@check('final_geometry_allows_only_bottom_occlusion', 'patched_payload_unit')
def bottom_occlusion():
    g, _ = table(cue=9)
    payload, _ = probe.parse_input(g)
    p = next((n for n, x in payload['pieces'].items() if x['kind'] == 'post'))
    b = next((n for n, x in payload['pieces'].items() if x['kind'] == 'beam'))
    payload['pieces'][b]['body_columns'] = [payload['pieces'][p]['column']]
    rows = {p: payload['original_rows'][p], b: payload['height'] - 1}
    out, rec = probe.final_geometry(payload, {p, b}, rows)
    if not (out is not None and rec['hidden_count'] == 1):
        raise AssertionError()
    if not rec['material_count'] == rec['visible_scene_count'] + 1:
        raise AssertionError()
    if not out[rows[b]][payload['pieces'][p]['column']] == payload['pieces'][b]['colour']:
        raise AssertionError()
    return {'material': rec['material_count'], 'visible': rec['visible_scene_count'], 'hidden': rec['hidden_count']}

def synthetic_pairs():
    a, ao = table()
    b, bo = table(height=11, width=14, cue=2, right=2)
    return [{'input': a, 'output': ao}, {'input': b, 'output': bo}]

@check('synthetic_teacher_fit_and_distinct_requirement')
def fit_good():
    pairs = synthetic_pairs()
    model, rec = probe.fit_teachers(pairs)
    if not (model is True and rec['all_teachers_evaluated'] and (rec['teacher_equal'] == [True, True])):
        raise AssertionError()
    duplicate, dup = probe.fit_teachers([pairs[0], deepcopy(pairs[0])])
    if not (duplicate is None and dup['distinct_inputs'] == 1):
        raise AssertionError()
    return {'accepted_distinct': rec['distinct_inputs'], 'duplicate_rejected': True}

@check('teacher_object_independence_and_no_mutation')
def independence():
    pairs = synthetic_pairs()
    original = deepcopy(pairs)
    first, r1 = probe.fit_teachers(pairs)
    pairs[0]['unrelated_metadata'] = {'scale': 999, 'reference': pairs[1]}
    second, r2 = probe.fit_teachers(list(reversed(pairs)))
    if not first is second is True:
        raise AssertionError()
    if not r1['teacher_records'] == list(reversed(r2['teacher_records'])):
        raise AssertionError()
    for now, old in zip(pairs, original):
        if not (now['input'] == old['input'] and now['output'] == old['output']):
            raise AssertionError()
    return {'order_independent': True, 'input_output_grids_unmutated': True, 'unrelated_metadata_ignored': True}

@check('targets_only_final_equality_and_every_teacher_evaluated', 'instrumented_synthetic_teacher_test')
def target_independence():
    pairs = synthetic_pairs()
    wrong = deepcopy(pairs)
    wrong[0]['output'][1][1] = 7
    calls = []
    actual = probe.render

    def traced(g, *args, **kwargs):
        calls.append(digest(g))
        return actual(g, *args, **kwargs)
    with patch.object(probe, 'render', traced):
        accepted, a = probe.fit_teachers(pairs)
        rejected, b = probe.fit_teachers(wrong)
    if not (accepted is True and rejected is None):
        raise AssertionError()
    if not (len(calls) == 4 and calls[:2] == calls[2:]):
        raise AssertionError()
    if not a['teacher_records'] == b['teacher_records']:
        raise AssertionError()
    if not (b['teacher_equal'] == [False, True] and b['all_teachers_evaluated']):
        raise AssertionError()
    return {'render_calls': len(calls), 'render_records_identical_after_target_change': True, 'final_equalities': b['teacher_equal']}

@check('invalid_teacher_containers_veto')
def bad_teachers():
    bad = [None, [], {}, [None], [{'input': []}], [{'output': []}]]
    for value in bad:
        model, rec = probe.fit_teachers(value)
        if not (model is None and rec['failure'] == 'invalid_teachers'):
            raise AssertionError()
    return {'invalid_containers': len(bad)}

@check('parse_and_iteration_exceptions_veto', 'injected_exception_unit')
def exceptions():
    g, _ = table()
    with patch.object(probe, 'parse_input', side_effect=RuntimeError('synthetic parse fault')):
        out, rec = probe.render(g)
    no_completion(out, rec)
    if not (rec['failure'] == 'input_interpretation_exception' and rec['partial_state_discarded']):
        raise AssertionError()
    actual, calls = (probe.evaluate_map, [])

    def broken(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError('synthetic iteration fault')
        return actual(*args, **kwargs)
    with patch.object(probe, 'evaluate_map', broken):
        out2, rec2 = probe.render(g)
    no_completion(out2, rec2)
    if not (rec2['failure'] == 'contact_evaluation_exception' and rec2['partial_state_discarded']):
        raise AssertionError()
    return {'parse': summary(rec), 'iteration': summary(rec2)}

@check('fit_exception_discards_partial_fit', 'injected_exception_unit')
def fit_exception():
    actual, calls = (probe.render, [])

    def broken(g):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError('synthetic teacher fault')
        return actual(g)
    with patch.object(probe, 'render', broken):
        model, rec = probe.fit_teachers(synthetic_pairs())
    if not (model is None and rec['failure'] == 'teacher_evaluation_exception' and rec['partial_fit_discarded']):
        raise AssertionError()
    if not rec['fit'] is False:
        raise AssertionError()
    return {'calls_before_veto': len(calls), 'failure': rec['failure']}

class SupportControls(unittest.TestCase):
    pass


def as_test(fn):
    def test(self):
        fn()
    return test


for test_name, test_fn in registered:
    setattr(SupportControls, 'test_' + test_name, as_test(test_fn))


class NativeSupportControls(unittest.TestCase):
    def teachers(self):
        return [{'input': grid, 'output': output}
                for grid, output in (table(width=width) for width in range(11, 16))]

    def test_five_boards_support(self):
        train = self.teachers()
        material = probe.支持構造教材(train)
        self.assertEqual(vars(material), {'適合': True})
        for minimum, admitted in ((3, True), (6, False)):
            machine = HDS学習実行系(最小支持数=minimum)
            record = 候補機構を学習(machine, {'train': train, 'test': []}, (),
                                    'ARC支持構造沈降', material.候補)
            self.assertEqual(record['現在観測数'], 5)
            self.assertEqual(record['事前観測数'], 0)
            self.assertEqual(record['同値採用'], admitted)
            self.assertEqual(record['隔離数'], 0)

    def test_native_partial_hold_and_detachment(self):
        train = self.teachers()
        good, expected = table(height=10, width=19)
        bad = deepcopy(good)
        bad[0][18] = 8
        material = probe.支持構造教材(train)
        for queries, answers in (([good, bad], [expected, None]), ([bad, good], [None, expected])):
            solved = 課題を解く({'train': train, 'test': [{'input':g} for g in queries]}, [])
            self.assertEqual([row['answer'] for row in solved['results']], answers)
        train[0]['input'][:] = [[9]]
        train[0]['output'][:] = [[9]]
        self.assertEqual(vars(material), {'適合': True})
        self.assertEqual(material.候補(good, {})[0], expected)
        self.assertIsNone(material.候補(bad, {})[0])

    def test_native_rejects_identifier_and_test_output(self):
        with self.assertRaises(ValueError):
            課題を解く({'train': [], 'test': [], 'task_id': 'forbidden'}, [])
        with self.assertRaises(ValueError):
            課題を解く({'train': [], 'test': [{'input': [[0]], 'output': [[0]]}]}, [])


if __name__ == '__main__':
    unittest.main()
