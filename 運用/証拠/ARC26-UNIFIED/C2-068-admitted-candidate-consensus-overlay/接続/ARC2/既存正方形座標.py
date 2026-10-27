"""旧solid-square/D4座標の3関数。新しい格子写像から利用する。"""
from __future__ import annotations
from typing import Any

def solid_square_component(component: dict[str, Any]) -> bool:
    row0, col0, row1, col1 = component["bbox"]
    size = row1 - row0 + 1
    if size != col1 - col0 + 1:
        return False
    if int(component["size"]) != size * size:
        return False
    expected_cells = {
        (row, col)
        for row in range(row0, row1 + 1)
        for col in range(col0, col1 + 1)
    }
    return set(component["cells"]) == expected_cells

def d4_motif_transform_steps(transform_name: str) -> tuple[int, bool]:
    base = transform_name.split("_", 1)[0]
    if not base.startswith("rot"):
        raise ValueError(f"invalid d4 motif transform: {transform_name}")
    return int(base[3:]) // 90, transform_name.endswith("_flip_h")

def d4_motif_transform_coord(
    height: int,
    width: int,
    transform_name: str,
    row: int,
    col: int,
) -> tuple[int, int]:
    rotation_steps, flipped = d4_motif_transform_steps(transform_name)
    out_row = int(row)
    out_col = int(col)
    current_height = int(height)
    current_width = int(width)
    for _step in range(rotation_steps):
        out_row, out_col = out_col, current_height - 1 - out_row
        current_height, current_width = current_width, current_height
    if flipped:
        out_col = current_width - 1 - out_col
    return out_row, out_col
