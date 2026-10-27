"""Paired public-training LOO probe for generic HDS condition backoff.

This is an evaluation-only monkey patch. It does not modify production HDS files.
It may use only the public ARC-AGI-2 training split and stores aggregate metrics,
never task identifiers, grids, or held-out examples.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
HDS_DIR = ROOT / "HDS/学習系統/v0.4.2"
TRAINING_DIR = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
SUPPORT_MINIMUM = 3

sys.path.insert(0, str(HDS_DIR))
sys.path.insert(1, str(ROOT))

from hds学習系統 import 適応 as 適応模块  # noqa: E402
from hds学習系統.型 import 予測記録  # noqa: E402
from 接続.ARC2.HDS接続 import 課題を解く  # noqa: E402


基準予測する = 適応模块.共通適応器.予測する
候補計数: dict[str, int] = {}


def 格子キー(格子: Any) -> tuple[tuple[int, ...], ...] | None:
    if not (
        isinstance(格子, list)
        and 1 <= len(格子) <= 30
        and all(
            isinstance(row, list)
            and 1 <= len(row) <= 30
            and len(row) == len(格子[0])
            and all(type(color) is int and 0 <= color <= 9 for color in row)
            for row in 格子
        )
    ):
        return None
    return tuple(tuple(row) for row in 格子)


def 部分条件合意(原理: Any, 写像: dict[tuple[str, ...], Any]):
    条件経路群 = tuple(原理.条件経路群)
    if not 条件経路群:
        return None

    可視添字 = tuple(i for i, path in enumerate(条件経路群) if path in 写像)
    可視値 = {i: 適応模块.値キー(写像[条件経路群[i]]) for i in 可視添字}
    if len(可視添字) < len(条件経路群):
        投影添字群 = (可視添字,)
    else:
        投影添字群 = tuple(
            tuple(i for i in range(len(条件経路群)) if i != dropped)
            for dropped in range(len(条件経路群))
        )

    条件記録別: dict[tuple[str, ...], Any] = {}
    for 条件値群, 出力値 in 原理.対応値表:
        条件キー = tuple(条件値群)
        if 条件キー in 条件記録別:
            if 適応模块.値キー(条件記録別[条件キー]) != 適応模块.値キー(出力値):
                return None
        else:
            条件記録別[条件キー] = 出力値
    記録値表 = tuple(条件記録別.items())
    候補値群: list[Any] = []
    for 投影添字 in 投影添字群:
        一致記録 = [
            (条件値群, 出力値)
            for 条件値群, 出力値 in 記録値表
            if len(条件値群) == len(条件経路群)
            and all(条件値群[i] == 可視値[i] for i in 投影添字)
        ]
        if len(一致記録) < SUPPORT_MINIMUM:
            continue
        出力キー群 = {適応模块.値キー(output) for _, output in 一致記録}
        if len(出力キー群) != 1:
            return None
        候補値群.append(一致記録[0][1])

    if not 候補値群:
        return None
    if len({適応模块.値キー(value) for value in 候補値群}) != 1:
        return None
    return 候補値群[0]


def 候補予測する(self, 原理群, 新経験):
    予測群, 競合群, 観測要求群 = 基準予測する(self, 原理群, 新経験)
    要求対象 = {
        原理ID
        for 要求 in 観測要求群
        for 原理ID in 要求.原理参照群
    }
    既存競合経路 = {競合.結果経路 for 競合 in 競合群}
    写像 = 適応模块.経験写像(新経験)
    部分予測群 = []
    救済原理ID群: set[str] = set()

    for 原理 in 原理群:
        if 原理.原理識別子 not in 要求対象:
            continue
        if 原理.結果経路 in 既存競合経路:
            continue
        候補値 = 部分条件合意(原理, 写像)
        if 候補値 is None:
            continue
        条件値群 = tuple(
            写像[path]
            for path in 原理.条件経路群
            if path in 写像
        )
        部分予測群.append(予測記録(
            原理参照=原理.原理識別子,
            結果経路=原理.結果経路,
            予測値=候補値,
            条件値群=条件値群,
        ))
        救済原理ID群.add(原理.原理識別子)
        候補計数["partial_predictions"] = 候補計数.get("partial_predictions", 0) + 1

    if not 部分予測群:
        return 予測群, 競合群, 観測要求群

    全予測群 = tuple(予測群) + tuple(部分予測群)
    経路別: dict[tuple[str, ...], list[Any]] = {}
    for 予測 in 全予測群:
        経路別.setdefault(予測.結果経路, []).append(予測)

    新規競合群 = []
    競合経路 = set(既存競合経路)
    for 経路, 同経路予測群 in 経路別.items():
        値別: dict[str, Any] = {}
        for 予測 in 同経路予測群:
            値別.setdefault(適応模块.値キー(予測.予測値), 予測.予測値)
        if len(値別) > 1:
            from hds学習系統.型 import 競合記録

            新規競合群.append(競合記録(
                結果経路=経路,
                候補値群=tuple(値別.values()),
                原理参照群=tuple(p.原理参照 for p in 同経路予測群),
            ))
            競合経路.add(経路)

    確定予測群 = tuple(p for p in 全予測群 if p.結果経路 not in 競合経路)
    残存要求群 = []
    for 要求 in 観測要求群:
        残存原理ID群 = tuple(
            原理ID for 原理ID in 要求.原理参照群
            if 原理ID not in 救済原理ID群
        )
        if 残存原理ID群:
            残存要求群.append(replace(要求, 原理参照群=残存原理ID群))

    候補計数["rescued_requests"] = (
        候補計数.get("rescued_requests", 0) + len(救済原理ID群)
    )
    return (
        確定予測群,
        tuple(競合群) + tuple(新規競合群),
        tuple(残存要求群),
    )


def 結果行(結果: Any) -> dict[str, Any]:
    rows = 結果.get("results", []) if isinstance(結果, dict) else []
    return rows[0] if rows and isinstance(rows[0], dict) else {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-folds", type=int, default=None)
    parser.add_argument("--skip-folds", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.max_folds is not None and args.max_folds < 1:
        raise SystemExit("--max-folds must be positive")
    if args.skip_folds < 0:
        raise SystemExit("--skip-folds must be nonnegative")

    files = sorted(TRAINING_DIR.glob("*.json"))
    manifest = hashlib.sha256()
    eligible_tasks = folds = 0
    previous_answer = previous_exact = previous_wrong = 0
    current_answer = current_exact = current_wrong = 0
    exact_gain = exact_regression = wrong_to_exact = exact_to_wrong = 0
    changed_answer = 0
    previous_seconds = current_seconds = 0.0
    partial_prediction_total = rescued_request_total = 0
    folds_skipped = 0
    started = time.perf_counter()
    stop = False

    for path in files:
        raw = path.read_bytes()
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        examples = json.loads(raw).get("train", [])
        if len(examples) < SUPPORT_MINIMUM + 1:
            continue
        eligible_tasks += 1
        for index, heldout in enumerate(examples):
            if folds_skipped < args.skip_folds:
                folds_skipped += 1
                continue
            if args.max_folds is not None and folds >= args.max_folds:
                stop = True
                break
            folds += 1
            teachers = [pair for i, pair in enumerate(examples) if i != index]
            task = {"train": teachers, "test": [{"input": heldout["input"]}]}

            適応模块.共通適応器.予測する = 基準予測する
            before = time.perf_counter()
            previous_row = 結果行(課題を解く(deepcopy(task), [], 候補収集=True))
            previous_seconds += time.perf_counter() - before
            previous_output = 格子キー(previous_row.get("answer"))
            previous_is_answer = previous_output is not None
            previous_is_exact = previous_is_answer and previous_row.get("answer") == heldout["output"]
            previous_answer += int(previous_is_answer)
            previous_exact += int(previous_is_exact)
            previous_wrong += int(previous_is_answer and not previous_is_exact)

            候補計数.clear()
            適応模块.共通適応器.予測する = 候補予測する
            before = time.perf_counter()
            current_row = 結果行(課題を解く(deepcopy(task), [], 候補収集=True))
            current_seconds += time.perf_counter() - before
            partial_prediction_total += 候補計数.get("partial_predictions", 0)
            rescued_request_total += 候補計数.get("rescued_requests", 0)
            current_output = 格子キー(current_row.get("answer"))
            current_is_answer = current_output is not None
            current_is_exact = current_is_answer and current_row.get("answer") == heldout["output"]
            current_answer += int(current_is_answer)
            current_exact += int(current_is_exact)
            current_wrong += int(current_is_answer and not current_is_exact)
            exact_gain += int(current_is_exact and not previous_is_exact)
            exact_regression += int(previous_is_exact and not current_is_exact)
            wrong_to_exact += int(previous_is_answer and not previous_is_exact and current_is_exact)
            exact_to_wrong += int(previous_is_exact and current_is_answer and not current_is_exact)
            changed_answer += int(
                previous_output is not None
                and current_output is not None
                and previous_output != current_output
            )

        if eligible_tasks % 25 == 0:
            print(json.dumps({
                "eligible_tasks_done": eligible_tasks,
                "paired_loo_folds_done": folds,
                "elapsed_seconds": round(time.perf_counter() - started, 1),
            }), flush=True)
        if stop:
            break

    適応模块.共通適応器.予測する = 基準予測する
    complete = args.max_folds is None or not stop
    result = {
        "schema": "arc26-p5-hds-partial-condition-consensus-paired-loo.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "hypothesis": "for a valid provisional principle only, back off one condition coordinate or use the visible condition subset when at least three stored condition mappings unanimously predict the same output; retain conflict/HOLD on disagreement",
        "data_source": "public ARC-AGI-2 training split only",
        "public_training_outputs_used_for_loo": True,
        "hidden_or_evaluation_solutions_read": False,
        "task_identifiers_or_grids_saved": False,
        "fallback_counted_correct": False,
        "minimum_matching_condition_mappings": SUPPORT_MINIMUM,
        "fold_limit": args.max_folds,
        "skip_initial_folds": args.skip_folds,
        "folds_skipped": folds_skipped,
        "complete": complete and args.skip_folds == 0,
        "stop_reason": (
            "all_training_folds"
            if complete and args.skip_folds == 0
            else "deterministic_offset_sample" if args.skip_folds > 0
            else "fold_limit"
        ),
        "eligible_tasks": eligible_tasks,
        "paired_loo_folds": folds,
        "training_manifest_sha256": manifest.hexdigest(),
        "previous": {
            "answer_rows": previous_answer,
            "exact": previous_exact,
            "wrong_answers": previous_wrong,
            "fallback_rows": folds - previous_answer,
            "runtime_seconds": round(previous_seconds, 6),
        },
        "current": {
            "answer_rows": current_answer,
            "exact": current_exact,
            "wrong_answers": current_wrong,
            "fallback_rows": folds - current_answer,
            "runtime_seconds": round(current_seconds, 6),
            "partial_predictions": partial_prediction_total,
            "rescued_principle_requests": rescued_request_total,
        },
        "delta": {
            "answer_rows": current_answer - previous_answer,
            "exact": current_exact - previous_exact,
            "wrong_answers": current_wrong - previous_wrong,
            "fallback_rows": previous_answer - current_answer,
            "runtime_seconds": round(current_seconds - previous_seconds, 6),
            "exact_gains": exact_gain,
            "exact_regressions": exact_regression,
            "previous_wrong_to_current_exact": wrong_to_exact,
            "previous_exact_to_current_wrong": exact_to_wrong,
            "changed_nonfallback_answers": changed_answer,
        },
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "hds_adapter_sha256": hashlib.sha256((ROOT / "接続/ARC2/HDS接続.py").read_bytes()).hexdigest(),
        "hds_adaptation_sha256": hashlib.sha256((HDS_DIR / "hds学習系統/適応.py").read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "output": str(args.output),
        "complete": complete,
        "paired_loo_folds": folds,
        "previous_exact": previous_exact,
        "current_exact": current_exact,
        "delta_exact": current_exact - previous_exact,
        "previous_wrong": previous_wrong,
        "current_wrong": current_wrong,
        "elapsed_seconds": result["elapsed_seconds"],
    }), flush=True)


if __name__ == "__main__":
    main()
