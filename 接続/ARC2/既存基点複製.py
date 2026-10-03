"""既存の同色基点と単点配置によるmotif展開。"""
from __future__ import annotations
from typing import Any
import math
from .既存凡例穴対応 import grid_shape,bbox_to_list
from .既存辺対応抽出 import dominant_background
from .既存物体特徴 import color_components
from .既存領域転写 import bbox_shape_for_bbox
Grid=list[list[int]]
Cell=tuple[int,int]

def component_shape(component: dict[str, Any]) -> tuple[int, int]:
    return bbox_shape_for_bbox(component["bbox"])

def render_anchored_singleton_motif_tiler(grid: Grid) -> tuple[Grid | None, dict[str, Any]]:
    if not grid or not grid[0]:
        return None, {"failure": "empty_grid"}

    height, width = grid_shape(grid)
    background = dominant_background(grid)
    colors = sorted({value for row in grid for value in row if value != background})
    candidate_records: list[tuple[Grid, dict[str, Any]]] = []

    for source_color in colors:
        source_components = color_components(grid, source_color, include_diagonal=True)
        motif_components = [component for component in source_components if component["size"] > 1]
        anchor_components = [component for component in source_components if component["size"] == 1]
        if len(motif_components) != 1 or len(anchor_components) != 1:
            continue
        motif_component = motif_components[0]
        anchor_cell = next(iter(anchor_components[0]["cells"]))
        motif_height, motif_width = component_shape(motif_component)
        source_row0, source_col0, _, _ = motif_component["bbox"]
        motif_cells = {
            (row - source_row0, col - source_col0)
            for row, col in motif_component["cells"]
        }

        for marker_color in colors:
            if marker_color == source_color:
                continue
            marker_components = color_components(grid, marker_color, include_diagonal=True)
            marker_cells: list[Cell] = []
            marker_components_supported = True
            for component in marker_components:
                if component["size"] != 1:
                    marker_components_supported = False
                    break
                marker_cells.append(next(iter(component["cells"])))
            if not marker_components_supported or not marker_cells:
                continue

            row_step = 0
            col_step = 0
            for marker_row, marker_col in marker_cells:
                row_delta = abs(marker_row - anchor_cell[0])
                col_delta = abs(marker_col - anchor_cell[1])
                if row_delta:
                    row_step = math.gcd(row_step, row_delta)
                if col_delta:
                    col_step = math.gcd(col_step, col_delta)
            if row_step == 0:
                row_step = 1
            if col_step == 0:
                col_step = 1

            output = [[background for _ in range(width)] for _ in range(height)]
            for motif_row, motif_col in motif_cells:
                output[source_row0 + motif_row][source_col0 + motif_col] = marker_color

            placements: list[list[int]] = []
            collision = None
            unsupported_scale = None
            for marker_row, marker_col in sorted(marker_cells):
                row_delta = marker_row - anchor_cell[0]
                col_delta = marker_col - anchor_cell[1]
                scaled_row = row_delta * motif_height
                scaled_col = col_delta * motif_width
                if scaled_row % row_step != 0 or scaled_col % col_step != 0:
                    unsupported_scale = {
                        "marker_cell": [marker_row, marker_col],
                        "row_delta": row_delta,
                        "col_delta": col_delta,
                        "row_step": row_step,
                        "col_step": col_step,
                        "motif_shape": [motif_height, motif_width],
                    }
                    break
                target_row0 = source_row0 + scaled_row // row_step
                target_col0 = source_col0 + scaled_col // col_step
                if (
                    target_row0 < 0
                    or target_col0 < 0
                    or target_row0 + motif_height > height
                    or target_col0 + motif_width > width
                ):
                    collision = {
                        "failure": "anchored_motif_placement_oob",
                        "marker_cell": [marker_row, marker_col],
                        "target_top_left": [target_row0, target_col0],
                        "motif_shape": [motif_height, motif_width],
                    }
                    break
                placements.append([target_row0, target_col0])
                for motif_row, motif_col in motif_cells:
                    output_row = target_row0 + motif_row
                    output_col = target_col0 + motif_col
                    existing = output[output_row][output_col]
                    if existing not in {background, source_color}:
                        collision = {
                            "failure": "anchored_motif_collision",
                            "cell": [output_row, output_col],
                            "existing": existing,
                            "incoming": source_color,
                        }
                        break
                    output[output_row][output_col] = source_color
                if collision:
                    break
            if unsupported_scale:
                continue
            if collision:
                continue
            if output == grid:
                continue
            candidate_records.append(
                (
                    output,
                    {
                        "renderer_case": "anchored_singleton_motif_tiler",
                        "background": background,
                        "anchored_source_color": source_color,
                        "anchored_marker_color": marker_color,
                        "anchored_source_bbox": bbox_to_list(motif_component["bbox"]),
                        "anchored_anchor_cell": [anchor_cell[0], anchor_cell[1]],
                        "anchored_motif_shape": [motif_height, motif_width],
                        "anchored_row_step": row_step,
                        "anchored_col_step": col_step,
                        "anchored_marker_count": len(marker_cells),
                        "anchored_placement_count": len(placements),
                        "anchored_placements": placements,
                    },
                )
            )

    unique_outputs: dict[tuple[tuple[int, ...], ...], tuple[Grid, dict[str, Any]]] = {}
    for output, record in candidate_records:
        key = tuple(tuple(row) for row in output)
        unique_outputs[key] = (output, record)
    if len(unique_outputs) != 1:
        return None, {
            "failure": "anchored_singleton_motif_candidate_not_unique",
            "candidate_count": len(candidate_records),
            "unique_output_count": len(unique_outputs),
        }
    return next(iter(unique_outputs.values()))
