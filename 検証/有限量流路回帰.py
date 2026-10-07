"""Ordinary compacting, wall, inventory and branch-consensus contrasts."""
from collections import Counter
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from 接続.ARC2 import 有限量流路接続 as finite


class FiniteFlowChecks(unittest.TestCase):
    def test_vertical_compaction_preserves_multicolor_walls_and_counts(self):
        grid = [[0, 1, 0], [2, 0, 3], [2, 0, 3], [2, 2, 3]]
        output, record = finite.render(grid, (0, 1))
        expected = [[0, 0, 0], [2, 0, 3], [2, 1, 3], [2, 2, 3]]
        self.assertEqual(output, expected)
        self.assertEqual(record['terminal_count'], 1)
        self.assertEqual(Counter(sum(output, [])), Counter(sum(grid, [])))
        self.assertTrue(finite.expected_terminal(output, 0, 1))
        self.assertFalse(finite.expected_terminal(grid, 0, 1))

    def test_equal_level_alternatives_hold(self):
        grid = [[0, 0, 0], [0, 1, 0], [0, 2, 0], [2, 2, 2]]
        output, record = finite.render(grid, (0, 1))
        self.assertIsNone(output)
        self.assertTrue(record['search_complete'])
        self.assertEqual(record['terminal_count'], 2)
        self.assertEqual({tuple(map(tuple, s)) for s in record['terminal_states']},
                         {((2, 0),), ((2, 2),)})

    def test_all_branches_can_converge(self):
        grid = [[0, 1, 0], [0, 1, 0], [0, 2, 0], [2, 2, 2]]
        output, record = finite.render(grid, (0, 1))
        self.assertEqual(output, [[0, 0, 0], [0, 0, 0], [1, 2, 1], [2, 2, 2]])
        self.assertGreater(record['legal_spills'], 1)
        self.assertEqual(record['terminal_count'], 1)

    def test_fixed_wall_blocks_lateral_path(self):
        grid = [[0, 0, 0], [4, 1, 5], [0, 2, 0], [2, 2, 2]]
        output, record = finite.render(grid, (0, 1))
        self.assertEqual(output, grid)
        self.assertEqual(record['legal_spills'], 0)

    def test_strict_validation(self):
        for grid in ([], [[True]], [[10]], [[0], [0, 1]], [[0] * 31]):
            self.assertEqual(finite.render(grid, (0, 1))[1]['failure'], 'invalid_arc_grid')
        grid = [[0, 1], [2, 0]]
        for role in ((0, 0), (0, True), (0, 10), [0, 1]):
            self.assertEqual(finite.render(grid, role)[1]['failure'], 'invalid_finite_roles')
        pair = {'input': grid, 'output': grid}
        for teachers in (None, [], [pair], [pair, pair],
                         [{'input': grid, 'output': [[True]]}]):
            self.assertEqual(finite.fit(teachers), ())


if __name__ == '__main__':
    unittest.main()
