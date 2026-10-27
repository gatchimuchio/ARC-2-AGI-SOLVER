"""Screen a D4-invariant local-cell context candidate; no labels are read."""
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
    if any(not isinstance(row, list) or len(row) != width for row in grid):
        return None
    return len(grid), width


def _context(grid, r, c):
    h, w = len(grid), len(grid[0])
    return tuple(grid[nr][nc] if 0 <= nr < h and 0 <= nc < w else -1
                 for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                 for nr, nc in [(r + dr, c + dc)])


def _canonical(context):
    matrix = [context[index:index + 3] for index in range(0, 9, 3)]
    forms = []
    for transform in (
        lambda r, c: (r, c), lambda r, c: (r, 2 - c),
        lambda r, c: (2 - r, c), lambda r, c: (2 - r, 2 - c),
        lambda r, c: (c, r), lambda r, c: (c, 2 - r),
        lambda r, c: (2 - c, r), lambda r, c: (2 - c, 2 - r),
    ):
        out = [[0] * 3 for _ in range(3)]
        for r in range(3):
            for c in range(3):
                nr, nc = transform(r, c)
                out[nr][nc] = matrix[r][c]
        forms.append(tuple(value for row in out for value in row))
    return min(forms)


def _candidate(teachers, query):
    qshape = _shape(query)
    if qshape is None:
        return None
    compatible = [
        pair for pair in teachers
        if _shape(pair.get("input")) == qshape and _shape(pair.get("output")) == qshape
    ]
    if not compatible:
        return None
    mapping = {}
    conflicts = set()
    for pair in compatible:
        source, target = pair["input"], pair["output"]
        for r in range(qshape[0]):
            for c in range(qshape[1]):
                key = _canonical(_context(source, r, c))
                color = target[r][c]
                if key in mapping and mapping[key] != color:
                    conflicts.add(key)
                else:
                    mapping[key] = color
    for key in conflicts:
        mapping.pop(key, None)
    result = [row.copy() for row in query]
    changed = 0
    for r in range(qshape[0]):
        for c in range(qshape[1]):
            color = mapping.get(_canonical(_context(query, r, c)))
            if color is not None and color != result[r][c]:
                result[r][c] = color
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
        "schema": "arc2-dihedral-local-context-v69-screen-v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "hypothesis": "learn an unambiguous 3x3 cell context rule after canonicalizing all D4 orientations; leave unseen contexts unchanged",
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
