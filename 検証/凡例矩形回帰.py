"""Synthetic controls for the complete bounded legend/extent program space."""
import copy
import unittest
from unittest.mock import patch
from pathlib import Path
import sys
根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / "HDS/学習系統/v0.4.2")]
from 接続.ARC2 import 凡例矩形教材 as p
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 課題を解く


def scene(rows=((1, 6),), sources=((1, (5, 8, 9, 13), 'TLBR'),), bg=0,
          h=20, w=26):
    grid = [[bg] * w for _ in range(h)]
    for i, (key, value) in enumerate(rows):
        grid[1 + i][1:3] = [key, value]
    for colour, (t, l, b, r), kind in sources:
        if kind == 'TLBR':
            cells = {(t, l), (t + 1, l), (t, l + 1),
                     (b, r), (b - 1, r), (b, r - 1)}
        elif kind == 'TRBL':
            cells = {(t, r), (t + 1, r), (t, r - 1),
                     (b, l), (b - 1, l), (b, l + 1)}
        else:
            cells = {(y, x) for y in range(t, b + 1) for x in range(l, r + 1)}
        for y, x in cells:
            grid[y][x] = colour
    return grid


def program(priority='FIRST', preservation='WHOLE_L3_COMPONENTS', null=None,
            action='LITERAL'):
    return priority, preservation, null, action


def overlap(unmapped=False, holes=False):
    rows = ((1, 0), (3, 6)) if unmapped else ((1, 0), (2, 6))
    inside = (2, (8, 11, 12, 17), 'TLBR') if holes else (2, (8, 11, 9, 13), 'RECT')
    return scene(rows, ((1, (5, 8, 15, 21), 'TLBR'), inside))


class BboxLegendControls(unittest.TestCase):
    def rendered(self, grid, model=program()):
        payload, record = p.parse_input(grid)
        self.assertIsNotNone(payload, record)
        return p.render_program(payload, model)

    def test_complete_program_space(self):
        self.assertEqual(len(p.PROGRAMS), 126)
        self.assertEqual(len(set(p.PROGRAMS)), 126)
        self.assertEqual(sum(m[2] is None for m in p.PROGRAMS), 6)

    def test_invalid_arc_grids(self):
        for g in ([], [[True]], [[-1]], [[10]], [[0], [0, 1]], [[0] * 31], [[0]] * 31):
            self.assertIsNone(p.parse_input(g)[0])

    def test_background_tie(self):
        self.assertIsNone(p.parse_input([[1, 2]])[0])

    def test_right_column_all_background_not_inferred(self):
        g = scene(((1, 0), (2, 0)), ())
        rec = p.raw_inventory(g)
        self.assertEqual(rec['raw_table_candidate_count'], 0)
        self.assertFalse(rec['source_typing_performed'])

    def test_background_value_and_unused_key(self):
        g = scene(((1, 0), (2, 7)))
        payload, rec = p.parse_input(g)
        self.assertIsNotNone(payload)
        self.assertEqual(rec['unused_table_keys'], [2])
        self.assertEqual(rec['unique_raw_table']['rows_top_to_bottom'][0]['value'], 0)

    def test_second_raw_table_blocks_source_typing(self):
        g = scene()
        g[15][2:4] = [8, 9]
        g[17][20] = 4
        with patch.object(p, 'source_geometry', side_effect=RuntimeError('must not type')):
            rec = p.raw_inventory(g)
        self.assertEqual(rec['raw_table_candidate_count'], 2)
        self.assertFalse(rec['source_typing_performed'])

    def test_duplicate_table_keys(self):
        g = scene(((1, 6), (1, 7)))
        self.assertEqual(p.raw_inventory(g)['raw_table_candidate_count'], 0)

    def test_dense_2x2_is_not_two_Ls(self):
        g = scene(sources=((1, (5, 8, 6, 9), 'RECT'),))
        payload, rec = p.parse_input(g)
        source = rec['sources'][0]
        self.assertEqual(source['matching_geometric_corner_explanations'], ['TL+BR', 'TR+BL'])
        self.assertTrue(source['filled_rectangle_match'])
        self.assertFalse(source['two_whole_three_cell_inward_L_source_match'])
        self.assertFalse(payload['sources'][0]['annotations'])
        out, record = p.render_program(payload, program())
        self.assertEqual(sum(v == 6 for row in out for v in row), 5)
        self.assertEqual(len(record['actions']['preserve_source']), 0)

    def test_dense_rectangles_bars_and_singletons(self):
        for box in ((5, 8, 8, 14), (5, 8, 5, 12), (5, 8, 10, 8), (5, 8, 5, 8)):
            g = scene(sources=((1, box, 'RECT'),))
            out, rec = self.rendered(g)
            t, l, b, r = box
            self.assertTrue(all(out[y][x] == 6 for y in range(t, b + 1) for x in range(l, r + 1)))
            self.assertEqual(len(rec['actions']['preserve_source']), 0)

    def test_both_corner_diagonals(self):
        for kind in ('TLBR', 'TRBL'):
            out, rec = self.rendered(scene(sources=((1, (5, 8, 9, 13), kind),)))
            self.assertEqual(len(rec['actions']['preserve_source']), 6)
            self.assertEqual(len(rec['actions']['literal']), 24)

    def test_whole_source_extra_component_rejected(self):
        g = scene()
        g[17][22] = 1
        payload, rec = p.parse_input(g)
        self.assertIsNone(payload)
        self.assertIn(1, rec['failed_source_geometry_colours'])

    def test_all_sources_checked_without_skip(self):
        g = scene()
        for colour, y in ((2, 14), (3, 17)):
            g[y][18] = colour
            g[y][21] = colour
        payload, rec = p.parse_input(g)
        self.assertIsNone(payload)
        self.assertEqual(rec['failed_source_geometry_colours'], [2, 3])

    def test_source_bbox_table_intersection(self):
        g = scene(((2, 7),), ((1, (0, 0, 15, 20), 'TLBR'),))
        g[1][1:3] = [0, 0]
        g[4][4:6] = [2, 7]
        payload, rec = p.parse_input(g)
        self.assertIsNone(payload)
        self.assertEqual(rec['source_bbox_table_intersection_colours'], [1])

    def test_full_row_count_not_observed_cap(self):
        g = scene(tuple((key, 9) for key in range(1, 9)), ())
        payload, rec = p.parse_input(g)
        self.assertIsNotNone(payload)
        self.assertEqual(len(rec['unique_raw_table']['rows_top_to_bottom']), 8)

    def test_first_and_last_are_opposite_owners(self):
        g = scene(((1, 4), (2, 6)), ((1, (5, 8, 9, 13), 'TLBR'),
                                   (2, (3, 6, 13, 20), 'TLBR')))
        a, ra = self.rendered(g, program())
        z, rz = self.rendered(g, program(priority='LAST'))
        self.assertEqual(a[7][10], 4)
        self.assertEqual(z[7][10], 6)
        self.assertEqual(ra['winner_colours'][7][10], 1)
        self.assertEqual(rz['winner_colours'][7][10], 2)

    def test_lower_annotation_is_not_globally_protected(self):
        g = scene(((2, 6), (1, 4)), ((1, (5, 8, 9, 13), 'TLBR'),
                                   (2, (3, 6, 13, 20), 'TLBR')))
        out, rec = self.rendered(g)
        self.assertEqual(g[5][8], 1)
        self.assertEqual(out[5][8], 6)

    def test_preservation_scope_shared_by_type(self):
        g = scene()
        a, ra = self.rendered(g, program(preservation='NONE'))
        b, rb = self.rendered(g, program(preservation='ALL_SOURCE'))
        c, rc = self.rendered(g)
        self.assertEqual(a[5][8], 6)
        self.assertEqual(b, c)
        g = scene(sources=((1, (5, 8, 6, 9), 'RECT'),))
        b, _ = self.rendered(g, program(preservation='ALL_SOURCE'))
        c, _ = self.rendered(g)
        self.assertEqual(b[5][8], 1)
        self.assertEqual(c[5][8], 6)

    def test_null_opaque_not_lower_rendered_content(self):
        g = overlap()
        out, rec = self.rendered(g, program(null=0, action='KEEP_ORIGINAL_INPUT'))
        self.assertEqual(out[8][11], 2)
        self.assertEqual(rec['winner_colours'][8][11], 1)
        self.assertNotEqual(out[8][11], 6)

    def test_null_actions_diverge_on_original_foreground(self):
        g = overlap()
        a, _ = self.rendered(g, program(null=0, action='RESET_BACKGROUND'))
        b, _ = self.rendered(g, program(null=0, action='KEEP_ORIGINAL_INPUT'))
        self.assertEqual(a[8][11], 0)
        self.assertEqual(b[8][11], 2)
        self.assertNotEqual(a, b)

    def test_unmapped_bbox_is_full_acceptance_invariant(self):
        for holes in (False, True):
            g = overlap(True, holes)
            a, ra = self.rendered(g, program(null=0, action='RESET_BACKGROUND'))
            b, rb = self.rendered(g, program(null=0, action='KEEP_ORIGINAL_INPUT'))
            self.assertIsNone(a)
            self.assertEqual(ra['failure'], 'unmapped_bbox_would_change')
            self.assertIsNotNone(b)
            self.assertTrue(all(b[r][c] == g[r][c] for r, c in rb['unmapped_protected_cells']))
            if holes:
                g[1][2] = 6
                literal, rl = self.rendered(g, program())
                self.assertIsNone(literal)
                self.assertIn([9, 12], rl['unmapped_protection_violations'])

    def test_one_retained_failure_vetoes_other_success(self):
        models = (program(null=0, action='RESET_BACKGROUND'),
                  program(null=0, action='KEEP_ORIGINAL_INPUT'))
        answer, rec = p.predict(overlap(True), models)
        self.assertIsNone(answer)
        self.assertEqual(rec['failure'], 'retained_program_failed')
        self.assertEqual(len(rec['render_records']), 2)

    def test_model_disagreement_is_hold(self):
        models = (program(null=0, action='RESET_BACKGROUND'),
                  program(null=0, action='KEEP_ORIGINAL_INPUT'))
        answer, rec = p.predict(overlap(), models)
        self.assertIsNone(answer)
        self.assertEqual(rec['failure'], 'retained_program_grids_disagree')

    def test_distinct_same_grid_models_are_all_kept(self):
        models = (program(), program(preservation='ALL_SOURCE'))
        answer, rec = p.predict(scene(), models)
        self.assertIsNotNone(answer)
        self.assertEqual(rec['model_count'], 2)
        self.assertEqual(len(rec['render_records']), 2)

    def test_self_map_fills_sparse_body(self):
        g = scene(((1, 1),))
        out, rec = self.rendered(g)
        self.assertEqual(g[7][10], 0)
        self.assertEqual(out[7][10], 1)
        self.assertEqual(rec['changed_cell_count'], 24)

    def test_reciprocal_values_do_not_cascade(self):
        g = scene(((1, 2), (2, 1)), ((1, (5, 8, 6, 10), 'RECT'),
                                   (2, (12, 17, 13, 19), 'RECT')))
        out, rec = self.rendered(g)
        self.assertEqual(out[5][8], 2)
        self.assertEqual(out[12][17], 1)

    def test_empty_scene_and_noop(self):
        g = scene(sources=())
        out, rec = self.rendered(g)
        self.assertEqual(out, g)
        self.assertEqual(rec['mapped_union_cell_count'], 0)

    def test_palette_zero_foreground_and_nonzero_bg(self):
        g = scene(((0, 8),), ((0, (5, 8, 9, 13), 'TRBL'),), bg=4)
        out, rec = self.rendered(g)
        self.assertEqual(out[7][10], 8)
        self.assertEqual(out[5][13], 0)
        self.assertTrue(rec['table_preserved'])
        self.assertTrue(rec['outside_mapped_union_preserved'])

    def test_complete_fit_and_target_detachment(self):
        inputs = [scene(), scene(sources=((1, (6, 9, 11, 14), 'TLBR'),))]
        teachers = [{'input': g, 'output': self.rendered(g)[0]} for g in inputs]
        models, rec = p.fit_teachers(teachers)
        self.assertIsNotNone(models)
        self.assertEqual(rec['programs_explored'], 126)
        self.assertTrue(all(len(row['teacher_equal']) == 2 for row in rec['program_comparisons']))
        before = p.predict(inputs[0], models)
        teachers[0]['output'][0][0] = 9
        teachers[1]['input'][0][0] = 9
        self.assertEqual(p.predict(inputs[0], models), before)

    def test_two_distinct_additional_support(self):
        g = scene()
        pair = {'input': g, 'output': self.rendered(g)[0]}
        model, rec = p.fit_teachers([pair, copy.deepcopy(pair)])
        self.assertIsNone(model)
        self.assertEqual(rec['failure'], 'requires_two_distinct_teacher_inputs')

    def test_exception_does_not_return_partial_fit(self):
        inputs = [scene(), scene(sources=((1, (6, 9, 11, 14), 'TLBR'),))]
        teachers = [{'input': g, 'output': self.rendered(g)[0]} for g in inputs]
        original = p.render_program
        count = [0]
        def interrupted(payload, model):
            count[0] += 1
            if count[0] == 101:
                raise RuntimeError('synthetic interruption')
            return original(payload, model)
        with patch.object(p, 'render_program', interrupted):
            models, rec = p.fit_teachers(teachers)
        self.assertIsNone(models)
        self.assertEqual(rec['failure'], 'program_comparison_incomplete')
        self.assertTrue(rec['partial_models_discarded'])

    def test_invalid_programs_and_duplicate_models(self):
        for models in ((), (program(), program()), (('FIRST', 'NONE', True, 'RESET_BACKGROUND'),),
                       (('FIRST', 'NONE', 10, 'RESET_BACKGROUND'),), (['FIRST', 'NONE', None, 'LITERAL'],)):
            self.assertIsNone(p.predict(scene(), models)[0])

    def native_teachers(self):
        result = []
        for shift in range(4):
            grid = scene(sources=((1, (5 + shift, 8, 9 + shift, 13), 'TLBR'),))
            result.append({'input': grid, 'output': self.rendered(grid)[0]})
        return result

    def test_native_support_is_four_boards(self):
        train = self.native_teachers()
        material = p.凡例矩形教材(train)
        models, _ = p.fit_teachers(train)
        self.assertEqual(vars(material), {'共有規則': models})
        for minimum, admitted in ((3, True), (5, False)):
            machine = HDS学習実行系(最小支持数=minimum)
            record = 候補機構を学習(machine, {'train': train, 'test': []}, (),
                                    'ARC凡例矩形転写', material.候補)
            self.assertEqual(record['現在観測数'], 4)
            self.assertEqual(record['事前観測数'], 0)
            self.assertEqual(record['同値採用'], admitted)
            self.assertEqual(record['隔離数'], 0)

    def test_native_query_order_failure_and_teacher_detachment(self):
        train = self.native_teachers()
        good = scene(sources=((1, (5, 8, 12, 16), 'TLBR'),))
        expected = self.rendered(good)[0]
        bad = overlap()
        material = p.凡例矩形教材(train)
        models = material.共有規則
        self.assertIsNone(material.候補(bad, None)[0])
        for queries, answers in (([good, bad], [expected, None]), ([bad, good], [None, expected])):
            solved = 課題を解く({'train': train, 'test': [{'input': g} for g in queries]}, [])
            self.assertEqual([row['answer'] for row in solved['results']], answers)
        train[0]['input'][:] = [[9]]
        train[0]['output'][:] = [[9]]
        self.assertEqual(vars(material), {'共有規則': models})
        self.assertEqual(material.候補(good, None)[0], expected)
        self.assertIsNone(material.候補(bad, None)[0])

    def test_native_rejects_task_identifier_and_test_output(self):
        with self.assertRaises(ValueError):
            課題を解く({'train': [], 'test': [], 'task_id': 'forbidden'}, [])
        with self.assertRaises(ValueError):
            課題を解く({'train': [], 'test': [{'input': [[0]], 'output': [[0]]}]}, [])


if __name__ == '__main__':
    unittest.main()
