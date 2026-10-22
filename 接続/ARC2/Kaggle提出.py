"""Kaggle Code Competition向けの入力・出力アダプタ。推論本体は既存HDS接続を呼ぶ。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
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
    """HDSの確定出力を2候補へ写し、HOLD等は入力由来格子で補完する。"""
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
                }
            )
        出力.append({"attempt_1": deepcopy(候補), "attempt_2": deepcopy(候補)})
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
        from 接続.ARC2.HDS接続 import 課題を解く, 事前教材を読む

        結果 = 課題を解く(課題, 事前教材を読む())
        公開結果 = {
            "results": [
                {
                    "answer": 行.get("answer"),
                    "status": 行.get("status"),
                }
                for 行 in 結果.get("results", [])
            ]
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
        from 接続.ARC2.HDS接続 import 事前教材を読む

        教材 = 事前教材を読む()
        print(json.dumps({"status": "ok", "prior_examples": len(教材)}))
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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    環境 = os.environ.copy()
    環境["ARC2_PAYLOAD_ROOT"] = str(payload_root)
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
    return 結果を候補へ(課題ID, 課題, 実行結果)


def _atomic_new(path: Path, value: dict[str, Any]) -> bytes:
    content = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with path.open("xb") as target:
        target.write(content)
    return content


def _discover_challenges() -> Path:
    候補 = list(Path("/kaggle/input").rglob("arc-agi_evaluation_challenges.json"))
    if len(候補) != 1:
        raise RuntimeError(f"大会evaluation challengeを一意に特定できない: 候補数={len(候補)}")
    return 候補[0]


def run_cli(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--preflight", action="store_true")
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
                lambda item: _run_one(item[0], item[1], str(入口), payload_root),
                item_iter,
            )
        )
    提出: dict[str, list[dict[str, Any]]] = {}
    保留群: list[dict[str, Any]] = []
    for (課題ID, _), (候補群, 保留記録) in zip(課題群.items(), 記録群, strict=True):
        提出[課題ID] = 候補群
        保留群.extend(保留記録)
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
        "fallbacks": 保留群,
        "seconds": round(time.monotonic() - started, 3),
        "submission_sha256": hashlib.sha256(submission_bytes).hexdigest(),
    }
    _atomic_new(audit_path, audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
