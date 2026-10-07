# NEW current ordinary113: five existing ordinary checks using independently specified current controls.
"""Original teachers, tiny scaffold contrast, and conservative family binding."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from 接続.ARC2 import 配置展開教材 as family
from 接続.ARC2 import 枠命令配置接続 as binding
from 接続.ARC2 import 全枠命令配置 as view

DATA = ROOT / '検証/枠命令配置資料'
TEACHERS = next(iter(json.loads((DATA / 'teachers-only.json').read_text()).values()))['train']
CONTROL = json.loads((DATA / 'new-current-ordinary-controls.json').read_text())
MODEL = tuple(CONTROL['model'])


def old_teacher(alternate=False):
    tile = [[1, 2], [2, 1]] if alternate else [[1, 2, 0], [2, 1, 1]]
    mask = [[3, 3, 3], [0, 3, 0]] if alternate else [[3, 0], [3, 3]]
    grid = [[0] * 14 for _ in range(11)]
    for values, top, left in ((tile, 1, 1), (mask, 6, 9)):
        for row, values_row in enumerate(values):
            grid[top + row][left:left + len(values_row)] = values_row
    return {'input': grid, 'output': family.render_layout_mask_macro_tile_expander(grid)[0]}


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.material = family.配置展開教材(TEACHERS)

    def test_original_teachers(self):
        material = self.material
        self.assertFalse(material.適合)
        self.assertEqual(len(material.枠命令モデル群), 1)
        for teacher in TEACHERS:
            self.assertEqual(material.候補(teacher['input'], None)[0], teacher['output'])
            self.assertEqual(view.frozen.consensus(teacher['input'], material.枠命令モデル群)[0], teacher['output'])
        record = material.枠命令適合記録
        self.assertEqual(record['evaluated_teacher_calls'], 2048 * 3)
        self.assertEqual(record['symbolic_unexecuted_teacher_calls'], 0)
        self.assertEqual(len(record['teacher_parse_witnesses']), 3)
        self.assertNotIn('teacher_parse_witnesses', material.記録()['全教師共通枠命令配置'])
        self.assertLess(len(json.dumps(material.記録())), 2000)

    def test_padding_and_disconnected_frame(self):
        for name in ('thin', 'thick', 'stray'):
            expected = CONTROL['expected'] if name != 'stray' else None
            self.assertEqual(view.render(CONTROL[name], MODEL)[0], expected)
        self.assertEqual(view.frozen.render(CONTROL['thin'], MODEL)[0], CONTROL['expected'])
        self.assertIsNone(view.frozen.render(CONTROL['thick'], MODEL)[0])

    def test_legacy_positive_state_and_records(self):
        teachers = [old_teacher(), old_teacher(True)]
        with patch.object(binding, 'fit', side_effect=AssertionError('unexpected fallback')):
            material = family.配置展開教材(teachers)
        self.assertEqual(vars(material), {'適合': True})
        self.assertEqual(material.記録(), {'全教師共通配置積': True})
        for teacher in teachers:
            self.assertEqual(material.候補(teacher['input'], None), family.guarded_render(teacher['input']))



    def test_complete_necessary_parse_proof(self):
        teachers = [{'input': CONTROL[name], 'output': CONTROL['expected']} for name in ('thin', 'thick')]
        with patch.object(view.strict, 'fit', side_effect=AssertionError('symbolically excluded fit')):
            models, record = binding.fit(teachers)
        self.assertEqual(models, ())
        self.assertEqual(record['proof_parse_calls'], 2)
        self.assertEqual(record['rejected_teacher_indices'], [0, 1])
        self.assertEqual(record['evaluated_teacher_calls'], 0)
        self.assertEqual(record['symbolic_unexecuted_teacher_calls'], 4096)
        self.assertEqual([w['teacher_index'] for w in record['teacher_parse_witnesses']], [0, 1])



    def test_frozen_code_and_api(self):
        self.assertIs(view.fit, view.strict.fit)
        self.assertIs(view.act, view.strict.act)
        self.assertIs(view.MODELS, view.strict.MODELS)
        self.assertIs(view.relational_parse.__code__, view.frozen.relational_parse.__code__)
        self.assertIs(view._scaffold_render.__code__, view.frozen.render.__code__)
        self.assertIs(view.consensus.__code__, view.frozen.consensus.__code__)


if __name__ == '__main__':
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
    summary = {'evidence_kind': 'NEW ordinary113 check; missing historical tiny-controls not reconstructed', 'tests_run': result.testsRun, 'successful': result.wasSuccessful()}
    if not result.wasSuccessful():
        summary['details'] = stream.getvalue()
    print(json.dumps(summary, ensure_ascii=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)
