"""Aggregate-only challenge probe for cropped periodic D4 as attempt 2."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v16-periodic-tiling-20261026/full-runtime-output-20261026/submission.json"
OUTPUT = Path(__file__).with_name(Path(__file__).stem + "-production-module.json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(rows_by_task, labels):
    correct_tasks = correct_examples = distinct_pairs = 0
    for task_id, rows in rows_by_task.items():
        target_rows = labels[task_id]
        outcomes = []
        for row, target in zip(rows, target_rows, strict=True):
            outcomes.append(target in (row["attempt_1"], row["attempt_2"]))
            distinct_pairs += row["attempt_1"] != row["attempt_2"]
        correct_examples += sum(outcomes)
        correct_tasks += all(outcomes)
    return {"correct_tasks": correct_tasks, "correct_examples": correct_examples, "distinct_attempt_pairs": distinct_pairs}


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2.複合crop周期タイルD4候補 import 複合crop周期タイルD4候補
    from 接続.ARC2.複合幾何変換候補 import CompositeGeometryCandidate

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    composite_predictions = {}
    cropped_predictions = {}
    candidate_fit_examples = candidate_distinct_examples = 0
    composite_fit_examples = 0
    # Materialize every candidate before opening public training outputs.
    for task_id, task in challenge.items():
        composite = CompositeGeometryCandidate(task["train"])
        cropped = 複合crop周期タイルD4候補(task["train"])
        composite_predictions[task_id] = []
        cropped_predictions[task_id] = []
        for pair in task["test"]:
            composite_candidate, _ = composite.候補(pair["input"], {})
            cropped_candidate, _ = cropped.候補(pair["input"])
            composite_fit_examples += composite_candidate is not None
            candidate_fit_examples += cropped_candidate is not None
            base_first = baseline[task_id][len(composite_predictions[task_id])]["attempt_1"]
            candidate_distinct_examples += cropped_candidate is not None and cropped_candidate != base_first
            composite_predictions[task_id].append(composite_candidate)
            cropped_predictions[task_id].append(cropped_candidate)

    v16_rows = {task_id: [dict(row) for row in rows] for task_id, rows in baseline.items()}
    v18_rows = {task_id: [dict(row) for row in rows] for task_id, rows in baseline.items()}
    v19_rows = {task_id: [dict(row) for row in rows] for task_id, rows in baseline.items()}
    composite_selected = cropped_selected = 0
    for task_id, rows in baseline.items():
        for index, row in enumerate(rows):
            first = row["attempt_1"]
            if row["attempt_2"] == first:
                composite = composite_predictions[task_id][index]
                if composite is not None and composite != first:
                    v18_rows[task_id][index]["attempt_2"] = composite
                    composite_selected += 1
                v19_rows[task_id][index]["attempt_2"] = v18_rows[task_id][index]["attempt_2"]
                candidate = cropped_predictions[task_id][index]
                if candidate is not None and candidate != first and v19_rows[task_id][index]["attempt_2"] == first:
                    v19_rows[task_id][index]["attempt_2"] = candidate
                    cropped_selected += 1

    # Offline labels are read only after all candidate predictions are fixed.
    labels = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in TRAINING.glob("*.json")
    }
    if not set(challenge).issubset(labels):
        raise RuntimeError("challenge task missing public offline label")
    v16_score, v18_score, v19_score = (score(rows, labels) for rows in (v16_rows, v18_rows, v19_rows))
    base_ok = {task_id: all(target in (row["attempt_1"], row["attempt_2"]) for row, target in zip(v18_rows[task_id], labels[task_id], strict=True)) for task_id in v18_rows}
    new_ok = {task_id: all(target in (row["attempt_1"], row["attempt_2"]) for row, target in zip(v19_rows[task_id], labels[task_id], strict=True)) for task_id in v19_rows}
    report = {
        "schema": "arc2-cropped-periodic-d4-challenge-probe-v1",
        "challenge_tasks": len(challenge),
        "challenge_test_examples": sum(len(task["test"]) for task in challenge.values()),
        "candidate_generation_completed_before_labels_loaded": True,
        "runtime_received_targets": False,
        "labels_source": "public ARC-AGI-2 training outputs; offline scorecard only",
        "baseline_submission_sha256": sha(BASELINE),
        "challenge_sha256": sha(CHALLENGE),
        "cropped_periodic_d4_module_sha256": sha(ROOT / "接続/ARC2/複合crop周期タイルD4候補.py"),
        "composite_geometry_module_sha256": sha(ROOT / "接続/ARC2/複合幾何変換候補.py"),
        "cropped_periodic_d4_fit_examples": candidate_fit_examples,
        "cropped_periodic_d4_distinct_from_primary_examples": candidate_distinct_examples,
        "composite_geometry_fit_examples": composite_fit_examples,
        "composite_geometry_selected_attempt2": composite_selected,
        "cropped_periodic_d4_selected_attempt2_after_composite_priority": cropped_selected,
        "v16_baseline": v16_score,
        "v18_reconstructed": v18_score,
        "v19_combined_candidate": v19_score,
        "delta_v19_vs_v18_tasks": v19_score["correct_tasks"] - v18_score["correct_tasks"],
        "delta_v19_vs_v18_examples": v19_score["correct_examples"] - v18_score["correct_examples"],
        "newly_correct_tasks_vs_v18": sum(new_ok[task_id] and not base_ok[task_id] for task_id in base_ok),
        "regressed_tasks_vs_v18": sum(base_ok[task_id] and not new_ok[task_id] for task_id in base_ok),
        "official_competition_score": "UNKNOWN_NOT_SUBMITTED",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "cropped_periodic_d4_fit_examples", "cropped_periodic_d4_distinct_from_primary_examples",
        "composite_geometry_selected_attempt2", "cropped_periodic_d4_selected_attempt2_after_composite_priority",
        "v16_baseline", "v18_reconstructed", "v19_combined_candidate", "delta_v19_vs_v18_tasks",
        "delta_v19_vs_v18_examples", "newly_correct_tasks_vs_v18", "regressed_tasks_vs_v18"
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
