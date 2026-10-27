from __future__ import annotations

from collections import Counter
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


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BUNDLE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v61-kaggle-staging-20261026/bundle.zip"
CHALLENGES = ROOT / "入力/Kaggle/arc-agi_training_challenges.json"
OUTPUT = HERE / "summary-observation-request-categories.json"
EXPECTED_BUNDLE_SHA256 = "06f7e19da4f1b6fc0059a4aef03833fd9074bc725204a3f9c5c1b33523e0fbee"
EXPECTED_WRAPPER_SHA256 = "c20102c4e9a01e833ca8f9e2778b5306333c50c065d9aebe7cbeaf574e74418d"
EXPECTED_HDS_SHA256 = "8cc1456edfab1b84478fcc1b8f82973481709d85a45532b5181d0e79655362a3"
EXPECTED_PREVIOUS_SUBMISSION_SHA256 = "b8159ef2d67e458fcac637ff090958a78f6e773b5eef863d6b2861ab9c176019"
CHUNK_SIZE = 100


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    started = time.monotonic()
    bundle_bytes = BUNDLE.read_bytes()
    challenge_bytes = CHALLENGES.read_bytes()
    bundle_sha = sha256(bundle_bytes)
    challenge_sha = sha256(challenge_bytes)
    if bundle_sha != EXPECTED_BUNDLE_SHA256:
        raise RuntimeError("v61 bundle digest mismatch")

    with zipfile.ZipFile(BUNDLE) as archive:
        manifest_bytes = archive.read("__arc2_bundle_manifest__.json")
        manifest = json.loads(manifest_bytes)
        payload_manifest = manifest["files"]
        wrapper_bytes = archive.read("接続/ARC2/Kaggle提出.py")
        hds_bytes = archive.read("接続/ARC2/HDS接続.py")
        template_ref = json.loads(archive.read("接続/ARC2/テンプレート充填教材.json"))
        if sha256(wrapper_bytes) != EXPECTED_WRAPPER_SHA256:
            raise RuntimeError("v61 wrapper digest mismatch")
        if sha256(hds_bytes) != EXPECTED_HDS_SHA256:
            raise RuntimeError("v61 HDS digest mismatch")
        if template_ref.get("分割") != "training":
            raise RuntimeError("v61 static prior source is not training-only")
        prior_source_ids = {
            entry["課題ID"] for entry in template_ref.get("教材", [])
        }

    all_tasks = json.loads(challenge_bytes.decode("utf-8"))
    if not isinstance(all_tasks, dict):
        raise RuntimeError("training challenge root is not a mapping")
    task_items = list(all_tasks.items())
    prior_source_task_count = sum(task_id in prior_source_ids for task_id, _ in task_items)
    test_examples = sum(len(task["test"]) for task in all_tasks.values())
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()

    request_counts: Counter[str] = Counter()
    fallback_reasons: Counter[str] = Counter()
    output_map: dict[str, list[dict]] = {}
    chunk_hashes: list[str] = []
    completed_tasks = 0
    fallback_examples = 0
    runner_seconds = 0.0

    with tempfile.TemporaryDirectory(prefix="arc2-v61-observation-request-audit-") as temp_name:
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

        runner = temp_root / "Kaggle提出.py"
        runner.write_bytes(wrapper_bytes)
        env = os.environ.copy()
        for name in list(env):
            if name.startswith("KAGGLE_") or name in {
                "ARC2_AGGREGATE_DIAGNOSTICS", "ARC2_PAYLOAD_ROOT", "ARC2_WORKER_LAUNCHER",
            }:
                env.pop(name, None)
        env["ARC2_PAYLOAD_ROOT"] = str(payload_root)
        env["ARC2_WORKER_LAUNCHER"] = str(runner)
        env["ARC2_SOURCE_COMMIT"] = source_commit
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        chunks = [
            task_items[start:start + CHUNK_SIZE]
            for start in range(0, len(task_items), CHUNK_SIZE)
        ]
        for chunk_number, chunk in enumerate(chunks, start=1):
            challenge_path = temp_root / f"training-challenges-{chunk_number:03d}.json"
            challenge_path.write_text(
                json.dumps(dict(chunk), ensure_ascii=False) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            output_dir = temp_root / f"output-{chunk_number:03d}"
            command = [
                sys.executable, str(runner), "--aggregate-diagnostics",
                "--challenges", str(challenge_path), "--output-dir", str(output_dir),
            ]
            run = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                encoding="utf-8",
                capture_output=True,
                env=env,
                check=False,
            )
            if run.returncode != 0:
                raise RuntimeError(
                    f"v61 chunk {chunk_number}/{len(chunks)} failed; returncode={run.returncode}"
                )
            audit_path = output_dir / "submission_audit.json"
            submission_path = output_dir / "submission.json"
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            submission_bytes = submission_path.read_bytes()
            if sha256(submission_bytes) != audit.get("submission_sha256"):
                raise RuntimeError(f"chunk {chunk_number} submission digest mismatch")
            chunk_submission = json.loads(submission_bytes.decode("utf-8"))
            if list(chunk_submission) != [task_id for task_id, _ in chunk]:
                raise RuntimeError(f"chunk {chunk_number} task order mismatch")
            output_map.update(chunk_submission)
            chunk_hashes.append(sha256(submission_bytes))
            fallback_examples += int(audit.get("fallback_count", 0))
            for reason, count in audit.get("solver_hold_reason_counts", {}).items():
                if isinstance(reason, str) and type(count) is int and count >= 0:
                    fallback_reasons[reason] += count
            diagnostics = audit.get("aggregate_diagnostics", {})
            observed_counts = diagnostics.get("observation_request_counts", {})
            if not isinstance(observed_counts, dict):
                raise RuntimeError(f"chunk {chunk_number} lacks observation-request aggregates")
            for category, count in observed_counts.items():
                if isinstance(category, str) and type(count) is int and count >= 0:
                    request_counts[category] += count
            runner_seconds += float(audit.get("seconds", 0.0))
            completed_tasks += len(chunk)
            print(json.dumps({
                "state": "batch_complete",
                "batch": chunk_number,
                "batches": len(chunks),
                "tasks_completed": completed_tasks,
                "public_training_tasks": len(task_items),
                "fallback_examples": fallback_examples,
                "observation_request_counts": dict(sorted(request_counts.items())),
            }, ensure_ascii=False), flush=True)

    combined_submission = (
        json.dumps(output_map, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    combined_submission_sha = sha256(combined_submission)
    request_partition = sum(
        request_counts.get(key, 0)
        for key in (
            "missing_condition_path_requests",
            "unknown_condition_value_requests",
            "other_additional_observation_requests",
        )
    )
    if request_counts.get("additional_observation_requests", 0) != request_partition:
        raise RuntimeError("observation-request categories do not partition total requests")

    summary = {
        "schema": "arc2-v61-observation-request-category-audit-v1",
        "track": "ARC2",
        "experiment_id": "ARC2-v61-observation-request-category-audit-20261027",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": source_commit,
        "bundle_sha256": bundle_sha,
        "bundle_manifest_sha256": sha256(manifest_bytes),
        "v61_wrapper_sha256": sha256(wrapper_bytes),
        "v61_hds_sha256": sha256(hds_bytes),
        "training_challenges_sha256": challenge_sha,
        "scope": {
            "dataset": "public ARC2 training challenge inputs",
            "public_training_tasks": len(all_tasks),
            "static_prior_source_tasks_included": prior_source_task_count,
            "test_examples": test_examples,
            "chunk_size": CHUNK_SIZE,
            "runtime_received_test_solutions": False,
            "solutions_file_opened": False,
            "task_ids_or_raw_grids_persisted": False,
        },
        "observation_request_counts": dict(sorted(request_counts.items())),
        "count_semantics": {
            "additional_observation_requests": "sum of HDS aggregate request records over eligible task test examples",
            "category_partition": [
                "missing_condition_path_requests",
                "unknown_condition_value_requests",
                "other_additional_observation_requests",
            ],
            "category_counts_partition_total": request_counts.get("additional_observation_requests", 0) == request_partition,
            "requests_are_not_equivalent_to_wrong_answers_or_solved_examples": True,
        },
        "fallback": {
            "fallback_examples": fallback_examples,
            "reason_counts": dict(sorted(fallback_reasons.items())),
            "fallback_count_matches_reason_count_sum": fallback_examples == sum(fallback_reasons.values()),
        },
        "reproduction": {
            "chunk_count": len(chunk_hashes),
            "chunk_submission_hashes_sha256": sha256(",".join(chunk_hashes).encode("ascii")),
            "combined_submission_sha256": combined_submission_sha,
            "matches_previous_full_run_submission_sha256": combined_submission_sha == EXPECTED_PREVIOUS_SUBMISSION_SHA256,
            "previous_full_run_submission_sha256": EXPECTED_PREVIOUS_SUBMISSION_SHA256,
            "aggregate_runner_seconds": round(runner_seconds, 3),
            "wall_seconds": round(time.monotonic() - started, 3),
        },
        "interpretation": [
            "This is a category-level diagnostic of HDS observation requests; it does not inspect training solutions or hidden scoring data.",
            "Request counts describe HDS diagnostic requests and are not accuracy metrics.",
            "No production source was changed and no Kaggle submission or notebook run was performed.",
        ],
        "production_source_changed": False,
        "official_submission_performed": False,
        "official_score": None,
    }
    content = (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with OUTPUT.open("xb") as target:
        target.write(content)
    print(json.dumps({
        "state": "complete",
        "summary_path": str(OUTPUT.relative_to(ROOT)),
        "summary_sha256": sha256(content),
        "observation_request_counts": summary["observation_request_counts"],
        "fallback_examples": fallback_examples,
        "combined_submission_sha256": combined_submission_sha,
        "wall_seconds": summary["reproduction"]["wall_seconds"],
    }, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
