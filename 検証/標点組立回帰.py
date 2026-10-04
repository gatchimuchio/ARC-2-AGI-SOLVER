"""標点組立の合成回帰対照。通常実行と python -O の双方で検証する。"""
from collections import Counter
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location('marked_piece_regression_subject', ROOT / '接続' / 'ARC2' / '標点組立教材.py')
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


L_HOST = [(0, 0, 5), (0, 1, 7), (1, 0, 7)]

RING_HOST = [(r, c, 5 if (r, c) == (0, 0) else 7)
             for r in range(3) for c in range(3) if (r, c) != (1, 1)]

METRICS = {}

def make_grid(pieces, starts, height=12, width=12, background=0):
    grid = [[background] * width for _ in range(height)]
    occupied = set()
    for cells, (dr, dc) in zip(pieces, starts):
        for r, c, value in cells:
            point = r + dr, c + dc
            if point in occupied or not (0 <= point[0] < height and 0 <= point[1] < width):
                raise ValueError('invalid synthetic fixture placement')
            occupied.add(point)
            grid[point[0]][point[1]] = value
    return grid

def base_grid(shifted=False):
    return make_grid([L_HOST, [(0, 0, 2)]],
                     [(3, 2), (9, 8)] if shifted else [(1, 1), (7, 7)])

def singleton_grid(colors=(2, 2, 2), shifted=False):
    return make_grid([L_HOST, *[[(0, 0, color)] for color in colors]],
                     [(2, 2), (2, 8), (8, 2), (8, 8)] if shifted
                     else [(1, 1), (1, 7), (7, 1), (7, 7)])

def independent_orientation(cells, label):
    transforms = (lambda r, c: (r, c), lambda r, c: (c, -r),
                  lambda r, c: (-r, -c), lambda r, c: (-c, r))
    moved = [(*transforms[label](r, c), value) for r, c, value in cells]
    r0, c0 = min(x[0] for x in moved), min(x[1] for x in moved)
    return tuple(sorted((r-r0, c-c0, value) for r, c, value in moved))

def synthetic_pairs(non_square=False):
    if non_square:
        output = [[5, 7, 2], [7, 2, 2]]
        grids = [singleton_grid(), singleton_grid(shifted=True)]
    else:
        output = [[5, 7], [7, 2]]
        grids = [base_grid(), base_grid(True)]
    return [{'input': grid, 'output': deepcopy(output)} for grid in grids]

class BoundaryControls(unittest.TestCase):
    def run_fixture(self, name, grid, aspect):
        parsed, _ = probe.parse(grid)
        self.assertIsNotNone(parsed)
        output, record = probe.search_assemblies(parsed, aspect)
        METRICS[name] = {key: record.get(key) for key in (
            'complete', 'failure', 'canvas_shape', 'work', 'work_categories',
            'physical_model_count', 'models_seen', 'unique_grid_count')}
        return parsed, output, record

    def check_models(self, parsed, record):
        pieces = {piece['index']: piece['cells'] for piece in parsed['pieces']}
        source_counts = Counter(value for cells in pieces.values() for r, c, value in cells)
        height, width = record['canvas_shape']
        for model in record['models']:
            self.assertEqual(sorted(p[0] for p in model['placements']), sorted(pieces))
            paint = {}
            for identity, label, dr, dc in model['placements']:
                self.assertIn(label, (0, 1, 2, 3))
                for r, c, value in independent_orientation(pieces[identity], label):
                    point = r+dr, c+dc
                    self.assertNotIn(point, paint, 'same-color overlap is also forbidden')
                    self.assertTrue(0 <= point[0] < height and 0 <= point[1] < width)
                    paint[point] = value
                    if identity == parsed['role']['host_component_index'] and value == parsed['role']['marker_color']:
                        self.assertEqual(point, (0, 0))
            self.assertEqual(set(paint), {(r, c) for r in range(height) for c in range(width)})
            self.assertEqual(Counter(paint.values()), source_counts)
            self.assertEqual([[paint[r, c] for c in range(width)] for r in range(height)], model['grid'])

    def check_discard(self, output, record, failure):
        self.assertIsNone(output)
        self.assertFalse(record['complete'])
        self.assertEqual(record['failure'], failure)
        self.assertEqual(record['models'], [])
        self.assertEqual(record['physical_model_count'], 0)
        self.assertEqual(record.get('unique_grid_count', 0), 0)

    def test_assertions_raise_even_when_optimized(self):
        with self.assertRaises(AssertionError):
            self.assertEqual('intentional wrong value', 'expected value')
        with self.assertRaises(AssertionError):
            self.assertIsNone(object())

    def test_invalid_grid_types_bounds_and_values(self):
        invalid = [None, 3, '0', (), [], [[]], [[1], []], [[0], [0, 1]],
                   [[True]], [[False]], [[1.0]], [['1']], [[None]], [[-1]], [[10]],
                   [[0] * 31], [[0] for _ in range(31)], ((0,),), [(0,)],
                   [[0], (0,)]]
        for grid in invalid:
            with self.subTest(grid_type=type(grid).__name__, representation=repr(grid)[:50]):
                self.assertFalse(probe.valid_grid(grid))
                parsed, record = probe.parse(grid)
                self.assertIsNone(parsed)
                self.assertEqual(record['failure'], 'invalid_arc_grid')
                output, rendered = probe.render(grid, (1, 1))
                self.assertIsNone(output)
                self.assertEqual(rendered['failure'], 'invalid_arc_grid')

    def test_valid_arc_bounds_are_inclusive(self):
        for grid in ([[0]], [[9]], [[0] * 30], [[9] for _ in range(30)], [[0]*30 for _ in range(30)]):
            self.assertTrue(probe.valid_grid(grid))

    def test_all_ten_backgrounds_and_known_raw_roles(self):
        cases = (
            (base_grid(), [(0, 5, 4)]),
            (singleton_grid(), [(0, 5, 6)]),
            ([[0, 0, 1, 2]], [(0, 1, 2), (0, 2, 2), (2, 1, 3)]),
            ([[1, 1, 2]], [(background, 2, 3) for background in (0, 3, 4, 5, 6, 7, 8, 9)]),
        )
        for grid, expected in cases:
            observed = probe.observe_input(grid)
            self.assertEqual([row['background'] for row in observed['all_background_observations']], list(range(10)))
            self.assertEqual([(role['background'], role['marker_color'], role['all_foreground_area']) for role in observed['complete_roles']], expected)


    def test_two_singleton_marker_choices_are_retained_and_hold(self):
        grid = make_grid([[(0, 0, 5), (0, 1, 7)], [(0, 0, 2)]], [(1, 1), (7, 7)])
        observed = probe.observe_input(grid)
        self.assertEqual([(r['background'], r['marker_color']) for r in observed['complete_roles']], [(0, 5), (0, 7)])
        with patch.object(probe, 'search_assemblies', side_effect=AssertionError('packing ran before raw uniqueness')) as search:
            output, record = probe.render(grid, (3, 1))
        self.assertIsNone(output)
        self.assertEqual(record['failure'], 'raw_role_not_unique')
        search.assert_not_called()

    def test_multiple_backgrounds_cannot_be_rescued_by_area_or_packing(self):
        grid = [[0, 0, 1, 2]]
        observed = probe.observe_input(grid)
        self.assertEqual([(r['background'], r['all_foreground_area']) for r in observed['complete_roles']], [(0, 2), (0, 2), (2, 3)])
        with patch.object(probe, 'search_assemblies', side_effect=AssertionError('ambiguous role reached packing')) as search:
            for aspect in ((3, 1), (1, 1), None):
                output, record = probe.render(grid, aspect)
                self.assertIsNone(output)
                self.assertEqual(record['failure'], 'raw_role_not_unique')
        search.assert_not_called()
        # Explicit boundary demonstration: the B=2 role alone would fit, while
        # both B=0 roles fail area. This is not an allowed public parse result.
        outcomes = []
        for role in observed['complete_roles']:
            components = observed['all_background_observations'][role['background']]['whole_mixed_c8_components']
            manual = {'role': role, 'pieces': tuple({'index': p['component_index'], 'cells': tuple(map(tuple, p['cells']))} for p in components)}
            output, record = probe.search_assemblies(manual, (3, 1))
            outcomes.append((output, record.get('failure')))
        self.assertEqual([item[1] for item in outcomes[:2]], ['area_not_compatible_with_aspect'] * 2)
        self.assertEqual(outcomes[2][0], [[1, 0, 0]])

    def test_absent_background_roles_are_not_removed(self):
        parsed, record = probe.parse([[1, 1, 2]])
        self.assertIsNone(parsed)
        self.assertEqual({r['background'] for r in record['raw']['complete_roles']}, {0, 3, 4, 5, 6, 7, 8, 9})
        self.assertEqual(record['raw']['complete_role_count'], 8)

    def test_base_consensus_and_all_four_rotation_aliases(self):
        parsed, output, record = self.run_fixture('base', base_grid(), (1, 1))
        self.assertEqual(output, [[5, 7], [7, 2]])
        self.assertTrue(record['complete'])
        self.assertEqual(record['physical_model_count'], 4)
        singleton_id = next(p['index'] for p in parsed['pieces'] if len(p['cells']) == 1)
        self.assertEqual({next(p[1] for p in m['placements'] if p[0] == singleton_id) for m in record['models']}, {0, 1, 2, 3})
        self.check_models(parsed, record)

    def test_equal_color_physical_identity_exchange(self):
        parsed, output, record = self.run_fixture('exchangeable_same_color', singleton_grid(), (3, 2))
        self.assertEqual(output, [[5, 7, 2], [7, 2, 2]])
        self.assertEqual(record['physical_model_count'], 6 * 4**3)
        self.assertEqual(record['unique_grid_count'], 1)
        zero_labels = [m for m in record['models'] if all(p[1] == 0 for p in m['placements'])]
        self.assertEqual(len(zero_labels), 6)
        self.assertEqual(len({tuple(tuple(p) for p in m['placements']) for m in zero_labels}), 6)
        self.check_models(parsed, record)

    def test_marker_color_elsewhere_is_allowed(self):
        grid = make_grid([RING_HOST, [(0, 0, 5)]], [(1, 1), (9, 9)])
        parsed, output, record = self.run_fixture('marker_color_elsewhere', grid, (1, 1))
        self.assertEqual(parsed['role']['marker_color_occurrences_outside_host'], 1)
        self.assertEqual(output, [[5, 7, 7], [7, 5, 7], [7, 7, 7]])
        self.check_models(parsed, record)

    def test_holes_and_overlapping_bounding_boxes_preserve_support(self):
        grid = make_grid([RING_HOST, [(0, 0, 2)]], [(1, 1), (9, 9)])
        parsed, output, record = self.run_fixture('holed_support', grid, (1, 1))
        self.assertEqual(output, [[5, 7, 7], [7, 2, 7], [7, 7, 7]])
        self.assertEqual(record['physical_model_count'], 4)
        self.check_models(parsed, record)

    def test_first_occupied_cell_may_differ_from_bbox_top_left(self):
        complement = [(0, 2, 2), (1, 1, 2), (1, 2, 2), (2, 0, 2), (2, 1, 2), (2, 2, 2)]
        grid = make_grid([L_HOST, complement], [(1, 1), (7, 7)])
        parsed, output, record = self.run_fixture('absent_bbox_top_left', grid, (1, 1))
        self.assertEqual(output, [[5, 7, 2], [7, 2, 2], [2, 2, 2]])
        self.assertEqual(record['physical_model_count'], 1)
        self.assertNotIn((0, 0), {(r, c) for r, c, value in complement})
        self.check_models(parsed, record)

    def test_same_color_overlap_rejected_without_aborting_other_branches(self):
        host = [(0, 0, 5), (0, 1, 7), (0, 2, 7), (1, 1, 7)]
        same_color_piece = [(0, 0, 7), (0, 1, 7), (1, 1, 7)]
        grid = make_grid([host, same_color_piece, [(0, 0, 2)], [(0, 0, 2)]], [(1, 1), (1, 7), (7, 1), (7, 7)])
        parsed, output, record = self.run_fixture('same_color_collision', grid, (1, 1))
        self.assertIsNone(output)
        self.assertTrue(record['complete'])
        self.assertEqual(record['failure'], 'complete_grids_disagree')
        self.assertEqual(record['physical_model_count'], 64)
        self.assertEqual(record['unique_grid_count'], 2)
        # Host label 0 leaves first empty (1,0); piece label 0 translated there
        # is in bounds and collides at (1,1), with color 7 on both supports.
        host_paint = {(r, c): v for r, c, v in host}
        moved = {(r+1, c): v for r, c, v in same_color_piece}
        self.assertEqual(set(host_paint) & set(moved), {(1, 1)})
        self.assertEqual(host_paint[1, 1], moved[1, 1])
        for model in record['models']:
            self.assertFalse([0, 0, 0, 0] in model['placements'] and [1, 0, 1, 0] in model['placements'])
        self.check_models(parsed, record)

    def test_all_distinct_colored_grids_force_complete_disagreement(self):
        parsed, output, record = self.run_fixture('colored_disagreement', singleton_grid((2, 3, 4)), (3, 2))
        self.assertIsNone(output)
        self.assertTrue(record['complete'])
        self.assertEqual(record['physical_model_count'], 384)
        self.assertEqual(record['unique_grid_count'], 6)
        self.assertEqual(record['failure'], 'complete_grids_disagree')
        self.check_models(parsed, record)

    def test_piece_counts_one_two_and_four_are_allowed(self):
        grid = [[5, 7, 0], [7, 7, 0]]
        parsed, output, record = self.run_fixture('one_host_only', grid, (1, 1))
        self.assertEqual(len(parsed['pieces']), 1)
        self.assertEqual(output, [[5, 7], [7, 7]])
        self.check_models(parsed, record)
        self.assertEqual(len(probe.parse(base_grid())[0]['pieces']), 2)
        self.assertEqual(len(probe.parse(singleton_grid())[0]['pieces']), 4)

    def test_palette_permutation_allows_body_zero_and_marker_zero(self):
        for mapping in ({0: 4, 5: 0, 7: 8, 2: 6}, {0: 5, 5: 6, 7: 0, 2: 9}):
            grid = [[mapping[v] for v in row] for row in base_grid()]
            output, record = probe.render(grid, (1, 1))
            self.assertEqual(output, [[mapping[v] for v in row] for row in [[5, 7], [7, 2]]])
            self.assertTrue(record['assembly']['complete'])
            self.check_models(probe.parse(grid)[0], record['assembly'])

    def test_input_spacing_translation_and_host_rotation(self):
        for label in range(4):
            host = independent_orientation(L_HOST, label)
            grid = make_grid([host, [(0, 0, 2)]], [(3, 4), (10, 10)])
            output, record = probe.render(grid, (1, 1))
            self.assertEqual(output, [[5, 7], [7, 2]])
            self.assertEqual(record['assembly']['physical_model_count'], 4)
            self.check_models(probe.parse(grid)[0], record['assembly'])

    def test_invalid_aspect_and_budget(self):
        parsed, _ = probe.parse(base_grid())
        for aspect in (None, (), (1,), (1, 1, 1), (True, 1), (1.0, 1), (0, 1), (-1, 1), (2, 2), '1:1'):
            output, record = probe.search_assemblies(parsed, aspect)
            self.assertIsNone(output)
            self.assertEqual(record['failure'], 'invalid_aspect_or_budget')
        for budget in (None, 0, -1, 100001, True, 1.0):
            output, record = probe.search_assemblies(parsed, (1, 1), budget=budget)
            self.assertIsNone(output)
            self.assertEqual(record['failure'], 'invalid_aspect_or_budget')

    def test_invalid_area_and_oversize_canvas(self):
        for grid, aspect in ((base_grid(), (3, 1)), (singleton_grid(), (1, 1))):
            output, record = probe.render(grid, aspect)
            self.assertIsNone(output)
            self.assertEqual(record['failure'], 'area_not_compatible_with_aspect')
            self.assertEqual(record['assembly']['work'], 0)
        grid = make_grid([L_HOST, [(r, c, 2) for r in range(4) for c in range(7)]], [(1, 1), (6, 4)])
        output, record = probe.render(grid, (31, 1))
        self.assertIsNone(output)
        self.assertEqual(record['failure'], 'canvas_outside_arc_bounds')
        self.assertEqual(record['assembly']['canvas_shape'], [1, 31])
        self.assertEqual(record['assembly']['work'], 0)

    def test_zero_solutions_is_complete_hold(self):
        output, record = probe.render(base_grid(), (4, 1))
        self.assertIsNone(output)
        self.assertEqual(record['failure'], 'no_complete_assembly')
        self.assertTrue(record['assembly']['complete'])
        self.assertEqual(record['assembly']['models'], [])

    def test_exact_work_and_one_short_after_solutions(self):
        parsed, _ = probe.parse(base_grid())
        output, record = probe.search_assemblies(parsed, (1, 1))
        self.assertEqual(record['work'], 82)
        self.assertEqual(record['work_categories'], {'nodes': 6, 'orientations': 24, 'placements': 24, 'solutions': 28})
        exact, exact_record = probe.search_assemblies(parsed, (1, 1), budget=82)
        self.assertEqual(exact, output)
        self.assertTrue(exact_record['complete'])
        self.assertEqual(exact_record['models'], record['models'])
        short, short_record = probe.search_assemblies(parsed, (1, 1), budget=81)
        self.check_discard(short, short_record, 'search_budget_incomplete')
        self.assertGreater(short_record['models_seen'], 0)
        self.assertEqual(short_record['work'], 78)
        self.assertEqual(short_record['work_categories']['placements'], 20)
        METRICS['one_unit_short_after_solutions'] = {k: short_record[k] for k in ('work', 'models_seen', 'physical_model_count', 'complete', 'failure')}

    def test_every_budget_threshold_discards_partial_answers(self):
        parsed, _ = probe.parse(base_grid())
        had_partial_solution = False
        for budget in range(1, 82):
            output, record = probe.search_assemblies(parsed, (1, 1), budget=budget)
            self.check_discard(output, record, 'search_budget_incomplete')
            self.assertLessEqual(record['work'], budget)
            had_partial_solution |= record['models_seen'] > 0
        self.assertTrue(had_partial_solution)

    def test_exception_after_solution_discards_every_model(self):
        parsed, _ = probe.parse(base_grid())
        original_charge = probe.WorkBudget.charge
        seen = {'solution_charges': 0}
        def injected_charge(meter, amount, category):
            if category == 'solutions':
                seen['solution_charges'] += 1
                if seen['solution_charges'] == 2:
                    raise RuntimeError('synthetic exception after one model')
            return original_charge(meter, amount, category)
        with patch.object(probe.WorkBudget, 'charge', injected_charge):
            output, record = probe.search_assemblies(parsed, (1, 1))
        self.check_discard(output, record, 'search_exception')
        self.assertEqual(record['models_seen'], 1)
        self.assertEqual(record['exception_type'], 'RuntimeError')
        METRICS['exception_after_one_solution'] = {k: record[k] for k in ('work', 'models_seen', 'physical_model_count', 'complete', 'failure')}

    def test_orientation_exception_and_render_boundary_exception(self):
        parsed, _ = probe.parse(base_grid())
        with patch.object(probe, 'oriented_cells', side_effect=RuntimeError('synthetic orientation failure')):
            output, record = probe.search_assemblies(parsed, (1, 1))
        self.check_discard(output, record, 'search_exception')
        self.assertEqual(record['models_seen'], 0)
        with patch.object(probe, 'search_assemblies', side_effect=RuntimeError('synthetic external search failure')):
            output, record = probe.render(base_grid(), (1, 1))
        self.check_discard(output, record['assembly'], 'search_exception')

    def test_two_distinct_current_inputs_required(self):
        pairs = synthetic_pairs()
        for invalid in ([], pairs[:1], None):
            aspect, record = probe.fit_teachers(invalid)
            self.assertIsNone(aspect)
            self.assertEqual(record['failure'], 'fewer_than_two_teachers')
        aspect, record = probe.fit_teachers([pairs[0], deepcopy(pairs[0])])
        self.assertIsNone(aspect)
        self.assertEqual(record['failure'], 'fewer_than_two_distinct_inputs')
        aspect, record = probe.fit_teachers(pairs)
        self.assertEqual(aspect, (1, 1))
        self.assertEqual(record['distinct_input_count'], 2)

    def test_all_inputs_parsed_before_any_target_is_read(self):
        class OutputTrap(dict):
            def get(self, key, default=None):
                if key == 'output':
                    raise AssertionError('output read before raw rejection')
                return super().get(key, default)
        pairs = [OutputTrap(input=base_grid()), OutputTrap(input=[[0, 0, 1, 2]])]
        with patch.object(probe, 'search_assemblies', side_effect=AssertionError('search before raw rejection')) as search:
            aspect, record = probe.fit_teachers(pairs)
        self.assertIsNone(aspect)
        self.assertEqual(record['failure'], 'teacher_raw_role_failed')
        self.assertEqual(len(record['raw_records']), 2)
        search.assert_not_called()

    def test_non_square_ratio_is_fitted_and_reduced(self):
        pairs = synthetic_pairs(non_square=True)
        aspect, record = probe.fit_teachers(pairs)
        self.assertEqual(aspect, (3, 2))
        self.assertIs(type(aspect), tuple)
        self.assertEqual(record['teacher_matches'], [True, True])
        self.assertEqual([search['canvas_shape'] for search in record['searches']], [[2, 3], [2, 3]])

    def test_target_mutation_cannot_change_fitted_aspect_or_prediction(self):
        pairs = synthetic_pairs(non_square=True)
        aspect, record = probe.fit_teachers(pairs)
        before, before_record = probe.render(pairs[0]['input'], aspect)
        pairs[0]['output'][0][0] = 9
        pairs[1]['output'][:] = [[9] * 7]
        after, after_record = probe.render(pairs[0]['input'], aspect)
        self.assertEqual(aspect, (3, 2))
        self.assertEqual(before, after)
        self.assertEqual(before_record['assembly']['models'], after_record['assembly']['models'])

    def test_fit_searches_all_inputs_before_target_equality(self):
        calls = []
        original = probe.search_assemblies
        class EqualityTrap(list):
            def __eq__(self, other):
                if len(calls) != 2:
                    raise AssertionError('target equality before all searches')
                return super().__eq__(other)
        pairs = synthetic_pairs()
        for pair in pairs:
            pair['output'] = EqualityTrap(pair['output'])
        def tracking_search(parsed, aspect, **kwargs):
            result = original(parsed, aspect, **kwargs)
            calls.append(result[1]['complete'])
            return result
        with patch.object(probe, 'search_assemblies', tracking_search):
            aspect, record = probe.fit_teachers(pairs)
        self.assertEqual(aspect, (1, 1))
        self.assertEqual(calls, [True, True])

    def test_bad_targets_do_not_select_a_packing(self):
        pairs = synthetic_pairs(non_square=True)
        pairs[0]['input'] = singleton_grid((2, 3, 4))
        parsed, _ = probe.parse(pairs[0]['input'])
        _, result = probe.search_assemblies(parsed, (3, 2))
        pairs[0]['output'] = deepcopy(result['models'][0]['grid'])
        aspect, record = probe.fit_teachers(pairs)
        self.assertIsNone(aspect)
        self.assertEqual(record['searches'][0]['unique_grid_count'], 6)
        self.assertEqual(record['searches'][0]['physical_model_count'], 384)
        self.assertEqual(record['searches'][0]['failure'], 'complete_grids_disagree')

    def test_teacher_order_preserves_models_and_per_input_work(self):
        pairs = synthetic_pairs()
        aspect, forward = probe.fit_teachers(pairs)
        reverse_aspect, reverse = probe.fit_teachers(list(reversed(pairs)))
        self.assertEqual(aspect, reverse_aspect)
        for first, second in zip(forward['searches'], reversed(reverse['searches'])):
            self.assertEqual(first['models'], second['models'])
            self.assertEqual(first['work'], second['work'])
            self.assertEqual(first['budget'], 100000)
            self.assertEqual(second['budget'], 100000)

    def test_second_teacher_search_exception_rejects_fit(self):
        original = probe.search_assemblies
        count = 0
        def fail_second(parsed, aspect, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise RuntimeError('synthetic second-teacher search failure')
            return original(parsed, aspect, **kwargs)
        with patch.object(probe, 'search_assemblies', fail_second):
            aspect, record = probe.fit_teachers(synthetic_pairs())
        self.assertIsNone(aspect)
        self.assertEqual(count, 2)
        self.assertEqual(record['teacher_matches'], [True, False])
        self.check_discard(None, record['searches'][1], 'search_exception')

    def test_teacher_output_validation_aspect_and_equality_failures(self):
        for target, expected_failure in (([[True]], 'invalid_teacher_output'), ([[0, 0]], 'teacher_aspects_disagree'), ([[9, 7], [7, 2]], 'teacher_assembly_or_equality_failed')):
            pairs = synthetic_pairs()
            pairs[1]['output'] = target
            aspect, record = probe.fit_teachers(pairs)
            self.assertIsNone(aspect)
            self.assertEqual(record['failure'], expected_failure)

    def test_identity_is_not_vetoed_after_complete_agreement_boundary_injection(self):
        # Identity cannot arise naturally under unique raw roles: a present B
        # shrinks area, and an absent B on one bicolored whole grid yields at
        # least eight absent-background roles. Inject only a completed search
        # result to exercise the wrapper's separate no-identity-veto boundary.
        grid = base_grid()
        completed = {'complete': True, 'models': [{'placements': [], 'grid': deepcopy(grid)}],
                     'physical_model_count': 1, 'unique_grid_count': 1}
        with patch.object(probe, 'search_assemblies', return_value=(deepcopy(grid), completed)):
            output, record = probe.render(grid, (1, 1))
        self.assertEqual(output, grid)
        self.assertTrue(record['assembly']['complete'])
        self.assertNotIn('failure', record)

    def test_wrapper_fit_stores_only_immutable_aspect(self):
        pairs = synthetic_pairs()
        wrapper = probe.標点組立教材(pairs)
        self.assertEqual(wrapper.__dict__, {'共有縦横比': (1, 1)})
        self.assertIs(type(wrapper.共有縦横比), tuple)
        self.assertEqual(wrapper.記録(), {'適合': True, '共有縦横比': (1, 1)})
        output, record = wrapper.候補(pairs[0]['input'], object())
        self.assertEqual(output, pairs[0]['output'])
        self.assertTrue(record['assembly']['complete'])

    def test_wrapper_unfitted_holds_without_search(self):
        pairs = synthetic_pairs()
        for teachers in ([], pairs[:1], [pairs[0], deepcopy(pairs[0])]):
            wrapper = probe.標点組立教材(teachers)
            self.assertIsNone(wrapper.共有縦横比)
            self.assertEqual(wrapper.記録(), {'適合': False, '共有縦横比': None})
            grid = base_grid()
            unchanged = deepcopy(grid)
            with patch.object(probe, 'render', side_effect=AssertionError('unfitted wrapper reached render')) as render:
                output, record = wrapper.候補(grid, None)
            self.assertIsNone(output)
            self.assertEqual(record, {'failure': '全教師を再現する標点組立規則なし'})
            self.assertEqual(grid, unchanged)
            render.assert_not_called()

    def test_wrapper_teacher_mutation_independence_and_input_unchanged(self):
        pairs = synthetic_pairs(non_square=True)
        untouched_teachers = deepcopy(pairs)
        wrapper = probe.標点組立教材(pairs)
        self.assertEqual(pairs, untouched_teachers)
        grid = deepcopy(pairs[0]['input'])
        untouched_grid = deepcopy(grid)
        before, first_record = wrapper.候補(grid, None)
        self.assertEqual(grid, untouched_grid)
        self.assertEqual(before, [[5, 7, 2], [7, 2, 2]])
        for pair in pairs:
            pair['input'][:] = [[9]]
            pair['output'][:] = [[1] * 7]
        after, second_record = wrapper.候補(grid, None)
        self.assertEqual(after, before)
        self.assertEqual(first_record['assembly']['models'], second_record['assembly']['models'])
        self.assertEqual(grid, untouched_grid)
        self.assertEqual(wrapper.__dict__, {'共有縦横比': (3, 2)})
        self.assertEqual(wrapper.記録(), {'適合': True, '共有縦横比': (3, 2)})
        after[0][0] = 9
        repeated, _ = wrapper.候補(grid, None)
        self.assertEqual(repeated, before)


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed_cases = []

    def addSuccess(self, test):
        self.passed_cases.append(test.id().rsplit('.', 1)[-1])
        super().addSuccess(test)

def run_single():
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BoundaryControls)
    result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=RecordingResult).run(suite)
    report = {'optimized': bool(sys.flags.optimize), 'tests_run': result.testsRun,
              'successful': result.wasSuccessful(), 'passed_cases': result.passed_cases,
              'failures': [{'test': str(test), 'traceback': trace} for test, trace in result.failures + result.errors],
              'synthetic_fixture_metrics': METRICS}
    return report

def main():
    report = run_single()
    print(json.dumps(report, sort_keys=True))
    return 0 if report['successful'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

