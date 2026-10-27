"""Support-2 public-training LOO probe for one constant foreground translation."""
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
D4_PATH = "接続/ARC2/格子D4教材.py"
D4_SHA256 = "a5d6a2eedb063a876b47cd5d2fdf28cec13af535d89b9fef65df41b81c5ccf18"
TRANSLATION_PATH = "接続/ARC2/全前景平行移動教材.py"
sys.path.insert(0, str(ROOT))
from 接続.ARC2.全前景平行移動教材 import 全前景平行移動教材  # noqa: E402

raw_d4 = subprocess.run(
    ["git", "show", f"{COMMIT}:{D4_PATH}"], cwd=ROOT, check=True, capture_output=True
).stdout
if hashlib.sha256(raw_d4).hexdigest() != D4_SHA256:
    raise SystemExit("reference D4 module hash mismatch")
translation_sha = hashlib.sha256((ROOT / TRANSLATION_PATH).read_bytes()).hexdigest()
d4_module = ModuleType("arc2_p5_d4_reference")
exec(compile(raw_d4, f"{COMMIT}:{D4_PATH}", "exec"), d4_module.__dict__)


def background(grid):
    colors = {value for row in grid for value in row}
    counts = {color: sum(value == color for row in grid for value in row) for color in colors}
    return min(colors, key=lambda color: (-counts[color], color))


def shift_foreground(grid, dr, dc, bg):
    height, width = len(grid), len(grid[0])
    output = [[bg] * width for _ in range(height)]
    for row in range(height):
        for column in range(width):
            value = grid[row][column]
            if value == bg:
                continue
            target_row, target_column = row + dr, column + dc
            if not (0 <= target_row < height and 0 <= target_column < width):
                return None
            output[target_row][target_column] = value
    return output


def infer_offset(source, target):
    bg = background(source)
    source_cells = [
        (row, column)
        for row, values in enumerate(source)
        for column, value in enumerate(values)
        if value != bg
    ]
    target_cells = [
        (row, column)
        for row, values in enumerate(target)
        for column, value in enumerate(values)
        if value != bg
    ]
    if not source_cells:
        return None
    if len(source_cells) != len(target_cells):
        return False
    dr = min(row for row, _ in target_cells) - min(row for row, _ in source_cells)
    dc = min(column for _, column in target_cells) - min(
        column for _, column in source_cells
    )
    return (dr, dc) if shift_foreground(source, dr, dc, bg) == target else False


def fit(teachers):
    if not isinstance(teachers, (list, tuple)) or len(teachers) < 2:
        return set()
    input_grids = [tuple(tuple(row) for row in pair["input"]) for pair in teachers]
    if len(set(input_grids)) != len(input_grids):
        return set()
    common_offsets = None
    for pair in teachers:
        source, target = pair["input"], pair["output"]
        if len(source) != len(target) or any(
            len(source_row) != len(target_row)
            for source_row, target_row in zip(source, target)
        ):
            return set()
        offset = infer_offset(source, target)
        if offset is False or offset is None:
            return set()
        if common_offsets is None:
            common_offsets = {offset}
        else:
            common_offsets.intersection_update({offset})
        if not common_offsets:
            return set()
    return common_offsets or set()


def predict(grid, offsets):
    outputs = {
        tuple(tuple(row) for row in output)
        for dr, dc in offsets
        if (output := shift_foreground(grid, dr, dc, background(grid))) is not None
    }
    if len(outputs) != 1:
        return None
    return [list(row) for row in next(iter(outputs))]


def self_check():
    source_a, output_a = [[0, 1, 0, 0]], [[0, 0, 1, 0]]
    source_b, output_b = [[1, 0, 0, 0]], [[0, 1, 0, 0]]
    source_c, output_c = [[1, 0, 1, 0]], [[0, 1, 0, 1]]
    teachers = [
        {"input": source_a, "output": output_a},
        {"input": source_b, "output": output_b},
        {"input": source_c, "output": output_c},
    ]
    if fit(teachers) != {(0, 1)} or predict(source_a, fit(teachers)) != output_a:
        raise SystemExit("translation self-check failed")
    if fit(teachers[:2]) != {(0, 1)}:
        raise SystemExit("support-2 translation self-check failed")
    teachers.append({"input": [[1, 0, 0, 1]], "output": [[1, 0, 0, 1]]})
    if fit(teachers):
        raise SystemExit("incompatible-teacher self-check failed")


self_check()
train_dir = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
files = sorted(train_dir.glob("*.json"))
manifest = hashlib.sha256()
eligible_tasks = loo_folds = unique_teacher_folds = 0
baseline_answers = baseline_exact = baseline_wrong = 0
translation_answers = translation_exact = translation_wrong = 0
support3_answers = support3_exact = support3_wrong = 0
incremental_answers = incremental_exact = incremental_wrong = conflicts = agreements = 0
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
        teacher_inputs = [tuple(tuple(row) for row in pair["input"]) for pair in teachers]
        if len(teachers) >= 2 and len(set(teacher_inputs)) == len(teacher_inputs):
            unique_teacher_folds += 1
        baseline_model = d4_module.格子D4教材(teachers)
        baseline, _ = baseline_model.候補(heldout["input"], {})
        if baseline is not None:
            baseline_answers += 1
            if baseline == heldout["output"]:
                baseline_exact += 1
            else:
                baseline_wrong += 1

        existing_translation_model = 全前景平行移動教材(teachers)
        existing_translation, _ = existing_translation_model.候補(heldout["input"], {})
        if existing_translation is not None:
            support3_answers += 1
            if existing_translation == heldout["output"]:
                support3_exact += 1
            else:
                support3_wrong += 1

        translation = predict(heldout["input"], fit(teachers))
        if translation is not None:
            translation_answers += 1
            if translation == heldout["output"]:
                translation_exact += 1
            else:
                translation_wrong += 1
            existing = [value for value in (baseline, existing_translation) if value is not None]
            if not existing:
                incremental_answers += 1
                if translation == heldout["output"]:
                    incremental_exact += 1
                else:
                    incremental_wrong += 1
            elif all(translation == value for value in existing):
                agreements += 1
            else:
                conflicts += 1

result = {
    "schema": "arc2-p5-global-translation-support2-loo.v1",
    "instruction_id": "ARC2-SCORE-GATE-20261024",
    "reference_source_commit": COMMIT,
    "source_sha256": {
        f"{COMMIT}:{D4_PATH}": D4_SHA256,
        TRANSLATION_PATH: translation_sha,
        Path(__file__).name: hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    },
    "data_source": "public ARC-AGI-2 training split only",
    "training_manifest_sha256": manifest.hexdigest(),
    "public_training_files": len(files),
    "eligible_tasks_minimum_teacher_support_2": eligible_tasks,
    "loo_folds": loo_folds,
    "loo_folds_with_at_least_2_unique_teacher_inputs": unique_teacher_folds,
    "baseline_D4_answers": baseline_answers,
    "baseline_D4_exact": baseline_exact,
    "baseline_D4_wrong": baseline_wrong,
    "existing_support3_translation_answers": support3_answers,
    "existing_support3_translation_exact": support3_exact,
    "existing_support3_translation_wrong": support3_wrong,
    "translation_answers": translation_answers,
    "translation_exact": translation_exact,
    "translation_wrong": translation_wrong,
    "incremental_answers": incremental_answers,
    "incremental_exact": incremental_exact,
    "incremental_wrong": incremental_wrong,
    "agreements_with_existing_answer": agreements,
    "conflicts_with_existing_answer": conflicts,
    "elapsed_seconds": round(time.perf_counter() - started, 3),
    "evaluation_solutions_read": False,
    "task_identifiers_or_grids_saved": False,
    "decision": "REVIEW_REQUIRED" if incremental_exact and not incremental_wrong and not conflicts else "REJECT_OR_REFINE",
}
report = Path(__file__).with_suffix(".json")
report.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
