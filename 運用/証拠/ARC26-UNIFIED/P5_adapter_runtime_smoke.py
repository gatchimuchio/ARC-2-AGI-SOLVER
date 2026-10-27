from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from 接続.ARC2.Kaggle提出 import 入力検査, 提出検査, _run_one  # noqa: E402

TRAINING_DIR = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
TASKS = 5


def main() -> None:
    challenge_group = {}
    heldout_outputs = []
    source_manifest = hashlib.sha256()
    for path in sorted(TRAINING_DIR.glob("*.json")):
        raw = path.read_bytes()
        examples = json.loads(raw).get("train", [])
        if len(examples) < 4:
            continue
        source_manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        heldout = examples[-1]
        challenge_group[f"smoke-{len(challenge_group):04d}"] = {
            "train": examples[:-1],
            "test": [{"input": heldout["input"]}],
        }
        heldout_outputs.append(heldout["output"])
        if len(challenge_group) == TASKS:
            break
    if len(challenge_group) != TASKS:
        raise RuntimeError(f"expected {TASKS} public training tasks")

    tasks = 入力検査(challenge_group)
    submission = {}
    fallback_count = worker_error_count = first_exact = second_exact = 0
    distinct_second_count = 0
    started = time.perf_counter()
    for index, (task_id, task) in enumerate(tasks.items()):
        candidates, fallback_rows = _run_one(
            task_id,
            task,
            str(ROOT / "接続/ARC2/Kaggle提出.py"),
            ROOT,
        )
        submission[task_id] = candidates
        fallback_count += len(fallback_rows)
        worker_error_count += sum(row["reason"] != "solver_hold" for row in fallback_rows)
        first_is_usable = not any(row["test_index"] == 0 for row in fallback_rows)
        if first_is_usable and candidates[0]["attempt_1"] == heldout_outputs[index]:
            first_exact += 1
        if candidates[0]["attempt_2"] != candidates[0]["attempt_1"]:
            distinct_second_count += 1
            if candidates[0]["attempt_2"] == heldout_outputs[index]:
                second_exact += 1
    elapsed = time.perf_counter() - started
    提出検査(tasks, submission)

    result = {
        "schema": "arc2-p5-adapter-runtime-smoke.v1",
        "instruction_id": "ARC2-SCORE-GATE-20261024",
        "data_source": "public ARC-AGI-2 training split LOO; held-out output used only after worker return",
        "tasks": len(tasks),
        "submission_shape_valid": True,
        "fallback_rows": fallback_count,
        "worker_error_rows": worker_error_count,
        "first_exact_nonfallback": first_exact,
        "distinct_attempt2_rows": distinct_second_count,
        "attempt2_exact": second_exact,
        "elapsed_seconds": round(elapsed, 3),
        "evaluation_solutions_read": False,
        "task_identifiers_or_grids_saved": False,
        "public_training_sample_manifest_sha256": source_manifest.hexdigest(),
        "adapter_source_sha256": hashlib.sha256((ROOT / "接続/ARC2/Kaggle提出.py").read_bytes()).hexdigest(),
    }
    output = Path(__file__).with_suffix(".json")
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
