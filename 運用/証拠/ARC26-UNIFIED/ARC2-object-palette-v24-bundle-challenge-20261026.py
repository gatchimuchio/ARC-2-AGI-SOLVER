"""Run v21.1 and v24 bundles on all public tasks with relevant proposals."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "運用/証拠/ARC26-UNIFIED"
PROBE = EVIDENCE / "ARC2-object-palette-v24-probe-20261026.py"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v19-local-context-second-20261026/full-runtime/submission.json"
V21_BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v21.1-object-outlier-second-20261026"
V24_BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v24-palette-second-20261026"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(build: Path, tasks: dict, prefix: str):
    with tempfile.TemporaryDirectory(prefix=prefix) as temp_name:
        temp = Path(temp_name)
        subset = temp / "challenges.json"
        output_dir = temp / "output"
        subset.write_text(json.dumps(tasks, ensure_ascii=False), encoding="utf-8")
        environment = {
            **os.environ,
            "PYTHONUTF8": "1",
            "ARC2_PAYLOAD_ROOT": str(temp / "payload"),
        }
        process = subprocess.run(
            [
                sys.executable,
                str(build / "solve.py"),
                "--challenges",
                str(subset),
                "--output-dir",
                str(output_dir),
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
            check=False,
        )
        if process.returncode:
            raise RuntimeError(f"{build.name} failed: exit={process.returncode}")
        predictions = json.loads(
            (output_dir / "submission.json").read_text(encoding="utf-8")
        )
        audit = json.loads(
            (output_dir / "submission_audit.json").read_text(encoding="utf-8")
        )
        return predictions, audit


def _score(predictions, targets):
    exact_examples = exact_tasks = 0
    for task_id, rows in predictions.items():
        correct = [
            row["attempt_1"] == target or row["attempt_2"] == target
            for row, target in zip(rows, targets[task_id], strict=True)
        ]
        exact_examples += sum(correct)
        exact_tasks += all(correct)
    return {"exact_tasks": exact_tasks, "exact_examples": exact_examples}


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("arc2_v24_probe", PROBE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load palette probe")
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    from 接続.ARC2.物体抽出候補 import ObjectExtractionCandidate

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    selected = {}
    palette_candidate_examples = palette_already_attempt2 = 0
    for task_id, task in sorted(challenge.items()):
        model = ObjectExtractionCandidate(task["train"])
        palette_models = probe._fit(task["train"])
        relevant = False
        for index, pair in enumerate(task["test"]):
            first, second = (
                baseline[task_id][index]["attempt_1"],
                baseline[task_id][index]["attempt_2"],
            )
            old, _ = model.candidate(pair["input"])
            if old is not None and old != first:
                relevant = True
            existing, _ = model.outlier_candidate(pair["input"])
            if existing is not None and existing != first:
                relevant = True
            palette, votes, _ = probe._candidate(palette_models, pair["input"])
            if palette is not None and votes >= 2 and palette != first:
                palette_candidate_examples += 1
                relevant = True
                palette_already_attempt2 += palette == second
        if relevant:
            selected[task_id] = {
                "train": task["train"],
                "test": [{"input": pair["input"]} for pair in task["test"]],
            }

    v21, v21_audit = _run(V21_BUILD, selected, "arc2-v21.1-palette-")
    v24, v24_audit = _run(V24_BUILD, selected, "arc2-v24-palette-")
    targets = {
        path.stem: [
            pair["output"]
            for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])
        ]
        for path in SOURCE_ROOT.glob("*.json")
    }
    changed_examples = changed_attempt1 = changed_attempt2 = 0
    for task_id, rows in v24.items():
        for index, row in enumerate(rows):
            old = v21[task_id][index]
            changed_examples += row != old
            changed_attempt1 += row["attempt_1"] != old["attempt_1"]
            changed_attempt2 += row["attempt_2"] != old["attempt_2"]

    v21_manifest = json.loads(
        (V21_BUILD / "build-manifest.json").read_text(encoding="utf-8")
    )
    v24_manifest = json.loads(
        (V24_BUILD / "build-manifest.json").read_text(encoding="utf-8")
    )
    report = {
        "schema": "arc2-object-palette-v24-bundle-challenge-v1",
        "public_challenge_tasks": len(challenge),
        "public_challenge_examples": sum(len(task["test"]) for task in challenge.values()),
        "tasks_run_from_both_bundles": len(selected),
        "examples_run_from_both_bundles": sum(len(task["test"]) for task in selected.values()),
        "palette_candidate_examples": palette_candidate_examples,
        "palette_candidates_already_in_v19_attempt2": palette_already_attempt2,
        "v21.1_subset_score": _score(v21, targets),
        "v24_subset_score": _score(v24, targets),
        "changed_examples": changed_examples,
        "changed_attempt1_examples": changed_attempt1,
        "changed_attempt2_examples": changed_attempt2,
        "v21.1_bundle_fallbacks": v21_audit.get("fallback_count"),
        "v24_bundle_fallbacks": v24_audit.get("fallback_count"),
        "runtime_received_targets": False,
        "targets_read_after_both_bundle_outputs": True,
        "temporary_subset_outputs_and_payloads_removed": True,
        "per_task_predictions_or_targets_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "probe": _sha(PROBE),
            "challenge": _sha(CHALLENGE),
            "baseline_v19": _sha(BASELINE),
            "v21.1_build_manifest": _sha(V21_BUILD / "build-manifest.json"),
            "v24_build_manifest": _sha(V24_BUILD / "build-manifest.json"),
        },
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
