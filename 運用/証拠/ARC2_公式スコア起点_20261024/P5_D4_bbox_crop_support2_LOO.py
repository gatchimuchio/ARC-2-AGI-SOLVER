"""LOO probe for a conservative background-bbox crop before D4 transforms."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[3]
COMMIT = "2759d393a8d79824d36754785ce16f66d0493ebd"
MODULE_PATH = "接続/ARC2/格子D4教材.py"
EXPECTED_MODULE_SHA256 = "a5d6a2eedb063a876b47cd5d2fdf28cec13af535d89b9fef65df41b81c5ccf18"
TRANSLATION_PATH = "接続/ARC2/全前景平行移動教材.py"
CHALLENGE_SHA256 = "232264c58f825ee77327dcfc9f4e5cb2f83b8d997eb69032be1bf2205bbe1a83"
sys.path.insert(0, str(ROOT))
from 接続.ARC2.全前景平行移動教材 import 全前景平行移動教材  # noqa: E402

source_bytes = subprocess.run(
    ["git", "show", f"{COMMIT}:{MODULE_PATH}"],
    cwd=ROOT,
    check=True,
    capture_output=True,
).stdout
source_sha = hashlib.sha256(source_bytes).hexdigest()
if source_sha != EXPECTED_MODULE_SHA256:
    raise SystemExit("reference D4 module hash mismatch")
module = ModuleType("arc2_p5_d4_reference")
exec(compile(source_bytes, f"{COMMIT}:{MODULE_PATH}", "exec"), module.__dict__)


def crop_background_bbox(grid):
    colors = {value for row in grid for value in row}
    counts = {color: sum(value == color for row in grid for value in row) for color in colors}
    background = min(colors, key=lambda color: (-counts[color], color))
    cells = [
        (row_index, column_index)
        for row_index, row in enumerate(grid)
        for column_index, value in enumerate(row)
        if value != background
    ]
    if not cells:
        return [row[:] for row in grid]
    top = min(row for row, _ in cells)
    bottom = max(row for row, _ in cells)
    left = min(column for _, column in cells)
    right = max(column for _, column in cells)
    return [row[left:right + 1] for row in grid[top:bottom + 1]]


def d4(grid, operation):
    rotated = [row[:] for row in grid]
    for angle in (0, 90, 180, 270):
        if operation == f"rotate_{angle}":
            return rotated
        rotated = [list(row) for row in zip(*rotated[::-1])]
    reflected = [row[::-1] for row in grid]
    for angle in (0, 90, 180, 270):
        if operation == f"reflect_rotate_{angle}":
            return reflected
        reflected = [list(row) for row in zip(*reflected[::-1])]
    raise ValueError("unknown D4 operation")


OPERATIONS = tuple(
    [f"rotate_{angle}" for angle in (0, 90, 180, 270)]
    + [f"reflect_rotate_{angle}" for angle in (0, 90, 180, 270)]
)


def transformed(grid, crop, operation):
    return d4(crop_background_bbox(grid) if crop else grid, operation)


def fit(teachers, crop_modes):
    retained = []
    for crop in crop_modes:
        for operation in OPERATIONS:
            forward, reverse = {}, {}
            valid = True
            for pair in teachers:
                source = transformed(pair["input"], crop, operation)
                target = pair["output"]
                if len(source) != len(target) or any(
                    len(source_row) != len(target_row)
                    for source_row, target_row in zip(source, target)
                ):
                    valid = False
                    break
                for source_row, target_row in zip(source, target):
                    for input_color, output_color in zip(source_row, target_row):
                        if (
                            input_color in forward and forward[input_color] != output_color
                        ) or (
                            output_color in reverse and reverse[output_color] != input_color
                        ):
                            valid = False
                            break
                        forward[input_color] = output_color
                        reverse[output_color] = input_color
                    if not valid:
                        break
                if not valid:
                    break
            if valid:
                retained.append((crop, operation, forward))
    return retained


def predict(grid, programs):
    outputs = set()
    for crop, operation, mapping in programs:
        source = transformed(grid, crop, operation)
        colors = {value for row in source for value in row}
        if colors.issubset(mapping):
            output = tuple(tuple(mapping[value] for value in row) for row in source)
            outputs.add(output)
    if len(outputs) != 1:
        return None
    return [list(row) for row in next(iter(outputs))]


train_dir = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
files = sorted(train_dir.glob("*.json"))
manifest = hashlib.sha256()
eligible_tasks = loo_folds = unique_teacher_folds = 0
baseline_answers = baseline_exact = baseline_wrong = 0
bbox_answers = bbox_exact = bbox_wrong = bbox_conflicts = 0
combined_answers = combined_exact = combined_wrong = incremental = incremental_exact = incremental_wrong = 0
union_answers = union_exact = union_wrong = 0
incremental_over_existing = incremental_over_existing_exact = incremental_over_existing_wrong = 0
existing_conflicts = 0
started = time.perf_counter()

for path in files:
    raw = path.read_bytes()
    manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
    examples = json.loads(raw).get("train", [])
    if len(examples) < 3:
        continue
    eligible_tasks += 1
    for index, heldout in enumerate(examples):
        loo_folds += 1
        teachers = [pair for i, pair in enumerate(examples) if i != index]
        teacher_inputs = [tuple(map(tuple, pair["input"])) for pair in teachers]
        if len(teachers) >= 2 and len(set(teacher_inputs)) == len(teacher_inputs):
            unique_teacher_folds += 1
        baseline_model = module.格子D4教材(teachers)
        baseline, _ = baseline_model.候補(heldout["input"], {})
        if baseline is not None:
            baseline_answers += 1
            if baseline == heldout["output"]:
                baseline_exact += 1
            else:
                baseline_wrong += 1

        bbox_prediction = predict(heldout["input"], fit(teachers, (True,)))
        translation, _ = 全前景平行移動教材(teachers).候補(heldout["input"], {})
        if bbox_prediction is not None:
            bbox_answers += 1
            if bbox_prediction == heldout["output"]:
                bbox_exact += 1
            else:
                bbox_wrong += 1
            if baseline is not None and bbox_prediction != baseline:
                bbox_conflicts += 1
            existing = [value for value in (baseline, translation) if value is not None]
            if not existing:
                incremental_over_existing += 1
                if bbox_prediction == heldout["output"]:
                    incremental_over_existing_exact += 1
                else:
                    incremental_over_existing_wrong += 1
            elif any(bbox_prediction != value for value in existing):
                existing_conflicts += 1
        selected = baseline if baseline is not None else bbox_prediction
        if selected is not None:
            combined_answers += 1
            if selected == heldout["output"]:
                combined_exact += 1
            else:
                combined_wrong += 1
            if baseline is None:
                incremental += 1
                if selected == heldout["output"]:
                    incremental_exact += 1
                else:
                    incremental_wrong += 1

        union_prediction = predict(heldout["input"], fit(teachers, (False, True)))
        if union_prediction is not None:
            union_answers += 1
            if union_prediction == heldout["output"]:
                union_exact += 1
            else:
                union_wrong += 1

challenge_path = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
challenge_raw = challenge_path.read_bytes()
if hashlib.sha256(challenge_raw).hexdigest() != CHALLENGE_SHA256:
    raise SystemExit("official challenge input hash mismatch")
challenge = json.loads(challenge_raw)
challenge_candidate_tasks = challenge_candidate_outputs = 0
for task in challenge.values():
    teachers = task.get("train", [])
    if len(teachers) < 2:
        continue
    programs = fit(teachers, (True,))
    predictions = [predict(pair["input"], programs) for pair in task.get("test", [])]
    count = sum(value is not None for value in predictions)
    if count:
        challenge_candidate_tasks += 1
        challenge_candidate_outputs += count

result = {
    "schema": "arc2-p5-d4-background-bbox-support2-loo.v1",
    "instruction_id": "ARC2-SCORE-GATE-20261024",
    "source_commit": COMMIT,
    "source_sha256": {
        MODULE_PATH: source_sha,
        TRANSLATION_PATH: hashlib.sha256((ROOT / TRANSLATION_PATH).read_bytes()).hexdigest(),
        Path(__file__).name: hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    },
    "data_source": "public ARC-AGI-2 training split only",
    "training_manifest_sha256": manifest.hexdigest(),
    "public_training_files": len(files),
    "eligible_tasks_minimum_teacher_support_2": eligible_tasks,
    "loo_folds": loo_folds,
    "loo_folds_with_at_least_2_unique_teacher_inputs": unique_teacher_folds,
    "baseline_answers": baseline_answers,
    "baseline_exact": baseline_exact,
    "baseline_wrong": baseline_wrong,
    "bbox_only_answers": bbox_answers,
    "bbox_only_exact": bbox_exact,
    "bbox_only_wrong": bbox_wrong,
    "bbox_only_disagreements_with_baseline": bbox_conflicts,
    "priority_fallback_answers": combined_answers,
    "priority_fallback_exact": combined_exact,
    "priority_fallback_wrong": combined_wrong,
    "incremental_answers": incremental,
    "incremental_exact": incremental_exact,
    "incremental_wrong": incremental_wrong,
    "incremental_over_support3_D4_and_translation": incremental_over_existing,
    "incremental_over_support3_D4_and_translation_exact": incremental_over_existing_exact,
    "incremental_over_support3_D4_and_translation_wrong": incremental_over_existing_wrong,
    "conflicts_with_existing_answers": existing_conflicts,
    "full_plus_bbox_consensus_answers": union_answers,
    "full_plus_bbox_consensus_exact": union_exact,
    "full_plus_bbox_consensus_wrong": union_wrong,
    "challenge_sha256": hashlib.sha256(challenge_raw).hexdigest(),
    "challenge_tasks_with_candidate": challenge_candidate_tasks,
    "challenge_candidate_outputs": challenge_candidate_outputs,
    "elapsed_seconds": round(time.perf_counter() - started, 3),
    "evaluation_solutions_read": False,
    "task_identifiers_or_grids_saved": False,
    "hypothesis": "Use a D4+bijective-palette transform after cropping the dominant-color bounding box with two unique teachers.",
    "decision": "REVIEW_REQUIRED"
    if incremental_over_existing_exact and not incremental_over_existing_wrong and not existing_conflicts
    else "REJECT_OR_REFINE",
}
report = Path(__file__).with_suffix(".json")
report.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
