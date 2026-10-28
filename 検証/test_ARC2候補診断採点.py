import json
import pytest

from 検証.ARC2候補診断採点 import 集計


def test_only_observed_candidates_and_distinct_second_attempt_are_counted(tmp_path):
    challenges = {name: {"test": [{"input": [[0]]}]} for name in ("a", "b", "c", "d", "e")}
    predictions = {name: [{"attempt_1": [[0]], "attempt_2": [[0]]}] for name in challenges}
    predictions["a"][0]["attempt_2"] = [[1]]
    solutions = {name: [[[1]]] for name in challenges}
    def record(name, candidates):
        value = {"results": [{"diagnostic_candidates": {"preselection": candidates,
                   "postselection": [], "simple_candidate": None, "candidate_attempts": None}}]}
        (tmp_path / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
    record("a", [])
    record("b", [{"answer": [[1]]}])
    record("c", [{"answer": [[2]]}])
    record("d", [])
    audit = {"fallbacks": [{"task_id": name, "test_index": 0, "reason": "solver_hold"}
                           for name in challenges]}
    result = 集計(challenges=challenges, predictions=predictions, baseline_predictions=predictions,
              audit=audit, baseline_audit=audit, solutions=solutions, records_dir=tmp_path)
    assert result == {"submitted_correct": 1, "observed_correct_candidate_not_submitted": 1,
                      "observed_candidates_incorrect": 1, "no_candidate_observed": 1,
                      "unobserved": 1}


def test_changed_predictions_or_fallbacks_refuse_comparison(tmp_path):
    audit = {"fallbacks": []}
    kwargs = dict(challenges={}, predictions={}, baseline_predictions={"a": []}, audit=audit,
                  baseline_audit=audit, solutions={}, records_dir=tmp_path)
    with pytest.raises(ValueError, match="出力変更"):
        集計(**kwargs)
    kwargs["baseline_predictions"] = {}
    kwargs["baseline_audit"] = {"fallbacks": [{"task_id": "a", "test_index": 0, "reason": "solver_hold"}]}
    with pytest.raises(ValueError, match="fallback"):
        集計(**kwargs)
