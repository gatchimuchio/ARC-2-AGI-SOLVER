"""Probe train-fitted component extraction rules as alternate ARC2 answers."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v19-local-context-second-20261026/full-runtime/submission.json"
OUTPUT = Path(__file__).with_suffix(".json")
SEGMENTATIONS = ((4, True), (8, True), (4, False), (8, False))
SELECTORS = (
    "area:min", "area:max", "box:min", "box:max",
    "height:min", "height:max", "width:min", "width:max",
    "top:min", "top:max", "left:min", "left:max",
    "bottom:min", "bottom:max", "right:min", "right:max",
    "center_y:min", "center_y:max", "center_x:min", "center_x:max",
    "color_count:min", "color_count:max",
)
ORIENTATIONS = ("id", "r90", "r180", "r270", "fh", "fv", "t", "at")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid(grid):
    return (
        isinstance(grid, list) and 1 <= len(grid) <= 30
        and all(isinstance(row, list) and len(row) == len(grid[0])
                and 1 <= len(row) <= 30
                and all(type(c) is int and 0 <= c <= 9 for c in row)
                for row in grid)
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


def _background(grid):
    counts = Counter(c for row in grid for c in row)
    return min(counts, key=lambda c: (-counts[c], c))


def _components(grid, connectivity, same_color):
    height, width = len(grid), len(grid[0])
    background = _background(grid)
    visited = set()
    result = []
    deltas = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if connectivity == 8:
        deltas += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    for r in range(height):
        for c in range(width):
            color = grid[r][c]
            if color == background or (r, c) in visited:
                continue
            stack = [(r, c)]
            visited.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
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
                    stack.append((yy, xx))
            r0 = min(y for y, _ in cells); r1 = max(y for y, _ in cells)
            c0 = min(x for _, x in cells); c1 = max(x for _, x in cells)
            colors = {grid[y][x] for y, x in cells}
            result.append({
                "top": r0, "bottom": r1, "left": c0, "right": c1,
                "area": len(cells), "box": (r1-r0+1)*(c1-c0+1),
                "height": r1-r0+1, "width": c1-c0+1,
                "center_y": sum(y for y, _ in cells) / len(cells),
                "center_x": sum(x for _, x in cells) / len(cells),
                "color_count": len(colors),
                "crop": [row[c0:c1+1] for row in grid[r0:r1+1]],
            })
    return result


def _pick(objects, selector):
    feature, direction = selector.split(":")
    if not objects:
        return None
    values = [obj[feature] for obj in objects]
    extreme = min(values) if direction == "min" else max(values)
    matches = [obj for obj, value in zip(objects, values, strict=True) if value == extreme]
    return matches[0] if len(matches) == 1 else None


def _fit_color_map(source, target, mapping):
    if len(source) != len(target) or len(source[0]) != len(target[0]):
        return False
    for source_row, target_row in zip(source, target, strict=True):
        for before, after in zip(source_row, target_row, strict=True):
            old = mapping.get(before)
            if old is not None and old != after:
                return False
            mapping[before] = after
    return True


def _fit(teachers):
    # Cache components so descriptor fitting remains bounded.
    cached = []
    for pair in teachers:
        if not _valid(pair.get("input")) or not _valid(pair.get("output")):
            return []
        cached.append({
            "input": pair["input"],
            "output": pair["output"],
            "objects": {
                seg: _components(pair["input"], *seg)
                for seg in SEGMENTATIONS
            },
        })
    models = []
    for segmentation in SEGMENTATIONS:
        for selector in SELECTORS:
            for orientation in ORIENTATIONS:
                mapping = {}
                for pair in cached:
                    obj = _pick(pair["objects"][segmentation], selector)
                    if obj is None:
                        break
                    transformed = _orient(obj["crop"], orientation)
                    if not _fit_color_map(transformed, pair["output"], mapping):
                        break
                else:
                    models.append((segmentation, selector, orientation, dict(mapping)))
    return models


def _predict(model, grid):
    segmentation, selector, orientation, mapping = model
    obj = _pick(_components(grid, *segmentation), selector)
    if obj is None:
        return None
    transformed = _orient(obj["crop"], orientation)
    output = [[mapping.get(c, c) for c in row] for row in transformed]
    return output if _valid(output) else None


def _key(grid):
    return tuple(tuple(row) for row in grid)


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    generated = {}
    total_models = 0
    for task_id, task in sorted(challenge.items()):
        models = _fit(task["train"])
        total_models += len(models)
        rows = []
        for pair in task["test"]:
            counts = Counter()
            grids = {}
            for model in models:
                candidate = _predict(model, pair["input"])
                if candidate is not None:
                    key = _key(candidate)
                    counts[key] += 1
                    grids[key] = candidate
            if counts:
                top_count = max(counts.values())
                winners = [key for key, count in counts.items() if count == top_count]
                top = grids[winners[0]] if len(winners) == 1 else None
                rows.append({
                    "top": top,
                    "top_votes": top_count,
                    "applicable_models": sum(counts.values()),
                    "any_predictions": list(grids.values()),
                    "tied_top": len(winners) > 1,
                })
            else:
                rows.append({
                    "top": None, "top_votes": 0, "applicable_models": 0,
                    "any_predictions": [], "tied_top": False,
                })
        generated[task_id] = rows

    # Public targets are read only after every candidate prediction is complete.
    targets = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in SOURCE_ROOT.glob("*.json")
    }
    policies = ("top_support2", "plurality50", "unanimous")
    stats = {name: Counter() for name in policies}
    by_task = {name: defaultdict(list) for name in policies}
    baseline_by_task = defaultdict(list)
    baseline_exact_examples = 0
    generated_examples = 0
    eligible_predictions = 0
    tied_top_examples = 0
    oracle_hit_examples = 0
    for task_id, rows in generated.items():
        for index, row in enumerate(rows):
            generated_examples += 1
            target = targets[task_id][index]
            before_row = baseline[task_id][index]
            before = before_row["attempt_1"] == target or before_row["attempt_2"] == target
            baseline_exact_examples += before
            baseline_by_task[task_id].append(before)
            eligible_predictions += bool(row["any_predictions"])
            tied_top_examples += row["tied_top"]
            oracle_hit_examples += any(grid == target for grid in row["any_predictions"])
            for policy in policies:
                top = row["top"]
                votes = row["top_votes"]
                applicable = row["applicable_models"]
                use = (
                    top is not None
                    and (
                        (policy == "top_support2" and votes >= 2)
                        or (policy == "plurality50" and applicable > 0 and votes / applicable >= 0.5)
                        or (policy == "unanimous" and applicable > 0 and votes == applicable)
                    )
                )
                updated = dict(before_row)
                changed = bool(use and top not in (before_row["attempt_1"], before_row["attempt_2"]))
                # Preserve all already-correct v19 pairs; candidate probes only
                # occupy an available second-answer slot on baseline misses.
                if changed and not before:
                    updated["attempt_2"] = top
                    stats[policy]["selected_examples"] += 1
                after = updated["attempt_1"] == target or updated["attempt_2"] == target
                stats[policy]["newly_correct_examples"] += after and not before
                stats[policy]["regressed_examples"] += before and not after
                by_task[policy][task_id].append(after)
    baseline_task_exact = sum(all(values) for values in baseline_by_task.values())
    for policy in policies:
        stats[policy]["baseline_exact_examples"] = baseline_exact_examples
        stats[policy]["combined_exact_examples"] = baseline_exact_examples + stats[policy]["newly_correct_examples"] - stats[policy]["regressed_examples"]
        stats[policy]["baseline_exact_tasks"] = baseline_task_exact
        stats[policy]["combined_exact_tasks"] = sum(all(values) for values in by_task[policy].values())
        stats[policy]["newly_correct_tasks"] = sum(
            all(by_task[policy][task_id]) and not all(baseline_by_task[task_id])
            for task_id in baseline_by_task
        )
        stats[policy]["regressed_tasks"] = sum(
            all(baseline_by_task[task_id]) and not all(by_task[policy][task_id])
            for task_id in baseline_by_task
        )
    report = {
        "schema": "arc2-object-extraction-v19-probe-v1",
        "challenge_tasks": len(challenge),
        "challenge_examples": generated_examples,
        "baseline_v19": {
            "exact_tasks": baseline_task_exact,
            "exact_examples": baseline_exact_examples,
        },
        "fitted_models": total_models,
        "examples_with_candidate": eligible_predictions,
        "examples_with_tied_top": tied_top_examples,
        "oracle_candidate_exact_examples": oracle_hit_examples,
        "policies": {name: dict(values) for name, values in stats.items()},
        "runtime_received_challenge_targets": False,
        "targets_read_only_after_all_predictions": True,
        "per_task_predictions_or_targets_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "challenge": _sha(CHALLENGE),
            "baseline_v19": _sha(BASELINE),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
