"""旧v87の入力由来panel/凡例/通路演算。12関数は原文ASTを保持する。"""
from __future__ import annotations
from collections import Counter,deque
from typing import Any
from .既存凡例穴対応 import grid_shape, clone_grid
Grid=list[list[int]]
Cell=tuple[int,int]
BBox=tuple[int,int,int,int]

def dominant_background(grid: Grid) -> int:
    return Counter(value for row in grid for value in row).most_common(1)[0][0]

def color_components(grid: Grid, color: int) -> list[dict[str, Any]]:
    height, width = grid_shape(grid)
    seen: set[Cell] = set()
    components: list[dict[str, Any]] = []
    for row in range(height):
        for col in range(width):
            if grid[row][col] != color or (row, col) in seen:
                continue
            queue: deque[Cell] = deque([(row, col)])
            seen.add((row, col))
            cells: list[Cell] = []
            while queue:
                current_row, current_col = queue.popleft()
                cells.append((current_row, current_col))
                for row_delta, col_delta in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    next_row = current_row + row_delta
                    next_col = current_col + col_delta
                    next_cell = (next_row, next_col)
                    if not (0 <= next_row < height and 0 <= next_col < width):
                        continue
                    if next_cell in seen or grid[next_row][next_col] != color:
                        continue
                    seen.add(next_cell)
                    queue.append(next_cell)
            rows = [cell[0] for cell in cells]
            cols = [cell[1] for cell in cells]
            components.append(
                {
                    "cells": sorted(cells),
                    "bbox": (min(rows), min(cols), max(rows), max(cols)),
                    "size": len(cells),
                }
            )
    return sorted(components, key=lambda component: (component["bbox"], component["size"]))

def component_summary(component: dict[str, Any]) -> dict[str, Any]:
    return {
        "bbox": list(component["bbox"]),
        "size": component["size"],
        "cells": [list(cell) for cell in component["cells"]],
    }

def interval_overlap(first: tuple[int, int], second: tuple[int, int]) -> tuple[int, int] | None:
    start = max(first[0], second[0])
    end = min(first[1], second[1])
    return (start, end) if start <= end else None

def bbox_to_list(bbox: BBox) -> list[int]:
    return [bbox[0], bbox[1], bbox[2], bbox[3]]

def choose_frame_color(grid: Grid, background: int) -> int | None:
    counts = Counter(value for row in grid for value in row if value != background)
    if not counts:
        return None

    candidates: list[tuple[int, int, int]] = []
    for color, count in counts.items():
        score = 0
        for component in color_components(grid, color):
            row0, col0, row1, col1 = component["bbox"]
            height = row1 - row0 + 1
            width = col1 - col0 + 1
            if height < 3 or width < 3:
                continue
            payload_cells = [
                (row, col)
                for row in range(row0, row1 + 1)
                for col in range(col0, col1 + 1)
                if grid[row][col] not in {background, color}
            ]
            if payload_cells:
                score += height * width + len(payload_cells) * 4
        candidates.append((score, count, color))
    candidates.sort(reverse=True)
    if candidates[0][0] <= 0:
        return counts.most_common(1)[0][0]
    return candidates[0][2]

def extract_payload_panels(grid: Grid) -> tuple[int, int, list[dict[str, Any]]] | None:
    background = dominant_background(grid)
    frame_color = choose_frame_color(grid, background)
    if frame_color is None:
        return None

    panels: list[dict[str, Any]] = []
    for component in color_components(grid, frame_color):
        row0, col0, row1, col1 = component["bbox"]
        height = row1 - row0 + 1
        width = col1 - col0 + 1
        if height < 3 or width < 3:
            continue
        payload_cells: list[tuple[int, int, int]] = []
        for row in range(row0, row1 + 1):
            for col in range(col0, col1 + 1):
                value = grid[row][col]
                if value not in {background, frame_color}:
                    payload_cells.append((row, col, value))
        payload_colors = {value for _, _, value in payload_cells}
        if len(payload_colors) != 1:
            continue
        rows = [row for row, _, _ in payload_cells]
        cols = [col for _, col, _ in payload_cells]
        payload_color = payload_cells[0][2]
        panels.append(
            {
                "color": payload_color,
                "frame_component": component_summary(component),
                "frame_bbox": component["bbox"],
                "payload_bbox": (min(rows), min(cols), max(rows), max(cols)),
                "payload_cells": sorted((row, col) for row, col, _ in payload_cells),
            }
        )

    panels.sort(key=lambda panel: (panel["frame_bbox"], panel["color"]))
    if len(panels) < 2:
        return None
    return background, frame_color, panels

def extract_legend_sequence(grid: Grid, background: int, frame_color: int) -> list[int] | None:
    best: tuple[tuple[int, int], list[int]] | None = None
    for row_index, row in enumerate(grid):
        sequence: list[int] = []
        col = 0
        while col < len(row):
            if row[col] in {background, frame_color}:
                col += 1
                continue
            values: list[int] = []
            while col < len(row) and row[col] not in {background, frame_color}:
                values.append(row[col])
                col += 1
            if len(set(values)) == 1:
                sequence.append(values[0])
            else:
                sequence.extend(values)
        if len(sequence) < 2:
            continue
        # The legend is the longest non-frame payload row; ties choose the lower row.
        score = (len(sequence), row_index)
        if best is None or score > best[0]:
            best = (score, sequence)
    return best[1] if best is not None else None

def relation_between_panels(
    grid: Grid,
    background: int,
    source: dict[str, Any],
    target: dict[str, Any],
) -> dict[str, Any] | None:
    source_row0, source_col0, source_row1, source_col1 = source["frame_bbox"]
    target_row0, target_col0, target_row1, target_col1 = target["frame_bbox"]
    payload_row0, payload_col0, payload_row1, payload_col1 = source["payload_bbox"]
    other_row0, other_col0, other_row1, other_col1 = target["payload_bbox"]

    row_overlap = interval_overlap((payload_row0, payload_row1), (other_row0, other_row1))
    if row_overlap is not None:
        if source_col1 < target_col0:
            fill_rect = (row_overlap[0], source_col1 + 1, row_overlap[1], target_col0 - 1)
        elif target_col1 < source_col0:
            fill_rect = (row_overlap[0], target_col1 + 1, row_overlap[1], source_col0 - 1)
        else:
            fill_rect = None
        if fill_rect is not None and fill_rect[1] <= fill_rect[3]:
            row0, col0, row1, col1 = fill_rect
            if all(
                grid[row][col] == background
                for row in range(row0, row1 + 1)
                for col in range(col0, col1 + 1)
            ):
                return {
                    "direction": "horizontal",
                    "source_color": source["color"],
                    "target_color": target["color"],
                    "fill_rect": bbox_to_list(fill_rect),
                    "fill_color": source["color"],
                }

    col_overlap = interval_overlap((payload_col0, payload_col1), (other_col0, other_col1))
    if col_overlap is not None:
        if source_row1 < target_row0:
            fill_rect = (source_row1 + 1, col_overlap[0], target_row0 - 1, col_overlap[1])
        elif target_row1 < source_row0:
            fill_rect = (target_row1 + 1, col_overlap[0], source_row0 - 1, col_overlap[1])
        else:
            fill_rect = None
        if fill_rect is not None and fill_rect[0] <= fill_rect[2]:
            row0, col0, row1, col1 = fill_rect
            if all(
                grid[row][col] == background
                for row in range(row0, row1 + 1)
                for col in range(col0, col1 + 1)
            ):
                return {
                    "direction": "vertical",
                    "source_color": source["color"],
                    "target_color": target["color"],
                    "fill_rect": bbox_to_list(fill_rect),
                    "fill_color": source["color"],
                }

    return None

def find_legend_payload_path(
    grid: Grid,
    background: int,
    panels: list[dict[str, Any]],
    legend_sequence: list[int],
) -> tuple[list[int], list[dict[str, Any]]] | None:
    panels_by_color: dict[int, list[int]] = {}
    for index, panel in enumerate(panels):
        panels_by_color.setdefault(panel["color"], []).append(index)
    if any(color not in panels_by_color for color in legend_sequence):
        return None

    relation_cache: dict[tuple[int, int], dict[str, Any] | None] = {}

    def relation(source_index: int, target_index: int) -> dict[str, Any] | None:
        key = (source_index, target_index)
        if key not in relation_cache:
            relation_cache[key] = relation_between_panels(
                grid, background, panels[source_index], panels[target_index]
            )
        return relation_cache[key]

    path: list[int] = []
    used: set[int] = set()

    def search(sequence_index: int, previous_index: int | None) -> bool:
        if sequence_index == len(legend_sequence):
            return True
        color = legend_sequence[sequence_index]
        for candidate_index in panels_by_color[color]:
            if candidate_index in used:
                continue
            if previous_index is not None and relation(previous_index, candidate_index) is None:
                continue
            path.append(candidate_index)
            used.add(candidate_index)
            if search(sequence_index + 1, candidate_index):
                return True
            used.remove(candidate_index)
            path.pop()
        return False

    if not search(0, None):
        return None

    relation_records = [
        relation(source_index, target_index)
        for source_index, target_index in zip(path, path[1:])
    ]
    if any(record is None for record in relation_records):
        return None
    return path, [record for record in relation_records if record is not None]

def panel_summary(panel: dict[str, Any]) -> dict[str, Any]:
    return {
        "color": panel["color"],
        "frame_bbox": bbox_to_list(panel["frame_bbox"]),
        "payload_bbox": bbox_to_list(panel["payload_bbox"]),
        "payload_cells": [list(cell) for cell in panel["payload_cells"]],
    }

def render_legend_payload_gap_connectors(grid: Grid) -> tuple[Grid | None, dict[str, Any]]:
    extracted = extract_payload_panels(grid)
    if extracted is None:
        return None, {"failure": "payload_panel_extraction_failed"}
    background, frame_color, panels = extracted
    legend_sequence = extract_legend_sequence(grid, background, frame_color)
    if legend_sequence is None:
        return None, {
            "failure": "legend_sequence_extraction_failed",
            "background": background,
            "frame_color": frame_color,
            "panel_count": len(panels),
        }
    selected = find_legend_payload_path(grid, background, panels, legend_sequence)
    if selected is None:
        return None, {
            "failure": "legend_path_search_failed",
            "background": background,
            "frame_color": frame_color,
            "legend_sequence": legend_sequence,
            "panels": [panel_summary(panel) for panel in panels],
        }
    path, relation_records = selected

    output = clone_grid(grid)
    for record in relation_records:
        row0, col0, row1, col1 = record["fill_rect"]
        for row in range(row0, row1 + 1):
            for col in range(col0, col1 + 1):
                output[row][col] = record["fill_color"]

    if output == grid:
        return None, {"failure": "identity_render"}
    return output, {
        "background": background,
        "frame_color": frame_color,
        "legend_sequence": legend_sequence,
        "path_panel_indices": path,
        "path_panels": [panel_summary(panels[index]) for index in path],
        "relation_records": relation_records,
    }
