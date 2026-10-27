"""Score the completed v19 bundle runtime against v16 and matched v18."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v16-periodic-tiling-20261026/full-runtime-output-20261026/submission.json"
BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v19-local-context-second-20261026"
CURRENT = BUILD / "full-runtime/submission.json"
AUDIT = BUILD / "full-runtime/submission_audit.json"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _row_correct(row, target):
    return any(row.get(name) == target for name in ("attempt_1", "attempt_2"))


def _summary(rows, targets, inputs):
    exact_examples = nonidentity_examples = distinct_pairs = 0
    task_rows = {}
    for task_id, output_rows in rows.items():
        targets_for_task = targets[task_id]
        inputs_for_task = inputs[task_id]
        correctness = []
        for index, row in enumerate(output_rows):
            target = targets_for_task[index]
            exact = _row_correct(row, target)
            exact_examples += exact
            nonidentity_examples += exact and target != inputs_for_task[index]
            distinct_pairs += row.get("attempt_1") != row.get("attempt_2")
            correctness.append(exact)
        task_rows[task_id] = all(correctness)
    return {
        "exact_tasks": sum(task_rows.values()),
        "exact_examples": exact_examples,
        "nonidentity_exact_tasks": sum(
            task_rows[task_id]
            and all(targets[task_id][i] != inputs[task_id][i] for i in range(len(inputs[task_id])))
            for task_id in task_rows
        ),
        "nonidentity_exact_examples": nonidentity_examples,
        "distinct_attempt_pairs": distinct_pairs,
    }, task_rows


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    if not CURRENT.is_file() or not AUDIT.is_file():
        raise SystemExit("v19 full-runtime submission and audit are required")
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2.複合幾何変換候補 import CompositeGeometryCandidate
    from 接続.ARC2.局所近傍変換候補 import LocalCellContextCandidate
    from 接続.ARC2.単純変換候補 import valid_grid

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    current = json.loads(CURRENT.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    if audit.get("challenge_sha256") != _sha(CHALLENGE):
        raise SystemExit("challenge SHA mismatch")

    # Reconstruct the already scored v18 composition, then generate the local
    # context candidate from train/input only. No target is read in this pass.
    v18 = json.loads(json.dumps(baseline))
    local_predictions = {}
    for task_id, task in challenge.items():
        geometry = CompositeGeometryCandidate(task["train"])
        local = LocalCellContextCandidate(task["train"])
        local_predictions[task_id] = []
        for index, pair in enumerate(task["test"]):
            primary = baseline[task_id][index]["attempt_1"]
            geometry_prediction, _ = geometry.候補(pair["input"], {})
            if valid_grid(geometry_prediction) and geometry_prediction != primary:
                v18[task_id][index]["attempt_2"] = geometry_prediction
            local_prediction, _ = local.候補(pair["input"], {})
            local_predictions[task_id].append(local_prediction)

    # Public held-out outputs are read only after all predictions are complete.
    targets = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in SOURCE_ROOT.glob("*.json")
    }
    inputs = {
        task_id: [pair["input"] for pair in task["test"]]
        for task_id, task in challenge.items()
    }
    score_v16, tasks_v16 = _summary(baseline, targets, inputs)
    score_v18, tasks_v18 = _summary(v18, targets, inputs)
    score_v19, tasks_v19 = _summary(current, targets, inputs)

    changed_attempt_1 = changed_attempt_2 = 0
    local_fits = local_distinct = local_selected = 0
    for task_id, task in challenge.items():
        for index, pair in enumerate(task["test"]):
            base_row = v18[task_id][index]
            current_row = current[task_id][index]
            changed_attempt_1 += base_row.get("attempt_1") != current_row.get("attempt_1")
            changed_attempt_2 += base_row.get("attempt_2") != current_row.get("attempt_2")
            candidate = local_predictions[task_id][index]
            local_fits += candidate is not None
            distinct = candidate is not None and candidate not in (base_row.get("attempt_1"), base_row.get("attempt_2"))
            local_distinct += distinct
            local_selected += distinct and current_row.get("attempt_2") == candidate

    score = {
        "schema": "arc2-v19-local-context-full-runtime-scorecard-v1",
        "runtime_tasks": audit.get("tasks"),
        "runtime_examples": audit.get("test_examples"),
        "runtime_seconds": audit.get("seconds"),
        "fallback_count": audit.get("fallback_count"),
        "score_by_version": {"v16": score_v16, "v18_matched_composition": score_v18, "v19_full_runtime": score_v19},
        "delta_v19_minus_v18": {
            "exact_tasks": score_v19["exact_tasks"] - score_v18["exact_tasks"],
            "exact_examples": score_v19["exact_examples"] - score_v18["exact_examples"],
            "nonidentity_exact_tasks": score_v19["nonidentity_exact_tasks"] - score_v18["nonidentity_exact_tasks"],
            "nonidentity_exact_examples": score_v19["nonidentity_exact_examples"] - score_v18["nonidentity_exact_examples"],
            "newly_correct_tasks": sum(tasks_v19[t] and not tasks_v18[t] for t in tasks_v18),
            "regressed_tasks": sum(tasks_v18[t] and not tasks_v19[t] for t in tasks_v18),
            "attempt_1_changed_examples": changed_attempt_1,
            "attempt_2_changed_examples": changed_attempt_2,
            "distinct_local_candidates": local_distinct,
            "local_candidates_selected": local_selected,
        },
        "local_candidate_fits": local_fits,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "runtime_received_targets": False,
        "targets_read_only_after_full_runtime_and_candidate_predictions": True,
        "per_task_predictions_or_targets_saved": False,
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "challenge": _sha(CHALLENGE),
            "baseline_submission": _sha(BASELINE),
            "current_submission": _sha(CURRENT),
            "current_audit": _sha(AUDIT),
            "build_manifest": _sha(BUILD / "build-manifest.json"),
            "local_context_module": _sha(ROOT / "接続/ARC2/局所近傍変換候補.py"),
            "adapter": _sha(ROOT / "接続/ARC2/Kaggle提出.py"),
        },
    }
    OUTPUT.write_text(json.dumps(score, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(score, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
