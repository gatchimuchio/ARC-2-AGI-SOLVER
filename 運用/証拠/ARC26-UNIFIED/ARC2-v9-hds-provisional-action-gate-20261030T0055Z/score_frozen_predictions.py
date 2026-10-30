"""Score frozen ARC2 public-training predictions outside the runtime."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
BASE = Path(__file__).resolve().parent
TRAIN_DIR = ROOT / "\u5165\u529b" / "\u516c\u5f0f\u30bd\u30fc\u30b9" / "ARC-AGI-2" / "data" / "training"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    challenge_path = BASE / "challenge_input.json"
    manifest_path = BASE / "selection_manifest.json"
    baseline_freeze_path = BASE / "baseline-freeze.json"
    candidate_freeze_path = BASE / "candidate-freeze.json"
    baseline_path = BASE / "baseline_submission.json"
    candidate_path = BASE / "candidate_submission.json"
    baseline_audit_path = BASE / "baseline_audit.json"
    candidate_audit_path = BASE / "candidate_audit.json"
    output_path = BASE / "paired-score.json"
    if output_path.exists():
        raise FileExistsError("Refusing to overwrite existing paired score evidence")

    baseline_freeze = read_json(baseline_freeze_path)
    candidate_freeze = read_json(candidate_freeze_path)
    challenge = read_json(challenge_path)
    manifest = read_json(manifest_path)
    baseline_audit = read_json(baseline_audit_path)
    candidate_audit = read_json(candidate_audit_path)

    challenge_sha = sha256(challenge_path)
    assert challenge_sha == baseline_freeze["challenge_sha256"]
    assert challenge_sha == candidate_freeze["challenge_sha256"]
    assert sha256(baseline_path) == baseline_freeze["prediction_sha256"]
    assert sha256(candidate_path) == candidate_freeze["prediction_sha256"]
    assert sha256(baseline_audit_path) == baseline_freeze["audit_sha256"]
    assert sha256(candidate_audit_path) == candidate_freeze["audit_sha256"]
    assert baseline_audit["challenge_sha256"] == challenge_sha
    assert candidate_audit["challenge_sha256"] == challenge_sha
    assert baseline_freeze["scoring_status"].startswith("NOT_RUN")
    assert candidate_freeze["scoring_status"].startswith("NOT_RUN")

    baseline = read_json(baseline_path)
    candidate = read_json(candidate_path)
    baseline_fallbacks = {
        (item["task_id"], item["test_index"])
        for item in baseline_audit["fallbacks"]
    }
    candidate_fallbacks = {
        (item["task_id"], item["test_index"])
        for item in candidate_audit["fallbacks"]
    }

    result = {
        "format": "arc2-v9-paired-public-training-score-v1",
        "scored_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": BASE.name,
        "evidence_scope": "Public ARC2 training only; preregistered input-only cohort; exposure remains unknown.",
        "challenge_sha256": challenge_sha,
        "source_training_inventory_sha256": manifest["source_training_inventory_sha256"],
        "fallback_policy": "An audited input-copy fallback receives no credit. For an audited fallback grid, any attempt equal to its test input is excluded; a distinct second candidate may still score.",
        "baseline": {"prediction_sha256": sha256(baseline_path)},
        "candidate": {"prediction_sha256": sha256(candidate_path)},
        "paired": {"changed_attempt1": 0, "changed_attempt2": 0, "changed_test_examples": 0},
    }
    score_rows = {
        name: {"pass1": 0, "pass2": 0, "unique_attempt2": 0, "fallback_grids": 0}
        for name in ("baseline", "candidate")
    }
    total = 0
    for item in manifest["selected_source_tasks"]:
        alias = item["alias"]
        task_id = item["public_training_task_id"]
        source_path = TRAIN_DIR / f"{task_id}.json"
        assert sha256(source_path) == item["source_file_sha256"]
        source = read_json(source_path)
        challenge_tests = challenge[alias]["test"]
        truth_tests = source["test"]
        assert len(challenge_tests) == len(truth_tests) == item["test_grid_count"]
        assert len(baseline[alias]) == len(candidate[alias]) == len(truth_tests)

        for index, (challenge_test, truth_test, base_prediction, new_prediction) in enumerate(
            zip(challenge_tests, truth_tests, baseline[alias], candidate[alias])
        ):
            assert set(challenge_test) == {"input"}
            assert challenge_test["input"] == truth_test["input"]
            assert set(base_prediction) == {"attempt_1", "attempt_2"}
            assert set(new_prediction) == {"attempt_1", "attempt_2"}
            total += 1
            changed1 = base_prediction["attempt_1"] != new_prediction["attempt_1"]
            changed2 = base_prediction["attempt_2"] != new_prediction["attempt_2"]
            result["paired"]["changed_attempt1"] += changed1
            result["paired"]["changed_attempt2"] += changed2
            result["paired"]["changed_test_examples"] += changed1 or changed2
            truth = truth_test["output"]
            input_grid = challenge_test["input"]
            for name, prediction, fallback_set in (
                ("baseline", base_prediction, baseline_fallbacks),
                ("candidate", new_prediction, candidate_fallbacks),
            ):
                audited_fallback = (alias, index) in fallback_set
                valid1 = not (audited_fallback and prediction["attempt_1"] == input_grid)
                valid2 = not (audited_fallback and prediction["attempt_2"] == input_grid)
                correct1 = valid1 and prediction["attempt_1"] == truth
                correct2 = valid2 and prediction["attempt_2"] == truth
                score_rows[name]["pass1"] += correct1
                score_rows[name]["pass2"] += correct1 or correct2
                score_rows[name]["unique_attempt2"] += correct2 and not correct1
                score_rows[name]["fallback_grids"] += audited_fallback

    assert total == baseline_audit["test_examples"] == candidate_audit["test_examples"]
    for name in ("baseline", "candidate"):
        score_rows[name]["denominator"] = total
        score_rows[name]["fallback_count"] = (
            baseline_audit["fallback_count"] if name == "baseline"
            else candidate_audit["fallback_count"]
        )
        score_rows[name]["wall_seconds"] = (
            baseline_audit["seconds"] if name == "baseline"
            else candidate_audit["seconds"]
        )
        result[name].update(score_rows[name])
        result[name]["candidate_prediction_count"] = (
            baseline_audit["aggregate_diagnostics"]["candidate_prediction_count"]
            if name == "baseline"
            else candidate_audit["aggregate_diagnostics"]["candidate_prediction_count"]
        )
        result[name]["examples_with_candidates"] = (
            baseline_audit["aggregate_diagnostics"]["examples_with_candidates"]
            if name == "baseline"
            else candidate_audit["aggregate_diagnostics"]["examples_with_candidates"]
        )
    result["denominator"] = total
    result["delta"] = {
        key: score_rows["candidate"][key] - score_rows["baseline"][key]
        for key in ("pass1", "pass2", "unique_attempt2", "fallback_count", "wall_seconds")
    }
    result["official_score"] = None
    result["official_score_note"] = "This public-training score is not a Kaggle score."
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
