"""Probe generic object centrality and border-clearance selectors."""
from __future__ import annotations

from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE_V19 = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v19-local-context-second-20261026/full-runtime/submission.json"
OUT = Path(__file__).with_suffix(".json")

SEGMENTATIONS = ((4, True), (8, True), (4, False), (8, False))
ORIENTATIONS = ("id", "r90", "r180", "r270", "fh", "fv", "t", "at")
NEW_SELECTORS = (
    "center_distance:unique", "center_distance:min", "center_distance:max",
    "border_clearance:unique", "border_clearance:min", "border_clearance:max",
    "border_count:unique", "border_count:min", "border_count:max",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid(grid: object) -> bool:
    return (
        isinstance(grid, list) and 1 <= len(grid) <= 30
        and all(
            isinstance(row, list) and 1 <= len(row) <= 30
            and len(row) == len(grid[0])
            and all(type(color) is int and 0 <= color <= 9 for color in row)
            for row in grid
        )
    )


def _orient(grid, name):
    transpose = [list(row) for row in zip(*grid)]
    return {
        "id": [row[:] for row in grid],
        "r90": [list(row) for row in zip(*grid[::-1])],
        "r180": [row[::-1] for row in grid[::-1]],
        "r270": [list(row) for row in zip(*grid)][::-1],
        "fh": [row[::-1] for row in grid],
        "fv": grid[::-1],
        "t": transpose,
        "at": [row[::-1] for row in transpose[::-1]],
    }[name]


def _shape_signature(cells):
    transforms = (
        lambda y, x: (y, x), lambda y, x: (x, -y),
        lambda y, x: (-y, -x), lambda y, x: (-x, y),
        lambda y, x: (y, -x), lambda y, x: (-y, x),
        lambda y, x: (x, y), lambda y, x: (-x, -y),
    )
    signatures = []
    for transform in transforms:
        points = [transform(y, x) for y, x in cells]
        min_y = min(y for y, _ in points)
        min_x = min(x for _, x in points)
        signatures.append(tuple(sorted((y - min_y, x - min_x) for y, x in points)))
    original = tuple(sorted((y - min(y for y, _ in cells), x - min(x for _, x in cells)) for y, x in cells))
    return min(signatures), sum(signature == original for signature in signatures)


def _hole_count(occupied, height, width):
    empty = {
        (y, x)
        for y in range(height)
        for x in range(width)
        if (y, x) not in occupied
    }
    outside = set()
    pending = [
        point for point in empty
        if point[0] in (0, height - 1) or point[1] in (0, width - 1)
    ]
    outside.update(pending)
    while pending:
        y, x = pending.pop()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            point = (y + dy, x + dx)
            if point in empty and point not in outside:
                outside.add(point)
                pending.append(point)
    holes = empty - outside
    count = 0
    while holes:
        count += 1
        pending = [holes.pop()]
        while pending:
            y, x = pending.pop()
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                point = (y + dy, x + dx)
                if point in holes:
                    holes.remove(point)
                    pending.append(point)
    return count


def _components(grid, connectivity, same_color):
    height, width = len(grid), len(grid[0])
    counts = Counter(color for row in grid for color in row)
    background = min(counts, key=lambda color: (-counts[color], color))
    visited = set()
    result = []
    deltas = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if connectivity == 8:
        deltas += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    for row in range(height):
        for column in range(width):
            color = grid[row][column]
            if color == background or (row, column) in visited:
                continue
            pending = [(row, column)]
            visited.add((row, column))
            cells = []
            while pending:
                y, x = pending.pop()
                cells.append((y, x))
                for dy, dx in deltas:
                    yy, xx = y + dy, x + dx
                    if not (0 <= yy < height and 0 <= xx < width):
                        continue
                    if (yy, xx) in visited or grid[yy][xx] == background:
                        continue
                    if same_color and grid[yy][xx] != color:
                        continue
                    visited.add((yy, xx))
                    pending.append((yy, xx))
            top = min(y for y, _ in cells)
            bottom = max(y for y, _ in cells)
            left = min(x for _, x in cells)
            right = max(x for _, x in cells)
            local_cells = {(y-top, x-left) for y, x in cells}
            box_h, box_w = bottom-top+1, right-left+1
            shape, symmetry = _shape_signature(local_cells)
            perimeter = sum(
                (y+dy, x+dx) not in local_cells
                for y, x in local_cells
                for dy, dx in ((-1,0),(1,0),(0,-1),(0,1))
            )
            colors = {grid[y][x] for y, x in cells}
            center_row_delta = (
                2 * sum(y for y, _ in cells) - len(cells) * (height - 1)
            )
            center_column_delta = (
                2 * sum(x for _, x in cells) - len(cells) * (width - 1)
            )
            border_clearance = min(
                min(y, x, height - 1 - y, width - 1 - x)
                for y, x in cells
            )
            touched_borders = {
                border
                for y, x in cells
                for border, touches in (
                    ("top", y == 0),
                    ("bottom", y == height - 1),
                    ("left", x == 0),
                    ("right", x == width - 1),
                )
                if touches
            }
            result.append({
                "area": len(cells),
                "box": box_h * box_w,
                "height": box_h,
                "width": box_w,
                "color_count": len(colors),
                "shape": shape,
                "perimeter": perimeter,
                "holes": _hole_count(local_cells, box_h, box_w),
                "symmetry": symmetry,
                "aspect": Fraction(box_w, box_h),
                "solidity": Fraction(len(cells), box_h * box_w),
                "touches_border": any(
                    y in (0, height-1) or x in (0, width-1)
                    for y, x in cells
                ),
                "center_distance": Fraction(
                    center_row_delta ** 2 + center_column_delta ** 2,
                    4 * len(cells) ** 2,
                ),
                "border_clearance": border_clearance,
                "border_count": len(touched_borders),
                "crop": [line[left:right+1] for line in grid[top:bottom+1]],
            })
    return result


def _select(objects, selector):
    if not objects:
        return None
    feature, mode = selector.split(":")
    values = [obj[feature] for obj in objects]
    if mode == "unique":
        frequencies = Counter(values)
        singletons = [index for index, value in enumerate(values) if frequencies[value] == 1]
        if len(singletons) != 1 or not any(count > 1 for count in frequencies.values()):
            return None
        return objects[singletons[0]]
    extreme = min(values) if mode == "min" else max(values)
    matches = [obj for obj, value in zip(objects, values, strict=True) if value == extreme]
    return matches[0] if len(matches) == 1 else None


def _fit_color_map(source, target, mapping):
    if len(source) != len(target) or len(source[0]) != len(target[0]):
        return False
    for sr, tr in zip(source, target, strict=True):
        for a, b in zip(sr, tr, strict=True):
            old = mapping.get(a)
            if old is not None and old != b:
                return False
            mapping[a] = b
    return True


def _fit(teachers):
    if len(teachers) < 2 or any(
        not isinstance(pair, dict)
        or not _valid(pair.get("input"))
        or not _valid(pair.get("output"))
        for pair in teachers
    ):
        return []
    cache = [
        {
            "output": pair["output"],
            "objects": {
                seg: _components(pair["input"], *seg)
                for seg in SEGMENTATIONS
            },
        }
        for pair in teachers
    ]
    models = []
    for seg in SEGMENTATIONS:
        for selector in NEW_SELECTORS:
            for orientation in ORIENTATIONS:
                color_map = {}
                for pair in cache:
                    obj = _select(pair["objects"][seg], selector)
                    if obj is None or not _fit_color_map(
                        _orient(obj["crop"], orientation), pair["output"], color_map
                    ):
                        break
                else:
                    models.append((seg, selector, orientation, color_map.copy()))
    return models


def _predict(model, grid):
    seg, selector, orientation, color_map = model
    obj = _select(_components(grid, *seg), selector)
    if obj is None:
        return None
    result = [
        [color_map.get(color, color) for color in row]
        for row in _orient(obj["crop"], orientation)
    ]
    return result if _valid(result) else None


def _candidate(models, grid):
    counts = Counter()
    grids = {}
    for model in models:
        output = _predict(model, grid)
        if output is None:
            continue
        key = tuple(tuple(row) for row in output)
        counts[key] += 1
        grids[key] = output
    if not counts:
        return None, 0, 0
    top = max(counts.values())
    winners = [key for key, votes in counts.items() if votes == top]
    return (grids[winners[0]] if top >= 2 and len(winners) == 1 else None), top, sum(counts.values())


def main():
    if OUT.exists():
        raise SystemExit(f"refusing to overwrite {OUT}")
    import sys
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2.物体抽出候補 import ObjectExtractionCandidate

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline_v19 = json.loads(BASELINE_V19.read_text(encoding="utf-8"))
    v20_rows = {}
    extension_rows = {}
    challenge_candidate_examples = challenge_selected = 0
    for task_id, task in sorted(challenge.items()):
        old_model = ObjectExtractionCandidate(task["train"])
        new_models = _fit(task["train"])
        base_rows = [dict(row) for row in baseline_v19[task_id]]
        new_rows = []
        for index, pair in enumerate(task["test"]):
            old_candidate, _ = old_model.candidate(pair["input"])
            if (
                old_candidate is not None
                and old_candidate != base_rows[index]["attempt_1"]
                and base_rows[index]["attempt_1"] == base_rows[index]["attempt_2"]
            ):
                base_rows[index]["attempt_2"] = old_candidate
            existing_candidate, _ = old_model.outlier_candidate(pair["input"])
            if (
                existing_candidate is not None
                and existing_candidate != base_rows[index]["attempt_1"]
                and base_rows[index]["attempt_1"] == base_rows[index]["attempt_2"]
            ):
                base_rows[index]["attempt_2"] = existing_candidate
            candidate, votes, _applicable = _candidate(new_models, pair["input"])
            updated = dict(base_rows[index])
            if candidate is not None and candidate != updated["attempt_1"]:
                challenge_candidate_examples += 1
                if candidate != updated["attempt_2"] and updated["attempt_1"] == updated["attempt_2"]:
                    updated["attempt_2"] = candidate
                    challenge_selected += 1
            new_rows.append(updated)
        v20_rows[task_id] = base_rows
        extension_rows[task_id] = new_rows

    # Generate all LOO predictions before looking at held-out outputs.
    loo_proposals = []
    eligible_folds = 0
    for path in sorted(SOURCE_ROOT.glob("*.json")):
        task = json.loads(path.read_text(encoding="utf-8"))
        pairs = task.get("train", [])
        if len(pairs) < 3:
            continue
        for held_index, held in enumerate(pairs):
            eligible_folds += 1
            teachers = [pair for index, pair in enumerate(pairs) if index != held_index]
            candidate, votes, applicable = _candidate(_fit(teachers), held["input"])
            if candidate is not None and votes >= 2 and candidate != held["input"]:
                loo_proposals.append((held["input"], held["output"], candidate))

    # Public labels are read only after both challenge and LOO candidate generation.
    targets = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in SOURCE_ROOT.glob("*.json")
    }
    base_exact_examples = extension_exact_examples = 0
    base_exact_tasks = extension_exact_tasks = 0
    for task_id in challenge:
        base_correct = [
            row["attempt_1"] == target or row["attempt_2"] == target
            for row, target in zip(v20_rows[task_id], targets[task_id], strict=True)
        ]
        current_correct = [
            row["attempt_1"] == target or row["attempt_2"] == target
            for row, target in zip(extension_rows[task_id], targets[task_id], strict=True)
        ]
        base_exact_examples += sum(base_correct)
        extension_exact_examples += sum(current_correct)
        base_exact_tasks += all(base_correct)
        extension_exact_tasks += all(current_correct)
    identity_exact = sum(input_grid == target for input_grid, target, _ in loo_proposals)
    loo_candidate_exact = sum(candidate == target for _, target, candidate in loo_proposals)
    loo_proposal_count = len(loo_proposals)
    report = {
        "schema": "arc2-object-spatial-v23-probe-v1",
        "challenge_tasks": len(challenge),
        "challenge_examples": sum(len(task["test"]) for task in challenge.values()),
        "challenge_v21.1_baseline": {
            "exact_tasks": base_exact_tasks,
            "exact_examples": base_exact_examples,
        },
        "challenge_spatial_after_v21.1": {
            "exact_tasks": extension_exact_tasks,
            "exact_examples": extension_exact_examples,
            "candidate_examples": challenge_candidate_examples,
            "selected_duplicate_slots": challenge_selected,
            "newly_correct_tasks": extension_exact_tasks - base_exact_tasks,
            "newly_correct_examples": extension_exact_examples - base_exact_examples,
            "regressed_tasks": sum(
                all(
                    row["attempt_1"] == target or row["attempt_2"] == target
                    for row, target in zip(extension_rows[t], targets[t], strict=True)
                )
                is False
                and all(
                    row["attempt_1"] == target or row["attempt_2"] == target
                    for row, target in zip(v20_rows[t], targets[t], strict=True)
                )
                for t in challenge
            ),
        },
        "loo_eligible_folds": eligible_folds,
        "loo_candidate_proposal_folds": loo_proposal_count,
        "loo_identity_exact_among_proposals": identity_exact,
        "loo_candidate_exact": loo_candidate_exact,
        "loo_candidate_delta_vs_identity": loo_candidate_exact - identity_exact,
        "loo_targets_passed_to_candidate_generator": False,
        "challenge_targets_read_after_all_candidate_generation": True,
        "per_task_predictions_or_targets_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "challenge": _sha(CHALLENGE),
            "baseline_v19": _sha(BASELINE_V19),
            "current_object_candidate": _sha(ROOT / "接続/ARC2/物体抽出候補.py"),
        },
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
