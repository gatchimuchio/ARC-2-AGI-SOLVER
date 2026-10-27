"""Compare generic vote-based priorities for object candidate families on LOO proposals."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "運用/証拠/ARC26-UNIFIED"
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
PROBE = EVIDENCE / "ARC2-object-palette-v24-probe-20261026.py"
BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v25-composite-palette-second-20261026"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_bundle(tasks: dict):
    with tempfile.TemporaryDirectory(prefix="arc2-v28-priority-") as temp_name:
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
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=900,
            check=False,
        )
        if process.returncode:
            raise RuntimeError(f"exact v25 bundle failed: {process.returncode}")
        predictions = json.loads((output_dir / "submission.json").read_text(encoding="utf-8"))
        audit = json.loads((output_dir / "submission_audit.json").read_text(encoding="utf-8"))
    return predictions, audit


def _valid(grid) -> bool:
    return (
        isinstance(grid, list)
        and bool(grid)
        and all(isinstance(row, list) and row for row in grid)
        and len({len(row) for row in grid}) == 1
        and all(type(cell) is int and 0 <= cell <= 9 for row in grid for cell in row)
    )


def _score(predictions: dict, proposals: list[dict], selector: str | None = None) -> dict:
    baseline_exact = selected_exact = changes = newly_correct = newly_wrong = 0
    comparable_slots = selected = 0
    for i, proposal in enumerate(proposals):
        key = f"fold_{i:05d}"
        result = predictions[key][0]
        first = result["attempt_1"]
        current_second = result["attempt_2"]
        chosen = current_second
        available = proposal["candidates"]
        if selector is not None and any(
            current_second == candidate["answer"] for candidate in available
        ):
            comparable_slots += 1
            if available:
                if selector == "fixed":
                    chosen = available[0]["answer"]
                elif selector == "max_votes":
                    chosen = max(
                        enumerate(available),
                        key=lambda item: (item[1]["top_votes"], -item[0]),
                    )[1]["answer"]
                elif selector == "vote_ratio":
                    chosen = max(
                        enumerate(available),
                        key=lambda item: (
                            item[1]["top_votes"] / max(1, item[1]["applicable_models"]),
                            item[1]["top_votes"],
                            -item[0],
                        ),
                    )[1]["answer"]
                else:
                    raise ValueError(selector)
                selected += chosen != current_second
        target = proposal["target"]
        before = first == target or current_second == target
        after = first == target or chosen == target
        baseline_exact += before
        selected_exact += after
        changes += chosen != current_second
        newly_correct += after and not before
        newly_wrong += before and not after
    return {
        "exact": selected_exact,
        "baseline_exact": baseline_exact,
        "delta": selected_exact - baseline_exact,
        "newly_correct": newly_correct,
        "newly_wrong": newly_wrong,
        "changed_attempt2": changes,
        "candidate_slots_compared": comparable_slots,
        "changed_candidate_slots": selected,
    }


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("arc2_v28_proposal_probe", PROBE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load proposal probe")
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)

    original_components = probe._components

    def extended_components(grid, connectivity, same_color):
        objects = original_components(grid, connectivity, same_color)
        for obj in objects:
            obj.update({
                "area_palette": (obj["area"], obj["palette"]),
                "box_palette": (obj["box"], obj["palette"]),
                "shape_palette": (obj["shape"], obj["palette"]),
                "aspect_palette": (obj["aspect"], obj["palette"]),
                "holes_palette": (obj["holes"], obj["palette"]),
                "perimeter_palette": (obj["perimeter"], obj["palette"]),
                "symmetry_palette": (obj["symmetry"], obj["palette"]),
                "shape_area": (obj["shape"], obj["area"]),
                "shape_box": (obj["shape"], obj["box"]),
                "shape_dominant_color": (obj["shape"], obj["dominant_color"]),
                "area_dominant_color": (obj["area"], obj["dominant_color"]),
                "shape_color_count": (obj["shape"], obj["color_count"]),
                "area_dominant_count": (obj["area"], obj["dominant_count"]),
            })
        return objects

    probe._components = extended_components
    probe.NEW_SELECTORS += tuple(
        f"{feature}:unique" for feature in (
            "area_palette", "box_palette", "shape_palette", "aspect_palette",
            "holes_palette", "perimeter_palette", "symmetry_palette",
            "shape_area", "shape_box", "shape_dominant_color",
            "area_dominant_color", "shape_color_count", "area_dominant_count",
        )
    )

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
                if not _valid(prediction) or prediction == held["input"]:
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

    if len(proposals) != 43:
        raise RuntimeError(f"composite proposal count drifted: {len(proposals)}")
    tasks = {
        f"fold_{i:05d}": {
            "train": proposal["teachers"],
            "test": [{"input": proposal["held_input"]}],
        }
        for i, proposal in enumerate(proposals)
    }
    predictions, audit = _run_bundle(tasks)

    # Read held-out answers only after every exact-bundle prediction is materialized.
    for proposal in proposals:
        task = json.loads(proposal["path"].read_text(encoding="utf-8"))
        proposal["target"] = task["train"][proposal["held_index"]]["output"]

    scores = {
        "current_v25": _score(predictions, proposals),
        "fixed_object_outlier_palette": _score(predictions, proposals, "fixed"),
        "max_absolute_votes": _score(predictions, proposals, "max_votes"),
        "max_vote_ratio": _score(predictions, proposals, "vote_ratio"),
    }
    report = {
        "schema": "arc2-candidate-priority-v28-probe-v1",
        "proposal_folds": len(proposals),
        "eligible_folds": eligible,
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
            "proposal_probe": _sha(PROBE),
            "v25_build_manifest": _sha(BUILD / "build-manifest.json"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
