"""既存v53の上端ordinal・上下括り縦run演算。

出典: ARC-Layer-0-Functional-Compliance@454670a13024ccf28dc7e9ed9d8ee256ee6cd365
arc2_l0_agent_compiler_v53_header_ranked_vertical_run_recolor.py
Git blob: 10b2f5b439b1cf1a2cbda2c38fd341abdcaf9506
純粋5関数は原文。上端・縦run・上→左順は固定prior。
旧component、課題ID/隔離ID定数、reportは含めない。
"""
from __future__ import annotations
from collections import Counter
from .既存凡例穴対応 import grid_shape,clone_grid
Grid=list[list[int]]

def dominant_color(grid: Grid) -> int:
    return Counter(value for row in grid for value in row).most_common(1)[0][0]

def same_color_components_4(grid: Grid, color: int) -> list[list[tuple[int, int]]]:
    height, width = grid_shape(grid)
    seen: set[tuple[int, int]] = set()
    components = []
    for row in range(height):
        for col in range(width):
            if (row, col) in seen or grid[row][col] != color:
                continue
            stack = [(row, col)]
            seen.add((row, col))
            cells = []
            while stack:
                current_row, current_col = stack.pop()
                cells.append((current_row, current_col))
                for d_row, d_col in (
                    (1, 0),
                    (-1, 0),
                    (0, 1),
                    (0, -1),
                ):
                    next_cell = (current_row + d_row, current_col + d_col)
                    next_row, next_col = next_cell
                    if (
                        0 <= next_row < height
                        and 0 <= next_col < width
                        and next_cell not in seen
                        and grid[next_row][next_col] == color
                    ):
                        seen.add(next_cell)
                        stack.append(next_cell)
            components.append(sorted(cells))
    return components

def top_header_rank_by_color(grid: Grid, background: int) -> dict[int, dict]:
    ranks = {}
    colors = sorted(
        {
            value
            for col, value in enumerate(grid[0])
            if value != background
        }
    )
    for color in colors:
        top_components = [
            component
            for component in same_color_components_4(grid, color)
            if any(row == 0 for row, _ in component)
        ]
        if len(top_components) != 1:
            continue
        component = top_components[0]
        rows = [row for row, _ in component]
        cols = [col for _, col in component]
        ranks[color] = {
            "rank": max(rows) - min(rows) + 1,
            "component": component,
            "bbox": [min(rows), min(cols), max(rows), max(cols)],
        }
    return ranks

def vertical_bounded_runs(grid: Grid, background: int) -> list[dict]:
    height, width = grid_shape(grid)
    runs = []
    for col in range(width):
        row = 0
        while row < height:
            source = grid[row][col]
            if source == background:
                row += 1
                continue
            start = row
            while row < height and grid[row][col] == source:
                row += 1
            end = row - 1
            above = start - 1
            below = end + 1
            if above < 0 or below >= height:
                continue
            target = grid[above][col]
            if target in (background, source):
                continue
            if grid[below][col] != target:
                continue
            runs.append(
                {
                    "col": col,
                    "top_endpoint_row": above,
                    "bottom_endpoint_row": below,
                    "start": start,
                    "end": end,
                    "source": source,
                    "target": target,
                    "length": end - start + 1,
                }
            )
    return runs

def apply_header_ranked_vertical_run_recolor(
    grid: Grid,
) -> tuple[Grid | None, dict | None]:
    background = dominant_color(grid)
    output = clone_grid(grid)
    header_ranks = top_header_rank_by_color(grid, background)
    runs_by_target: dict[int, list[dict]] = {}
    for run in vertical_bounded_runs(grid, background):
        runs_by_target.setdefault(run["target"], []).append(run)

    actions = []
    for target, runs in sorted(runs_by_target.items()):
        header = header_ranks.get(target)
        if header is None:
            continue
        ranked_runs = sorted(
            runs,
            key=lambda item: (
                item["top_endpoint_row"],
                item["col"],
                item["bottom_endpoint_row"],
            ),
        )
        rank = header["rank"]
        if not (1 <= rank <= len(ranked_runs)):
            continue
        selected = ranked_runs[rank - 1]
        changed = []
        for row in range(selected["start"], selected["end"] + 1):
            if output[row][selected["col"]] != target:
                output[row][selected["col"]] = target
                changed.append((row, selected["col"]))
        if changed:
            actions.append(
                {
                    "target": target,
                    "source": selected["source"],
                    "header_rank": rank,
                    "header_component": header["component"],
                    "candidate_count": len(ranked_runs),
                    "ranked_candidates": ranked_runs,
                    "selected_candidate": selected,
                    "changed_cells": changed,
                }
            )

    if not actions:
        return None, None
    record = {
        "background": background,
        "actions": actions,
        "action_count": len(actions),
        "changed_count": sum(len(action["changed_cells"]) for action in actions),
    }
    return output, record
