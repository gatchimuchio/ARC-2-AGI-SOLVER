# NEW current ordinary117: four recovered self-contained checks plus two current ordinary checks.
"""Bounded public regression for the same-family embedded local-action binding."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from 接続.ARC2 import 記号命令教材 as interpreter
from 接続.ARC2 import 厳密枠局所命令 as strict
from 接続.ARC2 import 周期補色局所命令 as core
from 接続.ARC2 import 枠局所命令接続 as binding

DATA = ROOT / '検証' / '枠局所命令資料'
TEACHERS = json.loads((DATA / 'teachers-only.json').read_text())['4c7dc4dd']['train']
FIXTURES = json.loads((DATA / 'new-current-phase-controls.json').read_text())


def plain(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


class Controls(unittest.TestCase):
    def test_supplied_teachers_exact_and_bound(self):
        self.assertEqual(core.fit(TEACHERS), strict.fit(TEACHERS))
        self.assertTrue(core.fit(TEACHERS)[0])
        models, record = interpreter.fit_models(TEACHERS)
        self.assertIsNone(models)
        self.assertEqual(record['failure'], 'teacher_input_contract')
        self.assertIs(record['complete'], True)
        self.assertEqual(len(record['teacher_parse_records']), len(TEACHERS))
        material = interpreter.記号命令教材(TEACHERS)
        self.assertEqual(material.モデル, ())
        self.assertEqual(material.枠局所命令, ('embedded_local_actions',))
        for pair in TEACHERS:
            self.assertEqual(material.候補(pair['input'], None), strict.render(pair['input']))
            self.assertEqual(material.候補(pair['input'], None)[0], pair['output'])






    def test_area_necessity_visits_all_teachers_without_new_parse(self):
        teachers = [{'input': [[0]], 'output': [[0]]},
                    {'input': [[1]], 'output': [[0, 1], [1, 0], [0, 1]]}]
        models, old_record = interpreter.fit_models(teachers)
        with patch.object(binding, 'fit_embedded', side_effect=AssertionError('new_parse_was_called')):
            state, record = binding.fit_after_complete_instruction_no_fit(teachers, models, old_record)
        self.assertIsNone(state)
        self.assertEqual(record['failure'], 'four_framed_panels_area_necessity')
        self.assertEqual(record['parsed_teacher_count'], 0)
        self.assertEqual(record['rendered_teacher_count'], 0)
        witnesses = record['teacher_area_witnesses']
        self.assertEqual(len(witnesses), len(teachers))
        self.assertEqual([w['four_framed_panels_area'] for w in witnesses], [36, 80])
        self.assertTrue(all(not w['necessary_area_holds'] for w in witnesses))

    def test_only_exact_completed_structural_no_fit_enables_binding(self):
        models, original = interpreter.fit_models(TEACHERS)
        negatives = [dict(original, failure='no_shared_program_model'),
                     dict(original, failure='unknown_failure'),
                     dict(original, failure='search_budget_incomplete', complete=False),
                     dict(original, complete=False),
                     dict(original, teacher_parse_records=original['teacher_parse_records'][:-1]),
                     dict(original, teacher_parse_records=[{'failure': 'runtime_error'}] * len(TEACHERS))]
        for old_record in negatives:
            state, record = binding.fit_after_complete_instruction_no_fit(TEACHERS, models, old_record)
            self.assertIsNone(state)
            self.assertEqual(record['failure'], 'old_completed_structural_no_fit_required')
        state, record = binding.fit_after_complete_instruction_no_fit(TEACHERS, (), original)
        self.assertIsNone(state)
        self.assertEqual(record['failure'], 'old_completed_structural_no_fit_required')

    def test_teacher_validation_precedes_area_inference(self):
        for teachers in ([TEACHERS[0]], [TEACHERS[0], TEACHERS[0]],
                         [TEACHERS[0], {'input': [[0], [0, 1]], 'output': [[0]]}]):
            self.assertFalse(core.fit(teachers)[0])
            old_record = {'failure': 'teacher_input_contract', 'complete': True,
                          'teacher_parse_records': [{'failure': 'separator_not_unique'} for _ in teachers]}
            with patch.object(binding, 'fit_embedded', side_effect=AssertionError('new_parse_was_called')):
                state, record = binding.fit_after_complete_instruction_no_fit(teachers, None, old_record)
            self.assertIsNone(state)
            self.assertIn(record['failure'], ('insufficient_teachers', 'duplicate_teachers', 'invalid_teachers'))
            self.assertNotIn('teacher_area_witnesses', record)


    def test_new_literal_periodic_action_checks(self):
        for case in FIXTURES['phase']:
            before = deepcopy(case['input'])
            output, record = core.periodic_action(case['input'], case['blank'],
                                                  case['group_color'], tuple(case['model']))
            self.assertEqual(output, case['output'], case['name'])
            self.assertEqual(case['input'], before)
            self.assertEqual(record['period'], 2)

    def test_new_existing_ordinary_positive_state_and_records(self):
        # Reuse only the existing independent synthetic fixture definitions.
        import ast
        source = (ROOT / '検証/記号命令回帰.py').read_text()
        tree = ast.parse(source)
        nodes = [node for node in tree.body
                 if isinstance(node, ast.FunctionDef) and node.name in ('direct_execution', 'case')]
        namespace = {'A': '010101010', 'B': '101010101', 'C': '110011100'}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), '<existing-ordinary-instruction-fixture>', 'exec'), namespace)
        teachers = [namespace['case'](start_column=column) for column in (2, 3)]
        models, record = interpreter.fit_models(teachers)
        self.assertIs(record['complete'], True)
        self.assertEqual(len(models), 8)
        with patch.object(binding, 'fit_after_complete_instruction_no_fit',
                          side_effect=AssertionError('old positive must not enter fallback')):
            material = interpreter.記号命令教材(teachers)
        self.assertEqual(vars(material), {'モデル': tuple(models)})
        self.assertEqual(material.記録(), {'完走適合model数': len(models),
                                         '読取順序': sorted({m[0] for m in models})})
        for pair in teachers:
            self.assertEqual(material.候補(pair['input'], None),
                             interpreter.consensus(pair['input'], tuple(models)))
            self.assertEqual(material.候補(pair['input'], None)[0], pair['output'])


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
    print(json.dumps({'evidence_kind': 'NEW current117 ordinary check; historical synthetic expectations unavailable', 'tests_run': int(result.testsRun), 'successful': result.wasSuccessful()}, ensure_ascii=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)
