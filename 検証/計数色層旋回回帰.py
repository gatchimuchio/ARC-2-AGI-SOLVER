"""Small ordinary contrasts and the supplied teacher packet only."""
import hashlib
import json
from pathlib import Path
import resource
import time
import unittest
import sys
from unittest.mock import patch

resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[1] / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 計数色層旋回候補 as c

ROOT = Path(__file__).resolve().parent / '計数色層旋回資料'
TEACHERS = json.loads((ROOT / 'teachers-only.json').read_text())['train']


class OrdinaryContrasts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate = c.LayerTurnCandidate(TEACHERS)

    def test_all_teacher_cells(self):
        self.assertEqual(self.candidate.programs, ('rot90',))
        for pair in TEACHERS:
            self.assertEqual(self.candidate.predict(pair['input'])[0], pair['output'])
        self.assertEqual(sum(len(p['output'])*len(p['output'][0]) for p in TEACHERS), 369)

    def test_recolor_shift_and_cue_orientation(self):
        pair = TEACHERS[0]
        # Recolor all values, move the scene down/right on a larger rectangle,
        # and rotate its detached cyan domino in place without changing count.
        source = [row[:] for row in pair['input']]
        source[17][1] = 0
        source[16][2] = 8
        mapping = {i: (i + 7) % 10 for i in range(10)}
        shifted = [[mapping[0]] * 24 for _ in range(23)]
        for r, row in enumerate(source):
            for col, value in enumerate(row):
                shifted[r+1][col+2] = mapping[value]
        expected = [[mapping[v] for v in row] for row in pair['output']]
        self.assertEqual(self.candidate.predict(shifted)[0], expected)

    def test_unowned_and_nonstraight_cues_hold(self):
        nonstraight = [row[:] for row in TEACHERS[0]['input']]
        nonstraight[18][6] = 3
        nonstraight[19][5] = 3
        self.assertEqual(c.parse(nonstraight)[0], ())
        self.assertIsNone(self.candidate.predict(nonstraight)[0])
        unowned = [row[:] for row in TEACHERS[0]['input']]
        unowned[19][0] = 9
        self.assertEqual(c.parse(unowned)[0], ())
        self.assertIsNone(self.candidate.predict(unowned)[0])

    def test_all_square_roles_remain(self):
        grid = [[0] * 8 for _ in range(8)]
        for r, col in ((0, 2), (2, 0), (6, 6)):
            grid[r][col] = 2
        for r, col in ((0, 0), (1, 1), (4, 4)):
            grid[r][col] = 3
        roles, _ = c.parse(grid)
        boxes = {role.bbox for role in roles}
        self.assertIn((0, 0, 2, 2), boxes)
        self.assertIn((0, 0, 4, 4), boxes)
        result, record = c.render_roles(roles, 'identity')
        self.assertIsNone(result)
        self.assertEqual(record['failure'], 'eligible_roles_disagree')

    def test_failed_role_and_runtime_error_propagation(self):
        # Two independently moved color masks collide. A successful other
        # role cannot rescue the failed eligible role.
        collision = c.Role(0, (0, 0, 2, 2), (
            (2, frozenset({(0, 0)}), 1, ((5, 5),)),
            (3, frozenset({(0, 2)}), 0, ()),
        ))
        self.assertIsNone(c.render_role(collision, 'rot90')[0])
        good = c.parse(TEACHERS[0]['input'])[0][0]
        self.assertIsNone(c.render_roles((good, collision), 'rot90')[0])
        with patch.object(c, 'transform_grid_by_name', side_effect=RuntimeError('injected')):
            with self.assertRaisesRegex(RuntimeError, 'injected'):
                self.candidate.predict(TEACHERS[0]['input'])

    def test_all_fitted_programs_remain(self):
        # A symmetric square layer and center leave all eight actions fitted.
        grid = [[0] * 8 for _ in range(8)]
        for r in range(3):
            for col in range(3):
                grid[r][col] = 3 if (r, col) == (1, 1) else 2
        grid[6][6] = 2
        expected = [row[:3] for row in grid[:3]]
        ambiguous = c.LayerTurnCandidate([{'input': grid, 'output': expected}])
        self.assertEqual(ambiguous.programs, c.D4)
        self.assertIsNone(ambiguous.predict(TEACHERS[0]['input'])[0])


if __name__ == '__main__':
    started = time.monotonic()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(OrdinaryContrasts)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    candidate = c.LayerTurnCandidate(TEACHERS)
    report = {
        'scope': 'supplied teachers and ordinary synthetic contrasts only',
        'tests_run': result.testsRun,
        'success': result.wasSuccessful(),
        'teacher_cells': 369,
        'fit': candidate.記録(),
        'teacher_results': [
            {'index': i+1, 'exact': candidate.predict(p['input'])[0] == p['output'],
             'record': candidate.predict(p['input'])[1]}
            for i, p in enumerate(TEACHERS)
        ],
        'wall_seconds': time.monotonic() - started,
        'max_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'limits': {'cpu_seconds': 10, 'address_space_mib': 512},
    }
    (ROOT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'successful': result.wasSuccessful(), 'tests_run': result.testsRun}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
