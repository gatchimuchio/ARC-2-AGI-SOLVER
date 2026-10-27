"""既存の混色motifと単色layout maskによる積配置。"""
from __future__ import annotations
from typing import Any
from .既存凡例穴対応 import grid_shape,bbox_to_list
from .既存辺対応抽出 import dominant_background
from .既存領域転写 import mixed_region_dicts_for_grid
Grid=list[list[int]]
BBox=tuple[int,int,int,int]

def foreground_mixed_components(
    grid: Grid,
    background: int,
    include_diagonal: bool = True,
) -> list[dict[str, Any]]:
    return mixed_region_dicts_for_grid(
        grid,
        int(background),
        include_diagonal=include_diagonal,
    )

def crop_bbox(grid: Grid, bbox: BBox) -> Grid:
    row0, col0, row1, col1 = bbox
    return [row[col0 : col1 + 1] for row in grid[row0 : row1 + 1]]

def render_layout_mask_macro_tile_expander(grid: Grid) -> tuple[Grid | None, dict[str, Any]]:
    if not grid or not grid[0]:
        return None, {"failure": "empty_grid"}

    background = dominant_background(grid)
    components = foreground_mixed_components(grid, background)
    if len(components) != 2:
        return None, {
            "failure": "macro_tile_foreground_component_count_not_two",
            "foreground_component_count": len(components),
        }

    valid_pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for motif in components:
        motif_colors = set(motif["colors"])
        if len(motif_colors) < 2:
            continue
        for layout in components:
            if layout is motif:
                continue
            layout_colors = set(layout["colors"])
            if len(layout_colors) != 1:
                continue
            layout_color = next(iter(layout_colors))
            if layout_color in motif_colors:
                continue
            valid_pairs.append((motif, layout))

    if len(valid_pairs) != 1:
        return None, {
            "failure": "macro_tile_pair_not_unique",
            "valid_pair_count": len(valid_pairs),
            "foreground_component_count": len(components),
        }

    motif, layout = valid_pairs[0]
    layout_color = int(layout["colors"][0])
    motif_grid = crop_bbox(grid, motif["bbox"])
    layout_grid = crop_bbox(grid, layout["bbox"])
    tile_height, tile_width = grid_shape(motif_grid)
    layout_height, layout_width = grid_shape(layout_grid)
    output_height = tile_height * layout_height
    output_width = tile_width * layout_width
    if output_height > 30 or output_width > 30:
        return None, {
            "failure": "macro_tile_output_exceeds_arc_limit",
            "macro_tile_shape": [tile_height, tile_width],
            "macro_layout_shape": [layout_height, layout_width],
            "macro_tiled_shape": [output_height, output_width],
        }

    output = [[background for _ in range(output_width)] for _ in range(output_height)]
    active_cell_count = 0
    for layout_row, row_values in enumerate(layout_grid):
        for layout_col, value in enumerate(row_values):
            if value != layout_color:
                continue
            active_cell_count += 1
            output_row0 = layout_row * tile_height
            output_col0 = layout_col * tile_width
            for tile_row, motif_values in enumerate(motif_grid):
                for tile_col, motif_value in enumerate(motif_values):
                    output[output_row0 + tile_row][output_col0 + tile_col] = motif_value

    if active_cell_count == 0:
        return None, {"failure": "macro_tile_layout_has_no_active_cells"}
    if output == grid:
        return None, {"failure": "identity_macro_tile_render"}

    return output, {
        "renderer_case": "layout_mask_macro_tile_expander",
        "background": background,
        "macro_background_color": background,
        "macro_motif_bbox": bbox_to_list(motif["bbox"]),
        "macro_layout_bbox": bbox_to_list(layout["bbox"]),
        "macro_tile_shape": [tile_height, tile_width],
        "macro_layout_shape": [layout_height, layout_width],
        "macro_tiled_shape": [output_height, output_width],
        "macro_layout_color": layout_color,
        "macro_active_cell_count": active_cell_count,
        "macro_motif_colors": motif["colors"],
    }
