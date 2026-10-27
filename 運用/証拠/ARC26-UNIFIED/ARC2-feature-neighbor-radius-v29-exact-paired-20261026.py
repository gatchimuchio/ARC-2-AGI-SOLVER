"""Compare exact v28/v29 bundles with a wider feature-neighbor radius."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "運用/証拠/ARC26-UNIFIED"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
TEMPLATE = ROOT / "接続/ARC2/テンプレート充填教材.json"
V28_BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v28-vote-ratio-second-20261026"
V29_BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v29-feature-neighbor-radius-2x-20261026"
V28_CHALLENGE_REPORT = EVIDENCE / "ARC2-candidate-priority-v28-bundle-challenge-20261026.json"
OUTPUT = Path(__file__).with_suffix(".json")
EPSILON = 1e-12


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(build: Path) -> dict[str, str]:
    data = json.loads((build / "build-manifest.json").read_text(encoding="utf-8"))
    return {row["path"]: row["sha256"] for row in data["files"]}


def _run_bundle(build: Path, tasks: dict, prefix: str):
    if not tasks:
        return {}, {"fallback_count": 0}
    with tempfile.TemporaryDirectory(prefix=prefix) as temp_name:
        temp = Path(temp_name)
        challenge_path = temp / "challenges.json"
        output_dir = temp / "output"
        challenge_path.write_text(json.dumps(tasks, ensure_ascii=False), encoding="utf-8")
        environment = {
            **os.environ,
            "PYTHONUTF8": "1",
            "ARC2_PAYLOAD_ROOT": str(temp / "payload"),
        }
        process = subprocess.run(
            [
                sys.executable,
                str(build / "solve.py"),
                "--challenges",
                str(challenge_path),
                "--output-dir",
                str(output_dir),
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
            check=False,
        )
        if process.returncode:
            raise RuntimeError(
                f"{build.name} failed ({process.returncode}): {process.stderr[-4000:]}"
            )
        predictions = json.loads(
            (output_dir / "submission.json").read_text(encoding="utf-8")
        )
        audit = json.loads(
            (output_dir / "submission_audit.json").read_text(encoding="utf-8")
        )
    return predictions, audit


def _score(predictions: dict, targets: dict) -> dict[str, int]:
    exact_examples = exact_tasks = 0
    for task_key, rows in predictions.items():
        correct = [
            row["attempt_1"] == target or row["attempt_2"] == target
            for row, target in zip(rows, targets[task_key], strict=True)
        ]
        exact_examples += sum(correct)
        exact_tasks += all(correct)
    return {"exact_tasks": exact_tasks, "exact_examples": exact_examples}


def _candidate(selector, grid, multiplier: float):
    original_limit = selector.applicability_limit
    selector.applicability_limit = max(
        0.0, (original_limit - EPSILON) * multiplier / 2.0 + EPSILON
    )
    try:
        return selector.候補(grid, {})[0]
    finally:
        selector.applicability_limit = original_limit


def _pair_counts(rows: list[dict], before: dict, after: dict, targets: list):
    counts = {
        "folds": len(rows),
        "v28_exact": 0,
        "v29_exact": 0,
        "newly_correct": 0,
        "newly_wrong": 0,
        "examples_changed": 0,
        "attempt_1_changed": 0,
        "attempt_2_changed": 0,
    }
    for index, (old_row, new_row, target) in enumerate(zip(before, after, targets, strict=True)):
        old_correct = old_row["attempt_1"] == target or old_row["attempt_2"] == target
        new_correct = new_row["attempt_1"] == target or new_row["attempt_2"] == target
        counts["v28_exact"] += old_correct
        counts["v29_exact"] += new_correct
        counts["newly_correct"] += new_correct and not old_correct
        counts["newly_wrong"] += old_correct and not new_correct
        counts["examples_changed"] += old_row != new_row
        counts["attempt_1_changed"] += old_row["attempt_1"] != new_row["attempt_1"]
        counts["attempt_2_changed"] += old_row["attempt_2"] != new_row["attempt_2"]
    return counts


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    if not V28_BUILD.is_dir() or not V29_BUILD.is_dir():
        raise FileNotFoundError("exact v28/v29 bundle is missing")

    old_manifest = _manifest(V28_BUILD)
    new_manifest = _manifest(V29_BUILD)
    if old_manifest.keys() != new_manifest.keys():
        raise RuntimeError("v28/v29 payload file sets differ")
    changed_files = sorted(
        name for name in old_manifest if old_manifest[name] != new_manifest[name]
    )
    if changed_files != ["接続/ARC2/特徴近傍変換選択.py"]:
        raise RuntimeError(f"unexpected source delta: {changed_files}")

    sys.path.insert(0, str(ROOT))
    from 接続.ARC2 import 単純変換候補 as simple
    from 接続.ARC2 import 特徴近傍変換選択 as feature_module
    FeatureNeighborTransform = feature_module.FeatureNeighborTransform
    prior_sources = {
        row["課題ID"]
        for row in json.loads(TEMPLATE.read_text(encoding="utf-8"))["教材"]
    }
    model_cache = {}
    feature_cache = {}
    loaded = []
    for path in sorted(SOURCE_ROOT.glob("*.json")):
        task = json.loads(path.read_text(encoding="utf-8"))
        loaded.append((path, task))
        for pair in task.get("train", []):
            pair_key = json.dumps(pair, sort_keys=True, separators=(",", ":"))
            input_key = json.dumps(pair["input"], separators=(",", ":"))
            if pair_key not in model_cache:
                model_cache[pair_key] = simple.fitted_models([pair])
            if input_key not in feature_cache:
                feature_cache[input_key] = feature_module._feature(pair["input"])

    loo_rows = []
    loo_eligible = loo_15 = loo_20 = loo_added = 0
    for path, task in loaded:
        if path.stem in prior_sources:
            continue
        pairs = task.get("train", [])
        if len(pairs) < 3:
            continue
        for held_index, held in enumerate(pairs):
            loo_eligible += 1
            teachers = [pair for index, pair in enumerate(pairs) if index != held_index]
            pair_models = [
                model_cache[json.dumps(pair, sort_keys=True, separators=(",", ":"))]
                for pair in teachers
            ]
            pair_features = [
                feature_cache[json.dumps(pair["input"], separators=(",", ":"))]
                for pair in teachers
            ]
            selector = FeatureNeighborTransform(
                teachers,
                precomputed_models=pair_models,
                precomputed_features=pair_features,
            )
            candidate_15 = _candidate(selector, held["input"], 1.5)
            candidate_20 = _candidate(selector, held["input"], 2.0)
            loo_15 += candidate_15 is not None
            loo_20 += candidate_20 is not None
            loo_added += candidate_15 is None and candidate_20 is not None
            if candidate_15 is not None or candidate_20 is not None:
                loo_rows.append((path, held_index, teachers, held["input"]))

    loo_tasks = {
        f"fold_{index:05d}": {"train": teachers, "test": [{"input": grid}]}
        for index, (_, _, teachers, grid) in enumerate(loo_rows)
    }
    loo_v28, loo_v28_audit = _run_bundle(V28_BUILD, loo_tasks, "arc2-v28-radius-loo-")
    loo_v29, loo_v29_audit = _run_bundle(V29_BUILD, loo_tasks, "arc2-v29-radius-loo-")

    # Training targets are read only after both exact bundle runs have completed.
    loo_targets = [
        json.loads(path.read_text(encoding="utf-8"))["train"][held_index]["output"]
        for path, held_index, _, _ in loo_rows
    ]
    loo_old_rows = [loo_v28[f"fold_{index:05d}"][0] for index in range(len(loo_rows))]
    loo_new_rows = [loo_v29[f"fold_{index:05d}"][0] for index in range(len(loo_rows))]
    loo_score = _pair_counts(loo_rows, loo_old_rows, loo_new_rows, loo_targets)

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    selected = {}
    challenge_examples = 0
    challenge_15 = challenge_20 = challenge_added = 0
    for task_key, task in sorted(challenge.items()):
        selector = FeatureNeighborTransform(task["train"])
        relevant = False
        for pair in task["test"]:
            candidate_15 = _candidate(selector, pair["input"], 1.5)
            candidate_20 = _candidate(selector, pair["input"], 2.0)
            challenge_examples += 1
            challenge_15 += candidate_15 is not None
            challenge_20 += candidate_20 is not None
            challenge_added += candidate_15 is None and candidate_20 is not None
            relevant |= candidate_15 != candidate_20
        if relevant:
            selected[task_key] = {
                "train": task["train"],
                "test": [{"input": pair["input"]} for pair in task["test"]],
            }

    challenge_v28, challenge_v28_audit = _run_bundle(
        V28_BUILD, selected, "arc2-v28-radius-challenge-"
    )
    challenge_v29, challenge_v29_audit = _run_bundle(
        V29_BUILD, selected, "arc2-v29-radius-challenge-"
    )
    # Official public targets are opened only after both exact bundles finish.
    public_targets = {
        task_key: [
            pair["output"]
            for pair in json.loads((SOURCE_ROOT / f"{task_key}.json").read_text(encoding="utf-8")).get("test", [])
        ]
        for task_key in selected
    }
    challenge_v28_score = _score(challenge_v28, public_targets)
    challenge_v29_score = _score(challenge_v29, public_targets)
    changed_examples = changed_attempt_1 = changed_attempt_2 = 0
    for task_key, rows in challenge_v29.items():
        for index, new_row in enumerate(rows):
            old_row = challenge_v28[task_key][index]
            changed_examples += old_row != new_row
            changed_attempt_1 += old_row["attempt_1"] != new_row["attempt_1"]
            changed_attempt_2 += old_row["attempt_2"] != new_row["attempt_2"]

    v28_projection = json.loads(V28_CHALLENGE_REPORT.read_text(encoding="utf-8"))[
        "projected_full_challenge_v28"
    ]
    challenge_delta = {
        "exact_tasks": challenge_v29_score["exact_tasks"] - challenge_v28_score["exact_tasks"],
        "exact_examples": challenge_v29_score["exact_examples"] - challenge_v28_score["exact_examples"],
    }
    report = {
        "schema": "arc2-feature-neighbor-radius-v29-exact-paired-v1",
        "radius_factor_before": 1.5,
        "radius_factor_candidate": 2.0,
        "loo": {
            "eligible_folds": loo_eligible,
            "folds_with_candidate_at_1_5x": loo_15,
            "folds_with_candidate_at_2x": loo_20,
            "newly_eligible_folds_at_2x": loo_added,
            "exact_bundle_pair": loo_score,
            "v28_bundle_fallbacks": loo_v28_audit.get("fallback_count"),
            "v29_bundle_fallbacks": loo_v29_audit.get("fallback_count"),
        },
        "public_challenge": {
            "tasks": len(challenge),
            "examples": challenge_examples,
            "examples_with_candidate_at_1_5x": challenge_15,
            "examples_with_candidate_at_2x": challenge_20,
            "newly_eligible_examples_at_2x": challenge_added,
            "changed_scope_tasks_run_in_both_exact_bundles": len(selected),
            "examples_run_in_both_exact_bundles": sum(len(task["test"]) for task in selected.values()),
            "v28_subset_score": challenge_v28_score,
            "v29_subset_score": challenge_v29_score,
            "projected_v28_full_score": v28_projection,
            "projected_v29_full_score": {
                "exact_tasks": v28_projection["exact_tasks"] + challenge_delta["exact_tasks"],
                "exact_examples": v28_projection["exact_examples"] + challenge_delta["exact_examples"],
            },
            "projected_delta": challenge_delta,
            "changed_examples": changed_examples,
            "changed_attempt_1_examples": changed_attempt_1,
            "changed_attempt_2_examples": changed_attempt_2,
            "v28_bundle_fallbacks": challenge_v28_audit.get("fallback_count"),
            "v29_bundle_fallbacks": challenge_v29_audit.get("fallback_count"),
        },
        "runtime_received_test_targets": False,
        "loo_targets_read_after_both_exact_bundle_runs": True,
        "challenge_targets_read_after_both_exact_bundle_runs": True,
        "task_predictions_or_targets_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "challenge": _sha(CHALLENGE),
            "v28_bundle_manifest": _sha(V28_BUILD / "build-manifest.json"),
            "v29_bundle_manifest": _sha(V29_BUILD / "build-manifest.json"),
            "v28_challenge_report": _sha(V28_CHALLENGE_REPORT),
        },
        "payload_changed_files": changed_files,
        "temporary_subset_outputs_removed": True,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
