"""Versioned matched challenge worker audit for object extraction."""
from __future__ import annotations

from collections import defaultdict
from contextlib import redirect_stdout
import concurrent.futures
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v19-local-context-second-20261026/full-runtime/submission.json"
OUTPUT = Path(__file__).with_suffix(".json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_task_indices(challenge, baseline, candidate_class):
    affected = []
    candidate_examples = selected_examples = 0
    for task_id, task in sorted(challenge.items()):
        model = candidate_class(task["train"])
        base_rows = baseline[task_id]
        selects = False
        for index, pair in enumerate(task["test"]):
            candidate, _record = model.candidate(pair["input"])
            base = base_rows[index]
            if candidate is None or candidate == base["attempt_1"]:
                continue
            candidate_examples += 1
            if candidate == base["attempt_2"]:
                continue
            if base["attempt_1"] == base["attempt_2"]:
                selected_examples += 1
                selects = True
        if selects:
            affected.append({
                "task_id": task_id,
                "runtime_task": {
                    "train": task["train"],
                    "test": [{"input": pair["input"]} for pair in task["test"]],
                },
            })
    return affected, candidate_examples, selected_examples


def _run_task(index, runtime_task):
    os.environ["ARC2_PAYLOAD_ROOT"] = str(ROOT)
    sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2.Kaggle提出 import _worker, 結果を候補へ

    output = io.StringIO()
    with redirect_stdout(output):
        code = _worker(runtime_task)
    if code != 0:
        return index, {"error": "worker_exit"}
    try:
        raw = json.loads(output.getvalue())
        rows, _holds = 結果を候補へ("matched-challenge", runtime_task, raw)
        return index, {"rows": rows}
    except Exception as exc:
        return index, {"error": type(exc).__name__}


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2.物体抽出候補 import ObjectExtractionCandidate

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    affected, candidate_examples, selected_examples = _candidate_task_indices(
        challenge, baseline, ObjectExtractionCandidate
    )
    started = time.monotonic()
    worker_rows = [None] * len(affected)
    errors = 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:
        futures = [
            pool.submit(_run_task, index, record["runtime_task"])
            for index, record in enumerate(affected)
        ]
        for count, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            index, result = future.result()
            worker_rows[index] = result
            if count % 4 == 0 or count == len(futures):
                print(f"matched challenge tasks {count}/{len(futures)}", flush=True)

    # Test outputs are read only after all affected production-worker outputs freeze.
    targets = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in SOURCE_ROOT.glob("*.json")
    }
    current = {task_id: rows for task_id, rows in baseline.items()}
    for index, result in enumerate(worker_rows):
        if result is None or "rows" not in result:
            errors += 1
            continue
        task_id = affected[index]["task_id"]
        current[task_id] = result["rows"]

    def score(predictions):
        exact_examples = 0
        exact_tasks = 0
        for task_id, rows in predictions.items():
            correctness = [
                row["attempt_1"] == target or row["attempt_2"] == target
                for row, target in zip(rows, targets[task_id], strict=True)
            ]
            exact_examples += sum(correctness)
            exact_tasks += all(correctness)
        return {"exact_tasks": exact_tasks, "exact_examples": exact_examples}

    base_score = score(baseline)
    current_score = score(current)
    gains = regressions = changed_second = 0
    for task_id, rows in current.items():
        for index, row in enumerate(rows):
            old = baseline[task_id][index]
            target = targets[task_id][index]
            before = old["attempt_1"] == target or old["attempt_2"] == target
            after = row["attempt_1"] == target or row["attempt_2"] == target
            gains += after and not before
            regressions += before and not after
            changed_second += row["attempt_2"] != old["attempt_2"]
    report = {
        "schema": "arc2-object-extraction-v19-matched-challenge-v1",
        "challenge_tasks": len(challenge),
        "challenge_examples": sum(len(task["test"]) for task in challenge.values()),
        "candidate_examples_distinct_from_attempt1": candidate_examples,
        "selected_duplicate_second_slots": selected_examples,
        "affected_tasks_executed_by_current_adapter": len(affected),
        "worker_errors": errors,
        "baseline_v19": base_score,
        "matched_current_adapter": current_score,
        "delta": {
            "newly_correct_examples": gains,
            "regressed_examples": regressions,
            "changed_attempt2_examples": changed_second,
            "newly_correct_tasks": current_score["exact_tasks"] - base_score["exact_tasks"],
        },
        "runtime_received_challenge_targets": False,
        "targets_read_only_after_all_affected_predictions": True,
        "per_task_predictions_or_targets_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "source_sha256": {
            "runner": sha(Path(__file__)),
            "adapter": sha(ROOT / "接続/ARC2/Kaggle提出.py"),
            "object_extraction_module": sha(ROOT / "接続/ARC2/物体抽出候補.py"),
            "hds_connector": sha(ROOT / "接続/ARC2/HDS接続.py"),
            "challenge": sha(CHALLENGE),
            "baseline_v19": sha(BASELINE),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
