"""Aggregate-only offline analysis of the v16/v18 challenge fallback strata."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v16-periodic-tiling-20261026/full-runtime-output-20261026/submission.json"
OUTPUT = Path(__file__).with_suffix(".json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bucket(values: list[int]) -> str:
    count = len(set(values))
    return "1-2 colors" if count <= 2 else "3-4 colors" if count <= 4 else "5+ colors"


def task_shape_profile(task):
    pairs = task["train"]
    same = [
        (len(pair["input"]), len(pair["input"][0])) ==
        (len(pair["output"]), len(pair["output"][0]))
        for pair in pairs
    ]
    return "all_preserve" if all(same) else "all_change" if not any(same) else "mixed"


def example_bucket(task, pair):
    grid = pair["input"]
    height, width = len(grid), len(grid[0])
    cells = height * width
    size = "<=25 cells" if cells <= 25 else "26-100 cells" if cells <= 100 else ">100 cells"
    shape = "square" if height == width else "wide" if width > height else "tall"
    return {
        "teacher_count": "1" if len(task["train"]) == 1 else "2" if len(task["train"]) == 2 else "3" if len(task["train"]) == 3 else "4+",
        "teacher_shape_profile": task_shape_profile(task),
        "test_size": size,
        "test_shape": shape,
        "test_palette": bucket([color for row in grid for color in row]),
    }


def summarize(groups):
    result = {}
    for dimension, values in groups.items():
        result[dimension] = {}
        for name, rows in sorted(values.items()):
            result[dimension][name] = {
                "examples": len(rows),
                "exact_attempt_pairs": sum(row["exact"] for row in rows),
                "primary_equals_input": sum(row["primary_identity"] for row in rows),
                "distinct_attempt_pairs": sum(row["distinct"] for row in rows),
                "exact_rate": round(sum(row["exact"] for row in rows) / len(rows), 6) if rows else None,
            }
    return result


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    # These are offline labels only; the frozen runtime predictions already exist.
    labels = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in TRAINING.glob("*.json")
    }
    groups = defaultdict(lambda: defaultdict(list))
    baseline_exact_tasks = baseline_exact_examples = fallback_examples = distinct_pairs = 0
    task_results = []
    for task_id, task in challenge.items():
        targets = labels[task_id]
        row_results = []
        for index, pair in enumerate(task["test"]):
            row = baseline[task_id][index]
            exact = targets[index] in (row["attempt_1"], row["attempt_2"])
            row_results.append(exact)
            baseline_exact_examples += exact
            fallback_examples += row["attempt_1"] == pair["input"]
            distinct_pairs += row["attempt_1"] != row["attempt_2"]
            features = example_bucket(task, pair)
            score = {
                "exact": exact,
                "primary_identity": row["attempt_1"] == pair["input"],
                "distinct": row["attempt_1"] != row["attempt_2"],
            }
            for dimension, value in features.items():
                groups[dimension][value].append(score)
        baseline_exact_tasks += all(row_results)
        task_results.append(all(row_results))

    for name, results in zip(("all tasks",), (task_results,), strict=True):
        baseline_exact_tasks = sum(results)
    report = {
        "schema": "arc2-v18-fallback-strata-scorecard-v1",
        "challenge_tasks": len(challenge),
        "challenge_examples": sum(len(task["test"]) for task in challenge.values()),
        "baseline_source": "complete v16 local runtime output; v18 composition is separately recorded in its matched scorecard",
        "labels_source": "public ARC-AGI-2 training files; offline analysis only",
        "baseline_exact_tasks": baseline_exact_tasks,
        "baseline_exact_examples": baseline_exact_examples,
        "primary_equals_input_examples": fallback_examples,
        "distinct_attempt_pairs": distinct_pairs,
        "strata": summarize(groups),
        "per_task_ids_or_grids_saved": False,
        "runtime_received_targets": False,
        "challenge_sha256": sha(CHALLENGE),
        "baseline_submission_sha256": sha(BASELINE),
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    compact = {key: report[key] for key in ("challenge_tasks", "challenge_examples", "baseline_exact_tasks", "baseline_exact_examples", "primary_equals_input_examples", "distinct_attempt_pairs")}
    compact["strata"] = report["strata"]
    print(json.dumps(compact, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
