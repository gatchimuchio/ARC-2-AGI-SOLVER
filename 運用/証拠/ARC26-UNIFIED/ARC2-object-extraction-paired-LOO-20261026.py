"""Candidate-only paired LOO for object extraction; aggregate evidence only."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
OBJECT_RUNNER = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-object-extraction-v19-probe-20261026.py"
OUTPUT = Path(__file__).with_suffix(".json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_module():
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
    module = _load_module()
    tasks = []
    training_manifest = []
    for path in sorted(SOURCE_ROOT.glob("*.json")):
        task = json.loads(path.read_text(encoding="utf-8"))
        pairs = task.get("train", [])
        training_manifest.append((path.name, len(pairs), sha(path)))
        if len(pairs) >= 3:
            tasks.append(pairs)
    folds = []
    started = time.monotonic()
    for pairs in tasks:
        for held_index, held in enumerate(pairs):
            teachers = [pair for index, pair in enumerate(pairs) if index != held_index]
            models = module._fit(teachers)
            counts = Counter()
            grids = {}
            for model in models:
                candidate = module._predict(model, held["input"])
                if candidate is not None:
                    key = module._key(candidate)
                    counts[key] += 1
                    grids[key] = candidate
            if counts:
                top_count = max(counts.values())
                winners = [key for key, count in counts.items() if count == top_count]
                top = grids[winners[0]] if len(winners) == 1 else None
                folds.append({
                    "input": held["input"],
                    "target": held["output"],
                    "top": top,
                    "votes": top_count,
                    "applicable": sum(counts.values()),
                    "any": list(grids.values()),
                })
            else:
                folds.append({
                    "input": held["input"], "target": held["output"],
                    "top": None, "votes": 0, "applicable": 0, "any": [],
                })

    # Targets were excluded from candidate fitting; all fold proposals are now frozen.
    policy_results = {}
    policies = ("top_support2", "plurality50", "unanimous")
    for policy in policies:
        exact = selected = gains = regressions = any_exact = 0
        folds_by_task = defaultdict(list)
        task_predictions = defaultdict(list)
        for fold in folds:
            top = fold["top"]
            use = (
                top is not None
                and (
                    (policy == "top_support2" and fold["votes"] >= 2)
                    or (policy == "plurality50" and fold["applicable"] > 0 and fold["votes"] / fold["applicable"] >= 0.5)
                    or (policy == "unanimous" and fold["applicable"] > 0 and fold["votes"] == fold["applicable"])
                )
            )
            before = fold["input"] == fold["target"]
            after = before or (use and top == fold["target"])
            selected += bool(use and top != fold["input"])
            exact += after
            gains += after and not before
            regressions += before and not after
            any_exact += any(grid == fold["target"] for grid in fold["any"])
            # Task grouping is intentionally aggregate-only: task ids are not retained.
            task_predictions[id(fold)] = (before, after)
        policy_results[policy] = {
            "selected_nonidentity_folds": selected,
            "candidate_any_exact_upper_bound": any_exact,
            "identity_baseline_exact_folds": sum(fold["input"] == fold["target"] for fold in folds),
            "combined_exact_folds": exact,
            "newly_correct_folds": gains,
            "regressions": regressions,
        }
    total_folds = sum(len(json.loads(path.read_text(encoding="utf-8")).get("train", []))
                      for path in sorted(SOURCE_ROOT.glob("*.json"))
                      if len(json.loads(path.read_text(encoding="utf-8")).get("train", [])) >= 3)
    total_tasks = len(tasks)
    report = {
        "schema": "arc2-object-extraction-paired-loo-v1",
        "source_training_tasks": len(list(SOURCE_ROOT.glob("*.json"))),
        "eligible_tasks_with_at_least_3_pairs": total_tasks,
        "eligible_folds": total_folds,
        "evaluated_folds": len(folds),
        "candidate_generation_seconds": round(time.monotonic() - started, 3),
        "policies": policy_results,
        "heldout_outputs_passed_to_candidate_generator": False,
        "candidate_predictions_and_targets_saved": False,
        "task_ids_or_grids_saved": False,
        "source_sha256": {
            "runner": sha(Path(__file__)),
            "object_extraction_probe": sha(OBJECT_RUNNER),
            "training_manifest": hashlib.sha256(
                json.dumps(training_manifest, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
