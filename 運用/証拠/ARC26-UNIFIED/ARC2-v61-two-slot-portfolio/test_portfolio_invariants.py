"""Pure protocol tests: no HDS import, model fit, solver worker or network call."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch


sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("portfolio_evaluation_pure", HERE / "evaluate.py")
evaluation = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(evaluation)


class PortfolioProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidate_dir = os.environ.get("PORTFOLIO_TEST_CANDIDATE_DIR")
        candidate_sha = os.environ.get("PORTFOLIO_TEST_CANDIDATE_SHA256")
        cls.payloads, cls.report = evaluation.preflight(Path(candidate_dir) if candidate_dir else None, candidate_sha)
        baseline, valid = evaluation.pure_formatter(cls.payloads["baseline"]["entries"][evaluation.WRAPPER].decode("utf-8"))
        candidate, _ = evaluation.pure_formatter(cls.payloads["candidate"]["entries"][evaluation.WRAPPER].decode("utf-8"))
        cls.baseline, cls.candidate, cls.valid = staticmethod(baseline), staticmethod(candidate), staticmethod(valid)
        # Compile helper AST from the exact built payload, never a mutable overlay
        # file and never the wrapper's top-level imports or solver worker.
        tree = ast.parse(cls.payloads["candidate"]["entries"][evaluation.WRAPPER].decode("utf-8"))
        nodes = [node for node in tree.body if
                 isinstance(node, ast.FunctionDef) and node.name.startswith("_portfolio_")
                 or isinstance(node, ast.ClassDef) and node.name == "_PortfolioTaskProviders"
                 or isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id.startswith("_PORTFOLIO_") for target in node.targets)]
        namespace = {"Counter": Counter, "_portfolio_Counter": Counter,
                     "_portfolio_copy": deepcopy, "_portfolio_clock": time.monotonic}
        helper_module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *nodes], type_ignores=[])
        exec(compile(ast.fix_missing_locations(helper_module), "<built-portfolio-helpers-only>", "exec"), namespace)
        cls.select = staticmethod(namespace["_portfolio_select_attempt1"])
        cls.priority = namespace["_PORTFOLIO_PRIORITY"]
        cls.registry = namespace.get("_PortfolioTaskProviders")
        cls.qualified_policy = cls.report.get("new_attempt1_training_requirement") == "all_current_train_exact"

    def setUp(self):
        self.query, self.second, self.alternative = [[0]], [[1]], [[2]]
        self.task = {"train": [{"input": [[3]], "output": [[4]]}], "test": [{"input": self.query}]}

    def row(self, **changes):
        result = {"answer": None, "second_answer": deepcopy(self.second), "status": "断定保留",
                  "reasons": ["候補不足"], "hds_primary_hold": True,
                  "portfolio_attempt1": deepcopy(self.alternative),
                  "portfolio_diagnostics": {"eligible": True, "selected": True, "sources": [],
                                            "selected_family": "object_extraction"}}
        if self.qualified_policy:
            result["portfolio_diagnostics"]["selected_qualification"] = self.proof(1)
        result.update(changes)
        return result

    @staticmethod
    def proof(total):
        return {"qualified": True, "train_exact": total, "train_total": total,
                "fit_error_type": None, "validation_error_counts": {}}

    def qualified_value(self, value, total=1):
        if not self.qualified_policy:
            return value
        grid, evidence = value if isinstance(value, tuple) and len(value) == 2 else (value, {})
        return grid, {**evidence, "qualification": self.proof(total)}

    def providers(self, values):
        return tuple((family, "test_support_policy", lambda value=value: self.qualified_value(value))
                     for family, value in zip(self.priority, values, strict=True))

    def test_payload_difference_is_one_runtime_source_plus_internal_manifest(self):
        self.assertEqual(self.report["archive_member_changes"], sorted([evaluation.MANIFEST, evaluation.WRAPPER]))
        self.assertEqual(self.report["runtime_member_changes"], [evaluation.WRAPPER])
        self.assertEqual(self.report["unchanged_runtime_members"], 282)
        self.assertEqual(self.payloads["baseline"]["entries"][evaluation.HDS], self.payloads["candidate"]["entries"][evaluation.HDS])

    def test_new_candidate_directory_requires_an_explicit_hash_pin(self):
        with self.assertRaisesRegex(ValueError, "explicit --expected-candidate-sha256"):
            evaluation.preflight(HERE.parent / "not-opened-unpinned-candidate")

    def test_solver_evaluation_requires_new_first_full_train_contract(self):
        with self.assertRaisesRegex(ValueError, "all-current-train-qualified"):
            evaluation.require_candidate_contract({"new_attempt1_training_requirement": None})
        evaluation.require_candidate_contract({"new_attempt1_training_requirement": "all_current_train_exact"})

    def test_only_new_first_requires_complete_and_error_free_train_qualification(self):
        self.assertTrue(evaluation.new_first_qualification(None, 3)["valid"])
        self.assertTrue(evaluation.new_first_qualification({"attempt1_source": "input_copy_fallback"}, 3)["valid"])
        proof = {"qualified": True, "train_exact": 3, "train_total": 3,
                 "fit_error_type": None, "validation_error_counts": {}}
        audit = {"attempt1_source": "external_portfolio", "portfolio": {"selected_qualification": proof}}
        self.assertTrue(evaluation.new_first_qualification(audit, 3)["valid"])
        for changes in ({"qualified": False}, {"train_exact": 2}, {"train_total": 2},
                        {"fit_error_type": "SyntheticError"}, {"validation_error_counts": {"prediction": 1}},
                        {"train_exact": True}):
            altered = deepcopy(audit)
            altered["portfolio"]["selected_qualification"].update(changes)
            self.assertFalse(evaluation.new_first_qualification(altered, 3)["valid"])
        self.assertFalse(evaluation.new_first_qualification({"attempt1_source": "external_portfolio"}, 3)["valid"])

    def test_priority_dedup_alias_safety_and_target_free_diagnostics(self):
        shared = deepcopy(self.alternative)
        values = [(self.second, {}), (shared, {"top_votes": 3}), ([[5]], {}), (shared, {}),
                  (None, {}), (self.query, {}), ("invalid", {})]
        before = deepcopy((self.query, self.second, shared))
        selected, audit = self.select(self.query, self.second, self.providers(values), self.valid)
        self.assertEqual(selected, self.alternative)
        self.assertEqual(audit["selected_family"], "object_extraction")
        self.assertEqual(audit["distinct_alternatives_to_v61_attempt2"], 2)
        self.assertEqual(audit["selected_supporting_families"], ["object_extraction", "object_palette"])
        self.assertFalse(evaluation.contains_grid(audit))
        selected[0][0] = 8
        self.assertEqual((self.query, self.second, shared), before)

    def test_provider_failure_does_not_erase_other_valid_proposal(self):
        def failed():
            raise ArithmeticError("pure synthetic failure")
        providers = list(self.providers([(None, {})] * 7))
        providers[0] = (self.priority[0], "test", failed)
        providers[2] = (self.priority[2], "test", lambda: self.qualified_value((self.alternative, {})))
        selected, audit = self.select(self.query, self.second, tuple(providers), self.valid)
        self.assertEqual(selected, self.alternative)
        error_key = "query_error_type" if self.qualified_policy else "error_type"
        self.assertEqual(audit["sources"][0][error_key], "ArithmeticError")
        self.assertEqual(self.second, [[1]])

    def test_no_alternative_and_priority_change_are_explicit(self):
        selected, audit = self.select(self.query, self.second, self.providers([(self.second, {})] * 7), self.valid)
        self.assertIsNone(selected)
        self.assertFalse(audit["selected"])
        providers = list(self.providers([(None, {})] * 7))
        providers[0] = ("wrong_family", "test", lambda: None)
        with self.assertRaises(ValueError):
            self.select(self.query, self.second, tuple(providers), self.valid)

    def test_eligible_materialization_preserves_second_and_hold_provenance(self):
        source = {"results": [self.row()]}
        previous, old_hold = self.baseline("analysis", self.task, deepcopy(source))
        current, new_hold = self.candidate("analysis", self.task, deepcopy(source))
        self.assertEqual(previous, [{"attempt_1": self.query, "attempt_2": self.second}])
        self.assertEqual(current, [{"attempt_1": self.alternative, "attempt_2": self.second}])
        self.assertEqual(new_hold[0]["reason"], old_hold[0]["reason"])
        self.assertEqual(new_hold[0]["attempt1_source"], "external_portfolio")
        self.assertFalse(new_hold[0]["true_input_copy_fallback"])
        self.assertTrue(new_hold[0]["v61_attempt2_preserved"])
        invariants = evaluation.row_invariants(previous[0], current[0], self.query, True, new_hold[0])
        self.assertTrue(invariants["attempt2_equal"] and invariants["materialization_valid"])

    def test_formatter_rejects_unqualified_or_mismatched_training_count(self):
        if not self.qualified_policy:
            self.skipTest("historical v1 did not implement qualification")
        for changes in ({"qualified": False}, {"train_exact": 0}, {"train_total": 2},
                        {"fit_error_type": "TypeError"}, {"validation_error_counts": {"ValueError": 1}}):
            source = self.row()
            source["portfolio_diagnostics"]["selected_qualification"].update(changes)
            current, audit = self.candidate("analysis", self.task, {"results": [source]})
            self.assertEqual(current, [{"attempt_1": self.query, "attempt_2": self.second}])
            self.assertFalse(audit[0]["portfolio"]["materialized"])
        source = self.row()
        del source["portfolio_diagnostics"]["selected_qualification"]
        self.assertEqual(self.candidate("analysis", self.task, {"results": [source]})[0],
                         [{"attempt_1": self.query, "attempt_2": self.second}])

    def test_registry_qualifies_all_train_once_using_isolated_bound_predictor(self):
        if self.registry is None:
            self.skipTest("historical v1 did not implement qualification registry")
        teachers = [{"input": [[value]], "output": [[value + 1]]} for value in (3, 4, 5)]
        original = deepcopy(teachers)
        calls, factories = [], []
        def factory(training):
            factories.append(deepcopy(training))
            training[0]["output"][0][0] = 9  # Must not mutate registry or baseline support.
            def predict(query):
                calls.append(deepcopy(query))
                return [[query[0][0] + 1]], {"count": 1, "raw_grid": query}
            return predict
        registry = self.registry(teachers, [(family, "test", factory) for family in self.priority], self.valid)
        self.assertEqual(calls, [])
        first, evidence = registry.predict(self.priority[0], [[6]])
        self.assertEqual(first, [[7]])
        self.assertEqual(calls, [[[3]], [[4]], [[5]], [[6]]])
        self.assertEqual(teachers, original)
        self.assertEqual(evidence["qualification"]["train_exact"], 3)
        self.assertEqual(evidence["qualification"]["train_total"], 3)
        self.assertTrue(evidence["qualification"]["qualified"])
        self.assertTrue(evidence["timing"]["qualification_attempted"])
        self.assertFalse(evaluation.contains_grid(evidence))
        second, cached = registry.predict(self.priority[0], [[7]])
        self.assertEqual(second, [[8]])
        self.assertEqual(len(factories), 1)
        self.assertEqual(len(calls), 5)
        self.assertTrue(cached["timing"]["qualification_cached"])
        self.assertEqual(cached["timing"]["fit_seconds"], 0)
        # Returned evidence and grids cannot mutate cached qualification/support.
        cached["qualification"]["qualified"] = False
        self.assertTrue(registry.predict(self.priority[0], [[6]])[1]["qualification"]["qualified"])
        selected, audit = self.select([[0]], [[1]], registry.providers_for_query([[6]]), self.valid)
        self.assertEqual(selected, [[7]])
        self.assertEqual(audit["selected_qualification"]["train_total"], 3)
        self.assertTrue(evaluation.new_first_qualification(
            {"attempt1_source": "external_portfolio", "portfolio": audit}, 3)["valid"])

    def test_registry_rejects_mismatch_invalid_fit_and_validation_errors_without_query(self):
        if self.registry is None:
            self.skipTest("historical v1 did not implement qualification registry")
        teachers = [{"input": [[value]], "output": [[value + 1]]} for value in (3, 4, 5)]
        for failure in ("mismatch", "invalid", "fit", "validation"):
            with self.subTest(failure=failure):
                calls, fits = [], []
                def factory(training):
                    fits.append(1)
                    if failure == "fit":
                        raise ArithmeticError("synthetic fit failure")
                    def predict(query):
                        calls.append(deepcopy(query))
                        if query == [[4]]:
                            if failure == "validation":
                                raise ValueError("synthetic validation failure")
                            return "invalid" if failure == "invalid" else [[9]]
                        return [[query[0][0] + 1]]
                    return predict
                registry = self.registry(teachers, [(family, "test", factory) for family in self.priority], self.valid)
                predicted, evidence = registry.predict(self.priority[0], [[8]])
                self.assertIsNone(predicted)
                self.assertFalse(evidence["qualification"]["qualified"])
                self.assertNotIn([[8]], calls)
                self.assertEqual(len(calls), 0 if failure == "fit" else 3)
                self.assertIsNone(registry.predict(self.priority[0], [[8]])[0])
                self.assertEqual(len(fits), 1)
                self.assertEqual(len(calls), 0 if failure == "fit" else 3)
                if failure == "fit":
                    self.assertEqual(evidence["qualification"]["fit_error_type"], "ArithmeticError")
                elif failure == "validation":
                    self.assertEqual(evidence["qualification"]["validation_error_counts"], {"ValueError": 1})

    def test_existing_primary_and_error_rows_remain_outside_intervention(self):
        source = {"results": [self.row(answer=[[6]])]}
        self.assertEqual(self.baseline("analysis", self.task, deepcopy(source))[0],
                         self.candidate("analysis", self.task, deepcopy(source))[0])
        for source in ({"error": "task_wall_timeout"}, {"results": [self.row(answer="invalid")]}):
            previous, _ = self.baseline("analysis", self.task, deepcopy(source))
            current, audit = self.candidate("analysis", self.task, deepcopy(source))
            self.assertEqual(previous, current)
            self.assertEqual(audit[0]["attempt1_source"], "input_copy_fallback")

    def test_legacy_second_is_normalized_before_first_can_change(self):
        for second in (None, self.query, "invalid"):
            current, audit = self.candidate("analysis", self.task, {"results": [self.row(second_answer=second)]})
            self.assertEqual(current, [{"attempt_1": self.query, "attempt_2": self.query}])
            self.assertFalse(audit[0]["portfolio"]["materialized"])
        for proposal in (self.query, self.second):
            current, _ = self.candidate("analysis", self.task, {"results": [self.row(portfolio_attempt1=proposal)]})
            self.assertEqual(current, [{"attempt_1": self.query, "attempt_2": self.second}])

    def test_multirow_formatter_does_not_renormalize_later_second_slots(self):
        task = {"train": self.task["train"], "test": [{"input": self.query}, {"input": [[4]]}]}
        source = {"results": [self.row(), self.row(second_answer=[[5]], portfolio_attempt1=[[6]])]}
        before = deepcopy(source)
        previous, _ = self.baseline("analysis", task, deepcopy(source))
        current, audit = self.candidate("analysis", task, source)
        self.assertEqual([row["attempt_2"] for row in previous], [row["attempt_2"] for row in current])
        self.assertEqual(current, [{"attempt_1": [[2]], "attempt_2": [[1]]}, {"attempt_1": [[6]], "attempt_2": [[5]]}])
        self.assertEqual(source, before)
        self.assertTrue(all(row["v61_attempt2_preserved"] for row in audit))

    def test_eligibility_requires_complete_hds_hold_and_generated_existing_second(self):
        pair = {"attempt_1": self.query, "attempt_2": self.second}
        self.assertTrue(evaluation.baseline_eligible("complete", {"primary_is_none": True}, {"reason": "solver_hold"}, pair, self.query))
        for state, metadata, audit, candidate in [
            ("timeout", {"primary_is_none": True}, {"reason": "solver_hold"}, pair),
            ("complete", {"primary_is_none": False}, {"reason": "solver_hold"}, pair),
            ("complete", {"primary_is_none": True}, {"reason": "invalid_prediction"}, pair),
            ("complete", {"primary_is_none": True}, {"reason": "solver_hold"}, {"attempt_1": self.query, "attempt_2": self.query}),
        ]:
            self.assertFalse(evaluation.baseline_eligible(state, metadata, audit, candidate, self.query))

    def test_timeout_still_produces_one_audited_pair_for_every_requested_input(self):
        task = {"train": self.task["train"], "test": [{"input": self.query}, {"input": [[4]]}]}
        with patch.object(evaluation.subprocess, "run", side_effect=subprocess.TimeoutExpired("synthetic", 1)):
            result = evaluation.invoke(HERE / "not-executed", task, [], 1, self.baseline)
        self.assertEqual(result["state"], "timeout")
        self.assertEqual(len(result["predictions"]), 2)
        self.assertEqual(len(result["hold_audit"]), 2)
        self.assertEqual(result["predictions"][1], {"attempt_1": [[4]], "attempt_2": [[4]]})
        score = evaluation.score_attempts(result["predictions"][0], self.query, self.query, result["hold_audit"][0])
        self.assertTrue(score["raw_pass2"])
        self.assertFalse(score["nonfallback_pass2"])

    def test_scientific_scoring_is_attempt_level_and_raw_identity_regression_remains_visible(self):
        previous, old_hold = self.baseline("analysis", self.task, {"results": [self.row()]})
        current, new_hold = self.candidate("analysis", self.task, {"results": [self.row()]})
        old = evaluation.score_attempts(previous[0], self.query, self.query, old_hold[0])
        new = evaluation.score_attempts(current[0], self.query, self.query, new_hold[0])
        self.assertTrue(old["raw_pass2"])
        self.assertFalse(new["raw_pass2"])
        self.assertFalse(old["nonfallback_pass2"] or new["nonfallback_pass2"])
        first = evaluation.score_attempts(current[0], self.alternative, self.query, new_hold[0])
        second = evaluation.score_attempts(previous[0], self.second, self.query, old_hold[0])
        self.assertTrue(first["nonfallback_pass1"])
        self.assertTrue(second["nonfallback_pass2"] and second["second_incremental_exact"])
        self.assertTrue(evaluation.score_attempts({"attempt_1": self.query, "attempt_2": self.query}, self.query, self.query, None)["nonfallback_pass1"])

    def test_preservation_checks_detect_changed_second_and_outside_scope_rows(self):
        old = {"attempt_1": self.query, "attempt_2": self.second}
        changed = {"attempt_1": self.alternative, "attempt_2": [[7]]}
        result = evaluation.row_invariants(old, changed, self.query, False, {"attempt1_source": "external_portfolio"})
        self.assertFalse(result["attempt2_equal"])
        self.assertFalse(result["outside_scope_unchanged"])
        self.assertFalse(result["materialization_valid"])

    def test_parent_template_filter_removes_task_and_input_collisions(self):
        sources = [{"source_task_id": "same", "pair": {"input": [[3]], "output": [[4]]}},
                   {"source_task_id": "other", "pair": {"input": self.query, "output": [[5]]}},
                   {"source_task_id": "safe", "pair": {"input": [[6]], "output": [[7]]}}]
        pairs, audit = evaluation.template_for_task(sources, "same", [self.query])
        self.assertEqual(pairs, [{"input": [[6]], "output": [[7]]}])
        self.assertEqual(audit["removed_same_source_task"], 1)
        self.assertEqual(audit["removed_query_input_collision"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
