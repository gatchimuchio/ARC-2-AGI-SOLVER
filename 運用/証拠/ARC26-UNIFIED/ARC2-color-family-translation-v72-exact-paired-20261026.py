"""Pair v70 proposals with exact v51 outputs; score labels only after prediction."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "運用/証拠/ARC26-UNIFIED"
TRAIN = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
SCREEN = EVIDENCE / "ARC2-color-family-translation-v72-screen-20261026.py"
SCREEN_REPORT = SCREEN.with_suffix(".json")
BASELINE_REPORT = EVIDENCE / "ARC2-v51-largest-component-full-runtime-evaluation-20261026.json"
V61_RUNNER = EVIDENCE / "ARC2-object-teacher-pair-consensus-v61-exact-paired-20261026.py"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    screen = _load("arc2_v72_screen", SCREEN)
    baseline = _load("arc2_v61_runtime_harness", V61_RUNNER)

    loo_rows = []
    loo_eligible = 0
    for path in sorted(TRAIN.glob("*.json")):
        examples = json.loads(path.read_text(encoding="utf-8")).get("train", [])
        if len(examples) < 3:
            continue
        for held_index, held in enumerate(examples):
            teachers = [pair for index, pair in enumerate(examples) if index != held_index]
            loo_eligible += 1
            candidate = screen._fit(teachers, held["input"])
            if candidate is not None and candidate != held["input"]:
                loo_rows.append({"path": path, "index": held_index, "candidate": candidate})

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    runtime_tasks, public_candidates = {}, {}
    for task_index, (task_id, task) in enumerate(challenge.items()):
        candidates = {}
        for pair_index, pair in enumerate(task.get("test", [])):
            candidate = screen._fit(task.get("train", []), pair["input"])
            if candidate is not None and candidate != pair["input"]:
                candidates[pair_index] = candidate
        if candidates:
            key = f"public_{task_index:04d}"
            runtime_tasks[key] = {"train": task.get("train", []),
                                  "test": [{"input": pair["input"]} for pair in task.get("test", [])]}
            public_candidates[key] = (task_id, candidates)
    if not runtime_tasks:
        raise RuntimeError("no exact-v51 challenge inputs")

    training_hashes = [(path.name, _sha(path)) for path in sorted(TRAIN.glob("*.json"))]
    source_hashes = {
        "runner": _sha(Path(__file__)),
        "screen_runner": _sha(SCREEN),
        "screen_report": _sha(SCREEN_REPORT),
        "v51_baseline_report": _sha(BASELINE_REPORT),
        "v61_runtime_harness": _sha(V61_RUNNER),
        "challenge": _sha(CHALLENGE),
        "training_files_manifest": hashlib.sha256(
            json.dumps(training_hashes, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }
    source_hashes["v51_solve"] = _sha(baseline.BUILD / "solve.py")
    source_hashes["v51_build_manifest"] = _sha(baseline.BUILD / "build-manifest.json")

    predictions, _audit, runtime_seconds, output_hashes = baseline._run_exact_v51(runtime_tasks)

    loo_correct = 0
    for row in loo_rows:
        target = json.loads(row["path"].read_text(encoding="utf-8"))["train"][row["index"]]["output"]
        loo_correct += row["candidate"] == target

    public = Counter()
    task_results = {}
    for key, (task_id, candidates) in public_candidates.items():
        task = challenge[task_id]
        labels = json.loads((TRAIN / f"{task_id}.json").read_text(encoding="utf-8"))
        task_results[key] = {"before": [], "after": []}
        for pair_index, _pair in enumerate(task.get("test", [])):
            result = predictions[key][pair_index]
            target = labels["test"][pair_index]["output"]
            candidate = candidates.get(pair_index)
            before = baseline._exact(result, target)
            usable = candidate is not None and result["attempt_2"] == result["attempt_1"] and candidate != result["attempt_1"]
            after = before or (usable and candidate == target)
            public["examples_in_candidate_tasks"] += 1
            public["baseline_exact_examples"] += before
            public["combined_exact_examples"] += after
            public["candidate_proposals"] += candidate is not None
            public["candidate_exact_outputs"] += candidate == target
            public["candidate_usable_when_v51_slot_duplicate"] += usable
            public["newly_correct_examples"] += after and not before
            public["regressions"] += before and not after
            task_results[key]["before"].append(before)
            task_results[key]["after"].append(after)
    public["candidate_tasks"] = len(task_results)
    public["baseline_exact_tasks_in_candidate_region"] = sum(all(row["before"]) for row in task_results.values())
    public["combined_exact_tasks_in_candidate_region"] = sum(all(row["after"]) for row in task_results.values())
    public["newly_correct_tasks"] = sum(all(row["after"]) and not all(row["before"]) for row in task_results.values())
    public["regressed_tasks"] = sum(all(row["before"]) and not all(row["after"]) for row in task_results.values())

    baseline_score = json.loads(BASELINE_REPORT.read_text(encoding="utf-8"))["v51_full_challenge_score"]
    report = {
        "schema": "arc2-color-family-translation-v72-exact-paired-v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "policy": "exact v51 prediction on candidate challenge tasks; candidate may fill a duplicate second slot only; all held-out targets read after predictions finish",
        "loo_eligible_folds": loo_eligible,
        "loo_candidate_proposals": len(loo_rows),
        "loo_candidate_correct_examples": loo_correct,
        "challenge_tasks_with_candidates": len(public_candidates),
        "challenge_examples_with_candidates": sum(len(row[1]) for row in public_candidates.values()),
        "challenge_candidate_tasks_exact_v51_bundle_paired": dict(public),
        "exact_v51_runtime_tasks": len(runtime_tasks),
        "exact_v51_runtime_seconds": round(runtime_seconds, 3),
        "exact_v51_temporary_output_sha256": output_hashes,
        "v51_full_challenge_baseline": baseline_score,
        "combined_local_estimate_from_paired_delta": {
            "exact_tasks": baseline_score["exact_tasks"] + public["newly_correct_tasks"] - public["regressed_tasks"],
            "exact_examples": baseline_score["exact_examples"] + public["newly_correct_examples"] - public["regressions"],
            "scope": "paired local estimate; not a full 240-task rerun and not an official Kaggle score",
        },
        "targets_passed_to_runtime": False,
        "targets_read_after_prediction_completion": True,
        "task_ids_grids_or_targets_saved": False,
        "temporary_predictions_and_payload_removed": True,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": source_hashes,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
