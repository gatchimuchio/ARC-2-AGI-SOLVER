import json
import pytest

from 検証.ARC2候補診断採点 import 集計, _格子, _hash


def test_only_observed_candidates_and_distinct_second_attempt_are_counted(tmp_path):
    challenges = {name: {"test": [{"input": [[0]]}]} for name in ("a", "b", "c", "d", "e")}
    predictions = {name: [{"attempt_1": [[0]], "attempt_2": [[0]]}] for name in challenges}
    predictions["a"][0]["attempt_2"] = [[1]]
    solutions = {name: [[[1]]] for name in challenges}
    def record(name, candidates):
        value = {"results": [{"diagnostic_candidates": {"preselection": candidates,
                   "postselection": [], "simple_candidate": None, "candidate_attempts": None}}]}
        bound = {"run_token": "run123", "task_sha256": _hash(challenges[name]),
                 "result_sha256": _hash(value), "result": value}
        (tmp_path / f"{name}.json").write_text(json.dumps(bound), encoding="utf-8")
    record("a", [])
    record("b", [{"answer": [[1]]}])
    record("c", [{"answer": [[2]]}])
    record("d", [])
    audit = {"fallbacks": [{"task_id": name, "test_index": 0, "reason": "solver_hold"}
                           for name in challenges], "fallback_count": 5,
             "deadline_control": {"run_token": "run123"}}
    result = 集計(challenges=challenges, predictions=predictions, baseline_predictions=predictions,
              audit=audit, baseline_audit=audit, solutions=solutions, records_dir=tmp_path)
    assert result == {"submitted_correct": 1, "observed_correct_candidate_not_submitted": 1,
                      "observed_candidates_incorrect": 1, "no_candidate_observed": 1,
                      "unobserved": 1, "invalid_candidate_observations": 0,
                      "missing_diagnostic_rows": 1}


def test_changed_predictions_or_fallbacks_refuse_comparison(tmp_path):
    audit = {"fallbacks": [], "fallback_count": 0, "deadline_control": {"run_token": "run123"}}
    kwargs = dict(challenges={}, predictions={}, baseline_predictions={"a": []}, audit=audit,
                  baseline_audit=audit, solutions={}, records_dir=tmp_path)
    with pytest.raises(ValueError, match="出力変更"):
        集計(**kwargs)
    kwargs["baseline_predictions"] = {}
    kwargs["baseline_audit"] = {"fallbacks": [{"task_id": "a", "test_index": 0, "reason": "solver_hold"}], "fallback_count": 1}
    with pytest.raises(ValueError, match="fallback"):
        集計(**kwargs)


def test_illegal_grids_and_foreign_run_are_rejected(tmp_path):
    assert not _格子([[10]]) and not _格子([[-1]]) and not _格子([[0] * 31])
    challenge = {"test": [{"input": [[0]]}]}
    pred = {"a": [{"attempt_1": [[0]], "attempt_2": [[1]]}]}
    result = {"results": [{"diagnostic_candidates": {"preselection": [], "postselection": []}}]}
    record = {"run_token": "wrong", "task_sha256": _hash(challenge),
              "result_sha256": _hash(result), "result": result}
    (tmp_path / "a.json").write_text(json.dumps(record), encoding="utf-8")
    audit = {"fallbacks": [], "fallback_count": 0, "deadline_control": {"run_token": "run123"}}
    with pytest.raises(ValueError, match="診断記録"):
        集計(challenges={"a": challenge}, predictions=pred, baseline_predictions=pred,
           audit=audit, baseline_audit=audit, solutions={"a": [[[1]]]}, records_dir=tmp_path)
