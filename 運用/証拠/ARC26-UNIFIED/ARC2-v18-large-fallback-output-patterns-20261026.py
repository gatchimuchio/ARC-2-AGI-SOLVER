"""Aggregate offline output-pattern diagnostics, focused on large fallbacks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from collections import defaultdict


ROOT = Path(__file__).resolve().parents[3]
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v16-periodic-tiling-20261026/full-runtime-output-20261026/submission.json"
OUTPUT = Path(__file__).with_suffix(".json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def d4_names(grid):
    rotated = [row[:] for row in grid]
    values = []
    for _ in range(4):
        values.append(rotated)
        rotated = [list(row) for row in zip(*rotated[::-1])]
    reflected = [row[::-1] for row in grid]
    for _ in range(4):
        values.append(reflected)
        reflected = [list(row) for row in zip(*reflected[::-1])]
    return values


def feature(input_grid, output_grid):
    ih, iw = len(input_grid), len(input_grid[0])
    oh, ow = len(output_grid), len(output_grid[0])
    input_colors = {value for row in input_grid for value in row}
    output_colors = {value for row in output_grid for value in row}
    same_shape = (ih, iw) == (oh, ow)
    changed = None
    bijective_color_map = False
    if same_shape:
        changed = sum(input_grid[r][c] != output_grid[r][c] for r in range(ih) for c in range(iw))
        mapping, reverse = {}, {}
        bijective_color_map = True
        for r in range(ih):
            for c in range(iw):
                old, new = input_grid[r][c], output_grid[r][c]
                if old in mapping and mapping[old] != new or new in reverse and reverse[new] != old:
                    bijective_color_map = False
                    break
                mapping[old], reverse[new] = new, old
            if not bijective_color_map:
                break
    exact_d4 = any(input_grid == transformed for transformed in d4_names(output_grid))
    denom = max(1, ih * iw)
    ratio = changed / denom if changed is not None else None
    if ratio is None:
        change_band = "shape_changed"
    elif ratio == 0:
        change_band = "unchanged"
    elif ratio <= 0.05:
        change_band = "<=5% cells changed"
    elif ratio <= 0.20:
        change_band = "5-20% cells changed"
    elif ratio <= 0.50:
        change_band = "20-50% cells changed"
    else:
        change_band = ">50% cells changed"
    return {
        "same_shape": same_shape,
        "input_palette_preserved": output_colors.issubset(input_colors),
        "same_palette": input_colors == output_colors,
        "new_output_colors": bool(output_colors - input_colors),
        "bijective_same_size_color_map": bijective_color_map,
        "exact_whole_grid_d4": exact_d4,
        "change_band": change_band,
    }


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    labels = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in TRAINING.glob("*.json")
    }
    buckets = defaultdict(list)
    for task_id, task in challenge.items():
        for index, pair in enumerate(task["test"]):
            input_grid = pair["input"]
            target = labels[task_id][index]
            predicted = baseline[task_id][index]
            correct = target in (predicted["attempt_1"], predicted["attempt_2"])
            feature_row = feature(input_grid, target)
            cells = len(input_grid) * len(input_grid[0])
            size = "<=100 cells" if cells <= 100 else ">100 cells"
            status = "baseline exact" if correct else "baseline wrong"
            for dimension in (size, "all"):
                buckets[(dimension, status)].append(feature_row)

    summary = {}
    for (dimension, status), rows in sorted(buckets.items()):
        summary.setdefault(dimension, {})[status] = {
            "examples": len(rows),
            "same_shape": sum(row["same_shape"] for row in rows),
            "input_palette_preserved": sum(row["input_palette_preserved"] for row in rows),
            "same_palette": sum(row["same_palette"] for row in rows),
            "new_output_colors": sum(row["new_output_colors"] for row in rows),
            "bijective_same_size_color_map": sum(row["bijective_same_size_color_map"] for row in rows),
            "exact_whole_grid_d4": sum(row["exact_whole_grid_d4"] for row in rows),
            "change_bands": dict(sorted({band: sum(row["change_band"] == band for row in rows) for band in {row["change_band"] for row in rows}}.items())),
        }
    report = {
        "schema": "arc2-v18-large-fallback-output-patterns-v1",
        "challenge_tasks": len(challenge),
        "challenge_examples": sum(len(task["test"]) for task in challenge.values()),
        "focus": "large means test input area greater than 100 cells",
        "data_use": "public ARC-AGI-2 training outputs used for offline aggregate error analysis only",
        "runtime_received_targets": False,
        "per_task_ids_or_grids_saved": False,
        "baseline_source": "complete v16 runtime output",
        "challenge_sha256": sha(CHALLENGE),
        "baseline_submission_sha256": sha(BASELINE),
        "aggregates": summary,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["aggregates"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
