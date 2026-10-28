"""生成済み予測を別プロセスで採点し、fallbackを推論正解から除く。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def 採点(予測パス: Path, 監査パス: Path, 正解パス: Path, 課題パス: Path) -> dict:
    raw = 予測パス.read_bytes()
    予測 = json.loads(raw)
    監査 = json.loads(監査パス.read_text(encoding="utf-8"))
    正解 = json.loads(正解パス.read_text(encoding="utf-8"))
    課題raw = 課題パス.read_bytes()
    課題 = json.loads(課題raw)
    課題hash = hashlib.sha256(課題raw).hexdigest()
    if 監査.get("challenge_sha256") != 課題hash:
        raise ValueError("課題と監査のSHA256が一致しません")
    if set(予測) != set(課題):
        raise ValueError("予測と課題の対象が一致しません")
    出力hash = hashlib.sha256(raw).hexdigest()
    if 監査.get("submission_sha256") != 出力hash:
        raise ValueError("予測と監査のSHA256が一致しません")
    fallback一覧 = 監査.get("fallbacks")
    if not isinstance(fallback一覧, list):
        raise ValueError("fallback一覧がありません")
    fallback = {(item["task_id"], item["test_index"]) for item in fallback一覧}
    if len(fallback) != len(fallback一覧) or len(fallback) != 監査.get("fallback_count"):
        raise ValueError("fallback一覧に重複または件数不一致があります")
    結果 = {"tasks": len(予測), "grids": 0, "fallback": 0,
          "distinct_attempts": 0, "nonfallback_pass1": 0,
          "nonfallback_pass2": 0, "nonfallback_attempt2_only": 0,
          "fallback_first_matches": 0, "fallback_second_candidate_hits": 0}
    実際のfallback = set()
    for task, pairs in 予測.items():
        if (not isinstance(pairs, list) or task not in 正解
                or len(pairs) != len(正解[task]) or len(pairs) != len(課題[task]["test"])):
            raise ValueError("予測と正解の対象または出力数が一致しません")
        for index, pair in enumerate(pairs):
            if not isinstance(pair, dict) or set(pair) != {"attempt_1", "attempt_2"}:
                raise ValueError("attempt形式が不正です")
            結果["grids"] += 1
            first, second = pair["attempt_1"], pair["attempt_2"]
            結果["distinct_attempts"] += first != second
            hit1, hit2 = first == 正解[task][index], second == 正解[task][index]
            if (task, index) in fallback:
                実際のfallback.add((task, index))
                結果["fallback"] += 1
                if first != 課題[task]["test"][index]["input"]:
                    raise ValueError("fallbackの第1候補が入力コピーと一致しません")
                結果["fallback_first_matches"] += hit1
                # 第1候補がfallbackでも、異なる第2候補は独立して生成された格子。
                第二候補有効 = second != first
                結果["nonfallback_pass2"] += 第二候補有効 and hit2
                結果["nonfallback_attempt2_only"] += 第二候補有効 and hit2
                結果["fallback_second_candidate_hits"] += 第二候補有効 and hit2
            else:
                結果["nonfallback_pass1"] += hit1
                結果["nonfallback_pass2"] += hit1 or hit2
                結果["nonfallback_attempt2_only"] += not hit1 and hit2
    if 実際のfallback != fallback or 結果["grids"] != 監査.get("test_examples"):
        raise ValueError("監査対象が予測と一致しません")
    結果["prediction_sha256"] = 出力hash
    結果["answers_sha256"] = hashlib.sha256(正解パス.read_bytes()).hexdigest()
    結果["audit_sha256"] = hashlib.sha256(監査パス.read_bytes()).hexdigest()
    結果["challenges_sha256"] = 課題hash
    return 結果


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--solutions", required=True, type=Path)
    parser.add_argument("--challenges", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(採点(args.predictions, args.audit, args.solutions, args.challenges), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
