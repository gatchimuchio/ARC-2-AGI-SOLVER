"""Cross-validated feature-neighbor selection of simple ARC transforms.

Programs are fit from public training input/output pairs. At prediction time,
only input-derived structural features select a transform; task IDs and grids
are never written to the report. Held-out outputs remain in the parent scorer.
"""
from __future__ import annotations

from collections import Counter, deque
import hashlib
import importlib
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
SIMPLE_PATH = ROOT / "接続/ARC2/単純変換候補.py"
FEATURE_PATH = ROOT / "接続/ARC2/特徴近傍変換選択.py"
HDS_DIR = ROOT / "HDS/学習系統/v0.4.2"


def load_simple_runner():
    module_name = "接続.ARC2.単純変換候補"
    sys.modules.pop(module_name, None)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    importlib.invalidate_caches()
    return importlib.import_module(module_name)


def load_runtime():
    for name in tuple(sys.modules):
        if name == "接続" or name.startswith("接続."):
            del sys.modules[name]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    if str(HDS_DIR) not in sys.path:
        sys.path.insert(1, str(HDS_DIR))
    importlib.invalidate_caches()
    return importlib.import_module("接続.ARC2.HDS接続")


def load_feature_module():
    module_name = "接続.ARC2.特徴近傍変換選択"
    sys.modules.pop(module_name, None)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    importlib.invalidate_caches()
    return importlib.import_module(module_name)


def source_hashes():
    paths = {
        "runner": Path(__file__),
        "simple_transform_candidate": SIMPLE_PATH,
        "feature_neighbor_module": FEATURE_PATH,
        "hds_connector": ROOT / "接続/ARC2/HDS接続.py",
        "submission_adapter": ROOT / "接続/ARC2/Kaggle提出.py",
    }
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}


def feature(grid):
    height, width = len(grid), len(grid[0])
    counts = Counter(color for row in grid for color in row)
    area = height * width
    background = min(counts, key=lambda color: (-counts[color], color))
    points = [(r, c) for r, row in enumerate(grid) for c, value in enumerate(row) if value != background]
    if points:
        r0, r1 = min(r for r, _ in points), max(r for r, _ in points) + 1
        c0, c1 = min(c for _, c in points), max(c for _, c in points) + 1
        box_h, box_w = r1 - r0, c1 - c0
    else:
        box_h = box_w = 0

    seen = set()
    component_sizes = []
    for r, c in points:
        if (r, c) in seen:
            continue
        queue = deque([(r, c)])
        seen.add((r, c))
        size = 0
        while queue:
            rr, cc = queue.popleft()
            size += 1
            for nr, nc in ((rr - 1, cc), (rr + 1, cc), (rr, cc - 1), (rr, cc + 1)):
                if (0 <= nr < height and 0 <= nc < width and (nr, nc) not in seen and grid[nr][nc] != background):
                    seen.add((nr, nc))
                    queue.append((nr, nc))
        component_sizes.append(size)
    component_sizes.sort(reverse=True)

    horizontal_changes = sum(grid[r][c] != grid[r][c + 1] for r in range(height) for c in range(width - 1))
    vertical_changes = sum(grid[r][c] != grid[r + 1][c] for r in range(height - 1) for c in range(width))
    horizontal_edges = max(1, height * (width - 1))
    vertical_edges = max(1, (height - 1) * width)
    color_profile = sorted((count / area for count in counts.values()), reverse=True)
    color_profile.extend([0.0] * (10 - len(color_profile)))
    size_profile = [size / area for size in component_sizes[:5]]
    size_profile.extend([0.0] * (5 - len(size_profile)))
    return tuple([
        height / 30,
        width / 30,
        height / width,
        len(counts) / 10,
        len(points) / area,
        box_h / 30,
        box_w / 30,
        len(component_sizes) / 30,
        horizontal_changes / horizontal_edges,
        vertical_changes / vertical_edges,
        *color_profile,
        *size_profile,
    ])


def unique_second(candidates, first, simple):
    votes = Counter()
    if not isinstance(candidates, list):
        return None
    for item in candidates:
        if not isinstance(item, dict):
            continue
        grid = item.get("answer")
        if simple.valid_grid(grid) and simple.key(grid) != simple.key(first):
            votes[simple.key(grid)] += 1
    if not votes:
        return None
    top = max(votes.values())
    winners = [grid for grid, count in votes.items() if count == top]
    return [list(row) for row in winners[0]] if len(winners) == 1 else None


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--budget-seconds", type=float, default=1800)
    parser.add_argument("--prior-context", choices=("task", "global", "scoped"), default="task")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    if args.budget_seconds <= 0:
        raise SystemExit("budget must be positive")

    source_hashes_start = source_hashes()
    simple = load_simple_runner()
    feature_module = load_feature_module()
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
            feature_cache.setdefault(input_key, feature(pair["input"]))

    runtime = load_runtime()
    prior = runtime.事前教材を読む()
    template = json.loads((ROOT / "接続/ARC2/テンプレート充填教材.json").read_text(encoding="utf-8"))
    prior_sources = {item["課題ID"] for item in template["教材"]}
    for pair in prior:
        pair_key = json.dumps(pair, sort_keys=True, separators=(",", ":"))
        model_cache.setdefault(pair_key, simple.fitted_models([pair]))
        input_key = json.dumps(pair["input"], separators=(",", ":"))
        feature_cache.setdefault(input_key, feature(pair["input"]))

    folds = eligible = candidate_folds = candidate_unique = 0
    gate_calls = gate_admitted = gate_rejected = 0
    gate_states = Counter()
    prior_in_scope = prior_out_of_scope = prior_wrong_checks = prior_conflict_folds = 0
    paired_before = paired_after = gains = regressions = 0
    baseline_calls = baseline_exact = baseline_fallback = baseline_second_exact = 0
    candidate_exact = 0
    started = time.perf_counter()
    stopped = False
    for path, task in loaded:
        examples = task.get("train", [])
        if path.stem in prior_sources or len(examples) < 3:
            continue
        eligible += 1
        for heldout_index, heldout in enumerate(examples):
            if time.perf_counter() - started >= args.budget_seconds:
                stopped = True
                break
            teachers = [pair for index, pair in enumerate(examples) if index != heldout_index]
            supports = teachers if args.prior_context in {"task", "scoped"} else [*prior, *teachers]
            pair_models = [
                model_cache[json.dumps(pair, sort_keys=True, separators=(",", ":"))]
                for pair in supports
            ]
            pair_features = [
                feature_cache[json.dumps(pair["input"], separators=(",", ":"))]
                for pair in supports
            ]
            predictor = feature_module.FeatureNeighborTransform(
                supports,
                precomputed_models=pair_models,
                precomputed_features=pair_features,
            )
            candidate, _ = predictor.候補(heldout["input"], {})
            folds += 1
            if candidate is None:
                if folds % 500 == 0:
                    print(json.dumps({"folds_done": folds, "candidate_folds": candidate_folds}), flush=True)
                continue
            candidate_folds += 1
            target_key = simple.key(heldout["output"])
            candidate_exact += int(simple.key(candidate) == target_key)

            minimum_support = 2 if len(teachers) == 2 and teachers[0]["input"] != teachers[1]["input"] else 3
            machine = runtime.HDS学習実行系(最小支持数=minimum_support)
            for pair in teachers:
                machine.実行(runtime.格子観測(pair))

            def candidate_fn(input_grid, _expected):
                return predictor.候補(input_grid, {})

            gate_prior = []
            if args.prior_context == "global":
                gate_prior = prior
            elif args.prior_context == "scoped":
                prior_conflict = False
                for prior_pair in prior:
                    prior_prediction, _ = predictor.候補(prior_pair["input"], {})
                    if prior_prediction is None:
                        prior_out_of_scope += 1
                    else:
                        prior_in_scope += 1
                        if simple.key(prior_prediction) != simple.key(prior_pair["output"]):
                            prior_wrong_checks += 1
                            prior_conflict = True
                        else:
                            gate_prior.append(prior_pair)
                if prior_conflict:
                    prior_conflict_folds += 1
                    record = {"採用可": False, "同値採用": False, "状態": "prior counterexample"}
                else:
                    record = runtime.候補機構を学習(
                        machine,
                        {"train": teachers, "test": []},
                        gate_prior,
                        "ARC特徴近傍変換選択",
                        candidate_fn,
                    )
            else:
                record = runtime.候補機構を学習(
                    machine,
                    {"train": teachers, "test": []},
                    gate_prior,
                    "ARC特徴近傍変換選択",
                    candidate_fn,
                )
            admitted = bool(record["採用可"] and record["同値採用"])
            gate_calls += 1
            gate_admitted += int(admitted)
            gate_rejected += int(not admitted)
            gate_states[record.get("状態", "unknown")] += 1
            if not admitted:
                continue
            candidate_unique += 1

            baseline = runtime.課題を解く(
                {"train": teachers, "test": [{"input": heldout["input"]}]},
                prior,
                候補収集=True,
            )
            row = baseline.get("results", [{}])[0]
            answer = row.get("answer")
            first_valid = simple.valid_grid(answer)
            baseline_fallback += int(not first_valid)
            baseline_exact += int(first_valid and simple.key(answer) == target_key)
            first_for_adapter = answer if first_valid else heldout["input"]
            attempts_before = [first_for_adapter, unique_second(row.get("candidate_predictions"), first_for_adapter, simple)]
            attempts_after = [first_for_adapter, unique_second(
                [*(row.get("candidate_predictions") or []), {"family": "ARC特徴近傍変換選択", "answer": candidate}],
                first_for_adapter,
                simple,
            )]
            old_second = attempts_before[1]
            baseline_second_exact += int(old_second is not None and simple.key(old_second) == target_key)
            before = simple.key(attempts_before[0]) == target_key or old_second is not None and simple.key(old_second) == target_key
            after_second = attempts_after[1]
            after = simple.key(attempts_after[0]) == target_key or after_second is not None and simple.key(after_second) == target_key
            paired_before += int(before)
            paired_after += int(after)
            gains += int(after and not before)
            regressions += int(before and not after)
            if folds % 500 == 0:
                print(json.dumps({"folds_done": folds, "candidate_folds": candidate_folds, "gate_admitted": gate_admitted}), flush=True)
        if stopped:
            break

    source_hashes_end = source_hashes()
    result = {
        "schema": "arc2-v5-feature-neighbor-transform-loo.v4",
        "experiment_id": "ARC26-ARC2-V5-P5-FEATURE-NEIGHBOR-TRANSFORM-SCOPED-PRIOR-LOO",
        "data_source": "public ARC-AGI-2 training split and fixed training-only runtime prior",
        "feature_based_selection_only": True,
        "task_identifiers_or_grids_saved": False,
        "heldout_output_passed_to_solver": False,
        "evaluation_solutions_read_by_parent_only": True,
        "fallback_counted_correct": False,
        "candidate_program_families": ["D4 orientation", "color map", "crop background", "integer scale", "uniform downscale", "tile"],
        "selection_features": ["grid dimensions", "aspect ratio", "color-count profile", "foreground occupancy and bounds", "connected-component profile", "row and column transition rates"],
        "applicability_limit": "1.5 times the largest leave-one-out nearest-neighbor distance among current-task training inputs",
        "prior_examples": len(prior),
        "prior_context_mode": args.prior_context,
        "prior_in_scope_checks": prior_in_scope,
        "prior_out_of_scope_checks": prior_out_of_scope,
        "prior_wrong_checks": prior_wrong_checks,
        "prior_conflict_folds": prior_conflict_folds,
        "prior_source_tasks_excluded": len(prior_sources),
        "eligible_tasks": eligible,
        "loo_folds": folds,
        "complete": not stopped,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "training_manifest_sha256": manifest.hexdigest(),
        "candidate_folds": candidate_folds,
        "candidate_unique_consensus_exact": candidate_exact,
        "hds_gate_calls": gate_calls,
        "hds_gate_admitted": gate_admitted,
        "hds_gate_rejected": gate_rejected,
        "hds_gate_states": dict(gate_states),
        "paired_hds_calls": candidate_unique,
        "paired_first_exact": baseline_exact,
        "paired_first_fallback": baseline_fallback,
        "paired_second_exact": baseline_second_exact,
        "paired_before_exact_union": paired_before,
        "paired_after_exact_union": paired_after,
        "paired_delta_exact": paired_after - paired_before,
        "paired_gains": gains,
        "paired_regressions": regressions,
        "source_sha256_start": source_hashes_start,
        "source_sha256_end": source_hashes_end,
        "source_hashes_unchanged": source_hashes_start == source_hashes_end,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
