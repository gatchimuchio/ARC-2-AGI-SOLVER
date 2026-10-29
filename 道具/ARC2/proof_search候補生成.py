"""入力だけからProof SearchのARC2候補を作る比較用runner。正解ファイルは参照しない。"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
既定入力 = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-v9-candidate-family-confirm100-input-20261029.json"
既定候補器 = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-v9-proof-search-source-20261029/arc_proof_search.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("arc2_v9_proof_search", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"候補器を読み込めません: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=既定入力)
    parser.add_argument("--candidate-source", type=Path, default=既定候補器)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / "AppData/Local/Temp/arc2-v9-proof-search-confirm-20261029",
    )
    args = parser.parse_args()

    challenge = load_json(args.input)
    module = load_module(args.candidate_source)
    submission: dict[str, list[dict[str, list[list[int]]]]] = {}
    diagnostics: dict[str, list[dict[str, Any]]] = {}
    exact_program_counts: list[int] = []
    unique_program_counts: list[int] = []
    first_candidate_grids = second_candidate_grids = 0
    fallback_first_grids = fallback_second_slots = 0
    started = time.perf_counter()

    for alias, task in challenge.items():
        programs: list[tuple[Any, list[list[list[int]]]]] = []
        seen_programs: set[tuple[Any, ...]] = set()
        candidates = module.synthesize(task)
        exact_program_count = sum(bool(candidate.exact) for candidate in candidates)
        tests = task["test"]

        for candidate in candidates:
            if not candidate.exact:
                continue
            outputs: list[list[list[int]]] = []
            valid = True
            for test in tests:
                grid = module.safe(candidate.function, module.as_grid(test["input"]))
                if grid is None:
                    valid = False
                    break
                outputs.append(module.freeze(grid))
            if not valid:
                continue
            signature = tuple(tuple(tuple(row) for row in grid) for grid in outputs)
            if signature in seen_programs:
                continue
            seen_programs.add(signature)
            programs.append((candidate, outputs))

        exact_program_counts.append(exact_program_count)
        unique_program_counts.append(len(programs))
        task_predictions: list[dict[str, list[list[int]]]] = []
        task_diagnostics: list[dict[str, Any]] = []

        for test_index, test in enumerate(tests):
            selected: list[tuple[list[list[int]], dict[str, Any]]] = []
            seen_grids: set[tuple[tuple[int, ...], ...]] = set()
            for candidate, outputs in programs:
                output = outputs[test_index]
                signature = tuple(tuple(row) for row in output)
                if signature in seen_grids:
                    continue
                seen_grids.add(signature)
                selected.append(
                    (
                        output,
                        {
                            "source": "exact_program",
                            "name": candidate.name,
                            "cost": candidate.cost,
                            "training_score": candidate.training_score,
                        },
                    )
                )
                if len(selected) == 2:
                    break

            identity = module.freeze(module.as_grid(test["input"]))
            crop = module.freeze(module.crop_nonbackground(module.as_grid(test["input"])))
            fallback_candidates = [
                (identity, "fallback_identity"),
                (crop, "fallback_crop"),
            ]
            for output, fallback_name in fallback_candidates:
                if len(selected) == 2:
                    break
                signature = tuple(tuple(row) for row in output)
                if signature in seen_grids:
                    continue
                seen_grids.add(signature)
                selected.append(
                    (output, {"source": "fallback", "name": fallback_name})
                )

            while len(selected) < 2:
                output = selected[0][0] if selected else identity
                selected.append(
                    (
                        output,
                        {"source": "fallback", "name": "fallback_duplicate"},
                    )
                )

            first_candidate_grids += selected[0][1]["source"] == "exact_program"
            second_candidate_grids += selected[1][1]["source"] == "exact_program"
            fallback_first_grids += selected[0][1]["source"] == "fallback"
            fallback_second_slots += selected[1][1]["source"] == "fallback"
            task_predictions.append(
                {"attempt_1": selected[0][0], "attempt_2": selected[1][0]}
            )
            task_diagnostics.append(
                {
                    "attempt_1": selected[0][1],
                    "attempt_2": selected[1][1],
                    "exact_program_count": exact_program_count,
                    "unique_exact_program_outputs": len(programs),
                }
            )

        submission[alias] = task_predictions
        diagnostics[alias] = task_diagnostics

    elapsed = time.perf_counter() - started
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    submission_path = output_dir / "submission.json"
    diagnostics_path = output_dir / "generator-diagnostics.json"
    manifest_path = output_dir / "run-manifest.json"
    write_json(submission_path, submission)
    write_json(diagnostics_path, diagnostics)
    manifest = {
        "schema": "arc2-v9-input-only-generator-run-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "cohort_path": str(args.input.resolve()),
        "cohort_sha256": sha256(args.input),
        "candidate_source_path": str(args.candidate_source.resolve()),
        "candidate_source_sha256": sha256(args.candidate_source),
        "generator_script_path": str(Path(__file__).resolve()),
        "generator_script_sha256": sha256(Path(__file__).resolve()),
        "labels_read": False,
        "runtime_inputs": "各課題の公開train入出力とtest inputのみ",
        "tasks": len(challenge),
        "test_grids": sum(len(task["test"]) for task in challenge.values()),
        "tasks_with_exact_program": sum(count > 0 for count in exact_program_counts),
        "exact_program_count_total": sum(exact_program_counts),
        "unique_exact_program_outputs_total": sum(unique_program_counts),
        "candidate_attempt_1_grids": first_candidate_grids,
        "candidate_attempt_2_grids": second_candidate_grids,
        "fallback_attempt_1_grids": fallback_first_grids,
        "fallback_attempt_2_slots": fallback_second_slots,
        "elapsed_seconds": round(elapsed, 6),
        "submission_path": str(submission_path),
        "submission_sha256": sha256(submission_path),
        "diagnostics_path": str(diagnostics_path),
        "diagnostics_sha256": sha256(diagnostics_path),
    }
    write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
