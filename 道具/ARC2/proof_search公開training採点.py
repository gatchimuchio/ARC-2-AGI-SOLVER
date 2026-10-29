"""凍結済み予測を公開training正解で事後採点する隔離scorer。runtimeには含めない。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _task_signature(task: dict[str, Any]) -> str:
    normalized = {
        "train": [
            {"input": pair["input"], "output": pair["output"]}
            for pair in task["train"]
        ],
        "test": [{"input": pair["input"]} for pair in task["test"]],
    }
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _new_counts() -> dict[str, int]:
    return {
        "pass_at_1_grids": 0,
        "pass_at_2_grids": 0,
        "unique_attempt_2_hits": 0,
        "model_only_pass_at_1_grids": 0,
        "model_only_pass_at_2_grids": 0,
        "model_only_unique_attempt_2_hits": 0,
        "fallback_first_slots": 0,
        "fallback_second_slots": 0,
        "fallback_hit_grids": 0,
        "tasks_pass_at_2": 0,
        "model_only_tasks_pass_at_2": 0,
    }


def _metrics(
    predictions: dict[str, Any],
    truth_by_alias: dict[str, list[list[list[int]]]],
    fallback_slots: set[tuple[str, int, str]],
) -> tuple[dict[str, Any], dict[tuple[str, int], tuple[bool, bool]]]:
    counts = _new_counts()
    total_grids = total_tasks = 0
    per_grid: dict[tuple[str, int], tuple[bool, bool]] = {}
    for alias, truths in truth_by_alias.items():
        rows = predictions[alias]
        if len(rows) != len(truths):
            raise ValueError(f"{alias}: prediction/test solution count mismatch")
        total_tasks += 1
        task_all = True
        model_task_all = True
        for test_index, truth in enumerate(truths):
            row = rows[test_index]
            first = row["attempt_1"] == truth
            second = row["attempt_2"] == truth
            first_fallback = (alias, test_index, "attempt_1") in fallback_slots
            second_fallback = (alias, test_index, "attempt_2") in fallback_slots
            model_first = first and not first_fallback
            model_second = second and not second_fallback
            raw_pass2 = first or second
            model_pass2 = model_first or model_second
            counts["pass_at_1_grids"] += first
            counts["pass_at_2_grids"] += raw_pass2
            counts["unique_attempt_2_hits"] += second and not first
            counts["model_only_pass_at_1_grids"] += model_first
            counts["model_only_pass_at_2_grids"] += model_pass2
            counts["model_only_unique_attempt_2_hits"] += model_second and not model_first
            counts["fallback_first_slots"] += first_fallback
            counts["fallback_second_slots"] += second_fallback
            counts["fallback_hit_grids"] += raw_pass2 and not model_pass2
            total_grids += 1
            task_all = task_all and raw_pass2
            model_task_all = model_task_all and model_pass2
            per_grid[(alias, test_index)] = (raw_pass2, model_pass2)
        counts["tasks_pass_at_2"] += task_all
        counts["model_only_tasks_pass_at_2"] += model_task_all

    def rate(key: str, denominator: int) -> float:
        return counts[key] / denominator if denominator else 0.0

    result = {
        **counts,
        "tasks": total_tasks,
        "test_grids": total_grids,
        "pass_at_1_grid_rate": rate("pass_at_1_grids", total_grids),
        "pass_at_2_grid_rate": rate("pass_at_2_grids", total_grids),
        "model_only_pass_at_1_grid_rate": rate("model_only_pass_at_1_grids", total_grids),
        "model_only_pass_at_2_grid_rate": rate("model_only_pass_at_2_grids", total_grids),
        "task_pass_at_2_rate": rate("tasks_pass_at_2", total_tasks),
        "model_only_task_pass_at_2_rate": rate("model_only_tasks_pass_at_2", total_tasks),
    }
    return result, per_grid


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    parser.add_argument("--cohort", type=Path, default=ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-v9-candidate-family-confirm100-input-20261029.json")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--baseline-audit", type=Path, required=True)
    parser.add_argument("--training-challenges", type=Path, default=ROOT / "入力/Kaggle/arc-agi_training_challenges.json")
    parser.add_argument("--training-solutions", type=Path, default=ROOT / "入力/Kaggle/arc-agi_training_solutions.json")
    parser.add_argument("--expected-predictions-sha256", required=True)
    parser.add_argument("--expected-baseline-sha256", default="2173b7ee8d4d72e377da32fbeaaae1e50e350f1bbe22cb6d9534fedc9483ce56")
    parser.add_argument("--expected-cohort-sha256", default="6d430ce94842262e32dedc4b1add48de313dd022f976a3b54bfadfb90f7be9da")
    parser.add_argument("--expected-training-challenges-sha256", default="779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5")
    parser.add_argument("--expected-training-solutions-sha256", default="9f07a38bd25af5e83aa5bf85c5cb1a1fefdb30f6a755256fa65429e697ca97f9")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    # Verify the prediction freeze and public data versions before opening any labels.
    observed = {
        "predictions": sha256(args.predictions),
        "baseline": sha256(args.baseline),
        "cohort": sha256(args.cohort),
        "training_challenges": sha256(args.training_challenges),
        "training_solutions": sha256(args.training_solutions),
    }
    expected = {
        "predictions": args.expected_predictions_sha256,
        "baseline": args.expected_baseline_sha256,
        "cohort": args.expected_cohort_sha256,
        "training_challenges": args.expected_training_challenges_sha256,
        "training_solutions": args.expected_training_solutions_sha256,
    }
    for name, expected_hash in expected.items():
        if observed[name] != expected_hash:
            raise ValueError(f"{name} SHA256 mismatch: {observed[name]} != {expected_hash}")

    cohort = load_json(args.cohort)
    candidate = load_json(args.predictions)
    candidate_diagnostics = load_json(args.diagnostics)
    baseline = load_json(args.baseline)
    baseline_audit = load_json(args.baseline_audit)
    if set(candidate) != set(cohort) or set(baseline) != set(cohort):
        raise ValueError("prediction keys do not match the frozen cohort aliases")

    challenge_data = load_json(args.training_challenges)
    signatures: dict[str, list[str]] = {}
    for task_id, task in challenge_data.items():
        signatures.setdefault(_task_signature(task), []).append(task_id)
    alias_to_task: dict[str, str] = {}
    for alias, task in cohort.items():
        matches = signatures.get(_task_signature(task), [])
        if len(matches) != 1:
            raise ValueError(f"{alias}: expected exactly one public training challenge match, got {len(matches)}")
        alias_to_task[alias] = matches[0]

    # This is the first point at which test labels are read; the prediction SHA is frozen above.
    solutions = load_json(args.training_solutions)
    truth_by_alias: dict[str, list[list[list[int]]]] = {}
    for alias, task_id in alias_to_task.items():
        truths = solutions.get(task_id)
        if not isinstance(truths, list):
            raise ValueError(f"{alias}: missing public training solutions")
        truth_by_alias[alias] = truths

    candidate_fallbacks: set[tuple[str, int, str]] = set()
    for alias, rows in candidate_diagnostics.items():
        for test_index, row in enumerate(rows):
            for attempt in ("attempt_1", "attempt_2"):
                if row[attempt].get("source") == "fallback":
                    candidate_fallbacks.add((alias, test_index, attempt))
    # The old audit labels a whole grid as solver_hold when attempt 1 fell back;
    # attempt 2 may still be a learned generic proposal. Exclude only an identity
    # copy in slot 2, whose output provenance cannot add solver ability.
    baseline_fallbacks: set[tuple[str, int, str]] = set()
    for item in baseline_audit.get("fallbacks", []):
        alias = item["task_id"]
        test_index = int(item["test_index"])
        baseline_fallbacks.add((alias, test_index, "attempt_1"))
        baseline_row = baseline[alias][test_index]
        input_grid = cohort[alias]["test"][test_index]["input"]
        if (
            baseline_row["attempt_2"] == baseline_row["attempt_1"]
            or baseline_row["attempt_2"] == input_grid
        ):
            baseline_fallbacks.add((alias, test_index, "attempt_2"))

    candidate_metrics, candidate_grid = _metrics(candidate, truth_by_alias, candidate_fallbacks)
    baseline_metrics, baseline_grid = _metrics(baseline, truth_by_alias, baseline_fallbacks)
    aliases = sorted(truth_by_alias)
    keys = sorted(candidate_metrics)
    deltas = {
        key: candidate_metrics[key] - baseline_metrics[key]
        for key in keys
        if isinstance(candidate_metrics[key], (int, float))
        and isinstance(baseline_metrics.get(key), (int, float))
    }
    candidate_added = []
    baseline_lost = []
    model_added = []
    model_lost = []
    for alias, test_index in sorted(candidate_grid):
        candidate_raw, candidate_model = candidate_grid[(alias, test_index)]
        baseline_raw, baseline_model = baseline_grid[(alias, test_index)]
        if candidate_raw and not baseline_raw:
            candidate_added.append({"alias": alias, "test_index": test_index})
        if baseline_raw and not candidate_raw:
            baseline_lost.append({"alias": alias, "test_index": test_index})
        if candidate_model and not baseline_model:
            model_added.append({"alias": alias, "test_index": test_index})
        if baseline_model and not candidate_model:
            model_lost.append({"alias": alias, "test_index": test_index})

    result = {
        "schema": "arc2-v9-public-training-postscore-v1",
        "track": "ARC2",
        "labels_read_after_prediction_freeze": True,
        "exposure": "exposure_unknown",
        "prediction_sha256": observed["predictions"],
        "baseline_sha256": observed["baseline"],
        "cohort_sha256": observed["cohort"],
        "training_challenges_sha256": observed["training_challenges"],
        "training_solutions_sha256": observed["training_solutions"],
        "task_id_mapping_used_only_by_offline_scorer": True,
        "task_count": len(aliases),
        "candidate": candidate_metrics,
        "baseline": baseline_metrics,
        "delta_candidate_minus_baseline": deltas,
        "coverage_changes": {
            "candidate_added_raw_hits": candidate_added,
            "baseline_lost_raw_hits": baseline_lost,
            "candidate_added_model_only_hits": model_added,
            "baseline_lost_model_only_hits": model_lost,
        },
    }
    write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
