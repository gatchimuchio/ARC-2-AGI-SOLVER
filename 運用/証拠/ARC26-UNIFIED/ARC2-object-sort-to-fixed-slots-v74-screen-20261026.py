"""Screen sorting of unchanged objects into teacher-demonstrated output slots."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TRAIN = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
OUTPUT = Path(__file__).with_suffix(".json")
RULES = tuple((name, direction) for name in ("area", "width", "height", "color", "shape", "perimeter")
              for direction in (1, -1))


def _shape(grid):
    if not isinstance(grid, list) or not grid or not isinstance(grid[0], list) or not grid[0]:
        return None
    width = len(grid[0])
    return (len(grid), width) if all(isinstance(row, list) and len(row) == width for row in grid) else None


def _background(grid):
    counts = Counter(color for row in grid for color in row)
    return min(counts, key=lambda color: (-counts[color], color))


def _objects(grid, background):
    h, w = len(grid), len(grid[0])
    seen, output = set(), []
    for r in range(h):
        for c in range(w):
            color = grid[r][c]
            if color == background or (r, c) in seen:
                continue
            stack, cells = [(r, c)], []
            seen.add((r, c))
            while stack:
                rr, cc = stack.pop()
                cells.append((rr, cc))
                for nr, nc in ((rr - 1, cc), (rr + 1, cc), (rr, cc - 1), (rr, cc + 1)):
                    if 0 <= nr < h and 0 <= nc < w and (nr, nc) not in seen and grid[nr][nc] == color:
                        seen.add((nr, nc))
                        stack.append((nr, nc))
            top, left = min(x for x, _ in cells), min(y for _, y in cells)
            shape = tuple(sorted((x - top, y - left) for x, y in cells))
            height = max(x for x, _ in cells) - top + 1
            width = max(y for _, y in cells) - left + 1
            perimeter = sum((rr + dr, cc + dc) not in cells for rr, cc in cells
                            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)))
            output.append({"color": color, "shape": shape, "anchor": (top, left), "cells": tuple(cells),
                           "area": len(cells), "height": height, "width": width, "perimeter": perimeter})
    return output


def _sort_key(obj, rule):
    name, direction = rule
    value = obj[name]
    primary = value if direction == 1 else _reverse(value)
    return primary, obj["color"], obj["shape"]


def _reverse(value):
    if isinstance(value, tuple):
        return tuple((-a, -b) if isinstance(a, int) and isinstance(b, int) else a for a, b in value) if value and isinstance(value[0], tuple) else tuple(-x for x in value)
    return -value


def _pair_view(pair):
    source, target = pair.get("input"), pair.get("output")
    if _shape(source) is None or _shape(source) != _shape(target):
        return None
    bg_in, bg_out = _background(source), _background(target)
    if bg_in != bg_out:
        return None
    src, dst = _objects(source, bg_in), _objects(target, bg_out)
    if len(src) < 2 or len(src) != len(dst):
        return None
    sig = lambda obj: (obj["color"], obj["shape"])
    if Counter(map(sig, src)) != Counter(map(sig, dst)):
        return None
    slots = tuple(obj["anchor"] for obj in sorted(dst, key=lambda obj: obj["anchor"]))
    output_order = tuple(sig(obj) for obj in sorted(dst, key=lambda obj: obj["anchor"]))
    return bg_in, src, slots, output_order


def _candidate(teachers, query):
    qshape = _shape(query)
    if qshape is None or not teachers:
        return None
    views = [_pair_view(pair) for pair in teachers]
    if any(view is None for view in views):
        return None
    first_slots = views[0][2]
    bg = views[0][0]
    if any(view[0] != bg or view[2] != first_slots for view in views):
        return None
    fitting_rules = []
    for rule in RULES:
        if all(tuple((obj["color"], obj["shape"]) for obj in sorted(view[1], key=lambda obj: _sort_key(obj, rule))) == view[3]
               for view in views):
            fitting_rules.append(rule)
    if not fitting_rules:
        return None
    objects = _objects(query, bg)
    if len(objects) != len(first_slots):
        return None
    outputs = set()
    for rule in fitting_rules:
        arranged = sorted(objects, key=lambda obj: _sort_key(obj, rule))
        grid = [[bg] * qshape[1] for _ in range(qshape[0])]
        valid = True
        for obj, (top, left) in zip(arranged, first_slots):
            for r, c in obj["cells"]:
                nr, nc = top + r - obj["anchor"][0], left + c - obj["anchor"][1]
                if not (0 <= nr < qshape[0] and 0 <= nc < qshape[1]) or grid[nr][nc] != bg:
                    valid = False
                    break
                grid[nr][nc] = obj["color"]
            if not valid:
                break
        if valid and grid != query:
            outputs.add(tuple(tuple(row) for row in grid))
    return list(map(list, next(iter(outputs)))) if len(outputs) == 1 else None


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    eligible = proposals = 0
    for path in sorted(TRAIN.glob("*.json")):
        examples = json.loads(path.read_text(encoding="utf-8")).get("train", [])
        if len(examples) < 3:
            continue
        for held_index, held in enumerate(examples):
            teachers = [pair for index, pair in enumerate(examples) if index != held_index]
            eligible += 1
            proposals += _candidate(teachers, held["input"]) is not None
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    public_tasks = public_examples = 0
    for task in challenge.values():
        count = sum(_candidate(task.get("train", []), pair["input"]) is not None for pair in task.get("test", []))
        public_examples += count
        public_tasks += count > 0
    report = {
        "schema": "arc2-object-sort-to-fixed-slots-v74-screen-v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "hypothesis": "infer a consistent ascending or descending object feature order and place unchanged objects into fixed output slots shown by teachers",
        "loo_eligible_folds": eligible,
        "loo_candidate_proposals": proposals,
        "challenge_tasks_with_proposals": public_tasks,
        "challenge_examples_with_proposals": public_examples,
        "runtime_started": False,
        "targets_read": False,
        "task_ids_grids_or_targets_saved": False,
        "source_sha256": {
            "runner": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "challenge": hashlib.sha256(CHALLENGE.read_bytes()).hexdigest(),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
