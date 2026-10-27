"""Paired v21.1 adapter evaluation for inter-object relation proposals."""
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
PROBE = EVIDENCE / "ARC2-object-palette-v24-probe-20261026.py"
ADAPTER = ROOT / "接続/ARC2/Kaggle提出.py"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _adapter_result(fold):
    teachers, held_input, _, candidate = fold
    from 接続.ARC2.Kaggle提出 import _run_one
    task = {"train": teachers, "test": [{"input": held_input}]}
    rows, holds, _ = _run_one(
        "relation-loo", task, str(ADAPTER), ROOT
    )
    if len(rows) != 1:
        return {"error": "adapter_output_invalid"}
    reasons = {}
    for hold in holds:
        reason = hold.get("reason", "unknown")
        reasons[reason] = reasons.get(reason, 0) + 1
    return {
        "attempt_1": rows[0]["attempt_1"],
        "attempt_2": rows[0]["attempt_2"],
        "candidate": candidate,
        "hold": bool(holds),
        "hold_reasons": reasons,
    }


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))
    spec = importlib.util.spec_from_file_location("arc2_v22_probe", PROBE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load v22 probe")
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
            teachers = [
                pair for index, pair in enumerate(pairs) if index != held_index
            ]
            candidate, votes, _ = probe._candidate(
                probe._fit(teachers), held["input"]
            )
            if candidate is not None and votes >= 2 and candidate != held["input"]:
                folds.append((teachers, held["input"], held["output"], candidate))
    if len(folds) != 40:
        raise RuntimeError(f"proposal fold count drifted: {len(folds)}")

    with ThreadPoolExecutor(max_workers=3) as pool:
        predictions = list(pool.map(_adapter_result, folds))
    errors = sum("error" in row for row in predictions)
    if errors:
        raise RuntimeError(f"adapter errors: {errors}")
    holds = sum(row["hold"] for row in predictions)
    hold_reasons = {}
    base_exact = paired_exact = applied = newly_correct = newly_wrong = 0
    for (_, _, target, _), row in zip(folds, predictions, strict=True):
        for reason, count in row["hold_reasons"].items():
            hold_reasons[reason] = hold_reasons.get(reason, 0) + count
        before = row["attempt_1"] == target or row["attempt_2"] == target
        second = row["attempt_2"]
        if row["attempt_1"] == second and row["candidate"] != row["attempt_1"]:
            second = row["candidate"]
            applied += 1
        after = row["attempt_1"] == target or second == target
        base_exact += before
        paired_exact += after
        newly_correct += after and not before
        newly_wrong += before and not after

    report = {
        "schema": "arc2-object-palette-v24-paired-loo-v1",
        "eligible_folds": eligible,
        "candidate_proposal_folds": len(folds),
        "adapter_evaluation_folds": len(predictions),
        "adapter_errors": errors,
        "adapter_hold_folds": holds,
        "adapter_hold_reasons": dict(sorted(hold_reasons.items())),
        "v21.1_adapter_exact_on_proposals": base_exact,
        "v24_palette_candidate_applied_to_duplicate_slots": applied,
        "paired_v24_exact_on_proposals": paired_exact,
        "newly_correct": newly_correct,
        "newly_wrong": newly_wrong,
        "net_delta": paired_exact - base_exact,
        "regressions": newly_wrong,
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
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
