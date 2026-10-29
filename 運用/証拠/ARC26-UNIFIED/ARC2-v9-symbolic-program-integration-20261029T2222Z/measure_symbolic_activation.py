from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[3]
PREREG = json.loads((RUN / "preregistration.json").read_text(encoding="utf-8"))
CHALLENGE_PATH = RUN / "challenge_input.json"
CHALLENGE = json.loads(CHALLENGE_PATH.read_text(encoding="utf-8"))
BASELINE = json.loads((RUN / "baseline-freeze/submission.json").read_text(encoding="utf-8"))
CANDIDATE_ROOT = Path(PREREG["candidate"]["worktree"])
sys.path.insert(0, str(CANDIDATE_ROOT))
from 接続.ARC2.汎用プログラム帰納候補 import 汎用プログラム帰納候補群  # noqa: E402


def measure(item: tuple[str, dict]) -> dict[str, int]:
    alias, task = item
    group = 汎用プログラム帰納候補群(task["train"])
    total = {
        "exact_programs": len(group._候補群),
        "grids": 0,
        "first_predictions": 0,
        "second_predictions": 0,
        "distinct_prediction_pairs": 0,
        "predictions_distinct_from_baseline_attempts": 0,
        "grids_with_any_candidate": 0,
        "grids_with_second_candidate": 0,
    }
    for index, test in enumerate(task["test"]):
        total["grids"] += 1
        first, first_evidence = group.第一候補(test["input"], {})
        second, _ = group.第二候補(test["input"], {})
        candidates = first_evidence.get("candidate_attempts", [])
        values = [first, second]
        if len(candidates) == 2:
            total["distinct_prediction_pairs"] += int(candidates[0] != candidates[1])
        valid = [value for value in values if value is not None]
        total["first_predictions"] += int(first is not None)
        total["second_predictions"] += int(second is not None)
        total["grids_with_any_candidate"] += int(bool(valid))
        total["grids_with_second_candidate"] += int(second is not None)
        baseline_pair = BASELINE[alias][index]
        for value in valid:
            total["predictions_distinct_from_baseline_attempts"] += int(
                value not in (baseline_pair["attempt_1"], baseline_pair["attempt_2"])
            )
    total["tasks_with_exact_program"] = int(bool(group._候補群))
    return total


started_at_utc = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
started = time.monotonic()
with ThreadPoolExecutor(max_workers=3) as executor:
    rows = list(executor.map(measure, CHALLENGE.items()))
seconds = round(time.monotonic() - started, 3)
keys = rows[0].keys() if rows else ()
aggregate = {key: sum(row[key] for row in rows) for key in keys}
aggregate["tasks"] = len(rows)
aggregate["mean_exact_programs_per_task"] = round(aggregate["exact_programs"] / max(len(rows), 1), 3)
challenge_sha = hashlib.sha256(CHALLENGE_PATH.read_bytes()).hexdigest()
assert challenge_sha == PREREG["runtime_input"]["sha256"]
assert all("output" not in pair for task in CHALLENGE.values() for pair in task["test"])
aggregate_audit = json.loads(
    Path(r"C:\Users\ohira\AppData\Local\Temp\arc2-v9-symbolic-candidate-diagnostics-20261029T2222Z/submission_audit.json")
    .read_text(encoding="utf-8")
)
symbolic_in_hds = {
    name: value
    for name, value in aggregate_audit.get("aggregate_diagnostics", {}).get(
        "candidate_family_counts", {}
    ).items()
    if "記号プログラム帰納" in name
}
result = {
    "schema": "arc2-v9-symbolic-candidate-activation-diagnostics-v1",
    "run_id": PREREG["run_id"],
    "started_at_utc": started_at_utc,
    "finished_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    "challenge_sha256": challenge_sha,
    "cohort_tasks": len(CHALLENGE),
    "cohort_grids": sum(len(task["test"]) for task in CHALLENGE.values()),
    "label_access": "none; train pairs and test inputs only",
    "direct_generator": aggregate,
    "hds_aggregate_diagnostics": {
        "submission_sha256": aggregate_audit.get("submission_sha256"),
        "byte_identical_to_candidate_freeze": aggregate_audit.get("submission_sha256")
        == json.loads((RUN / "candidate-freeze/freeze.json").read_text(encoding="utf-8"))[
            "artifacts"
        ]["submission.json"],
        "seconds_with_diagnostics": aggregate_audit.get("seconds"),
        "fallback_count": aggregate_audit.get("fallback_count"),
        "candidate_family_counts": aggregate_audit.get("aggregate_diagnostics", {}).get(
            "candidate_family_counts", {}
        ),
        "symbolic_family_count_in_hds_output": symbolic_in_hds,
    },
    "diagnostic_runtime_seconds": seconds,
    "interpretation": "Compare direct train-exact generator activation with HDS candidate-family output. No target labels were read.",
}
out = RUN / "symbolic_activation_diagnostics.json"
if out.exists():
    raise FileExistsError(out)
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"direct_generator": aggregate, "hds_symbolic_family_count": symbolic_in_hds, "diagnostic_runtime_seconds": seconds}, ensure_ascii=False))
