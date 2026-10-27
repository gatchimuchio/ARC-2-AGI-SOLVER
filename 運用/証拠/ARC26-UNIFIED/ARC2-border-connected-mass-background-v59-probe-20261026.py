"""Screen a border-connected component-mass background rule for object extraction."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _border_connected_mass_background(grid):
    height, width = len(grid), len(grid[0])
    counts = Counter(color for row in grid for color in row)
    mass = Counter()
    seen = set()
    for row in range(height):
        for column in range(width):
            if (row, column) in seen:
                continue
            color = grid[row][column]
            pending = [(row, column)]
            seen.add((row, column))
            size = 0
            touches_border = False
            while pending:
                y, x = pending.pop()
                size += 1
                touches_border |= y in (0, height - 1) or x in (0, width - 1)
                for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if (0 <= yy < height and 0 <= xx < width and (yy, xx) not in seen
                            and grid[yy][xx] == color):
                        seen.add((yy, xx))
                        pending.append((yy, xx))
            if touches_border:
                mass[color] += size
    return min(counts, key=lambda color: (-mass[color], -counts[color], color))


def _candidate(module, teachers, query):
    model = module.ObjectExtractionCandidate(teachers)
    outputs = []
    for method in (model.candidate, model.outlier_candidate, model.palette_candidate):
        prediction, _ = method(query)
        if module._valid_grid(prediction) and prediction != query:
            outputs.append(module._grid_key(prediction))
    counts = Counter(outputs)
    if not counts:
        return None
    top = max(counts.values())
    winners = [key for key, votes in counts.items() if votes == top]
    if top < 2 or len(winners) != 1:
        return None
    return [list(row) for row in winners[0]]


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2 import 物体抽出候補 as module

    original_background = module._background
    module._background = _border_connected_mass_background
    eligible = loo_proposals = 0
    for path in sorted(SOURCE_ROOT.glob("*.json")):
        training = json.loads(path.read_text(encoding="utf-8")).get("train", [])
        if len(training) < 3:
            continue
        for held_index, held in enumerate(training):
            teachers = [pair for index, pair in enumerate(training) if index != held_index]
            eligible += 1
            loo_proposals += _candidate(module, teachers, held["input"]) is not None

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    public_examples = public_tasks = 0
    for task in challenge.values():
        task_has_candidate = False
        for pair in task.get("test", []):
            has_candidate = _candidate(module, task.get("train", []), pair["input"]) is not None
            public_examples += has_candidate
            task_has_candidate |= has_candidate
        public_tasks += task_has_candidate
    module._background = original_background
    report = {
        "schema": "arc2-border-connected-mass-background-v59-probe-v1",
        "policy": "choose the color with the largest total area across all 4-connected components touching any grid border; ties by total color count then lowest color",
        "loo_eligible_folds": eligible,
        "loo_candidate_proposal_folds": loo_proposals,
        "challenge_tasks": len(challenge),
        "challenge_examples": sum(len(task.get("test", [])) for task in challenge.values()),
        "challenge_tasks_with_candidates": public_tasks,
        "challenge_examples_with_candidates": public_examples,
        "heldout_outputs_read": False,
        "challenge_targets_read": False,
        "per_task_ids_grids_or_candidates_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "object_module": _sha(ROOT / "接続/ARC2/物体抽出候補.py"),
            "challenge_inputs": _sha(CHALLENGE),
            "v51_build_manifest": _sha(ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v51-largest-component-background-20261026/build-manifest.json"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
