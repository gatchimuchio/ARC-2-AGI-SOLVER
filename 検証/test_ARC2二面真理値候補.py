from 接続.ARC2 import 二面真理値候補 as module
from 接続.ARC2.二面真理値候補 import candidate, candidate_details


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
