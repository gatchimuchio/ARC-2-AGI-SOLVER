"""Pure DTO/config controls: no public files, constructors or HDS calls."""
from copy import deepcopy
import unittest

import prune_fit_diagnosis as study


class Controls(unittest.TestCase):
    def test_fixed_ablation_changes_only_the_separate_local_field(self):
        self.assertEqual(study.FIT_BOUNDS, {**study.DEFAULT_BOUNDS, "minimum_leaf_teacher_support": 1})
        self.assertEqual(study.EXPECTED_MODULE_DEFAULT_BOUNDS, {**study.DEFAULT_BOUNDS, "minimum_leaf_teacher_support": 2})
        self.assertEqual(study.FIT_BOUNDS["minimum_teacher_support"], 2)
        self.assertEqual(study.FIT_BOUNDS["minimum_cell_support"], 2)
        self.assertEqual(study.FIT_BOUNDS["max_fit_states"], 256)
        self.assertEqual(study.FIT_BOUNDS["max_work_units"], 2_000_000)

    def test_only_support_bounds_and_exact_frozen_config_are_accepted(self):
        payload = {"support": [{"input": [[i, 0]], "output": [[i, 0]]} for i in range(3)],
                   "bounds": dict(study.FIT_BOUNDS)}
        study.validate_payload(payload, "pruned_fit")
        for key, value in (("minimum_teacher_support", 1), ("minimum_cell_support", 1),
                           ("minimum_leaf_teacher_support", 2), ("max_fit_states", 512)):
            invalid = deepcopy(payload)
            invalid["bounds"][key] = value
            with self.assertRaises(ValueError):
                study.validate_payload(invalid, "pruned_fit")
        invalid = {**payload, "test": [{"input": [[9]]}]}
        with self.assertRaises(ValueError):
            study.validate_payload(invalid, "pruned_fit")

    def test_unseen_excluded_and_feedback_only_after_as_ordinary_teacher(self):
        pairs = [{"input": [[i, 0]], "output": [[i, 1]]} for i in range(5)]
        row = {"task_id": "parent_only", "support_indices": [0, 1, 2], "feedback_index": 3, "unseen_index": 4}
        for phase, expected in (("before", [0, 1, 2]), ("after", [0, 1, 2, 3])):
            payload = study.make_payload({"parent_only": {"train": pairs}}, row, phase, study.FIT_BOUNDS)
            study.validate_payload(payload, "pruned_fit")
            self.assertEqual(set(payload), {"support", "bounds"})
            self.assertEqual(payload["support"], [pairs[index] for index in expected])
            self.assertNotIn(pairs[4], payload["support"])


if __name__ == "__main__":
    unittest.main()
