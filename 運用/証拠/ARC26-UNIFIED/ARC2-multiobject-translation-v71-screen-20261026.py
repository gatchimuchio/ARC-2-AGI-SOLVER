"""Screen a generic descriptor-conditioned translation rule for whole objects."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TRAIN = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
OUTPUT = Path(__file__).with_suffix(".json")


def _shape(grid):
    if not isinstance(grid, list) or not grid or not isinstance(grid[0], list) or not grid[0]:
        return None
    width = len(grid[0])
    return (len(grid), width) if all(isinstance(row, list) and len(row) == width for row in grid) else None


def _background(grid):
    counts = Counter(color for row in grid for color in row)
    return min(counts, key=lambda color: (-counts[color], color))


def _objects(grid, background):
    height, width = len(grid), len(grid[0])
    seen = set()
    objects = []
    for r in range(height):
        for c in range(width):
            color = grid[r][c]
            if color == background or (r, c) in seen:
                continue
            stack, cells = [(r, c)], []
            seen.add((r, c))
            while stack:
                rr, cc = stack.pop()
                cells.append((rr, cc))
                for nr, nc in ((rr - 1, cc), (rr + 1, cc), (rr, cc - 1), (rr, cc + 1)):
                    if 0 <= nr < height and 0 <= nc < width and (nr, nc) not in seen and grid[nr][nc] == color:
                        seen.add((nr, nc))
                        stack.append((nr, nc))
            top, left = min(r0 for r0, _ in cells), min(c0 for _, c0 in cells)
            shape = tuple(sorted((r0 - top, c0 - left) for r0, c0 in cells))
            objects.append({"descriptor": (color, shape), "anchor": (top, left), "cells": tuple(cells)})
    return objects


def _fit(teachers, query):
    qshape = _shape(query)
    if qshape is None or not teachers:
        return None
    deltas = {}
    expected_background = None
    for pair in teachers:
        source, target = pair.get("input"), pair.get("output")
        if _shape(source) != qshape or _shape(target) != qshape:
            return None
        bg_in, bg_out = _background(source), _background(target)
        if bg_in != bg_out or (expected_background is not None and bg_in != expected_background):
            return None
        expected_background = bg_in
        source_objects, target_objects = _objects(source, bg_in), _objects(target, bg_out)
        source_by, target_by = defaultdict(list), defaultdict(list)
        for obj in source_objects:
            source_by[obj["descriptor"]].append(obj)
        for obj in target_objects:
            target_by[obj["descriptor"]].append(obj)
        if set(source_by) != set(target_by) or any(len(source_by[key]) != 1 or len(target_by[key]) != 1 for key in source_by):
            return None
        for descriptor in source_by:
            src, dst = source_by[descriptor][0], target_by[descriptor][0]
            delta = (dst["anchor"][0] - src["anchor"][0], dst["anchor"][1] - src["anchor"][1])
            previous = deltas.get(descriptor)
            if previous is not None and previous != delta:
                return None
            deltas[descriptor] = delta

    if not deltas or not any(delta != (0, 0) for delta in deltas.values()):
        return None
    background = _background(query)
    if background != expected_background:
        return None
    result = [[background] * qshape[1] for _ in range(qshape[0])]
    moved = False
    for obj in _objects(query, background):
        delta = deltas.get(obj["descriptor"])
        if delta is None:
            return None
        moved |= delta != (0, 0)
        for r, c in obj["cells"]:
            nr, nc = r + delta[0], c + delta[1]
            if not (0 <= nr < qshape[0] and 0 <= nc < qshape[1]) or result[nr][nc] != background:
                return None
            result[nr][nc] = obj["descriptor"][0]
    return result if moved and result != query else None


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
            proposals += _fit(teachers, held["input"]) is not None
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    public_tasks = public_examples = 0
    for task in challenge.values():
        count = sum(_fit(task.get("train", []), pair["input"]) is not None for pair in task.get("test", []))
        public_examples += count
        public_tasks += count > 0
    report = {
        "schema": "arc2-multiobject-translation-v71-screen-v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "hypothesis": "match unchanged monochrome 4-connected objects by color and translation-normalized shape; learn a consistent per-descriptor translation vector and apply it to all objects",
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
