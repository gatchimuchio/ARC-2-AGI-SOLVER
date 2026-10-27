"""Paired LOO probe requiring support examples to vary omitted conditions.

The public-training runner, HDS sources, task eligibility, and minimum support
remain unchanged. A partial-condition prediction is allowed only when its
unanimous supporting examples cover at least two values for every omitted
condition coordinate. Aggregate diagnostics are saved without task IDs/grids.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE_RUNNER = (
    ROOT
    / "運用/証拠/ARC26-UNIFIED/"
    / "P5_HDS_partial_condition_consensus_visible_guard_LOO.py"
)
OMITTED_COORDINATE_MINIMUM_VALUES = 2

spec = importlib.util.spec_from_file_location(
    "arc2_variation_coverage_loo_base", BASE_RUNNER
)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load the preserved support-three runner")
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


class DiagnosticCounts(dict):
    """Accumulate per-fold counters when the base runner clears its mapping."""

    def __init__(self):
        super().__init__()
        self.completed_partial_projections = 0
        self.rejected_for_missing_variation = 0

    def clear(self):
        self.completed_partial_projections += self.get(
            "partial_projection_support_passed_before_variation", 0
        )
        self.rejected_for_missing_variation += self.get(
            "partial_projection_rejected_no_omitted_variation", 0
        )
        super().clear()


diagnostics = DiagnosticCounts()
runner.候補計数 = diagnostics


def 部分条件合意_異値被覆(原理, 写像):
    条件経路群 = tuple(原理.条件経路群)
    if not 条件経路群:
        return None

    可視添字 = tuple(i for i, path in enumerate(条件経路群) if path in 写像)
    if not 可視添字:
        return None
    可視値 = {i: runner.適応模块.値キー(写像[条件経路群[i]]) for i in 可視添字}
    if len(可視添字) < len(条件経路群):
        投影添字群 = (可視添字,)
    else:
        投影添字群 = tuple(
            tuple(i for i in range(len(条件経路群)) if i != dropped)
            for dropped in range(len(条件経路群))
        )

    条件記録別 = {}
    for 条件値群, 出力値 in 原理.対応値表:
        条件キー = tuple(条件値群)
        if 条件キー in 条件記録別:
            if runner.適応模块.値キー(条件記録別[条件キー]) != runner.適応模块.値キー(出力値):
                return None
        else:
            条件記録別[条件キー] = 出力値

    候補値群 = []
    for 投影添字 in 投影添字群:
        一致記録 = [
            (条件値群, 出力値)
            for 条件値群, 出力値 in 条件記録別.items()
            if len(条件値群) == len(条件経路群)
            and all(条件値群[i] == 可視値[i] for i in 投影添字)
        ]
        if len(一致記録) < runner.SUPPORT_MINIMUM:
            continue
        出力キー群 = {runner.適応模块.値キー(output) for _, output in 一致記録}
        if len(出力キー群) != 1:
            return None

        diagnostics["partial_projection_support_passed_before_variation"] = (
            diagnostics.get("partial_projection_support_passed_before_variation", 0) + 1
        )
        除外添字群 = tuple(i for i in range(len(条件経路群)) if i not in 投影添字)
        if any(
            len({条件値群[i] for 条件値群, _ in 一致記録})
            < OMITTED_COORDINATE_MINIMUM_VALUES
            for i in 除外添字群
        ):
            diagnostics["partial_projection_rejected_no_omitted_variation"] = (
                diagnostics.get("partial_projection_rejected_no_omitted_variation", 0) + 1
            )
            continue
        候補値群.append(一致記録[0][1])

    if not 候補値群:
        return None
    if len({runner.適応模块.値キー(value) for value in 候補値群}) != 1:
        return None
    return 候補値群[0]


runner.部分条件合意 = 部分条件合意_異値被覆


def _add_metadata(output_path: Path) -> None:
    diagnostics.completed_partial_projections += diagnostics.get(
        "partial_projection_support_passed_before_variation", 0
    )
    diagnostics.rejected_for_missing_variation += diagnostics.get(
        "partial_projection_rejected_no_omitted_variation", 0
    )
    result = json.loads(output_path.read_text(encoding="utf-8"))
    result["partial_condition_variation_gate"] = {
        "effective_minimum_support_mappings": runner.SUPPORT_MINIMUM,
        "minimum_distinct_values_per_omitted_coordinate": OMITTED_COORDINATE_MINIMUM_VALUES,
        "qualifying_projection_count_before_variation_gate": diagnostics.completed_partial_projections,
        "projection_rejections_for_missing_omitted_variation": diagnostics.rejected_for_missing_variation,
    }
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    runner.main()
    try:
        output_argument = sys.argv[sys.argv.index("--output") + 1]
    except (ValueError, IndexError) as exc:
        raise SystemExit("runner requires --output <path>") from exc
    _add_metadata(Path(output_argument))
