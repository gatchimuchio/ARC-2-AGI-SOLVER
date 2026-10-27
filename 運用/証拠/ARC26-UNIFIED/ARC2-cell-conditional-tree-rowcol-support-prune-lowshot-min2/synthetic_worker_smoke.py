"""Four fresh exploratory FIXED_MIN2 workers, existing row-count fixture only."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

import public_harness as harness


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-module-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if harness.sha(harness.MODULE.read_bytes()) != args.expected_module_sha256:
        raise ValueError("module differs from review pin")
    if args.output.exists():
        raise FileExistsError("refuse to overwrite synthetic evidence")
    # Reuse the existing default row-count fixture from test_support_prune.py.
    pairs = []
    for active, single, color in ((1, 5, 1), (2, 4, 3), (3, 1, 5), (4, 2, 7)):
        grid = [[0] * 7 for _ in range(7)]
        grid[active][0] = grid[active][-1] = color
        grid[single][0] = color + 1
        target = [[6] * 7 if sum(value != 0 for value in row) == 2 else row[:] for row in grid]
        pairs.append({"input": deepcopy(grid), "output": target})
    dataset = {"synthetic_only": {"train": pairs}}
    row = {"task_id": "synthetic_only", "support_indices": [0, 1],
           "feedback_index": 2, "unseen_index": 3}
    source = harness.source_fingerprint()
    results = {arm: {} for arm in harness.ARMS}
    for phase in harness.PHASES:
        for arm in harness.ARMS:
            payload = harness.make_payload(dataset, row, arm, phase, source["sha256"])
            harness.validate_payload(payload)
            response = harness.invoke(payload, 30)
            scores, safe = harness.score_result(response, [pairs[2]["output"], pairs[3]["output"]])
            if response["state"] != "complete":
                raise AssertionError(f"synthetic worker failed for {arm}/{phase}: {safe}")
            for key in ("hds_configuration_before", "hds_configuration_after"):
                settings = safe[key]
                if settings["actual_outer_minimum_support"] != 2 or settings["actual_validator_minimum_support"] != 2:
                    raise AssertionError("real inner/outer support floors differ from constructor min2")
            if not safe["admission"]["採用可"] or not safe["admission"]["同値採用"]:
                raise AssertionError("real HDS must admit all current teachers even in two-support before phase")
            if safe["hds_admitted"]["experience_count"] != len(payload["support"]):
                raise AssertionError("HDS observation count differs from current support")
            if not all(score["direct_exact"] and score["hds_exact"] for score in scores):
                raise AssertionError("synthetic direct/HDS output mismatch")
            if not all(item["hds_queried"] for item in safe["rows"]):
                raise AssertionError("synthetic did not exercise real HDS query")
            if not safe["model_unchanged_after_query"]:
                raise AssertionError("query mutated learned tree state")
            results[arm][phase] = {"scores": scores, "evidence": safe}
    if source != harness.source_fingerprint():
        raise AssertionError("sources changed during synthetic smoke")
    report = {"state": "PASS_DATAFLOW_FIXED_MIN2", "completed_at": datetime.now(timezone.utc).isoformat(),
              "study_scope": harness.STUDY_SCOPE, "fresh_processes": 4, "public_data_loaded": False,
              "module_sha256": args.expected_module_sha256, "baseline_module_sha256": harness.BASELINE_MODULE_SHA256,
              "harness_sha256": harness.sha(Path(harness.__file__).read_bytes()),
              "source_sha256": source["sha256"], "results": results,
              "production_policy_changed": False, "must_not_pool_with_default_min3": True,
              "scope": "synthetic plumbing only; no public/full-solver/official or pruning-capability improvement claim"}
    if harness.contains_grid(report):
        raise AssertionError("raw synthetic grids escaped evidence stripping")
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
