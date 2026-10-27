"""Compare current main against the HDS-admitted generic object family.

The Kaggle wrapper receives only public test challenges. Public solutions are
loaded after baseline and two candidate full-runtime outputs are complete.
Only aggregate metrics and artifact hashes are persisted.
"""
from __future__ import annotations

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
EXPECTED_TASKS = 240
EXPECTED_EXAMPLES = 259
RUN_TIMEOUT_SECONDS = 7200


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_helper():
    spec = importlib.util.spec_from_file_location("current_main_loo_helper", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the matched-LOO snapshot helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_wrapper(label: str, payload_root: Path, output_dir: Path, revision: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True)
    env = {
        **os.environ,
        "ARC2_PAYLOAD_ROOT": str(payload_root),
        "ARC2_SOURCE_COMMIT": revision,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    started = time.perf_counter()
    command = [
        sys.executable,
        str(payload_root / "接続/ARC2/Kaggle提出.py"),
        "--challenges",
        str(CHALLENGE),
        "--output-dir",
        str(output_dir),
    ]
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
            f"{label} full runtime failed ({process.returncode}); "
            f"stdout_tail={process.stdout[-2400:]!r}; stderr_tail={process.stderr[-2400:]!r}"
        )
    prediction_path = output_dir / "submission.json"
    audit_path = output_dir / "submission_audit.json"
    if not prediction_path.is_file() or not audit_path.is_file():
        raise RuntimeError(f"{label} did not create both expected artifacts")
    return {
        "label": label,
        "prediction_path": prediction_path,
        "audit_path": audit_path,
        "wall_seconds": round(time.perf_counter() - started, 3),
        "prediction_sha256": _sha(prediction_path.read_bytes()),
        "audit_sha256": _sha(audit_path.read_bytes()),
    }


def _score(run: dict[str, Any], targets: dict[str, Any]) -> dict[str, Any]:
    predictions = json.loads(run["prediction_path"].read_text(encoding="utf-8"))
    audit = json.loads(run["audit_path"].read_text(encoding="utf-8"))
    fallback_pairs = {
        (item["task_id"], item["test_index"]) for item in audit.get("fallbacks", [])
    }
    if not set(predictions).issubset(targets):
        raise ValueError(f"{run['label']}: a prediction task has no public-solution target")

    raw_exact = primary_exact = pair_exact = strict_pair_exact = fallback_exact = 0
    exact_tasks = strict_exact_tasks = 0
    example_count = 0
    correctness: dict[tuple[str, int], dict[str, bool]] = {}
    for task_id, rows in predictions.items():
        task_targets = targets[task_id]
        if len(rows) != len(task_targets):
            raise ValueError(f"{run['label']}: prediction/target count mismatch")
        task_pair: list[bool] = []
        task_strict: list[bool] = []
        for index, (row, target) in enumerate(zip(rows, task_targets, strict=True)):
            first, second = row["attempt_1"], row["attempt_2"]
            fallback = (task_id, index) in fallback_pairs
            raw = first == target or second == target
            primary = not fallback and first == target
            # A distinct attempt 2 is a generated candidate even when attempt 1 held.
            pair = primary or (second != first and second == target)
            strict = raw and not fallback
            example_count += 1
            raw_exact += raw
            primary_exact += primary
            pair_exact += pair
            strict_pair_exact += strict
            fallback_exact += raw and fallback
            task_pair.append(pair)
            task_strict.append(strict)
            correctness[(task_id, index)] = {
                "raw": raw,
                "primary": primary,
                "pair": pair,
                "strict_pair": strict,
            }
        exact_tasks += all(task_pair)
        strict_exact_tasks += all(task_strict)

    if example_count != EXPECTED_EXAMPLES or len(predictions) != EXPECTED_TASKS:
        raise ValueError(f"{run['label']}: public challenge cohort size changed")
    return {
        "run": run["label"],
        "prediction_sha256": run["prediction_sha256"],
        "audit_sha256": run["audit_sha256"],
        "wrapper_wall_seconds": run["wall_seconds"],
        "reported_runtime_seconds": audit.get("seconds"),
        "runtime_tasks": audit.get("tasks"),
        "runtime_examples": audit.get("test_examples"),
        "fallback_count": len(fallback_pairs),
        "raw_exact_examples_including_fallback": raw_exact,
        "raw_exact_examples_from_fallback_excluded": strict_pair_exact,
        "fallback_exact_examples_excluded": fallback_exact,
        "solver_pass_at_1_excluding_fallback": primary_exact,
        "solver_pass_at_2_excluding_fallback_answer_and_input_copy": pair_exact,
        "solver_exact_tasks_pass_at_2": exact_tasks,
        "strict_exact_tasks_excluding_any_fallback": strict_exact_tasks,
        "example_count": example_count,
        "task_count": len(predictions),
        "_correctness": correctness,
    }


def _paired_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, int]:
    if set(before["_correctness"]) != set(after["_correctness"]):
        raise ValueError("paired run keys differ")
    fields = ("raw", "primary", "pair", "strict_pair")
    result: dict[str, int] = {}
    for field in fields:
        gains = regressions = 0
        for key, old in before["_correctness"].items():
            new = after["_correctness"][key]
            gains += new[field] and not old[field]
            regressions += old[field] and not new[field]
        result[f"{field}_gains"] = gains
        result[f"{field}_regressions"] = regressions
        result[f"{field}_delta"] = gains - regressions
    return result


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    challenge_bytes = CHALLENGE.read_bytes()
    challenge_sha = _sha(challenge_bytes)
    if challenge_sha != EXPECTED_CHALLENGE_SHA256:
        raise RuntimeError("public challenge hash differs from the recorded cohort")
    challenges = json.loads(challenge_bytes)
    challenge_examples = sum(len(task["test"]) for task in challenges.values())
    if len(challenges) != EXPECTED_TASKS or challenge_examples != EXPECTED_EXAMPLES:
        raise RuntimeError("public challenge task/example count differs from expected")

    helper = _load_helper()
    bundle_bytes = helper.BUNDLE.read_bytes()
    if _sha(bundle_bytes) != helper.EXPECTED_BUNDLE_SHA256:
        raise RuntimeError("seed bundle checksum mismatch")
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()
    with tempfile.TemporaryDirectory(prefix="arc2-current-main-full-public-") as temp_name:
        temp = Path(temp_name)
        roots = {name: temp / name for name in ("baseline", "candidate")}
        for path in roots.values():
            path.mkdir()
        manifest, bundle_manifest_sha = helper.extract_bundle(bundle_bytes, roots["baseline"])
        helper.extract_bundle(bundle_bytes, roots["candidate"])
        head_files = helper.read_head_payload(manifest, revision)
        baseline_payload_sha, retained_train, removed_paths = helper.materialize_head_snapshot(
            roots["baseline"], manifest, head_files
        )
        candidate_payload_sha, retained_candidate_train, removed_candidate_paths = helper.materialize_head_snapshot(
            roots["candidate"], manifest, head_files
        )
        if (baseline_payload_sha != candidate_payload_sha
                or retained_train != retained_candidate_train
                or removed_paths != removed_candidate_paths):
            raise RuntimeError("baseline and candidate payloads differ before the candidate patch")
        candidate_hds_sha = helper.patch_candidate_hds(
            roots["candidate"] / "接続/ARC2/HDS接続.py"
        )
        baseline_hds_sha = helper.sha256(
            (roots["baseline"] / "接続/ARC2/HDS接続.py").read_bytes()
        )
        wrapper_sha = helper.sha256(
            (roots["baseline"] / "接続/ARC2/Kaggle提出.py").read_bytes()
        )
        runs = [
            _run_wrapper("current_main", roots["baseline"], temp / "out-baseline", revision),
            _run_wrapper("candidate_repeat_1", roots["candidate"], temp / "out-candidate-1", revision),
            _run_wrapper("candidate_repeat_2", roots["candidate"], temp / "out-candidate-2", revision),
        ]

        # Public labels are read only after every baseline and candidate output is fixed.
        targets = json.loads(TARGETS.read_text(encoding="utf-8"))
        scores = [_score(run, targets) for run in runs]
        baseline_score, candidate_score, repeat_score = scores
        candidate_outputs_reproducible = (
            candidate_score["prediction_sha256"] == repeat_score["prediction_sha256"]
            and candidate_score["_correctness"] == repeat_score["_correctness"]
            and candidate_score["fallback_count"] == repeat_score["fallback_count"]
        )
        public_target_sha = _sha(TARGETS.read_bytes())
        summaries = [
            {key: value for key, value in score.items() if key != "_correctness"}
            for score in scores
        ]
        report = {
            "schema": "arc2-current-main-object-candidate-full-public-evaluation-v1",
            "run_id": "ARC2-current-main-object-candidate-full-public-evaluation-20261028",
            "track": "ARC2",
            "source_revision": revision,
            "payload_manifest_sha256": baseline_payload_sha,
            "seed_bundle_sha256": _sha(bundle_bytes),
            "seed_bundle_manifest_sha256": bundle_manifest_sha,
            "payload_member_count": len(manifest["files"]),
            "bundle_only_public_training_files_retained": retained_train,
            "bundle_paths_absent_from_main_removed": removed_paths,
            "baseline_hds_sha256": baseline_hds_sha,
            "candidate_hds_sha256": candidate_hds_sha,
            "wrapper_sha256": wrapper_sha,
            "challenge_file_sha256": challenge_sha,
            "public_solutions_sha256": public_target_sha,
            "public_solution_task_count": len(targets),
            "prediction_task_set_is_subset_of_public_solutions": True,
            "challenge_tasks": len(challenges),
            "challenge_examples": challenge_examples,
            "candidates": summaries,
            "paired_delta_candidate_vs_current_main": _paired_delta(
                baseline_score, candidate_score
            ),
            "candidate_repeat_reproducible": candidate_outputs_reproducible,
            "public_solutions_read_after_all_runtime_predictions": True,
            "fallback_policy": "A fallback copy is never counted as solver-correct; pass@2 may count only a distinct generated attempt 2.",
            "task_ids_or_raw_grids_or_per_example_labels_persisted": False,
            "hidden_or_evaluation_solutions_read": False,
            "official_submission_performed": False,
            "official_score": None,
            "limitations": [
                "Local public-solution evaluation is not an official Kaggle score.",
                "The full wrapper ran against public test challenges; public solutions were loaded only afterward.",
            ],
        }
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with OUTPUT.open("w", encoding="utf-8", newline="\n") as target:
            target.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
