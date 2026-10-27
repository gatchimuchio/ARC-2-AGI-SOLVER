"""Existing A3/F/U fixture through four fresh default-grammar harness workers."""
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
        raise FileExistsError("refuse to overwrite existing synthetic evidence")
    # Exact teacher construction from test_cell_conditional_tree.py's
    # test_feedback_removes_role_ambiguity_with_both_phases_already_hds_eligible.
    # Unlike that restricted-grammar induction test, this plumbing run retains
    # all 33 public-default features in both phases, with no tuning.
    def teacher(grid):
        target = deepcopy(grid)
        for row in range(1, len(grid)):
            for column in range(1, len(grid[0])):
                target[row][column] = grid[row - 1][column]
        return {"input": grid, "output": target}
    pairs = [teacher(grid) for grid in (
        [[1, 2, 3], [2, 3, 4], [3, 4, 5]],
        [[6, 7, 8], [7, 8, 9], [8, 9, 0]],
        [[2, 4, 6], [4, 6, 8], [6, 8, 1]],
        [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
        [[9, 8, 7], [6, 5, 4], [3, 2, 1]],
    )]
    dataset = {"synthetic_only": {"train": pairs}}
    row = {"task_id": "synthetic_only", "support_indices": [0, 1, 2],
           "feedback_index": 3, "unseen_index": 4}
    source = harness.source_fingerprint()
    results = {arm: {} for arm in harness.ARMS}
    for phase in harness.PHASES:
        for arm in harness.ARMS:
            payload = harness.make_payload(dataset, row, arm, phase, source["sha256"])
            harness.validate_payload(payload)
            if payload["feature_indices"] != list(range(33)):
                raise AssertionError("synthetic must retain public default grammar")
            result = harness.invoke(payload, 30)
            scores, safe = harness.score_result(result, [pairs[3]["output"], pairs[4]["output"]])
            if result["state"] != "complete":
                raise AssertionError(f"synthetic dataflow failed for {arm}/{phase}: {safe}")
            if not safe["model_unchanged_after_query"]:
                raise AssertionError("query mutated normalized learned state")
            results[arm][phase] = {"scores": scores, "evidence": safe}
    if source != harness.source_fingerprint():
        raise AssertionError("source changed during synthetic smoke")
    report = {"state": "PASS_DATAFLOW", "completed_at": datetime.now(timezone.utc).isoformat(),
              "fixture": "existing synthetic north/west ambiguity A3->A+F4; no new induction design",
              "candidate_feature_indices": list(range(33)), "fresh_processes": 4,
              "public_data_loaded": False, "module_sha256": args.expected_module_sha256,
              "harness_sha256": harness.sha(Path(harness.__file__).read_bytes()),
              "source_sha256": source["sha256"], "results": results,
              "scope": "default-grammar plumbing only; actual status/admission/output retained without asserting public gain or HDS-core discovery"}
    if harness.contains_grid(report):
        raise AssertionError("raw synthetic grids escaped evidence stripping")
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    brief = {key: value for key, value in report.items() if key != "results"}
    brief["observed"] = {arm: {phase: {
        "status": result["evidence"]["model_fitted"]["typed_state"].get("status", "legacy_local_context"),
        "admission": result["evidence"]["admission"],
        "direct_exact": [score["direct_exact"] for score in result["scores"]],
        "hds_exact": [score["hds_exact"] for score in result["scores"]],
        "hds_queried": [row["hds_queried"] for row in result["evidence"]["rows"]],
    } for phase, result in phases.items()} for arm, phases in results.items()}
    print(json.dumps(brief, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
