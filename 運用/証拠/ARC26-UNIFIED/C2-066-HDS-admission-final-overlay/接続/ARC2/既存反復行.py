"""既存v34の最小境界周期・行ごとのsingleton抽出演算。

出典: ARC-Layer-0-Functional-Compliance@454670a13024ccf28dc7e9ed9d8ee256ee6cd365
arc2_l0_agent_compiler_v34_periodic_panel_anomaly.py
Git blob: a58926fb65b0dc0cde779f83113168f5e650e29b
純粋3関数は原文。旧component/ID/reportは除外。
"""
from __future__ import annotations
from collections import Counter
from .既存凡例穴対応 import grid_shape
from .既存対角領域 import is_rectangular
Grid=list[list[int]]

def infer_panel_periods(grid: Grid) -> list[int]:
    if not is_rectangular(grid):
        return []
    height, width = grid_shape(grid)
    periods: list[int] = []
    for period in range(2, width):
        panel_count, remainder = divmod(width - 1, period)
        if remainder != 0 or panel_count < 2:
            continue
        separator_cols = list(range(0, width, period))
        if all(
            len({grid[row][col] for col in separator_cols}) == 1
            for row in range(height)
        ):
            periods.append(period)
    return periods

def select_panel_period(grid: Grid) -> int | None:
    periods = infer_panel_periods(grid)
    return periods[0] if periods else None

def periodic_panel_anomaly_compress(grid: Grid) -> Grid | None:
    period = select_panel_period(grid)
    if period is None:
        return None
    _, width = grid_shape(grid)
    panel_count = (width - 1) // period
    output: Grid = []

    for row in grid:
        chunks = [
            tuple(row[index * period : (index + 1) * period])
            for index in range(panel_count)
        ]
        counts = Counter(chunks)
        unique_chunks = [chunk for chunk, count in counts.items() if count == 1]
        if len(unique_chunks) == 1:
            chosen = unique_chunks[0]
        elif len(counts) == 1:
            chosen = chunks[0]
        else:
            return None
        output.append(list(chosen) + [row[-1]])
    return output
