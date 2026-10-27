"""Evaluate leave-one-teacher-out object models against exact v51 answer slots."""
from __future__ import annotations

from collections import Counter
import hashlib
import importlib.util
from itertools import combinations
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
V51_PROBE = EVIDENCE / "ARC2-largest-component-object-v51-probe-20261026.py"
BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v51-largest-component-background-20261026"
OUTPUT = Path(__file__).with_suffix(".json")
LOO_SAMPLE_LIMIT = 128


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _install_single_vote_support(module):
    def candidate_from_models(models, test_input, *, outlier=False):
        if not module._valid_grid(test_input):
            return None, {"fitted_models": len(models), "applicable_models": 0}
        predictions = Counter()
        grids = {}
        applicable = 0
        for model in models:
            output = module._apply(model, test_input, outlier=outlier)
            if output is None:
                continue
            applicable += 1
            key = module._grid_key(output)
            predictions[key] += 1
            grids[key] = output
        if not predictions:
            return None, {"fitted_models": len(models), "applicable_models": 0}
        top_votes = max(predictions.values())
        winners = [key for key, votes in predictions.items() if votes == top_votes]
        candidate = grids[winners[0]] if len(winners) == 1 else None
        return candidate, {
            "fitted_models": len(models),
            "applicable_models": applicable,
            "distinct_predictions": len(predictions),
            "top_votes": top_votes,
        }
    module._candidate_from_models = candidate_from_models


def _candidate(module, teachers, query):
    if len(teachers) < 2:
        return None
    subset_size = min(len(teachers), max(2, len(teachers) - 1))
    subsets = list(combinations(teachers, subset_size))
    predictions = Counter()
    grids = {}
    for subset in subsets:
        model = module.ObjectExtractionCandidate(list(subset))
        methods = (
            ("object", model.candidate),
            ("outlier", model.outlier_candidate),
            ("palette", model.palette_candidate),
        )
        rows = []
        for index, (family, method) in enumerate(methods):
            prediction, record = method(query)
            if not module._valid_grid(prediction) or prediction == query:
                continue
            votes = int(record.get("top_votes", 0))
            applicable = max(1, int(record.get("applicable_models", 0)))
            rows.append((family, prediction, (votes / applicable, votes, -index)))
        if not rows:
            continue
        rows.sort(key=lambda row: row[2], reverse=True)
        best_score = rows[0][2]
        winners = [row for row in rows if row[2] == best_score]
        winner_keys = {module._grid_key(row[1]) for row in winners}
        if len(winner_keys) != 1:
            continue
        key = next(iter(winner_keys))
        predictions[key] += 1
        grids[key] = winners[0][1]
    if not predictions:
        return None
    top_votes = max(predictions.values())
    winners = [key for key, votes in predictions.items() if votes == top_votes]
    if len(winners) != 1:
        return None
    minimum_support = 1 if len(subsets) == 1 else 2
    if top_votes < minimum_support:
        return None
    return grids[winners[0]]


def _run_exact_v51(tasks: dict):
    with tempfile.TemporaryDirectory(prefix="arc2-v51-teacher-loo-v63-") as temp_name:
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
            raise RuntimeError(f"exact v51 failed ({process.returncode}): {detail}")
        submission_path = output_dir / "submission.json"
        audit_path = output_dir / "submission_audit.json"
        predictions = json.loads(submission_path.read_text(encoding="utf-8"))
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        hashes = {"submission": _sha(submission_path), "audit": _sha(audit_path)}
    return predictions, audit, runtime, hashes


def _exact(row, target):
    return row["attempt_1"] == target or row["attempt_2"] == target


def _even_sample(rows, limit):
    if len(rows) <= limit:
        return rows
    if limit == 1:
        return [rows[len(rows) // 2]]
    indices = [round(index * (len(rows) - 1) / (limit - 1)) for index in range(limit)]
    return [rows[index] for index in indices]


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("arc2_v51_largest_background_probe", V51_PROBE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the v51 background rule")
    v51_probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v51_probe)
    from 接続.ARC2 import 物体抽出候補 as module
    module._background = v51_probe._largest_component_background
    _install_single_vote_support(module)

    loo_all = []
    loo_eligible = 0
    for path in sorted(SOURCE_ROOT.glob("*.json")):
        training = json.loads(path.read_text(encoding="utf-8")).get("train", [])
        if len(training) < 3:
            continue
        for held_index, held in enumerate(training):
            teachers = [pair for index, pair in enumerate(training) if index != held_index]
            loo_eligible += 1
            candidate = _candidate(module, teachers, held["input"])
            if candidate is not None and candidate != held["input"]:
                loo_all.append({"path": path, "index": held_index, "teachers": teachers,
                                "input": held["input"], "candidate": candidate})
    loo_records = _even_sample(loo_all, LOO_SAMPLE_LIMIT)

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    public_tasks, public_candidates = {}, {}
    for task_index, (task_id, task) in enumerate(challenge.items()):
        candidates = {}
        for pair_index, pair in enumerate(task.get("test", [])):
            candidate = _candidate(module, task.get("train", []), pair["input"])
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
    print(json.dumps({"phase": "exact_v51_paired_runtime_started", "loo_proposals_all": len(loo_all),
                      "loo_proposals_sampled": len(loo_records), "public_candidate_tasks": len(public_tasks),
                      "runtime_tasks": len(runtime_tasks)}), flush=True)
    predictions, audit, runtime, output_hashes = _run_exact_v51(runtime_tasks)

    loo = Counter()
    for index, row in enumerate(loo_records):
        baseline = predictions[f"loo_{index:05d}"][0]
        target = json.loads(row["path"].read_text(encoding="utf-8"))["train"][row["index"]]["output"]
        before = _exact(baseline, target)
        candidate = row["candidate"]
        usable = baseline["attempt_2"] == baseline["attempt_1"] and candidate != baseline["attempt_1"]
        after = before or (usable and candidate == target)
        loo["v51_exact"] += before
        loo["candidate_exact_outputs"] += candidate == target
        loo["candidate_usable_when_v51_slot_duplicate"] += usable
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
            public["candidate_usable_when_v51_slot_duplicate"] += usable
            public["newly_correct_examples"] += after and not before
            public["regressions"] += before and not after
            task_results[task_id]["before"].append(before)
            task_results[task_id]["after"].append(after)
    public["baseline_exact_tasks"] = sum(all(row["before"]) for row in task_results.values())
    public["combined_exact_tasks"] = sum(all(row["after"]) for row in task_results.values())
    public["newly_correct_tasks"] = sum(all(row["after"]) and not all(row["before"]) for row in task_results.values())
    public["regressed_tasks"] = sum(all(row["before"]) and not all(row["after"]) for row in task_results.values())

    report = {
        "schema": "arc2-object-teacher-leave-one-out-v63-exact-paired-v1",
        "policy": "fit object/outlier/palette models on near-complete teacher subsets, omitting one teacher at a time (or using the full two-teacher set); accept only a unique output supported by at least two subsets when multiple subsets exist",
        "loo_eligible_folds": loo_eligible,
        "loo_candidate_proposal_folds_all": len(loo_all),
        "loo_candidate_proposal_folds_sampled": len(loo_records),
        "loo_sample_policy": "evenly spaced deterministic sample from sorted training task/fold proposals",
        "loo_exact_v51_bundle_paired_sample": dict(loo),
        "challenge_tasks": len(challenge),
        "challenge_examples": sum(len(task.get("test", [])) for task in challenge.values()),
        "challenge_tasks_with_candidates": len(public_tasks),
        "challenge_examples_with_candidates": sum(len(indices) for _, indices in public_candidates.values()),
        "challenge_candidate_tasks_exact_v51_bundle_paired": dict(public),
        "exact_v51_runtime_tasks": len(runtime_tasks),
        "exact_v51_runtime_seconds": round(runtime, 3),
        "exact_v51_fallback_count": audit.get("fallback_count"),
        "exact_v51_temporary_output_sha256": output_hashes,
        "candidate_runtime_received_heldout_outputs": False,
        "exact_v51_runtime_received_heldout_or_challenge_targets": False,
        "all_targets_read_after_both_prediction_sets": True,
        "per_task_ids_grids_or_targets_saved": False,
        "temporary_outputs_and_payload_removed": True,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "v51_background_probe": _sha(V51_PROBE),
            "challenge_inputs": _sha(CHALLENGE),
            "v51_build_manifest": _sha(BUILD / "build-manifest.json"),
            "object_module": _sha(ROOT / "接続/ARC2/物体抽出候補.py"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
