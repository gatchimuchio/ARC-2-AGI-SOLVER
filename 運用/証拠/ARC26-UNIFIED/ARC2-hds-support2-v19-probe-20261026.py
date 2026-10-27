"""Probe global HDS minimum support 2 as an alternate challenge candidate."""
from __future__ import annotations

from collections import Counter, defaultdict
import concurrent.futures
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v19-local-context-second-20261026/full-runtime/submission.json"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _key(grid):
    return tuple(tuple(row) for row in grid)


def _valid_grid(grid):
    return (
        isinstance(grid, list)
        and 1 <= len(grid) <= 30
        and all(
            isinstance(row, list)
            and 1 <= len(row) <= 30
            and len(row) == len(grid[0])
            and all(type(color) is int and 0 <= color <= 9 for color in row)
            for row in grid
        )
    )


def _worker(task_record):
    sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2 import HDS接続 as hds

    original_engine = hds.HDS学習実行系

    def support2_engine(*, 最小支持数=3, 最大条件数=2):
        return original_engine(最小支持数=2, 最大条件数=最大条件数)

    hds.HDS学習実行系 = support2_engine
    task = task_record["task"]
    raw = hds.課題を解く(task, hds.事前教材を読む(), 候補収集=True)
    rows = []
    for source, result in zip(task["test"], raw.get("results", []), strict=True):
        candidates = []
        if isinstance(result, dict):
            answer = result.get("answer")
            if _valid_grid(answer):
                candidates.append(("hds_answer", answer))
            pair = result.get("candidate_attempts")
            if isinstance(pair, list) and len(pair) == 2:
                for grid in pair:
                    if _valid_grid(grid):
                        candidates.append(("hds_pair", grid))
            for record in result.get("candidate_predictions", []):
                if isinstance(record, dict) and _valid_grid(record.get("answer")):
                    candidates.append((record.get("family", "hds_candidate"), record["answer"]))
        counts = {}
        for family, grid in candidates:
            counts.setdefault(_key(grid), {"grid": grid, "families": set()})
            counts[_key(grid)]["families"].add(family)
        rows.append({
            "direct_answer": result.get("answer") if isinstance(result, dict) and _valid_grid(result.get("answer")) else None,
            "candidates": [
            {"grid": value["grid"], "votes": len(value["families"])}
            for value in counts.values()
            ],
        })
    return task_record["task_id"], rows


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    tasks = [
        {
            "task_id": task_id,
            "task": {
                "train": task["train"],
                "test": [{"input": pair["input"]} for pair in task["test"]],
            },
        }
        for task_id, task in sorted(challenge.items())
    ]
    started = time.monotonic()
    generated = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_worker, task): task["task_id"] for task in tasks}
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            task_id, rows = future.result()
            generated[task_id] = rows
            if index % 24 == 0 or index == len(tasks):
                print(f"support2 generation {index}/{len(tasks)}", flush=True)

    # Challenge targets are opened only after every candidate pool is frozen.
    targets = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in SOURCE_ROOT.glob("*.json")
    }
    stats = {
        name: {
            "candidate_examples": 0,
            "distinct_from_both_examples": 0,
            "any_candidate_exact_examples": 0,
            "selected_examples": 0,
            "newly_correct_examples": 0,
            "regressed_examples": 0,
            "baseline_exact_tasks": 0,
            "combined_exact_tasks": 0,
            "newly_correct_tasks": 0,
            "regressed_tasks": 0,
        }
        for name in ("hds_answer", "unique_top_vote")
    }
    baseline_exact_examples = 0
    baseline_task_rows = {}
    updated_task_rows = {name: defaultdict(list) for name in stats}
    examples = 0
    distinct_pool_examples = 0
    top_ties = 0
    for task_id, rows in generated.items():
        baseline_task_rows[task_id] = []
        for index, row in enumerate(rows):
            examples += 1
            target = targets[task_id][index]
            base = baseline[task_id][index]
            before = base["attempt_1"] == target or base["attempt_2"] == target
            baseline_exact_examples += before
            baseline_task_rows[task_id].append(before)
            candidates = row["candidates"]
            distinct = [
                item for item in candidates
                if item["grid"] != base["attempt_1"] and item["grid"] != base["attempt_2"]
            ]
            distinct_pool_examples += bool(distinct)
            any_exact = any(item["grid"] == target for item in candidates)
            vote_counts = Counter()
            by_key = {}
            for item in candidates:
                k = _key(item["grid"])
                vote_counts[k] = max(vote_counts[k], item["votes"])
                by_key[k] = item["grid"]
            max_vote = max(vote_counts.values(), default=0)
            winners = [k for k, vote in vote_counts.items() if vote == max_vote]
            unique_top = by_key[winners[0]] if len(winners) == 1 and max_vote > 0 else None
            if len(winners) > 1 and max_vote > 0:
                top_ties += 1
            final_answer = row["direct_answer"]
            for name, candidate in (("hds_answer", final_answer), ("unique_top_vote", unique_top)):
                stat = stats[name]
                stat["candidate_examples"] += candidate is not None
                stat["distinct_from_both_examples"] += candidate is not None and candidate not in (base["attempt_1"], base["attempt_2"])
                stat["any_candidate_exact_examples"] += any_exact if name == "unique_top_vote" else (
                    candidate == target if candidate is not None else False
                )
                updated = dict(base)
                if not before and candidate is not None and candidate not in (base["attempt_1"], base["attempt_2"]):
                    updated["attempt_2"] = candidate
                    stat["selected_examples"] += 1
                after = updated["attempt_1"] == target or updated["attempt_2"] == target
                stat["newly_correct_examples"] += after and not before
                stat["regressed_examples"] += before and not after
                updated_task_rows[name][task_id].append(after)
    baseline_exact_tasks = sum(all(values) for values in baseline_task_rows.values())
    for name, stat in stats.items():
        stat["baseline_exact_tasks"] = baseline_exact_tasks
        stat["combined_exact_tasks"] = sum(all(values) for values in updated_task_rows[name].values())
        stat["newly_correct_tasks"] = sum(
            all(updated_task_rows[name][task_id]) and not all(baseline_task_rows[task_id])
            for task_id in baseline_task_rows
        )
        stat["regressed_tasks"] = sum(
            all(baseline_task_rows[task_id]) and not all(updated_task_rows[name][task_id])
            for task_id in baseline_task_rows
        )
    report = {
        "schema": "arc2-hds-support2-v19-probe-v1",
        "challenge_tasks": len(challenge),
        "challenge_examples": examples,
        "candidate_generation_seconds": round(time.monotonic() - started, 3),
        "baseline_v19": {
            "exact_tasks": baseline_exact_tasks,
            "exact_examples": baseline_exact_examples,
        },
        "distinct_candidates_from_current_pair_examples": distinct_pool_examples,
        "examples_with_tied_top_candidates": top_ties,
        "policies": stats,
        "runtime_received_challenge_targets": False,
        "targets_read_only_after_all_candidate_generation": True,
        "per_task_predictions_or_targets_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "challenge": _sha(CHALLENGE),
            "baseline_v19": _sha(BASELINE),
            "hds_connector": _sha(ROOT / "接続/ARC2/HDS接続.py"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"baseline_v19": report["baseline_v19"], "policies": stats, "distinct_candidate_examples": distinct_pool_examples}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
