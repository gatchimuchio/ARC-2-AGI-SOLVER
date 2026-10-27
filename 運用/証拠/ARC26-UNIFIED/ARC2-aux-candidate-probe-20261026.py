"""Offline, aggregate-only probe for simple and feature-neighbor candidates.

Predictions for all challenge inputs are materialized in memory before public
training outputs are loaded for offline scoring. No per-task predictions or
targets are written to disk.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact(row: dict, target: list[list[int]]) -> bool:
    return any(row.get(name) == target for name in ("attempt_1", "attempt_2"))


def score(candidate_by_task, baseline, labels):
    baseline_tasks = baseline_examples = candidate_tasks = candidate_examples = 0
    merged_tasks = merged_examples = 0
    newly_correct_tasks = regressed_tasks = 0
    predicted_tasks = predicted_examples = 0

    for task_id, base_rows in baseline.items():
        targets = labels[task_id]
        candidates = candidate_by_task.get(task_id, [])
        merged_rows = []
        for index, target in enumerate(targets):
            base = base_rows[index]
            candidate = candidates[index] if index < len(candidates) else None
            if candidate is not None:
                predicted_examples += 1
            merged_second = (
                candidate
                if isinstance(candidate, list) and candidate != base["attempt_1"]
                else base["attempt_2"]
            )
            merged_rows.append({"attempt_1": base["attempt_1"], "attempt_2": merged_second})
            baseline_examples += exact(base, target)
            candidate_examples += candidate == target
            merged_examples += exact(merged_rows[-1], target)
        predicted_tasks += bool(any(x is not None for x in candidates))
        base_ok = all(exact(row, target) for row, target in zip(base_rows, targets, strict=True))
        merged_ok = all(
            exact(row, target)
            for row, target in zip(merged_rows, targets, strict=True)
        )
        baseline_tasks += base_ok
        candidate_tasks += bool(candidates) and all(
            index < len(candidates) and candidates[index] == target
            for index, target in enumerate(targets)
        )
        merged_tasks += merged_ok
        newly_correct_tasks += merged_ok and not base_ok
        regressed_tasks += base_ok and not merged_ok

    return {
        "candidate_tasks_with_any_prediction": predicted_tasks,
        "candidate_predicted_examples": predicted_examples,
        "candidate_exact_tasks": candidate_tasks,
        "candidate_exact_examples": candidate_examples,
        "baseline_correct_tasks": baseline_tasks,
        "baseline_correct_examples": baseline_examples,
        "candidate_as_attempt_2_correct_tasks": merged_tasks,
        "candidate_as_attempt_2_correct_examples": merged_examples,
        "delta_correct_tasks": merged_tasks - baseline_tasks,
        "delta_correct_examples": merged_examples - baseline_examples,
        "newly_correct_tasks": newly_correct_tasks,
        "regressed_tasks": regressed_tasks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    sys.path.insert(0, str(ROOT))
    from 接続.ARC2.特徴近傍変換選択 import FeatureNeighborTransform
    from 接続.ARC2.単純変換候補 import unique_candidate

    challenge_path = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
    baseline_path = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v10/output/submission.json"
    training_dir = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
    challenge = json.loads(challenge_path.read_text(encoding="utf-8"))
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    # Candidate generation sees only each challenge task's public train and test inputs.
    feature_predictions: dict[str, list] = {}
    simple_predictions: dict[str, list] = {}
    for task_id, task in challenge.items():
        feature = FeatureNeighborTransform(task["train"])
        feature_predictions[task_id] = [
            feature.候補(pair["input"], {})[0] for pair in task["test"]
        ]
        simple_predictions[task_id] = [
            unique_candidate(task["train"], pair["input"]) for pair in task["test"]
        ]

    if set(feature_predictions) != set(challenge) or set(simple_predictions) != set(challenge):
        raise RuntimeError("candidate generation did not cover every challenge task")

    # The public ARC-AGI-2 training outputs are opened only after all predictions exist.
    labels = {}
    for path in training_dir.glob("*.json"):
        task = json.loads(path.read_text(encoding="utf-8"))
        labels[path.stem] = [pair["output"] for pair in task.get("test", [])]
    if not set(challenge).issubset(labels):
        raise RuntimeError("some challenge tasks have no offline scoring labels")
    for task_id, task in challenge.items():
        if len(labels[task_id]) != len(task["test"]):
            raise RuntimeError("offline scoring example count mismatch")

    report = {
        "schema": "arc2-aux-candidate-probe-v1",
        "candidate_generation_completed_before_labels_loaded": True,
        "labels_source": "public ARC-AGI-2 training files, offline scorecard only",
        "challenge_tasks": len(challenge),
        "challenge_test_examples": sum(len(task["test"]) for task in challenge.values()),
        "simple_transform": score(simple_predictions, baseline, labels),
        "feature_neighbor": score(feature_predictions, baseline, labels),
        "integration_assumption": "candidate is offered as attempt_2; baseline attempt_1 is preserved and baseline attempt_2 is retained when the candidate is absent or duplicates attempt_1",
        "not_production_gate_equivalence": True,
        "official_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": sha(Path(__file__)),
            "challenge_inputs": sha(challenge_path),
            "baseline_submission": sha(baseline_path),
            "simple_transform": sha(ROOT / "接続/ARC2/単純変換候補.py"),
            "feature_neighbor": sha(ROOT / "接続/ARC2/特徴近傍変換選択.py"),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "simple_transform": report["simple_transform"], "feature_neighbor": report["feature_neighbor"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
