"""Four short fresh-process plumbing checks, synthetic grids only."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import public_harness as harness


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-module-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--observation-update", action="store_true")
    args = parser.parse_args()
    if harness.sha(harness.MODULE.read_bytes()) != args.expected_module_sha256:
        raise ValueError("module SHA does not match review pin")
    if args.output.exists():
        raise FileExistsError("refuse to overwrite synthetic evidence")
    for path in (harness.ROOT, harness.ROOT / "HDS/学習系統/v0.4.2"):
        sys.path.insert(0, str(path))
    from 接続.ARC2.単純変換候補 import orientations
    inputs = [([[0, 1, 0], [0, 0, 2]], "rotate90"),
              ([[0, 3, 0], [0, 0, 4]], "rotate90"),
              ([[0, 0], [1, 0], [0, 2]], "reflect_horizontal"),
              ([[0, 0], [3, 0], [0, 4]], "reflect_horizontal"),
              ([[0, 5, 0], [0, 0, 6]], "rotate90"),
              ([[0, 0], [7, 0], [0, 8]], "reflect_horizontal")]
    if args.observation_update:
        inputs = [([[0, 1, 2], [0, 1, 2]], "rotate90"),
                  ([[0, 3, 4], [0, 3, 4]], "rotate90"),
                  ([[0, 1, 0], [0, 0, 2], [0, 0, 0], [1, 0, 0]], "reflect_horizontal"),
                  ([[0, 3, 0], [0, 0, 4], [0, 0, 0], [3, 0, 0]], "reflect_horizontal"),
                  ([[0, 5, 6], [0, 0, 7]], "rotate90"),
                  ([[0, 8, 1], [0, 0, 9]], "rotate90")]
    pairs = [{"input": deepcopy(grid), "output": orientations(grid)[orientation]} for grid, orientation in inputs]
    dataset = {"synthetic_only": {"train": pairs}}
    row = {"task_id": "synthetic_only", "support_indices": [0, 1, 2, 3],
           "feedback_index": 4, "unseen_index": 5}
    source = harness.source_fingerprint()
    results = {arm: {} for arm in harness.ARMS}
    for phase in harness.PHASES:
        for arm in harness.ARMS:
            payload = harness.make_payload(dataset, row, arm, phase, source["sha256"])
            if args.observation_update:
                payload["feature_indices"] = [0]  # Same fixed height-only grammar in both candidate phases.
            harness.validate_payload(payload)
            response = harness.invoke(payload, 30)
            scores, safe = harness.score_result(response, [pairs[4]["output"], pairs[5]["output"]])
            if response["state"] != "complete":
                raise AssertionError(f"synthetic {arm}/{phase} failed: {safe}")
            expected_hold = args.observation_update and arm == "feature_predicate" and phase == "before"
            require_correct = not args.observation_update or (arm == "feature_predicate" and phase == "after")
            if expected_hold and not all(score["direct_abstain_or_failure"] and score["hds_abstain_or_failure"] for score in scores):
                raise AssertionError("ambiguous synthetic before must retain HOLD on the two unseen queries")
            if require_correct and not all(score["direct_exact"] and score["hds_exact"] for score in scores):
                raise AssertionError(f"synthetic {arm}/{phase} did not predict both queries: {scores}")
            if require_correct and not all(item["hds_queried"] and item["equality_admitted"] for item in safe["rows"]):
                raise AssertionError("synthetic did not exercise actual equality-admitted HDS query")
            if safe["hds_admitted"]["experience_count"] != len(payload["support"]):
                raise AssertionError("HDS observation count differs from current support")
            if not safe["model_unchanged_after_query"]:
                raise AssertionError("query mutated fitted candidate state")
            results[arm][phase] = {"scores": scores, "evidence": safe}
    if source != harness.source_fingerprint():
        raise AssertionError("sources changed during synthetic smoke")
    if args.observation_update:
        previous = results["feature_predicate"]["before"]["evidence"]
        current = results["feature_predicate"]["after"]["evidence"]
        if previous["model_fitted"]["typed_state"]["status"] != "fitted":
            raise AssertionError("before must already be fitted with both branch support floors satisfied")
        old_count = len(previous["model_fitted"]["typed_state"]["hypotheses"])
        new_count = len(current["model_fitted"]["typed_state"]["hypotheses"])
        if not 0 < new_count < old_count:
            raise AssertionError("observed feedback must reduce retained hypotheses")
    report = {"state": "PASS", "completed_at": datetime.now(timezone.utc).isoformat(),
              "fixture": "synthetic shape-conditioned rotate90/reflection, four support then five",
              "observation_update": args.observation_update,
              "candidate_feature_indices": [0] if args.observation_update else list(range(25)),
              "fresh_worker_processes": 4, "public_data_loaded": False,
              "module_sha256": args.expected_module_sha256, "source_sha256": source["sha256"],
              "harness_sha256": harness.sha(Path(harness.__file__).read_bytes()),
              "scope": "synthetic external induction plus real HDS admission/query; no public performance or HDS-core-learning claim",
              "results": results}
    if harness.contains_grid(report):
        raise AssertionError("synthetic evidence unexpectedly contains raw grids")
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
