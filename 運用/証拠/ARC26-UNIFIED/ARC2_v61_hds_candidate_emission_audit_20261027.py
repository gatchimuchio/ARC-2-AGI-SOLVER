"""Read-only HDS stage instrumentation on the frozen v61 challenge inputs.

The runner records only aggregate family-fit, query-emission, HOLD, and
reproduction metrics. It never loads solutions or persists task IDs or grids.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import zipfile


ROOT = Path(__file__).resolve().parents[3]
BUNDLE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v61-kaggle-staging-20261026/bundle.zip"
CHALLENGES = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
OUTPUT = ROOT / "出力/検証/ARC2-v61-hds-candidate-emission-audit-20261027.json"
EXPECTED_OUTPUT_SHA256 = "827bccfc1cf51e2fc87d687ba51e1375899650a530ec00e7a20eb1f71eb2dd18"
EXPECTED_WRAPPER_SHA256 = "c20102c4e9a01e833ca8f9e2778b5306333c50c065d9aebe7cbeaf574e74418d"
EXPECTED_HDS_SHA256 = "8cc1456edfab1b84478fcc1b8f82973481709d85a45532b5181d0e79655362a3"
MAX_WORKERS = 3
TASK_TIMEOUT_SECONDS = 90


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def instrument_wrapper(source: str) -> str:
    worker_anchor = "def _worker(課題: dict[str, list[dict[str, Any]]]) -> int:\n"
    stage_helper = '''def _aggregate_hds_stage(結果, 課題):
    family_fit = {}
    for 記録 in 結果.get("families", []):
        if not isinstance(記録, dict) or not isinstance(記録.get("境界"), str):
            continue
        名 = 記録["境界"]
        項目 = family_fit.setdefault(名, {
            "task_records": 0, "fit_eligible": 0,
            "equality_admitted": 0, "jointly_admitted": 0,
            "states": Counter(),
        })
        適合 = 記録.get("採用可") is True
        同値 = 記録.get("同値採用") is True
        項目["task_records"] += 1
        項目["fit_eligible"] += int(適合)
        項目["equality_admitted"] += int(同値)
        項目["jointly_admitted"] += int(適合 and 同値)
        if isinstance(記録.get("状態"), str):
            項目["states"][記録["状態"]] += 1

    emissions = {}
    emitted_rows = 0
    rows_with_multiple_distinct_candidates = 0
    result_rows = 結果.get("results", [])
    for 位置, 行 in enumerate(result_rows):
        if not isinstance(行, dict):
            continue
        候補群 = 行.get("candidate_predictions", [])
        if not isinstance(候補群, list):
            continue
        distinct = set()
        row_families = set()
        row_emitted = False
        for 候補 in 候補群:
            if not isinstance(候補, dict):
                continue
            名, 格子 = 候補.get("family"), 候補.get("answer")
            if not isinstance(名, str) or not 格子か(格子):
                continue
            key = tuple(tuple(行) for 行 in 格子)
            distinct.add(key)
            row_emitted = True
            row_families.add(名)
            item = emissions.setdefault(名, {
                "emission_records": 0, "examples_with_emission": 0,
                "nonidentity_emissions": 0, "identity_emissions": 0,
            })
            item["emission_records"] += 1
            if 位置 < len(課題["test"]) and 格子 != 課題["test"][位置]["input"]:
                item["nonidentity_emissions"] += 1
            else:
                item["identity_emissions"] += 1
        if row_emitted:
            emitted_rows += 1
            for 名 in row_families:
                emissions[名]["examples_with_emission"] += 1
            if len(distinct) > 1:
                rows_with_multiple_distinct_candidates += 1

    status_counts = Counter()
    hold_reasons = Counter()
    answered = 0
    for 行 in result_rows:
        if not isinstance(行, dict):
            continue
        status = 行.get("status")
        if isinstance(status, str):
            status_counts[status] += 1
        if 格子か(行.get("answer")):
            answered += 1
        else:
            for 理由 in 行.get("reasons", []):
                if isinstance(理由, str):
                    hold_reasons[理由] += 1

    joint = sum(item["jointly_admitted"] for item in family_fit.values())
    query_count = len(課題.get("test", []))
    return {
        "family_fit_records": {
            名: {
                **{k: v for k, v in item.items() if k != "states"},
                "states": dict(sorted(item["states"].items())),
            }
            for 名, item in sorted(family_fit.items())
        },
        "jointly_admitted_family_task_records": joint,
        "admitted_family_query_opportunities": joint * query_count,
        "emissions_by_family": dict(sorted(emissions.items())),
        "hds_candidate_emission_records": sum(
            item["emission_records"] for item in emissions.values()
        ),
        "examples_with_hds_candidate_emission": emitted_rows,
        "examples_with_multiple_distinct_hds_candidates": rows_with_multiple_distinct_candidates,
        "hds_answered_examples": answered,
        "hds_hold_examples": max(0, len(result_rows) - answered),
        "hds_result_status_counts": dict(sorted(status_counts.items())),
        "hds_hold_reason_counts": dict(sorted(hold_reasons.items())),
        "observation_request_counts": 結果.get("observation_request_counts", {}),
    }

'''
    if source.count(worker_anchor) != 1:
        raise RuntimeError("unexpected worker insertion anchor")
    source = source.replace(worker_anchor, stage_helper + worker_anchor, 1)

    call_anchor = '        # This partial-fit family is allowed to propose only attempt 2. It never\n'
    call_instrumentation = '''        診断HDS段階 = _aggregate_hds_stage(結果, 課題) if 観測診断 else None
        # This partial-fit family is allowed to propose only attempt 2. It never
'''
    if source.count(call_anchor) != 1:
        raise RuntimeError("unexpected post-HDS insertion anchor")
    source = source.replace(call_anchor, call_instrumentation, 1)

    output_anchor = '        print(json.dumps(公開結果, ensure_ascii=False))\n'
    output_instrumentation = '''        if 観測診断:
            公開結果["aggregate_diagnostics"]["hds_stage"] = 診断HDS段階
        print(json.dumps(公開結果, ensure_ascii=False))
'''
    if source.count(output_anchor) != 1:
        raise RuntimeError("unexpected worker output insertion anchor")
    return source.replace(output_anchor, output_instrumentation, 1)


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    started = time.monotonic()
    bundle_bytes = BUNDLE.read_bytes()
    challenge_bytes = CHALLENGES.read_bytes()
    challenge_map = json.loads(challenge_bytes.decode("utf-8"))
    if not isinstance(challenge_map, dict) or not challenge_map:
        raise ValueError("challenge input must be a nonempty task object")
    if any(
        not isinstance(task, dict)
        or set(task) != {"train", "test"}
        or any(not isinstance(pair, dict) or set(pair) != {"input"} for pair in task["test"])
        for task in challenge_map.values()
    ):
        raise ValueError("only input-only test challenge pairs are permitted")

    with zipfile.ZipFile(BUNDLE) as archive:
        manifest_bytes = archive.read("__arc2_bundle_manifest__.json")
        manifest = json.loads(manifest_bytes)
        expected = {row["path"]: row for row in manifest["files"]}
        if set(archive.namelist()[1:]) != set(expected):
            raise ValueError("bundle manifest does not cover exact members")
        wrapper_bytes = archive.read("接続/ARC2/Kaggle提出.py")
        hds_bytes = archive.read("接続/ARC2/HDS接続.py")
        if sha256(wrapper_bytes) != EXPECTED_WRAPPER_SHA256:
            raise ValueError("v61 wrapper hash mismatch")
        if sha256(hds_bytes) != EXPECTED_HDS_SHA256:
            raise ValueError("v61 HDS source hash mismatch")

    with tempfile.TemporaryDirectory(prefix="arc2-v61-hds-emission-") as temp_name:
        temp_root = Path(temp_name)
        payload_root = temp_root / "payload"
        payload_root.mkdir()
        with zipfile.ZipFile(BUNDLE) as archive:
            for member, row in expected.items():
                relative = PurePosixPath(member)
                if relative.is_absolute() or ".." in relative.parts or "\\" in member:
                    raise ValueError(f"unsafe bundle member: {member}")
                raw = archive.read(member)
                if len(raw) != row["size"] or sha256(raw) != row["sha256"]:
                    raise ValueError(f"bundle member integrity error: {member}")
                target = payload_root.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)

        launcher = temp_root / "diagnostic_Kaggle提出.py"
        launcher.write_text(
            instrument_wrapper(wrapper_bytes.decode("utf-8")),
            encoding="utf-8",
            newline="\n",
        )
        instrumented_sha = sha256(launcher.read_bytes())
        env = os.environ.copy()
        for name in list(env):
            if name.startswith("KAGGLE_") or name in {
                "ARC2_AGGREGATE_DIAGNOSTICS", "ARC2_PAYLOAD_ROOT",
            }:
                env.pop(name, None)
        env.update({
            "ARC2_PAYLOAD_ROOT": str(payload_root),
            "ARC2_AGGREGATE_DIAGNOSTICS": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        })

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
            raise RuntimeError(f"v61 payload preflight failed: {preflight.stdout[-300:]!r}")

        helper_spec = __import__("importlib.util", fromlist=["spec_from_file_location"])
        spec = helper_spec.spec_from_file_location("arc2_v61_emission_wrapper", launcher)
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot import instrumented v61 wrapper helpers")
        wrapper = helper_spec.module_from_spec(spec)
        spec.loader.exec_module(wrapper)
        validated = wrapper.入力検査(challenge_map)
        task_items = list(validated.items())

        def run_task(item: tuple[str, dict]) -> tuple[str, dict]:
            task_id, task = item
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
            if run.returncode != 0 and "error" not in result:
                result = {"error": "worker_exit"}
            return task_id, result if isinstance(result, dict) else {"error": "invalid_worker_result"}

        results: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(run_task, item) for item in task_items]
            for future in as_completed(futures):
                task_id, result = future.result()
                results[task_id] = result
                if len(results) % 40 == 0 or len(results) == len(task_items):
                    print(json.dumps({"completed_tasks": len(results), "total_tasks": len(task_items)}), flush=True)

        family_fit = defaultdict(lambda: {
            "task_records": 0, "fit_eligible": 0,
            "equality_admitted": 0, "jointly_admitted": 0,
            "states": Counter(),
        })
        emissions = defaultdict(lambda: {
            "emission_records": 0, "examples_with_emission": 0,
            "nonidentity_emissions": 0, "identity_emissions": 0,
        })
        worker_errors = Counter()
        hds_status = Counter()
        hds_hold_reasons = Counter()
        request_counts = Counter()
        hds_answered = hds_holds = emitted_examples = multi_candidate_examples = 0
        total_examples = fallback_rows = admitted_query_opportunities = 0
        submission = {}
        for task_id, task in task_items:
            result = results[task_id]
            if result.get("error"):
                worker_errors[str(result["error"])] += 1
            diagnostic = result.get("aggregate_diagnostics", {}).get("hds_stage", {})
            for name, record in diagnostic.get("family_fit_records", {}).items():
                agg = family_fit[name]
                for key in ("task_records", "fit_eligible", "equality_admitted", "jointly_admitted"):
                    agg[key] += record.get(key, 0)
                agg["states"].update(record.get("states", {}))
            admitted_query_opportunities += diagnostic.get("admitted_family_query_opportunities", 0)
            for name, record in diagnostic.get("emissions_by_family", {}).items():
                agg = emissions[name]
                for key in ("emission_records", "examples_with_emission", "nonidentity_emissions", "identity_emissions"):
                    agg[key] += record.get(key, 0)
            hds_answered += diagnostic.get("hds_answered_examples", 0)
            hds_holds += diagnostic.get("hds_hold_examples", 0)
            emitted_examples += diagnostic.get("examples_with_hds_candidate_emission", 0)
            multi_candidate_examples += diagnostic.get("examples_with_multiple_distinct_hds_candidates", 0)
            hds_status.update(diagnostic.get("hds_result_status_counts", {}))
            hds_hold_reasons.update(diagnostic.get("hds_hold_reason_counts", {}))
            request_counts.update(diagnostic.get("observation_request_counts", {}))
            rows = result.get("results", [])
            total_examples += len(task["test"])
            outputs, holds = wrapper.結果を候補へ(task_id, task, result)
            fallback_rows += len(holds)
            submission[task_id] = outputs

        wrapper.提出検査(validated, submission)
        submission_bytes = (json.dumps(submission, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        submission_sha = sha256(submission_bytes)
        unchanged = submission_sha == EXPECTED_OUTPUT_SHA256
        if not unchanged:
            print(json.dumps({"warning": "submission output differs from frozen v61 output", "sha256": submission_sha}), flush=True)

    joint = sum(item["jointly_admitted"] for item in family_fit.values())
    summary = {
        "schema": "arc2-v61-hds-candidate-emission-audit-v1",
        "status": "COMPLETE" if not worker_errors else "COMPLETE_WITH_WORKER_ERRORS",
        "audit_script_sha256": sha256(Path(__file__).read_bytes()),
        "bundle_sha256": sha256(bundle_bytes),
        "bundle_manifest_sha256": sha256(manifest_bytes),
        "wrapper_sha256": sha256(wrapper_bytes),
        "instrumented_wrapper_sha256": instrumented_sha,
        "hds_sha256": sha256(hds_bytes),
        "challenge_sha256": sha256(challenge_bytes),
        "challenge_file": "arc-agi_test_challenges.json",
        "challenge_tasks": len(task_items),
        "test_examples": total_examples,
        "max_workers": MAX_WORKERS,
        "task_timeout_seconds": TASK_TIMEOUT_SECONDS,
        "worker_errors": dict(sorted(worker_errors.items())),
        "fallback_rows": fallback_rows,
        "hds_answered_examples": hds_answered,
        "hds_hold_examples": hds_holds,
        "hds_result_status_counts": dict(sorted(hds_status.items())),
        "hds_hold_reason_counts": dict(sorted(hds_hold_reasons.items())),
        "observation_request_counts": dict(sorted(request_counts.items())),
        "family_count": len(family_fit),
        "family_fit_aggregate": {
            name: {
                **{key: value for key, value in record.items() if key != "states"},
                "states": dict(sorted(record["states"].items())),
            }
            for name, record in sorted(family_fit.items())
        },
        "jointly_admitted_family_task_records": joint,
        "admitted_family_query_opportunities": admitted_query_opportunities,
        "hds_candidate_emission_records": sum(item["emission_records"] for item in emissions.values()),
        "examples_with_hds_candidate_emission": emitted_examples,
        "examples_with_multiple_distinct_hds_candidates": multi_candidate_examples,
        "emissions_by_family": {name: dict(record) for name, record in sorted(emissions.items())},
        "local_submission_sha256": submission_sha,
        "matches_frozen_v61_submission": unchanged,
        "runtime_seconds": round(time.monotonic() - started, 3),
        "solutions_file_opened": False,
        "hidden_or_evaluation_solutions_read": False,
        "task_id_used_for_runtime_answer_selection": False,
        "task_ids_or_raw_grids_persisted": False,
        "official_score": None,
        "official_submission_performed": False,
    }
    output_bytes = (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with OUTPUT.open("xb") as target:
        target.write(output_bytes)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
