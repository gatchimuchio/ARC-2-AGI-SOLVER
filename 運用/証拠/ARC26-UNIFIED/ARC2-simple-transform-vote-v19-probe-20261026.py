"""Aggregate-only probe of unanimous and plurality fitted simple transforms."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v19-local-context-second-20261026/full-runtime/submission.json"
OUTPUT = Path(__file__).with_suffix(".json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2.単純変換候補 import predict_pool

    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    started = time.monotonic()
    generated: dict[str, list[tuple[list[list[int]] | None, int, int, int]]] = {}
    for task_id, task in sorted(challenge.items()):
        rows = []
        for pair in task["test"]:
            models, predictions, _, _ = predict_pool(task["train"], pair["input"])
            counts = predictions
            if not counts:
                rows.append((None, 0, 0, len(models)))
                continue
            top_count = max(counts.values())
            winners = [grid for grid, count in counts.items() if count == top_count]
            top = [list(row) for row in winners[0]] if len(winners) == 1 else None
            rows.append((top, top_count, sum(counts.values()), len(models)))
        generated[task_id] = rows

    # Public outputs are read only after every test prediction has been frozen.
    targets = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in SOURCE_ROOT.glob("*.json")
    }
    thresholds: dict[str, float] = {
        "top_support2": -1.0,
        "plurality_50": 0.50,
        "supermajority_75": 0.75,
        "supermajority_90": 0.90,
        "unanimous": 1.0,
    }
    rows_by_policy: dict[str, list[tuple[str, bool, bool, bool]]] = defaultdict(list)
    generated_examples = 0
    total_models = 0
    top_ties = 0
    for task_id, rows in generated.items():
        for index, (top, count, prediction_count, model_count) in enumerate(rows):
            generated_examples += 1
            total_models += model_count
            base = baseline[task_id][index]
            target = targets[task_id][index]
            before = base["attempt_1"] == target or base["attempt_2"] == target
            if count and top is None:
                top_ties += 1
            for policy, threshold in thresholds.items():
                if policy == "top_support2":
                    use = top is not None and count >= 2
                else:
                    use = top is not None and prediction_count > 0 and count / prediction_count >= threshold
                updated = dict(base)
                if use and top != base["attempt_1"]:
                    updated["attempt_2"] = top
                after = updated["attempt_1"] == target or updated["attempt_2"] == target
                rows_by_policy[policy].append((task_id, before, after, bool(use and top != base["attempt_1"])))

    baseline_task_exact = {}
    for task_id in generated:
        task_rows = [row for row in rows_by_policy["unanimous"] if row[0] == task_id]
        baseline_task_exact[task_id] = all(row[1] for row in task_rows)
    baseline_exact_examples = sum(row[1] for row in rows_by_policy["unanimous"])
    baseline_exact_tasks = sum(baseline_task_exact.values())
    results = {}
    for policy, rows in rows_by_policy.items():
        after_tasks: dict[str, list[bool]] = defaultdict(list)
        before_tasks: dict[str, list[bool]] = defaultdict(list)
        for task_id, before, after, changed in rows:
            before_tasks[task_id].append(before)
            after_tasks[task_id].append(after)
        results[policy] = {
            "selected_distinct_examples": sum(row[3] for row in rows),
            "combined_exact_examples": sum(row[2] for row in rows),
            "newly_correct_examples": sum(after and not before for _, before, after, _ in rows),
            "regressed_examples": sum(before and not after for _, before, after, _ in rows),
            "baseline_exact_tasks": sum(all(values) for values in before_tasks.values()),
            "combined_exact_tasks": sum(all(values) for values in after_tasks.values()),
            "newly_correct_tasks": sum(all(after_tasks[t]) and not all(before_tasks[t]) for t in before_tasks),
            "regressed_tasks": sum(all(before_tasks[t]) and not all(after_tasks[t]) for t in before_tasks),
        }
    report = {
        "schema": "arc2-simple-transform-vote-v19-probe-v1",
        "challenge_tasks": len(challenge),
        "challenge_examples": generated_examples,
        "baseline_v19": {
            "exact_tasks": baseline_exact_tasks,
            "exact_examples": baseline_exact_examples,
        },
        "fitted_model_total": total_models,
        "test_examples_with_unique_top_prediction": sum(top is not None for rows in generated.values() for top, _, _, _ in rows),
        "test_examples_with_tied_top": top_ties,
        "policies": results,
        "runtime_received_challenge_targets": False,
        "targets_read_only_after_all_predictions": True,
        "per_task_predictions_or_targets_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "candidate_seconds": round(time.monotonic() - started, 3),
        "source_sha256": {
            "runner": sha(Path(__file__)),
            "challenge": sha(CHALLENGE),
            "baseline_v19": sha(BASELINE),
            "simple_transform_candidate": sha(ROOT / "接続/ARC2/単純変換候補.py"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"baseline_v19": report["baseline_v19"], "models": total_models, "unique_top": report["test_examples_with_unique_top_prediction"], "policies": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
