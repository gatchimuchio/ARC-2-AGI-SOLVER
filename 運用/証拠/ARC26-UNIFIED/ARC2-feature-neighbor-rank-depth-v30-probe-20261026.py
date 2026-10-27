"""Screen deeper transform ranks for ambiguous feature-neighbor predictions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "運用/証拠/ARC26-UNIFIED"
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
TEMPLATE = ROOT / "接続/ARC2/テンプレート充填教材.json"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _key(grid):
    return tuple(tuple(row) for row in grid)


def _rank_depth_candidate(selector, grid, feature_module):
    original, _ = selector.候補(grid, {})
    if original is not None:
        return original
    if not feature_module.valid_grid(grid) or len(selector.teachers) < 2:
        return None
    current = feature_module._feature(grid)
    distances = [
        feature_module._distance(current, teacher_feature)
        for teacher_feature in selector.features
    ]
    best_distance = min(distances)
    if best_distance > selector.applicability_limit:
        return None
    nearest = [
        index
        for index, distance in enumerate(distances)
        if abs(distance - best_distance) <= 1e-12
    ]
    grouped = []
    for index in nearest:
        groups = []
        for model in selector.models[index]:
            if not groups or groups[-1][0][0] != model[0]:
                groups.append([model])
            else:
                groups[-1].append(model)
        grouped.append(groups)
    if not grouped:
        return None
    max_depth = min(len(groups) for groups in grouped)
    for depth in range(1, max_depth):
        predictions = set()
        complete = True
        for groups in grouped:
            teacher_predictions = set()
            for model in groups[depth]:
                prediction = feature_module.apply_model(model, grid)
                if feature_module.valid_grid(prediction):
                    teacher_predictions.add(_key(prediction))
            if not teacher_predictions:
                complete = False
                break
            predictions.update(teacher_predictions)
        if complete and len(predictions) == 1:
            return [list(row) for row in next(iter(predictions))]
    return None


def _cache_pair(pair, simple, feature_module, models, features):
    pair_key = json.dumps(pair, sort_keys=True, separators=(",", ":"))
    input_key = json.dumps(pair["input"], separators=(",", ":"))
    if pair_key not in models:
        models[pair_key] = simple.fitted_models([pair])
    if input_key not in features:
        features[input_key] = feature_module._feature(pair["input"])
    return models[pair_key], features[input_key]


def _selector(teachers, simple, feature_module, model_cache, feature_cache):
    pairs = [_cache_pair(pair, simple, feature_module, model_cache, feature_cache) for pair in teachers]
    return feature_module.FeatureNeighborTransform(
        teachers,
        precomputed_models=[pair[0] for pair in pairs],
        precomputed_features=[pair[1] for pair in pairs],
    )


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2 import 単純変換候補 as simple
    from 接続.ARC2 import 特徴近傍変換選択 as feature_module

    prior_sources = {
        row["課題ID"]
        for row in json.loads(TEMPLATE.read_text(encoding="utf-8"))["教材"]
    }
    model_cache = {}
    feature_cache = {}
    eligible = baseline_candidates = variant_candidates = changed_folds = 0
    loo_records = []
    changed_candidate_with_same_input = 0
    for path in sorted(TRAINING.glob("*.json")):
        if path.stem in prior_sources:
            continue
        task = json.loads(path.read_text(encoding="utf-8"))
        pairs = task.get("train", [])
        if len(pairs) < 3:
            continue
        for held_index, held in enumerate(pairs):
            eligible += 1
            teachers = [pair for index, pair in enumerate(pairs) if index != held_index]
            selector = _selector(teachers, simple, feature_module, model_cache, feature_cache)
            baseline = selector.候補(held["input"], {})[0]
            candidate = _rank_depth_candidate(selector, held["input"], feature_module)
            baseline_candidates += baseline is not None
            variant_candidates += candidate is not None
            if baseline == candidate:
                continue
            changed_folds += 1
            changed_candidate_with_same_input += candidate == held["input"]
            loo_records.append((path, held_index, baseline, candidate))

    # Held-out outputs are read only after every LOO candidate has been generated.
    baseline_exact = variant_exact = newly_exact = newly_wrong = 0
    for path, held_index, baseline, candidate in loo_records:
        target = json.loads(path.read_text(encoding="utf-8"))["train"][held_index]["output"]
        old_exact = baseline == target
        new_exact = candidate == target
        baseline_exact += old_exact
        variant_exact += new_exact
        newly_exact += new_exact and not old_exact
        newly_wrong += old_exact and not new_exact

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    public_examples = baseline_public = variant_public = changed_public = 0
    public_selected = set()
    public_records = []
    for task_key, task in sorted(challenge.items()):
        selector = _selector(task["train"], simple, feature_module, model_cache, feature_cache)
        selected_task = False
        for pair_index, pair in enumerate(task["test"]):
            public_examples += 1
            baseline = selector.候補(pair["input"], {})[0]
            candidate = _rank_depth_candidate(selector, pair["input"], feature_module)
            baseline_public += baseline is not None
            variant_public += candidate is not None
            if baseline != candidate:
                changed_public += 1
                public_records.append((task_key, pair_index, baseline, candidate))
                selected_task = True
        if selected_task:
            public_selected.add(task_key)

    # Public labels are read after the complete input-only candidate scan.
    public_old_exact = public_new_exact = public_newly_correct = public_newly_wrong = 0
    for task_key, pair_index, baseline, candidate in public_records:
        task = json.loads((TRAINING / f"{task_key}.json").read_text(encoding="utf-8"))
        target = task["test"][pair_index]["output"]
        old_exact = baseline == target
        new_exact = candidate == target
        public_old_exact += old_exact
        public_new_exact += new_exact
        public_newly_correct += new_exact and not old_exact
        public_newly_wrong += old_exact and not new_exact

    report = {
        "schema": "arc2-feature-neighbor-rank-depth-v30-probe-v1",
        "eligible_loo_folds": eligible,
        "loo_baseline_candidate_folds": baseline_candidates,
        "loo_rank_depth_candidate_folds": variant_candidates,
        "loo_changed_candidate_folds": changed_folds,
        "loo_candidate_exact": {
            "baseline": baseline_exact,
            "rank_depth": variant_exact,
            "newly_correct": newly_exact,
            "newly_wrong": newly_wrong,
        },
        "loo_candidate_equal_to_held_input": changed_candidate_with_same_input,
        "public_challenge_tasks": len(challenge),
        "public_challenge_examples": public_examples,
        "public_candidate_examples": {
            "baseline": baseline_public,
            "rank_depth": variant_public,
            "changed": changed_public,
        },
        "public_changed_tasks_for_exact_bundle": len(public_selected),
        "public_candidate_exact": {
            "baseline": public_old_exact,
            "rank_depth": public_new_exact,
            "newly_correct": public_newly_correct,
            "newly_wrong": public_newly_wrong,
        },
        "candidate_generation_received_heldout_outputs": False,
        "public_candidate_scan_received_test_targets": False,
        "targets_read_after_all_candidate_generation": True,
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
