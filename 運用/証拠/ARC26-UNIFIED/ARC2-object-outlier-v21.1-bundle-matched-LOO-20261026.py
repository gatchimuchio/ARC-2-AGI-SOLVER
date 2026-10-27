"""Exact-bundle paired LOO for v20 and v21.1 on v21 proposal folds."""
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
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
PROBE = EVIDENCE / "ARC2-object-outlier-v21-probe-20261026.py"
V20_BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v20-object-extraction-second-20261026"
V21_BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v21.1-object-outlier-second-20261026"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _proposals(probe):
    folds = []
    eligible = 0
    for path in sorted(SOURCE_ROOT.glob("*.json")):
        task = json.loads(path.read_text(encoding="utf-8"))
        pairs = task.get("train", [])
        if len(pairs) < 3:
            continue
        for held_index, held in enumerate(pairs):
            eligible += 1
            teachers = [
                pair for index, pair in enumerate(pairs) if index != held_index
            ]
            candidate, votes, _ = probe._candidate(
                probe._fit(teachers), held["input"]
            )
            if candidate is not None and votes >= 2 and candidate != held["input"]:
                folds.append((teachers, held["input"], held["output"]))
    return eligible, folds


def _run_bundle(build: Path, tasks: dict, prefix: str):
    with tempfile.TemporaryDirectory(prefix=prefix) as temp_name:
        temp = Path(temp_name)
        subset_path = temp / "challenges.json"
        output_dir = temp / "output"
        payload_root = temp / "payload"
        subset_path.write_text(
            json.dumps(tasks, ensure_ascii=False), encoding="utf-8"
        )
        environment = {
            **os.environ,
            "PYTHONUTF8": "1",
            "ARC2_PAYLOAD_ROOT": str(payload_root),
        }
        process = subprocess.run(
            [
                sys.executable,
                str(build / "solve.py"),
                "--challenges",
                str(subset_path),
                "--output-dir",
                str(output_dir),
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=900,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(
                f"{build.name} failed with exit {process.returncode}"
            )
        predictions = json.loads(
            (output_dir / "submission.json").read_text(encoding="utf-8")
        )
        audit = json.loads(
            (output_dir / "submission_audit.json").read_text(encoding="utf-8")
        )
        return predictions, audit


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))
    spec = importlib.util.spec_from_file_location("arc2_v21_probe", PROBE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load proposal runner")
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    eligible, folds = _proposals(probe)
    if len(folds) != 41:
        raise RuntimeError(f"proposal fold count drifted: {len(folds)}")

    tasks = {
        f"fold_{index:05d}": {
            "train": teachers,
            "test": [{"input": held_input}],
        }
        for index, (teachers, held_input, _) in enumerate(folds)
    }
    v20, v20_audit = _run_bundle(V20_BUILD, tasks, "arc2-v20-loo-")
    v21, v21_audit = _run_bundle(V21_BUILD, tasks, "arc2-v21-loo-")

    base_exact = candidate_exact = applied = newly_correct = newly_wrong = 0
    for index, (_, _, target) in enumerate(folds):
        key = f"fold_{index:05d}"
        before = v20[key][0]
        after = v21[key][0]
        before_exact = before["attempt_1"] == target or before["attempt_2"] == target
        after_exact = after["attempt_1"] == target or after["attempt_2"] == target
        base_exact += before_exact
        candidate_exact += after_exact
        applied += after["attempt_2"] != before["attempt_2"]
        newly_correct += after_exact and not before_exact
        newly_wrong += before_exact and not after_exact

    v20_manifest = json.loads(
        (V20_BUILD / "build-manifest.json").read_text(encoding="utf-8")
    )
    v21_manifest = json.loads(
        (V21_BUILD / "build-manifest.json").read_text(encoding="utf-8")
    )
    report = {
        "schema": "arc2-object-outlier-v21.1-bundle-matched-loo-v1",
        "eligible_folds": eligible,
        "candidate_proposal_folds": len(folds),
        "v20_bundle_evaluation_folds": len(v20),
        "v21_bundle_evaluation_folds": len(v21),
        "v20_bundle_fallbacks": v20_audit.get("fallback_count"),
        "v21_bundle_fallbacks": v21_audit.get("fallback_count"),
        "v20_bundle_exact_on_proposals": base_exact,
        "v21_bundle_exact_on_proposals": candidate_exact,
        "attempt2_changes": applied,
        "newly_correct": newly_correct,
        "newly_wrong": newly_wrong,
        "net_delta": candidate_exact - base_exact,
        "regressions": newly_wrong,
        "heldout_outputs_passed_to_candidate_generator_or_runtimes": False,
        "per_fold_predictions_or_targets_saved": False,
        "temporary_fold_inputs_outputs_and_payloads_removed": True,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "proposal_runner": _sha(PROBE),
            "v20_build_manifest": _sha(V20_BUILD / "build-manifest.json"),
            "v21_build_manifest": _sha(V21_BUILD / "build-manifest.json"),
            "adapter": _sha(ROOT / "接続/ARC2/Kaggle提出.py"),
            "object_extraction_module": _sha(ROOT / "接続/ARC2/物体抽出候補.py"),
        },
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
