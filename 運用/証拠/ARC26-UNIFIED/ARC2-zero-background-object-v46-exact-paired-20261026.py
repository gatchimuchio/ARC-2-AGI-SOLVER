"""Score the new zero-background object selectors against the exact v28 bundle."""
from __future__ import annotations

from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "運用/証拠/ARC26-UNIFIED"
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
PROBE = EVIDENCE / "ARC2-zero-background-object-v46-probe-20261026.py"
BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v28-vote-ratio-second-20261026"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_exact_v28(tasks: dict):
    with tempfile.TemporaryDirectory(prefix="arc2-v28-zero-background-") as temp_name:
        temp = Path(temp_name)
        challenge_path = temp / "challenges.json"
        output_dir = temp / "output"
        stdout_path, stderr_path = temp / "solver.stdout.log", temp / "solver.stderr.log"
        challenge_path.write_text(json.dumps(tasks, ensure_ascii=False), encoding="utf-8")
        env = {**os.environ, "PYTHONUTF8": "1", "ARC2_PAYLOAD_ROOT": str(temp / "payload")}
        started = time.perf_counter()
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                [sys.executable, str(BUILD / "solve.py"), "--challenges", str(challenge_path), "--output-dir", str(output_dir)],
                cwd=ROOT, env=env, stdout=stdout, stderr=stderr,
            )
            while process.poll() is None:
                time.sleep(1)
        runtime = time.perf_counter() - started
        if process.returncode:
            detail = stderr_path.read_text(encoding="utf-8", errors="replace")[-4000:]
            raise RuntimeError(f"exact v28 failed ({process.returncode}): {detail}")
        submission_path = output_dir / "submission.json"
        audit_path = output_dir / "submission_audit.json"
        predictions = json.loads(submission_path.read_text(encoding="utf-8"))
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        hashes = {"submission": _sha(submission_path), "audit": _sha(audit_path)}
    return predictions, audit, runtime, hashes


def _exact(row, target):
    return row["attempt_1"] == target or row["attempt_2"] == target


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("arc2_v46_zero_background_probe", PROBE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load zero-background probe")
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    from 接続.ARC2 import 物体抽出候補

    物体抽出候補._background = probe._zero_background
    loo_records = []
    eligible = 0
    for path in sorted(SOURCE_ROOT.glob("*.json")):
        training = json.loads(path.read_text(encoding="utf-8")).get("train", [])
        if len(training) < 3:
            continue
        for held_index, held in enumerate(training):
            teachers = [pair for index, pair in enumerate(training) if index != held_index]
            eligible += 1
            candidate = probe._candidate(物体抽出候補, teachers, held["input"])
            if candidate is not None and candidate != held["input"]:
                loo_records.append({"path": path, "index": held_index, "teachers": teachers,
                                    "input": held["input"], "candidate": candidate})

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    public_tasks, public_candidates = {}, {}
    for task_index, (task_id, task) in enumerate(challenge.items()):
        candidates = {}
        for pair_index, pair in enumerate(task.get("test", [])):
            candidate = probe._candidate(物体抽出候補, task.get("train", []), pair["input"])
            if candidate is not None and candidate != pair["input"]:
                candidates[pair_index] = candidate
        if candidates:
            key = f"public_{task_index:04d}"
            public_tasks[key] = {"train": task.get("train", []),
                                 "test": [{"input": pair["input"]} for pair in task.get("test", [])]}
            public_candidates[key] = (task_id, candidates)

    runtime_tasks = {
        f"loo_{index:05d}": {"train": row["teachers"], "test": [{"input": row["input"]}]}
        for index, row in enumerate(loo_records)
    }
    runtime_tasks.update(public_tasks)
    if not runtime_tasks:
        raise RuntimeError("no exact-bundle inputs")
    print(json.dumps({"phase": "exact_v28_paired_runtime_started", "loo_proposals": len(loo_records),
                      "public_candidate_tasks": len(public_tasks), "runtime_tasks": len(runtime_tasks)}), flush=True)
    predictions, audit, runtime, output_hashes = _run_exact_v28(runtime_tasks)

    loo = Counter()
    for index, row in enumerate(loo_records):
        baseline = predictions[f"loo_{index:05d}"][0]
        target = json.loads(row["path"].read_text(encoding="utf-8"))["train"][row["index"]]["output"]
        before = _exact(baseline, target)
        candidate = row["candidate"]
        usable = baseline["attempt_2"] == baseline["attempt_1"] and candidate != baseline["attempt_1"]
        after = before or (usable and candidate == target)
        loo["v28_exact"] += before
        loo["candidate_exact_outputs"] += candidate == target
        loo["candidate_usable_when_v28_slot_duplicate"] += usable
        loo["newly_correct"] += after and not before
        loo["regressions"] += before and not after
    public = Counter()
    task_results = {}
    for key, (task_id, candidate_by_index) in public_candidates.items():
        task = challenge[task_id]
        labels = json.loads((SOURCE_ROOT / f"{task_id}.json").read_text(encoding="utf-8"))
        task_results[task_id] = {"before": [], "after": []}
        for pair_index, _pair in enumerate(task.get("test", [])):
            baseline = predictions[key][pair_index]
            target = labels["test"][pair_index]["output"]
            candidate = candidate_by_index.get(pair_index)
            before = _exact(baseline, target)
            usable = candidate is not None and baseline["attempt_2"] == baseline["attempt_1"] and candidate != baseline["attempt_1"]
            after = before or (usable and candidate == target)
            public["examples_evaluated_in_candidate_tasks"] += 1
            public["baseline_exact_examples"] += before
            public["combined_exact_examples"] += after
            public["candidate_proposals"] += candidate is not None
            public["candidate_exact_outputs"] += candidate == target
            public["candidate_usable_when_v28_slot_duplicate"] += usable
            public["newly_correct_examples"] += after and not before
            public["regressed_examples"] += before and not after
            task_results[task_id]["before"].append(before)
            task_results[task_id]["after"].append(after)
    public["baseline_exact_tasks"] = sum(all(row["before"]) for row in task_results.values())
    public["combined_exact_tasks"] = sum(all(row["after"]) for row in task_results.values())
    public["newly_correct_tasks"] = sum(all(row["after"]) and not all(row["before"]) for row in task_results.values())
    public["regressed_tasks"] = sum(all(row["before"]) and not all(row["after"]) for row in task_results.values())

    report = {
        "schema": "arc2-zero-background-object-v46-exact-paired-v1",
        "loo_eligible_folds": eligible,
        "loo_candidate_proposal_folds": len(loo_records),
        "loo_exact_v28_bundle_paired": dict(loo),
        "challenge_tasks": len(challenge),
        "challenge_examples": sum(len(task.get("test", [])) for task in challenge.values()),
        "challenge_tasks_with_candidates": len(public_tasks),
        "challenge_examples_with_candidates": sum(len(indices) for _, indices in public_candidates.values()),
        "challenge_candidate_tasks_exact_v28_bundle_paired": dict(public),
        "exact_v28_runtime_tasks": len(runtime_tasks),
        "exact_v28_runtime_seconds": round(runtime, 3),
        "exact_v28_fallback_count": audit.get("fallback_count"),
        "exact_v28_temporary_output_sha256": output_hashes,
        "candidate_runtime_received_heldout_outputs": False,
        "exact_v28_runtime_received_heldout_or_challenge_targets": False,
        "all_targets_read_after_both_prediction_sets": True,
        "per_task_ids_grids_predictions_or_targets_saved": False,
        "temporary_outputs_and_payload_removed": True,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {"runner": _sha(Path(__file__)), "candidate_probe": _sha(PROBE),
                          "challenge_inputs": _sha(CHALLENGE), "v28_build_manifest": _sha(BUILD / "build-manifest.json")},
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
