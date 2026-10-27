"""Kaggle Code Competition向けの入力・出力アダプタ。推論本体は既存HDS接続を呼ぶ。"""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any


大会 = "arc-prize-2026-arc-agi-2"
課題時間上限秒 = 300
並列数 = 3
提出名 = "submission.json"
監査名 = "submission_audit.json"


def 格子か(値: object) -> bool:
    return (
        isinstance(値, list)
        and 1 <= len(値) <= 30
        and all(
            isinstance(行, list)
            and 1 <= len(行) <= 30
            and len(行) == len(値[0])
            and all(type(色) is int and 0 <= 色 <= 9 for 色 in 行)
            for 行 in 値
        )
    )


def _保留理由ラベル群(値: object) -> list[str]:
    """安全な文字列のHDS保留理由だけを重複なく保持する。"""
    if not isinstance(値, list):
        return []
    理由群: set[str] = set()
    for 理由 in 値:
        if not isinstance(理由, str):
            continue
        ラベル = " ".join(理由.split())
        if (
            not ラベル
            or len(ラベル) > 160
            or re.search(r"\b[0-9a-f]{8,}\b", ラベル, re.IGNORECASE)
        ):
            continue
        理由群.add(ラベル)
    return sorted(理由群)


def _保留理由数(保留群: list[dict[str, Any]]) -> dict[str, int]:
    """各fallback例に現れたHDS理由を汎用ラベルごとに数える。"""
    数 = Counter(
        理由
        for 保留 in 保留群
        for 理由 in _保留理由ラベル群(保留.get("solver_hold_reasons"))
    )
    return dict(sorted(数.items()))


def _一意な別候補を選ぶ(
    予測群: object, 第一候補: list[list[int]]
) -> list[list[int]] | None:
    """HDS採用予測から一意な最多票の別格子だけを選ぶ。"""
    if not isinstance(予測群, list):
        return None
    票: Counter[tuple[tuple[int, ...], ...]] = Counter()
    for 予測 in 予測群:
        if not isinstance(予測, dict):
            continue
        格子 = 予測.get("answer")
        if not 格子か(格子) or 格子 == 第一候補:
            continue
        鍵 = tuple(tuple(行) for 行 in 格子)
        票[鍵] += 1
    if not 票:
        return None
    最大票 = max(票.values())
    勝者 = [格子 for 格子, 数 in 票.items() if 数 == 最大票]
    if len(勝者) != 1:
        return None
    return [list(行) for 行 in 勝者[0]]


def _完全候補対(候補対: object) -> tuple[list[list[int]], list[list[int]]] | None:
    """Return a distinct, complete pair of valid grids for the two answer slots."""
    if (not isinstance(候補対, list) or len(候補対) != 2
            or not all(格子か(格子) for 格子 in 候補対)
            or 候補対[0] == 候補対[1]):
        return None
    return deepcopy(候補対[0]), deepcopy(候補対[1])


def 入力検査(原本: object) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Kaggle challenge JSONから公開trainとinput-only testだけを取り出す。"""
    if not isinstance(原本, dict) or not 原本:
        raise ValueError("challenge JSONは空でないtask objectを必要とする")
    整形済み: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for 課題ID, 課題 in 原本.items():
        if not isinstance(課題ID, str) or not 課題ID:
            raise ValueError("課題IDは空でない文字列が必要")
        if not isinstance(課題, dict) or set(課題) != {"train", "test"}:
            raise ValueError(f"{課題ID}: challengeはtrain/testだけを必要とする")
        教師, 試験 = 課題["train"], 課題["test"]
        if not isinstance(教師, list) or not 教師:
            raise ValueError(f"{課題ID}: train例がないか不正")
        if not isinstance(試験, list) or not 試験:
            raise ValueError(f"{課題ID}: test例がないか不正")
        整形教師 = []
        for 位置, 対 in enumerate(教師):
            if not isinstance(対, dict) or not {"input", "output"} <= set(対):
                raise ValueError(f"{課題ID}: train例{位置}にinput/outputが必要")
            if not 格子か(対["input"]) or not 格子か(対["output"]):
                raise ValueError(f"{課題ID}: train例{位置}のgridが不正")
            整形教師.append({"input": deepcopy(対["input"]), "output": deepcopy(対["output"])})
        整形試験 = []
        for 位置, 対 in enumerate(試験):
            if not isinstance(対, dict) or set(対) != {"input"}:
                raise ValueError(f"{課題ID}: test例{位置}はinputだけを必要とする")
            if not 格子か(対["input"]):
                raise ValueError(f"{課題ID}: test例{位置}のgridが不正")
            整形試験.append({"input": deepcopy(対["input"])})
        整形済み[課題ID] = {"train": 整形教師, "test": 整形試験}
    return 整形済み


def 結果を候補へ(
    課題ID: str,
    課題: dict[str, list[dict[str, Any]]],
    結果: object,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """第1候補と一意なHDS別候補を写し、HOLD等は入力格子で補完する。"""
    行群 = 結果.get("results") if isinstance(結果, dict) else None
    障害 = 結果.get("error") if isinstance(結果, dict) else "invalid_worker_result"
    if not isinstance(行群, list) or len(行群) != len(課題["test"]):
        行群 = []
        障害 = 障害 or "result_count_mismatch"
    出力, 保留記録 = [], []
    for 位置, 対 in enumerate(課題["test"]):
        行 = 行群[位置] if 位置 < len(行群) and isinstance(行群[位置], dict) else {}
        予測 = 行.get("answer")
        if 格子か(予測):
            候補 = deepcopy(予測)
        else:
            候補 = deepcopy(対["input"])
            理由 = "solver_hold" if 予測 is None else "invalid_prediction"
            if 障害:
                理由 = str(障害)
            保留記録.append(
                {
                    "task_id": 課題ID,
                    "test_index": 位置,
                    "reason": 理由,
                    "solver_status": 行.get("status"),
                    "solver_hold_reasons": _保留理由ラベル群(
                        行.get("reasons")
                    ),
                }
            )
        第二候補 = 行.get("second_answer")
        if not 格子か(第二候補) or 第二候補 == 候補:
            第二候補 = 候補
        出力.append(
            {"attempt_1": deepcopy(候補), "attempt_2": deepcopy(第二候補)}
        )
    return 出力, 保留記録


def 提出検査(
    課題群: dict[str, dict[str, list[dict[str, Any]]]],
    提出: object,
) -> None:
    if not isinstance(提出, dict) or set(提出) != set(課題群):
        raise ValueError("submission task集合に欠落または余分なtaskがある")
    for 課題ID, 課題 in 課題群.items():
        候補群 = 提出[課題ID]
        if not isinstance(候補群, list) or len(候補群) != len(課題["test"]):
            raise ValueError(f"{課題ID}: submissionのtest数が一致しない")
        for 位置, 候補 in enumerate(候補群):
            if not isinstance(候補, dict) or set(候補) != {"attempt_1", "attempt_2"}:
                raise ValueError(f"{課題ID}: test例{位置}に2候補が必要")
            if not all(格子か(候補[名]) for 名 in ("attempt_1", "attempt_2")):
                raise ValueError(f"{課題ID}: test例{位置}の候補gridが不正")


def _worker(課題: dict[str, list[dict[str, Any]]]) -> int:
    try:
        ルート = Path(os.environ["ARC2_PAYLOAD_ROOT"]).resolve()
        sys.path.insert(0, str(ルート / "HDS/学習系統/v0.4.2"))
        sys.path.insert(0, str(ルート))
        from 接続.ARC2.HDS接続 import 課題を解く, 事前教材を読む, 汎用事前記憶を読む
        from 接続.ARC2.単純変換候補 import unique_candidate
        from 接続.ARC2.複合幾何変換候補 import CompositeGeometryCandidate
        from 接続.ARC2.局所近傍変換候補 import LocalCellContextCandidate
        from 接続.ARC2.物体抽出候補 import ObjectExtractionCandidate
        from 接続.ARC2.埋込見本一致候補 import fit_candidate, predict_candidate

        事前教材 = 事前教材を読む()
        汎用記憶 = 汎用事前記憶を読む()
        観測診断 = os.environ.get("ARC2_AGGREGATE_DIAGNOSTICS") == "1"
        if 観測診断:
            結果 = 課題を解く(課題, 事前教材, 候補収集=True, 観測診断=True, 汎用事前教材=汎用記憶)
        else:
            結果 = 課題を解く(課題, 事前教材, 候補収集=True, 汎用事前教材=汎用記憶)
        # This partial-fit family is allowed to propose only attempt 2. It never
        # replaces the HDS answer and requires high teacher support plus a single
        # residual confined to one header card at most.
        見本モデル, 見本適合記録 = fit_candidate(課題["train"])
        # Runtime candidates combine current HDS families, generic transforms,
        # teacher-fitted repeated-panel/composite-geometry programs, and a
        # local cell-context rule. The recovered v4 solver is excluded because
        # it contains task identifiers.
        複合幾何候補器 = CompositeGeometryCandidate(課題["train"])
        局所近傍候補器 = LocalCellContextCandidate(課題["train"])
        物体抽出候補器 = ObjectExtractionCandidate(課題["train"])
        公開行群 = []
        候補機構数: Counter[str] = Counter()
        非同一候補機構数: Counter[str] = Counter()
        候補予測数 = 非同一候補予測数 = 候補あり例数 = 非同一候補あり例数 = 0
        単純変換候補数 = 単純変換非同一数 = 0
        物体抽出候補例数 = 物体抽出選択例数 = 0
        物体外れ値候補例数 = 物体外れ値選択例数 = 0
        物体パレット候補例数 = 物体パレット選択例数 = 0
        for 位置, 元行 in enumerate(結果.get("results", [])):
            行 = 元行 if isinstance(元行, dict) else {}
            候補対 = _完全候補対(行.get("candidate_attempts"))
            第一候補 = 候補対[0] if 候補対 else 行.get("answer")
            if not 格子か(第一候補):
                第一候補 = 課題["test"][位置]["input"] if 位置 < len(課題["test"]) else []
            局所近傍候補 = None
            if 位置 < len(課題["test"]):
                局所近傍候補, _ = 局所近傍候補器.候補(
                    課題["test"][位置]["input"], {}
                )
                if 見本モデル is not None:
                    見本候補, _ = predict_candidate(
                        課題["test"][位置]["input"], 見本モデル
                    )
                    if 格子か(見本候補) and 見本候補 != 第一候補:
                        候補群 = 行.get("candidate_predictions")
                        if not isinstance(候補群, list):
                            候補群 = []
                            行["candidate_predictions"] = 候補群
                        候補群.append({
                            "family": "ARC反復見本パネル照合候補",
                            "answer": 見本候補,
                        })
                単純候補 = unique_candidate(
                    課題["train"], 課題["test"][位置]["input"]
                )
                if 単純候補 is not None:
                    単純変換候補数 += 1
                    if 単純候補 != 第一候補:
                        単純変換非同一数 += 1
                        行["simple_transform_candidate"] = 単純候補
                複合幾何候補, _ = 複合幾何候補器.候補(
                    課題["test"][位置]["input"], {}
                )
                if 格子か(複合幾何候補) and 複合幾何候補 != 第一候補:
                    候補群 = 行.get("candidate_predictions")
                    if not isinstance(候補群, list):
                        候補群 = []
                        行["candidate_predictions"] = 候補群
                    候補群.append({
                        "family": "ARC背景crop複合幾何変換",
                        "answer": 複合幾何候補,
                    })
            第二候補 = (候補対[1] if 候補対 else _一意な別候補を選ぶ(
                行.get("candidate_predictions"), 第一候補
            ))
            if not 格子か(第二候補) or 第二候補 == 第一候補:
                単純候補 = 行.get("simple_transform_candidate")
                第二候補 = (
                    単純候補
                    if 格子か(単純候補) and 単純候補 != 第一候補
                    else None
                )
            if (
                (not 格子か(第二候補) or 第二候補 == 第一候補)
                and 格子か(局所近傍候補)
                and 局所近傍候補 != 第一候補
            ):
                第二候補 = 局所近傍候補
            if 位置 < len(課題["test"]):
                物体枠未充足 = not 格子か(第二候補) or 第二候補 == 第一候補
                物体候補群 = []
                物体抽出候補, 物体抽出記録 = 物体抽出候補器.candidate(
                    課題["test"][位置]["input"]
                )
                if 格子か(物体抽出候補) and 物体抽出候補 != 第一候補:
                    物体抽出候補例数 += 1
                    if 物体枠未充足:
                        物体候補群.append(("object", 物体抽出候補, 物体抽出記録))
                    if 観測診断:
                        候補群 = 行.get("candidate_predictions")
                        if not isinstance(候補群, list):
                            候補群 = []
                            行["candidate_predictions"] = 候補群
                        候補群.append({
                            "family": "ARC物体抽出・切出し",
                            "answer": 物体抽出候補,
                        })
                if 物体枠未充足:
                    物体外れ値候補, 物体外れ値記録 = 物体抽出候補器.outlier_candidate(
                        課題["test"][位置]["input"]
                    )
                    if (
                        格子か(物体外れ値候補)
                        and 物体外れ値候補 != 第一候補
                    ):
                        物体外れ値候補例数 += 1
                        物体候補群.append(("outlier", 物体外れ値候補, 物体外れ値記録))
                        if 観測診断:
                            候補群 = 行.get("candidate_predictions")
                            if not isinstance(候補群, list):
                                候補群 = []
                                行["candidate_predictions"] = 候補群
                            候補群.append({
                                "family": "ARC物体外れ値選択・切出し",
                                "answer": 物体外れ値候補,
                            })
                    物体パレット候補, 物体パレット記録 = 物体抽出候補器.palette_candidate(
                        課題["test"][位置]["input"]
                    )
                    if 格子か(物体パレット候補) and 物体パレット候補 != 第一候補:
                        物体パレット候補例数 += 1
                        物体候補群.append(("palette", 物体パレット候補, 物体パレット記録))
                        if 観測診断:
                            候補群 = 行.get("candidate_predictions")
                            if not isinstance(候補群, list):
                                候補群 = []
                                行["candidate_predictions"] = 候補群
                            候補群.append({
                                "family": "ARC物体パレット選択・切出し",
                                "answer": 物体パレット候補,
                            })
                if 物体枠未充足 and 物体候補群:
                    選択種別, 第二候補, _ = max(
                        enumerate(物体候補群),
                        key=lambda item: (
                            int(item[1][2].get("top_votes", 0))
                            / max(1, int(item[1][2].get("applicable_models", 0))),
                            int(item[1][2].get("top_votes", 0)),
                            -item[0],
                        ),
                    )[1]
                    if 選択種別 == "object":
                        物体抽出選択例数 += 1
                    elif 選択種別 == "outlier":
                        物体外れ値選択例数 += 1
                    elif 選択種別 == "palette":
                        物体パレット選択例数 += 1
            if (
                (not 格子か(第二候補) or 第二候補 == 第一候補)
                and 位置 < len(課題["test"])
            ):
                _teacher_pair_candidate, _teacher_pair_record = 物体抽出候補器.teacher_pair_consensus_candidate(
                    課題["test"][位置]["input"]
                )
                if (
                    格子か(_teacher_pair_candidate)
                    and _teacher_pair_candidate != 第一候補
                ):
                    第二候補 = _teacher_pair_candidate
                    if 観測診断:
                        候補群 = 行.get("candidate_predictions")
                        if not isinstance(候補群, list):
                            候補群 = []
                            行["candidate_predictions"] = 候補群
                        候補群.append({
                            "family": "ARC物体teacher-pair consensus",
                            "answer": _teacher_pair_candidate,
                        })
            if 格子か(局所近傍候補) and 局所近傍候補 != 第一候補:
                候補群 = 行.get("candidate_predictions")
                if not isinstance(候補群, list):
                    候補群 = []
                    行["candidate_predictions"] = 候補群
                候補群.append({
                    "family": "ARC局所近傍セル変換",
                    "answer": 局所近傍候補,
                })
            公開行群.append(
                {
                    "answer": 第一候補 if 候補対 else 元行.get("answer"),
                    "status": 行.get("status"),
                    "reasons": _保留理由ラベル群(行.get("reasons")),
                    "second_answer": 第二候補 if 位置 < len(課題["test"]) else None,
                }
            )
            if 観測診断 and 位置 < len(課題["test"]):
                行候補群 = 行.get("candidate_predictions")
                行候補群 = 行候補群 if isinstance(行候補群, list) else []
                候補あり例数 += bool(行候補群)
                非同一例あり = False
                for 候補記録 in 行候補群:
                    if not isinstance(候補記録, dict):
                        continue
                    機構名 = 候補記録.get("family")
                    候補格子 = 候補記録.get("answer")
                    if not isinstance(機構名, str) or not 格子か(候補格子):
                        continue
                    候補予測数 += 1
                    候補機構数[機構名] += 1
                    if 候補格子 != 課題["test"][位置]["input"]:
                        非同一候補予測数 += 1
                        非同一候補機構数[機構名] += 1
                        非同一例あり = True
                非同一候補あり例数 += 非同一例あり
        公開結果 = {"results": 公開行群}
        if 観測診断:
            公開結果["aggregate_diagnostics"] = {
                "observation_request_counts": 結果.get(
                    "observation_request_counts", {}
                ),
                "candidate_prediction_count": 候補予測数,
                "examples_with_candidates": 候補あり例数,
                "nonidentity_candidate_prediction_count": 非同一候補予測数,
                "examples_with_nonidentity_candidates": 非同一候補あり例数,
                "candidate_family_counts": dict(sorted(候補機構数.items())),
                "nonidentity_candidate_family_counts": dict(
                    sorted(非同一候補機構数.items())
                ),
                "simple_transform_unique_candidates": 単純変換候補数,
                "simple_transform_distinct_from_first": 単純変換非同一数,
                "object_extraction_candidates": 物体抽出候補例数,
                "object_extraction_selected": 物体抽出選択例数,
                "object_outlier_candidates": 物体外れ値候補例数,
                "object_outlier_selected": 物体外れ値選択例数,
                "object_palette_candidates": 物体パレット候補例数,
                "object_palette_selected": 物体パレット選択例数,
                "repeated_panel_candidate_fit": 見本適合記録,
            }
        print(json.dumps(公開結果, ensure_ascii=False))
        return 0
    except Exception as error:  # Kaggle parentが課題単位のfallbackを記録する。
        print(json.dumps({"error": type(error).__name__}, ensure_ascii=False))
        return 1


def _preflight() -> int:
    try:
        ルート = Path(os.environ["ARC2_PAYLOAD_ROOT"]).resolve()
        sys.path.insert(0, str(ルート / "HDS/学習系統/v0.4.2"))
        sys.path.insert(0, str(ルート))
        from 接続.ARC2.HDS接続 import 事前教材を読む, 汎用事前記憶を読む

        教材 = 事前教材を読む()
        汎用事前記憶を読む()
        print(json.dumps({
            "status": "ok",
            "template_examples": len(教材),
        }, ensure_ascii=False))
        return 0
    except Exception as error:
        print(
            json.dumps(
                {"error": type(error).__name__, "message": str(error)[:240]},
                ensure_ascii=False,
            )
        )
        return 1


def _run_one(
    課題ID: str,
    課題: dict[str, list[dict[str, Any]]],
    launcher: str,
    payload_root: Path,
    *,
    aggregate_diagnostics: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    環境 = os.environ.copy()
    環境["ARC2_PAYLOAD_ROOT"] = str(payload_root)
    if aggregate_diagnostics:
        環境["ARC2_AGGREGATE_DIAGNOSTICS"] = "1"
    else:
        環境.pop("ARC2_AGGREGATE_DIAGNOSTICS", None)
    try:
        実行 = subprocess.run(
            [sys.executable, launcher, "--worker"],
            input=json.dumps(課題, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=課題時間上限秒,
            env=環境,
            check=False,
        )
    except subprocess.TimeoutExpired:
        実行結果: object = {"error": "task_wall_timeout"}
    else:
        if 実行.returncode:
            try:
                実行結果 = json.loads(実行.stdout)
            except (json.JSONDecodeError, TypeError):
                実行結果 = {"error": "worker_exit"}
        else:
            try:
                実行結果 = json.loads(実行.stdout)
            except (json.JSONDecodeError, TypeError):
                実行結果 = {"error": "worker_invalid_json"}
    診断 = (
        実行結果.get("aggregate_diagnostics", {})
        if aggregate_diagnostics and isinstance(実行結果, dict)
        else {}
    )
    return (*結果を候補へ(課題ID, 課題, 実行結果), 診断)


def _atomic_new(path: Path, value: dict[str, Any]) -> bytes:
    content = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with path.open("xb") as target:
        target.write(content)
    return content


def _discover_challenges(input_root: Path = Path("/kaggle/input")) -> Path:
    """公式sample_submissionと対応するtest challengeを一意に選ぶ。"""
    候補 = list(input_root.rglob("arc-agi_test_challenges.json"))
    if len(候補) != 1:
        raise RuntimeError(f"大会test challengeを一意に特定できない: 候補数={len(候補)}")
    return 候補[0]


def run_cli(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--aggregate-diagnostics", action="store_true")
    parser.add_argument("--challenges", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("/kaggle/working"))
    arguments = parser.parse_args(argv)
    if arguments.worker:
        try:
            task = json.load(sys.stdin)
            return _worker(task)
        except Exception as error:
            print(json.dumps({"error": type(error).__name__}, ensure_ascii=False))
            return 1
    if arguments.preflight:
        return _preflight()

    入口 = Path(os.environ.get("ARC2_WORKER_LAUNCHER", sys.argv[0])).resolve()
    payload_root = Path(os.environ.get("ARC2_PAYLOAD_ROOT", Path(__file__).resolve().parents[2]))
    入力path = arguments.challenges or _discover_challenges()
    raw = 入力path.read_bytes()
    課題群 = 入力検査(json.loads(raw.decode("utf-8")))
    総test = sum(len(課題["test"]) for 課題 in 課題群.values())
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    submission_path = arguments.output_dir / 提出名
    audit_path = arguments.output_dir / 監査名
    if submission_path.exists() or audit_path.exists():
        raise FileExistsError("既存のsubmissionまたはauditを上書きしない")

    # 先にimportと教材の読込みを独立workerで確認し、全課題が同じ依存障害で
    # fallbackになる提出物を作らない。
    preflight = subprocess.run(
        [sys.executable, str(入口), "--preflight"],
        text=True,
        capture_output=True,
        timeout=120,
        env={**os.environ, "ARC2_PAYLOAD_ROOT": str(payload_root)},
        check=False,
    )
    if preflight.returncode:
        raise RuntimeError(f"HDS runtime preflight failed: {preflight.stdout[-400:]}")

    started = time.monotonic()
    item_iter = iter(課題群.items())
    with ThreadPoolExecutor(max_workers=並列数) as executor:
        記録群 = list(
            executor.map(
                lambda item: _run_one(
                    item[0],
                    item[1],
                    str(入口),
                    payload_root,
                    aggregate_diagnostics=arguments.aggregate_diagnostics,
                ),
                item_iter,
            )
        )
    提出: dict[str, list[dict[str, Any]]] = {}
    保留群: list[dict[str, Any]] = []
    診断数: Counter[str] = Counter()
    機構数: Counter[str] = Counter()
    非同一機構数: Counter[str] = Counter()
    追加観測数: Counter[str] = Counter()
    for (課題ID, _), (候補群, 保留記録, 診断) in zip(課題群.items(), 記録群, strict=True):
        提出[課題ID] = 候補群
        保留群.extend(保留記録)
        if not arguments.aggregate_diagnostics or not isinstance(診断, dict):
            continue
        for キー in (
            "candidate_prediction_count",
            "examples_with_candidates",
            "nonidentity_candidate_prediction_count",
            "examples_with_nonidentity_candidates",
            "simple_transform_unique_candidates",
            "simple_transform_distinct_from_first",
        ):
            値 = 診断.get(キー)
            if type(値) is int and 値 >= 0:
                診断数[キー] += 値
        for キー, 値群 in (
            ("candidate_family_counts", 機構数),
            ("nonidentity_candidate_family_counts", 非同一機構数),
            ("observation_request_counts", 追加観測数),
        ):
            元 = 診断.get(キー)
            if not isinstance(元, dict):
                continue
            for 名, 値 in 元.items():
                if isinstance(名, str) and len(名) <= 160 and type(値) is int and 値 >= 0:
                    値群[名] += 値
    提出検査(課題群, 提出)

    submission_bytes = _atomic_new(submission_path, 提出)
    audit = {
        "format": "arc2-kaggle-submission-audit-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": os.environ.get("ARC2_SOURCE_COMMIT", "unknown"),
        "challenge_sha256": hashlib.sha256(raw).hexdigest(),
        "challenge_file": 入力path.name,
        "tasks": len(課題群),
        "test_examples": 総test,
        "attempts_per_test": 2,
        "fallback_count": len(保留群),
        "solver_hold_reason_counts": _保留理由数(保留群),
        "fallbacks": 保留群,
        "seconds": round(time.monotonic() - started, 3),
        "submission_sha256": hashlib.sha256(submission_bytes).hexdigest(),
    }
    if arguments.aggregate_diagnostics:
        audit["aggregate_diagnostics"] = {
            **dict(診断数),
            "candidate_family_counts": dict(sorted(機構数.items())),
            "nonidentity_candidate_family_counts": dict(sorted(非同一機構数.items())),
            "observation_request_counts": dict(sorted(追加観測数.items())),
        }
    _atomic_new(audit_path, audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
