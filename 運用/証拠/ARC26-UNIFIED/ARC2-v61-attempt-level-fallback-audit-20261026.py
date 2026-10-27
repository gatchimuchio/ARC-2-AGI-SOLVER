"""Score fixed ARC2 outputs while excluding only actual fallback copies.

The audit's fallback marker means the HDS primary answer was absent. The
submission wrapper can still place a separately generated, non-identity
candidate in attempt_2. This scorer excludes input-copy fallback matches but
counts a correct non-identity attempt_2 on such a row.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
CHALLENGES = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
TARGETS = ROOT / "入力/Kaggle/arc-agi_training_solutions.json"
RUNS = {
    "v51": {
        "output": ROOT
        / "出力/Kaggle/arc2-v51-local-largest-component-object-candidate/v13/wrapper-output/submission.json",
        "audit": ROOT
        / "出力/Kaggle/arc2-v51-local-largest-component-object-candidate/v13/wrapper-output/submission_audit.json",
        "kernel": "tecchannn/arc2-v51-local-largest-component-object-candidate",
        "version": 13,
    },
    "v61": {
        "output": ROOT
        / "出力/Kaggle/arc2-v61-local-teacher-pair-consensus-candidate/v1/wrapper-output/submission.json",
        "audit": ROOT
        / "出力/Kaggle/arc2-v61-local-teacher-pair-consensus-candidate/v1/wrapper-output/submission_audit.json",
        "kernel": "tecchannn/arc2-v61-local-teacher-pair-consensus-candidate",
        "version": 1,
    },
}
REPORT = Path(__file__).with_suffix(".json")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def measure(
    run: dict[str, Any],
    challenges: dict[str, Any],
    targets: dict[str, Any],
) -> dict[str, Any]:
    output = load(run["output"])
    audit = load(run["audit"])
    fallback_pairs = {
        (item["task_id"], item["test_index"]) for item in audit["fallbacks"]
    }
    if not set(output).issubset(challenges) or not set(output).issubset(targets):
        raise ValueError("Output keys do not align with challenge/target files.")

    raw_exact = fallback_row_raw_exact = fallback_input_copy_exact = 0
    fallback_nonidentity_attempt2_exact = solver_exact = 0
    raw_exact_tasks = solver_exact_tasks = examples = 0
    per_example: dict[tuple[str, int], dict[str, Any]] = {}

    for task_id, predictions in output.items():
        tests = challenges[task_id]["test"]
        expected = targets[task_id]
        if len(predictions) != len(tests) or len(predictions) != len(expected):
            raise ValueError("Prediction/challenge/target test counts differ.")
        task_raw: list[bool] = []
        task_solver: list[bool] = []
        for index, (prediction, test, target) in enumerate(
            zip(predictions, tests, expected)
        ):
            query = test["input"]
            attempt1 = prediction["attempt_1"]
            attempt2 = prediction["attempt_2"]
            raw = attempt1 == target or attempt2 == target
            fallback = (task_id, index) in fallback_pairs
            input_copy = fallback and (
                (attempt1 == query and attempt1 == target)
                or (attempt2 == query and attempt2 == target)
            )
            nonidentity_second = fallback and attempt2 != query and attempt2 == target
            solver = nonidentity_second if fallback else raw
            examples += 1
            raw_exact += raw
            fallback_row_raw_exact += fallback and raw
            fallback_input_copy_exact += input_copy
            fallback_nonidentity_attempt2_exact += nonidentity_second
            solver_exact += solver
            task_raw.append(raw)
            task_solver.append(solver)
            per_example[(task_id, index)] = {
                "raw": raw,
                "solver": solver,
                "fallback": fallback,
                "attempt1": attempt1,
                "attempt2": attempt2,
            }
        raw_exact_tasks += all(task_raw)
        solver_exact_tasks += all(task_solver)

    return {
        "kernel": run["kernel"],
        "version": run["version"],
        "output_sha256": sha256(run["output"]),
        "audit_sha256": sha256(run["audit"]),
        "fallback_rows": len(fallback_pairs),
        "raw_exact_examples_including_any_match": raw_exact,
        "raw_exact_fallback_rows": fallback_row_raw_exact,
        "fallback_input_copy_exact_examples_excluded": fallback_input_copy_exact,
        "fallback_nonidentity_attempt2_exact_examples_counted": fallback_nonidentity_attempt2_exact,
        "attempt_level_solver_exact_examples": solver_exact,
        "raw_exact_tasks": raw_exact_tasks,
        "attempt_level_solver_exact_tasks": solver_exact_tasks,
        "example_count": examples,
        "task_count": len(output),
        "_per_example": per_example,
    }


def main() -> None:
    challenges = load(CHALLENGES)
    targets = load(TARGETS)
    measured = {name: measure(run, challenges, targets) for name, run in RUNS.items()}
    before = measured["v51"]["_per_example"]
    after = measured["v61"]["_per_example"]
    if set(before) != set(after):
        raise ValueError("Paired runs do not cover the same examples.")

    changed = raw_gains = raw_regressions = solver_gains = solver_regressions = 0
    changed_fallback = 0
    for key, old in before.items():
        new = after[key]
        changed += (old["attempt1"], old["attempt2"]) != (
            new["attempt1"], new["attempt2"]
        )
        changed_fallback += (
            (old["attempt1"], old["attempt2"])
            != (new["attempt1"], new["attempt2"])
            and (old["fallback"] or new["fallback"])
        )
        raw_gains += new["raw"] and not old["raw"]
        raw_regressions += old["raw"] and not new["raw"]
        solver_gains += new["solver"] and not old["solver"]
        solver_regressions += old["solver"] and not new["solver"]

    candidates = {
        name: {key: value for key, value in row.items() if key != "_per_example"}
        for name, row in measured.items()
    }
    report = {
        "schema": "arc2-attempt-level-fallback-paired-evaluation-v1",
        "run_id": "ARC2-V61-ATTEMPT-LEVEL-FALLBACK-AUDIT-20261026T203151Z",
        "track": "ARC2",
        "dataset": "Public ARC2 training solutions; post-hoc scoring only",
        "challenge_sha256": sha256(CHALLENGES),
        "target_sha256": sha256(TARGETS),
        "v61_teacher_pair_builder_sha256": sha256(
            ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-object-teacher-pair-consensus-v61-build-20261026.py"
        ),
        "scoring_rule": "For an audit-marked HDS primary HOLD row, exclude input-copy matches but count a correct non-identity attempt_2 as a generated candidate. For non-HOLD rows, use the official any-attempt exact-match rule.",
        "fallback_marker_scope": "The wrapper adds a fallback row when the HDS primary answer is missing; it does not assert that attempt_2 is also a fallback.",
        "predictions_fixed_before_posthoc_scoring": True,
        "candidates": candidates,
        "paired_delta": {
            "changed_examples": changed,
            "changed_examples_on_fallback_marked_rows": changed_fallback,
            "raw_output_gains_including_fallback": raw_gains,
            "raw_output_regressions_including_fallback": raw_regressions,
            "attempt_level_solver_gains_excluding_input_copy_fallback": solver_gains,
            "attempt_level_solver_regressions_excluding_input_copy_fallback": solver_regressions,
        },
        "conclusion": "The previous row-level exclusion was overly conservative: the audit marker records a missing HDS primary answer, while v61 can supply a separately generated non-identity attempt_2. This report counts that candidate and still excludes input-copy fallback matches.",
        "official_score": None,
        "limitations": [
            "Local public-data comparison only; not an official Kaggle score.",
            "No task IDs, grids, targets, or per-example labels are persisted.",
            "A non-identity candidate hit demonstrates an output candidate, not that the HDS primary mechanism accepted it.",
        ],
    }
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
