"""Evaluate a conservative multi-neighbor feature selector through actual HDS LOO."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
BASE_RUNNER = ROOT / "運用/証拠/ARC26-UNIFIED/P5_feature_neighbor_production_matched_LOO.py"


def neighborhood_consensus(self, grid, _expected):
    """Use all training-supported neighbors inside the task-local radius."""
    if not self_module.valid_grid(grid) or len(self.teachers) < 2:
        return None, {"reason": "insufficient_structural_support"}
    current = self_module._feature(grid)
    distances = [self_module._distance(current, feature) for feature in self.features]
    best_distance = min(distances)
    if best_distance > self.applicability_limit:
        return None, {"reason": "outside_training_feature_scope"}

    neighbors = [
        index
        for index, distance in enumerate(distances)
        if distance <= self.applicability_limit + 1e-12
    ]
    predictions = set()
    for index in neighbors:
        models = self.models[index]
        if not models:
            continue
        simplest_rank = models[0][0]
        for model in models:
            if model[0] != simplest_rank:
                break
            prediction = self_module.apply_model(model, grid)
            if self_module.valid_grid(prediction):
                predictions.add(self_module.key(prediction))
    if len(predictions) != 1:
        return None, {
            "reason": "ambiguous_or_unsupported_transform",
            "neighbor_count": len(neighbors),
        }
    return [list(row) for row in next(iter(predictions))], {
        "neighbor_count": len(neighbors),
    }


def main() -> int:
    global self_module
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budget-seconds", type=float, default=1500)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    raw_output = args.output.with_name(args.output.stem + ".raw.json")
    if raw_output.exists():
        raise SystemExit(f"refusing to overwrite {raw_output}")

    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("arc2_paired_feature_loo", BASE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the actual-runtime paired LOO runner")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    _current, _simple, self_module, _adapter = runner.load_modules()
    self_module.FeatureNeighborTransform.候補 = neighborhood_consensus

    sys.argv = [
        str(BASE_RUNNER),
        "--output",
        str(raw_output),
        "--budget-seconds",
        str(args.budget_seconds),
    ]
    runner.main()

    report = json.loads(raw_output.read_text(encoding="utf-8"))
    variant_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report["experiment_id"] = "ARC26-ARC2-V5-P5-FEATURE-NEIGHBOR-BALL-CONSENSUS-LOO"
    report["variant_id"] = "all input-feature neighbors within the existing task-local applicability radius"
    report["variant_runner_sha256"] = variant_sha256
    report["selection_policy"] = (
        "Keep each teacher's simplest fitted transform; pool predictions from every "
        "training input whose feature distance is within the existing task-local radius; "
        "emit only a single unanimous grid, then pass it through the unchanged HDS gate."
    )
    report["task_identifiers_or_grids_saved"] = False
    report["heldout_output_passed_to_solver"] = False
    report["fallback_counted_correct"] = False
    report["production_source_modified"] = False

    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({
        "report": str(args.output),
        "variant_runner_sha256": variant_sha256,
        "complete": report.get("complete"),
        "loo_folds_scanned": report.get("loo_folds_scanned"),
        "candidate_eligible_folds": report.get("candidate_eligible_folds"),
        "paired_baseline_exact": report.get("paired_baseline_exact"),
        "paired_candidate_exact": report.get("paired_candidate_exact"),
        "paired_delta_exact": report.get("paired_delta_exact"),
        "paired_regressions": report.get("paired_regressions"),
        "baseline_first_fallbacks": report.get("baseline_first_fallbacks"),
        "candidate_first_fallbacks": report.get("candidate_first_fallbacks"),
        "source_hashes_unchanged": report.get("source_hashes_unchanged"),
        "production_source_modified": report["production_source_modified"],
    }, ensure_ascii=False, indent=2))
    return 0 if report.get("complete") and report.get("source_hashes_unchanged") else 1


self_module = None


if __name__ == "__main__":
    raise SystemExit(main())
