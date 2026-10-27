"""Aggregate a fallback-excluded public-solution comparison for ARC2.

Predictions are already fixed before this script reads public solutions. It
prints and saves aggregate counts only; it never writes task IDs or target
grids to the report.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
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


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _measure(run: dict[str, Any], targets: dict[str, Any]) -> dict[str, Any]:
    predictions = _load(run["output"])
    audit = _load(run["audit"])
    fallback_pairs = {
        (item["task_id"], item["test_index"]) for item in audit["fallbacks"]
    }
    if not set(predictions).issubset(targets):
        raise ValueError("A prediction task has no public post-hoc target.")

    raw_examples = 0
    nonfallback_examples = 0
    fallback_exact_examples = 0
    raw_tasks = 0
    nonfallback_tasks = 0
    example_count = 0
    by_example: dict[tuple[str, int], dict[str, Any]] = {}

    for task_id, task_predictions in predictions.items():
        task_targets = targets[task_id]
        if len(task_predictions) != len(task_targets):
            raise ValueError(f"Prediction/target count mismatch in {run['kernel']}.")
        task_raw: list[bool] = []
        task_nonfallback: list[bool] = []
        for index, (prediction, target) in enumerate(
            zip(task_predictions, task_targets)
        ):
            exact = (
                prediction["attempt_1"] == target
                or prediction["attempt_2"] == target
            )
            fallback = (task_id, index) in fallback_pairs
            counted = exact and not fallback
            example_count += 1
            raw_examples += exact
            nonfallback_examples += counted
            fallback_exact_examples += exact and fallback
            task_raw.append(exact)
            task_nonfallback.append(counted)
            by_example[(task_id, index)] = {
                "raw_exact": exact,
                "nonfallback_exact": counted,
                "fallback": fallback,
                "prediction": prediction,
            }
        raw_tasks += all(task_raw)
        nonfallback_tasks += all(task_nonfallback)

    return {
        "kernel": run["kernel"],
        "version": run["version"],
        "output_sha256": _sha256(run["output"]),
        "audit_sha256": _sha256(run["audit"]),
        "fallback_count": len(fallback_pairs),
        "raw_output_exact_examples_including_fallback": raw_examples,
        "fallback_exact_examples_excluded_from_solver_metric": fallback_exact_examples,
        "solver_exact_examples_excluding_fallback": nonfallback_examples,
        "raw_output_exact_tasks_including_fallback": raw_tasks,
        "solver_exact_tasks_excluding_fallback": nonfallback_tasks,
        "example_count": example_count,
        "task_count": len(predictions),
        "_by_example": by_example,
    }


def main() -> None:
    targets = _load(TARGETS)
    measured = {name: _measure(run, targets) for name, run in RUNS.items()}
    before = measured["v51"]["_by_example"]
    after = measured["v61"]["_by_example"]
    if set(before) != set(after):
        raise ValueError("The paired candidates do not cover the same examples.")

    changed_examples = raw_gains = raw_regressions = 0
    nonfallback_gains = nonfallback_regressions = 0
    changed_fallback_examples = 0
    for key, previous in before.items():
        current = after[key]
        changed = previous["prediction"] != current["prediction"]
        changed_examples += changed
        changed_fallback_examples += changed and (
            previous["fallback"] or current["fallback"]
        )
        raw_gains += current["raw_exact"] and not previous["raw_exact"]
        raw_regressions += previous["raw_exact"] and not current["raw_exact"]
        nonfallback_gains += (
            current["nonfallback_exact"] and not previous["nonfallback_exact"]
        )
        nonfallback_regressions += (
            previous["nonfallback_exact"] and not current["nonfallback_exact"]
        )

    summaries = {
        name: {key: value for key, value in result.items() if key != "_by_example"}
        for name, result in measured.items()
    }
    report = {
        "schema": "arc2-fallback-excluded-paired-public-evaluation-v1",
        "run_id": "ARC2-V61-FALLBACK-EXCLUDED-PAIRED-20261026T184028Z",
        "track": "ARC2",
        "dataset": "Kaggle ARC2 public training solutions, post-hoc scorer only",
        "challenge_file": "入力/Kaggle/arc-agi_test_challenges.json",
        "challenge_sha256": "232264c58f825ee77327dcfc9f4e5cb2f83b8d997eb69032be1bf2205bbe1a83",
        "target_file": str(TARGETS.relative_to(ROOT)),
        "target_sha256": _sha256(TARGETS),
        "predictions_fixed_before_targets_loaded": True,
        "scoring": "An exact grid is counted as solver-correct only when the output audit does not mark that test example as fallback. A task is exact only when all its grids are solver-correct.",
        "candidates": summaries,
        "paired_delta": {
            "changed_examples": changed_examples,
            "changed_examples_marked_fallback": changed_fallback_examples,
            "raw_output_correct_gains_including_fallback": raw_gains,
            "raw_output_regressions_including_fallback": raw_regressions,
            "solver_correct_gains_excluding_fallback": nonfallback_gains,
            "solver_regressions_excluding_fallback": nonfallback_regressions,
        },
        "conclusion": "v61 has one additional exact public output only when fallback matches are included. Excluding fallback, v51 and v61 are tied at 9/259 exact grids and 8/240 exact tasks; the teacher-pair change demonstrates no solver-ability gain on this evaluation.",
        "official_score": None,
        "limitations": [
            "This is a local public-data comparison, not an official Kaggle score.",
            "Fallback matches are excluded from the solver-ability metric.",
            "No task IDs, target grids, or per-example correctness labels are persisted.",
        ],
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
