"""Probe majority-color connected regions as generic ARC2 object candidates."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from collections import Counter

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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _add_background_components(probe, grid, connectivity, same_color):
    objects = probe._components_base(grid, connectivity, same_color)
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
    if not same_color:
        return objects
    height, width = len(grid), len(grid[0])
    counts = Counter(color for row in grid for color in row)
    background = min(counts, key=lambda color: (-counts[color], color))
    visited = set()
    deltas = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if connectivity == 8:
        deltas += [(-1, -1), (-1, 1), (1, -1), (1, 1)]

    for row in range(height):
        for column in range(width):
            if grid[row][column] != background or (row, column) in visited:
                continue
            pending = [(row, column)]
            visited.add((row, column))
            cells = []
            while pending:
                y, x = pending.pop()
                cells.append((y, x))
                for dy, dx in deltas:
                    yy, xx = y + dy, x + dx
                    if (
                        0 <= yy < height
                        and 0 <= xx < width
                        and (yy, xx) not in visited
                        and grid[yy][xx] == background
                    ):
                        visited.add((yy, xx))
                        pending.append((yy, xx))

            top = min(y for y, _ in cells)
            bottom = max(y for y, _ in cells)
            left = min(x for _, x in cells)
            right = max(x for _, x in cells)
            local_cells = {(y - top, x - left) for y, x in cells}
            object_height, object_width = bottom - top + 1, right - left + 1
            color_counts = Counter(grid[y][x] for y, x in cells)
            palette = tuple(sorted(color_counts))
            dominant_color = min(
                color_counts, key=lambda color: (-color_counts[color], color)
            )
            shape, symmetry = probe._shape_signature(local_cells)
            perimeter = sum(
                (y + dy, x + dx) not in local_cells
                for y, x in local_cells
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))
            )
            holes = probe._hole_count(local_cells, object_height, object_width)
            aspect = probe.Fraction(object_width, object_height)
            area = len(cells)
            box = object_height * object_width
            colors = set(palette)
            objects.append({
                "area": area,
                "box": box,
                "height": object_height,
                "width": object_width,
                "color_count": len(colors),
                "palette": palette,
                "dominant_color": dominant_color,
                "dominant_count": color_counts[dominant_color],
                "palette_frequency": sum(
                    sum(row_values.count(color) for row_values in grid)
                    for color in palette
                ),
                "shape": shape,
                "perimeter": perimeter,
                "holes": holes,
                "symmetry": symmetry,
                "aspect": aspect,
                "solidity": probe.Fraction(area, box),
                "touches_border": any(
                    y in (0, height - 1) or x in (0, width - 1)
                    for y, x in cells
                ),
                "crop": [line[left:right + 1] for line in grid[top:bottom + 1]],
                "area_palette": (area, palette),
                "box_palette": (box, palette),
                "shape_palette": (shape, palette),
                "aspect_palette": (aspect, palette),
                "holes_palette": (holes, palette),
                "perimeter_palette": (perimeter, palette),
                "symmetry_palette": (symmetry, palette),
                "shape_area": (shape, area),
                "shape_box": (shape, box),
                "shape_dominant_color": (shape, dominant_color),
                "area_dominant_color": (area, dominant_color),
                "shape_color_count": (shape, len(colors)),
                "area_dominant_count": (area, color_counts[dominant_color]),
            })
    return objects


def _run_v25(tasks):
    with tempfile.TemporaryDirectory(prefix="arc2-v25-background-") as temp_name:
        temp = Path(temp_name)
        challenges = temp / "challenges.json"
        output_dir = temp / "output"
        challenges.write_text(json.dumps(tasks, ensure_ascii=False), encoding="utf-8")
        env = {
            **os.environ,
            "PYTHONUTF8": "1",
            "ARC2_PAYLOAD_ROOT": str(temp / "payload"),
        }
        process = subprocess.run(
            [
                sys.executable,
                str(V25_BUILD / "solve.py"),
                "--challenges",
                str(challenges),
                "--output-dir",
                str(output_dir),
            ],
            cwd=ROOT,
            env=env,
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


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("arc2_v27_background_probe", PROBE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load object proposal probe")
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    probe.Fraction = __import__("fractions").Fraction
    base_components = probe._components
    probe._components = lambda grid, connectivity, same_color: _add_background_components(
        probe, grid, connectivity, same_color
    )
    probe._components_base = base_components
    probe.NEW_SELECTORS = probe.NEW_SELECTORS + tuple(
        f"{feature}:unique" for feature in COMPOSITES
    )

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
                proposals.append(
                    (path, held_index, teachers, held["input"], candidate)
                )

    tasks = {
        f"fold_{index:05d}": {
            "train": teachers,
            "test": [{"input": held_input}],
        }
        for index, (_, _, teachers, held_input, _) in enumerate(proposals)
    }
    if not tasks:
        predictions, audit = {}, {"fallback_count": 0}
    else:
        predictions, audit = _run_v25(tasks)

    base_exact = candidate_exact = applied = newly_correct = newly_wrong = 0
    duplicate_slots = 0
    for index, (path, held_index, _, _, candidate) in enumerate(proposals):
        row = predictions[f"fold_{index:05d}"][0]
        first, second = row["attempt_1"], row["attempt_2"]
        after_second = second
        if (
            second == first
            and candidate is not None
            and candidate != first
        ):
            after_second = candidate
            applied += candidate != second
        target = json.loads(path.read_text(encoding="utf-8"))["train"][held_index]["output"]
        before = first == target or second == target
        after = first == target or after_second == target
        base_exact += before
        candidate_exact += after
        newly_correct += after and not before
        newly_wrong += before and not after
        duplicate_slots += first == second

    report = {
        "schema": "arc2-background-component-v27-probe-v1",
        "eligible_folds": eligible,
        "background_component_proposal_folds": len(proposals),
        "exact_v25_bundle_evaluation_folds": len(predictions),
        "v25_bundle_fallbacks": audit.get("fallback_count"),
        "v25_duplicate_attempt2_slots": duplicate_slots,
        "v25_exact_on_background_proposals": base_exact,
        "background_candidate_exact_on_proposals": candidate_exact,
        "attempt2_changes": applied,
        "newly_correct": newly_correct,
        "newly_wrong": newly_wrong,
        "net_delta": candidate_exact - base_exact,
        "regressions": newly_wrong,
        "heldout_outputs_passed_to_candidate_generator_or_runtime": False,
        "targets_read_after_exact_v25_bundle_outputs": True,
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
