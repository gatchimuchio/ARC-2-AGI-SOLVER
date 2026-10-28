"""保存済み候補の事後照合。推論には正解を渡さず、診断経路の射程だけを集計する。"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def 読む(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _格子(value):
    return (isinstance(value, list) and 1 <= len(value) <= 30
            and all(isinstance(row, list) and 1 <= len(row) <= 30
                    and all(type(x) is int and 0 <= x <= 9 for x in row)
                    for row in value)
            and len({len(row) for row in value}) == 1)


def _記録候補(row):
    diag = row.get("diagnostic_candidates")
    if not isinstance(diag, dict):
        raise ValueError("候補診断が欠落しています")
    values = []
    for key in ("preselection", "postselection"):
        group = diag.get(key, [])
        if not isinstance(group, list):
            raise ValueError("候補一覧が不正です")
        values.extend(item.get("answer") for item in group if isinstance(item, dict))
    attempts = diag.get("candidate_attempts")
    if isinstance(attempts, list):
        values.extend(attempts)
    values.extend((diag.get("simple_candidate"), row.get("answer"), row.get("second_answer")))
    return ([value for value in values if _格子(value)],
            sum(isinstance(value, list) and not _格子(value) for value in values))


def _hash(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def 集計(*, challenges, predictions, baseline_predictions, audit, baseline_audit,
       solutions, records_dir):
    if predictions != baseline_predictions:
        raise ValueError("診断による出力変更のため基準との比較を中止します")
    if set(predictions) != set(challenges) or not set(challenges) <= set(solutions):
        raise ValueError("対象課題の集合が不正です")
    def fallbacks(a):
        rows = a["fallbacks"]
        values = {(x["task_id"], x["test_index"], x["reason"]) for x in rows}
        indices = {(x["task_id"], x["test_index"]) for x in rows}
        if len(indices) != len(rows) or a.get("fallback_count") != len(rows):
            raise ValueError("fallback一覧の重複または件数不一致")
        return values
    if fallbacks(audit) != fallbacks(baseline_audit):
        raise ValueError("診断前後でfallbackが変化したため比較を中止します")
    fallback_indices = {(task, index) for task, index, _ in fallbacks(audit)}
    token = audit.get("deadline_control", {}).get("run_token")
    if not isinstance(token, str) or not token:
        raise ValueError("診断実行IDがありません")
    counts = Counter()
    actual_fallbacks = set()
    for task, challenge in challenges.items():
        tests = challenge["test"]
        if any(set(t) != {"input"} for t in tests):
            raise ValueError("推論入力にtest正解または余分な情報があります")
        pred = predictions[task]
        truth = solutions[task]
        if len(tests) != len(pred) or len(tests) != len(truth):
            raise ValueError("test数と出力数が一致しません")
        if not task.isalnum():
            raise ValueError("診断記録IDが不正です")
        path = records_dir / f"{task}.json"
        if path.is_file():
            record = 読む(path)
            result = record.get("result")
            if (record.get("run_token") != token or record.get("task_sha256") != _hash(challenge)
                    or record.get("result_sha256") != _hash(result) or not isinstance(result, dict)):
                raise ValueError("診断記録と実行ID・入力・結果の対応が不正です")
            rows = result.get("results")
            if rows is None and "error" not in result:
                raise ValueError("診断結果に行もエラーもありません")
        else:
            rows = None
        if rows is not None and (not isinstance(rows, list) or len(rows) != len(tests)):
            raise ValueError("診断記録の行数が不正です")
        for index, (attempt, expected) in enumerate(zip(pred, truth, strict=True)):
            first, second = attempt["attempt_1"], attempt["attempt_2"]
            if not _格子(first) or not _格子(second):
                raise ValueError("予測格子が不正です")
            if (task, index) in fallback_indices:
                actual_fallbacks.add((task, index))
                if first != tests[index]["input"]:
                    raise ValueError("fallbackが入力コピーではありません")
            correct = ((task, index) not in fallback_indices and first == expected) or (
                second != first and second == expected)
            if correct:
                counts["submitted_correct"] += 1
            elif rows is None:
                counts["unobserved"] += 1
            else:
                candidates, invalid = _記録候補(rows[index])
                counts["invalid_candidate_observations"] += invalid
                if any(x == expected for x in candidates):
                    counts["observed_correct_candidate_not_submitted"] += 1
                elif candidates:
                    counts["observed_candidates_incorrect"] += 1
                else:
                    counts["no_candidate_observed"] += 1
    if actual_fallbacks != fallback_indices:
        raise ValueError("存在しない課題または位置のfallbackがあります")
    return {name: counts[name] for name in (
        "submitted_correct", "observed_correct_candidate_not_submitted",
        "observed_candidates_incorrect", "no_candidate_observed", "unobserved",
        "invalid_candidate_observations")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("challenges", "predictions", "baseline", "audit", "baseline-audit", "solutions", "records-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    original = args.baseline.read_bytes()
    current = args.predictions.read_bytes()
    if original != current:
        raise ValueError("診断前後の予測バイト列が一致しません")
    audit, baseline_audit = 読む(args.audit), 読む(args.baseline_audit)
    challenge_sha = hashlib.sha256(args.challenges.read_bytes()).hexdigest()
    prediction_sha = hashlib.sha256(current).hexdigest()
    if any(a.get("challenge_sha256") != challenge_sha or a.get("submission_sha256") != prediction_sha
           for a in (audit, baseline_audit)):
        raise ValueError("監査記録と入力または予測のhashが一致しません")
    result = 集計(challenges=読む(args.challenges), predictions=読む(args.predictions),
                baseline_predictions=読む(args.baseline), audit=audit,
                baseline_audit=baseline_audit, solutions=読む(args.solutions),
                records_dir=args.records_dir)
    print(json.dumps({"counts": result, "prediction_sha256": prediction_sha,
                      "scope": "Only candidates captured by instrumented paths; postselection candidates may be diagnostic-only."},
                     ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
