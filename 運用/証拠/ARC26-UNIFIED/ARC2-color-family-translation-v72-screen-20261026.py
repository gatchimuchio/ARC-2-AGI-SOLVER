"""Screen a generic same-color component translation rule."""
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
    h, w = len(grid), len(grid[0])
    seen, out = set(), []
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
            out.append({"color": color, "shape": shape, "anchor": (top, left), "cells": tuple(cells)})
    return out


def _fit(teachers, query):
    qshape = _shape(query)
    if qshape is None or not teachers:
        return None
    deltas, expected_bg = {}, None
    for pair in teachers:
        source, target = pair.get("input"), pair.get("output")
        if _shape(source) != qshape or _shape(target) != qshape:
            return None
        bg_in, bg_out = _background(source), _background(target)
        if bg_in != bg_out or (expected_bg is not None and bg_in != expected_bg):
            return None
        expected_bg = bg_in
        src, dst = _objects(source, bg_in), _objects(target, bg_out)
        by_src, by_dst = defaultdict(list), defaultdict(list)
        for obj in src:
            by_src[(obj["color"], obj["shape"])].append(obj)
        for obj in dst:
            by_dst[(obj["color"], obj["shape"])].append(obj)
        if set(by_src) != set(by_dst) or any(len(by_src[k]) != 1 or len(by_dst[k]) != 1 for k in by_src):
            return None
        pair_deltas = defaultdict(set)
        for key in by_src:
            a, b = by_src[key][0], by_dst[key][0]
            pair_deltas[key[0]].add((b["anchor"][0] - a["anchor"][0], b["anchor"][1] - a["anchor"][1]))
        if any(len(values) != 1 for values in pair_deltas.values()):
            return None
        for color, values in pair_deltas.items():
            delta = next(iter(values))
            if color in deltas and deltas[color] != delta:
                return None
            deltas[color] = delta

    if not deltas or not any(delta != (0, 0) for delta in deltas.values()) or _background(query) != expected_bg:
        return None
    result = [[expected_bg] * qshape[1] for _ in range(qshape[0])]
    moved = False
    for obj in _objects(query, expected_bg):
        delta = deltas.get(obj["color"])
        if delta is None:
            return None
        moved |= delta != (0, 0)
        for r, c in obj["cells"]:
            nr, nc = r + delta[0], c + delta[1]
            if not (0 <= nr < qshape[0] and 0 <= nc < qshape[1]) or result[nr][nc] != expected_bg:
                return None
            result[nr][nc] = obj["color"]
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
        "schema": "arc2-color-family-translation-v72-screen-v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "hypothesis": "match unchanged foreground components by color and exact translation-normalized shape, then apply one consistent translation vector per color",
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
