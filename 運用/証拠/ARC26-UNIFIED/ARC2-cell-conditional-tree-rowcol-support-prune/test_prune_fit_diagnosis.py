from copy import deepcopy
import ast
import importlib.util
import json
from pathlib import Path
import sys

import pytest


HERE = Path(__file__).resolve().parent
def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


diagnosis = load("arc2_fit_budget_diagnosis_test", "prune_fit_diagnosis.py")
model = load("arc2_fit_budget_condition_model", "cell_conditional_tree.py")


def input_grid(rare, *, move=False):
    grid = [[0] * 5 for _ in range(5)]
    grid[0][0] = grid[0][1] = 1
    grid[4][3 if move else 4] = rare
    return grid


def pair(grid, color=None):
    return {"input": grid, "output": deepcopy(grid) if color is None else [[color] * 5 for _ in range(5)]}


def test_identical_full_feature_group_with_no_common_action_disproves_any_depth():
    first, second = input_grid(2), input_grid(2, move=True)
    assert model._input_cells(first)[12][0] == model._input_cells(second)[12][0]
    result = diagnosis.necessary_condition(model, [pair(first, 6), pair(second, 7)])

    assert result["grammar_impossible_at_any_depth"] is True
    assert result["inexpressible_groups"] > 0
    assert result["cells_in_inexpressible_groups"] >= 2
    assert all(type(value) in (int, bool) for value in result.values())


def test_different_targets_with_same_features_remain_possible_via_own_dynamic_role():
    first, second = input_grid(7), input_grid(8)
    first_features, first_roles = model._input_cells(first)[12]
    second_features, second_roles = model._input_cells(second)[12]
    assert first_features == second_features
    assert model._program_value("unique_rarest", first_roles) == 7
    assert model._program_value("unique_rarest", second_roles) == 8
    result = diagnosis.necessary_condition(model, [pair(first, 7), pair(second, 8)])

    assert result["grammar_impossible_at_any_depth"] is False
    assert result["inexpressible_groups"] == 0


def test_nonminimal_programs_are_not_pruned_before_intersection():
    first, second = input_grid(6), input_grid(7)
    _features, roles = model._input_cells(first)[12]
    assert model._program_value("unique_rarest", roles) == 6
    assert model._program_cost("unique_rarest") < model._program_cost("constant:6")
    result = diagnosis.necessary_condition(model, [pair(first, 6), pair(second, 6)])

    assert result["inexpressible_groups"] == 0  # Constant6 remains common despite local role preference.


def test_positive_copy_control_does_not_misuse_per_group_teacher_support(monkeypatch):
    monkeypatch.setattr(model, "CellConditionalTree", lambda *args, **kwargs: pytest.fail("condition must not fit"))
    result = diagnosis.necessary_condition(model, [pair(input_grid(2))])

    assert result["checked_cells"] == 25
    assert result["grammar_impossible_at_any_depth"] is False
    assert result["nonempty_intersections_are_only_necessary"] is True


def test_worker_payload_excludes_identifiers_queries_and_u_but_after_observes_f():
    pairs = [{"input": [[color]], "output": [[color]]} for color in range(5)]
    training = {"parent_only_id": {"train": pairs, "test": [{"input": [[9]], "output": [[8]]}]}}
    row = {"task_id": "parent_only_id", "support_indices": [0, 1, 2], "feedback_index": 3, "unseen_index": 4}
    before = diagnosis.make_payload(training, row, "before", diagnosis.DEFAULT_BOUNDS)
    after = diagnosis.make_payload(training, row, "after", diagnosis.DEFAULT_BOUNDS)

    assert set(before) == set(after) == {"support", "bounds"}
    assert before["support"] == pairs[:3]
    assert after["support"] == pairs[:4]  # Observed F target is deliberately current train after feedback.
    assert pairs[4] not in before["support"] and pairs[4] not in after["support"]
    diagnosis.validate_payload(before, "necessary_condition")
    with pytest.raises(ValueError):
        diagnosis.validate_payload({**before, "queries": []}, "necessary_condition")
    with pytest.raises(ValueError):
        diagnosis.validate_payload({**before, "bounds": {**diagnosis.DEFAULT_BOUNDS, "max_depth": 4}}, "necessary_condition")
    for field, value in (("max_fit_states", 1024), ("max_work_units", 8_000_000)):
        with pytest.raises(ValueError):
            diagnosis.validate_payload({**before, "bounds": {**diagnosis.DEFAULT_BOUNDS, field: value}}, "pruned_fit")
    assert diagnosis.DEFAULT_BOUNDS["max_fit_states"] == 256
    assert diagnosis.DEFAULT_BOUNDS["max_work_units"] == 2_000_000


def test_phase_selection_requires_only_recorded_fit_status_not_scores():
    def evidence(status):
        state = dict.fromkeys(diagnosis.SUMMARY_FIELDS, 0)
        state.update(status=status, bounds=diagnosis.DEFAULT_BOUNDS, feature_indices=list(range(35)))
        return {"evidence": {"state": "complete", "model_fitted": {"typed_state": state}, "source_sha256": "pin", "arm_feature_count": 35, "typed_action_count": 21}}
    record = {"cohort_index": 2, "results": {"rowcol35": {"before": evidence("fit_state_budget_exceeded"),
                                                           "after": evidence("teacher_shape_changed")}}}
    selected = diagnosis.selected_cases([record])

    assert len(selected) == 1
    assert selected[0]["cohort_index"] == 2 and selected[0]["phase"] == "before"
    assert "scores" not in json.dumps(selected)


def test_one_pruned_fit_uses_only_same_bounds_and_optional_condition_does_not_expand():
    payload = {"support": [pair(input_grid(color)) for color in (2, 3, 4)], "bounds": diagnosis.DEFAULT_BOUNDS}
    calls = []
    def worker(data, mode):
        calls.append((deepcopy(data), mode))
        return {"state": "complete", "condition": {"grammar_impossible_at_any_depth": True}}
    result = diagnosis.diagnose_case(payload, worker)
    assert len(calls) == 1 and calls[0][1] == "pruned_fit"
    assert calls[0][0] == payload
    calls.clear()
    diagnosis.diagnose_case(payload, worker, with_condition=True)
    assert len(calls) == 1 and calls[0][1] == "pruned_fit_with_condition"
    assert calls[0][0]["support"] == payload["support"]
    assert calls[0][0]["bounds"] == diagnosis.DEFAULT_BOUNDS
    assert not hasattr(diagnosis, "EXPANDED_BOUNDS")


def test_before_never_indexes_feedback_or_u_and_after_never_indexes_u():
    class CurrentOnlyPairs(list):
        def __init__(self, values, blocked):
            super().__init__(values)
            self.blocked = set(blocked)
            self.accessed = []
        def __getitem__(self, key):
            assert key not in self.blocked, "heldout pair was accessed"
            self.accessed.append(key)
            return super().__getitem__(key)
    values = [{"input": [[v]], "output": [[v + 1]]} for v in range(5)]
    row = {"task_id": "parent_only", "support_indices": [0, 1, 2], "feedback_index": 3, "unseen_index": 4}
    for phase, blocked, expected in (("before", (3, 4), [0, 1, 2]), ("after", (4,), [0, 1, 2, 3])):
        pairs = CurrentOnlyPairs(values, blocked)
        result = diagnosis.make_payload({"parent_only": {"train": pairs}}, row, phase, diagnosis.DEFAULT_BOUNDS)
        assert set(pairs.accessed) == set(expected)
        assert set(result) == {"support", "bounds"}
    for changes in ({"support_indices": [0, 1, 3]}, {"support_indices": [0, 1, 4]},
                    {"feedback_index": 4}, {"support_indices": [0, 0, 1]}):
        with pytest.raises(ValueError):
            diagnosis.make_payload({"parent_only": {"train": values}}, {**row, **changes}, "before", diagnosis.DEFAULT_BOUNDS)


def test_script_has_no_hds_or_heldout_query_or_scoring_call():
    source = Path(diagnosis.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {"候補", "admit_to_hds", "query_via_hds", "new_hds_machine", "score_result", "出力格子", "課題を解く"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else None
            assert name not in forbidden
    assert 'module._connection = no_hds' in source
    assert 'FIT worker dataset/JSON file reads forbidden' in source


def test_fresh_synthetic_condition_worker_import_guard_and_no_fit():
    sources = diagnosis.fingerprint()
    payload = {"support": [pair(input_grid(color)) for color in (2, 3, 4)], "bounds": diagnosis.DEFAULT_BOUNDS}
    result = diagnosis.invoke(payload, "necessary_condition", sources["sha256"], timeout=30)

    assert result["state"] == "complete", result
    assert result["fit_executed"] is False and "fit" not in result
    assert result["condition"]["inexpressible_groups"] == 0
    assert result["runtime_origins_before"]["all_origins_pinned_current_worktree"] is True
    assert result["runtime_origins_after"] == result["runtime_origins_before"]
    assert result["support_unchanged"] is True
    assert "output" not in result and "forest" not in result
