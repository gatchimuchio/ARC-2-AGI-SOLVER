"""Paired LOO slice through the actual ARC2 HDS runtime before/after candidate."""
from __future__ import annotations

from collections import Counter
import hashlib
import importlib
import json
from pathlib import Path
import sys
import time
import types


ROOT = Path(__file__).resolve().parents[3]
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
HDS_PATH = ROOT / "接続/ARC2/HDS接続.py"
HDS_DIR = ROOT / "HDS/学習系統/v0.4.2"


def load_modules():
    sys.path[:0] = [str(ROOT), str(HDS_DIR)]
    importlib.invalidate_caches()
    current = importlib.import_module("接続.ARC2.HDS接続")
    simple = importlib.import_module("接続.ARC2.単純変換候補")
    feature = importlib.import_module("接続.ARC2.特徴近傍変換選択")
    adapter = importlib.import_module("接続.ARC2.Kaggle提出")
    return current, simple, feature, adapter


def load_baseline_without_feature_neighbor(source_text):
    replacements = (
        (
            "from .特徴近傍変換選択 import FeatureNeighborTransform\n",
            "",
        ),
        (
            "    特徴近傍 = FeatureNeighborTransform(課題[\"train\"])\n",
            "",
        ),
        (
            "        (\"ARC特徴近傍変換選択\", 特徴近傍.候補, ()),\n",
            "",
        ),
        (
            "    記録群 = []\n"
            "    for 境界, 候補器, 教材 in 機構群:\n"
            "        if 境界 == \"ARC特徴近傍変換選択\":\n"
            "            教材 = [例 for 例 in 事前教材 if 特徴近傍.適用範囲内(例[\"input\"])]\n"
            "        記録群.append(候補機構を学習(機械, 課題, 教材, 境界, 候補器))\n",
            "    記録群 = [候補機構を学習(機械, 課題, 教材, 境界, 候補器)\n"
            "              for 境界, 候補器, 教材 in 機構群]\n",
        ),
        (
            '            "feature_neighbor_transform": 特徴近傍.記録(),\n',
            "",
        ),
    )
    baseline = source_text
    for old, new in replacements:
        if baseline.count(old) != 1:
            raise RuntimeError("could not isolate candidate-only baseline source")
        baseline = baseline.replace(old, new, 1)
    module = types.ModuleType("接続.ARC2.HDS接続_feature_neighbor_baseline")
    module.__file__ = str(HDS_PATH)
    module.__package__ = "接続.ARC2"
    exec(compile(baseline, str(HDS_PATH), "exec"), module.__dict__)
    return module


def source_hashes():
    paths = {
        "runner": Path(__file__),
        "hds_connector": HDS_PATH,
        "feature_neighbor_module": ROOT / "接続/ARC2/特徴近傍変換選択.py",
        "simple_transform_module": ROOT / "接続/ARC2/単純変換候補.py",
        "submission_adapter": ROOT / "接続/ARC2/Kaggle提出.py",
    }
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}


def candidate_attempts(runtime, adapter, task, prior):
    result = runtime.課題を解く(task, prior, 候補収集=True)
    rows = result.get("results", [])
    submission_rows = []
    for index, test_pair in enumerate(task["test"]):
        row = rows[index] if index < len(rows) and isinstance(rows[index], dict) else {}
        first = row.get("answer")
        if not adapter.格子か(first):
            first = test_pair["input"]
        second = adapter._一意な別候補を選ぶ(row.get("candidate_predictions"), first)
        submission_rows.append({
            "answer": row.get("answer"),
            "second_answer": second,
            "status": row.get("status"),
            "reasons": row.get("reasons"),
        })
    packaged, _ = adapter.結果を候補へ("matched-loo", task, {"results": submission_rows})
    return result, packaged


def solves(raw_row, packaged_row, target, input_grid, adapter):
    first = raw_row.get("answer")
    first_valid = adapter.格子か(first)
    first_ok = first_valid and first == target
    second = packaged_row["attempt_2"]
    second_ok = (
        second != packaged_row["attempt_1"]
        and adapter.格子か(second)
        and (first_valid or second != input_grid)
        and second == target
    )
    return bool(first_ok or second_ok)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budget-seconds", type=float, default=1800)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    hashes_start = source_hashes()
    current, simple, feature, adapter = load_modules()
    source_text = HDS_PATH.read_text(encoding="utf-8")
    baseline = load_baseline_without_feature_neighbor(source_text)
    prior = current.事前教材を読む()
    template = json.loads((ROOT / "接続/ARC2/テンプレート充填教材.json").read_text(encoding="utf-8"))
    prior_sources = {item["課題ID"] for item in template["教材"]}

    files = sorted(TRAINING.glob("*.json"))
    manifest = hashlib.sha256()
    loaded = []
    model_cache = {}
    feature_cache = {}
    for path in files:
        raw = path.read_bytes()
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        task = json.loads(raw)
        loaded.append((path, task))
        for pair in task.get("train", []):
            pair_key = json.dumps(pair, sort_keys=True, separators=(",", ":"))
            model_cache.setdefault(pair_key, simple.fitted_models([pair]))
            input_key = json.dumps(pair["input"], separators=(",", ":"))
            feature_cache.setdefault(input_key, feature._feature(pair["input"]))

    folds = candidate_folds = before_exact = after_exact = 0
    baseline_fallbacks = candidate_fallbacks = 0
    accepted = rejected = candidate_predictions = 0
    gains = regressions = unchanged = 0
    baseline_runtime = candidate_runtime = 0.0
    gate_states = Counter()
    started = time.perf_counter()
    stopped = False
    for path, task_data in loaded:
        examples = task_data.get("train", [])
        if path.stem in prior_sources or len(examples) < 3:
            continue
        for heldout_index, heldout in enumerate(examples):
            if time.perf_counter() - started >= args.budget_seconds:
                stopped = True
                break
            teachers = [pair for index, pair in enumerate(examples) if index != heldout_index]
            pair_models = [
                model_cache[json.dumps(pair, sort_keys=True, separators=(",", ":"))]
                for pair in teachers
            ]
            pair_features = [
                feature_cache[json.dumps(pair["input"], separators=(",", ":"))]
                for pair in teachers
            ]
            selector = feature.FeatureNeighborTransform(
                teachers,
                precomputed_models=pair_models,
                precomputed_features=pair_features,
            )
            proposed, _ = selector.候補(heldout["input"], {})
            folds += 1
            if proposed is None:
                continue
            candidate_folds += 1
            task = {"train": teachers, "test": [{"input": heldout["input"]}]}

            before_start = time.perf_counter()
            before_raw, before_submission = candidate_attempts(baseline, adapter, task, prior)
            baseline_runtime += time.perf_counter() - before_start
            after_start = time.perf_counter()
            after_raw, after_submission = candidate_attempts(current, adapter, task, prior)
            candidate_runtime += time.perf_counter() - after_start

            before_row = before_raw.get("results", [{}])[0]
            after_row = after_raw.get("results", [{}])[0]
            target = heldout["output"]
            input_grid = heldout["input"]
            before_solved = solves(before_row, before_submission[0], target, input_grid, adapter)
            after_solved = solves(after_row, after_submission[0], target, input_grid, adapter)
            before_exact += int(before_solved)
            after_exact += int(after_solved)
            gains += int(after_solved and not before_solved)
            regressions += int(before_solved and not after_solved)
            unchanged += int(before_solved == after_solved)
            baseline_fallbacks += int(not adapter.格子か(before_row.get("answer")))
            candidate_fallbacks += int(not adapter.格子か(after_row.get("answer")))

            record = next(
                (item for item in after_raw.get("families", []) if item.get("境界") == "ARC特徴近傍変換選択"),
                {},
            )
            is_accepted = bool(record.get("採用可") and record.get("同値採用"))
            accepted += int(is_accepted)
            rejected += int(not is_accepted)
            gate_states[record.get("状態", "missing")] += 1
            candidate_predictions += sum(
                item.get("family") == "ARC特徴近傍変換選択"
                for item in after_row.get("candidate_predictions", [])
                if isinstance(item, dict)
            )
            if folds % 100 == 0:
                print(json.dumps({"folds_done": folds, "candidate_folds": candidate_folds, "accepted": accepted, "gains": gains, "regressions": regressions}), flush=True)
        if stopped:
            break

    hashes_end = source_hashes()
    result = {
        "schema": "arc2-v5-feature-neighbor-production-paired-loo.v1",
        "experiment_id": "ARC26-ARC2-V5-P5-FEATURE-NEIGHBOR-ACTUAL-RUNTIME-PAIRED-LOO",
        "training_manifest_sha256": manifest.hexdigest(),
        "data_source": "public ARC-AGI-2 training split and fixed training-only prior",
        "heldout_output_passed_to_solver": False,
        "fallback_counted_correct": False,
        "task_identifiers_or_grids_saved": False,
        "comparison": "current runtime source with only the new candidate import/registration/filter/record removed in memory for baseline",
        "eligible_tasks": sum(
            1 for path, item in loaded
            if path.stem not in prior_sources and len(item.get("train", [])) >= 3
        ),
        "loo_folds_scanned": folds,
        "complete": not stopped,
        "candidate_eligible_folds": candidate_folds,
        "actual_hds_gate_accepted": accepted,
        "actual_hds_gate_rejected": rejected,
        "actual_hds_gate_states": dict(gate_states),
        "actual_candidate_predictions_emitted": candidate_predictions,
        "paired_baseline_exact": before_exact,
        "paired_candidate_exact": after_exact,
        "paired_delta_exact": after_exact - before_exact,
        "paired_gains": gains,
        "paired_regressions": regressions,
        "paired_unchanged": unchanged,
        "baseline_first_fallbacks": baseline_fallbacks,
        "candidate_first_fallbacks": candidate_fallbacks,
        "baseline_runtime_seconds": round(baseline_runtime, 3),
        "candidate_runtime_seconds": round(candidate_runtime, 3),
        "source_sha256_start": hashes_start,
        "source_sha256_end": hashes_end,
        "source_hashes_unchanged": hashes_start == hashes_end,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
