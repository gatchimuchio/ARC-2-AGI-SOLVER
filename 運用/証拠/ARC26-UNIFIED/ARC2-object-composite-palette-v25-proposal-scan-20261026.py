"""Count generic composite object-selector LOO proposals across ARC2 training."""
from __future__ import annotations

from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "運用/証拠/ARC26-UNIFIED"
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
PROBE = EVIDENCE / "ARC2-object-palette-v24-probe-20261026.py"
OUTPUT = Path(__file__).with_suffix(".json")
COMPOSITES = (
    "area_palette", "box_palette", "shape_palette", "aspect_palette",
    "holes_palette", "perimeter_palette", "symmetry_palette",
    "shape_area", "shape_box", "shape_dominant_color",
    "area_dominant_color", "shape_color_count", "area_dominant_count",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("arc2_v25_proposal_scan", PROBE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load palette probe")
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
    eligible = proposals = 0
    vote_counts: Counter[str] = Counter()
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
                proposals += 1
                vote_counts[str(votes)] += 1

    report = {
        "schema": "arc2-object-composite-palette-v25-proposal-scan-v1",
        "eligible_folds": eligible,
        "composite_feature_pairs": list(COMPOSITES),
        "proposal_folds": proposals,
        "proposal_vote_count_distribution": dict(sorted(vote_counts.items())),
        "heldout_outputs_passed_to_candidate_generator": False,
        "targets_used_for_scoring": False,
        "fold_ids_predictions_or_targets_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "palette_probe": _sha(PROBE),
        },
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
