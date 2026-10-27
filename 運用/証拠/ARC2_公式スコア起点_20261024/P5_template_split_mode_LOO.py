"""Evaluate teacher-inferred template split modes on public-training LOO folds."""
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
MODULE_PATH = "接続/ARC2/既存穴充填.py"
PRIOR_PATH = "接続/ARC2/テンプレート充填教材.json"


def git_blob(relative: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{COMMIT}:{relative}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


module_bytes = git_blob(MODULE_PATH)
prior_bytes = git_blob(PRIOR_PATH)
source_sha = hashlib.sha256(module_bytes).hexdigest()
prior_sha = hashlib.sha256(prior_bytes).hexdigest()
if source_sha != "451d07ba636d4e4ce5a2443cfe56745f55fd16cf8845a2f4c9f62abd08d78b53":
    raise SystemExit("reference renderer hash mismatch")
if prior_sha != "8f5f24571f0457c44af68b57b9aebbcf4dabbb9164f24942108e1b98f635f112":
    raise SystemExit("reference prior manifest hash mismatch")

renderer_module = ModuleType("arc2_p5_template_hole_renderer")
renderer_module.__file__ = f"{COMMIT}:{MODULE_PATH}"
exec(compile(module_bytes, renderer_module.__file__, "exec"), renderer_module.__dict__)
candidates = renderer_module._template_hole_pack_candidates

prior_manifest = json.loads(prior_bytes.decode("utf-8"))
if prior_manifest.get("分割") != "training":
    raise SystemExit("prior examples are not training-only")
train_dir = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
prior, prior_task_ids = [], set()
seen = set()
for source in prior_manifest["教材"]:
    task_id = source["課題ID"]
    prior_task_ids.add(task_id)
    original = json.loads((train_dir / f"{task_id}.json").read_text(encoding="utf-8"))
    for index in source["訓練例位置"]:
        key = (task_id, index)
        if key in seen:
            raise SystemExit("duplicate fixed prior teacher")
        seen.add(key)
        prior.append(original["train"][index])


def unique_legacy(grid):
    rows = candidates(grid)
    return rows[0]["output"] if len(rows) == 1 else None


def consistent_modes(pairs):
    retained = None
    for pair in pairs:
        matching = {
            row["split_mode"] for row in candidates(pair["input"])
            if row["output"] == pair["output"]
        }
        retained = matching if retained is None else retained & matching
        if not retained:
            return set()
    return retained or set()


def mode_prediction(grid, modes):
    outputs = {
        tuple(tuple(int(value) for value in row) for row in candidate["output"])
        for candidate in candidates(grid)
        if candidate["split_mode"] in modes
    }
    if len(outputs) != 1:
        return None
    return [list(row) for row in next(iter(outputs))]


files = sorted(train_dir.glob("*.json"))
manifest = hashlib.sha256()
eligible_tasks = excluded_prior_tasks = excluded_prior_folds = loo_folds = 0
baseline_answers = baseline_exact = baseline_wrong = 0
candidate_answers = candidate_exact = candidate_wrong = 0
incremental_answers = incremental_exact = incremental_wrong = disagreements = 0
started = time.perf_counter()

for path in files:
    raw = path.read_bytes()
    manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
    task = json.loads(raw)
    examples = task.get("train", [])
    if path.stem in prior_task_ids:
        excluded_prior_tasks += 1
        if len(examples) >= 4:
            excluded_prior_folds += len(examples)
        continue
    if len(examples) < 4:
        continue
    eligible_tasks += 1
    for index, heldout in enumerate(examples):
        loo_folds += 1
        teachers = prior + [pair for i, pair in enumerate(examples) if i != index]
        modes = consistent_modes(teachers)
        prediction = mode_prediction(heldout["input"], modes) if modes else None
        baseline_fit = all(
            (output := unique_legacy(pair["input"])) is not None
            and output == pair["output"]
            for pair in teachers
        )
        baseline = unique_legacy(heldout["input"]) if baseline_fit else None

        if baseline is not None:
            baseline_answers += 1
            if baseline == heldout["output"]:
                baseline_exact += 1
            else:
                baseline_wrong += 1
        if prediction is not None:
            candidate_answers += 1
            if prediction == heldout["output"]:
                candidate_exact += 1
            else:
                candidate_wrong += 1
            if baseline is None:
                incremental_answers += 1
                if prediction == heldout["output"]:
                    incremental_exact += 1
                else:
                    incremental_wrong += 1
            elif prediction != baseline:
                disagreements += 1

result = {
    "schema": "arc2-template-hole-mode-loo.v1",
    "instruction_id": "ARC2-SCORE-GATE-20261024",
    "source_commit": COMMIT,
    "source_sha256": {
        MODULE_PATH: source_sha,
        PRIOR_PATH: prior_sha,
    },
    "data_source": "public ARC-AGI-2 training split only",
    "training_manifest_sha256": manifest.hexdigest(),
    "public_training_files": len(files),
    "fixed_prior_examples": len(prior),
    "fixed_prior_source_tasks_excluded_from_evaluation": excluded_prior_tasks,
    "eligible_tasks_minimum_teacher_support_3": eligible_tasks,
    "excluded_prior_source_folds": excluded_prior_folds,
    "loo_folds": loo_folds,
    "baseline_unique_candidate_answers": baseline_answers,
    "baseline_exact": baseline_exact,
    "baseline_wrong": baseline_wrong,
    "split_mode_candidate_answers": candidate_answers,
    "split_mode_candidate_exact": candidate_exact,
    "split_mode_candidate_wrong": candidate_wrong,
    "incremental_answers": incremental_answers,
    "incremental_exact": incremental_exact,
    "incremental_wrong": incremental_wrong,
    "disagreements_on_baseline_answered_folds": disagreements,
    "elapsed_seconds": round(time.perf_counter() - started, 3),
    "evaluation_solutions_read": False,
    "challenge_inputs_read": False,
    "task_identifiers_or_grids_saved": False,
    "hypothesis": "Infer a generic split_mode from complete teacher pairs; answer only if every surviving split_mode produces one identical query grid.",
    "decision": "REJECT_NO_INCREMENTAL_LOO_ANSWER" if incremental_answers == 0 else "REVIEW_REQUIRED",
}
report = Path(__file__).with_suffix(".json")
report.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
