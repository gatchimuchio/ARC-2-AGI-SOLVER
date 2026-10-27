"""Check the translation candidate against full HDS on LOO and challenge inputs."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[3]
COMMIT = "2759d393a8d79824d36754785ce16f66d0493ebd"
D4_PATH = "接続/ARC2/格子D4教材.py"
EXPECTED_D4_SHA256 = "a5d6a2eedb063a876b47cd5d2fdf28cec13af535d89b9fef65df41b81c5ccf18"
sys.path.insert(0, str(ROOT))
from 接続.ARC2.HDS接続 import 課題を解く, 事前教材を読む  # noqa: E402
from 接続.ARC2.全前景平行移動教材 import 全前景平行移動教材  # noqa: E402

raw_d4 = subprocess.run(
    ["git", "show", f"{COMMIT}:{D4_PATH}"], cwd=ROOT, check=True, capture_output=True
).stdout
if hashlib.sha256(raw_d4).hexdigest() != EXPECTED_D4_SHA256:
    raise SystemExit("reference D4 module hash mismatch")
d4_module = ModuleType("arc2_p5_d4_reference")
exec(compile(raw_d4, f"{COMMIT}:{D4_PATH}", "exec"), d4_module.__dict__)

train_dir = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
training_files = sorted(train_dir.glob("*.json"))
training_manifest = hashlib.sha256()
prior = 事前教材を読む()
loo_candidates = loo_exact = loo_wrong = loo_hds_holds = 0
loo_hds_answers = loo_hds_matches = loo_hds_conflicts = 0
loo_family_adopted = loo_family_not_adopted = 0
loo_hold_reasons = Counter()
started = time.perf_counter()

for path in training_files:
    raw = path.read_bytes()
    training_manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
    examples = json.loads(raw).get("train", [])
    if len(examples) < 4:
        continue
    for index, heldout in enumerate(examples):
        teachers = [pair for i, pair in enumerate(examples) if i != index]
        baseline = d4_module.格子D4教材(teachers).候補(heldout["input"], {})[0]
        if baseline is not None:
            continue
        translation_model = 全前景平行移動教材(teachers)
        candidate, _ = translation_model.候補(heldout["input"], {})
        if candidate is None:
            continue
        loo_candidates += 1
        if candidate == heldout["output"]:
            loo_exact += 1
        else:
            loo_wrong += 1

        solver_result = 課題を解く(
            {"train": teachers, "test": [{"input": heldout["input"]}]}, prior
        )
        result = solver_result["results"][0]
        answer = result.get("answer")
        if answer is None:
            loo_hds_holds += 1
            loo_hold_reasons.update(result.get("reasons", []))
        else:
            loo_hds_answers += 1
            if answer == candidate:
                loo_hds_matches += 1
            else:
                loo_hds_conflicts += 1
        family_rows = solver_result.get("families", [])
        family = next(
            (row for row in family_rows if row.get("境界") == "ARC全前景平行移動"),
            None,
        )
        if family and family.get("採用可") and family.get("同値採用"):
            loo_family_adopted += 1
        else:
            loo_family_not_adopted += 1

challenge_path = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
challenge_raw = challenge_path.read_bytes()
challenge = json.loads(challenge_raw)
if hashlib.sha256(challenge_raw).hexdigest() != "232264c58f825ee77327dcfc9f4e5cb2f83b8d997eb69032be1bf2205bbe1a83":
    raise SystemExit("official challenge input hash mismatch")
challenge_tasks = challenge_tests = challenge_candidate_tasks = 0
challenge_candidate_outputs = challenge_hds_matches = challenge_hds_holds = challenge_hds_conflicts = 0
challenge_hold_reasons = Counter()
for task in challenge.values():
    challenge_tasks += 1
    teachers = task.get("train", [])
    test_pairs = task.get("test", [])
    challenge_tests += len(test_pairs)
    if len(teachers) < 3:
        continue
    model = 全前景平行移動教材(teachers)
    predictions = [model.候補(pair["input"], {})[0] for pair in test_pairs]
    if not any(prediction is not None for prediction in predictions):
        continue
    challenge_candidate_tasks += 1
    solver_result = 課題を解く(
        {"train": teachers, "test": [{"input": pair["input"]} for pair in test_pairs]},
        prior,
    )
    for prediction, result in zip(predictions, solver_result["results"]):
        if prediction is None:
            continue
        challenge_candidate_outputs += 1
        answer = result.get("answer")
        if answer is None:
            challenge_hds_holds += 1
            challenge_hold_reasons.update(result.get("reasons", []))
        elif answer == prediction:
            challenge_hds_matches += 1
        else:
            challenge_hds_conflicts += 1

result = {
    "schema": "arc2-p5-global-translation-full-hds-check.v1",
    "instruction_id": "ARC2-SCORE-GATE-20261024",
    "candidate_source_sha256": hashlib.sha256(
        (ROOT / "接続/ARC2/全前景平行移動教材.py").read_bytes()
    ).hexdigest(),
    "hds_source_sha256": hashlib.sha256((ROOT / "接続/ARC2/HDS接続.py").read_bytes()).hexdigest(),
    "baseline_source": {f"{COMMIT}:{D4_PATH}": EXPECTED_D4_SHA256},
    "training_manifest_sha256": training_manifest.hexdigest(),
    "loo_candidate_folds_incremental_over_D4": loo_candidates,
    "loo_exact": loo_exact,
    "loo_wrong": loo_wrong,
    "full_hds_holds_on_candidate_folds": loo_hds_holds,
    "full_hds_answers_on_candidate_folds": loo_hds_answers,
    "full_hds_matches_candidate": loo_hds_matches,
    "full_hds_conflicts": loo_hds_conflicts,
    "full_hds_hold_reason_counts": dict(sorted(loo_hold_reasons.items())),
    "candidate_family_adopted_on_loo_folds": loo_family_adopted,
    "candidate_family_not_adopted_on_loo_folds": loo_family_not_adopted,
    "official_challenge_sha256": hashlib.sha256(challenge_raw).hexdigest(),
    "official_challenge_tasks": challenge_tasks,
    "official_challenge_test_inputs": challenge_tests,
    "official_challenge_tasks_with_candidate": challenge_candidate_tasks,
    "official_challenge_candidate_outputs": challenge_candidate_outputs,
    "full_hds_matches_candidate_on_challenge": challenge_hds_matches,
    "full_hds_holds_on_challenge_candidate": challenge_hds_holds,
    "full_hds_conflicts_on_challenge": challenge_hds_conflicts,
    "full_hds_hold_reason_counts_on_challenge": dict(sorted(challenge_hold_reasons.items())),
    "evaluation_solutions_read": False,
    "task_identifiers_or_grids_saved": False,
    "elapsed_seconds": round(time.perf_counter() - started, 3),
}
report = Path(__file__).with_suffix(".json")
report.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
