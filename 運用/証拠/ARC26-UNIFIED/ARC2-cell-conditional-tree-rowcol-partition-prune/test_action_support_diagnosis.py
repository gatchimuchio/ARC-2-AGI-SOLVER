"""Synthetic support-only controls; no fit, public data or heldout queries."""
from copy import deepcopy
from dataclasses import asdict
import sys
import unittest

import action_support_diagnosis as study


base = study.load_base()
sys.path.insert(0, str(study.ROOT))
module = base.load_source(base.MODULE, "action_support_synthetic_fixed_module")


def pair(grid, target):
    return {"input": deepcopy(grid), "output": deepcopy(target)}


def condition(pairs, **overrides):
    return study.action_support_condition(module, pairs, module.Bounds(**overrides))


class Controls(unittest.TestCase):
    def test_root_raw_support_can_pass_but_all_actions_for_cell_lack_teacher_support(self):
        result = condition([pair([[0, 1]], [[6, 6]]), pair([[0, 2]], [[7, 7]])])
        self.assertEqual(result["distinct_input_teachers"], 2)
        self.assertEqual(result["physical_cell_count"], 4)
        self.assertTrue(result["grammar_impossible_at_any_depth"])
        self.assertEqual(result["cells_without_any_support_eligible_matching_action"], 4)
        self.assertEqual(result["supported_allowed_action_count_histogram"], {"0": 4})

    def test_copy_role_has_support_across_different_actual_colors(self):
        result = condition([pair([[0, 1]], [[0, 1]]), pair([[2, 3]], [[2, 3]])])
        self.assertFalse(result["grammar_impossible_at_any_depth"])
        center = next(row for row in result["action_supports"] if row["program"] == "center")
        self.assertEqual(center["matching_cell_count"], 4)
        self.assertEqual(center["matching_distinct_teacher_count"], 2)

    def test_dynamic_rarest_role_uses_each_own_input_not_equal_absolute_targets(self):
        result = condition([pair([[0, 0, 7]], [[7, 7, 7]]), pair([[0, 0, 8]], [[8, 8, 8]])])
        self.assertFalse(result["grammar_impossible_at_any_depth"])
        rare = next(row for row in result["action_supports"] if row["program"] == "unique_rarest")
        self.assertEqual(rare["matching_cell_count"], 6)
        self.assertEqual(rare["matching_distinct_teacher_count"], 2)
        constants = [row for row in result["action_supports"] if row["program"] in ("constant:7", "constant:8")]
        self.assertTrue(all(row["matching_distinct_teacher_count"] == 1 for row in constants))

    def test_duplicate_inputs_do_not_inflate_teacher_or_cell_support(self):
        p = pair([[0, 1]], [[6, 6]])
        result = condition([p, deepcopy(p)])
        self.assertEqual(result["raw_teacher_count"], 2)
        self.assertEqual(result["distinct_input_teachers"], 1)
        self.assertEqual(result["physical_cell_count"], 2)
        self.assertTrue(result["grammar_impossible_at_any_depth"])
        q = deepcopy(p)
        q["output"] = [[7, 7]]
        with self.assertRaises(ValueError):
            condition([p, q])

    def test_physical_cell_floor_is_separate_from_teacher_floor(self):
        pairs = [pair([[0, 1]], [[6, 1]]), pair([[0, 2]], [[6, 2]])]
        ordinary, stricter = condition(pairs), condition(pairs, minimum_cell_support=3)
        self.assertFalse(ordinary["grammar_impossible_at_any_depth"])
        self.assertTrue(stricter["grammar_impossible_at_any_depth"])
        constant = next(row for row in stricter["action_supports"] if row["program"] == "constant:6")
        self.assertEqual(constant["matching_distinct_teacher_count"], 2)
        self.assertEqual(constant["matching_cell_count"], 2)
        self.assertFalse(constant["globally_support_eligible"])

    def test_all_actions_before_mdl_and_undefined_roles_not_counted(self):
        result = condition([pair([[0, 1]], [[0, 1]]), pair([[0, 2]], [[0, 2]])])
        actions = {row["program"]: row for row in result["action_supports"]}
        self.assertEqual(len(actions), 21)
        self.assertTrue(actions["constant:0"]["globally_support_eligible"])
        self.assertEqual(actions["background"]["matching_cell_count"], 0)
        self.assertEqual(actions["unique_rarest"]["matching_cell_count"], 0)

    def test_no_constructor_hds_or_query_is_needed_and_support_is_immutable(self):
        original = module.CellConditionalTree
        def forbidden(*_args, **_kwargs):
            raise AssertionError("not support-only")
        module.CellConditionalTree = forbidden
        try:
            support = [pair([[0, 1]], [[0, 1]]), pair([[0, 2]], [[0, 2]])]
            before = deepcopy(support)
            result = condition(support)
            self.assertEqual(support, before)
            self.assertFalse(result["grammar_impossible_at_any_depth"])
        finally:
            module.CellConditionalTree = original

    def test_existing_dto_excludes_u_and_after_feedback_is_only_training(self):
        train = [pair([[index, 0]], [[index, 0]]) for index in range(5)]
        row = {"task_id": "parent_only", "support_indices": [0, 1, 2], "feedback_index": 3, "unseen_index": 4}
        for phase, expected in [("before", [0, 1, 2]), ("after", [0, 1, 2, 3])]:
            payload = base.make_payload({"parent_only": {"train": train}}, row, phase, base.DEFAULT_BOUNDS)
            base.validate_payload(payload, "necessary_condition")
            self.assertEqual(set(payload), {"support", "bounds"})
            self.assertEqual(payload["support"], [train[index] for index in expected])
            self.assertNotIn(train[4], payload["support"])
        self.assertEqual(asdict(module.Bounds()), base.DEFAULT_BOUNDS)


if __name__ == "__main__":
    unittest.main()
