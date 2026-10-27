from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))
sys.path.insert(0, str(ROOT))
from 接続.ARC2.HDS接続 import 課題を解く  # noqa: E402
from 接続.ARC2.Kaggle提出 import 格子か, _一意な別候補を選ぶ  # noqa: E402

TRAINING_DIR = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
SAMPLE_FOLDS = 50


def main() -> None:
    samples = []
    manifest = hashlib.sha256()
    for path in sorted(TRAINING_DIR.glob("*.json")):
        raw = path.read_bytes()
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        examples = json.loads(raw).get("train", [])
        if len(examples) < 4:
            continue
        for index, heldout in enumerate(examples):
            teachers = [pair for i, pair in enumerate(examples) if i != index]
            challenge = {"train": teachers, "test": [{"input": heldout["input"]}]}
            samples.append((challenge, heldout["input"]))
            if len(samples) == SAMPLE_FOLDS:
                break
        if len(samples) == SAMPLE_FOLDS:
            break
    if len(samples) != SAMPLE_FOLDS:
        raise RuntimeError(f"expected {SAMPLE_FOLDS} public LOO folds, got {len(samples)}")

    baseline_seconds = []
    candidate_seconds = []
    first_answer_changes = 0
    distinct_second_candidates = 0

    for index, (challenge, fallback) in enumerate(samples):
        def run(collect: bool):
            started = time.perf_counter()
            result = 課題を解く(challenge, [], 候補収集=collect)
            selected = []
            if collect:
                for row in result.get("results", []):
                    row = row if isinstance(row, dict) else {}
                    first = row.get("answer")
                    if not 格子か(first):
                        first = fallback
                    second = _一意な別候補を選ぶ(
                        row.get("candidate_predictions"), first
                    )
                    selected.append(second)
            return result, selected, time.perf_counter() - started

        if index % 2 == 0:
            baseline, _, base_elapsed = run(False)
            candidate, selected, current_elapsed = run(True)
        else:
            candidate, selected, current_elapsed = run(True)
            baseline, _, base_elapsed = run(False)
        baseline_seconds.append(base_elapsed)
        candidate_seconds.append(current_elapsed)
        if selected and selected[0] is not None:
            distinct_second_candidates += 1
        base_rows = baseline.get("results", [])
        candidate_rows = candidate.get("results", [])
        if len(base_rows) != len(candidate_rows):
            first_answer_changes += 1
        else:
            for base_row, candidate_row in zip(base_rows, candidate_rows):
                base_row = base_row if isinstance(base_row, dict) else {}
                candidate_row = candidate_row if isinstance(candidate_row, dict) else {}
                if (base_row.get("answer"), base_row.get("status")) != (
                    candidate_row.get("answer"), candidate_row.get("status")
                ):
                    first_answer_changes += 1
                    break

    baseline_total = sum(baseline_seconds)
    candidate_total = sum(candidate_seconds)
    result = {
        "schema": "arc2-p5-candidate-collection-runtime-benchmark.v1",
        "instruction_id": "ARC2-SCORE-GATE-20261024",
        "data_source": "public ARC-AGI-2 training split only; held-out output unused",
        "sampled_loo_folds": len(samples),
        "prior_examples_used": 0,
        "baseline_mode": "候補収集=False",
        "current_mode": "候補収集=True plus adapter unique-alternative selector",
        "baseline_elapsed_seconds": round(baseline_total, 3),
        "current_elapsed_seconds": round(candidate_total, 3),
        "elapsed_delta_seconds": round(candidate_total - baseline_total, 3),
        "elapsed_delta_percent": round((candidate_total / baseline_total - 1) * 100, 3),
        "baseline_median_seconds_per_fold": round(statistics.median(baseline_seconds), 4),
        "current_median_seconds_per_fold": round(statistics.median(candidate_seconds), 4),
        "first_answer_changed_folds": first_answer_changes,
        "folds_with_distinct_second_candidate": distinct_second_candidates,
        "evaluation_solutions_read": False,
        "task_identifiers_or_grids_saved": False,
        "sample_source_manifest_sha256": manifest.hexdigest(),
        "hds_source_sha256": hashlib.sha256((ROOT / "接続/ARC2/HDS接続.py").read_bytes()).hexdigest(),
        "adapter_source_sha256": hashlib.sha256((ROOT / "接続/ARC2/Kaggle提出.py").read_bytes()).hexdigest(),
        "benchmark_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    output = Path(__file__).with_suffix(".json")
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
