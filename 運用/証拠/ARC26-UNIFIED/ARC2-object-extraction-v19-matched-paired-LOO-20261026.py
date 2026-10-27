"""Matched v19-adapter LOO for the train-fitted object extraction candidate."""
from __future__ import annotations

from collections import Counter
from contextlib import redirect_stdout
import concurrent.futures
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
OBJECT_RUNNER = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-object-extraction-v19-probe-20261026.py"
OUTPUT = Path(__file__).with_suffix(".json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_candidate_module():
    spec = importlib.util.spec_from_file_location("arc2_object_extraction_probe", OBJECT_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load object extraction probe")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_v19_adapter(index, task):
    os.environ["ARC2_PAYLOAD_ROOT"] = str(ROOT)
    sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2.Kaggle提出 import _worker, 結果を候補へ

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = _worker(task)
    if code != 0:
        return index, {"error": "worker_exit"}
    try:
        raw = json.loads(buffer.getvalue())
        rows, _holds = 結果を候補へ("paired-loo", task, raw)
        return index, {"rows": rows}
    except Exception as exc:
        return index, {"error": type(exc).__name__}


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    candidate_module = load_candidate_module()
    jobs = []
    total_eligible_folds = 0
    start = time.monotonic()
    for path in sorted(SOURCE_ROOT.glob("*.json")):
        task_data = json.loads(path.read_text(encoding="utf-8"))
        pairs = task_data.get("train", [])
        if len(pairs) < 3:
            continue
        for held_index, held in enumerate(pairs):
            total_eligible_folds += 1
            teachers = [pair for index, pair in enumerate(pairs) if index != held_index]
            models = candidate_module._fit(teachers)
            counts = Counter()
            grids = {}
            for model in models:
                proposed = candidate_module._predict(model, held["input"])
                if proposed is not None:
                    key = candidate_module._key(proposed)
                    counts[key] += 1
                    grids[key] = proposed
            if not counts:
                continue
            top_count = max(counts.values())
            winners = [key for key, count in counts.items() if count == top_count]
            if top_count < 2 or len(winners) != 1:
                continue
            candidate = grids[winners[0]]
            if candidate == held["input"]:
                continue
            runtime_task = {
                "train": teachers,
                "test": [{"input": held["input"]}],
            }
            # The held-out output remains separate and is never sent to the adapter.
            jobs.append((runtime_task, candidate, held["output"]))

    baseline_rows = [None] * len(jobs)
    worker_errors = 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(run_v19_adapter, index, task) for index, (task, _, _) in enumerate(jobs)]
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            job_index, result = future.result()
            baseline_rows[job_index] = result
            if index % 8 == 0 or index == len(futures):
                print(f"matched v19 baseline {index}/{len(futures)}", flush=True)
    if any(result is None for result in baseline_rows):
        raise RuntimeError("matched worker result count mismatch")

    baseline_exact = combined_exact = selected = gains = regressions = 0
    duplicate_slots = distinct_candidates = candidate_exact = 0
    for result, (_task, candidate, target) in zip(baseline_rows, jobs, strict=True):
        if "rows" not in result or len(result["rows"]) != 1:
            worker_errors += 1
            continue
        row = result["rows"][0]
        before = row["attempt_1"] == target or row["attempt_2"] == target
        baseline_exact += before
        duplicate = row["attempt_1"] == row["attempt_2"]
        duplicate_slots += duplicate
        distinct = candidate not in (row["attempt_1"], row["attempt_2"])
        distinct_candidates += distinct
        candidate_exact += candidate == target
        updated = dict(row)
        if duplicate and distinct:
            updated["attempt_2"] = candidate
            selected += 1
        after = updated["attempt_1"] == target or updated["attempt_2"] == target
        combined_exact += after
        gains += after and not before
        regressions += before and not after

    report = {
        "schema": "arc2-object-extraction-v19-matched-paired-loo-v1",
        "eligible_training_folds": total_eligible_folds,
        "candidate_support2_folds": len(jobs),
        "matched_v19_adapter_folds": len(jobs) - worker_errors,
        "worker_errors": worker_errors,
        "selection_policy": "support >= 2 unique top; replace attempt_2 only when it duplicates attempt_1",
        "baseline_exact_candidate_folds": baseline_exact,
        "combined_exact_candidate_folds": combined_exact,
        "newly_correct_folds": gains,
        "regressions": regressions,
        "selected_duplicate_slots": selected,
        "baseline_duplicate_slots": duplicate_slots,
        "candidate_distinct_from_both_attempts": distinct_candidates,
        "candidate_exact_folds": candidate_exact,
        "elapsed_seconds": round(time.monotonic() - start, 3),
        "heldout_outputs_passed_to_adapter_or_candidate": False,
        "heldout_outputs_read_after_all_predictions": True,
        "per_fold_predictions_or_targets_saved": False,
        "source_sha256": {
            "runner": sha(Path(__file__)),
            "object_extraction_probe": sha(OBJECT_RUNNER),
            "adapter": sha(ROOT / "接続/ARC2/Kaggle提出.py"),
            "hds_connector": sha(ROOT / "接続/ARC2/HDS接続.py"),
            "training_manifest": hashlib.sha256(
                json.dumps(
                    [
                        (p.name, len(json.loads(p.read_text(encoding="utf-8")).get("train", [])), sha(p))
                        for p in sorted(SOURCE_ROOT.glob("*.json"))
                    ],
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
