"""Measure exact support-2 D4 as a second guess alongside current full HDS."""

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
REFERENCE_COMMIT = "2759d393a8d79824d36754785ce16f66d0493ebd"
D4_PATH = "接続/ARC2/格子D4教材.py"
D4_SHA256 = "a5d6a2eedb063a876b47cd5d2fdf28cec13af535d89b9fef65df41b81c5ccf18"
CHALLENGE_SHA256 = "232264c58f825ee77327dcfc9f4e5cb2f83b8d997eb69032be1bf2205bbe1a83"
sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))
sys.path.insert(1, str(ROOT))
from 接続.ARC2.HDS接続 import 課題を解く, 事前教材を読む  # noqa: E402


raw_d4 = subprocess.run(
    ["git", "show", f"{REFERENCE_COMMIT}:{D4_PATH}"],
    cwd=ROOT,
    check=True,
    capture_output=True,
).stdout
if hashlib.sha256(raw_d4).hexdigest() != D4_SHA256:
    raise SystemExit("reference D4 source hash mismatch")
d4_module = ModuleType("arc2_p5_d4_support2_hds_reference")
exec(compile(raw_d4, f"{REFERENCE_COMMIT}:{D4_PATH}", "exec"), d4_module.__dict__)


def fit_exact_d4(teachers):
    if len(teachers) < 2:
        return ()
    if any(
        not isinstance(pair, dict)
        or not d4_module._有効格子(pair.get("input"))
        or not d4_module._有効格子(pair.get("output"))
        for pair in teachers
    ):
        return ()
    input_grids = [tuple(map(tuple, pair["input"])) for pair in teachers]
    if len(set(input_grids)) != len(input_grids):
        return ()
    operations = []
    for name in d4_module._変換群(teachers[0]["input"]):
        if all(
            d4_module._変換群(pair["input"])[name] == pair["output"]
            for pair in teachers
        ):
            operations.append(name)
    return tuple(operations)


def predict_exact_d4(grid, operations):
    if not operations or not d4_module._有効格子(grid):
        return None
    transformed = d4_module._変換群(grid)
    outputs = {tuple(map(tuple, transformed[name])) for name in operations}
    if len(outputs) != 1:
        return None
    return [list(row) for row in next(iter(outputs))]


def first_guess(solver_result, index, input_grid):
    rows = solver_result.get("results", [])
    result = rows[index] if index < len(rows) else {}
    answer = result.get("answer") if isinstance(result, dict) else None
    return answer if d4_module._有効格子(answer) else input_grid


def self_check():
    teachers = [
        {"input": [[1, 2, 0], [0, 0, 0]], "output": [[1, 2, 0], [0, 0, 0]]},
        {"input": [[0, 1, 2], [0, 0, 0]], "output": [[0, 1, 2], [0, 0, 0]]},
    ]
    operations = fit_exact_d4(teachers)
    if not operations or predict_exact_d4(teachers[0]["input"], operations) != teachers[0]["output"]:
        raise SystemExit("support-2 exact D4 self-check failed")


self_check()
prior = 事前教材を読む()
train_dir = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
training_files = sorted(train_dir.glob("*.json"))
training_manifest = hashlib.sha256()
loo_folds = candidate_folds = candidate_exact = candidate_wrong = 0
hds_holds = hds_answers = candidate_matches_hds = candidate_conflicts_hds = 0
second_attempt_distinct = second_attempt_exact = second_attempt_wrong = 0
first_guess_exact = union_guess_exact = 0
challenge_path = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
challenge_raw = challenge_path.read_bytes()
if hashlib.sha256(challenge_raw).hexdigest() != CHALLENGE_SHA256:
    raise SystemExit("official challenge input hash mismatch")
challenge = json.loads(challenge_raw)
challenge_tasks_with_candidate = challenge_inputs = challenge_candidates = 0
challenge_second_distinct = challenge_hds_holds = challenge_hds_answers = 0
challenge_matches_hds = challenge_conflicts_hds = 0
challenge_hold_reasons = Counter()
started = time.perf_counter()

for path in training_files:
    raw = path.read_bytes()
    training_manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
    examples = json.loads(raw).get("train", [])
    if len(examples) < 3:
        continue
    for index, heldout in enumerate(examples):
        loo_folds += 1
        teachers = [pair for i, pair in enumerate(examples) if i != index]
        candidate = predict_exact_d4(heldout["input"], fit_exact_d4(teachers))
        if candidate is None:
            continue
        candidate_folds += 1
        is_exact = candidate == heldout["output"]
        candidate_exact += int(is_exact)
        candidate_wrong += int(not is_exact)
        solver_result = 課題を解く(
            {"train": teachers, "test": [{"input": heldout["input"]}]}, prior
        )
        result = solver_result.get("results", [{}])[0]
        answer = result.get("answer")
        first = first_guess(solver_result, 0, heldout["input"])
        if answer is None:
            hds_holds += 1
            challenge_hold_reasons.update(result.get("reasons", []))
        else:
            hds_answers += 1
            if answer == candidate:
                candidate_matches_hds += 1
            else:
                candidate_conflicts_hds += 1
        if first == heldout["output"]:
            first_guess_exact += 1
        if first == heldout["output"] or candidate == heldout["output"]:
            union_guess_exact += 1
        if candidate != first:
            second_attempt_distinct += 1
            second_attempt_exact += int(is_exact)
            second_attempt_wrong += int(not is_exact)

for task in challenge.values():
    teachers = task.get("train", [])
    tests = task.get("test", [])
    if len(teachers) < 2:
        continue
    candidates = [
        predict_exact_d4(pair["input"], fit_exact_d4(teachers)) for pair in tests
    ]
    if not any(candidate is not None for candidate in candidates):
        continue
    challenge_tasks_with_candidate += 1
    challenge_inputs += len(tests)
    challenge_candidates += sum(candidate is not None for candidate in candidates)
    result = 課題を解く({"train": teachers, "test": tests}, prior)
    for index, (pair, candidate) in enumerate(zip(tests, candidates, strict=True)):
        if candidate is None:
            continue
        answer = result.get("results", [{}])[index].get("answer")
        first = first_guess(result, index, pair["input"])
        if answer is None:
            challenge_hds_holds += 1
        else:
            challenge_hds_answers += 1
            if answer == candidate:
                challenge_matches_hds += 1
            else:
                challenge_conflicts_hds += 1
        challenge_second_distinct += int(candidate != first)

report = {
    "schema": "arc2-p5-d4-support2-exact-hds-integration.v1",
    "instruction_id": "ARC2-SCORE-GATE-20261024",
    "reference_source_commit": REFERENCE_COMMIT,
    "reference_d4_sha256": D4_SHA256,
    "hds_source_sha256": hashlib.sha256((ROOT / "接続/ARC2/HDS接続.py").read_bytes()).hexdigest(),
    "probe_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "training_manifest_sha256": training_manifest.hexdigest(),
    "public_training_tasks_minimum_3_examples": sum(
        len(json.loads(path.read_text(encoding="utf-8")).get("train", [])) >= 3
        for path in training_files
    ),
    "public_training_loo_folds_minimum_teacher_support_2": loo_folds,
    "support2_exact_d4_candidate_folds": candidate_folds,
    "support2_exact_d4_exact": candidate_exact,
    "support2_exact_d4_wrong": candidate_wrong,
    "full_hds_holds_on_candidate_folds": hds_holds,
    "full_hds_answers_on_candidate_folds": hds_answers,
    "candidate_agrees_with_full_hds": candidate_matches_hds,
    "candidate_conflicts_with_full_hds": candidate_conflicts_hds,
    "current_first_guess_exact_on_candidate_folds": first_guess_exact,
    "current_first_or_new_candidate_exact_on_candidate_folds": union_guess_exact,
    "distinct_second_attempt_candidates": second_attempt_distinct,
    "distinct_second_attempt_exact": second_attempt_exact,
    "distinct_second_attempt_wrong": second_attempt_wrong,
    "loo_hold_reason_counts": dict(sorted(challenge_hold_reasons.items())),
    "challenge_sha256": hashlib.sha256(challenge_raw).hexdigest(),
    "challenge_tasks_with_candidate": challenge_tasks_with_candidate,
    "challenge_test_inputs_in_candidate_tasks": challenge_inputs,
    "challenge_candidate_outputs": challenge_candidates,
    "challenge_full_hds_holds_on_candidate_outputs": challenge_hds_holds,
    "challenge_full_hds_answers_on_candidate_outputs": challenge_hds_answers,
    "challenge_candidate_agreements_with_full_hds": challenge_matches_hds,
    "challenge_candidate_conflicts_with_full_hds": challenge_conflicts_hds,
    "challenge_distinct_second_attempt_candidates": challenge_second_distinct,
    "evaluation_solutions_read": False,
    "task_identifiers_or_grids_saved": False,
    "elapsed_seconds": round(time.perf_counter() - started, 3),
}
report_path = Path(__file__).with_suffix(".json")
report_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
