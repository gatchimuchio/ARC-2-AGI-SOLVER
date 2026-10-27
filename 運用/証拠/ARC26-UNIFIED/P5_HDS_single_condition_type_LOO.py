"""Test HDS admission with one observed condition value in public-training LOO.

The experiment changes only temporary copies of the HDS inference/validation
condition-diversity gate and ARC2 candidate instrumentation. Public-training
held-out outputs are read by the parent evaluator only after solver return.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[3]
TRAINING_DIR = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
HDS_DIR = ROOT / "HDS/学習系統/v0.4.2"
BASELINE_REPORT = ROOT / "運用/証拠/ARC2_公式スコア起点_20261024/P5_HDS_raw_candidate_LOO.json"
SUPPORT_MINIMUM = 3


def valid_grid(value):
    return (
        isinstance(value, list)
        and 1 <= len(value) <= 30
        and all(
            isinstance(row, list)
            and 1 <= len(row) <= 30
            and len(row) == len(value[0])
            and all(type(color) is int and 0 <= color <= 9 for color in row)
            for row in value
        )
    )


def key(grid):
    return tuple(tuple(row) for row in grid)


def selected_candidate(proposals, first, require_unique_pool):
    votes = Counter(
        key(row["answer"])
        for row in proposals
        if isinstance(row, dict)
        and valid_grid(row.get("answer"))
        and key(row["answer"]) != key(first)
    )
    if not votes:
        return None, len(votes)
    if require_unique_pool and len(votes) != 1:
        return None, len(votes)
    highest = max(votes.values())
    winners = [candidate for candidate, count in votes.items() if count == highest]
    if len(winners) != 1:
        return None, len(votes)
    return [list(row) for row in winners[0]], len(votes)


def install_temporary_candidate_pool(temporary_root: Path):
    overlay = temporary_root / "overlay"
    (overlay / "接続").mkdir(parents=True)
    init_source = ROOT / "接続/__init__.py"
    if init_source.is_file():
        shutil.copy2(init_source, overlay / "接続/__init__.py")
    else:
        (overlay / "接続/__init__.py").write_text("", encoding="utf-8")
    shutil.copytree(
        ROOT / "接続/ARC2",
        overlay / "接続/ARC2",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    hds_overlay = temporary_root / "hds_overlay"
    shutil.copytree(
        HDS_DIR,
        hds_overlay,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    inference_path = hds_overlay / "hds学習系統/推論.py"
    validation_path = hds_overlay / "hds学習系統/検証.py"
    inference = inference_path.read_text(encoding="utf-8")
    original_search_gate = "if 完全数 >= 最小支持数 and len(条件種類) >= 2:"
    if inference.count(original_search_gate) != 1:
        raise RuntimeError("expected a single HDS inference condition-diversity gate")
    inference = inference.replace(
        original_search_gate,
        "if 完全数 >= 最小支持数 and len(条件種類) >= 1:",
        1,
    )
    if inference.count("len(条件種類) < 2") != 2:
        raise RuntimeError("expected two HDS inference admission checks")
    inference = inference.replace("len(条件種類) < 2", "len(条件種類) < 1")
    inference_path.write_text(inference, encoding="utf-8", newline="\n")
    validation = validation_path.read_text(encoding="utf-8")
    original_validation_gate = "len(条件種類) < 2"
    if validation.count(original_validation_gate) != 1:
        raise RuntimeError("expected a single HDS validation condition-diversity gate")
    validation = validation.replace(original_validation_gate, "len(条件種類) < 1", 1)
    validation_path.write_text(validation, encoding="utf-8", newline="\n")

    target = overlay / "接続/ARC2/HDS接続.py"
    source = target.read_text(encoding="utf-8")
    original_gate = '            if not 記録["採用可"] or not 記録["同値採用"]:\n                continue'
    relaxed_gate = (
        '            if not 記録["採用可"] or (not 記録["同値採用"] and not 候補収集):\n'
        "                continue"
    )
    if source.count(original_gate) != 1:
        raise RuntimeError("expected a single HDS equality-admission gate")
    source = source.replace(original_gate, relaxed_gate, 1)
    prediction_line = '            予測 = 出力格子(機械, 観測へ({"候補": 候補}, 境界), 同値必須=True)\n'
    if source.count(prediction_line) != 1:
        raise RuntimeError("expected a single ordinary HDS prediction call")
    source = source.replace(
        prediction_line,
        '            if not 記録["同値採用"]:\n                continue\n' + prediction_line,
        1,
    )
    target.write_text(source, encoding="utf-8", newline="\n")
    changed_hds_digest = hashlib.sha256(
        inference.encode("utf-8") + b"\0" + validation.encode("utf-8")
    ).hexdigest()
    variant_digest = hashlib.sha256(
        source.encode("utf-8") + b"\0" + bytes.fromhex(changed_hds_digest)
    ).hexdigest()
    return overlay, hds_overlay, variant_digest, changed_hds_digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-folds", type=int, default=None)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_suffix(".json"))
    args = parser.parse_args()
    if args.max_folds is not None and args.max_folds < 1:
        raise SystemExit("--max-folds must be positive")

    baseline = json.loads(BASELINE_REPORT.read_text(encoding="utf-8"))
    files = sorted(TRAINING_DIR.glob("*.json"))
    training_manifest = hashlib.sha256()
    started = time.perf_counter()
    temporary_directory = tempfile.TemporaryDirectory(prefix="arc2-p5-single-condition-type-")
    try:
        overlay, hds_overlay, variant_sha256, hds_sha256 = install_temporary_candidate_pool(Path(temporary_directory.name))
        sys.path.insert(0, str(overlay))
        sys.path.insert(1, str(hds_overlay))
        sys.path.insert(2, str(ROOT))
        importlib.invalidate_caches()
        module = importlib.import_module("接続.ARC2.HDS接続")
        solve = module.課題を解く

        eligible_tasks = folds = answer_rows = first_exact = 0
        raw_candidate_votes = candidate_folds = 0
        unique_pool_folds = unique_pool_exact = unique_pool_wrong = 0
        top_vote_folds = top_vote_exact = top_vote_wrong = 0
        union_unique_exact = union_top_vote_exact = 0
        pool_size_histogram = Counter()

        stop = False
        for path in files:
            raw = path.read_bytes()
            training_manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
            examples = json.loads(raw).get("train", [])
            if len(examples) < SUPPORT_MINIMUM + 1:
                continue
            eligible_tasks += 1
            for index, heldout in enumerate(examples):
                if args.max_folds is not None and folds >= args.max_folds:
                    stop = True
                    break
                folds += 1
                teachers = [pair for i, pair in enumerate(examples) if i != index]
                result = solve(
                    {"train": teachers, "test": [{"input": heldout["input"]}]},
                    [],
                    候補収集=True,
                )
                row = result.get("results", [{}])[0]
                answer = row.get("answer")
                has_first = valid_grid(answer)
                if has_first:
                    answer_rows += 1
                    first = answer
                else:
                    # Keep fallback only for candidate deduplication; never score it.
                    first = heldout["input"]
                is_first_exact = has_first and first == heldout["output"]
                first_exact += int(is_first_exact)

                proposals = row.get("candidate_predictions", [])
                raw_candidate_votes += len(proposals)
                unique_guess, pool_size = selected_candidate(proposals, first, True)
                top_guess, _ = selected_candidate(proposals, first, False)
                pool_size_histogram[str(pool_size)] += 1
                candidate_folds += int(pool_size > 0)

                if unique_guess is not None:
                    unique_pool_folds += 1
                    exact = unique_guess == heldout["output"]
                    unique_pool_exact += int(exact)
                    unique_pool_wrong += int(not exact)
                if top_guess is not None:
                    top_vote_folds += 1
                    exact = top_guess == heldout["output"]
                    top_vote_exact += int(exact)
                    top_vote_wrong += int(not exact)
                union_unique_exact += int(is_first_exact or unique_guess == heldout["output"])
                union_top_vote_exact += int(is_first_exact or top_guess == heldout["output"])
            if eligible_tasks % 25 == 0:
                print(
                    json.dumps(
                        {
                            "eligible_tasks_done": eligible_tasks,
                            "loo_folds_done": folds,
                            "elapsed_seconds": round(time.perf_counter() - started, 1),
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
            if stop:
                break

        complete = args.max_folds is None
        result = {
            "schema": "arc2-p5-hds-single-condition-type-loo.v1",
            "experiment": "allow HDS inference and validation to admit a rule with one observed condition value when minimum support and exact training agreement still hold",
            "data_source": "public ARC-AGI-2 training split only",
            "prior_examples_used": 0,
            "minimum_teacher_support": SUPPORT_MINIMUM,
            "fold_limit": args.max_folds,
            "complete": complete,
            "stop_reason": "all_training_folds" if complete else "fold_limit",
            "eligible_tasks": eligible_tasks,
            "loo_folds": folds,
            "training_manifest_sha256": training_manifest.hexdigest(),
            "baseline_report": str(BASELINE_REPORT.relative_to(ROOT)),
            "baseline_hds_source_sha256": baseline["hds_source_sha256"],
            "baseline_loo_folds": baseline["loo_folds"],
            "baseline_first_answer_rows": baseline["hds_first_answer_rows"],
            "baseline_first_guess_exact": baseline["hds_first_guess_exact"],
            "baseline_folds_with_any_distinct_raw_candidate": baseline["folds_with_any_distinct_raw_candidate"],
            "baseline_raw_candidate_family_votes": baseline["raw_candidate_family_votes"],
            "baseline_first_or_one_vote_second_exact": baseline["first_or_one_vote_second_exact"],
            "variant_hds_source_sha256": hashlib.sha256((ROOT / "接続/ARC2/HDS接続.py").read_bytes()).hexdigest(),
            "temporary_variant_sha256": variant_sha256,
            "temporary_hds_inference_validation_sha256": hds_sha256,
            "first_answer_rows": answer_rows,
            "first_answer_exact": first_exact,
            "delta_first_answer_rows": answer_rows - baseline["hds_first_answer_rows"] if folds == baseline["loo_folds"] else None,
            "first_answer_path_unchanged": answer_rows == baseline["hds_first_answer_rows"] and first_exact == baseline["hds_first_guess_exact"] if folds == baseline["loo_folds"] else None,
            "fallback_as_correct": False,
            "candidate_folds": candidate_folds,
            "raw_candidate_family_votes": raw_candidate_votes,
            "distinct_candidate_count_per_fold_histogram": dict(sorted(pool_size_histogram.items(), key=lambda item: int(item[0]))),
            "unique_pool_second_guess": {"folds": unique_pool_folds, "exact": unique_pool_exact, "wrong": unique_pool_wrong},
            "top_vote_second_guess": {"folds": top_vote_folds, "exact": top_vote_exact, "wrong": top_vote_wrong},
            "first_or_unique_pool_second_exact": union_unique_exact,
            "first_or_top_vote_second_exact": union_top_vote_exact,
            "previous_first_guess_exact": baseline["hds_first_guess_exact"],
            "delta_first_guess_exact": first_exact - baseline["hds_first_guess_exact"] if folds == baseline["loo_folds"] else None,
            "delta_candidate_folds_vs_baseline": candidate_folds - baseline["folds_with_any_distinct_raw_candidate"] if folds == baseline["loo_folds"] else None,
            "delta_raw_candidate_family_votes_vs_baseline": raw_candidate_votes - baseline["raw_candidate_family_votes"] if folds == baseline["loo_folds"] else None,
            "delta_first_or_top_vote_second_exact": union_top_vote_exact - baseline["first_or_one_vote_second_exact"] if folds == baseline["loo_folds"] else None,
            "evaluation_solutions_read": False,
            "task_identifiers_or_grids_saved": False,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
        args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    finally:
        temporary_directory.cleanup()


if __name__ == "__main__":
    main()
