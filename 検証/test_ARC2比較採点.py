import hashlib
import json
import pytest

from 検証.ARC2比較採点 import 比較


def test_paired_improvement_and_regression_are_not_hidden_by_zero_delta(tmp_path):
    def save(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path
    challenges = save("challenges.json", {k: {"test": [{"input": [[0]]}]} for k in ("a", "b")})
    solutions = save("solutions.json", {"a": [[[1]]], "b": [[[1]]]})
    previous = save("before.json", {"a": [{"attempt_1": [[0]], "attempt_2": [[0]]}],
                                    "b": [{"attempt_1": [[1]], "attempt_2": [[1]]}]})
    current = save("after.json", {"a": [{"attempt_1": [[0]], "attempt_2": [[1]]}],
                                  "b": [{"attempt_1": [[0]], "attempt_2": [[0]]}]})
    def audit(name, predictions):
        return save(name, {"challenge_sha256": hashlib.sha256(challenges.read_bytes()).hexdigest(),
                           "submission_sha256": hashlib.sha256(predictions.read_bytes()).hexdigest(),
                           "fallback_count": 1, "test_examples": 2,
                           "fallbacks": [{"task_id": "a", "test_index": 0, "reason": "solver_hold"}]})
    old_audit, new_audit = audit("old-audit.json", previous), audit("new-audit.json", current)
    result = 比較(previous=previous, previous_audit=old_audit, current=current, current_audit=new_audit,
               challenges=challenges, solutions=solutions)
    assert (result["pass2_delta"], result["improved_grids"], result["regressed_grids"]) == (0, 1, 1)
    assert (result["changed_first_attempts"], result["changed_second_attempts"]) == (1, 2)
    new_audit.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA256"):
        比較(previous=previous, previous_audit=old_audit, current=current, current_audit=new_audit,
           challenges=challenges, solutions=solutions)
