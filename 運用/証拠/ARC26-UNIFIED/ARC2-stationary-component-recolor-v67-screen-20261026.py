"""Screen a generic stationary-component recoloring hypothesis.

This is a proposal-count screen only. It uses demonstrations and query inputs,
does not read held-out outputs, and stores no task IDs or grids.
"""
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


def _background(grid):
    return min(Counter(color for row in grid for color in row), key=lambda c: (-sum(row.count(c) for row in grid), c))


def _canonical_shape(cells):
    points = list(cells)
    forms = []
    for transform in (
        lambda r, c: (r, c), lambda r, c: (r, -c),
        lambda r, c: (-r, c), lambda r, c: (-r, -c),
        lambda r, c: (c, r), lambda r, c: (c, -r),
        lambda r, c: (-c, r), lambda r, c: (-c, -r),
    ):
        moved = [transform(r, c) for r, c in points]
        min_r = min(r for r, _ in moved)
        min_c = min(c for _, c in moved)
        forms.append(tuple(sorted((r - min_r, c - min_c) for r, c in moved)))
    return min(forms)


def _components(grid, background):
    seen = set()
    rows, cols = len(grid), len(grid[0])
    result = []
    for r in range(rows):
        for c in range(cols):
            color = grid[r][c]
            if color == background or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                rr, cc = stack.pop()
                cells.append((rr, cc))
                for nr, nc in ((rr - 1, cc), (rr + 1, cc), (rr, cc - 1), (rr, cc + 1)):
                    if (0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in seen
                            and grid[nr][nc] == color):
                        seen.add((nr, nc))
                        stack.append((nr, nc))
            result.append((color, tuple(cells)))
    return result


def _fit(teachers, query):
    if not teachers or not query or not query[0]:
        return None
    mapping = {}
    background_pair = None
    for pair in teachers:
        source, target = pair.get("input"), pair.get("output")
        if not source or not target or len(source) != len(target) or len(source[0]) != len(target[0]):
            return None
        if any(len(row) != len(source[0]) for row in source + target):
            return None
        bg_in, bg_out = _background(source), _background(target)
        if background_pair is None:
            background_pair = (bg_in, bg_out)
        elif background_pair != (bg_in, bg_out):
            return None
        objects = _components(source, bg_in)
        if not objects:
            return None
        covered = set()
        for color, cells in objects:
            out_colors = {target[r][c] for r, c in cells}
            if len(out_colors) != 1:
                return None
            descriptor = (color, _canonical_shape(cells))
            output_color = next(iter(out_colors))
            prior = mapping.get(descriptor)
            if prior is not None and prior != output_color:
                return None
            mapping[descriptor] = output_color
            covered.update(cells)
        if any(target[r][c] != bg_out for r in range(len(source)) for c in range(len(source[0]))
               if (r, c) not in covered):
            return None

    bg_in, bg_out = background_pair
    if _background(query) != bg_in:
        return None
    result = [[bg_out for _ in row] for row in query]
    objects = _components(query, bg_in)
    if not objects:
        return None
    for color, cells in objects:
        output_color = mapping.get((color, _canonical_shape(cells)))
        if output_color is None:
            return None
        for r, c in cells:
            result[r][c] = output_color
    return result if result != query else None


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    loo_eligible = loo_proposals = 0
    for path in sorted(TRAIN.glob("*.json")):
        train = json.loads(path.read_text(encoding="utf-8")).get("train", [])
        if len(train) < 3:
            continue
        for held_index, held in enumerate(train):
            teachers = [pair for index, pair in enumerate(train) if index != held_index]
            loo_eligible += 1
            loo_proposals += _fit(teachers, held["input"]) is not None

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    challenge_examples = challenge_tasks = 0
    for task in challenge.values():
        count = sum(_fit(task.get("train", []), pair["input"]) is not None for pair in task.get("test", []))
        challenge_examples += count
        challenge_tasks += count > 0

    report = {
        "schema": "arc2-stationary-component-recolor-v67-screen-v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "hypothesis": "recolor each stationary monochrome 4-connected component by a consistent mapping from input color and D4-normalized shape; preserve the mapped background",
        "loo_eligible_folds": loo_eligible,
        "loo_candidate_proposals": loo_proposals,
        "challenge_tasks_with_proposals": challenge_tasks,
        "challenge_examples_with_proposals": challenge_examples,
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
