"""Synthetic only: leaf2 equivalence, leaf1 risks, schema, real HDS3 plumbing."""
import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib
import importlib.util
from itertools import combinations, product
import json
from pathlib import Path
import sys
import time
import unittest


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
OLD = HERE.with_name("ARC2-cell-conditional-tree-rowcol-action-support-prune") / "cell_conditional_tree.py"
NEW = HERE / "cell_conditional_tree.py"
OLD_SHA256 = "405065a7d8260f6b618e3b7cb1a90103f3e610250438eb5db7abf9c3289d366c"
NEW_SHA256 = "66a5b525e42881ae35b2a125c7a8f85628a8cce9b95179fdd89c62b38b7e22d6"
HDS_SMOKE = {}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path, name, expected):
    if sha(path.read_bytes()) != expected:
        raise ValueError("test source pin changed")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


old = load(OLD, "leaf_ablation_old405", OLD_SHA256)
new = load(NEW, "leaf_ablation_new", NEW_SHA256)
AMPLE = {"max_fit_states": 4096, "max_work_units": 32_000_000, "max_alternatives": 128}


def pair(grid, target):
    return {"input": deepcopy(grid), "output": deepcopy(target)}


def positive_and_negatives():
    # Only teacher1 has the positive recolour branch; teachers2/3 are negatives.
    return [pair([[0, value, value], [0, 0, 0]], [[0, 6 if value == 1 else value, 6 if value == 1 else value], [0, 0, 0]])
            for value in (1, 2, 3)]


def leaves(forest):
    for tree in forest["choices"]:
        if tree["kind"] == "leaf":
            yield tree
        else:
            for branch in tree["branches"].values():
                yield from leaves(branch)


class Controls(unittest.TestCase):
    def test_global_and_local_contracts_are_separate_and_old_caps_grammar_hds_unchanged(self):
        self.assertEqual(asdict(new.Bounds()), {**asdict(old.Bounds()), "minimum_leaf_teacher_support": 2})
        self.assertNotEqual(new.SCHEMA, old.SCHEMA)
        self.assertEqual(new.HDS_BOUNDARY, old.HDS_BOUNDARY)
        self.assertEqual(new.FEATURES, old.FEATURES)
        self.assertEqual(new.PROGRAMS, old.PROGRAMS)
        for values in ({"minimum_teacher_support": 1}, {"minimum_cell_support": 1},
                       {"minimum_leaf_teacher_support": 0}, {"minimum_leaf_teacher_support": 3},
                       {"minimum_leaf_teacher_support": True}):
            with self.assertRaises(ValueError):
                new.Bounds(**values)

    def test_leaf2_96_ample_forests_and_all_small_queries_exactly_match405(self):
        grids = [[list(values)] for values in product((0, 1), repeat=2)]
        checked = 0
        for inputs in combinations(grids, 2):
            for targets in product(grids, repeat=2):
                teachers = [pair(i, o) for i, o in zip(inputs, targets, strict=True)]
                a = old.CellConditionalTree(teachers, bounds=old.Bounds(**AMPLE))
                b = new.CellConditionalTree(teachers, bounds=new.Bounds(**AMPLE))
                self.assertNotIn("budget_exceeded", a.status)
                self.assertNotIn("budget_exceeded", b.status)
                self.assertEqual(a.status, b.status)
                self.assertEqual(a.forest, b.forest)
                self.assertEqual((a.fit_states, a.work_units), (b.fit_states, b.work_units))
                for grid in grids:
                    self.assertEqual(a.候補(grid, {}), b.候補(grid, {}))
                checked += 1
        self.assertEqual(checked, 96)

    def test_all_equal_minimal_trees_and_disagreement_hold_remain_for_both_leaf_floors(self):
        teachers = []
        for grid in ([[1, 2, 3], [2, 3, 4], [3, 4, 5]], [[6, 7, 8], [7, 8, 9], [8, 9, 0]]):
            target = deepcopy(grid)
            for row in (1, 2):
                for column in (1, 2):
                    target[row][column] = grid[row - 1][column]
            teachers.append(pair(grid, target))
        grammar = tuple(new.FEATURES.index(name) for name in ("border_top", "border_left"))
        previous = old.CellConditionalTree(teachers, bounds=old.Bounds(**AMPLE), feature_indices=grammar)
        query = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        for floor in (1, 2):
            current = new.CellConditionalTree(teachers, bounds=new.Bounds(**AMPLE, minimum_leaf_teacher_support=floor), feature_indices=grammar)
            self.assertEqual(previous.forest, current.forest)
            self.assertGreaterEqual(len(current.forest["choices"]), 2)
            self.assertEqual(current.候補(query, {}), (None, {"reason": "ambiguous_minimal_trees"}))

    def test_one_positive_teacher_can_fit_but_has_a_meaningful_unseen_overfit_counterexample(self):
        teachers = positive_and_negatives()
        grammar = (new.FEATURES.index("context_4"),)
        baseline = old.CellConditionalTree(teachers, bounds=old.Bounds(**AMPLE), feature_indices=grammar)
        control = new.CellConditionalTree(teachers, bounds=new.Bounds(**AMPLE), feature_indices=grammar)
        expanded = new.CellConditionalTree(teachers, bounds=new.Bounds(**AMPLE, minimum_leaf_teacher_support=1), feature_indices=grammar)
        self.assertEqual(baseline.status, control.status)
        self.assertIsNone(control.forest)
        self.assertEqual(expanded.status, "fitted")
        self.assertEqual(expanded.training_replayed, 3)
        self.assertTrue(any(leaf["teacher_support"] == 1 for leaf in leaves(expanded.forest)))
        self.assertTrue(all(expanded.候補(p["input"], {})[0] == p["output"] for p in teachers))
        # Consistent alternate ground truth: recolour exactly the two adjacent
        # first-row marker1 cells, otherwise copy. This query has THREE marker1
        # cells; training cannot distinguish that rule from recolour-all-1.
        query = [[0, 1, 1], [0, 1, 0]]
        self.assertNotEqual(expanded.候補(query, {})[0], query)

    def test_global_two_distinct_teachers_and_cell_floor_are_not_relaxed(self):
        teacher = positive_and_negatives()[0]
        bounds = new.Bounds(minimum_leaf_teacher_support=1)
        self.assertEqual(new.CellConditionalTree([teacher], bounds=bounds).status, "insufficient_distinct_teachers")
        self.assertEqual(new.CellConditionalTree([teacher, deepcopy(teacher)], bounds=bounds).status, "insufficient_distinct_teachers")
        conflict = deepcopy(teacher)
        conflict["output"][0][1] = 7
        self.assertEqual(new.CellConditionalTree([teacher, conflict], bounds=bounds).status, "conflicting_duplicate_input")
        grammar = (new.FEATURES.index("context_4"),)
        too_few_cells = new.CellConditionalTree(positive_and_negatives(),
            bounds=new.Bounds(**AMPLE, minimum_leaf_teacher_support=1, minimum_cell_support=3), feature_indices=grammar)
        self.assertNotEqual(too_few_cells.status, "fitted")

    def test_same_typed_dynamic_role_does_not_require_same_absolute_colour(self):
        teachers = [pair([[0, 0, color], [0, 0, 0], [0, 0, 0]],
                         [[color, color, color], [0, 0, 0], [0, 0, 0]]) for color in (7, 8)]
        grammar = (new.FEATURES.index("border_top"),)
        a = old.CellConditionalTree(teachers, bounds=old.Bounds(**AMPLE), feature_indices=grammar)
        for floor in (1, 2):
            b = new.CellConditionalTree(teachers, bounds=new.Bounds(**AMPLE, minimum_leaf_teacher_support=floor), feature_indices=grammar)
            self.assertEqual(a.forest, b.forest)
            self.assertEqual(b.候補([[0, 0, 9], [0, 0, 0], [0, 0, 0]], {})[0], [[9, 9, 9], [0, 0, 0], [0, 0, 0]])

    def test_state_roundtrip_and_global_leaf_schema_rejections(self):
        grammar = (new.FEATURES.index("context_4"),)
        machine = new.CellConditionalTree(positive_and_negatives(),
            bounds=new.Bounds(**AMPLE, minimum_leaf_teacher_support=1), feature_indices=grammar)
        state = json.loads(json.dumps(machine.model_state()))
        restored = new.CellConditionalTree.from_state(state)
        self.assertEqual(restored.model_state(), state)
        query = [[0, 1, 1], [0, 1, 0]]
        self.assertEqual(restored.候補(query, {}), machine.候補(query, {}))
        with self.assertRaises(ValueError):
            old.CellConditionalTree.from_state(state)
        old_state = old.CellConditionalTree(positive_and_negatives()).model_state()
        with self.assertRaises(ValueError):
            new.CellConditionalTree.from_state(old_state)
        for mutate in (lambda s: s["bounds"].update(minimum_leaf_teacher_support=0),
                       lambda s: s["bounds"].update(minimum_leaf_teacher_support=3),
                       lambda s: s["bounds"].update(minimum_teacher_support=1),
                       lambda s: s.update(distinct_training_examples=1),
                       lambda s: next(leaves(s["forest"])).update(teacher_support=0),
                       lambda s: s["bounds"].update(minimum_leaf_teacher_support=2)):
            corrupt = deepcopy(state)
            mutate(corrupt)
            with self.assertRaises(ValueError):
                new.CellConditionalTree.from_state(corrupt)

    def test_real_hds_outer_and_validator_three_exact_replay_and_counterexamples_unchanged(self):
        teachers = positive_and_negatives()
        grammar = (new.FEATURES.index("context_4"),)
        model = new.CellConditionalTree(teachers, bounds=new.Bounds(minimum_leaf_teacher_support=1), feature_indices=grammar)
        connection = new._connection()
        self.assertEqual(sha(Path(connection.__file__).read_bytes()), "69ba1aa8f428a108624ae871672496f8b0bf2746b93f96f65d1a0f78d3c0d1fe")
        calls = {"template": 0, "generic": 0}
        saved = {}
        for name, key in (("事前教材を読む", "template"), ("汎用事前記憶を読む", "generic")):
            if hasattr(connection, name):
                saved[name] = getattr(connection, name)
                def forbidden(_key=key):
                    calls[_key] += 1
                    raise AssertionError("synthetic smoke must not read prior data")
                setattr(connection, name, forbidden)
        try:
            hds = new.new_hds_machine()
            self.assertEqual((hds.最小支持数, hds.検証器.最小支持数), (3, 3))
            record = model.admit_to_hds(hds, teachers)
            self.assertTrue(record["採用可"])
            self.assertTrue(record["同値採用"])
            self.assertEqual(record["現在観測数"], 3)
            query = [[0, 1, 1], [0, 1, 0]]
            result = model.query_via_hds(hds, query)
            self.assertTrue(result["hds_queried"])
            self.assertTrue(result["equality_admitted"])
            self.assertEqual(result["answer"], model.候補(query, {})[0])
            bad_teachers = deepcopy(teachers)
            bad_teachers[-1]["output"][0][1] = 9
            bad_hds = new.new_hds_machine()
            bad = model.admit_to_hds(bad_hds, bad_teachers)
            self.assertFalse(bad["採用可"])
            self.assertEqual(bad["状態"], "教師反例により不採用")
            self.assertEqual((bad_hds.最小支持数, bad_hds.検証器.最小支持数), (3, 3))
            self.assertEqual(calls, {"template": 0, "generic": 0})
            HDS_SMOKE.update(actual_outer_minimum=3, actual_inner_validator_minimum=3,
                generator_global_minimum=2, local_leaf_minimum=1, minimum_cells=2,
                whole_current_train_replayed=3, equality_admitted=True, hds_query_exercised=True,
                query_answer_sha256=sha(json.dumps(result["answer"]).encode()),
                counterexample_adoption=False, prior_reader_calls=calls,
                scope="synthetic whole-program HDS3 plumbing; one positive leaf teacher is not three leaf teachers")
        finally:
            for name, fn in saved.items():
                setattr(connection, name, fn)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.report and args.report.exists():
        raise FileExistsError("refuse to overwrite synthetic evidence")
    started = time.perf_counter()
    result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
    report = {"state": "PASS" if result.wasSuccessful() else "FAIL", "tests": result.testsRun,
              "seconds": round(time.perf_counter() - started, 6), "hds_smoke": HDS_SMOKE,
              "old_module_sha256": sha(OLD.read_bytes()), "module_sha256": sha(NEW.read_bytes()),
              "test_sha256": sha(Path(__file__).read_bytes()), "public_fit_or_query_executed": False,
              "performance_or_score_improvement_claimed": False}
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)
