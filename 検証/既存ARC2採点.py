# 旧ARC採点器の関数本体を無改変で再利用。solver本体は移植しない。
# gatchimuchio/ARC-Layer-0-Functional-Compliance @454670a13024ccf28dc7e9ed9d8ee256ee6cd365
# arc_agi_2_solver/arc2_solver_core_audit.py
from __future__ import annotations
from collections import Counter
from typing import Any

def non_placeholder_attempts(attempts: list[AttemptCandidate]) -> list[AttemptCandidate]:
    return [attempt for attempt in attempts if attempt.source != "placeholder_input"]

def task_solved_by_predictions(prediction_entries: list[list[AttemptCandidate]], solutions: list[Grid]) -> bool:
    if len(prediction_entries) != len(solutions):
        return False
    for test_index, expected in enumerate(solutions):
        attempts = prediction_entries[test_index]
        if not any(attempt.output == expected for attempt in attempts):
            return False
    return True

def evaluate_solver_core(tasks: dict[str, Any], solutions: dict[str, list[Grid]]) -> dict[str, Any]:
    solved_task_ids: list[str] = []
    wrong_attempted_task_ids: list[str] = []
    no_candidate_task_ids: list[str] = []
    records: list[dict[str, Any]] = []
    component_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()

    for task_id, task in sorted(tasks.items()):
        result = solve_task(task)
        prediction_entries = [prediction.attempts for prediction in result.predictions]
        emitted = [
            attempt
            for attempts in prediction_entries
            for attempt in non_placeholder_attempts(attempts)
        ]
        solved = task_solved_by_predictions(prediction_entries, solutions.get(task_id, []))
        if solved:
            solved_task_ids.append(task_id)
        elif emitted:
            wrong_attempted_task_ids.append(task_id)
        else:
            no_candidate_task_ids.append(task_id)

        for attempt in emitted:
            component_counter[attempt.component] += 1
            source_counter[attempt.source] += 1

        records.append(
            {
                "task_id": task_id,
                "solved": solved,
                "candidate_emitted": bool(emitted),
                "emitted_components": sorted({attempt.component for attempt in emitted}),
                "emitted_sources": sorted({attempt.source for attempt in emitted}),
                "test_count": len(task.get("test", [])),
                "non_placeholder_attempt_count": len(emitted),
            }
        )

    return {
        "total_tasks": len(tasks),
        "solved_count": len(solved_task_ids),
        "score": len(solved_task_ids) / len(tasks) if tasks else 0.0,
        "solved_task_ids": solved_task_ids,
        "wrong_attempted_task_ids": wrong_attempted_task_ids,
        "no_candidate_task_ids": no_candidate_task_ids,
        "component_attempt_counts": dict(sorted(component_counter.items())),
        "source_attempt_counts": dict(sorted(source_counter.items())),
        "task_records": records,
    }
