"""Compare global prior candidates with exact v28 baseline outputs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
TEMPLATE = ROOT / "接続/ARC2/テンプレート充填教材.json"
OUTPUT = Path(__file__).with_suffix(".json")
V28_BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v28-vote-ratio-second-20261026"
V28_FULL_REPORT = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-v28-full-runtime-evaluation-20261026.json"


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _key(grid):
    return tuple(tuple(row) for row in grid)


class GlobalFeatureNeighbor:
    def __init__(self, rows, feature_matrix, simple, feature_module, radius):
        self.rows = rows
        self.features = feature_matrix
        self.simple = simple
        self.feature_module = feature_module
        self.radius = radius
        self.model_cache = {}
        self.query_cache = {}

    def exclude_task(self, task_id):
        return GlobalFeatureNeighborView(self, task_id)


class GlobalFeatureNeighborView:
    def __init__(self, owner, excluded_task):
        self.owner = owner
        self.excluded_task = excluded_task
        self.excluded_indices = np.asarray(
            [i for i, row in enumerate(owner.rows) if row["task_id"] == excluded_task],
            dtype=np.int32,
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
        # A single analogous example is not enough to identify a transform.
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
        if len(predictions) != 1:
            self.owner.query_cache[cache_key] = None
            return None
        result = [list(row) for row in next(iter(predictions))]
        self.owner.query_cache[cache_key] = result
        return result



def _run_bundle(build, tasks):
    if not tasks:
        return {}, {"fallback_count": 0}
    with tempfile.TemporaryDirectory(prefix="arc2-v28-global-prior-") as temp_name:
        temp = Path(temp_name)
        challenge_path = temp / "challenges.json"
        output_dir = temp / "output"
        challenge_path.write_text(json.dumps(tasks, ensure_ascii=False), encoding="utf-8")
        process = subprocess.run(
            [sys.executable, str(build / "solve.py"), "--challenges", str(challenge_path), "--output-dir", str(output_dir)],
            cwd=ROOT,
            env={**os.environ, "PYTHONUTF8": "1", "ARC2_PAYLOAD_ROOT": str(temp / "payload")},
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900, check=False,
        )
        if process.returncode:
            raise RuntimeError(f"{build.name} failed: {process.stderr[-4000:]}")
        predictions = json.loads((output_dir / "submission.json").read_text(encoding="utf-8"))
        audit = json.loads((output_dir / "submission_audit.json").read_text(encoding="utf-8"))
    return predictions, audit

def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2 import 単純変換候補 as simple
    from 接続.ARC2 import 特徴近傍変換選択 as feature_module

    source_ids = {
        row["課題ID"]
        for row in json.loads(TEMPLATE.read_text(encoding="utf-8"))["教材"]
    }
    paths = sorted(TRAINING.glob("*.json"))
    manifest = hashlib.sha256()
    loaded = []
    rows = []
    per_task_indices = {}
    within_task_distances = []
    for path in paths:
        raw = path.read_bytes()
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        task = json.loads(raw)
        features = [feature_module._feature(pair["input"]) for pair in task.get("train", [])]
        indices = []
        for pair, feature in zip(task.get("train", []), features, strict=True):
            indices.append(len(rows))
            rows.append({"task_id": path.stem, "pair": pair})
        per_task_indices[path.stem] = indices
        if len(features) > 1:
            for index, feature in enumerate(features):
                distance = min(
                    feature_module._distance(feature, other)
                    for other_index, other in enumerate(features)
                    if other_index != index
                )
                within_task_distances.append(distance)
        loaded.append((path, task))

    radius = float(np.quantile(np.asarray(within_task_distances), 0.95, method="higher"))
    feature_matrix = np.asarray(
        [feature_module._feature(row["pair"]["input"]) for row in rows],
        dtype=np.float64,
    )
    global_model = GlobalFeatureNeighbor(rows, feature_matrix, simple, feature_module, radius)

    loo_eligible = loo_gated_folds = loo_proposals = 0
    loo_records = []
    for path, task in loaded:
        if path.stem in source_ids:
            continue
        pairs = task.get("train", [])
        if len(pairs) < 3:
            continue
        loo_eligible += len(pairs)
        selector = global_model.exclude_task(path.stem)
        teacher_predictions = [selector.candidate(pair["input"]) for pair in pairs]
        for held_index, held in enumerate(pairs):
            accepted = all(
                teacher_predictions[index] == pair["output"]
                for index, pair in enumerate(pairs)
                if index != held_index
            )
            if not accepted:
                continue
            loo_gated_folds += 1
            candidate = teacher_predictions[held_index]
            if candidate is None or candidate == held["input"]:
                continue
            loo_proposals += 1
            loo_records.append((path, held_index, candidate))
    # Held-out outputs are first consulted after all global candidates are fixed.
    loo_exact = 0
    for path, held_index, candidate in loo_records:
        target = json.loads(path.read_text(encoding="utf-8"))["train"][held_index]["output"]
        loo_exact += candidate == target

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    public_examples = public_gated_tasks = public_proposals = 0
    public_records = []
    changed_tasks = set()
    for task_id, task in sorted(challenge.items()):
        selector = global_model.exclude_task("")
        teacher_predictions = [selector.candidate(pair["input"]) for pair in task["train"]]
        accepted = all(
            prediction == pair["output"]
            for pair, prediction in zip(task["train"], teacher_predictions, strict=True)
        )
        if not accepted:
            continue
        public_gated_tasks += 1
        for index, pair in enumerate(task["test"]):
            public_examples += 1
            candidate = selector.candidate(pair["input"])
            if candidate is not None and candidate != pair["input"]:
                public_proposals += 1
                public_records.append((task_id, index, candidate))
                changed_tasks.add(task_id)
    selected = {
        task_id: {
            "train": challenge[task_id]["train"],
            "test": [{"input": pair["input"]} for pair in challenge[task_id]["test"]],
        }
        for task_id in sorted(changed_tasks)
    }
    v28_predictions, v28_audit = _run_bundle(V28_BUILD, selected)

    # Public test targets are read only after exact v28 outputs and all global candidates exist.
    public_exact = v28_changed_exact = potential_safe_gains = 0
    public_changed_correct = public_changed_wrong = 0
    v28_subset_exact_examples = v28_subset_exact_tasks = 0
    v34_subset_exact_examples = v34_subset_exact_tasks = 0
    changed_records = {(task_id, index): candidate for task_id, index, candidate in public_records}
    public_targets = {
        task_id: json.loads((TRAINING / f"{task_id}.json").read_text(encoding="utf-8"))["test"]
        for task_id in selected
    }
    for task_id, result_rows in v28_predictions.items():
        candidate_rows = []
        targets = public_targets[task_id]
        for index, row in enumerate(result_rows):
            target = targets[index]["output"]
            candidate = changed_records.get((task_id, index))
            base_correct = row["attempt_1"] == target or row["attempt_2"] == target
            if candidate is not None:
                candidate_exact = candidate == target
                public_exact += candidate_exact
                v28_changed_exact += base_correct
                public_changed_correct += candidate_exact and base_correct
                public_changed_wrong += base_correct and not candidate_exact
                if candidate_exact and not base_correct and row["attempt_2"] == row["attempt_1"]:
                    potential_safe_gains += 1
                if row["attempt_2"] == row["attempt_1"]:
                    row = {**row, "attempt_2": candidate}
            candidate_rows.append(row)
            v28_subset_exact_examples += base_correct
        v28_task_correct = all(
            row["attempt_1"] == targets[index]["output"] or row["attempt_2"] == targets[index]["output"]
            for index, row in enumerate(result_rows)
        )
        v34_task_correct = all(
            row["attempt_1"] == targets[index]["output"] or row["attempt_2"] == targets[index]["output"]
            for index, row in enumerate(candidate_rows)
        )
        v28_subset_exact_tasks += v28_task_correct
        v34_subset_exact_tasks += v34_task_correct
        v34_subset_exact_examples += sum(
            row["attempt_1"] == targets[index]["output"] or row["attempt_2"] == targets[index]["output"]
            for index, row in enumerate(candidate_rows)
        )
    v28_full_score = json.loads(V28_FULL_REPORT.read_text(encoding="utf-8"))["v28_full_runtime"]
    projected_v34_full_score = {
        "exact_tasks": v28_full_score["exact_tasks"] + v34_subset_exact_tasks - v28_subset_exact_tasks,
        "exact_examples": v28_full_score["exact_examples"] + v34_subset_exact_examples - v28_subset_exact_examples,
    }

    report = {
        "schema": "arc2-global-training-feature-neighbor-v34-exact-baseline-probe-v1",
        "minimum_nearest_training_examples": 1,
        "training_tasks": len(paths),
        "training_pairs": len(rows),
        "training_manifest_sha256": manifest.hexdigest(),
        "radius_method": "95th percentile of each training example's nearest same-task input-feature distance; inputs only",
        "radius": radius,
        "loo": {
            "eligible_folds": loo_eligible,
            "folds_passing_training_only_global_candidate_gate": loo_gated_folds,
            "folds_with_distinct_candidate": loo_proposals,
            "candidate_exact": loo_exact,
        },
        "public_challenge": {
            "tasks": len(challenge),
            "examples": sum(len(task["test"]) for task in challenge.values()),
            "tasks_passing_training_only_global_candidate_gate": public_gated_tasks,
            "eligible_examples_with_candidate": public_proposals,
            "candidate_exact_on_changed_examples": public_exact,
            "v28_exact_on_changed_examples": v28_changed_exact,
            "candidate_already_correct_in_v28": public_changed_correct,
            "candidate_wrong_where_v28_correct": public_changed_wrong,
            "potential_safe_second_slot_gains": potential_safe_gains,
            "tasks_run_in_exact_v28_bundle": len(selected),
            "examples_run_in_exact_v28_bundle": sum(len(task["test"]) for task in selected.values()),
            "v28_subset_score": {"exact_tasks": v28_subset_exact_tasks, "exact_examples": v28_subset_exact_examples},
            "safe_second_slot_candidate_subset_projection": {"exact_tasks": v34_subset_exact_tasks, "exact_examples": v34_subset_exact_examples},
            "projected_full_v28_score": v28_full_score,
            "projected_full_v34_score": projected_v34_full_score,
            "projected_delta": {"exact_tasks": v34_subset_exact_tasks - v28_subset_exact_tasks, "exact_examples": v34_subset_exact_examples - v28_subset_exact_examples},
            "v28_bundle_fallbacks": v28_audit.get("fallback_count"),
        },
        "global_pool_contains_training_split_only": True,
        "runtime_selector_uses_task_ids": False,
        "loo_pool_excludes_entire_scored_task": True,
        "heldout_output_passed_to_candidate_generation": False,
        "public_test_targets_passed_to_candidate_generation": False,
        "targets_read_after_exact_v28_bundle": True,
        "per_task_ids_grids_and_predictions_written": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "challenge": _sha(CHALLENGE),
            "feature_neighbor": _sha(ROOT / "接続/ARC2/特徴近傍変換選択.py"),
            "simple_transforms": _sha(ROOT / "接続/ARC2/単純変換候補.py"),
            "v28_bundle_manifest": _sha(V28_BUILD / "build-manifest.json"),
            "v28_full_runtime_report": _sha(V28_FULL_REPORT),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
