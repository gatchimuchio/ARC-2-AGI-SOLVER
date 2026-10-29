from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[3]
PREREG = json.loads((RUN / "preregistration.json").read_text(encoding="utf-8"))
CHALLENGE_PATH = RUN / "challenge_input.json"
CHALLENGE = json.loads(CHALLENGE_PATH.read_text(encoding="utf-8"))
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
FREEZES = {name: RUN / f"{name}-freeze" for name in ("baseline", "candidate")}


challenge_sha = hashlib.sha256(CHALLENGE_PATH.read_bytes()).hexdigest()
assert challenge_sha == PREREG["runtime_input"]["sha256"]
assert all(
    "output" not in pair
    for task in CHALLENGE.values()
    for pair in task["test"]
)

frozen: dict[str, tuple[dict, dict, dict]] = {}
for name, folder in FREEZES.items():
    meta = json.loads((folder / "freeze.json").read_text(encoding="utf-8"))
    submission_bytes = (folder / "submission.json").read_bytes()
    audit_bytes = (folder / "submission_audit.json").read_bytes()
    assert hashlib.sha256(submission_bytes).hexdigest() == meta["artifacts"]["submission.json"]
    assert hashlib.sha256(audit_bytes).hexdigest() == meta["artifacts"]["submission_audit.json"]
    assert meta["challenge_sha256"] == challenge_sha
    frozen[name] = (
        json.loads(submission_bytes),
        json.loads(audit_bytes),
        meta,
    )

fallback_sets: dict[str, set[tuple[str, int]]] = {}
for name, (_, audit, _) in frozen.items():
    keys = {(item["task_id"], item["test_index"]) for item in audit["fallbacks"]}
    assert len(keys) == len(audit["fallbacks"]) == audit["fallback_count"]
    fallback_sets[name] = keys
assert fallback_sets["baseline"] == fallback_sets["candidate"]

selected_ids = PREREG["cohort"]["selected_public_training_task_ids"]
assert len(selected_ids) == 100
counts = {
    "grids": 0,
    "fallback_grids": 0,
    "baseline_pass1": 0,
    "baseline_pass2": 0,
    "candidate_pass1": 0,
    "candidate_pass2": 0,
    "baseline_tasks_pass1": 0,
    "baseline_tasks_pass2": 0,
    "candidate_tasks_pass1": 0,
    "candidate_tasks_pass2": 0,
    "baseline_attempt2_rescues": 0,
    "candidate_attempt2_rescues": 0,
}
paired = {
    f"{metric}_{unit}_{kind}": 0
    for metric in ("pass1", "pass2")
    for unit in ("grid", "task")
    for kind in ("improvements", "regressions")
}
source_hash_rows: list[tuple[str, str]] = []

for position, public_id in enumerate(selected_ids, 1):
    alias = f"fresh_{position:03d}"
    source_path = TRAINING / f"{public_id}.json"
    source_bytes = source_path.read_bytes()
    source_hash_rows.append((public_id, hashlib.sha256(source_bytes).hexdigest()))
    source = json.loads(source_bytes)
    assert alias in CHALLENGE
    tests = source["test"]
    challenge_tests = CHALLENGE[alias]["test"]
    assert len(tests) == len(challenge_tests)
    for name in ("baseline", "candidate"):
        assert len(frozen[name][0][alias]) == len(tests)

    task_marks = {
        name: {"pass1": [], "pass2": []}
        for name in ("baseline", "candidate")
    }
    for test_index, target in enumerate(tests):
        assert challenge_tests[test_index]["input"] == target["input"]
        counts["grids"] += 1
        is_fallback = (alias, test_index) in fallback_sets["baseline"]
        counts["fallback_grids"] += int(is_fallback)
        expected = target["output"]
        grid_marks: dict[str, tuple[bool, bool]] = {}
        for name in ("baseline", "candidate"):
            attempts = frozen[name][0][alias][test_index]
            pass1 = not is_fallback and attempts["attempt_1"] == expected
            pass2 = not is_fallback and (
                attempts["attempt_1"] == expected
                or attempts["attempt_2"] == expected
            )
            grid_marks[name] = (pass1, pass2)
            task_marks[name]["pass1"].append(pass1)
            task_marks[name]["pass2"].append(pass2)
            counts[f"{name}_pass1"] += int(pass1)
            counts[f"{name}_pass2"] += int(pass2)
            counts[f"{name}_attempt2_rescues"] += int(pass2 and not pass1)

        for metric, index in (("pass1", 0), ("pass2", 1)):
            baseline_hit = grid_marks["baseline"][index]
            candidate_hit = grid_marks["candidate"][index]
            paired[f"{metric}_grid_improvements"] += int(candidate_hit and not baseline_hit)
            paired[f"{metric}_grid_regressions"] += int(baseline_hit and not candidate_hit)

    for name in ("baseline", "candidate"):
        for metric in ("pass1", "pass2"):
            counts[f"{name}_tasks_{metric}"] += int(all(task_marks[name][metric]))
    for metric in ("pass1", "pass2"):
        baseline_hit = all(task_marks["baseline"][metric])
        candidate_hit = all(task_marks["candidate"][metric])
        paired[f"{metric}_task_improvements"] += int(candidate_hit and not baseline_hit)
        paired[f"{metric}_task_regressions"] += int(baseline_hit and not candidate_hit)

assert counts["grids"] == PREREG["cohort"]["test_grid_count"] == 111
source_manifest = "".join(
    f"{public_id} {digest}\n" for public_id, digest in source_hash_rows
).encode("ascii")
baseline_meta = frozen["baseline"][2]
candidate_meta = frozen["candidate"][2]
result = {
    "schema": "arc2-v9-public-training-paired-score-v1",
    "run_id": PREREG["run_id"],
    "scored_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    "scope": "PUBLIC_TRAINING_HOLDOUT_ONLY_NOT_OFFICIAL_SCORE",
    "external_pretraining_exposure": "unknown",
    "cohort": {
        "tasks": 100,
        "test_grids": counts["grids"],
        "fallback_grids": counts["fallback_grids"],
        "fallback_counted_correct": False,
    },
    "challenge_sha256": challenge_sha,
    "scorer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "public_training_source_file_manifest_sha256": hashlib.sha256(source_manifest).hexdigest(),
    "freeze_commits": {"baseline": "814e4e6", "candidate": "5dd131b"},
    "prediction_byte_identical": (
        (FREEZES["baseline"] / "submission.json").read_bytes()
        == (FREEZES["candidate"] / "submission.json").read_bytes()
    ),
    "baseline": {
        "pass1_grids": counts["baseline_pass1"],
        "pass1_rate": counts["baseline_pass1"] / counts["grids"],
        "pass2_grids": counts["baseline_pass2"],
        "pass2_rate": counts["baseline_pass2"] / counts["grids"],
        "tasks_pass1": counts["baseline_tasks_pass1"],
        "tasks_pass2": counts["baseline_tasks_pass2"],
        "attempt2_rescues": counts["baseline_attempt2_rescues"],
        "fallback_grids": frozen["baseline"][1]["fallback_count"],
        "runtime_seconds": baseline_meta["seconds"],
    },
    "candidate": {
        "pass1_grids": counts["candidate_pass1"],
        "pass1_rate": counts["candidate_pass1"] / counts["grids"],
        "pass2_grids": counts["candidate_pass2"],
        "pass2_rate": counts["candidate_pass2"] / counts["grids"],
        "tasks_pass1": counts["candidate_tasks_pass1"],
        "tasks_pass2": counts["candidate_tasks_pass2"],
        "attempt2_rescues": counts["candidate_attempt2_rescues"],
        "fallback_grids": frozen["candidate"][1]["fallback_count"],
        "runtime_seconds": candidate_meta["seconds"],
    },
    "delta_candidate_minus_baseline": {
        "pass1_grids": counts["candidate_pass1"] - counts["baseline_pass1"],
        "pass2_grids": counts["candidate_pass2"] - counts["baseline_pass2"],
        "tasks_pass1": counts["candidate_tasks_pass1"] - counts["baseline_tasks_pass1"],
        "tasks_pass2": counts["candidate_tasks_pass2"] - counts["baseline_tasks_pass2"],
        "attempt2_rescues": counts["candidate_attempt2_rescues"] - counts["baseline_attempt2_rescues"],
        "fallback_grids": frozen["candidate"][1]["fallback_count"] - frozen["baseline"][1]["fallback_count"],
        "runtime_seconds": round(candidate_meta["seconds"] - baseline_meta["seconds"], 3),
    },
    "paired_changes": paired,
    "adoption": "REJECTED_NO_ACCURACY_DELTA_AND_SLOWER",
    "official_score": None,
    "official_submission_id": 57783547,
    "official_submission_status_at_last_query": "PENDING",
}
result_path = RUN / "score_result.json"
if result_path.exists():
    raise FileExistsError(result_path)
result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: result[key] for key in (
    "scope", "cohort", "baseline", "candidate", "delta_candidate_minus_baseline",
    "paired_changes", "adoption", "prediction_byte_identical"
)}, ensure_ascii=False))
