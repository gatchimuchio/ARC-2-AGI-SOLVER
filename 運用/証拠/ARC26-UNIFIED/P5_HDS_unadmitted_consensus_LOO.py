"""Test unanimous raw HDS predictions as a guarded attempt-2 candidate in public-training LOO."""

from __future__ import annotations

from collections import Counter
import hashlib
import importlib
import json
from pathlib import Path
import runpy
import sys
import tempfile
import time
import shutil


ROOT = Path(__file__).resolve().parents[3]
SHARED_PATH = ROOT / "運用/証拠/ARC26-UNIFIED/P5_HDS_train_proven_candidate_LOO.py"
SHARED = runpy.run_path(str(SHARED_PATH), run_name="p5_shared_helpers")
valid_grid = SHARED["valid_grid"]
key = SHARED["key"]
selected_candidate = SHARED["selected_candidate"]
TRAINING_DIR = SHARED["TRAINING_DIR"]
HDS_DIR = SHARED["HDS_DIR"]
BASELINE_REPORT = ROOT / "運用/証拠/ARC2_公式スコア起点_20261024/P5_HDS_raw_candidate_LOO.json"
SUPPORT_MINIMUM = 3


def install_temporary_raw_consensus(temporary_root: Path):
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
    target = overlay / "接続/ARC2/HDS接続.py"
    source = target.read_text(encoding="utf-8")
    return_block = (
        '        "equality_admitted": 同値あり,\n'
        '        "quarantined": len(実行結果.係争中原理群),\n'
    )
    raw_candidate = (
        '        "equality_admitted": 同値あり,\n'
        '        "raw_consensus_candidate": (\n'
        '            deepcopy(値群[0])\n'
        '            if not 同値あり and 値群 and all(v == 値群[0] for v in 値群)\n'
        '            and 有効格子(値群[0]) else None\n'
        '        ),\n'
        '        "quarantined": len(実行結果.係争中原理群),\n'
    )
    if source.count(return_block) != 1:
        raise RuntimeError("expected a single output-grid return block")
    source = source.replace(return_block, raw_candidate, 1)
    candidate_list = "        生候補群 = []\n"
    collect_block = (
        "        生候補群 = []\n"
        '        if (候補収集 and 基底結果["answer"] is None\n'
        '                and 基底結果["raw_consensus_candidate"] is not None):\n'
        '            生候補群.append({"family": "HDS未確定原理合意",\n'
        '                             "answer": deepcopy(基底結果["raw_consensus_candidate"])})\n'
    )
    if source.count(candidate_list) != 1:
        raise RuntimeError("expected a single raw candidate collection point")
    source = source.replace(candidate_list, collect_block, 1)
    target.write_text(source, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return overlay, digest


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--max-folds", type=int, default=None)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_suffix(".json"))
    args = parser.parse_args()
    if args.max_folds is not None and args.max_folds < 1:
        raise SystemExit("--max-folds must be positive")

    baseline = json.loads(BASELINE_REPORT.read_text(encoding="utf-8"))
    files = sorted(TRAINING_DIR.glob("*.json"))
    manifest = hashlib.sha256()
    started = time.perf_counter()
    temporary_directory = tempfile.TemporaryDirectory(prefix="arc2-p5-hds-consensus-")
    try:
        overlay, variant_sha256 = install_temporary_raw_consensus(Path(temporary_directory.name))
        sys.path.insert(0, str(overlay))
        sys.path.insert(1, str(HDS_DIR))
        sys.path.insert(2, str(ROOT))
        importlib.invalidate_caches()
        module = importlib.import_module("接続.ARC2.HDS接続")
        solve = module.課題を解く

        eligible_tasks = folds = answer_rows = first_exact = 0
        candidate_folds = raw_votes = unique_second_folds = unique_second_exact = unique_second_wrong = 0
        top_second_folds = top_second_exact = top_second_wrong = 0
        union_top_exact = union_unique_exact = 0
        pool_histogram = Counter()
        stop = False
        for path in files:
            raw = path.read_bytes()
            manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
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
                solved = solve({"train": teachers, "test": [{"input": heldout["input"]}]}, [], 候補収集=True)
                row = solved.get("results", [{}])[0]
                first = row.get("answer")
                has_first = valid_grid(first)
                if has_first:
                    answer_rows += 1
                else:
                    first = heldout["input"]  # deduplication only; fallback is never scored
                is_first_exact = has_first and first == heldout["output"]
                first_exact += int(is_first_exact)
                proposals = row.get("candidate_predictions", [])
                raw_votes += len(proposals)
                unique_guess, pool_size = selected_candidate(proposals, first, True)
                top_guess, _ = selected_candidate(proposals, first, False)
                pool_histogram[str(pool_size)] += 1
                candidate_folds += int(pool_size > 0)
                if unique_guess is not None:
                    unique_second_folds += 1
                    exact = unique_guess == heldout["output"]
                    unique_second_exact += int(exact)
                    unique_second_wrong += int(not exact)
                if top_guess is not None:
                    top_second_folds += 1
                    exact = top_guess == heldout["output"]
                    top_second_exact += int(exact)
                    top_second_wrong += int(not exact)
                union_unique_exact += int(is_first_exact or unique_guess == heldout["output"])
                union_top_exact += int(is_first_exact or top_guess == heldout["output"])
            if eligible_tasks % 25 == 0:
                print(json.dumps({"eligible_tasks_done": eligible_tasks, "loo_folds_done": folds, "elapsed_seconds": round(time.perf_counter() - started, 1)}, sort_keys=True), flush=True)
            if stop:
                break

        complete = args.max_folds is None
        result = {
            "schema": "arc2-p5-hds-unadmitted-consensus-loo.v1",
            "hypothesis": "allow a unanimous valid raw HDS output with no equality-admitted principle to enter the attempt-2 candidate pool; keep answer and HOLD gates unchanged",
            "data_source": "public ARC-AGI-2 training split only",
            "prior_examples_used": 0,
            "minimum_teacher_support": SUPPORT_MINIMUM,
            "fold_limit": args.max_folds,
            "complete": complete,
            "stop_reason": "all_training_folds" if complete else "fold_limit",
            "eligible_tasks": eligible_tasks,
            "loo_folds": folds,
            "training_manifest_sha256": manifest.hexdigest(),
            "baseline_report": str(BASELINE_REPORT.relative_to(ROOT)),
            "baseline_hds_source_sha256": baseline["hds_source_sha256"],
            "production_hds_source_sha256": hashlib.sha256((ROOT / "接続/ARC2/HDS接続.py").read_bytes()).hexdigest(),
            "temporary_variant_sha256": variant_sha256,
            "baseline_loo_folds": baseline["loo_folds"],
            "baseline_first_answer_rows": baseline["hds_first_answer_rows"],
            "baseline_first_exact": baseline["hds_first_guess_exact"],
            "baseline_candidate_folds": baseline["folds_with_any_distinct_raw_candidate"],
            "baseline_raw_family_votes": baseline["raw_candidate_family_votes"],
            "baseline_union_exact": baseline["first_or_one_vote_second_exact"],
            "first_answer_rows": answer_rows,
            "first_exact": first_exact,
            "delta_first_answer_rows": answer_rows - baseline["hds_first_answer_rows"] if folds == baseline["loo_folds"] else None,
            "delta_first_exact": first_exact - baseline["hds_first_guess_exact"] if folds == baseline["loo_folds"] else None,
            "candidate_folds": candidate_folds,
            "raw_candidate_family_votes": raw_votes,
            "distinct_candidate_count_per_fold_histogram": dict(sorted(pool_histogram.items(), key=lambda item: int(item[0]))),
            "unique_pool_second_guess": {"folds": unique_second_folds, "exact": unique_second_exact, "wrong": unique_second_wrong},
            "top_vote_second_guess": {"folds": top_second_folds, "exact": top_second_exact, "wrong": top_second_wrong},
            "first_or_unique_pool_second_exact": union_unique_exact,
            "first_or_top_vote_second_exact": union_top_exact,
            "delta_candidate_folds": candidate_folds - baseline["folds_with_any_distinct_raw_candidate"] if folds == baseline["loo_folds"] else None,
            "delta_raw_candidate_family_votes": raw_votes - baseline["raw_candidate_family_votes"] if folds == baseline["loo_folds"] else None,
            "delta_union_top_vote_exact": union_top_exact - baseline["first_or_one_vote_second_exact"] if folds == baseline["loo_folds"] else None,
            "fallback_as_correct": False,
            "evaluation_solutions_read": False,
            "task_identifiers_or_grids_saved": False,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "baseline_elapsed_seconds": baseline["elapsed_seconds"],
        }
        args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    finally:
        temporary_directory.cleanup()


if __name__ == "__main__":
    main()
