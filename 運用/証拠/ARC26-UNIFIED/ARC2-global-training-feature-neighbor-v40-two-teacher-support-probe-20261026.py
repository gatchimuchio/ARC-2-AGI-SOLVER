"""Probe a global training-only nearest-transform candidate with two exact teacher supports."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
TEMPLATE = ROOT / "接続/ARC2/テンプレート充填教材.json"
OUTPUT = Path(__file__).with_suffix(".json")


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
            accepted = sum(
                teacher_predictions[index] == pair["output"]
                for index, pair in enumerate(pairs)
                if index != held_index
            ) >= 2
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
    for task_id, task in sorted(challenge.items()):
        selector = global_model.exclude_task("")
        teacher_predictions = [selector.candidate(pair["input"]) for pair in task["train"]]
        accepted = sum(
            prediction == pair["output"]
            for pair, prediction in zip(task["train"], teacher_predictions, strict=True)
        ) >= 2
        if not accepted:
            continue
        public_gated_tasks += 1
        for index, pair in enumerate(task["test"]):
            public_examples += 1
            candidate = selector.candidate(pair["input"])
            if candidate is not None and candidate != pair["input"]:
                public_proposals += 1
                public_records.append((task_id, index, candidate))
    # Public test targets are read only after the full input-only scan.
    public_exact = 0
    for task_id, index, candidate in public_records:
        target = json.loads((TRAINING / f"{task_id}.json").read_text(encoding="utf-8"))["test"][index]["output"]
        public_exact += candidate == target

    report = {
        "schema": "arc2-global-training-feature-neighbor-v40-probe-v1",
        "minimum_nearest_training_examples": 1,
        "minimum_exact_teacher_pair_support": 2,
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
            "candidate_exact": public_exact,
        },
        "global_pool_contains_training_split_only": True,
        "runtime_selector_uses_task_ids": False,
        "loo_pool_excludes_entire_scored_task": True,
        "heldout_output_passed_to_candidate_generation": False,
        "public_test_targets_passed_to_candidate_generation": False,
        "per_task_ids_grids_and_predictions_written": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "challenge": _sha(CHALLENGE),
            "feature_neighbor": _sha(ROOT / "接続/ARC2/特徴近傍変換選択.py"),
            "simple_transforms": _sha(ROOT / "接続/ARC2/単純変換候補.py"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
