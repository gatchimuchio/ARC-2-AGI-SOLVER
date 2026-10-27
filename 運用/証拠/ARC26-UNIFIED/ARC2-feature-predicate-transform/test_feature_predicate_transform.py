from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from 接続.ARC2.単純変換候補 import fitted_models, orientations


MODULE_PATH = Path(__file__).with_name("feature_predicate_transform.py")
SPEC = importlib.util.spec_from_file_location("arc2_feature_predicate_experiment", MODULE_PATH)
experiment = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = experiment
SPEC.loader.exec_module(experiment)
FeaturePredicateTransform = experiment.FeaturePredicateTransform
Bounds = experiment.Bounds


def pair(grid, orientation):
    return {"input": deepcopy(grid), "output": orientations(grid)[orientation]}


def teachers():
    return [
        pair([[0, 1, 0], [0, 0, 2]], "rotate90"),
        pair([[0, 3, 0], [0, 0, 4]], "rotate90"),
        pair([[0, 0], [1, 0], [0, 2]], "reflect_horizontal"),
        pair([[0, 0], [3, 0], [0, 4]], "reflect_horizontal"),
    ]


def test_learns_two_typed_transforms_and_generalizes_to_new_input_colors():
    examples = teachers()
    assert fitted_models(examples) == []  # Existing single global program cannot solve the fixture.
    model = FeaturePredicateTransform(examples)
    left = [[0, 5, 0], [0, 0, 6]]
    right = [[0, 0], [7, 0], [0, 8]]

    assert model.記録()["status"] == "fitted"
    assert model.記録()["training_replayed"] == 4
    assert model.候補(left, {})[0] == orientations(left)["rotate90"]
    assert model.候補(right, {})[0] == orientations(right)["reflect_horizontal"]


def test_observations_change_model_structure_without_saving_answer_grids():
    examples = teachers()
    query = [[0, 5, 0], [0, 0, 6]]
    before = FeaturePredicateTransform(examples[:2])
    after = FeaturePredicateTransform(examples)

    assert before.候補(query, {})[0] is None
    assert before.model_state()["hypotheses"] == []
    assert after.model_state()["hypotheses"]
    assert after.候補(query, {})[0] == orientations(query)["rotate90"]
    def no_raw_grids(value):
        if isinstance(value, dict):
            assert not ({"input", "output", "task_id", "answer_map"} & set(value))
            for item in value.values():
                no_raw_grids(item)
        elif isinstance(value, list):
            assert not (value and all(isinstance(row, list) for row in value))
            for item in value:
                no_raw_grids(item)
    no_raw_grids(after.model_state())


def test_runtime_context_cannot_supply_or_override_a_target():
    model = FeaturePredicateTransform(teachers())
    query = [[0, 5, 0], [0, 0, 6]]
    ordinary = model.候補(query, {})

    assert model.候補(query, {"expected": [[9]], "output": [[8]], "task_id": "unused"}) == ordinary


def test_duplicate_observation_does_not_create_second_branch_support():
    examples = teachers()
    duplicate = [examples[0], deepcopy(examples[0]), examples[2], examples[3]]
    model = FeaturePredicateTransform(duplicate)

    assert model.記録()["distinct_training_examples"] == 3
    assert model.候補(examples[0]["input"], {}) == (None, {"reason": "insufficient_distinct_support"})


def test_conflicting_outputs_for_same_input_abstain():
    examples = teachers()
    contradictory = deepcopy(examples[0])
    contradictory["output"] = [[9]]
    model = FeaturePredicateTransform([*examples, contradictory])

    assert model.候補(examples[0]["input"], {}) == (None, {"reason": "conflicting_duplicate_input"})


def test_every_current_teacher_is_validated_and_invalid_pair_is_not_dropped():
    examples = teachers()
    contradiction = {"input": [[0, 5, 0], [0, 0, 6]], "output": [[0] * 7 for _ in range(7)]}
    model = FeaturePredicateTransform([*examples, contradiction])
    invalid = FeaturePredicateTransform([*examples, {"input": [[1]], "output": []}])

    assert model.候補(examples[0]["input"], {})[0] is None
    assert model.記録()["status"] == "no_conditional_model"
    assert invalid.記録()["status"] == "invalid_teacher"


def test_unobserved_threshold_interval_abstains():
    examples = teachers()[:2] + [
        pair([[0, 1, 0], [0, 0, 2], [0, 0, 0], [0, 0, 0], [0, 0, 0]], "reflect_horizontal"),
        pair([[0, 3, 0], [0, 0, 4], [0, 0, 0], [0, 0, 0], [0, 0, 0]], "reflect_horizontal"),
    ]
    model = FeaturePredicateTransform(examples, feature_indices=(0,))
    query = [[0, 5, 0], [0, 0, 6], [0, 0, 0]]

    assert model.記録()["status"] == "fitted"
    assert model.候補(query, {}) == (None, {"reason": "unobserved_predicate_gap"})


def test_equal_simple_programs_that_disagree_on_unseen_grid_abstain():
    examples = [
        pair([[0, 1, 2], [0, 1, 2]], "rotate90"),
        pair([[0, 3, 4], [0, 3, 4]], "rotate90"),
        pair([[0, 1, 0], [0, 0, 2], [0, 0, 0], [1, 0, 0]], "reflect_horizontal"),
        pair([[0, 3, 0], [0, 0, 4], [0, 0, 0], [3, 0, 0]], "reflect_horizontal"),
    ]
    model = FeaturePredicateTransform(examples, feature_indices=(0,))
    query = [[0, 5, 6], [0, 0, 7]]

    assert model.記録()["status"] == "fitted"
    assert model.記録()["retained_hypotheses"] >= 2
    assert model.候補(query, {}) == (None, {"reason": "ambiguous_minimal_hypotheses"})


def test_additional_teacher_disambiguates_unseen_query_with_same_support_eligibility():
    examples = [
        pair([[0, 1, 2], [0, 1, 2]], "rotate90"),
        pair([[0, 3, 4], [0, 3, 4]], "rotate90"),
        pair([[0, 1, 0], [0, 0, 2], [0, 0, 0], [1, 0, 0]], "reflect_horizontal"),
        pair([[0, 3, 0], [0, 0, 4], [0, 0, 0], [3, 0, 0]], "reflect_horizontal"),
    ]
    feedback = pair([[0, 5, 6], [0, 0, 7]], "rotate90")
    unseen = [[0, 8, 1], [0, 0, 9]]
    before = FeaturePredicateTransform(examples, feature_indices=(0,))
    after = FeaturePredicateTransform([*examples, feedback], feature_indices=(0,))

    # Both phases already satisfy the same two-distinct-inputs-per-branch floor.
    assert before.記録()["status"] == after.記録()["status"] == "fitted"
    assert before.model_state()["bounds"] == after.model_state()["bounds"]
    assert all(min(h["support"]) >= 2 for h in before.model_state()["hypotheses"])
    assert all(min(h["support"]) >= 2 for h in after.model_state()["hypotheses"])
    assert before.候補(unseen, {}) == (None, {"reason": "ambiguous_minimal_hypotheses"})
    assert after.候補(unseen, {})[0] == orientations(unseen)["rotate90"]
    assert after.記録()["retained_hypotheses"] < before.記録()["retained_hypotheses"]
    assert after.記録()["training_replayed"] == 5


def test_fit_is_deterministic_under_teacher_reordering():
    examples = teachers()

    assert FeaturePredicateTransform(examples).model_state() == FeaturePredicateTransform(list(reversed(examples))).model_state()


def test_existing_global_transform_is_left_to_existing_solver():
    examples = [pair(p["input"], "rotate90") for p in teachers()]
    model = FeaturePredicateTransform(examples)

    assert model.記録()["status"] == "global_transform_already_supported"
    assert model.候補(examples[0]["input"], {})[0] is None


def test_search_budget_abstains_instead_of_truncating_hypotheses():
    model = FeaturePredicateTransform(teachers(), feature_indices=(0, 1), bounds=Bounds(max_predicates=1))

    assert model.記録()["predicates"] == 2
    assert model.記録()["status"] == "predicate_budget_exceeded"
    assert model.model_state()["hypotheses"] == []


def test_state_roundtrip_and_fresh_process_prediction_need_no_teacher_memory():
    model = FeaturePredicateTransform(teachers())
    state = json.loads(json.dumps(model.model_state()))
    query = [[0, 5, 0], [0, 0, 6]]
    restored = FeaturePredicateTransform.from_state(state)
    assert restored.model_state() == state
    assert restored.候補(query, {}) == model.候補(query, {})
    code = """
import importlib.util,json,sys
spec=importlib.util.spec_from_file_location('fresh_predicate_experiment',sys.argv[1])
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
payload=json.load(sys.stdin)
model=module.FeaturePredicateTransform.from_state(payload['state'])
print(json.dumps(model.候補(payload['query'],{})[0]))
"""
    completed = subprocess.run([sys.executable, "-c", code, str(MODULE_PATH)],
                               input=json.dumps({"state": state, "query": query}),
                               capture_output=True, text=True, encoding="utf-8", check=True,
                               cwd=MODULE_PATH.parents[4])
    assert json.loads(completed.stdout) == orientations(query)["rotate90"]


def test_state_rejects_added_answer_map_and_invalid_support():
    state = FeaturePredicateTransform(teachers()).model_state()
    injected = {**state, "answer_map": {"anything": [[9]]}}
    with pytest.raises(ValueError):
        FeaturePredicateTransform.from_state(injected)
    too_little = deepcopy(state)
    too_little["hypotheses"][0]["support"] = [1, 3]
    with pytest.raises(ValueError):
        FeaturePredicateTransform.from_state(too_little)


def test_real_existing_hds_admission_validates_current_training_pairs():
    examples = teachers()
    model = FeaturePredicateTransform(examples)
    machine = experiment.new_hds_machine()
    admission = model.admit_to_hds(machine, examples)

    assert admission["採用可"] is True
    assert admission["同値採用"] is True
    assert admission["現在観測数"] == 4
    query = [[0, 5, 0], [0, 0, 6]]
    output = model.query_via_hds(machine, query)
    assert output["hds_queried"] is True
    assert output["answer"] == orientations(query)["rotate90"]


def test_existing_hds_counterexample_is_preserved_and_not_force_admitted():
    examples = teachers()
    model = FeaturePredicateTransform(examples)
    contradiction = {"input": [[0, 5, 0], [0, 0, 6]], "output": [[9]]}

    admission = model.admit_to_hds(experiment.new_hds_machine(), [*examples, contradiction])

    assert admission["採用可"] is False
    assert admission["状態"] == "教師反例により不採用"


def test_hds_hold_is_returned_without_candidate_fallback(monkeypatch):
    model = FeaturePredicateTransform(teachers())
    calls = []
    def hold(machine, observation, **kwargs):
        calls.append((machine, observation, kwargs))
        return {"answer": None, "status": "断定保留", "reasons": ["synthetic HDS hold"], "equality_admitted": False}
    monkeypatch.setattr(experiment, "_hds_connection", lambda: SimpleNamespace(
        観測へ=lambda values, boundary: (values, boundary), 出力格子=hold))

    result = model.query_via_hds(object(), [[0, 5, 0], [0, 0, 6]])

    assert len(calls) == 1
    assert calls[0][2] == {"同値必須": True}
    assert result["answer"] is None
    assert result["status"] == "断定保留"
    assert result["hds_queried"] is True
