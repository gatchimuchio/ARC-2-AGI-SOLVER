"""Score the orthogonal-context candidate against exact v28 on proposal inputs."""
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
PROBE = EVIDENCE / "ARC2-orthogonal-cell-context-v36-probe-20261026.py"
BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v28-vote-ratio-second-20261026"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_exact_v28(tasks: dict):
    with tempfile.TemporaryDirectory(prefix="arc2-v28-orthogonal-context-") as temp_name:
        temp = Path(temp_name)
        challenge_path = temp / "challenges.json"
        output_dir = temp / "output"
        stdout_path = temp / "solver.stdout.log"
        stderr_path = temp / "solver.stderr.log"
        challenge_path.write_text(json.dumps(tasks, ensure_ascii=False), encoding="utf-8")
        environment = {**os.environ, "PYTHONUTF8": "1", "ARC2_PAYLOAD_ROOT": str(temp / "payload")}
        start = time.perf_counter()
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                [sys.executable, str(BUILD / "solve.py"), "--challenges", str(challenge_path), "--output-dir", str(output_dir)],
                cwd=ROOT, env=environment, stdout=stdout, stderr=stderr,
            )
            last_report = 0
            while process.poll() is None:
                elapsed = int(time.perf_counter() - start)
                if elapsed - last_report >= 60:
                    print(json.dumps({"exact_v28_runtime_seconds": elapsed}), flush=True)
                    last_report = elapsed
                time.sleep(5)
        runtime = time.perf_counter() - start
        if process.returncode:
            detail = stderr_path.read_text(encoding="utf-8", errors="replace")[-4000:]
            raise RuntimeError(f"exact v28 bundle failed ({process.returncode}): {detail}")
        submission_path = output_dir / "submission.json"
        audit_path = output_dir / "submission_audit.json"
        predictions = json.loads(submission_path.read_text(encoding="utf-8"))
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        submission_sha = _sha(submission_path)
        audit_sha = _sha(audit_path)
    return predictions, audit, runtime, submission_sha, audit_sha


def _exact(row, target):
    return row["attempt_1"] == target or row["attempt_2"] == target


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("arc2_v36_orthogonal_probe", PROBE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load orthogonal-context probe")
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)

    loo_records = []
    eligible_folds = 0
    for path in sorted(SOURCE_ROOT.glob("*.json")):
        training = json.loads(path.read_text(encoding="utf-8")).get("train", [])
        if len(training) < 3:
            continue
        for held_index, held in enumerate(training):
            teachers = [pair for index, pair in enumerate(training) if index != held_index]
            eligible_folds += 1
            proposed, _ = probe.candidate(teachers, held["input"])
            if proposed is not None and proposed != held["input"]:
                loo_records.append({
                    "path": path,
                    "held_index": held_index,
                    "teachers": teachers,
                    "input": held["input"],
                    "candidate": proposed,
                })

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    public_candidate_indices = {}
    public_runtime_tasks = {}
    for task_index, (task_id, task) in enumerate(challenge.items()):
        indices = {}
        for pair_index, pair in enumerate(task.get("test", [])):
            proposed, _ = probe.candidate(task.get("train", []), pair["input"])
            if proposed is not None and proposed != pair["input"]:
                indices[pair_index] = proposed
        if indices:
            runtime_id = f"public_{task_index:04d}"
            public_candidate_indices[runtime_id] = (task_id, indices)
            public_runtime_tasks[runtime_id] = {
                "train": task.get("train", []),
                "test": [{"input": pair["input"]} for pair in task.get("test", [])],
            }

    runtime_tasks = {
        f"loo_{index:05d}": {
            "train": record["teachers"],
            "test": [{"input": record["input"]}],
        }
        for index, record in enumerate(loo_records)
    }
    runtime_tasks.update(public_runtime_tasks)
    if not runtime_tasks:
        raise RuntimeError("candidate scan produced no exact-bundle inputs")
    print(json.dumps({
        "phase": "exact_v28_paired_runtime_started",
        "loo_proposal_folds": len(loo_records),
        "public_candidate_tasks": len(public_runtime_tasks),
        "runtime_tasks": len(runtime_tasks),
    }), flush=True)
    predictions, audit, runtime, submission_sha, audit_sha = _run_exact_v28(runtime_tasks)

    # Read every held-out/public target only after candidate and exact-v28 predictions are frozen.
    loo = Counter()
    for index, record in enumerate(loo_records):
        runtime_id = f"loo_{index:05d}"
        baseline = predictions[runtime_id][0]
        target = json.loads(record["path"].read_text(encoding="utf-8"))["train"][record["held_index"]]["output"]
        proposed = record["candidate"]
        before = _exact(baseline, target)
        usable = baseline["attempt_2"] == baseline["attempt_1"] and proposed != baseline["attempt_1"]
        after = before or (usable and proposed == target)
        loo["v28_exact"] += before
        loo["candidate_exact_outputs"] += proposed == target
        loo["candidate_usable_when_v28_slot_duplicate"] += usable
        loo["newly_correct"] += after and not before
        loo["regressions"] += before and not after
        loo["v28_attempt2_distinct"] += baseline["attempt_2"] != baseline["attempt_1"]

    public = Counter()
    task_status = {}
    for runtime_id, (task_id, candidate_by_index) in public_candidate_indices.items():
        task = challenge[task_id]
        rows = predictions[runtime_id]
        label_data = json.loads((SOURCE_ROOT / f"{task_id}.json").read_text(encoding="utf-8"))
        task_status.setdefault(task_id, {"before": [], "after": []})
        for pair_index, pair in enumerate(task.get("test", [])):
            baseline = rows[pair_index]
            target = label_data["test"][pair_index]["output"]
            proposed = candidate_by_index.get(pair_index)
            before = _exact(baseline, target)
            usable = proposed is not None and baseline["attempt_2"] == baseline["attempt_1"] and proposed != baseline["attempt_1"]
            after = before or (usable and proposed == target)
            public["examples_evaluated_in_candidate_tasks"] += 1
            public["baseline_exact_examples"] += before
            public["combined_exact_examples"] += after
            public["candidate_proposals"] += proposed is not None
            public["candidate_exact_outputs"] += proposed == target
            public["candidate_usable_when_v28_slot_duplicate"] += usable
            public["newly_correct_examples"] += after and not before
            public["regressed_examples"] += before and not after
            task_status[task_id]["before"].append(before)
            task_status[task_id]["after"].append(after)
    public["baseline_exact_tasks"] = sum(all(row["before"]) for row in task_status.values())
    public["combined_exact_tasks"] = sum(all(row["after"]) for row in task_status.values())
    public["newly_correct_tasks"] = sum(all(row["after"]) and not all(row["before"]) for row in task_status.values())
    public["regressed_tasks"] = sum(all(row["before"]) and not all(row["after"]) for row in task_status.values())

    report = {
        "schema": "arc2-orthogonal-cell-context-v36-exact-paired-v1",
        "loo_eligible_folds": eligible_folds,
        "loo_candidate_proposal_folds": len(loo_records),
        "loo_exact_v28_bundle_paired": dict(loo),
        "challenge_tasks": len(challenge),
        "challenge_examples": sum(len(task.get("test", [])) for task in challenge.values()),
        "challenge_tasks_with_candidates": len(public_runtime_tasks),
        "challenge_examples_with_candidates": sum(len(indices) for _, indices in public_candidate_indices.values()),
        "challenge_candidate_tasks_exact_v28_bundle_paired": dict(public),
        "exact_v28_runtime_tasks": len(runtime_tasks),
        "exact_v28_runtime_seconds": round(runtime, 3),
        "exact_v28_fallback_count": audit.get("fallback_count"),
        "exact_v28_temporary_submission_sha256": submission_sha,
        "exact_v28_temporary_audit_sha256": audit_sha,
        "candidate_runtime_received_heldout_outputs": False,
        "exact_v28_runtime_received_heldout_or_challenge_targets": False,
        "all_targets_read_after_both_candidate_and_exact_v28_predictions": True,
        "per_task_ids_grids_predictions_or_targets_saved": False,
        "temporary_outputs_and_payload_removed": True,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "candidate_probe": _sha(PROBE),
            "challenge_inputs": _sha(CHALLENGE),
            "v28_build_manifest": _sha(BUILD / "build-manifest.json"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
