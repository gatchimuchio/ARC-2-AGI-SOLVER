"""Public-training ablation of HDS core state before and after task examples.

The held-out output remains in the scorer process and is compared only after
both HDS queries. No task identifier or held-out output is passed to HDS.
This isolates the generic HDS core; it does not run ARC candidate modules or
load the separate template-prior bundle.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
HDS_ROOT = ROOT / "HDS/学習系統/v0.4.2"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(HDS_ROOT) not in sys.path:
    sys.path.insert(0, str(HDS_ROOT))

from 接続.ARC2 import HDS接続 as hds  # noqa: E402

TRAINING = ROOT / "入力/Kaggle/arc-agi_training_challenges.json"


def _state_digest(machine) -> str:
    state = machine.状態.現在状態
    payload = json.dumps(state, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _snapshot(machine) -> dict[str, int | str]:
    return {
        "version": machine.状態.現在版,
        "experience_count": machine.台帳.件数("観測台帳"),
        "update_count": machine.台帳.件数("更新台帳"),
        "active_principle_count": len(machine._有効原理群()),
        "quarantined_principle_count": len(machine._係争中原理群()),
        "state_sha256": _state_digest(machine),
    }


def run(max_folds: int, output: Path) -> dict:
    if not output.is_absolute():
        output = (ROOT / output).resolve()
    raw = TRAINING.read_bytes()
    tasks = json.loads(raw.decode("utf-8"))
    eligible = []
    for task_id in sorted(tasks):
        train = tasks[task_id].get("train", [])
        if len(train) < 4:
            continue
        for heldout_index, heldout in enumerate(train):
            support = train[:heldout_index] + train[heldout_index + 1 :]
            eligible.append((support, heldout))
            if len(eligible) >= max_folds:
                break
        if len(eligible) >= max_folds:
            break

    output.parent.mkdir(parents=True, exist_ok=True)
    summary_path = output.with_suffix(".summary.json")
    if output.exists() or summary_path.exists():
        raise FileExistsError(output)

    counts: Counter[str] = Counter()
    rows: list[dict] = []
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({
            "record_type": "header",
            "schema": "arc2-p3-hds-core-adaptation-loo-v1",
            "training_sha256": hashlib.sha256(raw).hexdigest(),
            "training_tasks": len(tasks),
            "requested_folds": len(eligible),
            "minimum_support": 3,
            "task_id_passed_to_hds": False,
            "heldout_output_passed_to_hds": False,
            "separate_template_prior_loaded": False,
            "candidate_modules_loaded": False,
        }, ensure_ascii=False) + "\n")
        stream.flush()

        for fold_index, (support, heldout) in enumerate(eligible, start=1):
            machine = hds.HDS学習実行系(最小支持数=3)
            before_state = _snapshot(machine)
            query = {"input": heldout["input"]}
            before = hds.出力格子(machine, hds.格子観測(query))

            learning_states: Counter[str] = Counter()
            accepted_principles = 0
            started = time.perf_counter()
            for pair in support:
                result = machine.実行(hds.格子観測(pair))
                state = result.学習過程.学習成立状態
                learning_states[str(getattr(state, "value", state))] += 1
                accepted_principles += len(result.学習過程.採用原理参照群)
            training_seconds = time.perf_counter() - started

            after_state = _snapshot(machine)
            after = hds.出力格子(machine, hds.格子観測(query))
            # The held-out output is used only here, after both input-only calls.
            before_answer = before.get("answer")
            after_answer = after.get("answer")
            before_exact = before_answer is not None and before_answer == heldout["output"]
            after_exact = after_answer is not None and after_answer == heldout["output"]
            row = {
                "record_type": "fold",
                "fold_index": fold_index,
                "support_examples": len(support),
                "before_exact": before_exact,
                "after_exact": after_exact,
                "adaptation_recovery": after_exact and not before_exact,
                "adaptation_regression": before_exact and not after_exact,
                "prediction_before_present": before_answer is not None,
                "prediction_after_present": after_answer is not None,
                "state_before": before_state,
                "state_after": after_state,
                "accepted_principles_during_training": accepted_principles,
                "learning_state_counts": dict(learning_states),
                "training_seconds": round(training_seconds, 4),
            }
            rows.append(row)
            for key in ("before_exact", "after_exact", "adaptation_recovery", "adaptation_regression"):
                counts[key] += int(row[key])
            counts["state_version_changed"] += int(after_state["version"] != before_state["version"])
            counts["state_digest_changed"] += int(after_state["state_sha256"] != before_state["state_sha256"])
            counts["active_principles_after"] += int(after_state["active_principle_count"])
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()

    summary = {
        "schema": "arc2-p3-hds-core-adaptation-loo-summary-v1",
        "records_path": output.relative_to(ROOT).as_posix(),
        "training_sha256": hashlib.sha256(raw).hexdigest(),
        "training_tasks": len(tasks),
        "eligible_folds": sum(len(t.get("train", [])) for t in tasks.values() if len(t.get("train", [])) >= 4),
        "processed_folds": len(rows),
        "minimum_support": 3,
        "before_exact": counts["before_exact"],
        "after_exact": counts["after_exact"],
        "adaptation_recoveries": counts["adaptation_recovery"],
        "adaptation_regressions": counts["adaptation_regression"],
        "state_version_changed_folds": counts["state_version_changed"],
        "state_digest_changed_folds": counts["state_digest_changed"],
        "active_principles_after_total": counts["active_principles_after"],
        "learning_state_counts": dict(sum((Counter(r["learning_state_counts"]) for r in rows), Counter())),
        "fallback_counted_correct": False,
        "hidden_or_evaluation_solutions_read": False,
        "heldout_output_passed_to_hds": False,
        "heldout_output_compared_after_queries": True,
        "separate_template_prior_loaded": False,
        "candidate_modules_loaded": False,
        "official_submission": False,
        "learning_effect": "MEASURED_FOR_HDS_CORE_ONLY",
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-folds", type=int, default=20)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or ROOT / "出力/検証" / f"ARC2-P3-HDS-core-adaptation-LOO-{stamp}.jsonl"
    summary = run(args.max_folds, output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
