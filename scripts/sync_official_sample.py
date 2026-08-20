#!/usr/bin/env python3
"""Generate the ARC Prize 2026 ARC-AGI-2 Kaggle sample from official ARC-AGI-2 data."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

EXPECTED = {
    "arc-agi_evaluation_challenges.json": {
        "sha256": "e7c62a4bd211867c6b538f66b8013b81f299663c82ca062f49a52bf439d6e4e8",
        "size": 984679,
    },
    "arc-agi_evaluation_solutions.json": {
        "sha256": "84be4f4f39b79e82c36d565fc878830988b094917f052ee7069aef30b33ca8f1",
        "size": 223838,
    },
    "arc-agi_test_challenges.json": {
        "sha256": "232264c58f825ee77327dcfc9f4e5cb2f83b8d997eb69032be1bf2205bbe1a83",
        "size": 1015295,
    },
    "arc-agi_training_challenges.json": {
        "sha256": "779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5",
        "size": 4010050,
    },
    "arc-agi_training_solutions.json": {
        "sha256": "9f07a38bd25af5e83aa5bf85c5cb1a1fefdb30f6a755256fa65429e697ca97f9",
        "size": 658743,
    },
    "sample_submission.json": {
        "sha256": "6b372dce41ad86a941ccdcbebb2b1926fd4f011d77c824ff421d77730f169a9a",
        "size": 19936,
    },
}


def load_tasks(directory: Path) -> OrderedDict[str, dict[str, Any]]:
    tasks: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for path in sorted(directory.glob("*.json")):
        task_id = path.stem
        task = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(task, dict) or "train" not in task or "test" not in task:
            raise RuntimeError(f"unexpected ARC task shape: {path}")
        tasks[task_id] = task
    return tasks


def split_challenges_and_solutions(
    tasks: OrderedDict[str, dict[str, Any]],
) -> tuple[OrderedDict[str, dict[str, Any]], OrderedDict[str, list[Any]]]:
    challenges: OrderedDict[str, dict[str, Any]] = OrderedDict()
    solutions: OrderedDict[str, list[Any]] = OrderedDict()

    for task_id, task in tasks.items():
        test_challenges: list[dict[str, Any]] = []
        test_solutions: list[Any] = []
        for test_case in task["test"]:
            if "input" not in test_case or "output" not in test_case:
                raise RuntimeError(f"official task {task_id} lacks input/output in test case")
            test_challenges.append({"input": test_case["input"]})
            test_solutions.append(test_case["output"])

        challenges[task_id] = {
            "train": task["train"],
            "test": test_challenges,
        }
        solutions[task_id] = test_solutions

    return challenges, solutions


def build_sample_submission(
    test_challenges: OrderedDict[str, dict[str, Any]],
) -> OrderedDict[str, list[dict[str, Any]]]:
    zero = [[0, 0], [0, 0]]
    submission: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for task_id, task in test_challenges.items():
        submission[task_id] = [
            {"attempt_1": zero, "attempt_2": zero}
            for _ in task["test"]
        ]
    return submission


def encode_json(value: Any) -> bytes:
    # Kaggle sample files use Python's default compact json.dumps formatting,
    # preserving insertion order and without a trailing newline.
    return json.dumps(value).encode("utf-8")


def verify_payload(name: str, payload: bytes) -> None:
    expected = EXPECTED[name]
    actual_sha = hashlib.sha256(payload).hexdigest()
    actual_size = len(payload)
    if actual_sha != expected["sha256"] or actual_size != expected["size"]:
        raise RuntimeError(
            f"{name} mismatch: sha256={actual_sha} size={actual_size}; "
            f"expected sha256={expected['sha256']} size={expected['size']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True, help="checkout of arcprize/ARC-AGI-2")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    training = load_tasks(args.source / "data" / "training")
    evaluation = load_tasks(args.source / "data" / "evaluation")
    if len(training) != 1000:
        raise RuntimeError(f"expected 1000 training tasks, got {len(training)}")
    if len(evaluation) != 120:
        raise RuntimeError(f"expected 120 evaluation tasks, got {len(evaluation)}")

    training_challenges, training_solutions = split_challenges_and_solutions(training)
    evaluation_challenges, evaluation_solutions = split_challenges_and_solutions(evaluation)

    # Kaggle's local placeholder test file is the first 240 lexicographically
    # ordered training challenges. The hidden rerun file replaces this at scoring time.
    test_challenges: OrderedDict[str, dict[str, Any]] = OrderedDict(
        list(training_challenges.items())[:240]
    )
    sample_submission = build_sample_submission(test_challenges)

    outputs = OrderedDict(
        [
            ("arc-agi_evaluation_challenges.json", evaluation_challenges),
            ("arc-agi_evaluation_solutions.json", evaluation_solutions),
            ("arc-agi_test_challenges.json", test_challenges),
            ("arc-agi_training_challenges.json", training_challenges),
            ("arc-agi_training_solutions.json", training_solutions),
            ("sample_submission.json", sample_submission),
        ]
    )

    args.output.mkdir(parents=True, exist_ok=True)
    for name, value in outputs.items():
        payload = encode_json(value)
        verify_payload(name, payload)
        (args.output / name).write_bytes(payload)
        print(f"verified {name}: {len(payload)} bytes {hashlib.sha256(payload).hexdigest()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
