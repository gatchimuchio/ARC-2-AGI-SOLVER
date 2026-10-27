"""Pure dataflow/scoring tests; no candidate fit, HDS execution or solver job."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("feature_public_harness_pure", HERE / "public_harness.py")
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


def dataset():
    return {f"task{index}": {"train": [{"input": [[color, color + 1]], "output": [[color + 2]]}
                                      for color in range(6)]} for index in range(30)}


class PublicHarnessTests(unittest.TestCase):
    def test_cohort_is_input_only_deterministic_and_above_both_support_floors(self):
        data = dataset()
        first = harness.freeze_cohort(data, 20, 20261026)
        self.assertEqual(first, harness.freeze_cohort(data, 20, 20261026))
        changed = deepcopy(data)
        for task in changed.values():
            for pair in task["train"]:
                pair["output"] = [[9, 8, 7]]
        self.assertEqual(first, harness.freeze_cohort(changed, 20, 20261026))
        self.assertEqual(len({row["task_id"] for row in first["rows"]}), 20)
        for row in first["rows"]:
            self.assertGreaterEqual(row["before_support"], 4)
            self.assertEqual(row["after_support"], row["before_support"] + 1)
            self.assertNotIn(row["unseen_index"], row["support_indices"])
            self.assertNotIn(row["feedback_index"], row["support_indices"])
        self.assertEqual(first["rows"][0]["arm_order"], list(harness.ARMS))
        self.assertEqual(first["rows"][1]["arm_order"], list(reversed(harness.ARMS)))

    def test_u_target_is_absent_both_phases_feedback_target_enters_only_after(self):
        data = dataset()
        row = harness.freeze_cohort(data, 1, 7)["rows"][0]
        before = harness.make_payload(data, row, "feature_predicate", "before", "hash")
        after = harness.make_payload(data, row, "feature_predicate", "after", "hash")
        harness.validate_payload(before)
        harness.validate_payload(after)
        self.assertEqual(before["queries"], after["queries"])
        self.assertEqual(before["support"], after["support"][:-1])
        self.assertEqual(after["support"][-1], data[row["task_id"]]["train"][row["feedback_index"]])
        changed = deepcopy(data)
        changed[row["task_id"]]["train"][row["unseen_index"]]["output"] = [[9, 9]]
        for phase, expected in (("before", before), ("after", after)):
            self.assertEqual(expected, harness.make_payload(changed, row, "feature_predicate", phase, "hash"))
        changed[row["task_id"]]["train"][row["feedback_index"]]["output"] = [[8, 8]]
        self.assertEqual(before, harness.make_payload(changed, row, "feature_predicate", "before", "hash"))
        self.assertNotEqual(after, harness.make_payload(changed, row, "feature_predicate", "after", "hash"))

    def test_runtime_rejects_query_labels_ids_and_support_below_floor(self):
        data = dataset()
        row = harness.freeze_cohort(data, 1, 7)["rows"][0]
        payload = harness.make_payload(data, row, "feature_neighbor", "before", "hash")
        for change in (lambda p: p.update(task_id="forbidden"),
                       lambda p: p["queries"][1].update(output=[[9]]),
                       lambda p: p["queries"][1].update(task_id="forbidden"),
                       lambda p: p.update(support=p["support"][:3])):
            altered = deepcopy(payload)
            change(altered)
            with self.assertRaises(ValueError):
                harness.validate_payload(altered)

    def test_timeout_failure_keeps_requested_denominator_without_copy_predictions(self):
        with patch.object(harness.subprocess, "run", side_effect=subprocess.TimeoutExpired("synthetic", 1)):
            response = harness.invoke({}, 1)
        self.assertEqual(response["state"], "timeout")
        scores, safe = harness.score_result(response, [[[0]], [[1]]])
        self.assertEqual(len(scores), 2)
        self.assertTrue(all(not row["complete"] and not row["direct_exact"] and not row["hds_exact"] for row in scores))
        self.assertTrue(all(row["direct_abstain_or_failure"] for row in scores))
        self.assertNotIn("rows", safe)

    def test_actual_identity_candidate_counts_and_predictions_are_stripped_from_evidence(self):
        response = {"state": "complete", "rows": [{"direct": [[0]], "hds": None, "hds_status": "hold"},
                                                  {"direct": [[1]], "hds": [[1]], "hds_status": "output"}]}
        scores, safe = harness.score_result(response, [[[0]], [[1]]])
        self.assertTrue(scores[0]["direct_exact"])
        self.assertFalse(scores[0]["hds_exact"])
        self.assertTrue(scores[1]["direct_exact"] and scores[1]["hds_exact"])
        self.assertNotIn("direct", safe["rows"][0])
        self.assertNotIn("hds", safe["rows"][1])
        self.assertFalse(harness.contains_grid(safe))
        self.assertIn("direct", response["rows"][0])

    def test_bad_worker_shapes_are_failures(self):
        for value in ([], {"state": "complete", "rows": []}, {"state": "complete", "rows": [None, None]}):
            result = subprocess.CompletedProcess("synthetic", 0, stdout=__import__("json").dumps(value), stderr="")
            with patch.object(harness.subprocess, "run", return_value=result):
                response = harness.invoke({}, 1)
            self.assertNotEqual(response["state"], "complete")
            self.assertEqual(len(harness.score_result(response, [[[0]], [[1]]])[0]), 2)

    def test_diagnostics_drop_grids_and_numeric_typed_state_is_not_output_memory(self):
        safe = harness.count_diagnostics({"reason": "hold", "count": 3, "output": [[9]],
                                          "raw": {"input": [[8]], "output": [[7]]}})
        self.assertEqual(safe, {"reason": "hold", "count": 3})
        self.assertFalse(harness.contains_grid({"predicate": {"feature": 2, "lower": 0.1, "upper": 0.2},
                                               "palette": {"1": 2, "2": 3}, "support": [2, 2]}))
        self.assertTrue(harness.contains_grid({"accidental_raw_target": [[1, 2], [3, 4]]}))

    def test_ineligible_counts_duplicate_inputs_and_max_support_are_excluded(self):
        data = dataset()
        data["floor5"] = {"train": deepcopy(data["task0"]["train"][:5])}
        data["too_many10"] = {"train": deepcopy(data["task0"]["train"]) +
                                            [{"input": [[i]], "output": [[i]]} for i in range(6, 10)]}
        data["duplicate"] = deepcopy(data["task0"])
        data["duplicate"]["train"][1]["input"] = deepcopy(data["duplicate"]["train"][0]["input"])
        cohort = harness.freeze_cohort(data, 30, 5)
        self.assertEqual(cohort["eligible_task_count"], 30)
        self.assertNotIn("floor5", [row["task_id"] for row in cohort["rows"]])

    def test_aggregate_preserves_failure_denominators_and_separates_real_hds_scores(self):
        results = {arm: {} for arm in harness.ARMS}
        for arm in harness.ARMS:
            for phase in harness.PHASES:
                success = arm == "feature_predicate" and phase == "after"
                raw = {"state": "complete", "rows": [{"direct": [[0]], "hds": None},
                                                         {"direct": [[1]] if success else None,
                                                          "hds": [[1]] if success else None}],
                       "model_fitted": {"sha256": phase},
                       "hds_admitted": {"semantic_rule_sha256": phase},
                       "model_unchanged_after_query": True,
                       "hds_semantics_unchanged_after_query": True}
                if arm == "feature_neighbor" and phase == "before":
                    raw = {"state": "timeout"}
                scores, safe = harness.score_result(raw, [[[0]], [[1]]])
                results[arm][phase] = {"scores": scores, "evidence": safe}
        summary = harness.summarize([{"results": results}], 1)
        self.assertEqual(summary["feature_neighbor"]["unseen"]["before"]["requested"], 1)
        self.assertEqual(summary["feature_neighbor"]["unseen"]["before"]["complete"], 0)
        self.assertEqual(summary["feature_predicate"]["unseen"]["hds_gains"], 1)
        comparison = summary["candidate_vs_old_selector_unseen"]["after_hds"]
        for key in ("current", "delta", "gains", "requested", "new_correct_old_wrong", "hypothetical_two_candidate_union_exact"):
            self.assertEqual(comparison[key], 1)
        for key in ("previous", "regressions"):
            self.assertEqual(comparison[key], 0)
        self.assertEqual(summary["feature_predicate"]["feedback"]["before"]["direct_exact"], 1)
        self.assertEqual(summary["feature_predicate"]["feedback"]["before"]["hds_exact"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
