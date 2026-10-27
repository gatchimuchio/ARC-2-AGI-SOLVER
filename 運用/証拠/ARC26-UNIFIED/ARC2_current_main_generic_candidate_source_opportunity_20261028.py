"""Score all current-main candidate sources on a frozen public ARC2 challenge.

This extends the prior family audit with the generic simple-transform candidate
kept outside candidate_predictions. Runtime sees only public training pairs and
challenge inputs. Candidate grids stay in memory, and public training solutions
are read only after predictions freeze. Only aggregate metrics and hashes persist.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
HELPER_PATH = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2_current_main_object_candidate_hds_admission_matched_LOO_20261028.py"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
TARGETS = ROOT / "入力/Kaggle/arc-agi_training_solutions.json"
OUTPUT = Path(__file__).with_suffix(".json")
EXPECTED_CHALLENGE_SHA256 = "232264c58f825ee77327dcfc9f4e5cb2f83b8d997eb69032be1bf2205bbe1a83"
EXPECTED_TARGETS_SHA256 = "9f07a38bd25af5e83aa5bf85c5cb1a1fefdb30f6a755256fa65429e697ca97f9"
EXPECTED_BASELINE_PREDICTION_SHA256 = "54f6a303c4143f15279e2084d5ad798455e565b4d51cd6a2b226e4d4735af46a"
EXPECTED_TASKS = 240
EXPECTED_EXAMPLES = 259
RUN_TIMEOUT_SECONDS = 7200
POOL_MARKER = "__ARC2_CANDIDATE_POOL__"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def valid_grid(grid: object) -> bool:
    return (
        isinstance(grid, list) and 1 <= len(grid) <= 30
        and all(
            isinstance(row, list) and 1 <= len(row) <= 30
            and len(row) == len(grid[0])
            and all(type(color) is int and 0 <= color <= 9 for color in row)
            for row in grid
        )
    )


def load_helper():
    spec = importlib.util.spec_from_file_location("arc2_candidate_family_helper", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the frozen payload snapshot helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def instrument_wrapper(path: Path) -> tuple[str, str]:
    source = path.read_text(encoding="utf-8")
    original_sha = sha256(source.encode("utf-8"))
    candidate_row_anchor = '                    "second_answer": 第二候補 if 位置 < len(課題["test"]) else None,\n'
    candidate_row_replacement = candidate_row_anchor + (
        '                    "simple_transform_candidate": (\n'
        '                        deepcopy(行.get("simple_transform_candidate"))\n'
        '                        if 観測診断 and 格子か(行.get("simple_transform_candidate"))\n'
        '                        else None\n'
        '                    ),\n'
        '                    "candidate_predictions": (\n'
        '                        deepcopy(行.get("candidate_predictions", []))\n'
        '                        if 観測診断 else []\n'
        '                    ),\n'
    )
    if source.count(candidate_row_anchor) != 1:
        raise RuntimeError("worker result row anchor did not match exactly once")
    source = source.replace(candidate_row_anchor, candidate_row_replacement, 1)

    diagnostic_anchor = (
        '    診断 = (\n'
        '        実行結果.get("aggregate_diagnostics", {})\n'
        '        if aggregate_diagnostics and isinstance(実行結果, dict)\n'
        '        else {}\n'
        '    )\n'
    )
    diagnostic_replacement = diagnostic_anchor + (
        '    if aggregate_diagnostics and isinstance(実行結果, dict):\n'
        '        行群 = 実行結果.get("results", [])\n'
        '        診断["candidate_predictions_by_test"] = [\n'
        '            行.get("candidate_predictions", []) if isinstance(行, dict) else []\n'
        '            for 行 in 行群\n'
        '        ]\n'
    )
    if source.count(diagnostic_anchor) != 1:
        raise RuntimeError("worker aggregate diagnostic anchor did not match exactly once")
    source = source.replace(diagnostic_anchor, diagnostic_replacement, 1)

    final_print_anchor = (
        '    print(json.dumps(audit, ensure_ascii=False, indent=2))\n'
        '    return 0\n'
    )
    final_print_replacement = (
        '    print(json.dumps(audit, ensure_ascii=False, indent=2))\n'
        '    if arguments.aggregate_diagnostics and os.environ.get("ARC2_RETURN_CANDIDATE_POOL") == "1":\n'
        '        候補流 = {\n'
        '            課題ID: 診断.get("candidate_predictions_by_test", [])\n'
        '            for (課題ID, _), (_, _, 診断) in zip(課題群.items(), 記録群, strict=True)\n'
        '        }\n'
        '        print("__ARC2_CANDIDATE_POOL__" + json.dumps(候補流, ensure_ascii=False, separators=(",", ":")))\n'
        '    return 0\n'
    )
    if source.count(final_print_anchor) != 1:
        raise RuntimeError("CLI output anchor did not match exactly once")
    source = source.replace(final_print_anchor, final_print_replacement, 1)
    path.write_text(source, encoding="utf-8", newline="\n")
    return original_sha, sha256(source.encode("utf-8"))


def run_wrapper(payload_root: Path, output_dir: Path, revision: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True)
    env = {
        **os.environ,
        "ARC2_PAYLOAD_ROOT": str(payload_root),
        "ARC2_SOURCE_COMMIT": revision,
        "ARC2_RETURN_CANDIDATE_POOL": "1",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    command = [
        sys.executable,
        str(payload_root / "接続/ARC2/Kaggle提出.py"),
        "--aggregate-diagnostics",
        "--challenges",
        str(CHALLENGE),
        "--output-dir",
        str(output_dir),
    ]
    started = time.perf_counter()
    process = subprocess.run(
        command,
        cwd=payload_root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=RUN_TIMEOUT_SECONDS,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(
            "instrumented full runtime failed; "
            f"stdout_tail={process.stdout[-1200:]!r}; stderr_tail={process.stderr[-1200:]!r}"
        )
    pool_lines = [line for line in process.stdout.splitlines() if line.startswith(POOL_MARKER)]
    if len(pool_lines) != 1:
        raise RuntimeError(f"expected one in-memory candidate pool marker; found {len(pool_lines)}")
    candidate_pool = json.loads(pool_lines[0][len(POOL_MARKER):])
    prediction_path = output_dir / "submission.json"
    audit_path = output_dir / "submission_audit.json"
    if not prediction_path.is_file() or not audit_path.is_file():
        raise RuntimeError("instrumented wrapper did not create submission and audit")
    return {
        "candidate_pool": candidate_pool,
        "prediction_path": prediction_path,
        "audit_path": audit_path,
        "prediction_sha256": sha256(prediction_path.read_bytes()),
        "audit_sha256": sha256(audit_path.read_bytes()),
        "wrapper_wall_seconds": round(time.perf_counter() - started, 3),
    }


def score_candidate_pool(
    run: dict[str, Any], challenges: dict[str, Any], targets: dict[str, Any]
) -> dict[str, Any]:
    predictions = json.loads(run["prediction_path"].read_text(encoding="utf-8"))
    audit = json.loads(run["audit_path"].read_text(encoding="utf-8"))
    pool = run["candidate_pool"]
    if (
        set(predictions) != set(challenges)
        or not set(predictions).issubset(targets)
        or set(pool) != set(predictions)
    ):
        raise RuntimeError("challenge, prediction, public target, and candidate task sets differ")
    fallbacks = {
        (item["task_id"], item["test_index"])
        for item in audit.get("fallbacks", [])
    }
    if audit.get("tasks") != EXPECTED_TASKS or audit.get("test_examples") != EXPECTED_EXAMPLES:
        raise RuntimeError("instrumented runtime challenge counts differ")

    family_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "candidate_outputs": 0,
        "candidate_examples": set(),
        "distinct_grids": set(),
        "exact_outputs": 0,
        "exact_already_in_attempt_pair": 0,
        "exact_not_in_attempt_pair": 0,
        "add_only_pass2_opportunities": 0,
    })
    candidate_count = 0
    nonidentity_count = 0
    current_pair_exact = 0
    unique_unselected_exact_examples: set[tuple[str, int]] = set()
    add_only_union_examples: set[tuple[str, int]] = set()
    for task_id, rows in predictions.items():
        target_rows = targets[task_id]
        query_rows = challenges[task_id]["test"]
        candidate_rows = pool[task_id]
        if not (len(rows) == len(target_rows) == len(query_rows) == len(candidate_rows)):
            raise RuntimeError("candidate/test/output row count mismatch")
        for index, (row, target, query, records) in enumerate(
            zip(rows, target_rows, query_rows, candidate_rows, strict=True)
        ):
            if not isinstance(records, list):
                raise RuntimeError("candidate stream row is not a list")
            simple_candidate = row.get("simple_transform_candidate")
            if valid_grid(simple_candidate):
                records = [*records, {"family": "ARC単純変換候補", "answer": simple_candidate}]
            first = row["attempt_1"]
            second = row["attempt_2"]
            fallback = (task_id, index) in fallbacks
            pair_ok = (
                (not fallback and first == target)
                or (second != first and second == target)
            )
            current_pair_exact += int(pair_ok)
            seen: set[tuple[str, tuple[tuple[int, ...], ...]]] = set()
            for record in records:
                if not isinstance(record, dict):
                    continue
                family = record.get("family")
                grid = record.get("answer")
                if not isinstance(family, str) or len(family) > 160 or not valid_grid(grid):
                    continue
                if grid == query["input"]:
                    continue
                key = (family, tuple(tuple(values) for values in grid))
                if key in seen:
                    continue
                seen.add(key)
                stats = family_stats[family]
                stats["candidate_outputs"] += 1
                stats["candidate_examples"].add((task_id, index))
                stats["distinct_grids"].add(key[1])
                candidate_count += 1
                nonidentity_count += 1
                if grid != target:
                    continue
                stats["exact_outputs"] += 1
                selected = grid == first or grid == second
                if selected:
                    stats["exact_already_in_attempt_pair"] += 1
                    continue
                stats["exact_not_in_attempt_pair"] += 1
                example_key = (task_id, index)
                unique_unselected_exact_examples.add(example_key)
                if not pair_ok and second == first and grid != first:
                    stats["add_only_pass2_opportunities"] += 1
                    add_only_union_examples.add(example_key)

    aggregate_families = {}
    for family in sorted(family_stats):
        stats = family_stats[family]
        aggregate_families[family] = {
            "candidate_outputs": stats["candidate_outputs"],
            "candidate_examples": len(stats["candidate_examples"]),
            "distinct_candidate_grids": len(stats["distinct_grids"]),
            "exact_outputs": stats["exact_outputs"],
            "exact_already_in_attempt_pair": stats["exact_already_in_attempt_pair"],
            "exact_not_in_attempt_pair": stats["exact_not_in_attempt_pair"],
            "add_only_pass2_opportunities": stats["add_only_pass2_opportunities"],
        }
    return {
        "prediction_sha256": run["prediction_sha256"],
        "audit_sha256": run["audit_sha256"],
        "wrapper_wall_seconds": run["wrapper_wall_seconds"],
        "runtime_seconds": audit.get("seconds"),
        "challenge_tasks": audit.get("tasks"),
        "challenge_examples": audit.get("test_examples"),
        "fallback_count": audit.get("fallback_count"),
        "current_nonfallback_pass_at_2": current_pair_exact,
        "candidate_outputs": candidate_count,
        "candidate_outputs_nonidentity": nonidentity_count,
        "unique_unselected_exact_examples": len(unique_unselected_exact_examples),
        "unique_add_only_pass2_opportunities": len(add_only_union_examples),
        "family_candidate_metrics": aggregate_families,
    }


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    challenge_bytes = CHALLENGE.read_bytes()
    if sha256(challenge_bytes) != EXPECTED_CHALLENGE_SHA256:
        raise RuntimeError("public challenge hash differs from the recorded cohort")
    challenges = json.loads(challenge_bytes)
    example_count = sum(len(task["test"]) for task in challenges.values())
    if len(challenges) != EXPECTED_TASKS or example_count != EXPECTED_EXAMPLES:
        raise RuntimeError("public challenge size differs from the frozen cohort")
    helper = load_helper()
    bundle_bytes = helper.BUNDLE.read_bytes()
    if sha256(bundle_bytes) != helper.EXPECTED_BUNDLE_SHA256:
        raise RuntimeError("frozen Kaggle payload checksum mismatch")
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()

    with tempfile.TemporaryDirectory(prefix="arc2-candidate-family-opportunity-") as temp_name:
        temp_root = Path(temp_name)
        payload_root = temp_root / "payload"
        payload_root.mkdir()
        manifest, bundle_manifest_sha = helper.extract_bundle(bundle_bytes, payload_root)
        head_files = helper.read_head_payload(manifest, revision)
        payload_sha, retained_training, removed_absent = helper.materialize_head_snapshot(
            payload_root, manifest, head_files
        )
        wrapper_path = payload_root / "接続/ARC2/Kaggle提出.py"
        original_wrapper_sha, instrumented_wrapper_sha = instrument_wrapper(wrapper_path)
        run = run_wrapper(payload_root, temp_root / "output", revision)

        # The public solution file is opened only after the runtime predictions and
        # the in-memory candidate stream have been fixed.
        target_bytes = TARGETS.read_bytes()
        if sha256(target_bytes) != EXPECTED_TARGETS_SHA256:
            raise RuntimeError("public solution hash differs from the recorded cohort")
        targets = json.loads(target_bytes)
        metrics = score_candidate_pool(run, challenges, targets)
        previous_report = json.loads(Path(__file__).with_name("ARC2_current_main_candidate_family_opportunity_20261028.json").read_text(encoding="utf-8"))
        previous_metrics = previous_report["metrics"]
        if previous_metrics["prediction_sha256"] != metrics["prediction_sha256"]:
            raise RuntimeError("prediction output differs from the previous covered-family diagnostic")
        diagnostics = json.loads(run["audit_path"].read_text(encoding="utf-8")).get(
            "aggregate_diagnostics", {}
        )
        reported_family_counts = diagnostics.get("candidate_family_counts", {})
        report = {
            "schema": "arc2-current-main-generic-candidate-source-opportunity-v1",
            "run_id": "ARC2-current-main-generic-candidate-source-opportunity-20261028",
            "track": "ARC2",
            "instruction_id": "ARC26-UNIFIED-v6.0",
            "source_revision": revision,
            "payload_manifest_sha256": payload_sha,
            "seed_bundle_sha256": sha256(bundle_bytes),
            "seed_bundle_manifest_sha256": bundle_manifest_sha,
            "payload_member_count": len(manifest["files"]),
            "bundle_only_public_training_files_retained": retained_training,
            "bundle_paths_absent_from_main_removed": removed_absent,
            "original_wrapper_sha256": original_wrapper_sha,
            "instrumented_wrapper_sha256": instrumented_wrapper_sha,
            "challenge_sha256": sha256(challenge_bytes),
            "public_training_solutions_sha256": sha256(target_bytes),
            "public_solution_task_count": len(targets),
            "public_solutions_read_after_all_runtime_predictions": True,
            "aggregate_candidate_family_counts_from_runtime": reported_family_counts,
            "frozen_baseline_prediction_sha256": EXPECTED_BASELINE_PREDICTION_SHA256,
            "prediction_sha256_matches_frozen_baseline": (
                metrics["prediction_sha256"] == EXPECTED_BASELINE_PREDICTION_SHA256
            ),
            "previous_covered_family_diagnostic": {
                "candidate_outputs": previous_metrics["candidate_outputs"],
                "unique_unselected_exact_examples": previous_metrics["unique_unselected_exact_examples"],
                "evidence_sha256": sha256(Path(__file__).with_name("ARC2_current_main_candidate_family_opportunity_20261028.json").read_bytes()),
            },
            "incremental_candidate_source": "ARC generic simple-transform candidate field; other candidate_predictions sources already covered",
            "metrics": metrics,
            "fallback_counted_correct": False,
            "candidate_grids_passed_back_to_solver": False,
            "task_ids_or_raw_grids_or_per_example_labels_persisted": False,
            "hidden_or_evaluation_solutions_read": False,
            "production_source_changed": False,
            "official_submission_performed": False,
            "official_submission_id": 57682971,
            "official_status": "SubmissionStatus.COMPLETE",
            "official_score": None,
            "score_state": "SCORE_UNOBSERVED",
            "limitations": [
                "Candidate exactness is a public challenge diagnostic; it is not an official score.",
                "Per-task candidate grids and labels existed only in process memory and temporary pipes; only aggregate family counts were saved.",
                "Any candidate family selected for a solver change still requires matched public-training LOO before adoption.",
            ],
        }
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
