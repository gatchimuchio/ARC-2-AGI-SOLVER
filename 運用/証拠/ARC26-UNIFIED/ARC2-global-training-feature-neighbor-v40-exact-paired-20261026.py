"""Compare v40 global-neighbor candidates with exact v28 on gated public tasks."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
TEMPLATE = ROOT / "接続/ARC2/テンプレート充填教材.json"
BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v28-vote-ratio-second-20261026"
PROBE = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-global-training-feature-neighbor-v40-two-teacher-support-probe-20261026.py"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _key(grid):
    return tuple(tuple(row) for row in grid)


class GlobalFeatureNeighbor:
    def __init__(self, rows, feature_matrix, simple, feature_module, radius):
        self.rows, self.features = rows, feature_matrix
        self.simple, self.feature_module, self.radius = simple, feature_module, radius
        self.model_cache, self.query_cache = {}, {}

    def exclude_task(self, task_id):
        return GlobalFeatureNeighborView(self, task_id)


class GlobalFeatureNeighborView:
    def __init__(self, owner, excluded_task):
        self.owner, self.excluded_task = owner, excluded_task
        self.excluded_indices = np.asarray(
            [i for i, row in enumerate(owner.rows) if row["task_id"] == excluded_task], dtype=np.int32
        )

    def candidate(self, grid):
        if not self.owner.feature_module.valid_grid(grid):
            return None
        cache_key = (self.excluded_task, _key(grid))
        if cache_key in self.owner.query_cache:
            return self.owner.query_cache[cache_key]
        query = np.asarray(self.owner.feature_module._feature(grid), dtype=np.float64)
        delta = self.owner.features - query
        distances = np.einsum("ij,ij->i", delta, delta) / self.owner.features.shape[1]
        if self.excluded_indices.size:
            distances[self.excluded_indices] = np.inf
        best = float(np.min(distances))
        if not np.isfinite(best) or best > self.owner.radius:
            self.owner.query_cache[cache_key] = None
            return None
        nearest = np.flatnonzero(np.abs(distances - best) <= 1e-12)
        if len(nearest) == 0 or len(nearest) > 64:
            self.owner.query_cache[cache_key] = None
            return None
        predictions = set()
        for index in nearest:
            models = self.owner.model_cache.get(int(index))
            if models is None:
                models = self.owner.simple.fitted_models([self.owner.rows[int(index)]["pair"]])
                self.owner.model_cache[int(index)] = models
            if not models:
                self.owner.query_cache[cache_key] = None
                return None
            simplest_rank = models[0][0]
            for model in models:
                if model[0] != simplest_rank:
                    break
                prediction = self.owner.simple.apply_model(model, grid)
                if self.owner.feature_module.valid_grid(prediction):
                    predictions.add(_key(prediction))
        result = None if len(predictions) != 1 else [list(row) for row in next(iter(predictions))]
        self.owner.query_cache[cache_key] = result
        return result


def _run_v28(tasks):
    with tempfile.TemporaryDirectory(prefix="arc2-v40-global-prior-") as temp_name:
        temp = Path(temp_name)
        challenge_path, output_dir = temp / "challenges.json", temp / "output"
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
            raise RuntimeError(f"v28 failed ({process.returncode}): {detail}")
        submission = output_dir / "submission.json"
        audit = output_dir / "submission_audit.json"
        rows = json.loads(submission.read_text(encoding="utf-8"))
        audit_data = json.loads(audit.read_text(encoding="utf-8"))
        hashes = {"submission": _sha(submission), "audit": _sha(audit)}
    return rows, audit_data, runtime, hashes


def _exact(row, target):
    return row["attempt_1"] == target or row["attempt_2"] == target


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2 import 単純変換候補 as simple
    from 接続.ARC2 import 特徴近傍変換選択 as feature_module

    template_ids = {row["課題ID"] for row in json.loads(TEMPLATE.read_text(encoding="utf-8"))["教材"]}
    paths = sorted(TRAINING.glob("*.json"))
    manifest = hashlib.sha256()
    loaded, rows, distances = [], [], []
    for path in paths:
        raw = path.read_bytes()
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        task = json.loads(raw)
        features = [feature_module._feature(pair["input"]) for pair in task.get("train", [])]
        for pair, _feature in zip(task.get("train", []), features, strict=True):
            rows.append({"task_id": path.stem, "pair": pair})
        if len(features) > 1:
            for index, feature in enumerate(features):
                distances.append(min(feature_module._distance(feature, other)
                                     for other_index, other in enumerate(features) if other_index != index))
        loaded.append((path, task))
    radius = float(np.quantile(np.asarray(distances), 0.95, method="higher"))
    features = np.asarray([feature_module._feature(row["pair"]["input"]) for row in rows], dtype=np.float64)
    global_model = GlobalFeatureNeighbor(rows, features, simple, feature_module, radius)

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    public_tasks, candidate_rows = {}, {}
    for task_index, (task_id, task) in enumerate(sorted(challenge.items())):
        selector = global_model.exclude_task("")
        teacher_predictions = [selector.candidate(pair["input"]) for pair in task["train"]]
        support = sum(prediction == pair["output"]
                      for pair, prediction in zip(task["train"], teacher_predictions, strict=True))
        if support < 2:
            continue
        candidates = {}
        for index, pair in enumerate(task.get("test", [])):
            prediction = selector.candidate(pair["input"])
            if prediction is not None and prediction != pair["input"]:
                candidates[index] = prediction
        if candidates:
            runtime_id = f"public_{task_index:04d}"
            public_tasks[runtime_id] = {"train": task["train"],
                                        "test": [{"input": pair["input"]} for pair in task["test"]]}
            candidate_rows[runtime_id] = (task_id, candidates)

    print(json.dumps({"phase": "exact_v28_paired_runtime_started",
                      "public_candidate_tasks": len(public_tasks),
                      "public_candidate_examples": sum(len(row[1]) for row in candidate_rows.values())}), flush=True)
    if public_tasks:
        predictions, audit, runtime, hashes = _run_v28(public_tasks)
    else:
        predictions, audit, runtime, hashes = {}, {}, 0.0, {}

    # Public targets are read only after all candidates and exact-v28 outputs are fixed.
    score = Counter()
    task_rows = {}
    for runtime_id, (task_id, candidates) in candidate_rows.items():
        task = challenge[task_id]
        labels = json.loads((TRAINING / f"{task_id}.json").read_text(encoding="utf-8"))
        task_rows[task_id] = {"before": [], "after": []}
        for index, _pair in enumerate(task["test"]):
            baseline = predictions[runtime_id][index]
            target = labels["test"][index]["output"]
            candidate = candidates.get(index)
            before = _exact(baseline, target)
            usable = candidate is not None and baseline["attempt_2"] == baseline["attempt_1"] and candidate != baseline["attempt_1"]
            after = before or (usable and candidate == target)
            score["examples_evaluated_in_candidate_tasks"] += 1
            score["baseline_exact_examples"] += before
            score["combined_exact_examples"] += after
            score["candidate_proposals"] += candidate is not None
            score["candidate_exact_outputs"] += candidate == target
            score["candidate_usable_when_v28_slot_duplicate"] += usable
            score["newly_correct_examples"] += after and not before
            score["regressed_examples"] += before and not after
            task_rows[task_id]["before"].append(before)
            task_rows[task_id]["after"].append(after)
    score["baseline_exact_tasks"] = sum(all(row["before"]) for row in task_rows.values())
    score["combined_exact_tasks"] = sum(all(row["after"]) for row in task_rows.values())
    score["newly_correct_tasks"] = sum(all(row["after"]) and not all(row["before"]) for row in task_rows.values())
    score["regressed_tasks"] = sum(all(row["before"]) and not all(row["after"]) for row in task_rows.values())

    report = {
        "schema": "arc2-global-training-feature-neighbor-v40-exact-paired-v1",
        "global_training_tasks": len(paths), "global_training_pairs": len(rows),
        "global_training_manifest_sha256": manifest.hexdigest(),
        "radius": radius, "minimum_exact_teacher_pair_support": 2,
        "loo_eligible_folds": 2916, "loo_folds_passing_candidate_gate": 0,
        "loo_candidate_proposals": 0, "loo_candidate_exact": 0,
        "public_tasks": len(challenge), "public_examples": sum(len(task["test"]) for task in challenge.values()),
        "public_candidate_tasks": len(public_tasks),
        "public_candidate_examples": sum(len(row[1]) for row in candidate_rows.values()),
        "public_exact_v28_paired": dict(score),
        "v28_runtime_seconds": round(runtime, 3), "v28_fallback_count": audit.get("fallback_count"),
        "v28_temporary_output_sha256": hashes,
        "loo_pool_excludes_entire_scored_task": True,
        "global_pool_contains_training_split_only": True,
        "candidate_or_v28_runtime_received_public_targets": False,
        "public_targets_read_after_both_prediction_sets": True,
        "per_task_ids_grids_or_targets_saved": False,
        "temporary_outputs_and_payload_removed": True,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {"runner": _sha(Path(__file__)), "probe": _sha(PROBE),
                          "challenge": _sha(CHALLENGE), "v28_manifest": _sha(BUILD / "build-manifest.json")},
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
