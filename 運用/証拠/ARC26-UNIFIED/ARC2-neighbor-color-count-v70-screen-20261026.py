"""Screen a rotation/reflection-invariant neighbor-color-count rule."""
from __future__ import annotations

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


def _feature(grid, r, c):
    counts = [0] * 11  # boundary sentinel, then ARC colors 0..9
    h, w = len(grid), len(grid[0])
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == dc == 0:
                continue
            nr, nc = r + dr, c + dc
            value = grid[nr][nc] if 0 <= nr < h and 0 <= nc < w else -1
            counts[value + 1] += 1
    return grid[r][c], tuple(counts)


def _candidate(teachers, query):
    qshape = _shape(query)
    if qshape is None:
        return None
    compatible = [pair for pair in teachers
                  if _shape(pair.get("input")) == qshape and _shape(pair.get("output")) == qshape]
    if not compatible:
        return None
    mapping, conflicts = {}, set()
    for pair in compatible:
        source, target = pair["input"], pair["output"]
        for r in range(qshape[0]):
            for c in range(qshape[1]):
                key = _feature(source, r, c)
                value = target[r][c]
                if key in mapping and mapping[key] != value:
                    conflicts.add(key)
                else:
                    mapping[key] = value
    for key in conflicts:
        mapping.pop(key, None)
    result = [row.copy() for row in query]
    changed = 0
    for r in range(qshape[0]):
        for c in range(qshape[1]):
            value = mapping.get(_feature(query, r, c))
            if value is not None and value != result[r][c]:
                result[r][c] = value
                changed += 1
    return result if changed else None


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
        count = sum(_candidate(task.get("train", []), pair["input"]) is not None
                    for pair in task.get("test", []))
        public_examples += count
        public_tasks += count > 0
    report = {
        "schema": "arc2-neighbor-color-count-v70-screen-v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "hypothesis": "map the center color and D4-invariant 3x3 neighbor color histogram to an output color; preserve unseen or contradictory contexts",
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
