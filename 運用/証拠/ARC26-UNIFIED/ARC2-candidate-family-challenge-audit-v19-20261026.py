"""Score generic candidate families emitted by the current ARC2 runtime."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v19-local-context-second-20261026/full-runtime/submission.json"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _key(grid):
    return tuple(tuple(row) for row in grid)


def _candidate_rows(task_record):
    os.environ["ARC2_PAYLOAD_ROOT"] = str(ROOT)
    sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2.HDS接続 import 課題を解く, 事前教材を読む
    from 接続.ARC2.単純変換候補 import unique_candidate, valid_grid
    from 接続.ARC2.複合幾何変換候補 import CompositeGeometryCandidate
    from 接続.ARC2.局所近傍変換候補 import LocalCellContextCandidate
    from 接続.ARC2.埋込見本一致候補 import fit_candidate, predict_candidate

    task = task_record["task"]
    raw = 課題を解く(task, 事前教材を読む(), 候補収集=True)
    teachers = task["train"]
    embed_model, _ = fit_candidate(teachers)
    geometry = CompositeGeometryCandidate(teachers)
    local = LocalCellContextCandidate(teachers)
    candidates = []
    for index, (source, result) in enumerate(zip(task["test"], raw.get("results", []), strict=True)):
        rows = []
        if isinstance(result, dict):
            family = result.get("family")
            answer = result.get("answer")
            if isinstance(family, str) and valid_grid(answer):
                rows.append((family, answer))
            pair = result.get("candidate_attempts")
            pair_family = result.get("candidate_attempt_family")
            if isinstance(pair, list) and len(pair) == 2 and isinstance(pair_family, str):
                for slot, grid in enumerate(pair, start=1):
                    if valid_grid(grid):
                        rows.append((f"{pair_family}:attempt{slot}", grid))
            for record in result.get("candidate_predictions", []):
                if isinstance(record, dict) and isinstance(record.get("family"), str) and valid_grid(record.get("answer")):
                    rows.append((record["family"], record["answer"]))
        simple = unique_candidate(teachers, source["input"])
        if valid_grid(simple):
            rows.append(("ARC単純幾何色写像", simple))
        composite, _ = geometry.候補(source["input"], {})
        if valid_grid(composite):
            rows.append(("ARC背景crop複合幾何変換", composite))
        context, _ = local.候補(source["input"], {})
        if valid_grid(context):
            rows.append(("ARC局所近傍セル変換", context))
        if embed_model is not None:
            embedded, _ = predict_candidate(source["input"], embed_model)
            if valid_grid(embedded):
                rows.append(("ARC反復見本パネル照合候補", embedded))
        by_family = defaultdict(dict)
        for family, grid in rows:
            by_family[family][_key(grid)] = grid
        candidates.append({family: list(grids.values()) for family, grids in by_family.items()})
    return task_record["task_id"], candidates


def _exact(row, target):
    return any(row.get(key) == target for key in ("attempt_1", "attempt_2"))


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    tasks = [
        {"task_id": task_id,
         "task": {"train": task["train"], "test": [{"input": pair["input"]} for pair in task["test"]]}}
        for task_id, task in sorted(challenge.items())
    ]

    # Generate every task's candidate pool from train examples and test inputs only.
    started = time.monotonic()
    generated = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_candidate_rows, task): task["task_id"] for task in tasks}
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            task_id, rows = future.result()
            generated[task_id] = rows
            if index % 24 == 0 or index == len(tasks):
                print(f"candidate generation {index}/{len(tasks)}", flush=True)

    # Public outputs are loaded only after all candidates are frozen.
    targets = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in SOURCE_ROOT.glob("*.json")
    }
    family_stats = defaultdict(Counter)
    family_tasks = defaultdict(lambda: defaultdict(lambda: {"before": [], "after": []}))
    examples = 0
    baseline_examples = baseline_tasks = 0
    task_before = defaultdict(list)
    task_after = defaultdict(lambda: defaultdict(list))
    for task_id, rows in generated.items():
        for index, family_map in enumerate(rows):
            examples += 1
            base = baseline[task_id][index]
            target = targets[task_id][index]
            before = _exact(base, target)
            baseline_examples += before
            task_before[task_id].append(before)
            for family, candidates in family_map.items():
                stats = family_stats[family]
                stats["fitted_examples"] += 1
                exact_candidate = any(candidate == target for candidate in candidates)
                stats["exact_candidate_examples"] += exact_candidate
                distinct = [candidate for candidate in candidates if candidate not in (base.get("attempt_1"), base.get("attempt_2"))]
                stats["distinct_candidate_examples"] += bool(distinct)
                updated = dict(base)
                if distinct:
                    updated["attempt_2"] = distinct[0]
                    stats["candidate_as_attempt2_examples"] += 1
                after = _exact(updated, target)
                stats["combined_exact_examples"] += after
                stats["newly_correct_examples"] += after and not before
                stats["regressed_examples"] += before and not after
                family_tasks[family][task_id]["before"].append(before)
                family_tasks[family][task_id]["after"].append(after)
                task_after[family][task_id].append(after)
    baseline_tasks = sum(all(values) for values in task_before.values())
    per_family = {}
    for family, stats in family_stats.items():
        rows = family_tasks[family]
        per_family[family] = {
            **dict(stats),
            "baseline_exact_tasks": sum(all(value["before"]) for value in rows.values()),
            "combined_exact_tasks": sum(all(value["after"]) for value in rows.values()),
            "newly_correct_tasks": sum(all(value["after"]) and not all(value["before"]) for value in rows.values()),
            "regressed_tasks": sum(all(value["before"]) and not all(value["after"]) for value in rows.values()),
        }
    report = {
        "schema": "arc2-candidate-family-challenge-audit-v19-v1",
        "challenge_tasks": len(challenge),
        "challenge_examples": examples,
        "candidate_generation_seconds": round(time.monotonic() - started, 3),
        "baseline_v19": {"exact_tasks": baseline_tasks, "exact_examples": baseline_examples},
        "candidate_families": dict(sorted(per_family.items())),
        "runtime_received_challenge_targets": False,
        "targets_read_only_after_all_candidate_generation": True,
        "per_task_predictions_or_targets_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "challenge": _sha(CHALLENGE),
            "baseline_v19": _sha(BASELINE),
            "hds_connector": _sha(ROOT / "接続/ARC2/HDS接続.py"),
            "adapter": _sha(ROOT / "接続/ARC2/Kaggle提出.py"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"baseline_v19": report["baseline_v19"], "candidate_families": report["candidate_families"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
