"""Matched paired LOO for the v21 object-outlier proposal folds.

The candidate generator and the current Kaggle adapter receive train examples
and the held-out input only. Held-out outputs are retained only for aggregate
scoring after all predictions have been generated.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "運用/証拠/ARC26-UNIFIED"
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
PROBE = EVIDENCE / "ARC2-object-outlier-v21-probe-20261026.py"
OUT = Path(__file__).with_suffix(".json")
ADAPTER = ROOT / "接続/ARC2/Kaggle提出.py"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _current_adapter(fold):
    teachers, held_input, _, candidate = fold
    task = {"train": teachers, "test": [{"input": held_input}]}
    from 接続.ARC2.Kaggle提出 import _run_one
    rows, holds, _ = _run_one("paired-loo", task, str(ADAPTER), ROOT)
    if len(rows) != 1:
        return {"error": "adapter_output_invalid"}
    reason_counts = {}
    for hold in holds:
        reason = hold.get("reason", "unknown")
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    return {
        "attempt_1": rows[0]["attempt_1"],
        "attempt_2": rows[0]["attempt_2"],
        "candidate": candidate,
        "hold": bool(holds),
        "hold_reasons": reason_counts,
    }


def main():
    if OUT.exists():
        raise SystemExit(f"refusing to overwrite {OUT}")
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))
    spec = importlib.util.spec_from_file_location("arc2_v21_probe", PROBE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load v21 probe")
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)

    folds = []
    eligible = 0
    for path in sorted(SOURCE_ROOT.glob("*.json")):
        task = json.loads(path.read_text(encoding="utf-8"))
        pairs = task.get("train", [])
        if len(pairs) < 3:
            continue
        for held_index, held in enumerate(pairs):
            eligible += 1
            teachers = [pair for index, pair in enumerate(pairs) if index != held_index]
            candidate, votes, _ = probe._candidate(
                probe._fit(teachers), held["input"]
            )
            if candidate is not None and votes >= 2 and candidate != held["input"]:
                folds.append((teachers, held["input"], held["output"], candidate))

    if len(folds) != 41:
        raise RuntimeError(f"proposal fold count drifted: {len(folds)}")
    with ThreadPoolExecutor(max_workers=3) as pool:
        predictions = list(pool.map(_current_adapter, folds))

    base_exact = candidate_applied = candidate_exact = regressions = 0
    newly_correct = newly_wrong = 0
    errors = sum("error" in prediction for prediction in predictions)
    if errors:
        raise RuntimeError(f"adapter errors: {errors}")
    hold_folds = sum(prediction["hold"] for prediction in predictions)
    hold_reasons = {}
    for prediction in predictions:
        for reason, count in prediction["hold_reasons"].items():
            hold_reasons[reason] = hold_reasons.get(reason, 0) + count
    for (_, _, target, _), prediction in zip(folds, predictions, strict=True):
        first, second = prediction["attempt_1"], prediction["attempt_2"]
        before = first == target or second == target
        base_exact += before
        after_second = second
        if first == second and prediction["candidate"] != first:
            after_second = prediction["candidate"]
            candidate_applied += 1
        after = first == target or after_second == target
        candidate_exact += after
        newly_correct += after and not before
        newly_wrong += before and not after
        regressions += before and not after

    report = {
        "schema": "arc2-object-outlier-v21-paired-loo-v1",
        "eligible_folds": eligible,
        "candidate_proposal_folds": len(folds),
        "adapter_evaluation_folds": len(predictions),
        "adapter_errors": errors,
        "adapter_hold_folds": hold_folds,
        "adapter_hold_reasons": dict(sorted(hold_reasons.items())),
        "current_adapter_exact_on_proposals": base_exact,
        "v21_candidate_applied_to_duplicate_slots": candidate_applied,
        "paired_v21_exact_on_proposals": candidate_exact,
        "newly_correct": newly_correct,
        "newly_wrong": newly_wrong,
        "net_delta": candidate_exact - base_exact,
        "regressions": regressions,
        "heldout_outputs_passed_to_candidate_generator_or_adapter": False,
        "per_fold_predictions_or_targets_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "proposal_runner": _sha(PROBE),
            "adapter": _sha(ADAPTER),
            "object_candidate": _sha(ROOT / "接続/ARC2/物体抽出候補.py"),
        },
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
