"""Validate vote-based object-family priority on non-composite palette LOO proposals."""
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
PROBE = EVIDENCE / "ARC2-object-palette-v24-probe-20261026.py"
POLICY = EVIDENCE / "ARC2-candidate-priority-v28-probe-20261026.py"
BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v25-composite-palette-second-20261026"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_bundle(tasks: dict):
    with tempfile.TemporaryDirectory(prefix="arc2-v28-independent-") as temp_name:
        temp = Path(temp_name)
        challenge_path = temp / "challenges.json"
        output_dir = temp / "output"
        challenge_path.write_text(json.dumps(tasks, ensure_ascii=False), encoding="utf-8")
        process = subprocess.run(
            [
                sys.executable,
                str(BUILD / "solve.py"),
                "--challenges",
                str(challenge_path),
                "--output-dir",
                str(output_dir),
            ],
            cwd=ROOT,
            env={**os.environ, "PYTHONUTF8": "1", "ARC2_PAYLOAD_ROOT": str(temp / "payload")},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
            check=False,
        )
        if process.returncode:
            raise RuntimeError(f"exact v25 bundle failed: {process.returncode}")
        predictions = json.loads((output_dir / "submission.json").read_text(encoding="utf-8"))
        audit = json.loads((output_dir / "submission_audit.json").read_text(encoding="utf-8"))
    return predictions, audit


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    probe = _load("arc2_v28_independent_probe", PROBE)
    policy = _load("arc2_v28_priority_policy", POLICY)
    from 接続.ARC2.物体抽出候補 import ObjectExtractionCandidate

    proposals = []
    eligible = 0
    for path in sorted(SOURCE_ROOT.glob("*.json")):
        task = json.loads(path.read_text(encoding="utf-8"))
        pairs = task.get("train", [])
        if len(pairs) < 3:
            continue
        for held_index, held in enumerate(pairs):
            eligible += 1
            teachers = [pair for index, pair in enumerate(pairs) if index != held_index]
            candidate, votes, _ = probe._candidate(probe._fit(teachers), held["input"])
            if candidate is None or votes < 2 or candidate == held["input"]:
                continue
            object_candidates = ObjectExtractionCandidate(teachers)
            raw = [
                object_candidates.candidate(held["input"]),
                object_candidates.outlier_candidate(held["input"]),
                object_candidates.palette_candidate(held["input"]),
            ]
            available = []
            for family, (prediction, record) in zip(("object", "outlier", "palette"), raw):
                if not policy._valid(prediction) or prediction == held["input"]:
                    continue
                available.append({
                    "family": family,
                    "answer": prediction,
                    "top_votes": int(record.get("top_votes", 0)),
                    "applicable_models": int(record.get("applicable_models", 0)),
                })
            proposals.append({
                "path": path,
                "held_index": held_index,
                "teachers": teachers,
                "held_input": held["input"],
                "candidates": available,
            })
    if len(proposals) != 40:
        raise RuntimeError(f"independent base-palette proposal count drifted: {len(proposals)}")

    tasks = {
        f"fold_{i:05d}": {
            "train": proposal["teachers"],
            "test": [{"input": proposal["held_input"]}],
        }
        for i, proposal in enumerate(proposals)
    }
    predictions, audit = _run_bundle(tasks)

    # Read held-out answers only after exact-bundle outputs have been materialized.
    for proposal in proposals:
        task = json.loads(proposal["path"].read_text(encoding="utf-8"))
        proposal["target"] = task["train"][proposal["held_index"]]["output"]
    scores = {
        "current_v25": policy._score(predictions, proposals),
        "fixed_object_outlier_palette": policy._score(predictions, proposals, "fixed"),
        "max_absolute_votes": policy._score(predictions, proposals, "max_votes"),
        "max_vote_ratio": policy._score(predictions, proposals, "vote_ratio"),
    }
    report = {
        "schema": "arc2-candidate-priority-v28-independent-v1",
        "proposal_folds": len(proposals),
        "eligible_folds": eligible,
        "proposal_selector_set": "base palette selectors only; composite selectors excluded",
        "exact_bundle": "v25-composite-palette-second-20261026",
        "bundle_fallbacks": audit.get("fallback_count"),
        "scores": scores,
        "candidate_outputs_use_heldout_outputs": False,
        "heldout_outputs_read_after_exact_bundle_outputs": True,
        "fold_ids_predictions_or_targets_saved": False,
        "temporary_inputs_outputs_and_payloads_removed": True,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "priority_runner": _sha(POLICY),
            "proposal_probe": _sha(PROBE),
            "v25_build_manifest": _sha(BUILD / "build-manifest.json"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
