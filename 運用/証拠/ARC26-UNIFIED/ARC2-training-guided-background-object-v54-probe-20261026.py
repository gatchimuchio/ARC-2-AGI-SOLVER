"""Screen object extraction with a training-consensus removed-color background rule."""
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


def _mode_background(grid):
    counts = Counter(color for row in grid for color in row)
    return min(counts, key=lambda color: (-counts[color], color))


def _training_guided_background(teachers):
    votes = Counter()
    for pair in teachers:
        input_counts = Counter(color for row in pair["input"] for color in row)
        output_counts = Counter(color for row in pair["output"] for color in row)
        losses = {
            color: input_counts[color] - output_counts[color]
            for color in input_counts
        }
        largest_loss = max(losses.values(), default=0)
        winners = [color for color, loss in losses.items() if loss == largest_loss]
        if largest_loss > 0 and len(winners) == 1:
            votes[winners[0]] += 1
    if votes:
        top_votes = max(votes.values())
        winners = [color for color, count in votes.items() if count == top_votes]
        selected = winners[0] if top_votes >= 2 and len(winners) == 1 else None
    else:
        selected = None

    def choose(grid):
        counts = Counter(color for row in grid for color in row)
        if selected is not None and selected in counts:
            return selected
        return _mode_background(grid)

    return choose


def _candidate(module, teachers, query):
    module._background = _training_guided_background(teachers)
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
    module._background = _mode_background
    eligible = proposals = 0
    for path in sorted(SOURCE_ROOT.glob("*.json")):
        training = json.loads(path.read_text(encoding="utf-8")).get("train", [])
        if len(training) < 3:
            continue
        for held_index, held in enumerate(training):
            teachers = [pair for index, pair in enumerate(training) if index != held_index]
            eligible += 1
            proposals += _candidate(module, teachers, held["input"]) is not None
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    challenge_proposals = challenge_tasks_with_candidate = 0
    for task in challenge.values():
        task_has_candidate = False
        for pair in task.get("test", []):
            has_candidate = _candidate(module, task.get("train", []), pair["input"]) is not None
            task_has_candidate |= has_candidate
            challenge_proposals += has_candidate
        challenge_tasks_with_candidate += task_has_candidate
    report = {
        "schema": "arc2-training-guided-background-object-v54-probe-v1",
        "background_policy": "unique teacher plurality (at least two examples) of the color with the greatest input-minus-output count loss; otherwise use modal color",
        "candidate_agreement": "at least two of object, outlier, and palette families return the same distinct valid grid",
        "loo_eligible_folds": eligible,
        "loo_candidate_proposal_folds": proposals,
        "challenge_tasks": len(challenge),
        "challenge_examples": sum(len(task.get("test", [])) for task in challenge.values()),
        "challenge_tasks_with_candidate": challenge_tasks_with_candidate,
        "challenge_examples_with_candidate": challenge_proposals,
        "heldout_outputs_read": False,
        "challenge_targets_read": False,
        "per_task_ids_grids_or_candidates_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "object_module": _sha(ROOT / "接続/ARC2/物体抽出候補.py"),
            "challenge_inputs": _sha(CHALLENGE),
            "v28_build_manifest": _sha(ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v28-vote-ratio-second-20261026/build-manifest.json"),
        },
    }
    module._background = original_background
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
