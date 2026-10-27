import unittest
import sys

import colour_role_feasibility_probe as study
from colour_role_feasibility_probe import own_input_profiles, rank_profile, role_labels


class Controls(unittest.TestCase):
    def test_absent_target_has_no_frequency_role(self):
        profiles = own_input_profiles({0: 3, 1: 2, 2: 1}, 6)
        self.assertEqual(profiles["global"]["state"], "target_absent")
        self.assertEqual(profiles["nonbackground"]["state"], "target_absent")
        self.assertEqual(role_labels(profiles), ())

    def test_unique_global_and_nonbackground_rank(self):
        profiles = own_input_profiles({0: 3, 1: 2, 2: 1}, 1)
        self.assertEqual(profiles["global"]["state"], "unique")
        self.assertEqual(profiles["global"]["descending_dense_rank"], 2)
        self.assertEqual(profiles["nonbackground"]["descending_dense_rank"], 1)
        self.assertEqual(len(role_labels(profiles)), 4)

    def test_ties_are_explicit_and_never_unique_roles(self):
        profiles = own_input_profiles({0: 3, 1: 1, 2: 1, 3: 1}, 1)
        self.assertEqual(profiles["global"]["tie_size"], 3)
        self.assertEqual(profiles["global"]["descending_position_start"], 2)
        self.assertEqual(profiles["global"]["descending_position_end"], 4)
        self.assertEqual(profiles["nonbackground"]["state"], "tied")
        self.assertEqual(role_labels(profiles), ())

    def test_background_ambiguity_does_not_choose_numeric_colour(self):
        profiles = own_input_profiles({0: 2, 1: 2}, 1)
        self.assertEqual(profiles["nonbackground"]["state"], "background_not_unique")
        self.assertEqual(role_labels(profiles), ())

    def test_same_rank_role_does_not_require_same_absolute_colour(self):
        a = own_input_profiles({0: 3, 1: 2, 2: 1}, 1)
        b = own_input_profiles({4: 3, 7: 2, 8: 1}, 7)
        self.assertEqual(a, b)
        self.assertEqual(role_labels(a), role_labels(b))
        self.assertEqual(rank_profile({0: 3, 1: 2, 2: 1}, 2)["ascending_dense_rank"], 1)

    def test_distant_unique_middle_frequency_can_be_information_feasible_without_fit(self):
        parent = study.load_parent()
        sys.path.insert(0, str(parent.ROOT))
        base = parent.load_base()
        module = base.load_source(base.MODULE, "synthetic_colour_probe_module")
        support = []
        for common, rare, flip in [(1, 2, False), (3, 4, True)]:
            grid = [[0] * 5 for _ in range(5)]
            common_row, rare_row = (4, 0) if flip else (0, 4)
            for column in range(3):
                grid[common_row][column] = common
            for column in (3, 4):
                grid[rare_row][column] = rare
            support.append({"input": grid, "output": [[common] * 5 for _ in range(5)]})
        result = study.probe_callback(parent.action_support_condition)(module, support, module.Bounds())
        self.assertGreater(result["unsupported_cells"], 0)
        self.assertEqual(result["target_present_anywhere_in_own_input"], result["unsupported_cells"])
        self.assertEqual(result["unsupported_cells_with_globally_support_feasible_unique_frequency_role"], result["unsupported_cells"])
        self.assertTrue(result["role_binding_is_a_new_grammar_hypothesis_not_current_capability"])


if __name__ == "__main__":
    unittest.main()
