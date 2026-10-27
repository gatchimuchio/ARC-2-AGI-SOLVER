from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import zipfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BUNDLE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v61-kaggle-staging-20261026/bundle.zip"
CHALLENGES = ROOT / "入力/Kaggle/arc-agi_training_challenges.json"
SOLUTIONS = ROOT / "入力/Kaggle/arc-agi_training_solutions.json"
OUTPUT = HERE / "summary.json"
MAX_WORKERS = 3
TASK_TIMEOUT_SECONDS = 90


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def grid_key(grid: list[list[int]]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(row) for row in grid)


def patch_wrapper(source: str) -> str:
    row_anchor = '            if 観測診断 and 位置 < len(課題["test"]):\n'
    row_instrumentation = '''            if 観測診断 and 位置 < len(課題["test"]):
                診断候補記録群 = []
                def 候補を記録(family, answer):
                    if isinstance(family, str) and 格子か(answer) and answer != 第一候補:
                        診断候補記録群.append({
                            "family": family,
                            "answer": deepcopy(answer),
                        })
                for 記録 in 行.get("candidate_predictions", []):
                    if isinstance(記録, dict):
                        候補を記録(記録.get("family"), 記録.get("answer"))
                候補を記録("simple_transform_unique", 行.get("simple_transform_candidate"))
                候補対診断 = _完全候補対(行.get("candidate_attempts"))
                if 候補対診断:
                    候補対family = 行.get("candidate_attempt_family") or "admitted_candidate_attempt_pair"
                    for 格子診断 in 候補対診断:
                        候補を記録(候補対family, 格子診断)
                候補を記録("wrapper_selected_attempt2", 第二候補)
                公開行群[-1]["diagnostic_candidate_families"] = 診断候補記録群
            if 観測診断 and 位置 < len(課題["test"]):
'''
    if source.count(row_anchor) != 1:
        raise RuntimeError("unexpected candidate diagnostic insertion anchor")
    source = source.replace(row_anchor, row_instrumentation, 1)

    output_anchor = '        print(json.dumps(公開結果, ensure_ascii=False))\n'
    output_instrumentation = '''        if 観測診断:
            公開結果["diagnostic_family_fit_records"] = [
                {
                    key: 記録[key]
                    for key in (
                        "境界", "事前観測数", "現在観測数", "採用可",
                        "同値採用", "状態", "隔離数",
                    )
                    if key in 記録
                }
                for 記録 in 結果.get("families", [])
                if isinstance(記録, dict)
            ]
        print(json.dumps(公開結果, ensure_ascii=False))
'''
    if source.count(output_anchor) != 1:
        raise RuntimeError("unexpected family fit diagnostic insertion anchor")
    return source.replace(output_anchor, output_instrumentation, 1)


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    started = time.monotonic()
    bundle_bytes = BUNDLE.read_bytes()
    challenge_bytes = CHALLENGES.read_bytes()
    challenge_sha = sha256(challenge_bytes)
    bundle_sha = sha256(bundle_bytes)

    with zipfile.ZipFile(BUNDLE) as archive:
        manifest_bytes = archive.read("__arc2_bundle_manifest__.json")
        manifest = json.loads(manifest_bytes)
        payload_manifest = manifest["files"]
        payload_source_ids = set()
        template_member = "接続/ARC2/テンプレート充填教材.json"
        template_ref = json.loads(archive.read(template_member))
        if template_ref.get("分割") != "training":
            raise RuntimeError("v61 prior template source is not training-only")
        payload_source_ids = {
            entry["課題ID"] for entry in template_ref.get("教材", [])
        }
        exact_wrapper = archive.read("接続/ARC2/Kaggle提出.py")
        exact_hds = archive.read("接続/ARC2/HDS接続.py")
        if sha256(exact_wrapper) != "c20102c4e9a01e833ca8f9e2778b5306333c50c065d9aebe7cbeaf574e74418d":
            raise RuntimeError("v61 wrapper source hash mismatch")
        if sha256(exact_hds) != "8cc1456edfab1b84478fcc1b8f82973481709d85a45532b5181d0e79655362a3":
            raise RuntimeError("v61 HDS source hash mismatch")

    challenge_map_raw = json.loads(challenge_bytes.decode("utf-8"))
    tasks = list(challenge_map_raw.items())
    eligible_task_ids = {
        task_id for task_id, _task in tasks if task_id not in payload_source_ids
    }
    if not eligible_task_ids:
        raise RuntimeError("no eligible public training tasks")

    with tempfile.TemporaryDirectory(prefix="arc2-v61-candidate-coverage-") as temp_name:
        temp_root = Path(temp_name)
        payload_root = temp_root / "payload"
        payload_root.mkdir()
        with zipfile.ZipFile(BUNDLE) as archive:
            for entry in payload_manifest:
                member = entry["path"]
                relative = PurePosixPath(member)
                if relative.is_absolute() or ".." in relative.parts:
                    raise RuntimeError(f"unsafe payload member: {member}")
                raw = archive.read(member)
                if sha256(raw) != entry["sha256"]:
                    raise RuntimeError(f"payload member digest mismatch: {member}")
                destination = payload_root.joinpath(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(raw)

        exact_text = exact_wrapper.decode("utf-8")
        instrumented_text = patch_wrapper(exact_text)
        launcher = temp_root / "diagnostic_Kaggle提出.py"
        launcher.write_text(instrumented_text, encoding="utf-8", newline="\n")
        instrumented_sha = sha256(launcher.read_bytes())

        env = os.environ.copy()
        for name in list(env):
            if name.startswith("KAGGLE_") or name in {
                "ARC2_AGGREGATE_DIAGNOSTICS", "ARC2_PAYLOAD_ROOT",
            }:
                env.pop(name, None)
        env["ARC2_PAYLOAD_ROOT"] = str(payload_root)
        env["ARC2_AGGREGATE_DIAGNOSTICS"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        preflight = subprocess.run(
            [sys.executable, str(launcher), "--preflight"],
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=120,
            env=env,
            check=False,
        )
        if preflight.returncode != 0:
            raise RuntimeError(
                f"v61 payload preflight failed: {preflight.stdout[-300:]!r}"
            )

        spec = importlib.util.spec_from_file_location("arc2_v61_diag_wrapper", launcher)
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load instrumented v61 wrapper helpers")
        wrapper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wrapper)
        challenge_map = wrapper.入力検査(challenge_map_raw)
        task_items = [(task_id, challenge_map[task_id]) for task_id, _ in tasks]

        def run_task(item: tuple[str, dict]) -> tuple[str, dict]:
            task_id, task = item
            if any(set(test_pair) != {"input"} for test_pair in task["test"]):
                raise RuntimeError("worker test inputs contain a non-input field")
            try:
                run = subprocess.run(
                    [sys.executable, str(launcher), "--worker"],
                    input=json.dumps(task, ensure_ascii=False),
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    timeout=TASK_TIMEOUT_SECONDS,
                    env=env,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return task_id, {"error": "task_wall_timeout"}
            try:
                result = json.loads(run.stdout)
            except json.JSONDecodeError:
                result = {"error": "worker_invalid_json"}
            if run.returncode != 0 and not isinstance(result, dict):
                result = {"error": "worker_exit"}
            return task_id, result if isinstance(result, dict) else {"error": "invalid_worker_result"}

        print(
            json.dumps({
                "state": "prediction_run_started",
                "tasks": len(task_items),
                "eligible_tasks": len(eligible_task_ids),
                "workers": MAX_WORKERS,
            }),
            flush=True,
        )
        worker_by_id = {}
        completed = 0
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(run_task, item) for item in task_items]
            for future in as_completed(futures):
                task_id, result = future.result()
                worker_by_id[task_id] = result
                completed += 1
                if completed % 50 == 0 or completed == len(task_items):
                    print(
                        json.dumps({
                            "state": "predictions_in_progress",
                            "completed": completed,
                            "total": len(task_items),
                        }),
                        flush=True,
                    )

        submission: dict[str, list[dict]] = {}
        raw_prediction_material = []
        worker_errors = Counter()
        hds_fit_aggregate: dict[str, dict] = defaultdict(
            lambda: {
                "task_records": 0,
                "fit_eligible": 0,
                "equality_admitted": 0,
                "jointly_admitted": 0,
                "state_counts": Counter(),
            }
        )

        for task_id, task in task_items:
            result = worker_by_id[task_id]
            if result.get("error"):
                worker_errors[str(result["error"])] += 1
            rows = result.get("results")
            if not isinstance(rows, list) or len(rows) != len(task["test"]):
                worker_errors["result_count_mismatch"] += 1
            outputs, _holds = wrapper.結果を候補へ(task_id, task, result)
            submission[task_id] = outputs

            if task_id not in eligible_task_ids:
                continue
            diagnostic_rows = result.get("results", [])
            for test_index, test_input in enumerate(task["test"]):
                row = diagnostic_rows[test_index] if test_index < len(diagnostic_rows) and isinstance(diagnostic_rows[test_index], dict) else {}
                candidates = row.get("diagnostic_candidate_families", [])
                if not isinstance(candidates, list):
                    candidates = []
                family_predictions = []
                seen = set()
                for candidate in candidates:
                    if not isinstance(candidate, dict):
                        continue
                    family = candidate.get("family")
                    answer = candidate.get("answer")
                    if not isinstance(family, str) or not isinstance(answer, list):
                        continue
                    try:
                        key = grid_key(answer)
                    except TypeError:
                        continue
                    if key in seen:
                        continue
                    seen.add(key)
                    family_predictions.append({"family": family, "answer": answer})
                raw_prediction_material.append({
                    "task": task_id,
                    "test_index": test_index,
                    "primary": outputs[test_index]["attempt_1"],
                    "secondary": outputs[test_index]["attempt_2"],
                    "solver_answer_missing": row.get("answer") is None,
                    "candidate_families": family_predictions,
                })

            for fit_record in result.get("diagnostic_family_fit_records", []):
                if not isinstance(fit_record, dict):
                    continue
                family = fit_record.get("境界")
                if not isinstance(family, str):
                    continue
                agg = hds_fit_aggregate[family]
                agg["task_records"] += 1
                agg["fit_eligible"] += int(fit_record.get("採用可") is True)
                agg["equality_admitted"] += int(fit_record.get("同値採用") is True)
                agg["jointly_admitted"] += int(
                    fit_record.get("採用可") is True
                    and fit_record.get("同値採用") is True
                )
                if isinstance(fit_record.get("状態"), str):
                    agg["state_counts"][fit_record["状態"]] += 1

        wrapper.提出検査(challenge_map, submission)
        submission_bytes = (
            json.dumps(submission, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        task_order_sha = sha256(
            json.dumps(
                [task_id for task_id, _ in task_items if task_id in eligible_task_ids],
                separators=(",", ":"),
            ).encode()
        )
        frozen_material_bytes = json.dumps(
            {
                "task_order_sha256": task_order_sha,
                "worker_errors": dict(sorted(worker_errors.items())),
                "predictions": raw_prediction_material,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        frozen_sha = sha256(frozen_material_bytes)
        predictions_frozen_at = datetime.now(timezone.utc).isoformat()

        # Public training targets are opened only after all input-only worker outputs
        # and their digest have been frozen. Workers never receive this path or data.
        solution_bytes = SOLUTIONS.read_bytes()
        solution_sha = sha256(solution_bytes)
        solutions = json.loads(solution_bytes.decode("utf-8"))
        score_started = time.monotonic()

        family_metrics: dict[str, dict] = defaultdict(
            lambda: {
                "candidate_examples": 0,
                "oracle_exact_examples": 0,
                "exact_on_hds_hold_examples": 0,
                "exact_when_primary_wrong_examples": 0,
                "deterministic_replacement_rows": 0,
                "deterministic_gains_vs_attempt2": 0,
                "deterministic_regressions_vs_attempt2": 0,
            }
        )
        baseline_examples = baseline_attempt1 = baseline_attempt2_only = 0
        total_examples = 0
        solver_hold_examples = 0
        solved_task_count = 0
        example_task_rows: dict[str, list[dict]] = defaultdict(list)

        for record in raw_prediction_material:
            task_id = record["task"]
            index = record["test_index"]
            targets = solutions.get(task_id)
            if not isinstance(targets, list) or index >= len(targets):
                raise RuntimeError("public training solution alignment failed")
            target = targets[index]
            primary = record["primary"]
            secondary = record["secondary"]
            p1 = primary == target
            p2 = secondary == target
            base = p1 or p2
            total_examples += 1
            baseline_examples += int(base)
            baseline_attempt1 += int(p1)
            baseline_attempt2_only += int((not p1) and p2)
            solver_hold_examples += int(record["solver_answer_missing"])

            grouped: dict[str, set[tuple[tuple[int, ...], ...]]] = defaultdict(set)
            grid_by_key = {}
            for candidate in record["candidate_families"]:
                family = candidate["family"]
                answer = candidate["answer"]
                key = grid_key(answer)
                grouped[family].add(key)
                grid_by_key[key] = answer
            for family, keys in grouped.items():
                metric = family_metrics[family]
                metric["candidate_examples"] += 1
                oracle_exact = any(tuple(tuple(row) for row in target) == key for key in keys)
                metric["oracle_exact_examples"] += int(oracle_exact)
                metric["exact_on_hds_hold_examples"] += int(
                    oracle_exact and record["solver_answer_missing"]
                )
                metric["exact_when_primary_wrong_examples"] += int(oracle_exact and not p1)
                if len(keys) == 1:
                    candidate_grid = grid_by_key[next(iter(keys))]
                    metric["deterministic_replacement_rows"] += 1
                    metric["deterministic_gains_vs_attempt2"] += int(
                        candidate_grid == target and not p2
                    )
                    metric["deterministic_regressions_vs_attempt2"] += int(
                        candidate_grid != target and p2
                    )
            example_task_rows[task_id].append({
                "base_correct": base,
                "primary_correct": p1,
                "secondary_correct": p2,
            })

        if total_examples == 0:
            raise RuntimeError("no scored public training examples")
        solved_task_count = sum(
            all(row["base_correct"] for row in rows)
            for rows in example_task_rows.values()
        )
        for family, agg in hds_fit_aggregate.items():
            agg["state_counts"] = dict(sorted(agg["state_counts"].items()))

        summary = {
            "schema": "arc2-v61-public-training-candidate-coverage-v1",
            "track": "ARC2",
            "status": "COMPLETE",
            "started_at_utc": datetime.fromtimestamp(
                time.time() - (time.monotonic() - started), timezone.utc
            ).isoformat(),
            "predictions_frozen_at_utc": predictions_frozen_at,
            "scored_at_utc": datetime.now(timezone.utc).isoformat(),
            "scope": {
                "dataset": "public ARC2 training challenges and training solutions",
                "challenge_path": str(CHALLENGES.relative_to(ROOT)),
                "eligible_tasks": len(eligible_task_ids),
                "excluded_static_prior_tasks": len(task_items) - len(eligible_task_ids),
                "excluded_static_prior_task_ids_persisted": False,
                "test_examples": total_examples,
                "max_workers": MAX_WORKERS,
                "task_timeout_seconds": TASK_TIMEOUT_SECONDS,
                "runtime_received_test_outputs": False,
                "solutions_opened_after_prediction_freeze": True,
                "hidden_or_evaluation_solutions_read": False,
                "task_id_used_for_runtime_answer_selection": False,
            },
            "provenance": {
                "repo_head": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                ).strip(),
                "bundle_sha256": bundle_sha,
                "bundle_manifest_sha256": sha256(manifest_bytes),
                "payload_member_count_verified": len(payload_manifest),
                "v61_wrapper_sha256": sha256(exact_wrapper),
                "v61_hds_sha256": sha256(exact_hds),
                "instrumented_wrapper_sha256": instrumented_sha,
                "challenge_sha256": challenge_sha,
                "solutions_sha256": solution_sha,
                "probe_script_sha256": sha256(Path(__file__).read_bytes()),
                "frozen_predictions_sha256": frozen_sha,
                "task_order_sha256": task_order_sha,
            },
            "runtime": {
                "worker_errors": dict(sorted(worker_errors.items())),
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "scoring_seconds": round(time.monotonic() - score_started, 3),
                "submission_format_valid": True,
                "submission_sha256": sha256(submission_bytes),
                "raw_candidate_grids_persisted": False,
            },
            "baseline": {
                "exact_examples": baseline_examples,
                "example_count": total_examples,
                "exact_tasks": solved_task_count,
                "task_count": len(example_task_rows),
                "attempt1_exact_examples": baseline_attempt1,
                "attempt2_only_exact_examples": baseline_attempt2_only,
                "solver_hold_examples": solver_hold_examples,
            },
            "hds_family_fit_aggregate": dict(sorted(hds_fit_aggregate.items())),
            "candidate_family_metrics": {
                name: family_metrics[name]
                for name in sorted(
                    family_metrics,
                    key=lambda n: (
                        -family_metrics[n]["deterministic_gains_vs_attempt2"],
                        -family_metrics[n]["oracle_exact_examples"],
                        n,
                    ),
                )
            },
            "interpretation": {
                "candidate_coverage_is_not_adoption": True,
                "deterministic_policy_definition": (
                    "For rows with exactly one distinct candidate from a family, "
                    "replace attempt_2 with that candidate and compare against the "
                    "frozen baseline; rows with multiple distinct candidates are "
                    "reported only as oracle coverage."
                ),
                "official_score": None,
                "production_source_changed": False,
                "official_submission_performed": False,
            },
        }
        OUTPUT.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(json.dumps({
            "status": "COMPLETE",
            "tasks": len(example_task_rows),
            "examples": total_examples,
            "baseline_exact": baseline_examples,
            "baseline_tasks_exact": solved_task_count,
            "worker_errors": dict(sorted(worker_errors.items())),
            "frozen_prediction_sha256": frozen_sha,
            "solutions_sha256": solution_sha,
            "summary_path": str(OUTPUT.relative_to(ROOT)),
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
