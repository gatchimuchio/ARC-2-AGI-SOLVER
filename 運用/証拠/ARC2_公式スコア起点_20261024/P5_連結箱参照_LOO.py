"""Public-training LOO probe for the generic connected-box family.

This diagnostic reads only data/training/*.json. It never loads evaluation
solutions, challenge inputs, task identifiers into the report, or prior memory.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE_SHA256 = {
    "接続/ARC2/連結箱参照候補.py": "d4ac36b3f8055cfd6e30c449d5b2c5389023a987ef992bb875f88d241dec01a1",
    "接続/ARC2/連結箱参照核.py": "5bfb14ba308720f9767173feee25ee7a07cf204083e6ee478fd157177953882d",
    "接続/ARC2/連結箱参照教材.py": "11a98bdc51a3cfa7f20293f965c64d57ba3a6a77ba626b33bbd74b89e4fc88b2",
    "接続/ARC2/凡例旋回教材.py": "f88ff14a2ddd52cf62b5d9ea3a7d05f4c5a6643c97789e947fb01023724f9983",
    "接続/ARC2/既存物体特徴.py": "e7a662182961e45cdba38a00bbd267ad03261cb1217dc8d08f2d867d9f4acc60",
    "接続/ARC2/既存成分最短経路.py": "9017291824a0bea5f07a15b7c911222d7c6bcbd6c4736f5b93506af9d32177e0",
    "接続/ARC2/境界点周期候補.py": "6a006151aab77898eb78575786f1a1348d8b0c2808375382845500c3503085b5",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


for relative, expected in SOURCE_SHA256.items():
    actual = sha256(ROOT / relative)
    if actual != expected:
        raise SystemExit(f"source hash mismatch: {relative}: {actual}")

sys.path.insert(0, str(ROOT))
from 接続.ARC2 import 連結箱参照候補 as api  # noqa: E402


train_dir = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
files = sorted(train_dir.glob("*.json"))
manifest = hashlib.sha256()
eligible_tasks = loo_folds = fit_folds = answer_count = exact_count = wrong_count = 0
failure_counts: dict[str, int] = {}
started = time.perf_counter()

for path in files:
    raw = path.read_bytes()
    manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
    task = json.loads(raw)
    examples = task.get("train", [])
    if len(examples) < 4:  # holdout leaves at least three teacher pairs
        continue
    eligible_tasks += 1
    for index, heldout in enumerate(examples):
        teachers = [pair for i, pair in enumerate(examples) if i != index]
        state, record = api.fit(teachers)
        loo_folds += 1
        if state is None:
            failure = record.get("failure", "unknown")
            failure_counts[failure] = failure_counts.get(failure, 0) + 1
            continue
        fit_folds += 1
        prediction, _ = api.predict(heldout["input"], state)
        if prediction is not None:
            answer_count += 1
            if prediction == heldout["output"]:
                exact_count += 1
            else:
                wrong_count += 1

result = {
    "schema": "arc2-p5-family-loo.v1",
    "family": "ARC connected-box lookup",
    "reference_source_commit": "2759d393a8d79824d36754785ce16f66d0493ebd",
    "source_files_sha256": SOURCE_SHA256,
    "public_training_files": len(files),
    "eligible_tasks_minimum_teacher_support_3": eligible_tasks,
    "loo_folds": loo_folds,
    "fit_folds": fit_folds,
    "answer_count": answer_count,
    "exact_count": exact_count,
    "wrong_count": wrong_count,
    "fit_failure_counts": failure_counts,
    "training_manifest_sha256": manifest.hexdigest(),
    "elapsed_seconds": round(time.perf_counter() - started, 3),
    "evaluation_solutions_read": False,
    "challenge_inputs_read": False,
    "task_identifiers_or_grids_saved": False,
    "decision": "REJECT_NO_LOO_FIT" if fit_folds == 0 else "REVIEW_REQUIRED",
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
