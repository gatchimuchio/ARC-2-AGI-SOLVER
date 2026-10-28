from 接続.ARC2 import 二面真理値候補 as module
from 接続.ARC2.二面真理値候補 import candidate, candidate_details, local_training_evidence, provisional_action_gate


def _training():
    return [
        {"input": [[0, 0, 1, 0, 1, 0], [0, 0, 0, 1, 0, 0]],
         "output": [[0, 2, 2], [2, 0, 0]]},
        {"input": [[1, 0, 0, 1, 0, 0], [0, 0, 0, 0, 0, 1]],
         "output": [[2, 0, 0], [0, 0, 2]]},
    ]


def test_learns_complete_mapping_and_applies_to_new_input():
    test = [[1, 0, 1, 0, 1, 0], [0, 0, 0, 1, 0, 1]]
    assert candidate(_training(), test) == [[2, 2, 2], [2, 0, 2]]


def test_rejects_contradiction_repeated_examples_and_tied_background():
    train = _training()
    train[1]["output"][0][1] = 2
    assert candidate(train, _training()[0]["input"]) is None
    assert candidate(_training()[:1] * 2, _training()[0]["input"]) is None
    assert candidate(_training(), [[0, 1, 0, 1, 1, 0]]) is None


def test_rejects_third_output_color():
    train = _training()
    train[0]["output"][0][1] = 3
    train[0]["output"][1][0] = 3
    assert candidate(train, train[0]["input"]) is None


def test_loo_marks_unevaluable_folds_and_retains_provisional_source():
    answer, details = candidate_details(_training(), _training()[0]["input"])
    assert answer == _training()[0]["output"]
    assert details["loo_total"] == 2 and details["loo_unavailable"] == 2
    assert details["loo_conflicts"] == 0 and details["loo_correct"] == 0
    assert details["decision"] == "provisional_external_candidate"


def test_loo_conflict_rejects_a_candidate(monkeypatch):
    train = _training()
    monkeypatch.setattr(module, "_candidate_without_loo", lambda remaining, grid: [[9]])
    answer, details = candidate_details(train, train[0]["input"])
    assert answer is None and details["loo_conflicts"] == 2
    assert details["decision"] == "rejected_loo_conflict"


def _gate_inputs():
    return {"train_exact": True, "loo": {"loo_total": 2, "loo_correct": 0,
            "loo_conflicts": 0, "loo_unavailable": 2},
            "hds_basis": {"status": "断定保留", "reason_count": 1, "reason_labels": ["MISSING_OBSERVATION"], "quarantined": 0,
                          "answer_present": False, "equality_admitted": False},
            "now_monotonic": 10.0, "cutoff_monotonic": 20.0}


def test_provisional_gate_preserves_hds_hold_and_first_attempt_for_any_target():
    for first in range(3):
        for proposed in range(3):
            if first == proposed:
                continue
            gate = provisional_action_gate([[first]], [[first]], [[proposed]], **_gate_inputs())
            assert gate["accepted"] is True
            assert gate["hds_truth_approved"] is False and gate["confidence"] is None
            assert gate["hds_basis"]["status"] == "断定保留"
            for truth in range(3):
                before = first != truth
                after = first != truth and proposed != truth
                assert after <= before


def test_provisional_gate_rejects_existing_choice_missing_evidence_and_deadline():
    options = _gate_inputs()
    assert not provisional_action_gate([[0]], [[2]], [[1]], **options)["accepted"]
    assert not provisional_action_gate([[0]], None, [[0]], **options)["accepted"]
    assert not provisional_action_gate([[0]], None, [[10]], **options)["accepted"]
    assert not provisional_action_gate([[0]], None, [[1]], **{**options, "train_exact": False})["accepted"]
    assert not provisional_action_gate([[0]], None, [[1]], **{**options, "hds_basis": None})["accepted"]
    invalid_basis = {**options["hds_basis"], "status": "HDS_BOGUS_VALUE"}
    assert not provisional_action_gate([[0]], None, [[1]], **{**options, "hds_basis": invalid_basis})["accepted"]
    invalid_basis = {**options["hds_basis"], "reason_labels": []}
    assert not provisional_action_gate([[0]], None, [[1]], **{**options, "hds_basis": invalid_basis})["accepted"]
    invalid_basis = {**options["hds_basis"], "reason_labels": ["INVENTED"]}
    assert not provisional_action_gate([[0]], None, [[1]], **{**options, "hds_basis": invalid_basis})["accepted"]
    assert not provisional_action_gate([[0]], None, [[1]], **{**options, "cutoff_monotonic": 10.0})["accepted"]
    assert not provisional_action_gate([[0]], None, [[1]], **{**options, "cutoff_monotonic": float("nan")})["accepted"]
    assert not provisional_action_gate([[0]], None, [[1]], **{**options, "now_monotonic": 10**309})["accepted"]
    assert not provisional_action_gate([[0]], None, [[1]], **{**options, "cutoff_monotonic": 10**309})["accepted"]
    conflict = {"loo_total": 2, "loo_correct": 1, "loo_conflicts": 1, "loo_unavailable": 0}
    assert not provisional_action_gate([[0]], None, [[1]], **{**options, "loo": conflict})["accepted"]


def test_local_training_evidence_separates_exact_conflict_and_abstention():
    train = [{"input": [[0]], "output": [[1]]}, {"input": [[2]], "output": [[3]]}]

    class FakeModel:
        def __init__(self, pairs):
            self.pairs = pairs

        def 候補(self, grid, _policy):
            if len(self.pairs) == 2:
                return ([[1]] if grid == [[0]] else [[3]]), {}
            return (None if grid == [[0]] else [[4]]), {}

    result = local_training_evidence(train, FakeModel(train), FakeModel, clock=lambda: 1.0, cutoff_monotonic=2.0)
    assert result["train_exact"] and result["loo_applicable"]
    assert (result["loo_total"], result["loo_correct"], result["loo_conflicts"], result["loo_unavailable"]) == (2, 0, 1, 1)
    missing = local_training_evidence(train, FakeModel(train[:1]), FakeModel, clock=lambda: 1.0, cutoff_monotonic=2.0)
    assert not missing["train_exact"] and missing["reason"] == "training_not_reproduced"
    expired = local_training_evidence(train, FakeModel(train), FakeModel, clock=lambda: 2.0, cutoff_monotonic=2.0)
    assert not expired["train_exact"] and expired["reason"] == "deadline_expired"
    unknown = local_training_evidence(train, FakeModel(train), FakeModel, clock=lambda: 1.0, cutoff_monotonic=None)
    assert not unknown["train_exact"] and unknown["reason"] == "deadline_unknown"

    class Broken:
        def 候補(self, grid, _policy):
            raise RuntimeError("local-only failure")

    failed = local_training_evidence(train, Broken(), FakeModel, clock=lambda: 1.0, cutoff_monotonic=2.0)
    assert not failed["train_exact"] and failed["reason"] == "local_validation_error"
    failed_loo = local_training_evidence(train, FakeModel(train), lambda pairs: Broken(),
                                         clock=lambda: 1.0, cutoff_monotonic=2.0)
    assert not failed_loo["train_exact"] and failed_loo["reason"] == "local_validation_error"


def test_local_training_evidence_records_one_shot_as_loo_unavailable():
    class Single:
        def 候補(self, grid, _policy):
            return [[1]], {}

    train = [{"input": [[0]], "output": [[1]]}]
    result = local_training_evidence(train, Single(), lambda pairs: Single(), clock=lambda: 1.0, cutoff_monotonic=2.0)
    assert result["train_exact"] and not result["loo_applicable"] and result["loo_total"] == 0


def test_local_provisional_gate_records_one_shot_and_loo_conflict_without_hds_approval():
    options = _gate_inputs()
    one_shot = {"loo_total": 0, "loo_correct": 0, "loo_conflicts": 0, "loo_unavailable": 0}
    gate = provisional_action_gate([[0]], [[0]], [[1]], **{**options, "loo": one_shot}, allow_one_shot_loo=True)
    assert gate["accepted"] and gate["hds_truth_approved"] is False and gate["confidence"] is None
    conflict = {"loo_total": 2, "loo_correct": 1, "loo_conflicts": 1, "loo_unavailable": 0}
    gate = provisional_action_gate([[0]], [[0]], [[1]], **{**options, "loo": conflict}, allow_loo_conflicts=True)
    assert gate["accepted"] and gate["hds_truth_approved"] is False
    assert not provisional_action_gate([[0]], [[2]], [[1]], **{**options, "loo": conflict}, allow_loo_conflicts=True)["accepted"]
