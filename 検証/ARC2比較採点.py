"""同一公開入力の完成済み2実行を正解と事後照合し、改善と退行を分ける。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from 検証.ARC2予測結果採点 import 採点


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def 比較(*, previous, previous_audit, current, current_audit, challenges, solutions):
    before = 採点(previous, previous_audit, solutions, challenges)
    after = 採点(current, current_audit, solutions, challenges)
    if before["challenges_sha256"] != after["challenges_sha256"] or before["answers_sha256"] != after["answers_sha256"]:
        raise ValueError("比較の入力または事後採点対象が一致しません")
    p, q = _read(previous), _read(current)
    pa, qa = _read(previous_audit), _read(current_audit)
    truth = _read(solutions)
    pf = {(x["task_id"], x["test_index"]) for x in pa["fallbacks"]}
    qf = {(x["task_id"], x["test_index"]) for x in qa["fallbacks"]}
    changed_first = changed_second = improved = regressed = 0
    for task, rows in p.items():
        for i, row in enumerate(rows):
            new, expected = q[task][i], truth[task][i]
            def correct(value, fallback):
                first, second = value["attempt_1"], value["attempt_2"]
                return (not fallback and first == expected) or (second != first and second == expected)
            old_hit = correct(row, (task, i) in pf)
            new_hit = correct(new, (task, i) in qf)
            improved += not old_hit and new_hit
            regressed += old_hit and not new_hit
            changed_first += row["attempt_1"] != new["attempt_1"]
            changed_second += row["attempt_2"] != new["attempt_2"]
    delta = after["nonfallback_pass2"] - before["nonfallback_pass2"]
    if improved - regressed != delta:
        raise ValueError("例別集計と全体の正答差が一致しません")
    return {"previous": before, "current": after, "pass2_delta": delta,
            "improved_grids": improved, "regressed_grids": regressed,
            "changed_first_attempts": changed_first, "changed_second_attempts": changed_second,
            "previous_seconds": pa.get("seconds"), "current_seconds": qa.get("seconds"),
            "scope": "Posthoc scoring only. The caller must separately establish matching runtime conditions and provenance."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("previous", "previous-audit", "current", "current-audit", "challenges", "solutions"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(比較(previous=args.previous, previous_audit=args.previous_audit,
                        current=args.current, current_audit=args.current_audit,
                        challenges=args.challenges, solutions=args.solutions),
                     ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
