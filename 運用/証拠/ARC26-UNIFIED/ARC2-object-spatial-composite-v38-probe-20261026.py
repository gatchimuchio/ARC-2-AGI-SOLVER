"""Screen joint object geometry/position descriptors on LOO and challenge inputs."""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
OUTPUT = Path(__file__).with_suffix(".json")
NEW_SELECTORS = (
    "center_distance_palette:unique", "center_distance_shape:unique",
    "border_clearance_palette:unique", "border_clearance_shape:unique",
    "border_count_palette:unique", "border_count_shape:unique",
    "area_center_distance:unique", "shape_border_clearance:unique",
    "shape_border_count:unique", "perimeter_center_distance:unique",
    "solidity_border_clearance:unique", "touches_border_palette:unique",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _install_spatial_composites(module):
    original_components = module._components

    def extended_components(grid, connectivity, same_color, *, extended=False):
        objects = original_components(grid, connectivity, same_color, extended=extended)
        if not extended:
            return objects
        height, width = len(grid), len(grid[0])
        background = module._background(grid)
        for obj in objects:
            top, left = obj["top"], obj["left"]
            points = [
                (top + row, left + column)
                for row, line in enumerate(obj["crop"])
                for column, color in enumerate(line)
                if color != background
            ]
            area = len(points)
            row_delta = 2 * sum(row for row, _ in points) - area * (height - 1)
            column_delta = 2 * sum(column for _, column in points) - area * (width - 1)
            center_distance = Fraction(row_delta**2 + column_delta**2, 4 * area**2)
            border_clearance = min(
                min(row, column, height - 1 - row, width - 1 - column)
                for row, column in points
            )
            touched = {
                border
                for row, column in points
                for border, condition in (
                    ("top", row == 0), ("bottom", row == height - 1),
                    ("left", column == 0), ("right", column == width - 1),
                )
                if condition
            }
            obj.update({
                "center_distance": center_distance,
                "border_clearance": border_clearance,
                "border_count": len(touched),
                "center_distance_palette": (center_distance, obj["palette"]),
                "center_distance_shape": (center_distance, obj["shape"]),
                "border_clearance_palette": (border_clearance, obj["palette"]),
                "border_clearance_shape": (border_clearance, obj["shape"]),
                "border_count_palette": (len(touched), obj["palette"]),
                "border_count_shape": (len(touched), obj["shape"]),
                "area_center_distance": (obj["area"], center_distance),
                "shape_border_clearance": (obj["shape"], border_clearance),
                "shape_border_count": (obj["shape"], len(touched)),
                "perimeter_center_distance": (obj["perimeter"], center_distance),
                "solidity_border_clearance": (obj["solidity"], border_clearance),
                "touches_border_palette": (obj["touches_border"], obj["palette"]),
            })
        return objects

    module._components = extended_components
    module._PALETTE_SELECTORS = module._PALETTE_SELECTORS + NEW_SELECTORS


def _candidate(module, teachers, grid):
    models = module._fit(teachers, NEW_SELECTORS, extended=True)
    return module._candidate_from_models(models, grid, outlier=True)


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2 import 物体抽出候補

    _install_spatial_composites(物体抽出候補)
    eligible = proposals = challenge_fit = challenge_proposals = challenge_tasks_with_candidate = 0
    for path in sorted(SOURCE_ROOT.glob("*.json")):
        training = json.loads(path.read_text(encoding="utf-8")).get("train", [])
        if len(training) < 3:
            continue
        for held_index, held in enumerate(training):
            teachers = [pair for index, pair in enumerate(training) if index != held_index]
            eligible += 1
            prediction, record = _candidate(物体抽出候補, teachers, held["input"])
            proposals += prediction is not None and prediction != held["input"]

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    for task in challenge.values():
        train = task.get("train", [])
        task_has_candidate = False
        for pair in task.get("test", []):
            prediction, record = _candidate(物体抽出候補, train, pair["input"])
            challenge_fit += record.get("applicable_models", 0) > 0
            has_candidate = prediction is not None and prediction != pair["input"]
            challenge_proposals += has_candidate
            task_has_candidate |= has_candidate
        challenge_tasks_with_candidate += task_has_candidate
    report = {
        "schema": "arc2-object-spatial-composite-v38-probe-v1",
        "new_selectors": list(NEW_SELECTORS),
        "loo_eligible_folds": eligible,
        "loo_candidate_proposal_folds": proposals,
        "challenge_tasks": len(challenge),
        "challenge_examples": sum(len(task.get("test", [])) for task in challenge.values()),
        "challenge_examples_with_applicable_models": challenge_fit,
        "challenge_examples_with_candidate": challenge_proposals,
        "challenge_tasks_with_candidate": challenge_tasks_with_candidate,
        "heldout_outputs_read": False,
        "challenge_targets_read": False,
        "per_task_ids_grids_or_candidates_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "object_module_before_runtime_patch": _sha(ROOT / "接続/ARC2/物体抽出候補.py"),
            "challenge_inputs": _sha(CHALLENGE),
            "v28_build_manifest": _sha(ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v28-vote-ratio-second-20261026/build-manifest.json"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
