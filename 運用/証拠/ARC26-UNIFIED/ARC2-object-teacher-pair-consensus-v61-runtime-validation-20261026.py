"""Validate the bundled v61 fallback on only public tasks where it proposes."""
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
V51_PROBE = EVIDENCE / "ARC2-largest-component-object-v51-probe-20261026.py"
BUILD_V51 = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v51-largest-component-background-20261026"
BUILD_V61 = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v61-object-teacher-pair-consensus-20261026"
OUTPUT = Path(__file__).with_suffix(".json")


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
    from itertools import combinations
    predictions = Counter()
    grids = {}
    for subset in combinations(teachers, 2):
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
        winners = [row for row in rows if row[2] == rows[0][2]]
        keys = {module._grid_key(row[1]) for row in winners}
        if len(keys) != 1:
            continue
        key = next(iter(keys))
        predictions[key] += 1
        grids[key] = winners[0][1]
    if not predictions:
        return None
    top = max(predictions.values())
    winners = [key for key, votes in predictions.items() if votes == top]
    if len(winners) != 1 or top < (1 if len(teachers) == 2 else 2):
        return None
    return grids[winners[0]]


def _run_bundle(build: Path, tasks: dict, label: str):
    with tempfile.TemporaryDirectory(prefix=f"arc2-v61-runtime-{label}-") as temp_name:
        temp = Path(temp_name)
        challenge_path = temp / "challenges.json"
        output_dir = temp / "output"
        stdout_path, stderr_path = temp / "solver.stdout.log", temp / "solver.stderr.log"
        challenge_path.write_text(json.dumps(tasks, ensure_ascii=False), encoding="utf-8")
        env = {**os.environ, "PYTHONUTF8": "1", "ARC2_PAYLOAD_ROOT": str(temp / "payload")}
        started = time.perf_counter()
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                [sys.executable, str(build / "solve.py"), "--challenges", str(challenge_path), "--output-dir", str(output_dir)],
                cwd=ROOT, env=env, stdout=stdout, stderr=stderr,
            )
            while process.poll() is None:
                time.sleep(1)
        runtime = time.perf_counter() - started
        if process.returncode:
            detail = stderr_path.read_text(encoding="utf-8", errors="replace")[-4000:]
            raise RuntimeError(f"{label} bundle failed ({process.returncode}): {detail}")
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
    if not (BUILD_V51 / "build-manifest.json").is_file() or not (BUILD_V61 / "build-manifest.json").is_file():
        raise FileNotFoundError("v51 and v61 build manifests are required")
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("arc2_v51_largest_background_probe", V51_PROBE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the v51 background rule")
    v51_probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v51_probe)
    from 接続.ARC2 import 物体抽出候補 as module
    module._background = v51_probe._largest_component_background
    _install_single_vote_support(module)

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    public_tasks, proposed = {}, {}
    for task_index, (task_id, task) in enumerate(challenge.items()):
        candidate_by_index = {}
        for pair_index, pair in enumerate(task.get("test", [])):
            candidate = _candidate(module, task.get("train", []), pair["input"])
            if candidate is not None and candidate != pair["input"]:
                candidate_by_index[pair_index] = candidate
        if candidate_by_index:
            key = f"public_{task_index:04d}"
            public_tasks[key] = {
                "train": task.get("train", []),
                "test": [{"input": pair["input"]} for pair in task.get("test", [])],
            }
            proposed[key] = (task_id, candidate_by_index)
    if not public_tasks:
        raise RuntimeError("no public proposals")
    print(json.dumps({
        "phase": "paired_bundle_runtimes_started",
        "candidate_tasks": len(public_tasks),
        "candidate_examples": sum(len(row[1]) for row in proposed.values()),
    }), flush=True)

    baseline, baseline_audit, baseline_runtime, baseline_hashes = _run_bundle(BUILD_V51, public_tasks, "v51")
    candidate, candidate_audit, candidate_runtime, candidate_hashes = _run_bundle(BUILD_V61, public_tasks, "v61")

    # Challenge targets are opened only after both complete prediction sets exist.
    counts = Counter()
    task_results = {}
    for key, (task_id, candidate_by_index) in proposed.items():
        task = challenge[task_id]
        labels = json.loads((SOURCE_ROOT / f"{task_id}.json").read_text(encoding="utf-8"))
        task_results[key] = {"before": [], "after": []}
        for index, _pair in enumerate(task.get("test", [])):
            base_row = baseline[key][index]
            new_row = candidate[key][index]
            target = labels["test"][index]["output"]
            proposal = candidate_by_index.get(index)
            before = _exact(base_row, target)
            after = _exact(new_row, target)
            usable = (
                proposal is not None
                and base_row["attempt_2"] == base_row["attempt_1"]
                and proposal != base_row["attempt_1"]
            )
            expected_second = proposal if usable else base_row["attempt_2"]
            counts["examples"] += 1
            counts["baseline_exact"] += before
            counts["candidate_exact"] += after
            counts["newly_correct"] += after and not before
            counts["regressions"] += before and not after
            counts["candidate_proposals"] += proposal is not None
            counts["candidate_usable_duplicate_slots"] += usable
            counts["expected_second_matches"] += new_row["attempt_2"] == expected_second
            counts["attempt1_unchanged"] += new_row["attempt_1"] == base_row["attempt_1"]
            counts["attempt2_changed"] += new_row["attempt_2"] != base_row["attempt_2"]
            task_results[key]["before"].append(before)
            task_results[key]["after"].append(after)
    counts["baseline_exact_tasks"] = sum(all(rows["before"]) for rows in task_results.values())
    counts["candidate_exact_tasks"] = sum(all(rows["after"]) for rows in task_results.values())
    counts["newly_correct_tasks"] = sum(
        all(rows["after"]) and not all(rows["before"]) for rows in task_results.values()
    )
    counts["regressed_tasks"] = sum(
        all(rows["before"]) and not all(rows["after"]) for rows in task_results.values()
    )
    report = {
        "schema": "arc2-object-teacher-pair-consensus-v61-runtime-validation-v1",
        "candidate_tasks": len(public_tasks),
        "candidate_examples": sum(len(indices) for _, indices in proposed.values()),
        "paired_public_results": dict(counts),
        "v51_runtime_seconds": round(baseline_runtime, 3),
        "v61_runtime_seconds": round(candidate_runtime, 3),
        "v51_fallback_count": baseline_audit.get("fallback_count"),
        "v61_fallback_count": candidate_audit.get("fallback_count"),
        "v51_temporary_output_sha256": baseline_hashes,
        "v61_temporary_output_sha256": candidate_hashes,
        "challenge_targets_read_after_both_prediction_sets": True,
        "per_task_ids_grids_or_targets_saved": False,
        "temporary_outputs_and_payload_removed": True,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "challenge_inputs": _sha(CHALLENGE),
            "v51_build_manifest": _sha(BUILD_V51 / "build-manifest.json"),
            "v61_build_manifest": _sha(BUILD_V61 / "build-manifest.json"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
