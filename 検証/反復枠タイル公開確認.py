"""Portable public-family checks using only existing teachers and contrasts.

Run: python 反復枠タイル公開確認.py --root CHECKOUT [--overlay PAYLOAD]
No HDS/native/full run, original query, or new fixture is included.
"""
import argparse
import ast
import importlib.util
import json
from pathlib import Path
import sys
import unittest

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument('--overlay', type=Path)
args, remaining = parser.parse_known_args()
root = args.root.resolve()
overlay = args.overlay.resolve() if args.overlay else root
sys.path[:0] = [str(overlay), str(root)]
from 接続.ARC2 import 正方形格子教材 as public
from 接続.ARC2 import 正方形格子反復枠接続 as adapter
from 接続.ARC2 import 反復枠タイル本体 as core
from 接続.ARC2.反復枠共通部品 import transform_grid_by_name

fixtures = Path(__file__).resolve().parent / '反復枠タイル資料'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load('接続.ARC2._反復枠旧正方形', fixtures / '正方形格子旧実装.py')
f = load('_反復枠既存対照', fixtures / '既存対照.py')
teachers = json.loads((fixtures / 'teachers-only.json').read_text())['train']


class PublicTileBodyChecks(unittest.TestCase):
    def test_old_functions_and_positive_delegation(self):
        sources = [(fixtures / '正方形格子旧実装.py').read_text(),
                   (overlay / '接続/ARC2/正方形格子教材.py').read_text()]
        definitions = [{node.name: ast.get_source_segment(source, node)
                        for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)}
                       for source in sources]
        self.assertEqual(definitions[0], definitions[1])
        ordinary = [f.pair(i) for i in range(3)]
        symmetric = f.symmetric_pair()
        for group in [ordinary, [symmetric, {k: f.remap(v) for k, v in symmetric.items()}]]:
            self.assertEqual(public.fit_models(group), old.fit_models(group))
            before, after = old.正方形格子教材(group), public.正方形格子教材(group)
            self.assertTrue(before.モデル)
            self.assertEqual(before.__dict__, after.__dict__)
            self.assertEqual(before.記録(), after.記録())
            for pair in group:
                self.assertEqual(before.候補(pair['input'], None), after.候補(pair['input'], None))
                self.assertEqual(after.候補(pair['input'], None)[0], pair['output'])
        scaled = f.pair(a=2, b=3, pitch=5)
        self.assertEqual(public.render_model(scaled['input'], 'rot0'), old.render_model(scaled['input'], 'rot0'))

    def test_complete_gate_and_public_teacher_predictions(self):
        models, record = public.fit_models(teachers)
        self.assertIsNone(models)
        self.assertTrue(adapter.complete_square_structural_no_fit(teachers, models, record, public.MODELS))
        self.assertEqual(sum(len(rows) for rows in record['teacher_records'].values()), 24)
        view = public.正方形格子教材(teachers)
        self.assertIsNone(view.モデル)
        self.assertEqual(len(view.反復枠モデル['programs']), 6)
        self.assertEqual(len(view.記録()['反復枠タイル共通モデル']), 6)
        for pair in teachers:
            output, result = view.候補(pair['input'], None)
            self.assertEqual(output, pair['output'])
            self.assertEqual(result['evaluated_program_count'], 6)
            self.assertEqual(result['evaluated_program_role_count'], 6)
            self.assertEqual(result['distinct_output_count'], 1)
            self.assertTrue(all(row['output'] == pair['output'] for row in result['results']))
        duplicate = [teachers[0], teachers[0]]
        self.assertFalse(public.正方形格子教材(duplicate).モデル)
        self.assertIsNone(public.正方形格子教材(duplicate).反復枠モデル)

    def test_existing_ordinary_contrasts_through_public_family(self):
        view = public.正方形格子教材(teachers)
        changed = f.orbit_change(teachers[0]['input'], (7, 7), (4, 4), 4)
        dense = f.dense_ornament()
        expected_dense = f.source_oracle(dense, (8, 8), 1)
        cases = [(changed, f.source_oracle(changed, (7, 7), 6)),
                 (dense, expected_dense),
                 (transform_grid_by_name(dense, 'rot90'), transform_grid_by_name(expected_dense, 'rot90')),
                 ([[9-v for v in row] for row in dense], [[9-v for v in row] for row in expected_dense]),
                 (f.pad(dense), f.pad(expected_dense))]
        for grid, expected in cases:
            output, record = view.候補(grid, None)
            self.assertEqual(output, expected)
            self.assertEqual(record['full_output_count'], 6)
        no_span = f.orbit_change(teachers[0]['input'], (7, 7), (4, 0), 4)
        output, record = view.候補(no_span, None)
        self.assertIsNone(output)
        self.assertEqual(record['parse']['failure'], 'no_shared_tile_spanning_role')

    def test_original_programs_remain_separate(self):
        self.assertEqual(len(core.legacy.PROGRAMS), 12)
        self.assertEqual(len(core.PROGRAMS), 6)
        for pair in teachers:
            record = core.enumerate_original_outputs(pair['input'])
            self.assertEqual(len(record['results']), 12)
            self.assertTrue(all(row['output'] == pair['output'] for row in record['results']))
        dense = f.dense_ornament()
        original = core.enumerate_original_outputs(dense)
        state, _ = core.fit(teachers)
        output, _ = core.predict(dense, state)
        self.assertEqual(output[8][8], 1)
        self.assertTrue(all(row['output'][8][8] == 4 for row in original['results']))

    def test_existing_fitted_state_checks(self):
        state, _ = core.fit(teachers)
        for pair in teachers:
            output, record = core.predict(pair['input'], json.loads(json.dumps(state)))
            self.assertEqual(output, pair['output'])
            self.assertEqual(record['full_output_count'], 6)
        for empty in [None, {}, {'programs': []}]:
            output, record = core.predict(teachers[0]['input'], empty)
            self.assertIsNone(output)
            self.assertEqual(record['failure'], 'empty_or_no_fit_state')
        output, record = core.predict(teachers[0]['input'], {'programs': [state['programs'][0]]})
        self.assertEqual(output, teachers[0]['output'])
        self.assertEqual(record['evaluated_program_count'], 1)
        self.assertEqual(len(record['results']), 1)


if __name__ == '__main__':
    run = unittest.main(argv=[sys.argv[0]] + remaining, exit=False)
    print(json.dumps({'tests_run': run.result.testsRun, 'successful': run.result.wasSuccessful()}))
    sys.exit(0 if run.result.wasSuccessful() else 1)
