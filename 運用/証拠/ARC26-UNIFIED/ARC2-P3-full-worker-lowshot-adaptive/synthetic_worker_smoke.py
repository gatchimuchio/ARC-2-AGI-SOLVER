"""Two actual full-worker processes, synthetic rotate90 task, no public fit."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

import public_harness as h


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("refuse to overwrite synthetic evidence")
    sources = h.source_fingerprint()
    if sources["sha256"] != args.expected_source_sha256:
        raise ValueError("source differs from review pin")
    inputs = [[[0, color, 0], [0, 0, color + 1]] for color in (1, 3, 5, 7)]
    pairs = [{"input": deepcopy(grid), "output": [list(row) for row in zip(*grid[::-1])]} for grid in inputs]
    data = {"synthetic_only": {"train": pairs}}
    row = {"task_id": "synthetic_only", "support_indices": [0, 1], "feedback_index": 2, "unseen_index": 3}
    prior_sources, prior_files = h.template_sources_parent()
    prior, prior_audit = h.filtered_prior(prior_sources, "synthetic_only", inputs)
    results = {}
    for phase in h.PHASES:
        payload = h.make_payload(data, row, phase, prior, sources["sha256"])
        h.validate_payload(payload)
        raw = h.invoke(payload, 90)
        h.enforce_boundary(raw)
        if raw["state"] != "complete":
            raise AssertionError(f"synthetic {phase} failed: {raw.get('state')}, {raw.get('solver_error_type')}, {raw.get('frames')}")
        floor = 2 if phase == "before" else 3
        settings = raw["hds_central_constructor_settings"]
        if len(settings) != 1 or settings[0]["outer"] != floor or settings[0]["validator"] != floor:
            raise AssertionError("actual adaptive outer/inner constructor settings differ")
        if raw["prior_readers"]["generic_reader"] != 0 or raw["prior_readers"]["template_reader"] != 1:
            raise AssertionError("unexpected prior path")
        result = h.score_and_strip(raw, [pairs[2]["output"], pairs[3]["output"]], inputs[2:])
        if not all(score["nonfallback_pass2"] for score in result["scores"]):
            raise AssertionError(f"synthetic actual attempt policy did not solve both rotate90 queries: {result['scores']}")
        results[phase] = result
    if sources != h.source_fingerprint():
        raise AssertionError("source changed during smoke")
    report = {"state": "PASS_CURRENT_FULL_WORKER_ADAPTIVE2_TO3", "completed_at": datetime.now(timezone.utc).isoformat(),
              "source_sha256": sources["sha256"], "fresh_worker_processes": 2, "public_data_loaded": False,
              "scope": "synthetic actual worker/formatter/adaptive policy plumbing; no public or pure-HDS learning gain claim",
              "prior_filter": prior_audit, "parent_prior_files": prior_files, "results": results}
    if h.contains_grid(report):
        raise AssertionError("raw grid escaped synthetic evidence stripping")
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
