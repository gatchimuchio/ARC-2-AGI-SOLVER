"""Test confidence thresholds and replacement of a distinct v51 second answer."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "運用/証拠/ARC26-UNIFIED"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
V51_PROBE = EVIDENCE / "ARC2-largest-component-object-v51-probe-20261026.py"
V61_RUNNER = EVIDENCE / "ARC2-object-teacher-pair-consensus-v61-exact-paired-20261026.py"
BASELINE_REPORT = EVIDENCE / "ARC2-v51-largest-component-full-runtime-evaluation-20261026.json"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _candidate_with_support(module, teachers, query):
    if len(teachers) < 2:
        return None, 0, 0
    subsets = list(combinations(teachers, 2))
    predictions, grids = Counter(), {}
    for subset in subsets:
        model = module.ObjectExtractionCandidate(list(subset))
        methods = (model.candidate, model.outlier_candidate, model.palette_candidate)
        rows = []
        for index, method in enumerate(methods):
            prediction, record = method(query)
            if not module._valid_grid(prediction) or prediction == query:
                continue
            votes = int(record.get("top_votes", 0))
            applicable = max(1, int(record.get("applicable_models", 0)))
            rows.append((prediction, (votes / applicable, votes, -index)))
        if not rows:
            continue
        rows.sort(key=lambda row: row[1], reverse=True)
        best = rows[0][1]
        winners = [row for row in rows if row[1] == best]
        winner_keys = {module._grid_key(row[0]) for row in winners}
        if len(winner_keys) != 1:
            continue
        key = next(iter(winner_keys))
        predictions[key] += 1
        grids[key] = winners[0][0]
    if not predictions:
        return None, 0, len(subsets)
    top = max(predictions.values())
    winners = [key for key, votes in predictions.items() if votes == top]
    if len(winners) != 1 or top < 2:
        return None, top, len(subsets)
    return grids[winners[0]], top, len(subsets)


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    probe = _load("arc2_v51_object_probe", V51_PROBE)
    harness = _load("arc2_v61_harness", V61_RUNNER)
    from 接続.ARC2 import 物体抽出候補 as module
    module._background = probe._largest_component_background
    harness._install_single_vote_support(module)

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    tasks, candidate_rows = {}, {}
    support_histogram = Counter()
    for task_index, (task_id, task) in enumerate(challenge.items()):
        rows = {}
        for pair_index, pair in enumerate(task.get("test", [])):
            candidate, support, total = _candidate_with_support(module, task.get("train", []), pair["input"])
            support_histogram[f"{support}/{total}"] += candidate is not None
            if candidate is not None:
                rows[pair_index] = {"grid": candidate, "support": support, "total": total}
        if rows:
            key = f"public_{task_index:04d}"
            tasks[key] = {"train": task.get("train", []),
                          "test": [{"input": pair["input"]} for pair in task.get("test", [])]}
            candidate_rows[key] = (task_id, rows)
    if not tasks:
        raise RuntimeError("no v61 consensus candidate tasks")

    hashes = {
        "runner": _sha(Path(__file__)),
        "v51_probe": _sha(V51_PROBE),
        "v61_harness": _sha(V61_RUNNER),
        "object_module": _sha(ROOT / "接続/ARC2/物体抽出候補.py"),
        "challenge": _sha(CHALLENGE),
        "v51_baseline_report": _sha(BASELINE_REPORT),
    }
    preds, _audit, runtime_seconds, output_hashes = harness._run_exact_v51(tasks)
    base_score = json.loads(BASELINE_REPORT.read_text(encoding="utf-8"))["v51_full_challenge_score"]
    policies = {"duplicate_only_support2": Counter(), "replace_attempt2_support2": Counter(),
                "replace_attempt2_support3": Counter(), "replace_attempt2_ratio50": Counter()}
    task_status = {name: {} for name in policies}
    for key, (task_id, candidates) in candidate_rows.items():
        task = challenge[task_id]
        labels = json.loads((ROOT / "入力/公式ソース/ARC-AGI-2/data/training" / f"{task_id}.json").read_text(encoding="utf-8"))
        for name in policies:
            task_status[name][key] = {"before": [], "after": []}
        for index, _pair in enumerate(task.get("test", [])):
            row = preds[key][index]
            target = labels["test"][index]["output"]
            before = row["attempt_1"] == target or row["attempt_2"] == target
            entry = candidates.get(index)
            policies["duplicate_only_support2"]["proposals"] += entry is not None
            for name in policies:
                selected = None
                if entry is not None:
                    if name == "duplicate_only_support2" and row["attempt_1"] == row["attempt_2"]:
                        selected = entry["grid"]
                    elif name == "replace_attempt2_support2":
                        selected = entry["grid"]
                    elif name == "replace_attempt2_support3" and entry["support"] >= 3:
                        selected = entry["grid"]
                    elif name == "replace_attempt2_ratio50" and entry["support"] / entry["total"] >= 0.5:
                        selected = entry["grid"]
                after = row["attempt_1"] == target or (selected == target if selected is not None else row["attempt_2"] == target)
                metrics = policies[name]
                metrics["examples_in_candidate_tasks"] += 1
                metrics["baseline_exact_examples"] += before
                metrics["candidate_selected"] += selected is not None
                metrics["candidate_exact_outputs"] += selected == target if selected is not None else 0
                metrics["newly_correct_examples"] += after and not before
                metrics["regressions"] += before and not after
                task_status[name][key]["before"].append(before)
                task_status[name][key]["after"].append(after)
    for name, metrics in policies.items():
        metrics["candidate_tasks"] = len(task_status[name])
        metrics["baseline_exact_tasks_in_region"] = sum(all(row["before"]) for row in task_status[name].values())
        metrics["combined_exact_tasks_in_region"] = sum(all(row["after"]) for row in task_status[name].values())
        metrics["newly_correct_tasks"] = sum(all(row["after"]) and not all(row["before"]) for row in task_status[name].values())
        metrics["regressed_tasks"] = sum(all(row["before"]) and not all(row["after"]) for row in task_status[name].values())
        metrics["paired_full_local_estimate"] = {
            "exact_tasks": base_score["exact_tasks"] + metrics["newly_correct_tasks"] - metrics["regressed_tasks"],
            "exact_examples": base_score["exact_examples"] + metrics["newly_correct_examples"] - metrics["regressions"],
        }

    report = {
        "schema": "arc2-object-teacher-consensus-slot-policy-v73-v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_policy": "support counts are independent two-teacher subsets; v61 already requires a unique winner and support >=2",
        "support_histogram": dict(support_histogram),
        "candidate_tasks": len(tasks),
        "candidate_examples": sum(len(row[1]) for row in candidate_rows.values()),
        "policies": {key: dict(value) for key, value in policies.items()},
        "exact_v51_runtime_tasks": len(tasks),
        "exact_v51_runtime_seconds": round(runtime_seconds, 3),
        "exact_v51_temporary_output_sha256": output_hashes,
        "targets_passed_to_runtime": False,
        "targets_read_after_prediction_completion": True,
        "task_ids_grids_or_targets_saved": False,
        "temporary_predictions_and_payload_removed": True,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": hashes,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
