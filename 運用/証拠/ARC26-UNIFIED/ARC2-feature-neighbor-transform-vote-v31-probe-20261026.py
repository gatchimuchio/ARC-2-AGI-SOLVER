"""Probe all-model voting for feature-neighbor cases the current selector abstains on."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
TEMPLATE = ROOT / "接続/ARC2/テンプレート充填教材.json"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _key(grid):
    return tuple(tuple(row) for row in grid)


def _vote_candidate(selector, grid, feature_module):
    current, _ = selector.候補(grid, {})
    if current is not None:
        return current
    if not feature_module.valid_grid(grid) or len(selector.teachers) < 2:
        return None
    current_feature = feature_module._feature(grid)
    distances = [
        feature_module._distance(current_feature, teacher_feature)
        for teacher_feature in selector.features
    ]
    best_distance = min(distances)
    if best_distance > selector.applicability_limit:
        return None
    nearest = [
        index for index, distance in enumerate(distances)
        if abs(distance - best_distance) <= 1e-12
    ]
    votes = Counter()
    teacher_votes = []
    grids = {}
    for index in nearest:
        local = Counter()
        for model in selector.models[index]:
            prediction = feature_module.apply_model(model, grid)
            if not feature_module.valid_grid(prediction):
                continue
            prediction_key = _key(prediction)
            local[prediction_key] += 1
            votes[prediction_key] += 1
            grids.setdefault(prediction_key, [list(row) for row in prediction])
        teacher_votes.append(local)
    if not votes:
        return None
    ranked = votes.most_common()
    top_key, top_votes = ranked[0]
    second_votes = ranked[1][1] if len(ranked) > 1 else 0
    if top_votes < 2 or top_votes <= second_votes:
        return None
    if any(local.get(top_key, 0) == 0 for local in teacher_votes):
        return None
    return grids[top_key]


def _cache_pair(pair, simple, feature_module, models, features):
    pair_key = json.dumps(pair, sort_keys=True, separators=(",", ":"))
    input_key = json.dumps(pair["input"], separators=(",", ":"))
    if pair_key not in models:
        models[pair_key] = simple.fitted_models([pair])
    if input_key not in features:
        features[input_key] = feature_module._feature(pair["input"])
    return models[pair_key], features[input_key]


def _selector(teachers, simple, feature_module, model_cache, feature_cache):
    cached = [
        _cache_pair(pair, simple, feature_module, model_cache, feature_cache)
        for pair in teachers
    ]
    return feature_module.FeatureNeighborTransform(
        teachers,
        precomputed_models=[row[0] for row in cached],
        precomputed_features=[row[1] for row in cached],
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
    model_cache, feature_cache = {}, {}
    eligible = baseline_proposals = variant_proposals = changed = 0
    loo_records = []
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
            candidate = _vote_candidate(selector, held["input"], feature_module)
            baseline_proposals += baseline is not None
            variant_proposals += candidate is not None
            if baseline != candidate:
                changed += 1
                loo_records.append((path, held_index, baseline, candidate))

    # Held-out labels are read only after input-only candidate generation ends.
    baseline_exact = candidate_exact = newly_correct = newly_wrong = 0
    for path, held_index, baseline, candidate in loo_records:
        target = json.loads(path.read_text(encoding="utf-8"))["train"][held_index]["output"]
        old_exact = baseline == target
        new_exact = candidate == target
        baseline_exact += old_exact
        candidate_exact += new_exact
        newly_correct += new_exact and not old_exact
        newly_wrong += old_exact and not new_exact

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    public_examples = baseline_public = candidate_public = changed_public = 0
    changed_tasks = set()
    public_records = []
    for task_key, task in sorted(challenge.items()):
        selector = _selector(task["train"], simple, feature_module, model_cache, feature_cache)
        for index, pair in enumerate(task["test"]):
            public_examples += 1
            baseline = selector.候補(pair["input"], {})[0]
            candidate = _vote_candidate(selector, pair["input"], feature_module)
            baseline_public += baseline is not None
            candidate_public += candidate is not None
            if baseline != candidate:
                changed_public += 1
                changed_tasks.add(task_key)
                public_records.append((task_key, index, baseline, candidate))

    # Public labels are consulted only after every public candidate is fixed.
    public_old_exact = public_new_exact = public_gains = public_losses = 0
    for task_key, index, baseline, candidate in public_records:
        target = json.loads((TRAINING / f"{task_key}.json").read_text(encoding="utf-8"))["test"][index]["output"]
        old_exact = baseline == target
        new_exact = candidate == target
        public_old_exact += old_exact
        public_new_exact += new_exact
        public_gains += new_exact and not old_exact
        public_losses += old_exact and not new_exact

    report = {
        "schema": "arc2-feature-neighbor-transform-vote-v31-probe-v1",
        "eligible_loo_folds": eligible,
        "loo_candidate_proposals": {"baseline": baseline_proposals, "all_model_vote": variant_proposals},
        "loo_changed_folds": changed,
        "loo_candidate_exact_on_changed_folds": {
            "baseline": baseline_exact,
            "all_model_vote": candidate_exact,
            "newly_correct": newly_correct,
            "newly_wrong": newly_wrong,
        },
        "public_challenge_tasks": len(challenge),
        "public_challenge_examples": public_examples,
        "public_candidate_proposals": {"baseline": baseline_public, "all_model_vote": candidate_public},
        "public_changed_examples": changed_public,
        "public_changed_tasks_for_exact_bundle": len(changed_tasks),
        "public_candidate_exact_on_changed_examples": {
            "baseline": public_old_exact,
            "all_model_vote": public_new_exact,
            "newly_correct": public_gains,
            "newly_wrong": public_losses,
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
