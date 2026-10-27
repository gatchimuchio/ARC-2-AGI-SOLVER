"""Aggregate-only challenge probe for a two-teacher D4 candidate."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v16-periodic-tiling-20261026/full-runtime-output-20261026/submission.json"
LOO_RUNNER = Path(__file__).with_name("ARC2-grid-d4-support2-attempt2-paired-LOO-20261026.py")
OUTPUT = Path(__file__).with_suffix(".json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(rows_by_task, labels):
    tasks = examples = distinct = 0
    for task_id, rows in rows_by_task.items():
        outcomes = []
        for row, target in zip(rows, labels[task_id], strict=True):
            outcomes.append(target in (row["attempt_1"], row["attempt_2"]))
            distinct += row["attempt_1"] != row["attempt_2"]
        tasks += all(outcomes)
        examples += sum(outcomes)
    return {"correct_tasks": tasks, "correct_examples": examples, "distinct_attempt_pairs": distinct}


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2.複合幾何変換候補 import CompositeGeometryCandidate

    spec = importlib.util.spec_from_file_location("d4_support2_loo", LOO_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load support2 model")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    candidate_class = module.格子D4二例教材

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    candidate_predictions, composite_predictions = {}, {}
    candidate_fit = candidate_distinct = composite_selected = candidate_selected = 0
    for task_id, task in challenge.items():
        candidate_model = candidate_class(task["train"])
        composite_model = CompositeGeometryCandidate(task["train"])
        candidate_predictions[task_id], composite_predictions[task_id] = [], []
        for index, pair in enumerate(task["test"]):
            candidate, _ = candidate_model.候補(pair["input"], {})
            composite, _ = composite_model.候補(pair["input"], {})
            candidate_fit += candidate is not None
            candidate_distinct += candidate is not None and candidate != baseline[task_id][index]["attempt_1"]
            candidate_predictions[task_id].append(candidate)
            composite_predictions[task_id].append(composite)

    v16_rows = {task_id: [dict(row) for row in rows] for task_id, rows in baseline.items()}
    v18_rows = {task_id: [dict(row) for row in rows] for task_id, rows in baseline.items()}
    combined_rows = {task_id: [dict(row) for row in rows] for task_id, rows in baseline.items()}
    for task_id, rows in baseline.items():
        for index, row in enumerate(rows):
            first = row["attempt_1"]
            if row["attempt_2"] == first:
                composite = composite_predictions[task_id][index]
                if composite is not None and composite != first:
                    v18_rows[task_id][index]["attempt_2"] = composite
                    composite_selected += 1
            combined_rows[task_id][index]["attempt_2"] = v18_rows[task_id][index]["attempt_2"]
            candidate = candidate_predictions[task_id][index]
            if combined_rows[task_id][index]["attempt_2"] == first and candidate is not None and candidate != first:
                combined_rows[task_id][index]["attempt_2"] = candidate
                candidate_selected += 1

    # Read public targets only after every candidate output has been fixed.
    labels = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in TRAINING.glob("*.json")
    }
    v16_score, v18_score, combined_score = (score(rows, labels) for rows in (v16_rows, v18_rows, combined_rows))
    report = {
        "schema": "arc2-grid-d4-support2-attempt2-challenge-probe-v1",
        "challenge_tasks": len(challenge),
        "test_examples": sum(len(task["test"]) for task in challenge.values()),
        "candidate_generation_completed_before_labels_loaded": True,
        "runtime_received_targets": False,
        "labels_source": "public ARC-AGI-2 training outputs; offline scoring only",
        "baseline_submission_sha256": sha(BASELINE),
        "challenge_sha256": sha(CHALLENGE),
        "d4_module_sha256": sha(ROOT / "接続/ARC2/格子D4教材.py"),
        "support2_candidate_fit_examples": candidate_fit,
        "support2_candidate_distinct_from_primary": candidate_distinct,
        "v18_selected_attempt2": composite_selected,
        "support2_selected_after_v18_priority": candidate_selected,
        "v16_baseline": v16_score,
        "v18_reconstructed": v18_score,
        "combined_candidate": combined_score,
        "delta_vs_v18_tasks": combined_score["correct_tasks"] - v18_score["correct_tasks"],
        "delta_vs_v18_examples": combined_score["correct_examples"] - v18_score["correct_examples"],
        "official_score": "UNKNOWN_NOT_SUBMITTED",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "support2_candidate_fit_examples", "support2_candidate_distinct_from_primary",
        "v18_selected_attempt2", "support2_selected_after_v18_priority",
        "v16_baseline", "v18_reconstructed", "combined_candidate", "delta_vs_v18_tasks", "delta_vs_v18_examples"
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
