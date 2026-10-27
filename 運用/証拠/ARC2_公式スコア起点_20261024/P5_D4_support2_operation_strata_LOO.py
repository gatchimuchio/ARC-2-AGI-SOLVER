"""Probe exact grid-D4 transforms with two teachers, excluding color remaps."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from types import ModuleType


ROOT = Path(__file__).resolve().parents[3]
REFERENCE_COMMIT = "2759d393a8d79824d36754785ce16f66d0493ebd"
D4_PATH = "接続/ARC2/格子D4教材.py"
D4_SHA256 = "a5d6a2eedb063a876b47cd5d2fdf28cec13af535d89b9fef65df41b81c5ccf18"
TRANSLATION_PATH = "接続/ARC2/全前景平行移動教材.py"
TRAINING_DIR = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
sys.path.insert(0, str(ROOT))
from 接続.ARC2.全前景平行移動教材 import 全前景平行移動教材  # noqa: E402


raw_d4 = subprocess.run(
    ["git", "show", f"{REFERENCE_COMMIT}:{D4_PATH}"],
    cwd=ROOT,
    check=True,
    capture_output=True,
).stdout
if hashlib.sha256(raw_d4).hexdigest() != D4_SHA256:
    raise SystemExit("reference D4 source hash mismatch")
d4_module = ModuleType("arc2_p5_d4_support2_reference")
exec(compile(raw_d4, f"{REFERENCE_COMMIT}:{D4_PATH}", "exec"), d4_module.__dict__)


def fit_d4(teachers):
    if len(teachers) < 2:
        return (), ()
    if any(
        not isinstance(pair, dict)
        or not d4_module._有効格子(pair.get("input"))
        or not d4_module._有効格子(pair.get("output"))
        for pair in teachers
    ):
        return (), ()
    inputs = [tuple(map(tuple, pair["input"])) for pair in teachers]
    if len(set(inputs)) != len(inputs):
        return (), ()

    exact_ops, palette_ops = [], []
    for operation in d4_module._変換群(teachers[0]["input"]):
        forward, reverse = {}, {}
        exact = palette_valid = True
        for pair in teachers:
            transformed = d4_module._変換群(pair["input"])[operation]
            exact = exact and transformed == pair["output"]
            if not d4_module._色写像を学ぶ(
                transformed, pair["output"], forward, reverse
            ):
                palette_valid = False
                break
        if exact:
            exact_ops.append(operation)
        if palette_valid and any(source != target for source, target in forward.items()):
            palette_ops.append((operation, tuple(sorted(forward.items()))))
    return tuple(exact_ops), tuple(palette_ops)


def predict_d4(grid, model, include_palette=True):
    exact_ops, palette_ops = model
    if not exact_ops and not palette_ops:
        return None
    if not d4_module._有効格子(grid):
        return None
    transformed = d4_module._変換群(grid)
    outputs = set()
    outputs.update(tuple(map(tuple, transformed[name])) for name in exact_ops)
    for name, pairs in (palette_ops if include_palette else ()):
        image = transformed[name]
        mapping = dict(pairs)
        colors = {color for row in image for color in row}
        if colors.issubset(mapping):
            outputs.add(tuple(tuple(mapping[color] for color in row) for row in image))
    if len(outputs) != 1:
        return None
    return [list(row) for row in next(iter(outputs))]


def self_check():
    teachers = [
        {"input": [[1, 2, 0], [0, 0, 0]], "output": [[1, 2, 0], [0, 0, 0]]},
        {"input": [[0, 1, 2], [0, 0, 0]], "output": [[0, 1, 2], [0, 0, 0]]},
    ]
    model = fit_d4(teachers)
    if not model[0] or predict_d4(teachers[0]["input"], model) != teachers[0]["output"]:
        raise SystemExit("support-2 D4 self-check failed")
    if fit_d4([teachers[0], teachers[0]]) != ((), ()):
        raise SystemExit("duplicate-input support-2 self-check failed")


self_check()
manifest = hashlib.sha256()
files = sorted(TRAINING_DIR.glob("*.json"))
eligible_tasks = loo_folds = unique_teacher_folds = 0
baseline_d4_answers = baseline_d4_exact = baseline_d4_wrong = 0
support2_answers = support2_exact = support2_wrong = 0
translation_answers = translation_exact = translation_wrong = 0
incremental_answers = incremental_exact = incremental_wrong = conflicts = agreements = 0
strata = {}
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

        baseline_model = d4_module.格子D4教材(teachers)
        baseline, _ = baseline_model.候補(heldout["input"], {})
        if baseline is not None:
            baseline_d4_answers += 1
            if baseline == heldout["output"]:
                baseline_d4_exact += 1
            else:
                baseline_d4_wrong += 1

        model2 = fit_d4(teachers)
        candidate = predict_d4(heldout["input"], model2, include_palette=False)
        relation_counts = [
            sum(
                transformed == pair["output"]
                for transformed in d4_module._変換群(pair["input"]).values()
            )
            for pair in teachers
        ]
        stratum = (
            "all_teacher_pairs_have_unique_D4_match"
            if all(count == 1 for count in relation_counts)
            else "at_least_one_teacher_pair_has_ambiguous_D4_match"
        )
        summary = strata.setdefault(
            stratum,
            {"answers": 0, "exact": 0, "wrong": 0, "incremental_answers": 0,
             "incremental_exact": 0, "incremental_wrong": 0},
        )
        operation_key = "/".join(model2[0]) or "no_exact_operation"
        operation_summary = strata.setdefault(
            f"operation_set:{operation_key}",
            {"answers": 0, "exact": 0, "wrong": 0, "incremental_answers": 0,
             "incremental_exact": 0, "incremental_wrong": 0},
        )
        if candidate is not None:
            support2_answers += 1
            summary["answers"] += 1
            operation_summary["answers"] += 1
            if candidate == heldout["output"]:
                support2_exact += 1
                summary["exact"] += 1
                operation_summary["exact"] += 1
            else:
                support2_wrong += 1
                summary["wrong"] += 1
                operation_summary["wrong"] += 1

        translation_model = 全前景平行移動教材(teachers)
        translation, _ = translation_model.候補(heldout["input"], {})
        if translation is not None:
            translation_answers += 1
            if translation == heldout["output"]:
                translation_exact += 1
            else:
                translation_wrong += 1

        if candidate is not None:
            existing = [value for value in (baseline, translation) if value is not None]
            if not existing:
                incremental_answers += 1
                summary["incremental_answers"] += 1
                operation_summary["incremental_answers"] += 1
                if candidate == heldout["output"]:
                    incremental_exact += 1
                    summary["incremental_exact"] += 1
                    operation_summary["incremental_exact"] += 1
                else:
                    incremental_wrong += 1
                    summary["incremental_wrong"] += 1
                    operation_summary["incremental_wrong"] += 1
            elif all(candidate == value for value in existing):
                agreements += 1
            else:
                conflicts += 1

result = {
    "schema": "arc2-p5-d4-support2-operation-strata-loo.v1",
    "instruction_id": "ARC2-SCORE-GATE-20261024",
    "reference_source_commit": REFERENCE_COMMIT,
    "source_sha256": {
        f"{REFERENCE_COMMIT}:{D4_PATH}": D4_SHA256,
        TRANSLATION_PATH: hashlib.sha256((ROOT / TRANSLATION_PATH).read_bytes()).hexdigest(),
        Path(__file__).name: hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    },
    "data_source": "public ARC-AGI-2 training split only",
    "training_manifest_sha256": manifest.hexdigest(),
    "public_training_files": len(files),
    "eligible_tasks_minimum_teacher_support_2": eligible_tasks,
    "loo_folds": loo_folds,
    "loo_folds_with_at_least_2_unique_teacher_inputs": unique_teacher_folds,
    "baseline_support3_D4_answers": baseline_d4_answers,
    "baseline_support3_D4_exact": baseline_d4_exact,
    "baseline_support3_D4_wrong": baseline_d4_wrong,
    "support2_exact_D4_answers": support2_answers,
    "support2_exact_D4_exact": support2_exact,
    "support2_exact_D4_wrong": support2_wrong,
    "existing_translation_answers": translation_answers,
    "existing_translation_exact": translation_exact,
    "existing_translation_wrong": translation_wrong,
    "incremental_answers_over_D4_and_translation": incremental_answers,
    "incremental_exact": incremental_exact,
    "incremental_wrong": incremental_wrong,
    "agreements_with_existing_answer": agreements,
    "conflicts_with_existing_answer": conflicts,
    "candidate_result_by_teacher_or_fitted_operation_strata": strata,
    "elapsed_seconds": round(time.perf_counter() - started, 3),
    "evaluation_solutions_read": False,
    "task_identifiers_or_grids_saved": False,
    "decision": "REVIEW_REQUIRED"
    if incremental_exact and not incremental_wrong and not conflicts
    else "REJECT_OR_REFINE",
}
report = Path(__file__).with_suffix(".json")
report.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
