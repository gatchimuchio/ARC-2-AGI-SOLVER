"""Evaluate composite object-feature selectors on palette proposal LOO folds."""
from __future__ import annotations

from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "運用/証拠/ARC26-UNIFIED"
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
PROBE = EVIDENCE / "ARC2-object-palette-v24-probe-20261026.py"
V24_BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v24-palette-second-20261026"
OUTPUT = Path(__file__).with_suffix(".json")

COMPOSITES = (
    "area_palette", "box_palette", "shape_palette", "aspect_palette",
    "holes_palette", "perimeter_palette", "symmetry_palette",
    "shape_area", "shape_box", "shape_dominant_color",
    "area_dominant_color", "shape_color_count", "area_dominant_count",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_exact_v24(probe, folds):
    import os
    import subprocess
    import tempfile

    tasks = {
        f"fold_{index:05d}": {
            "train": teachers,
            "test": [{"input": held_input}],
        }
        for index, (teachers, held_input, _) in enumerate(folds)
    }
    with tempfile.TemporaryDirectory(prefix="arc2-v24-composite-") as temp_name:
        temp = Path(temp_name)
        challenge_path = temp / "challenges.json"
        output_dir = temp / "output"
        challenge_path.write_text(
            json.dumps(tasks, ensure_ascii=False), encoding="utf-8"
        )
        environment = {
            **os.environ,
            "PYTHONUTF8": "1",
            "ARC2_PAYLOAD_ROOT": str(temp / "payload"),
        }
        process = subprocess.run(
            [
                sys.executable,
                str(V24_BUILD / "solve.py"),
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
            timeout=900,
            check=False,
        )
        if process.returncode:
            raise RuntimeError(f"exact v24 bundle failed: {process.returncode}")
        predictions = json.loads(
            (output_dir / "submission.json").read_text(encoding="utf-8")
        )
    return tasks, predictions


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("arc2_v24_composite_probe", PROBE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load palette proposal probe")
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)

    original_components = probe._components

    def extended_components(grid, connectivity, same_color):
        objects = original_components(grid, connectivity, same_color)
        for obj in objects:
            values = {
                "area_palette": (obj["area"], obj["palette"]),
                "box_palette": (obj["box"], obj["palette"]),
                "shape_palette": (obj["shape"], obj["palette"]),
                "aspect_palette": (obj["aspect"], obj["palette"]),
                "holes_palette": (obj["holes"], obj["palette"]),
                "perimeter_palette": (obj["perimeter"], obj["palette"]),
                "symmetry_palette": (obj["symmetry"], obj["palette"]),
                "shape_area": (obj["shape"], obj["area"]),
                "shape_box": (obj["shape"], obj["box"]),
                "shape_dominant_color": (obj["shape"], obj["dominant_color"]),
                "area_dominant_color": (obj["area"], obj["dominant_color"]),
                "shape_color_count": (obj["shape"], obj["color_count"]),
                "area_dominant_count": (obj["area"], obj["dominant_count"]),
            }
            obj.update(values)
        return objects

    folds = []
    eligible = 0
    for path in sorted(SOURCE_ROOT.glob("*.json")):
        task = json.loads(path.read_text(encoding="utf-8"))
        pairs = task.get("train", [])
        if len(pairs) < 3:
            continue
        for held_index, held in enumerate(pairs):
            eligible += 1
            teachers = [
                pair for index, pair in enumerate(pairs) if index != held_index
            ]
            baseline_models = probe._fit(teachers)
            candidate, votes, _ = probe._candidate(
                baseline_models, held["input"]
            )
            if candidate is not None and votes >= 2 and candidate != held["input"]:
                folds.append((teachers, held["input"], held["output"]))
    if len(folds) != 40:
        raise RuntimeError(f"palette proposal count drifted: {len(folds)}")

    probe._components = extended_components
    probe.NEW_SELECTORS = probe.NEW_SELECTORS + tuple(
        f"{feature}:unique" for feature in COMPOSITES
    )
    tasks, base = _run_exact_v24(probe, folds)
    proposals = applied = newly_correct = newly_wrong = candidate_exact = 0
    duplicate_slots = 0
    for index, (teachers, held_input, target) in enumerate(folds):
        key = f"fold_{index:05d}"
        first = base[key][0]["attempt_1"]
        second = base[key][0]["attempt_2"]
        if second == first:
            duplicate_slots += 1
        composite_models = probe._fit(teachers)
        candidate, votes, _ = probe._candidate(composite_models, held_input)
        before_exact = first == target or second == target
        after_second = second
        if (
            second == first
            and candidate is not None
            and votes >= 2
            and candidate != first
        ):
            proposals += 1
            after_second = candidate
            applied += 1
        after_exact = first == target or after_second == target
        candidate_exact += after_exact
        newly_correct += after_exact and not before_exact
        newly_wrong += before_exact and not after_exact

    baseline_exact = 0
    for index, (_, _, target) in enumerate(folds):
        row = base[f"fold_{index:05d}"][0]
        baseline_exact += row["attempt_1"] == target or row["attempt_2"] == target

    report = {
        "schema": "arc2-object-composite-palette-v25-probe-v1",
        "eligible_folds": eligible,
        "palette_proposal_folds": len(folds),
        "exact_v24_bundle_folds": len(base),
        "composite_feature_pairs": list(COMPOSITES),
        "v24_duplicate_attempt2_slots": duplicate_slots,
        "composite_proposals_on_duplicate_slots": proposals,
        "composite_slots_applied": applied,
        "v24_exact_on_palette_proposals": baseline_exact,
        "composite_exact_on_palette_proposals": candidate_exact,
        "newly_correct": newly_correct,
        "newly_wrong": newly_wrong,
        "net_delta": candidate_exact - baseline_exact,
        "regressions": newly_wrong,
        "heldout_outputs_passed_to_candidate_generator_or_runtime": False,
        "targets_read_after_exact_v24_outputs": True,
        "fold_predictions_or_targets_saved": False,
        "temporary_inputs_outputs_and_payloads_removed": True,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "palette_probe": _sha(PROBE),
            "v24_build_manifest": _sha(V24_BUILD / "build-manifest.json"),
        },
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
