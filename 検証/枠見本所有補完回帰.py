"""Existing partial-panel family: strict delegation and complete exemplar ownership."""
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(根))
from 接続.ARC2 import 部分見本教材 as adapter
from 接続.ARC2 import 枠見本所有補完 as core
from 検証.部分見本回帰 import 教師 as panel_teachers


def teachers():
    return json.loads((根 / '検証/枠見本所有資料/教師.json').read_text())


# Reused independent ordinary scene from the previous composition checks.
def ordinary_scene():
    grid = [[0] * 29 for _ in range(19)]
    for r in range(8, 17):
        for c in range(1, 14):
            if r in (8, 16) or c in (1, 13):
                grid[r][c] = 5
    red = [[1, 1, 1], [1, 0, 0], [1, 1, 1]]
    green = [[1, 1, 1], [0, 1, 0], [0, 1, 0]]
    for left, color in ((3, 2), (8, 3)):
        for r in range(10, 13):
            for c in range(left, left + 3):
                grid[r][c] = color
    for top, left, color, mask in ((1, 1, 2, red), (1, 6, 3, green)):
        for r, row in enumerate(mask):
            for c, value in enumerate(row):
                grid[top + r][left + c] = color if value else 0
    for left, source, target in ((1, 2, 6), (6, 3, 7)):
        for r in (5, 6):
            grid[r][left:left + 2] = [source, target]
    expected = [row[1:14] for row in grid[8:17]]
    for left, target, mask in ((2, 6, red), (7, 7, green)):
        for r, row in enumerate(mask):
            for c, value in enumerate(row):
                expected[2 + r][left + c] = target if value else 0
    return grid, expected


# Reused complete-window example: a C and its isolated center own 14 cells.
def fragmented_scene():
    grid = [[0] * 24 for _ in range(19)]
    for r in range(7, 16):
        for c in range(1, 10):
            if r in (7, 15) or c in (1, 9):
                grid[r][c] = 5
    for r in range(9, 14):
        for c in range(3, 8):
            grid[r][c] = 2
    mask = [[int(r in (0, 4) or c == 0 or (r, c) == (2, 2))
             for c in range(5)] for r in range(5)]
    for r, row in enumerate(mask):
        for c, value in enumerate(row):
            grid[1 + r][1 + c] = 2 if value else 0
    grid[1][8:10] = [2, 6]
    expected = [row[1:10] for row in grid[7:16]]
    for r, row in enumerate(mask):
        for c, value in enumerate(row):
            expected[2 + r][2 + c] = 6 if value else 0
    return grid, expected


class 枠見本所有補完回帰(unittest.TestCase):
    def setUp(self):
        self.models = [('identity', 'keep', 'paired')]

    def test_01_original_teachers_all32_and_adapter(self):
        pairs = teachers()
        models, record = core.fit_teachers(pairs)
        self.assertEqual(models, self.models)
        self.assertEqual(record['program_count'], 32)
        self.assertEqual(len(record['trials']), 32)
        material = adapter.部分見本教材(pairs)
        self.assertEqual(material.枠見本モデル群, tuple(self.models))
        for pair in pairs:
            self.assertEqual(material.候補(pair['input'], None)[0], pair['output'])
        json.dumps(material.記録())

    def test_02_old_positive_output_and_record_delegate(self):
        pairs = panel_teachers()
        original = adapter._元部分見本教材(pairs)
        with patch.object(core, 'fit_teachers', side_effect=AssertionError('unexpected fallback')):
            current = adapter.部分見本教材(pairs)
        self.assertEqual(current.全教師再現, original.全教師再現)
        self.assertEqual(current.記録(), original.記録())
        for grid in [pair['input'] for pair in pairs] + [[]]:
            self.assertEqual(current.候補(grid, None), original.候補(grid, None))

    def test_03_finish_every_old_teacher_before_fallback(self):
        pairs = teachers()
        with patch.object(adapter, 'guarded_panel_exemplar', wraps=adapter.guarded_panel_exemplar) as old:
            material = adapter.部分見本教材(pairs)
        # Original all(...) stops on its first mismatch; then both are completed.
        self.assertEqual(old.call_count, 3)
        self.assertIsNotNone(material.枠見本モデル群)

    def test_04_original_errors_and_incomplete_returns_propagate(self):
        for error in (MemoryError, TimeoutError, ValueError):
            with patch.object(adapter, 'guarded_panel_exemplar', side_effect=error('injected')):
                with patch.object(core, 'fit_teachers') as fit:
                    with self.assertRaises(error):
                        adapter.部分見本教材(teachers())
                    fit.assert_not_called()
        with patch.object(adapter, 'guarded_panel_exemplar', return_value=(None, {
                'failure': 'no_valid_panel_exemplar_group', 'complete': False})):
            with patch.object(core, 'fit_teachers') as fit:
                with self.assertRaisesRegex(ValueError, 'original_panel_fit_incomplete'):
                    adapter.部分見本教材(teachers())
                fit.assert_not_called()

    def test_05_framed_errors_and_incomplete_returns_propagate(self):
        with patch.object(core, 'fit_teachers', return_value=(None, {'complete': False})):
            with self.assertRaisesRegex(ValueError, 'framed_panel_fit_incomplete'):
                adapter.部分見本教材(teachers())
        for error in (MemoryError, TimeoutError, ValueError):
            with patch.object(core, 'fit_teachers', side_effect=error('injected')):
                with self.assertRaises(error):
                    adapter.部分見本教材(teachers())

    def test_06_duplicate_and_invalid_teachers_never_enter_fallback(self):
        pair = teachers()[0]
        for pairs in ([], [pair, deepcopy(pair)], [{'input': [], 'output': [[0]]}]):
            with patch.object(core, 'fit_teachers') as fit:
                material = adapter.部分見本教材(pairs)
                self.assertEqual(material.記録(), {'全教師再現': False})
                fit.assert_not_called()

    def test_07_global_chain_and_all_ambiguous_card_assignments(self):
        grid, expected = ordinary_scene()
        for r in (5, 6):
            grid[r][2] = 3
        expected = [[3 if value == 6 else value for value in row] for row in expected]
        output, record = core.render(grid, self.models)
        self.assertEqual(output, expected)
        self.assertEqual(record['legend_ownership_count'], 1)
        for r in (5, 6):
            grid[r][16:18] = [2, 3]
        output, record = core.render(grid, self.models)
        self.assertIsNone(output)
        self.assertEqual(record['legend_ownership_count'], 3)
        self.assertEqual(record['executions'][0]['assignment_count'], 6)

    def test_08_fragmented_window_and_global_legend_composition(self):
        grid, expected = fragmented_scene()
        self.assertIsNone(core.render_strict111(grid, self.models)[0])
        output, record = core.render(grid, self.models)
        self.assertEqual(output, expected)
        self.assertEqual(record['complete_partition_count'], 1)
        window = record['glyph_window_partitions'][2]['windows'][0]
        self.assertEqual(window['components'], [0, 1])
        self.assertEqual(len(window['cells']), 14)
        grid, expected = ordinary_scene()
        for r in (5, 6):
            grid[r][2] = 3
        grid[3][2] = 0
        expected = [[3 if value == 6 else value for value in row] for row in expected]
        expected[4][3] = 0
        self.assertEqual(core.render(grid, self.models)[0], expected)

    def test_09_foreign_card_leftover_and_clipping_preserve_hold(self):
        grid, _ = fragmented_scene()
        for row, col in ((17, 21), (1, 6)):
            malformed = deepcopy(grid)
            malformed[row][col] = 2
            self.assertEqual(core.render(malformed, self.models),
                             core.render_strict111(malformed, self.models))
            self.assertIsNone(core.render(malformed, self.models)[0])
        foreign = deepcopy(grid)
        foreign[3][4] = 6
        observed, _ = core.observe(foreign)
        partitions, record = core.complete_glyph_partitions(foreign, observed)
        self.assertEqual(partitions, [])
        self.assertEqual(record[2]['window_count'], 0)
        self.assertEqual(core.render(foreign, self.models), core.render_strict111(foreign, self.models))

    def test_10_all_complete_partitions_and_retained_programs(self):
        grid, _ = fragmented_scene()
        for r in range(1, 6):
            for c in range(1, 6):
                grid[r][c] = 2 if (r, c) in ((1, 1), (1, 5), (5, 1), (5, 5)) else 0
        for r in range(10, 14):
            for c in range(3, 8):
                grid[r][c] = 0
        output, record = core.render(grid, self.models)
        self.assertIsNone(output)
        self.assertEqual(record['complete_partition_count'], 2)
        self.assertEqual(record['glyph_window_partitions'][2]['window_count'], 4)
        self.assertEqual([p['executions'][0]['assignment_count'] for p in record['partitions']], [2, 2])
        grid, _ = fragmented_scene()
        output, record = core.render(grid, self.models + [('flip_h', 'keep', 'paired')])
        self.assertIsNone(output)
        self.assertEqual(record['failure'], 'complete_glyph_partition_grids_disagree')


if __name__ == '__main__':
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(枠見本所有補完回帰))
    if not result.wasSuccessful():
        sys.stderr.write(stream.getvalue())
    print(json.dumps({'tests_run': result.testsRun, 'successful': result.wasSuccessful()}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
