import hashlib
import json

import pytest

from 検証.ARC2予測結果採点 import 採点


def fixture_files(tmp_path):
    predictions = {"task": [
        {"attempt_1": [[1]], "attempt_2": [[4]]},
        {"attempt_1": [[2]], "attempt_2": [[3]]},
        {"attempt_1": [[5]], "attempt_2": [[5]]},
    ]}
    pred = tmp_path / "submission.json"
    pred.write_text(json.dumps(predictions), encoding="utf-8")
    solutions = tmp_path / "solutions.json"
    solutions.write_text(json.dumps({"task": [[[4]], [[3]], [[5]]]}), encoding="utf-8")
    challenges = tmp_path / "challenges.json"
    challenges.write_text(json.dumps({"task": {"test": [{"input": [[1]]}, {"input": [[2]]}, {"input": [[5]]}]}}), encoding="utf-8")
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({"submission_sha256": hashlib.sha256(pred.read_bytes()).hexdigest(),
                                 "challenge_sha256": hashlib.sha256(challenges.read_bytes()).hexdigest(),
                                 "fallback_count": 2, "test_examples": 3,
                                 "fallbacks": [{"task_id": "task", "test_index": 0}, {"task_id": "task", "test_index": 2}]}), encoding="utf-8")
    return pred, audit, solutions, challenges


def test_fallback_match_is_not_counted_as_inference_and_attempt2_is_attributed(tmp_path):
    result = 採点(*fixture_files(tmp_path))
    assert result["grids"] == 3
    assert result["fallback_first_matches"] == 1
    assert result["fallback_second_candidate_hits"] == 1
    assert result["nonfallback_pass1"] == 0
    assert result["nonfallback_pass2"] == 2
    assert result["nonfallback_attempt2_only"] == 2


def test_rejects_audit_for_different_prediction_bytes(tmp_path):
    pred, audit, solutions, challenges = fixture_files(tmp_path)
    pred.write_bytes(pred.read_bytes() + b" ")
    with pytest.raises(ValueError, match="SHA256"):
        採点(pred, audit, solutions, challenges)


def test_rejects_missing_solution_instead_of_shrinking_denominator(tmp_path):
    pred, audit, solutions, challenges = fixture_files(tmp_path)
    solutions.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="対象"):
        採点(pred, audit, solutions, challenges)


def test_rejects_predictions_that_omit_a_challenge(tmp_path):
    pred, audit, solutions, challenges = fixture_files(tmp_path)
    challenges.write_text(json.dumps({"task": {"test": [{}, {}, {}]}, "missing": {"test": [{}]}}), encoding="utf-8")
    data = json.loads(audit.read_text(encoding="utf-8"))
    data["challenge_sha256"] = hashlib.sha256(challenges.read_bytes()).hexdigest()
    audit.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="課題"):
        採点(pred, audit, solutions, challenges)
