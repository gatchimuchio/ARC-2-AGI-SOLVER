"""Offline scorecard for replacing an existing second slot with palette output."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "運用/証拠/ARC26-UNIFIED"
PROBE = EVIDENCE / "ARC2-object-palette-v24-probe-20261026.py"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v19-local-context-second-20261026/full-runtime/submission.json"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _score(rows_by_task, targets):
    examples = tasks = 0
    exact = {}
    for task_id, rows in rows_by_task.items():
        scores = [
            row["attempt_1"] == target or row["attempt_2"] == target
            for row, target in zip(rows, targets[task_id], strict=True)
        ]
        examples += sum(scores)
        tasks += all(scores)
        exact[task_id] = scores
    return {"exact_tasks": tasks, "exact_examples": examples}, exact


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("arc2_v24_probe", PROBE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load palette probe")
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    from 接続.ARC2.物体抽出候補 import ObjectExtractionCandidate

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline_v19 = json.loads(BASELINE.read_text(encoding="utf-8"))
    v21_rows = {}
    force_rows = {}
    candidate_examples = duplicate_applied = replacement_slots = 0
    candidate_exact = 0
    # Generate all v21 and v24 predictions before reading held-out outputs.
    for task_id, task in sorted(challenge.items()):
        object_model = ObjectExtractionCandidate(task["train"])
        palette_models = probe._fit(task["train"])
        v21 = [dict(row) for row in baseline_v19[task_id]]
        forced = [dict(row) for row in baseline_v19[task_id]]
        for index, pair in enumerate(task["test"]):
            first = v21[index]["attempt_1"]
            second = v21[index]["attempt_2"]
            old, _ = object_model.candidate(pair["input"])
            if old is not None and old != first and first == second:
                second = old
            existing, _ = object_model.outlier_candidate(pair["input"])
            if existing is not None and existing != first and first == second:
                second = existing
            v21[index]["attempt_2"] = second
            forced[index]["attempt_2"] = second
            candidate, votes, _ = probe._candidate(palette_models, pair["input"])
            if candidate is None or votes < 2 or candidate == first:
                continue
            candidate_examples += 1
            if candidate == second:
                candidate_exact += 1
                continue
            if second == first:
                duplicate_applied += 1
            else:
                replacement_slots += 1
            forced[index]["attempt_2"] = candidate
            # Candidate correctness is counted only after all predictions exist.
        v21_rows[task_id] = v21
        force_rows[task_id] = forced

    targets = {
        path.stem: [
            pair["output"]
            for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])
        ]
        for path in SOURCE_ROOT.glob("*.json")
    }
    baseline_score, baseline_exact = _score(v21_rows, targets)
    force_score, force_exact = _score(force_rows, targets)
    candidate_hits = 0
    gains = regressions = 0
    for task_id, forced in force_rows.items():
        for index, row in enumerate(forced):
            if row["attempt_2"] != v21_rows[task_id][index]["attempt_2"]:
                target = targets[task_id][index]
                candidate_hits += row["attempt_1"] != target and row["attempt_2"] == target
                before = baseline_exact[task_id][index]
                after = force_exact[task_id][index]
                gains += after and not before
                regressions += before and not after

    report = {
        "schema": "arc2-object-palette-v24-challenge-replacement-v1",
        "challenge_tasks": len(challenge),
        "challenge_examples": sum(len(task["test"]) for task in challenge.values()),
        "v21.1_baseline": baseline_score,
        "palette_candidate_examples_distinct_from_attempt1": candidate_examples,
        "palette_candidates_already_in_attempt2": candidate_exact,
        "duplicate_slots_applied": duplicate_applied,
        "distinct_attempt2_slots_replaced": replacement_slots,
        "v24_forced_replacement_score": force_score,
        "newly_correct_examples": gains,
        "regressed_examples": regressions,
        "candidate_correct_after_replacement": candidate_hits,
        "runtime_received_targets": False,
        "targets_read_after_all_predictions": True,
        "per_task_predictions_or_targets_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "probe": _sha(PROBE),
            "challenge": _sha(CHALLENGE),
            "baseline_v19": _sha(BASELINE),
            "object_module": _sha(ROOT / "接続/ARC2/物体抽出候補.py"),
        },
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
