"""Targeted pure tests: actual formatter only; no solver/model/HDS execution."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("full_worker_adaptive_pure", HERE / "public_harness.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def training_data():
    return {f"task{index}": {"train": [{"input": [[color, color + 1]], "output": [[color + 2]]}
                                       for color in range(4)]} for index in range(30)}


class ActualWorkerHarnessTests(unittest.TestCase):
    def setUp(self):
        self.data = training_data()
        self.row = h.freeze_cohort(self.data, 1, 20261027)["rows"][0]
        self.payload = h.make_payload(self.data, self.row, "before", [], "source")
        self.task = self.payload["task"]
        self.formatter = h.pure_formatter()

    def actual_result(self, raw):
        predictions, audit = self.formatter("analysis", self.task, raw)
        return {"state": "complete", "predictions": predictions, "hold_audit": audit}

    def test_policy_pins_adaptive_source_and_absent_generic_path(self):
        audit = h.policy_audit()
        self.assertEqual(audit["adaptive_support"]["expected_outer_and_validator"], [2, 3])
        self.assertFalse(audit["adaptive_support"]["forced_or_mutated"])
        self.assertEqual(audit["generic_prior"]["status"], "ABSENT_CALL_PATH_PINNED_CURRENT_SOURCE")
        self.assertTrue(audit["generic_prior"]["not_v61_needed_extra_arithmetic"])

    def test_target_blind_exact4_cohort_and_reproducibility(self):
        first = h.freeze_cohort(self.data, 20, 20261027)
        changed = deepcopy(self.data)
        for task in changed.values():
            for pair in task["train"]:
                pair["output"] = [[9, 8, 7]]
        self.assertEqual(first, h.freeze_cohort(changed, 20, 20261027))
        self.assertEqual(first, h.freeze_cohort(self.data, 20, 20261027))
        self.assertEqual(len({row["task_id"] for row in first["rows"]}), 20)

    def test_reference_cohort_uses_exact_same_task_U_F_and_support(self):
        reference = json.loads(h.REFERENCE_COHORT.read_text(encoding="utf-8"))
        candidate = {"rows": deepcopy(reference["rows"]), "seed": reference["seed"],
                     "training_file_sha256": reference["training_file_sha256"]}
        self.assertTrue(h.verify_reference(candidate)["same_task_U_F_support_identity"])
        candidate["rows"][0]["unseen_index"] += 1
        with self.assertRaises(ValueError):
            h.verify_reference(candidate)

    def test_U_target_never_sent_and_F_target_enters_only_after(self):
        before = h.make_payload(self.data, self.row, "before", [], "source")
        after = h.make_payload(self.data, self.row, "after", [], "source")
        h.validate_payload(before)
        h.validate_payload(after)
        self.assertEqual(before["task"]["test"], after["task"]["test"])
        self.assertEqual(before["task"]["train"], after["task"]["train"][:-1])
        self.assertEqual(len(before["task"]["train"]), 2)
        self.assertEqual(len(after["task"]["train"]), 3)
        changed = deepcopy(self.data)
        changed[self.row["task_id"]]["train"][self.row["unseen_index"]]["output"] = [[9]]
        for phase, expected in (("before", before), ("after", after)):
            self.assertEqual(expected, h.make_payload(changed, self.row, phase, [], "source"))
        changed[self.row["task_id"]]["train"][self.row["feedback_index"]]["output"] = [[8]]
        self.assertEqual(before, h.make_payload(changed, self.row, "before", [], "source"))
        self.assertNotEqual(after, h.make_payload(changed, self.row, "after", [], "source"))

    def test_worker_rejects_identifiers_query_targets_nonempty_generic_and_prior_collision(self):
        for alter in (lambda p: p.update(task_id="forbidden"),
                      lambda p: p["task"]["test"][0].update(output=[[9]]),
                      lambda p: p["generic_prior"]["examples"].append({"input": [[1]], "output": [[2]]}),
                      lambda p: p["prior"].append({"input": deepcopy(p["task"]["test"][1]["input"]), "output": [[9]]})):
            payload = deepcopy(self.payload)
            alter(payload)
            with self.assertRaises((ValueError, h.DataBoundaryViolation)):
                h.validate_payload(payload)

    def test_template_filter_uses_all_four_inputs_without_targets(self):
        pairs = self.data[self.row["task_id"]]["train"]
        sources = [{"source_task_id": self.row["task_id"], "pair": {"input": [[8]], "output": [[7]]}},
                   {"source_task_id": "other", "pair": deepcopy(pairs[self.row["unseen_index"]])},
                   {"source_task_id": "other", "pair": deepcopy(pairs[self.row["support_indices"][0]])},
                   {"source_task_id": "safe", "pair": {"input": [[9]], "output": [[8]]}}]
        prior, audit = h.filtered_prior(sources, self.row["task_id"], [pair["input"] for pair in pairs])
        self.assertEqual(prior, [{"input": [[9]], "output": [[8]]}])
        self.assertEqual(audit["same_source_task_removed"], 1)
        self.assertEqual(audit["all_four_input_collisions_removed"], 2)

    def test_primary_HOLD_can_have_valid_generated_attempt2(self):
        query = self.task["test"][0]["input"]
        predictions, audit = self.formatter("analysis", self.task, {"results": [
            {"answer": None, "second_answer": [[7]], "status": "断定保留"}, {"answer": None}]})
        score = h.score_attempts(predictions[0], [[7]], query, audit[0])
        self.assertFalse(score["nonfallback_pass1"])
        self.assertTrue(score["nonfallback_pass2"] and score["second_incremental_exact"])
        self.assertTrue(score["attempt1_input_copy_fallback"])
        self.assertFalse(score["attempt2_input_copy_fallback"])

    def test_valid_identity_or_promoted_pair_is_not_blanket_excluded(self):
        query = self.task["test"][0]["input"]
        result = self.actual_result({"results": [{"answer": query, "second_answer": [[9]]}, {"answer": [[8]]}]})
        self.assertEqual(result["hold_audit"], [])
        result["raw_hds_rows"] = [{"primary_is_none": True, "candidate_pair_valid": True}]
        scored = h.score_and_strip(result, [query, [[8]]], [pair["input"] for pair in self.task["test"]])
        self.assertTrue(scored["scores"][0]["nonfallback_pass1"])
        self.assertFalse(scored["scores"][0]["attempt1_input_copy_fallback"])

    def test_timeout_normalized_actual_formatter_keeps_all_requested_rows(self):
        with patch.object(h.subprocess, "run", side_effect=subprocess.TimeoutExpired("synthetic", 1)):
            response = h.invoke(self.payload, 1)
        self.assertEqual(response["state"], "timeout")
        self.assertEqual(len(response["predictions"]), 2)
        self.assertEqual(len(response["hold_audit"]), 2)
        query = self.task["test"][0]["input"]
        score = h.score_attempts(response["predictions"][0], query, query, response["hold_audit"][0])
        self.assertTrue(score["raw_pass2"])
        self.assertFalse(score["nonfallback_pass2"] or score["generated_attempt_available"])

    def test_malformed_pairs_audits_and_noncomplete_responses_are_normalized(self):
        valid = self.actual_result({"results": [{"answer": [[7]]}, {"answer": [[8]]}]})
        cases = [[], {"state": "complete", "predictions": [{}, {}], "hold_audit": []},
                 {**valid, "hold_audit": None}, {**valid, "state": "solver_error"},
                 {**valid, "hold_audit": [{"test_index": 0, "reason": "hold"}] * 2}]
        for value in cases:
            with self.subTest(value=value):
                completed = subprocess.CompletedProcess("synthetic", 0, json.dumps(value), "")
                with patch.object(h.subprocess, "run", return_value=completed):
                    response = h.invoke(self.payload, 1)
                self.assertNotEqual(response["state"], "complete")
                self.assertEqual(len(response["predictions"]), 2)
                for index, pair in enumerate(response["predictions"]):
                    query = self.task["test"][index]["input"]
                    self.assertEqual(pair, {"attempt_1": query, "attempt_2": query})

    def test_caught_inner_JSON_exception_cannot_silently_succeed(self):
        with patch.object(h, "BLOCKED_JSON", []):
            try:
                h.BLOCKED_JSON.append("入力/forbidden.json")
                raise RuntimeError("caught by an inner helper")
            except RuntimeError:
                pass
            with self.assertRaises(h.DataBoundaryViolation):
                h.ensure_no_blocked_json()
        value = {"state": "boundary_violation", "boundary_violation": True,
                 "blocked_json": ["入力/forbidden.json"]}
        completed = subprocess.CompletedProcess("synthetic", 0, json.dumps(value), "")
        with patch.object(h.subprocess, "run", return_value=completed):
            normalized = h.invoke(self.payload, 1)
        self.assertTrue(normalized["boundary_violation"])
        with self.assertRaises(h.DataBoundaryViolation):
            h.enforce_boundary(normalized)

    def test_before_correct_after_timeout_is_a_requested_regression(self):
        queries = [pair["input"] for pair in self.task["test"]]
        before_raw = self.actual_result({"results": [{"answer": [[7]]}, {"answer": [[8]]}]})
        after_raw = h.normalize_failure(self.task, "timeout", self.formatter)
        before = h.score_and_strip(before_raw, [[[7]], [[8]]], queries)
        after = h.score_and_strip(after_raw, [[[7]], [[8]]], queries)
        summary = h.summarize([{"before": before, "after": after}], 1)
        self.assertEqual(summary["paired_complete"], 0)
        self.assertEqual(summary["unseen"]["nonfallback_pass2_regressions"], 1)
        self.assertEqual(summary["unseen"]["after"]["requested"], 1)
        self.assertEqual(summary["unseen"]["after"]["error_or_timeout"], 1)

    def test_family_dual_gate_stages_and_grid_free_diagnostics(self):
        cases = [({"status": "充足する候補なし"}, "no_candidate"),
                 ({"status": "教師反例により不採用"}, "teacher_counterexample"),
                 ({"training_all_reproduced": True, "equality_admitted": False}, "full_train_fit_without_equality"),
                 ({"training_all_reproduced": True, "equality_admitted": True}, "full_accepted")]
        for item, expected in cases:
            self.assertEqual(h.family_stage(item), expected)
        safe = h.count_diagnostics({"count": 3, "nested_output": {"output": [[9]]},
                                   "repeated_panel_candidate_fit": {"status": "fit", "teacher_count": 2,
                                                                    "candidate_models": [[[8]]]}})
        self.assertFalse(h.contains_grid(safe))
        self.assertNotIn("candidate_models", safe["repeated_panel_candidate_fit"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
