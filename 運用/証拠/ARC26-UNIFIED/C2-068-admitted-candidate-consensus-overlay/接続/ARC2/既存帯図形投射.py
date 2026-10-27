"""旧資産の色帯対応と下端整列投射。2関数は出典ASTと一致。"""
from __future__ import annotations
from typing import Any
from collections import Counter
from .既存凡例穴対応 import grid_shape,bbox_to_list
from .既存辺対応抽出 import dominant_background
from .既存物体特徴 import color_components
Grid=list[list[int]]
def horizontal_band_glyph_bands(grid: Grid) -> list[dict[str, int]]:
    if not grid or not grid[0]:
        return []
    height, width = grid_shape(grid)
    if width < 5:
        return []
    background = dominant_background(grid)
    band_rows: list[dict[str, int]] = []
    for row_index, row in enumerate(grid):
        edge_color = row[0]
        if edge_color == background or row[-1] != edge_color:
            continue
        interior = row[1:-1]
        fill_counts = Counter(interior)
        fill_color, fill_count = fill_counts.most_common(1)[0]
        if fill_color == background or fill_color == edge_color:
            continue
        if fill_count != width - 2:
            continue
        band_rows.append(
            {
                "row": row_index,
                "fill_color": int(fill_color),
                "edge_color": int(edge_color),
            }
        )

    bands: list[dict[str, int]] = []
    index = 0
    while index < len(band_rows):
        first = band_rows[index]
        last_index = index
        while (
            last_index + 1 < len(band_rows)
            and band_rows[last_index + 1]["row"] == band_rows[last_index]["row"] + 1
            and band_rows[last_index + 1]["fill_color"] == first["fill_color"]
            and band_rows[last_index + 1]["edge_color"] == first["edge_color"]
        ):
            last_index += 1
        row_min = first["row"]
        row_max = band_rows[last_index]["row"]
        if row_max - row_min + 1 >= 3:
            bands.append(
                {
                    "row_min": row_min,
                    "row_max": row_max,
                    "fill_color": first["fill_color"],
                    "edge_color": first["edge_color"],
                }
            )
        index = last_index + 1
    fill_colors = [band["fill_color"] for band in bands]
    if len(fill_colors) != len(set(fill_colors)):
        return []
    return bands

def render_horizontal_band_glyph_projector(grid: Grid) -> tuple[Grid | None, dict[str, Any]]:
    if not grid or not grid[0]:
        return None, {"failure": "empty_grid"}
    height, width = grid_shape(grid)
    background = dominant_background(grid)
    bands = horizontal_band_glyph_bands(grid)
    if not bands:
        return None, {"failure": "no_horizontal_band_glyph_bands"}
    band_rows = {
        row
        for band in bands
        for row in range(band["row_min"], band["row_max"] + 1)
    }
    output = [
        [grid[row][col] if row in band_rows else background for col in range(width)]
        for row in range(height)
    ]
    source_component_records: list[dict[str, Any]] = []
    projected_cell_count = 0
    for band in bands:
        fill_color = band["fill_color"]
        edge_color = band["edge_color"]
        band_height = band["row_max"] - band["row_min"] + 1
        for component in color_components(grid, fill_color, include_diagonal=False):
            row_min, col_min, row_max, col_max = component["bbox"]
            if any(row in band_rows for row, _ in component["cells"]):
                continue
            if row_max >= band["row_min"]:
                continue
            component_height = row_max - row_min + 1
            if component_height > band_height:
                return None, {
                    "failure": "band_glyph_source_taller_than_band",
                    "source_bbox": bbox_to_list(component["bbox"]),
                    "band": band,
                }
            target_row_min = band["row_max"] - component_height + 1
            for row, col in component["cells"]:
                target_row = target_row_min + row - row_min
                if not (band["row_min"] <= target_row <= band["row_max"] and 0 <= col < width):
                    return None, {
                        "failure": "band_glyph_projection_out_of_bounds",
                        "source_cell": [row, col],
                        "target_cell": [target_row, col],
                    }
                output[target_row][col] = edge_color
                projected_cell_count += 1
            source_component_records.append(
                {
                    "fill_color": fill_color,
                    "edge_color": edge_color,
                    "source_bbox": bbox_to_list(component["bbox"]),
                    "target_bbox": [
                        target_row_min,
                        col_min,
                        target_row_min + component_height - 1,
                        col_max,
                    ],
                    "cell_count": component["size"],
                }
            )

    if not source_component_records:
        return None, {"failure": "no_band_glyph_source_components", "band_count": len(bands)}
    if output == grid:
        return None, {"failure": "horizontal_band_glyph_no_change"}
    return output, {
        "renderer_case": "horizontal_band_glyph_projector",
        "band_glyph_band_count": len(bands),
        "band_glyph_source_component_count": len(source_component_records),
        "band_glyph_projected_cell_count": projected_cell_count,
        "bands": [dict(band) for band in bands],
        "source_component_records": source_component_records,
    }
