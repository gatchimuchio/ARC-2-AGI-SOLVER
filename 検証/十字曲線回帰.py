"""Synthetic controls for the learned-pitch curve and complete finite covering."""
import copy
import unittest
from unittest.mock import patch
from pathlib import Path
import sys
根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / "HDS/学習系統/v0.4.2")]
from 接続.ARC2 import 十字曲線教材 as p
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 課題を解く


def scene(height=13, width=17, center=(5, 6), length=2, foreground=6, background=0):
    grid = [[background] * width for _ in range(height)]
    for dr, dc in ((-1, 0), (0, 1), (1, 0), (0, -1)):
        for k in range(1, length + 1):
            grid[center[0] + dr * k][center[1] + dc * k] = foreground
    return grid


def step_expected(height=13, width=17, center=(5, 6), length=2,
                  foreground=6, background=0, pitch=2, hand='CW', extra=8, first_exit=False):
    out = [[background] * width for _ in range(height)]
    radius = max(pitch, length)
    maximum = max(center[0], height - 1 - center[0], center[1], width - 1 - center[1])
    def turn(vector, clockwise):
        r, c = vector
        return (c, -r) if clockwise else (-c, r)
    def paint(pos):
        inside = 0 <= pos[0] < height and 0 <= pos[1] < width
        if inside:
            out[pos[0]][pos[1]] = foreground
        return inside
    for u in ((-1, 0), (0, 1), (1, 0), (0, -1)):
        pos = center
        active = True
        for _ in range(radius):
            pos = (pos[0] + u[0], pos[1] + u[1])
            if not paint(pos) and first_exit:
                active = False
                break
        heading = u
        for k in range(maximum // pitch + extra):
            if not active:
                break
            for clockwise, count in ((hand == 'CW', pitch * (2 * k + 1)),
                                     (hand == 'CW', radius - pitch),
                                     (hand != 'CW', radius)):
                heading = turn(heading, clockwise)
                for _ in range(count):
                    pos = (pos[0] + heading[0], pos[1] + heading[1])
                    if not paint(pos) and first_exit:
                        active = False
                        break
                if not active:
                    break
    return out


class CrossArmControls(unittest.TestCase):
    def rendered(self, grid, model=(2, 'CW')):
        payload, record = p.parse_input(grid)
        self.assertIsNotNone(payload, record)
        return p.render_curve(payload, model)

    def test_complete_sixty_tuple_covering(self):
        self.assertEqual(len(p.MODELS), 60)
        self.assertEqual(len(set(p.MODELS)), 60)
        self.assertIn(('GE30', 'CW'), p.MODELS)
        self.assertIn(('GE30', 'CCW'), p.MODELS)

    def test_strict_grid_types(self):
        for grid in (None, [], ((0, 1),), [[True]], [[1.0]], [[10]], [[-1]], [[0], [0, 1]]):
            self.assertIsNone(p.parse_input(grid)[0])

    def test_thirty_one_rejected_before_raw_role(self):
        for grid in (scene(31, 13, (15, 6), 1), scene(13, 31, (6, 15), 1)):
            with patch.object(p, 'observe_input', side_effect=RuntimeError('raw must not run')):
                self.assertEqual(p.parse_input(grid)[1]['failure'], 'invalid_arc_grid')

    def test_thirty_domain_boundary(self):
        grid = scene(30, 30, (3, 7), 3)
        out, rec = self.rendered(grid)
        self.assertEqual(out, step_expected(30, 30, (3, 7), 3))
        self.assertEqual(rec['shape'], [30, 30])

    def test_missing_or_unequal_arm(self):
        grid = scene()
        grid[3][6] = 0
        self.assertIsNone(p.parse_input(grid)[0])
        grid = scene()
        grid[2][6] = 6
        self.assertIsNone(p.parse_input(grid)[0])

    def test_center_and_extra_foreground_rejected(self):
        for point in ((5, 6), (10, 14)):
            grid = scene()
            grid[point[0]][point[1]] = 6
            self.assertIsNone(p.parse_input(grid)[0])

    def test_other_colour_rejected_without_render(self):
        grid = scene()
        grid[10][14] = 7
        with patch.object(p, 'render_curve', side_effect=RuntimeError('must not render')):
            answer, rec = p.predict(grid, ((2, 'CW'),))
        self.assertIsNone(answer)
        self.assertEqual(rec['failure'], 'input_not_interpretable')

    def test_background_tie(self):
        self.assertIsNone(p.parse_input([[1, 2], [2, 1]])[0])

    def test_all_original_seed_cells_owned(self):
        grid = scene(length=3)
        payload, rec = p.parse_input(grid)
        self.assertEqual(len(payload['seeds']), 12)
        self.assertEqual(payload['center'], (5, 6))
        self.assertTrue(rec['raw']['raw_roles'][0]['whole_support_equality'])

    def test_every_model_matches_independent_longer_walk(self):
        fixtures = [(7, 9, (2, 4), 1), (11, 12, (5, 7), 3), (13, 17, (5, 6), 2)]
        for height, width, center, length in fixtures:
            grid = scene(height, width, center, length)
            for model in p.MODELS:
                d = 30 if model[0] == 'GE30' else model[0]
                out, rec = self.rendered(grid, model)
                self.assertEqual(out, step_expected(height, width, center, length, pitch=d, hand=model[1]))
                self.assertTrue(rec['seed_preserved'])

    def test_zero_jog_still_preserves_all_turns(self):
        out, rec = self.rendered(scene(length=1))
        self.assertEqual(out, step_expected(length=1))
        for arm in rec['arms']:
            for phase in arm['phases']:
                self.assertEqual(phase['vertices'][1], phase['vertices'][2])

    def test_pitch_one_contacts_are_not_filtered(self):
        grid = scene(length=3)
        out, rec = self.rendered(grid, (1, 'CW'))
        self.assertIsNotNone(out)
        self.assertEqual(out, step_expected(length=3, pitch=1))
        self.assertEqual(rec['model'], [1, 'CW'])

    def test_empty_phase_then_boundary_reentry(self):
        args = (21, 23, (8, 10), 3)
        grid = scene(*args, foreground=4, background=1)
        out, rec = self.rendered(grid)
        north = rec['arms'][0]
        self.assertEqual(rec['canvas_radius'], 12)
        self.assertEqual(rec['phases_per_arm'], 6)
        self.assertEqual(north['phases'][4]['visible_union_count'], 0)
        self.assertEqual(north['phases'][5]['visible_union_count'], 1)
        self.assertEqual(out[20][22], 4)
        self.assertEqual(out, step_expected(*args, foreground=4, background=1))
        truncated = step_expected(*args, foreground=4, background=1, first_exit=True)
        self.assertNotEqual(out, truncated)
        self.assertEqual(truncated[20][22], 1)

    def test_first_excluded_radius_exceeds_canvas(self):
        for model in p.MODELS:
            out, rec = self.rendered(scene(), model)
            self.assertGreater(rec['first_excluded_phase_lower_radius'], rec['canvas_radius'])
            self.assertTrue(all(len(a['phases']) == rec['phases_per_arm'] for a in rec['arms']))

    def test_segment_cells_follow_proved_annulus(self):
        grid = scene(30, 27, (14, 12), 10)
        for model in ((1, 'CW'), (2, 'CCW'), (11, 'CW'), ('GE30', 'CW')):
            out, rec = self.rendered(grid, model)
            for arm in rec['arms']:
                for phase in arm['phases']:
                    for segment in phase['segments']:
                        for r, c in segment['visible_cells']:
                            distance = max(abs(r - 14), abs(c - 12))
                            self.assertGreaterEqual(distance, phase['radial_lower_bound'])
                            self.assertLessEqual(distance, rec['completed_radius'] + phase['radial_lower_bound'])

    def test_tail_equals_multiple_larger_pitches(self):
        args = (30, 29, (14, 13), 11)
        grid = scene(*args)
        for hand in ('CW', 'CCW'):
            out, rec = self.rendered(grid, ('GE30', hand))
            self.assertEqual(rec['phases_per_arm'], 0)
            self.assertEqual(rec['foreground_cell_count'], 30 + 29 - 2)
            for d in (30, 31, 61, 100):
                self.assertEqual(out, step_expected(*args, pitch=d, hand=hand, extra=2))

    def test_endpoint_proposals_and_union_counts_separate(self):
        grid = scene(length=3)
        out, rec = self.rendered(grid)
        proposals = sum(len(a['initial_cells']) + sum(len(s['visible_cells']) for f in a['phases']
                                                     for s in f['segments']) for a in rec['arms'])
        self.assertEqual(proposals, rec['closed_segment_proposal_count'])
        self.assertGreater(proposals, rec['foreground_cell_count'])
        self.assertEqual(rec['changed_cell_count'], rec['foreground_cell_count'] - 12)
        self.assertEqual(sum(v == 6 for row in out for v in row), rec['foreground_cell_count'])

    def test_palette_zero_foreground_and_nonzero_bg(self):
        grid = scene(foreground=0, background=9)
        out, rec = self.rendered(grid)
        self.assertEqual(out, step_expected(foreground=0, background=9))
        self.assertEqual(out[5][6], 9)
        self.assertEqual(set(v for row in out for v in row), {0, 9})

    def test_mirror_swaps_hand(self):
        grid = scene()
        out, rec = self.rendered(grid)
        reflected = [row[::-1] for row in grid]
        opposite, _ = self.rendered(reflected, (2, 'CCW'))
        self.assertEqual(opposite, [row[::-1] for row in out])

    def test_tail_hands_remain_distinct_same_grid_models(self):
        models = (('GE30', 'CW'), ('GE30', 'CCW'))
        out, rec = p.predict(scene(), models)
        self.assertIsNotNone(out)
        self.assertEqual(len(rec['render_records']), 2)
        self.assertEqual(rec['models'], [['GE30', 'CW'], ['GE30', 'CCW']])

    def test_full_fit_retains_many_equal_teacher_models(self):
        inputs = [scene(3, 3, (1, 1), 1), scene(5, 5, (2, 2), 2)]
        models, rec = p.fit_teachers([{'input': g, 'output': copy.deepcopy(g)} for g in inputs])
        self.assertEqual(len(models), 56)
        self.assertEqual(rec['model_comparisons_completed'], 60)
        self.assertEqual(set(models), {(d, hand) for d in tuple(range(3, 30)) + ('GE30',)
                                      for hand in ('CW', 'CCW')})
        answer, detail = p.predict(scene(), models)
        self.assertIsNone(answer)
        self.assertEqual(detail['failure'], 'retained_curve_models_disagree')

    def test_empty_center_noop_is_permitted(self):
        grid = scene(3, 3, (1, 1), 1)
        out, rec = self.rendered(grid, ('GE30', 'CW'))
        self.assertEqual(out, grid)
        self.assertEqual(rec['changed_cell_count'], 0)

    def test_one_failed_model_does_not_leave_other_answer(self):
        original = p.render_curve
        def fail_one(payload, model):
            return (None, {'failure': 'synthetic_failure'}) if model[1] == 'CW' else original(payload, model)
        with patch.object(p, 'render_curve', fail_one):
            answer, rec = p.predict(scene(), (('GE30', 'CW'), ('GE30', 'CCW')))
        self.assertIsNone(answer)
        self.assertEqual(rec['failure'], 'retained_curve_model_failed')
        self.assertEqual(len(rec['render_records']), 2)

    def teachers(self):
        return [{'input': scene(length=k), 'output': step_expected(length=k)} for k in (1, 3)]

    def test_fit_all_teacher_comparisons_complete(self):
        models, rec = p.fit_teachers(self.teachers())
        self.assertEqual(models, ((2, 'CW'),))
        self.assertTrue(rec['complete'])
        self.assertEqual(len(rec['comparisons']), 60)
        self.assertTrue(all(len(c['teacher_equal']) == 2 for c in rec['comparisons']))

    def test_target_mismatch_does_not_short_circuit_models(self):
        teachers = self.teachers()
        teachers[0]['output'][5][6] = 6
        models, rec = p.fit_teachers(teachers)
        self.assertIsNone(models)
        self.assertEqual(rec['model_comparisons_completed'], 60)
        self.assertTrue(rec['complete'])

    def test_raw_teacher_failure_precedes_model_render(self):
        teachers = self.teachers()
        teachers[0]['input'][0][0] = 7
        with patch.object(p, 'render_curve', side_effect=RuntimeError('must not render')):
            models, rec = p.fit_teachers(teachers)
        self.assertIsNone(models)
        self.assertEqual(rec['model_comparisons_completed'], 0)

    def test_two_distinct_teacher_requirement(self):
        one = self.teachers()[0]
        self.assertEqual(p.fit_teachers([one, copy.deepcopy(one)])[1]['failure'],
                         'requires_two_distinct_teacher_inputs')

    def test_teacher_order_and_object_detachment(self):
        teachers = self.teachers()
        models, _ = p.fit_teachers(teachers)
        self.assertEqual(p.fit_teachers(teachers[::-1])[0], models)
        before = p.predict(scene(), models)
        teachers[0]['output'][:] = [[0]]
        teachers[0]['input'][:] = [[0]]
        self.assertEqual(p.predict(scene(), models), before)

    def test_interruption_after_fitted_model_discards_all(self):
        original = p.render_curve
        calls = [0]
        def interrupted(payload, model):
            calls[0] += 1
            if calls[0] == 7:
                raise RuntimeError('synthetic interruption after d2CW')
            return original(payload, model)
        with patch.object(p, 'render_curve', interrupted):
            models, rec = p.fit_teachers(self.teachers())
        self.assertIsNone(models)
        self.assertEqual(rec['completed_before_failure'], 3)
        self.assertTrue(rec['partial_models_discarded'])

    def test_invalid_model_schema(self):
        for models in ((), ((0, 'CW'),), ((True, 'CW'),), ((30, 'CW'),), ((2, 'other'),),
                       ((2, 'CW'), (2, 'CW')), ([2, 'CW'],)):
            self.assertIsNone(p.predict(scene(), models)[0])

    def test_unresolved_render_during_fit_discards_all(self):
        original = p.render_curve
        def unresolved(payload, model):
            if model == (29, 'CCW'):
                return None, {'failure': 'synthetic_unresolved_render'}
            return original(payload, model)
        with patch.object(p, 'render_curve', unresolved):
            models, rec = p.fit_teachers(self.teachers())
        self.assertIsNone(models)
        self.assertEqual(rec['failure'], 'curve_model_evaluation_failed')
        self.assertEqual(rec['failed_model'], [29, 'CCW'])
        self.assertTrue(rec['partial_models_discarded'])


    def native_teachers(self):
        fixtures = [(13, 17, (5, 6), 2), (15, 19, (6, 8), 3), (17, 21, (8, 9), 1)]
        return [{'input': scene(h, w, c, length),
                 'output': step_expected(h, w, c, length)} for h, w, c, length in fixtures]

    def test_native_support_is_three_boards(self):
        train = self.native_teachers()
        material = p.十字曲線教材(train)
        models, _ = p.fit_teachers(train)
        self.assertEqual(vars(material), {'共有規則': models})
        for minimum, admitted in ((3, True), (4, False)):
            machine = HDS学習実行系(最小支持数=minimum)
            record = 候補機構を学習(machine, {'train': train, 'test': []}, (),
                                    'ARC十字曲線延長', material.候補)
            self.assertEqual(record['現在観測数'], 3)
            self.assertEqual(record['事前観測数'], 0)
            self.assertEqual(record['同値採用'], admitted)
            self.assertEqual(record['隔離数'], 0)

    def test_native_query_order_and_teacher_detachment(self):
        train = self.native_teachers()
        good = scene(18, 23, (7, 9), 4)
        expected = step_expected(18, 23, (7, 9), 4)
        bad = copy.deepcopy(good)
        bad[0][0] = 7
        material = p.十字曲線教材(train)
        models = material.共有規則
        for queries, answers in (([good, bad], [expected, None]), ([bad, good], [None, expected])):
            solved = 課題を解く({'train': train, 'test': [{'input': g} for g in queries]}, [])
            self.assertEqual([row['answer'] for row in solved['results']], answers)
        train[0]['input'][:] = [[9]]
        train[0]['output'][:] = [[9]]
        self.assertEqual(vars(material), {'共有規則': models})
        self.assertEqual(material.候補(good, None)[0], expected)
        self.assertIsNone(material.候補(bad, None)[0])

    def test_native_rejects_identifier_and_test_output(self):
        with self.assertRaises(ValueError):
            課題を解く({'train': [], 'test': [], 'task_id': 'forbidden'}, [])
        with self.assertRaises(ValueError):
            課題を解く({'train': [], 'test': [{'input': [[0]], 'output': [[0]]}]}, [])


if __name__ == '__main__':
    unittest.main()
