"""Evaluate object extraction with a label-free duplicate-slot policy."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v19-local-context-second-20261026/full-runtime/submission.json"
OBJECT_RUNNER = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-object-extraction-v19-probe-20261026.py"
OUTPUT = Path(__file__).with_suffix(".json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_candidate_module():
    spec = importlib.util.spec_from_file_location("arc2_object_extraction_probe", OBJECT_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load object extraction probe")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    module = load_candidate_module()
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    generated = {}
    for task_id, task in sorted(challenge.items()):
        models = module._fit(task["train"])
        rows = []
        for pair in task["test"]:
            counts = Counter()
            grids = {}
            for model in models:
                candidate = module._predict(model, pair["input"])
                if candidate is not None:
                    key = module._key(candidate)
                    counts[key] += 1
                    grids[key] = candidate
            top_count = max(counts.values(), default=0)
            winners = [key for key, count in counts.items() if count == top_count]
            top = grids[winners[0]] if top_count >= 2 and len(winners) == 1 else None
            rows.append({"top": top, "votes": top_count, "predictions": len(counts)})
        generated[task_id] = rows

    # Only the evaluator reads public outputs, after predictions are frozen.
    targets = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in SOURCE_ROOT.glob("*.json")
    }
    baseline_by_task = defaultdict(list)
    after_by_task = defaultdict(list)
    baseline_exact_examples = new_exact = regressions = candidate_examples = distinct_candidates = 0
    duplicate_slots = selected = raw_candidate_exact = 0
    for task_id, rows in generated.items():
        for index, row in enumerate(rows):
            base = baseline[task_id][index]
            target = targets[task_id][index]
            before = base["attempt_1"] == target or base["attempt_2"] == target
            baseline_exact_examples += before
            baseline_by_task[task_id].append(before)
            top = row["top"]
            candidate_examples += top is not None
            candidate_diff = top is not None and top not in (base["attempt_1"], base["attempt_2"])
            distinct_candidates += candidate_diff
            raw_candidate_exact += top == target if top is not None else False
            duplicate = base["attempt_1"] == base["attempt_2"]
            duplicate_slots += duplicate
            updated = dict(base)
            # Runtime policy: fill a duplicate second slot only. It uses inputs
            # and current predictions, never challenge target correctness.
            use = bool(candidate_diff and duplicate)
            if use:
                updated["attempt_2"] = top
                selected += 1
            after = updated["attempt_1"] == target or updated["attempt_2"] == target
            new_exact += after and not before
            regressions += before and not after
            after_by_task[task_id].append(after)
    baseline_exact_tasks = sum(all(values) for values in baseline_by_task.values())
    combined_exact_tasks = sum(all(values) for values in after_by_task.values())
    newly_correct_tasks = sum(
        all(after_by_task[task_id]) and not all(baseline_by_task[task_id])
        for task_id in baseline_by_task
    )
    regressed_tasks = sum(
        all(baseline_by_task[task_id]) and not all(after_by_task[task_id])
        for task_id in baseline_by_task
    )
    report = {
        "schema": "arc2-object-extraction-v19-deployable-probe-v1",
        "challenge_tasks": len(challenge),
        "challenge_examples": sum(len(rows) for rows in generated.values()),
        "selection_policy": "support >= 2 unique top; replace attempt_2 only when it duplicates attempt_1",
        "baseline_v19": {
            "exact_tasks": baseline_exact_tasks,
            "exact_examples": baseline_exact_examples,
        },
        "candidate_examples": candidate_examples,
        "candidates_distinct_from_both_attempts": distinct_candidates,
        "raw_candidate_exact_examples": raw_candidate_exact,
        "baseline_duplicate_slots": duplicate_slots,
        "selected_examples": selected,
        "combined": {
            "exact_tasks": combined_exact_tasks,
            "exact_examples": baseline_exact_examples + new_exact - regressions,
            "newly_correct_tasks": newly_correct_tasks,
            "newly_correct_examples": new_exact,
            "regressed_tasks": regressed_tasks,
            "regressed_examples": regressions,
        },
        "runtime_received_challenge_targets": False,
        "targets_read_only_after_all_candidate_generation": True,
        "per_task_predictions_or_targets_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": sha(Path(__file__)),
            "object_extraction_probe": sha(OBJECT_RUNNER),
            "challenge": sha(CHALLENGE),
            "baseline_v19": sha(BASELINE),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
