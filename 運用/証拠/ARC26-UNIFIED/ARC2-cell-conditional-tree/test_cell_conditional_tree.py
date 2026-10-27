from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from 接続.ARC2.局所近傍変換候補 import LocalCellContextCandidate


MODULE = Path(__file__).with_name("cell_conditional_tree.py")
SPEC = importlib.util.spec_from_file_location("arc2_cell_tree_experiment", MODULE)
experiment = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = experiment
SPEC.loader.exec_module(experiment)
CellConditionalTree, Bounds = experiment.CellConditionalTree, experiment.Bounds


def feature(name):
    return experiment.FEATURES.index(name)


def paint(grid):
    return [[6 if value else 0 for value in row] for row in grid]


def paint_teachers():
    first = [[0] * 5 for _ in range(5)]
    first[1][1], first[3][3] = 1, 2
    second = [[0] * 5 for _ in range(5)]
    second[1][3], second[3][1] = 3, 4
    return [{"input": grid, "output": paint(grid)} for grid in (first, second)]


def left_copy(grid):
    return [[row[0], *row[:-1]] for row in grid]


def role_teachers():
    return [{"input": grid, "output": left_copy(grid)} for grid in (
        [[1, 2, 3], [4, 5, 6]], [[7, 0, 8], [2, 9, 1]],
    )]


def test_default_tree_generalizes_a_feature_subset_beyond_exact_context_mapping():
    examples = paint_teachers()
    model = CellConditionalTree(examples)
    query = [[0] * 5 for _ in range(5)]
    query[2][2], query[3][2] = 8, 9

    assert model.status == "fitted", model.model_state()
    assert model.training_replayed == 2
    assert model.候補(query, {})[0] == paint(query)
    assert LocalCellContextCandidate(examples).候補(query, {})[0] != paint(query)
    assert all(model.候補(pair["input"], {})[0] == pair["output"] for pair in examples)


def test_input_role_leaves_compute_new_colors_and_new_shape_without_coordinates():
    model = CellConditionalTree(role_teachers())
    query = [[9, 8, 7, 6], [5, 4, 3, 2], [1, 0, 2, 3]]

    assert model.status == "fitted", model.model_state()
    assert model.候補(query, {"output": [[9]], "task_id": "ignored"})[0] == left_copy(query)
    serialized = json.dumps(model.model_state())
    assert '"input"' not in serialized and '"output"' not in serialized
    assert "answer_map" not in serialized and "task_id" not in serialized
    assert "row_index" not in serialized and "column_index" not in serialized


def test_duplicate_inputs_cannot_create_teacher_support_and_conflicts_hold():
    example = paint_teachers()[0]
    duplicate = CellConditionalTree([example, deepcopy(example)])
    contradictory = deepcopy(example)
    contradictory["output"][0][0] = 9

    assert duplicate.status == "insufficient_distinct_teachers"
    assert CellConditionalTree([example, contradictory]).status == "conflicting_duplicate_input"


def test_shape_change_and_invalid_teacher_are_not_silently_ignored():
    examples = paint_teachers()
    assert CellConditionalTree([*examples, {"input": [[1]], "output": [[1, 1]]}]).status == "teacher_shape_changed"
    assert CellConditionalTree([*examples, {"input": [[1]], "output": []}]).status == "invalid_teacher"


def test_each_leaf_requires_two_distinct_teacher_inputs_not_repeated_cells():
    examples = [{"input": [[1] * 4] * 4, "output": [[6] * 4] * 4},
                {"input": [[2] * 4] * 4, "output": [[7] * 4] * 4}]
    model = CellConditionalTree(examples)

    assert model.status == "no_exact_bounded_tree"
    assert model.forest is None


def test_unseen_categorical_branch_holds_whole_grid():
    examples = [{"input": [[0, 1, 0]], "output": [[0, 6, 0]]},
                {"input": [[0, 1, 1]], "output": [[0, 6, 6]]}]
    model = CellConditionalTree(examples, feature_indices=(feature("context_4"),))

    assert model.status == "fitted"
    assert model.候補([[0, 2, 1]], {}) == (None, {"reason": "unseen_feature_category"})


def test_equal_cost_color_roles_that_disagree_on_query_are_retained_and_hold():
    grids = [[[1, 2, 3], [2, 3, 4], [3, 4, 5]],
             [[6, 7, 8], [7, 8, 9], [8, 9, 0]]]
    examples = []
    for grid in grids:
        target = deepcopy(grid)
        for row in (1, 2):
            for column in (1, 2):
                target[row][column] = grid[row - 1][column]
        examples.append({"input": grid, "output": target})
    model = CellConditionalTree(examples, feature_indices=(feature("border_top"), feature("border_left")))

    assert model.status == "fitted"
    assert "neighbor_1" in json.dumps(model.model_state())
    assert "neighbor_3" in json.dumps(model.model_state())
    assert model.候補([[1, 2, 3], [4, 5, 6], [7, 8, 9]], {}) == (None, {"reason": "ambiguous_minimal_trees"})


def test_budgets_hold_instead_of_returning_an_incomplete_search_result():
    examples = paint_teachers()
    assert CellConditionalTree(examples, bounds=Bounds(max_nodes=1)).status == "no_exact_bounded_tree"
    unsupported = [{"input": [[1, 1], [1, 1]], "output": [[6, 6], [6, 6]]},
                   {"input": [[2, 2], [2, 2]], "output": [[7, 7], [7, 7]]}]
    limited = CellConditionalTree(unsupported, bounds=Bounds(max_fit_states=1))
    assert limited.status == "fit_state_budget_exceeded"
    assert limited.forest is None
    assert CellConditionalTree(examples, bounds=Bounds(max_work_units=1)).status == "work_budget_exceeded"
    assert CellConditionalTree(examples, bounds=Bounds(max_training_cells=10)).status == "training_cell_budget_exceeded"


def test_reordering_is_deterministic_and_runtime_state_has_no_teacher_grids():
    examples = paint_teachers()
    before = CellConditionalTree(examples)
    after = CellConditionalTree(list(reversed(examples)))

    assert before.model_state() == after.model_state()
    assert not hasattr(before, "teachers")
    assert before.候補(examples[0]["input"], {}) == before.候補(examples[0]["input"], {"expected": [[9]]})


def test_state_roundtrip_in_fresh_process_needs_only_typed_state_and_input():
    model = CellConditionalTree(role_teachers())
    state = json.loads(json.dumps(model.model_state()))
    query = [[9, 8, 7, 6], [5, 4, 3, 2]]
    restored = CellConditionalTree.from_state(state)
    assert restored.model_state() == state
    assert restored.候補(query, {})[0] == left_copy(query)
    code = """
import importlib.util,json,sys
spec=importlib.util.spec_from_file_location('fresh_cell_tree',sys.argv[1])
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
payload=json.load(sys.stdin)
model=module.CellConditionalTree.from_state(payload['state'])
print(json.dumps(model.候補(payload['input'],{})[0]))
"""
    completed = subprocess.run([sys.executable, "-c", code, str(MODULE)], input=json.dumps({"state": state, "input": query}),
                               capture_output=True, text=True, encoding="utf-8", check=True, cwd=MODULE.parents[4])
    assert json.loads(completed.stdout) == left_copy(query)


def test_state_rejects_answer_map_and_unsupported_leaf():
    state = CellConditionalTree(role_teachers()).model_state()
    with pytest.raises(ValueError):
        CellConditionalTree.from_state({**state, "answer_map": {"x": [[9]]}})
    altered = deepcopy(state)
    def invalidate(forest):
        for tree in forest["choices"]:
            if tree["kind"] == "leaf":
                tree["teacher_support"] = 1
                return True
            for child in tree["branches"].values():
                if invalidate(child):
                    return True
    assert invalidate(altered["forest"])
    with pytest.raises(ValueError):
        CellConditionalTree.from_state(altered)


def test_real_existing_hds_admission_query_and_counterexample_rejection():
    examples = paint_teachers()
    model = CellConditionalTree(examples)
    machine = experiment.new_hds_machine()
    admission = model.admit_to_hds(machine, examples)
    # Preserve the unchanged HDS default support gate (three observations).
    assert admission["採用可"] is True and admission["同値採用"] is False
    assert model.query_via_hds(machine, examples[0]["input"])["answer"] is None
    third = [[0] * 5 for _ in range(5)]
    third[2][1], third[2][3] = 5, 7
    examples.append({"input": third, "output": paint(third)})
    model = CellConditionalTree(examples)
    machine = experiment.new_hds_machine()
    admission = model.admit_to_hds(machine, examples)
    assert admission["採用可"] is True and admission["同値採用"] is True
    query = [[0] * 5 for _ in range(5)]
    query[2][2] = 8
    output = model.query_via_hds(machine, query)
    assert output["hds_queried"] is True
    assert output["answer"] == paint(query)
    wrong = {"input": query, "output": [[9] * 5 for _ in range(5)]}
    rejection = model.admit_to_hds(experiment.new_hds_machine(), [*examples, wrong])
    assert rejection["採用可"] is False
    assert rejection["状態"] == "教師反例により不採用"


def test_feedback_removes_role_ambiguity_with_both_phases_already_hds_eligible():
    def teacher(grid):
        target = deepcopy(grid)
        for row in range(1, len(grid)):
            for column in range(1, len(grid[0])):
                target[row][column] = grid[row - 1][column]
        return {"input": grid, "output": target}
    examples = [teacher(grid) for grid in (
        [[1, 2, 3], [2, 3, 4], [3, 4, 5]],
        [[6, 7, 8], [7, 8, 9], [8, 9, 0]],
        [[2, 4, 6], [4, 6, 8], [6, 8, 1]],
    )]
    feedback = teacher([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    unseen = teacher([[9, 8, 7], [6, 5, 4], [3, 2, 1]])
    grammar = (feature("border_top"), feature("border_left"))
    before = CellConditionalTree(examples, feature_indices=grammar)
    after = CellConditionalTree([*examples, feedback], feature_indices=grammar)
    before_machine, after_machine = experiment.new_hds_machine(), experiment.new_hds_machine()
    previous_admission = before.admit_to_hds(before_machine, examples)
    current_admission = after.admit_to_hds(after_machine, [*examples, feedback])

    assert before.status == after.status == "fitted"
    assert previous_admission["同値採用"] is True
    assert current_admission["同値採用"] is True
    previous = before.query_via_hds(before_machine, unseen["input"])
    current = after.query_via_hds(after_machine, unseen["input"])
    assert previous["answer"] is None
    assert previous["reasons"] == ["ambiguous_minimal_trees"]
    assert current["answer"] == unseen["output"] and current["hds_queried"] is True
    assert before.model_state()["forest"] != after.model_state()["forest"]
    assert after.training_replayed == 4


def test_hds_hold_is_not_replaced_by_direct_candidate(monkeypatch):
    model = CellConditionalTree(paint_teachers())
    monkeypatch.setattr(experiment, "_connection", lambda: SimpleNamespace(
        観測へ=lambda value, boundary: (value, boundary),
        出力格子=lambda machine, observation, **kwargs: {"answer": None, "status": "HOLD", "same_required": kwargs["同値必須"]}))
    result = model.query_via_hds(object(), paint_teachers()[0]["input"])

    assert result["answer"] is None and result["status"] == "HOLD"
    assert result["hds_queried"] is True and result["same_required"] is True
