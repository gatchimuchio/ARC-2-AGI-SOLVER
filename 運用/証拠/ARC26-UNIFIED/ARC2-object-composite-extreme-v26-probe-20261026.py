"""Probe lexicographic min/max selectors on v25 composite-proposal LOO folds."""
from __future__ import annotations

from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "運用/証拠/ARC26-UNIFIED"
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
PROBE = EVIDENCE / "ARC2-object-palette-v24-probe-20261026.py"
V25_BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v25-composite-palette-second-20261026"
OUTPUT = Path(__file__).with_suffix(".json")
COMPOSITES = (
    "area_palette", "box_palette", "shape_palette", "aspect_palette",
    "holes_palette", "perimeter_palette", "symmetry_palette",
    "shape_area", "shape_box", "shape_dominant_color",
    "area_dominant_color", "shape_color_count", "area_dominant_count",
)
EXTREME_FEATURES = (
    "area_palette", "box_palette", "aspect_palette", "holes_palette",
    "perimeter_palette", "symmetry_palette", "shape_area", "shape_box",
    "area_dominant_color", "area_dominant_count",
)
EXTREME_SELECTORS = tuple(
    f"{feature}:{direction}"
    for feature in EXTREME_FEATURES
    for direction in ("min", "max")
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_v25(tasks: dict):
    with tempfile.TemporaryDirectory(prefix="arc2-v25-extreme-") as temp_name:
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
                str(V25_BUILD / "solve.py"),
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
            raise RuntimeError(f"exact v25 bundle failed: {process.returncode}")
        predictions = json.loads(
            (output_dir / "submission.json").read_text(encoding="utf-8")
        )
        audit = json.loads(
            (output_dir / "submission_audit.json").read_text(encoding="utf-8")
        )
    return predictions, audit


def _extend_probe(probe):
    original_components = probe._components

    def extended_components(grid, connectivity, same_color):
        objects = original_components(grid, connectivity, same_color)
        for obj in objects:
            obj.update({
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
            })
        return objects

    probe._components = extended_components
    probe.NEW_SELECTORS = probe.NEW_SELECTORS + tuple(
        f"{feature}:unique" for feature in COMPOSITES
    )


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("arc2_v26_extreme_probe", PROBE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load palette probe")
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    _extend_probe(probe)

    proposals = []
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
            candidate, votes, _ = probe._candidate(
                probe._fit(teachers), held["input"]
            )
            if candidate is not None and votes >= 2 and candidate != held["input"]:
                proposals.append((path, held_index, teachers, held["input"]))
    if len(proposals) != 43:
        raise RuntimeError(f"v25 proposal count drifted: {len(proposals)}")

    probe.NEW_SELECTORS += EXTREME_SELECTORS
    tasks = {
        f"fold_{index:05d}": {
            "train": teachers,
            "test": [{"input": held_input}],
        }
        for index, (_, _, teachers, held_input) in enumerate(proposals)
    }
    baseline, audit = _run_v25(tasks)

    duplicate_slots = candidate_proposals = applied = 0
    baseline_exact = candidate_exact = newly_correct = newly_wrong = 0
    for index, (path, held_index, teachers, held_input) in enumerate(proposals):
        key = f"fold_{index:05d}"
        row = baseline[key][0]
        first, second = row["attempt_1"], row["attempt_2"]
        duplicate_slots += second == first
        models = probe._fit(teachers)
        candidate, votes, _ = probe._candidate(models, held_input)
        after_second = second
        if (
            second == first
            and candidate is not None
            and votes >= 2
            and candidate != first
        ):
            candidate_proposals += 1
            after_second = candidate
            applied += candidate != second

        target = json.loads(path.read_text(encoding="utf-8"))["train"][held_index]["output"]
        before_exact = first == target or second == target
        after_exact = first == target or after_second == target
        baseline_exact += before_exact
        candidate_exact += after_exact
        newly_correct += after_exact and not before_exact
        newly_wrong += before_exact and not after_exact

    report = {
        "schema": "arc2-object-composite-extreme-v26-probe-v1",
        "eligible_folds": eligible,
        "v25_composite_proposal_folds": len(proposals),
        "exact_v25_bundle_evaluation_folds": len(baseline),
        "v25_bundle_fallbacks": audit.get("fallback_count"),
        "composite_extreme_selectors": list(EXTREME_SELECTORS),
        "v25_duplicate_attempt2_slots": duplicate_slots,
        "extreme_candidate_proposals_on_duplicate_slots": candidate_proposals,
        "extreme_candidate_slots_applied": applied,
        "v25_exact_on_proposals": baseline_exact,
        "composite_extreme_exact_on_proposals": candidate_exact,
        "newly_correct": newly_correct,
        "newly_wrong": newly_wrong,
        "net_delta": candidate_exact - baseline_exact,
        "regressions": newly_wrong,
        "heldout_outputs_passed_to_candidate_generator_or_runtime": False,
        "targets_read_after_exact_v25_bundle_output": True,
        "fold_ids_predictions_or_targets_saved": False,
        "temporary_inputs_outputs_and_payloads_removed": True,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "proposal_probe": _sha(PROBE),
            "v25_build_manifest": _sha(V25_BUILD / "build-manifest.json"),
        },
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
