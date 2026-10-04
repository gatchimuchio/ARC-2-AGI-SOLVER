"""Synthetic controls for all-layer geometry and symbolic colour priorities."""
import copy
import unittest
from unittest.mock import patch
from pathlib import Path
import sys
根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / "HDS/学習系統/v0.4.2")]
from 接続.ARC2 import 遮蔽区画教材 as p
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 課題を解く


def scene(counts=(1, 2), colours=(2, 4), background=0, noise=7, shift=0):
    g = [[background] * 28 for _ in range(12)]
    start = 1
    for n, colour in zip(counts, colours):
        r0, r1, c0, c1 = 1 + shift, 5 + shift, start, start + 2 * n
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if r in (r0, r1) or (c - c0) % 2 == 0:
                    g[r][c] = colour
        start = c1 + 4
    g[10][1] = noise
    return g


def expected(counts, colours, noise):
    return [[c] * n + [noise] * (max(counts) - n) for n, c in sorted(zip(counts, colours))]

COUNT_CONFLICT_ROWS = ('9000000000000', '0111111111000', '0100010001000', '0122210001000', '0120210001000', '0122210001000', '0120210001000', '0122210001000', '0100010001000', '0111111111000', '0000000000000', '0000000000000', '0000000000000')
ORDER_VETO_ROWS = ('900000000000000', '011111111111000', '010000000101000', '010222220101000', '010200020101000', '011222229101000', '010200020101000', '010222220101000', '010000000101000', '010000000101000', '010000000101000', '011111111111000', '000000000000000', '000000000000000', '000000000000000')


class PartitionControls(unittest.TestCase):
    def test_valid_layer_orders_with_different_counts_hold(self):
        grid = [[int(c) for c in row] for row in COUNT_CONFLICT_ROWS]
        payload, rec = p.parse_input(grid)
        self.assertIsNone(payload)
        self.assertEqual(rec['failure'], 'layer_order_counts_disagree')
        self.assertEqual(rec['failed_order_indices'], [])
        self.assertEqual(len(rec['orders']), 2)
        self.assertEqual([r['counts'] for r in rec['geometry_records']],
                         [[(1, 5), (2, 2)], [(1, 2), (2, 2)]])

    def test_one_invalid_layer_order_vetoes_valid_order(self):
        grid = [[int(c) for c in row] for row in ORDER_VETO_ROWS]
        payload, rec = p.parse_input(grid)
        self.assertIsNone(payload)
        self.assertEqual(rec['failure'], 'retained_layer_order_failed')
        self.assertEqual(len(rec['orders']), 2)
        self.assertEqual(rec['failed_order_indices'], [1])
        self.assertTrue(rec['geometry_records'][0]['valid'])
        self.assertFalse(rec['geometry_records'][1]['valid'])

    def test_two_disjoint_frames_all_orders(self):
        g = scene()
        out, rec = p.predict(g, ())
        self.assertEqual(out, expected((1, 2), (2, 4), 7))
        self.assertEqual(len(rec['input_record']['orders']), 2)
        self.assertTrue(rec['input_record']['all_layer_orders_masks_equal'])

    def test_all_arc_colour_roles(self):
        g = scene(background=9, noise=0, colours=(6, 8))
        out, _ = p.predict(g, ())
        self.assertEqual(out, expected((1, 2), (6, 8), 0))

    def test_colour_zero_can_be_signal(self):
        g = scene(background=9, noise=7, colours=(0, 5))
        out, _ = p.predict(g, ())
        self.assertEqual(out, expected((1, 2), (0, 5), 7))

    def test_hidden_corner_is_boundary_prior(self):
        g = scene()
        g[1][1] = 7
        payload, rec = p.parse_input(g)
        self.assertIsNotNone(payload)
        signal = rec['geometry_records'][0]['signals'][0]
        added = int(signal['perimeter_prior_added'], 16)
        self.assertEqual(added, 1 << 29)
        self.assertEqual(signal['region_count'], 1)
        self.assertFalse(signal['bridge_edges'])

    def test_new_perimeter_not_used_as_line_witness(self):
        g = [[0] * 12 for _ in range(11)]
        for r in range(1, 8):
            for c in range(1, 8):
                if r in (1, 4, 7) or c in (1, 7):
                    g[r][c] = 2
        for r in (1, 2, 3, 5, 6, 7):
            g[r][4] = 7
        g[9][0] = 7
        payload, rec = p.parse_input(g)
        self.assertEqual(payload['counts'], {2: 2})
        mask = int(rec['geometry_records'][0]['signals'][0]['final'], 16)
        self.assertFalse((mask >> (2 * 12 + 4)) & 1)

    def test_unknown_extra_colour_not_dropped(self):
        g = scene()
        g[9][18] = 8
        out, _ = p.predict(g, ())
        self.assertIsNone(out)

    def test_all_pixels_of_signal_affect_bbox(self):
        g = scene()
        g[9][18] = 2
        out, _ = p.predict(g, ())
        self.assertIsNone(out)

    def test_background_perimeter_hole(self):
        g = scene()
        g[1][2] = 0
        payload, rec = p.parse_input(g)
        self.assertIsNone(payload)
        self.assertFalse(rec['geometry_reached'])

    def test_raw_multiple_noise_roles_before_geometry(self):
        g = scene()
        g[10][1] = 0
        with patch.object(p, 'layer_orders', side_effect=AssertionError('not reached')):
            payload, rec = p.parse_input(g)
        self.assertIsNone(payload)
        self.assertEqual(len(rec['raw']['joint_roles']), 2)

    def test_background_tie(self):
        payload, rec = p.parse_input([[0, 1]])
        self.assertIsNone(payload)
        self.assertEqual(rec['raw']['failure'], 'background_mode_not_unique')

    def test_invalid_grid(self):
        for g in ([], [[0], [0, 1]], [[True]], [[11]], [[0] * 31]):
            self.assertIsNone(p.parse_input(g)[0])

    def test_dangling_signal_whole_order_fails(self):
        g = scene()
        g[2][2] = 2
        g[3][2] = 2
        payload, rec = p.parse_input(g)
        self.assertIsNone(payload)
        self.assertEqual(rec['failure'], 'retained_layer_order_failed')
        self.assertEqual(len(rec['failed_order_indices']), len(rec['orders']))

    def test_filled_2x2_is_not_a_thin_partition(self):
        g = scene()
        g[2][2] = 2
        payload, rec = p.parse_input(g)
        self.assertIsNone(payload)
        self.assertTrue(any(s['full_2x2'] for r in rec['geometry_records'] for s in r['signals']))

    def test_layer_budget_exact_and_one_below(self):
        g = scene()
        needed = p.parse_input(g)[1]['enumeration']['prefixes']
        with patch.object(p, 'MAX_PREFIXES', needed):
            self.assertIsNotNone(p.parse_input(g)[0])
        with patch.object(p, 'MAX_PREFIXES', needed - 1):
            with patch.object(p, 'complete_order', side_effect=AssertionError('must not run')):
                payload, rec = p.parse_input(g)
        self.assertIsNone(payload)
        self.assertFalse(rec['geometry_reached'])
        self.assertEqual(rec['orders'], [])
        self.assertGreater(rec['enumeration']['discovered_orders'], 0)

    def test_nine_foreground_prefix_domain_incomplete(self):
        g = [[0] * 30 for _ in range(20)]
        for i, colour in enumerate(range(1, 9)):
            r0, c0 = 1 + 5 * (i // 4), 1 + 6 * (i % 4)
            for r in range(r0, r0 + 3):
                for c in range(c0, c0 + 3):
                    if r in (r0, r0 + 2) or c in (c0, c0 + 2):
                        g[r][c] = colour
        g[18][28] = 9
        with patch.object(p, 'complete_order', side_effect=AssertionError('must not run')):
            payload, rec = p.parse_input(g)
        self.assertIsNone(payload)
        self.assertFalse(rec['enumeration']['complete'])
        self.assertEqual(rec['enumeration']['prefixes'], 100000)
        self.assertEqual(rec['raw']['joint_roles'][0]['order_count'], 40320)

    def test_output_width_thirty_and_thirty_one(self):
        for rows, cols, desired in ((5, 6, 30), (4, 8, 31)):
            g = [[0] * 30 for _ in range(20)]
            for r in range(1, 2 * rows + 2):
                for c in range(1, 2 * cols + 2):
                    if r % 2 or c % 2:
                        g[r][c] = 2
            if desired == 31:
                g[2][3] = 0
            g[18][28] = 7
            out, rec = p.predict(g, ())
            if desired == 30:
                self.assertEqual(out, [[2] * 30])
                self.assertEqual(rec['render_record']['noise_padding_cells'], 0)
            else:
                self.assertIsNone(out)
                self.assertEqual(rec['input_record']['geometry_records'][0]['counts'], [(2, 31)])

    def test_unknown_equal_count_priority_holds(self):
        g = scene(counts=(1, 1))
        out, rec = p.predict(g, ())
        self.assertIsNone(out)
        self.assertEqual(rec['failure'], 'unresolved_equal_count_priority')

    def test_learned_priority_can_reverse_numeric_labels(self):
        g = scene(counts=(1, 1))
        out, _ = p.predict(g, ((4, 2),))
        self.assertEqual(out, [[4], [2]])

    def test_transitive_path_through_absent_colour(self):
        g = scene(counts=(1, 1))
        out, _ = p.predict(g, ((2, 6), (6, 4)))
        self.assertEqual(out, [[2], [4]])

    def test_priority_cycle_and_invalid_values(self):
        for edges in (((2, 4), (4, 2)), ((2, 2),), ((False, 2),), ((2, 10),), None):
            self.assertIsNone(p.predict(scene(), edges)[0])

    def test_fit_preserves_all_unconstrained_priorities(self):
        teachers = [{'input': scene(shift=k), 'output': expected((1, 2), (2, 4), 7)} for k in (0, 2)]
        model, rec = p.fit_teachers(teachers)
        self.assertEqual(model, ())
        self.assertEqual(rec['consistent_total_colour_orders'], 3628800)
        self.assertIsNone(p.predict(scene(counts=(1, 1)), model)[0])

    def test_fit_tied_priority_and_teacher_object_independence(self):
        teachers = [{'input': scene(counts=(1, 1), shift=k), 'output': [[4], [2]]} for k in (0, 2)]
        model, rec = p.fit_teachers(teachers)
        self.assertEqual(model, ((4, 2),))
        self.assertEqual(rec['consistent_total_colour_orders'], 1814400)
        before = p.predict(scene(counts=(1, 1)), model)
        teachers[0]['output'][0][0] = 9
        self.assertEqual(p.predict(scene(counts=(1, 1)), model), before)

    def test_contradictory_teacher_ties_reject(self):
        teachers = [{'input': scene(counts=(1, 1), shift=0), 'output': [[4], [2]]},
                    {'input': scene(counts=(1, 1), shift=2), 'output': [[2], [4]]}]
        self.assertEqual(p.fit_teachers(teachers)[1]['failure'], 'no_shared_priority_order')

    def test_target_change_does_not_change_input_geometry(self):
        teachers = [{'input': scene(shift=k), 'output': expected((1, 2), (2, 4), 7)} for k in (0, 2)]
        records = p.fit_teachers(teachers)[1]['input_records']
        teachers[0]['output'] = [[9]]
        model, rec = p.fit_teachers(teachers)
        self.assertIsNone(model)
        self.assertEqual(rec['input_records'], records)

    def test_distinct_teacher_condition(self):
        pair = {'input': scene(), 'output': expected((1, 2), (2, 4), 7)}
        self.assertIsNone(p.fit_teachers([pair, copy.deepcopy(pair)])[0])


    def test_native_support_is_three_boards(self):
        train = [
            {'input': scene(counts=(1, 1), colours=(6, 8), shift=0), 'output': [[8], [6]]},
            {'input': scene(counts=(1, 2), colours=(6, 8), shift=1),
             'output': expected((1, 2), (6, 8), 7)},
            {'input': scene(counts=(2, 3), colours=(6, 8), shift=2),
             'output': expected((2, 3), (6, 8), 7)},
        ]
        material = p.遮蔽区画教材(train)
        self.assertEqual(vars(material), {'色順序': ((8, 6),)})
        for minimum, admitted in ((3, True), (4, False)):
            machine = HDS学習実行系(最小支持数=minimum)
            record = 候補機構を学習(machine, {'train': train, 'test': []}, (),
                                    'ARC遮蔽区画計数', material.候補)
            self.assertEqual(record['現在観測数'], 3)
            self.assertEqual(record['事前観測数'], 0)
            self.assertEqual(record['同値採用'], admitted)
            self.assertEqual(record['隔離数'], 0)

    def test_native_query_order_and_unseen_tie_hold(self):
        train = [
            {'input': scene(counts=(1, 1), colours=(6, 8), shift=0), 'output': [[8], [6]]},
            {'input': scene(counts=(1, 2), colours=(6, 8), shift=1),
             'output': expected((1, 2), (6, 8), 7)},
            {'input': scene(counts=(2, 3), colours=(6, 8), shift=2),
             'output': expected((2, 3), (6, 8), 7)},
        ]
        good = scene(counts=(3, 2), colours=(6, 8))
        answer = expected((3, 2), (6, 8), 7)
        bad = scene(counts=(1, 1), colours=(2, 4))
        for queries, answers in (([good, bad], [answer, None]), ([bad, good], [None, answer])):
            solved = 課題を解く({'train': train, 'test': [{'input': g} for g in queries]}, [])
            self.assertEqual([r['answer'] for r in solved['results']], answers)
        material = p.遮蔽区画教材(train)
        train[0]['input'][:] = [[0]]
        train[0]['output'][:] = [[0]]
        self.assertEqual(vars(material), {'色順序': ((8, 6),)})
        self.assertEqual(material.候補(good, None)[0], answer)
        self.assertIsNone(material.候補(bad, None)[0])

    def test_native_rejects_task_identifier_and_test_output(self):
        with self.assertRaises(ValueError):
            課題を解く({'train': [], 'test': [], 'task_id': 'forbidden'}, [])
        with self.assertRaises(ValueError):
            課題を解く({'train': [], 'test': [{'input': [[0]], 'output': [[0]]}]}, [])


if __name__ == '__main__':
    unittest.main()
