"""Evaluate a teacher-fitted second-attempt hedge on feature-neighbor LOO folds."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import time

from P5_feature_neighbor_production_matched_LOO import load_modules, source_hashes


ROOT = Path(__file__).resolve().parents[3]
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"


def _solved(first, second, target, input_grid, adapter) -> bool:
    first_valid = adapter.格子か(first)
    return bool(
        (first_valid and first == target)
        or (
            second != first
            and adapter.格子か(second)
            and (first_valid or second != input_grid)
            and second == target
        )
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budget-seconds", type=float, default=1800)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    hashes_start = source_hashes()
    current, simple, feature, adapter = load_modules()
    prior = current.事前教材を読む()
    template = json.loads((ROOT / "接続/ARC2/テンプレート充填教材.json").read_text(encoding="utf-8"))
    prior_sources = {item["課題ID"] for item in template["教材"]}
    files = sorted(TRAINING.glob("*.json"))
    manifest = hashlib.sha256()
    eligible_folds = candidate_folds = 0
    old_exact = new_exact = new_candidates = 0
    gains = regressions = unchanged = 0
    selected_support = Counter()
    model_agreement = Counter()
    started = time.perf_counter()
    stopped = False

    for path in files:
        if path.stem in prior_sources:
            continue
        raw_bytes = path.read_bytes()
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw_bytes).digest())
        task_data = json.loads(raw_bytes)
        examples = task_data.get("train", [])
        if len(examples) < 3:
            continue
        for heldout_index, heldout in enumerate(examples):
            if time.perf_counter() - started >= args.budget_seconds:
                stopped = True
                break
            teachers = [pair for index, pair in enumerate(examples) if index != heldout_index]
            proposed, _ = feature.FeatureNeighborTransform(teachers).候補(heldout["input"], {})
            eligible_folds += 1
            if proposed is None:
                continue
            candidate_folds += 1
            task = {"train": teachers, "test": [{"input": heldout["input"]}]}
            result = current.課題を解く(task, prior, 候補収集=True)
            row = result.get("results", [{}])[0]
            first = row.get("answer")
            if not adapter.格子か(first):
                first = heldout["input"]
            second = adapter._一意な別候補を選ぶ(row.get("candidate_predictions"), first)
            if not adapter.格子か(second) or second == first:
                second = simple.unique_candidate(teachers, heldout["input"])
            if not adapter.格子か(second) or second == first:
                second = first
            before = _solved(first, second, heldout["output"], heldout["input"], adapter)
            old_exact += int(before)

            _, predictions, _, _ = simple.predict_pool(teachers, heldout["input"])
            ordered = sorted(predictions.items(), key=lambda item: (-item[1], item[0]))
            alternative = None
            support = 0
            for grid_key, votes in ordered:
                if votes < 2:
                    break
                candidate = [list(grid_row) for grid_row in grid_key]
                if candidate in (first, second, heldout["input"]):
                    continue
                alternative, support = candidate, votes
                break
            after = before or alternative == heldout["output"]
            new_exact += int(after)
            new_candidates += int(alternative is not None)
            if alternative is not None:
                selected_support[str(support)] += 1
            model_agreement[str(max(predictions.values(), default=0))] += 1
            gains += int(after and not before)
            regressions += int(before and not after)
            unchanged += int(before == after)
        if stopped:
            break

    hashes_end = source_hashes()
    output = {
        "schema": "arc2-v5-simple-transform-second-attempt-loo.v1",
        "experiment_id": "ARC26-ARC2-V5-P5-SIMPLE-TRANSFORM-SECOND-ATTEMPT-LOO",
        "data_source": "public ARC-AGI-2 training split; task-level heldout output used only by scorer",
        "training_manifest_sha256": manifest.hexdigest(),
        "heldout_output_passed_to_solver": False,
        "fallback_counted_correct": False,
        "task_identifiers_or_grids_saved": False,
        "candidate_policy": "second slot only; exact-fit simple transforms with at least two model votes; excludes first, current second, and input copy",
        "loo_folds_scanned": eligible_folds,
        "complete": not stopped,
        "feature_neighbor_candidate_folds": candidate_folds,
        "previous_paired_exact": old_exact,
        "current_paired_exact": new_exact,
        "paired_delta_exact": new_exact - old_exact,
        "paired_gains": gains,
        "paired_regressions": regressions,
        "paired_unchanged": unchanged,
        "distinct_second_candidates": new_candidates,
        "selected_support_counts": dict(sorted(selected_support.items())),
        "max_transform_model_agreement_counts": dict(sorted(model_agreement.items())),
        "source_sha256_start": hashes_start,
        "source_sha256_end": hashes_end,
        "source_hashes_unchanged": hashes_start == hashes_end,
        "seconds": round(time.perf_counter() - started, 3),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
