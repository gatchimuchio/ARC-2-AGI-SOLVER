"""Compare v24/v25 exact bundles on public tasks with composite proposals."""
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
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE_V19 = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v19-local-context-second-20261026/full-runtime/submission.json"
PROBE = EVIDENCE / "ARC2-object-palette-v24-probe-20261026.py"
V24_BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v24-palette-second-20261026"
V25_BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v25-composite-palette-second-20261026"
V21_FULL_REPORT = EVIDENCE / "ARC2-v21.1-full-runtime-evaluation-20261026.json"
OUTPUT = Path(__file__).with_suffix(".json")
COMPOSITES = (
    "area_palette", "box_palette", "shape_palette", "aspect_palette",
    "holes_palette", "perimeter_palette", "symmetry_palette",
    "shape_area", "shape_box", "shape_dominant_color",
    "area_dominant_color", "shape_color_count", "area_dominant_count",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_bundle(build: Path, tasks: dict, prefix: str):
    with tempfile.TemporaryDirectory(prefix=prefix) as temp_name:
        temp = Path(temp_name)
        challenge_path = temp / "challenges.json"
        output_dir = temp / "output"
        challenge_path.write_text(
            json.dumps(tasks, ensure_ascii=False), encoding="utf-8"
        )
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
                str(challenge_path),
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
        if process.returncode:
            raise RuntimeError(f"{build.name} failed: {process.returncode}")
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
        correctness = [
            row["attempt_1"] == target or row["attempt_2"] == target
            for row, target in zip(rows, targets[task_id], strict=True)
        ]
        exact_examples += sum(correctness)
        exact_tasks += all(correctness)
    return {"exact_tasks": exact_tasks, "exact_examples": exact_examples}


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("arc2_v25_challenge_probe", PROBE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load object proposal probe")
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
    probe.NEW_SELECTORS = probe.NEW_SELECTORS + tuple(
        f"{feature}:unique" for feature in COMPOSITES
    )
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    old_attempt1 = json.loads(BASELINE_V19.read_text(encoding="utf-8"))
    selected = {}
    candidate_examples = 0
    for task_id, task in sorted(challenge.items()):
        models = probe._fit(task["train"])
        relevant = False
        for index, pair in enumerate(task["test"]):
            candidate, votes, _ = probe._candidate(models, pair["input"])
            if (
                candidate is not None
                and votes >= 2
                and candidate != old_attempt1[task_id][index]["attempt_1"]
            ):
                candidate_examples += 1
                relevant = True
        if relevant:
            selected[task_id] = {
                "train": task["train"],
                "test": [{"input": pair["input"]} for pair in task["test"]],
            }

    if selected:
        v24, v24_audit = _run_bundle(V24_BUILD, selected, "arc2-v24-composite-challenge-")
        v25, v25_audit = _run_bundle(V25_BUILD, selected, "arc2-v25-composite-challenge-")
    else:
        v24 = v25 = {}
        v24_audit = v25_audit = {"fallback_count": 0}

    targets = {
        path.stem: [
            pair["output"]
            for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])
        ]
        for path in SOURCE_ROOT.glob("*.json")
    }
    changed_examples = changed_attempt1 = changed_attempt2 = 0
    for task_id, rows in v25.items():
        for index, row in enumerate(rows):
            before = v24[task_id][index]
            changed_examples += row != before
            changed_attempt1 += row["attempt_1"] != before["attempt_1"]
            changed_attempt2 += row["attempt_2"] != before["attempt_2"]

    v24_score = _score(v24, targets)
    v25_score = _score(v25, targets)
    v21_full = json.loads(V21_FULL_REPORT.read_text(encoding="utf-8"))["v21.1_full_runtime"]
    delta_tasks = v25_score["exact_tasks"] - v24_score["exact_tasks"]
    delta_examples = v25_score["exact_examples"] - v24_score["exact_examples"]
    report = {
        "schema": "arc2-object-composite-palette-v25-bundle-challenge-v1",
        "public_challenge_tasks": len(challenge),
        "public_challenge_examples": sum(len(task["test"]) for task in challenge.values()),
        "composite_candidate_examples_distinct_from_v19_attempt1": candidate_examples,
        "tasks_with_possible_composite_changes": len(selected),
        "examples_run_from_both_exact_bundles": sum(
            len(task["test"]) for task in selected.values()
        ),
        "v24_subset_score": v24_score,
        "v25_subset_score": v25_score,
        "changed_examples": changed_examples,
        "changed_attempt1_examples": changed_attempt1,
        "changed_attempt2_examples": changed_attempt2,
        "v24_bundle_fallbacks": v24_audit.get("fallback_count"),
        "v25_bundle_fallbacks": v25_audit.get("fallback_count"),
        "projected_full_challenge_v24_baseline": v21_full,
        "projected_full_challenge_v25": {
            "exact_tasks": v21_full["exact_tasks"] + delta_tasks,
            "exact_examples": v21_full["exact_examples"] + delta_examples,
        },
        "projected_delta": {
            "exact_tasks": delta_tasks,
            "exact_examples": delta_examples,
        },
        "runtime_received_test_targets": False,
        "targets_read_after_both_exact_bundle_outputs": True,
        "temporary_subset_outputs_and_payloads_removed": True,
        "task_predictions_or_targets_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "probe": _sha(PROBE),
            "challenge": _sha(CHALLENGE),
            "baseline_v19": _sha(BASELINE_V19),
            "v21.1_full_report": _sha(V21_FULL_REPORT),
            "v24_build_manifest": _sha(V24_BUILD / "build-manifest.json"),
            "v25_build_manifest": _sha(V25_BUILD / "build-manifest.json"),
        },
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
