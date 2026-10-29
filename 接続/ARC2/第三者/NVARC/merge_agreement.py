#!/usr/bin/env python3
"""Merge NVARC with a high-precision two-checkpoint TRM selector.

SPDX-License-Identifier: MIT-0
"""

from __future__ import annotations

import argparse
from collections import Counter, deque
import json
from math import gcd
from pathlib import Path
from typing import Callable


Grid = list[list[int]]
Transform = Callable[[Grid], Grid]


def valid_grid(grid: object) -> bool:
    if not isinstance(grid, list) or not grid or not isinstance(grid[0], list) or not grid[0]:
        return False
    width = len(grid[0])
    return (
        len(grid) <= 30
        and width <= 30
        and all(isinstance(row, list) and len(row) == width for row in grid)
        and all(type(cell) is int and 0 <= cell <= 9 for row in grid for cell in row)
    )


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def transpose(grid: Grid) -> Grid:
    return [list(row) for row in zip(*grid)]


def rotate_90(grid: Grid) -> Grid:
    return [list(row) for row in zip(*grid[::-1])]


def rotate_180(grid: Grid) -> Grid:
    return [row[::-1] for row in grid[::-1]]


def rotate_270(grid: Grid) -> Grid:
    return [list(row) for row in zip(*grid)][::-1]


def flip_horizontal(grid: Grid) -> Grid:
    return [row[::-1] for row in grid]


def flip_vertical(grid: Grid) -> Grid:
    return grid[::-1]


def anti_transpose(grid: Grid) -> Grid:
    return rotate_180(transpose(grid))


SPATIAL_TRANSFORMS: dict[str, Transform] = {
    "identity": lambda grid: [row[:] for row in grid],
    "rotate_90": rotate_90,
    "rotate_180": rotate_180,
    "rotate_270": rotate_270,
    "flip_horizontal": flip_horizontal,
    "flip_vertical": flip_vertical,
    "transpose": transpose,
    "anti_transpose": anti_transpose,
}


def scale(grid: Grid, factor: int) -> Grid:
    result = []
    for row in grid:
        expanded = [value for value in row for _ in range(factor)]
        result.extend([expanded[:] for _ in range(factor)])
    return result


def tile(grid: Grid, rows: int, columns: int) -> Grid:
    horizontal = [row * columns for row in grid]
    return [row[:] for _ in range(rows) for row in horizontal]


def crop_not_color(grid: Grid, background: int) -> Grid | None:
    coordinates = [
        (row_index, column_index)
        for row_index, row in enumerate(grid)
        for column_index, value in enumerate(row)
        if value != background
    ]
    if not coordinates:
        return None
    row_values = [row for row, _ in coordinates]
    column_values = [column for _, column in coordinates]
    top, bottom = min(row_values), max(row_values)
    left, right = min(column_values), max(column_values)
    return [row[left : right + 1] for row in grid[top : bottom + 1]]


def crop_color_bbox(grid: Grid, color: int) -> Grid | None:
    coordinates = [
        (row_index, column_index)
        for row_index, row in enumerate(grid)
        for column_index, value in enumerate(row)
        if value == color
    ]
    if not coordinates:
        return None
    row_values = [row for row, _ in coordinates]
    column_values = [column for _, column in coordinates]
    top, bottom = min(row_values), max(row_values)
    left, right = min(column_values), max(column_values)
    return [row[left : right + 1] for row in grid[top : bottom + 1]]


def crop_nonbackground_flip_horizontal(grid: Grid) -> Grid | None:
    counts = Counter(value for row in grid for value in row)
    background = min(counts, key=lambda color: (-counts[color], color))
    cropped = crop_not_color(grid, background)
    return None if cropped is None else flip_horizontal(cropped)


def mode_color(grid: Grid) -> int:
    counts = Counter(value for row in grid for value in row)
    return min(counts, key=lambda color: (-counts[color], color))


def crop_mode_background(grid: Grid) -> Grid:
    cropped = crop_not_color(grid, mode_color(grid))
    return [row[:] for row in grid] if cropped is None else cropped


def remove_uniform_lines(grid: Grid) -> Grid:
    rows = [
        index
        for index, row in enumerate(grid)
        if any(value != row[0] for value in row)
    ]
    columns = [
        index
        for index in range(len(grid[0]))
        if any(grid[row][index] != grid[0][index] for row in range(len(grid)))
    ]
    if not rows or not columns:
        return [row[:] for row in grid]
    return [[grid[row][column] for column in columns] for row in rows]


def scale_2x2_remove_uniform_lines(grid: Grid) -> Grid:
    """Enlarge each cell 2x2, then discard the resulting uniform frame."""
    return remove_uniform_lines(scale(grid, 2))


def tile_1x2_remove_uniform_lines(grid: Grid) -> Grid:
    """Repeat the grid horizontally, then discard uniform framing lines."""
    return remove_uniform_lines(tile(grid, 1, 2))


def gravity_cells_vertical(grid: Grid, direction: str) -> Grid:
    """Compact non-background cells within each column, preserving order."""
    background = mode_color(grid)
    height = len(grid)
    width = len(grid[0])
    result = [[background for _ in range(width)] for _ in range(height)]
    for column in range(width):
        values = [
            grid[row][column]
            for row in range(height)
            if grid[row][column] != background
        ]
        start = 0 if direction == "up" else height - len(values)
        for offset, value in enumerate(values):
            result[start + offset][column] = value
    return result


def gravity_unique_rarest_left(grid: Grid) -> Grid | None:
    """Slide the unique rarest color left within fixed-object row segments."""
    background = mode_color(grid)
    counts = Counter(
        value
        for row in grid
        for value in row
        if value != background
    )
    if not counts:
        return None
    rarest_count = min(counts.values())
    rarest = [
        color for color, count in counts.items() if count == rarest_count
    ]
    if len(rarest) != 1:
        return None
    movable = rarest[0]
    result = [row[:] for row in grid]
    width = len(grid[0])
    for row_index, row in enumerate(grid):
        fixed = [
            column
            for column, value in enumerate(row)
            if value != background and value != movable
        ]
        for column, value in enumerate(row):
            if value == movable:
                result[row_index][column] = background
        segment_start = 0
        for blocker in fixed + [width]:
            count = sum(
                row[column] == movable
                for column in range(segment_start, blocker)
            )
            for column in range(segment_start, segment_start + count):
                result[row_index][column] = movable
            segment_start = blocker + 1
    return result


def monochrome_components(
    grid: Grid,
) -> list[list[tuple[int, int]]]:
    """Return deterministic four-connected same-color components."""
    background = mode_color(grid)
    height, width = len(grid), len(grid[0])
    seen: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []
    for start_row in range(height):
        for start_column in range(width):
            start = (start_row, start_column)
            if start in seen or grid[start_row][start_column] == background:
                continue
            color = grid[start_row][start_column]
            queue = [start]
            seen.add(start)
            component: list[tuple[int, int]] = []
            cursor = 0
            while cursor < len(queue):
                row, column = queue[cursor]
                cursor += 1
                component.append((row, column))
                for delta_row, delta_column in (
                    (-1, 0),
                    (1, 0),
                    (0, -1),
                    (0, 1),
                ):
                    neighbor = row + delta_row, column + delta_column
                    nr, nc = neighbor
                    if (
                        0 <= nr < height
                        and 0 <= nc < width
                        and neighbor not in seen
                        and grid[nr][nc] == color
                    ):
                        seen.add(neighbor)
                        queue.append(neighbor)
            components.append(component)
    return components


def remove_nonmodal_8_connected_singletons(grid: Grid) -> Grid:
    """Replace isolated non-background pixels with the modal background."""
    background = mode_color(grid)
    height, width = len(grid), len(grid[0])
    result = [row[:] for row in grid]
    for row in range(height):
        for column in range(width):
            color = grid[row][column]
            if color == background:
                continue
            has_same_color_neighbor = any(
                grid[neighbor_row][neighbor_column] == color
                for delta_row, delta_column in (
                    (-1, -1),
                    (-1, 0),
                    (-1, 1),
                    (0, -1),
                    (0, 1),
                    (1, -1),
                    (1, 0),
                    (1, 1),
                )
                if 0 <= (neighbor_row := row + delta_row) < height
                and 0 <= (neighbor_column := column + delta_column) < width
            )
            if not has_same_color_neighbor:
                result[row][column] = background
    return result


def count_nonzero_monochrome_components(
    grid: Grid, connectivity: int
) -> int:
    height, width = len(grid), len(grid[0])
    deltas = [
        (-1, 0),
        (1, 0),
        (0, -1),
        (0, 1),
    ]
    if connectivity == 8:
        deltas += [
            (-1, -1),
            (-1, 1),
            (1, -1),
            (1, 1),
        ]
    seen: set[tuple[int, int]] = set()
    count = 0
    for start_row in range(height):
        for start_column in range(width):
            start = start_row, start_column
            if start in seen or grid[start_row][start_column] == 0:
                continue
            count += 1
            color = grid[start_row][start_column]
            queue = [start]
            seen.add(start)
            cursor = 0
            while cursor < len(queue):
                row, column = queue[cursor]
                cursor += 1
                for delta_row, delta_column in deltas:
                    neighbor = row + delta_row, column + delta_column
                    nr, nc = neighbor
                    if (
                        0 <= nr < height
                        and 0 <= nc < width
                        and neighbor not in seen
                        and grid[nr][nc] == color
                    ):
                        seen.add(neighbor)
                        queue.append(neighbor)
    return count


def horizontal_zero_bar(length: int) -> Grid | None:
    return [[0] * length] if 1 <= length <= 30 else None


def count_nonzero_components_4_bar(grid: Grid) -> Grid | None:
    return horizontal_zero_bar(
        count_nonzero_monochrome_components(grid, 4)
    )


def count_distinct_nonzero_colors_zero_bar(grid: Grid) -> Grid | None:
    return horizontal_zero_bar(
        len({value for row in grid for value in row if value != 0})
    )


def count_distinct_occupied_row_widths_bar(grid: Grid) -> Grid | None:
    background = mode_color(grid)
    widths = {
        sum(value != background for value in row)
        for row in grid
        if any(value != background for value in row)
    }
    return horizontal_zero_bar(len(widths))


def count_hole_cells_4_bar(grid: Grid) -> Grid | None:
    background = mode_color(grid)
    height, width = len(grid), len(grid[0])
    exterior: set[tuple[int, int]] = set()
    queue: list[tuple[int, int]] = []
    for row in range(height):
        for column in range(width):
            if row not in (0, height - 1) and column not in (0, width - 1):
                continue
            point = row, column
            if grid[row][column] == background and point not in exterior:
                exterior.add(point)
                queue.append(point)
    cursor = 0
    while cursor < len(queue):
        row, column = queue[cursor]
        cursor += 1
        for delta_row, delta_column in (
            (-1, 0),
            (1, 0),
            (0, -1),
            (0, 1),
        ):
            neighbor = row + delta_row, column + delta_column
            nr, nc = neighbor
            if (
                0 <= nr < height
                and 0 <= nc < width
                and neighbor not in exterior
                and grid[nr][nc] == background
            ):
                exterior.add(neighbor)
                queue.append(neighbor)
    holes = sum(
        grid[row][column] == background
        and (row, column) not in exterior
        for row in range(height)
        for column in range(width)
    )
    return horizontal_zero_bar(holes)


def count_rare_pixels_vertical_bar(grid: Grid) -> Grid | None:
    counts = Counter(value for row in grid for value in row)
    common = {
        color
        for color, _ in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )[:2]
    }
    rare = sum(
        value not in common for row in grid for value in row
    )
    return [[0] for _ in range(rare)] if 1 <= rare <= 30 else None


def count_interior_nonzero_markers7_vertical(grid: Grid) -> Grid | None:
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    ]
    count = 0
    if points:
        top = min(row for row, _ in points)
        bottom = max(row for row, _ in points)
        left = min(column for _, column in points)
        right = max(column for _, column in points)
        count = sum(
            grid[row][column] != 0
            for row in range(top + 1, bottom)
            for column in range(left + 1, right)
        )
    if count > 7:
        return None
    return [[4] if index < count else [0] for index in range(7)]


def count_nonzero_component8_markers6_horizontal(
    grid: Grid,
) -> Grid | None:
    count = count_nonzero_monochrome_components(grid, 8)
    if count > 6:
        return None
    return [[4] * count + [0] * (6 - count)]


def count_simplified_convex_hull_sides_bar(grid: Grid) -> Grid | None:
    background = mode_color(grid)
    points = sorted(
        {
            (column, row)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value != background
        }
    )
    if len(points) < 3:
        return None

    def cross(
        origin: tuple[int, int],
        first: tuple[int, int],
        second: tuple[int, int],
    ) -> int:
        return (
            (first[0] - origin[0]) * (second[1] - origin[1])
            - (first[1] - origin[1]) * (second[0] - origin[0])
        )

    lower: list[tuple[int, int]] = []
    for point in points:
        while (
            len(lower) >= 2
            and cross(lower[-2], lower[-1], point) <= 0
        ):
            lower.pop()
        lower.append(point)
    upper: list[tuple[int, int]] = []
    for point in reversed(points):
        while (
            len(upper) >= 2
            and cross(upper[-2], upper[-1], point) <= 0
        ):
            upper.pop()
        upper.append(point)
    hull = lower[:-1] + upper[:-1]
    while len(hull) > 3:
        short_edge = next(
            (
                index
                for index, point in enumerate(hull)
                if (
                    (point[0] - hull[(index + 1) % len(hull)][0]) ** 2
                    + (point[1] - hull[(index + 1) % len(hull)][1]) ** 2
                )
                <= 1
            ),
            None,
        )
        if short_edge is None:
            break
        del hull[(short_edge + 1) % len(hull)]
    return horizontal_zero_bar(len(hull))


def count_occlusion_restored_nonzero_objects_bar(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    total = 0
    colors = sorted(
        {value for row in grid for value in row if value != 0}
    )
    for color in colors:
        points = {
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        }
        edges = {point: set() for point in points}
        for row, column in points:
            for delta_row, delta_column in (
                (-1, 0),
                (1, 0),
                (0, -1),
                (0, 1),
            ):
                neighbor = row + delta_row, column + delta_column
                if neighbor in points:
                    edges[(row, column)].add(neighbor)
            for delta_row, delta_column in (
                (1, 0),
                (0, 1),
                (1, 1),
                (1, -1),
            ):
                next_row = row + delta_row
                next_column = column + delta_column
                intervening = 0
                while (
                    0 <= next_row < height
                    and 0 <= next_column < width
                    and grid[next_row][next_column] != 0
                ):
                    if grid[next_row][next_column] == color:
                        if intervening:
                            endpoint = next_row, next_column
                            edges[(row, column)].add(endpoint)
                            edges[endpoint].add((row, column))
                        break
                    intervening += 1
                    next_row += delta_row
                    next_column += delta_column
        unseen = set(points)
        while unseen:
            total += 1
            queue = [unseen.pop()]
            while queue:
                point = queue.pop()
                for neighbor in edges[point]:
                    if neighbor in unseen:
                        unseen.remove(neighbor)
                        queue.append(neighbor)
    return horizontal_zero_bar(total)


def colored_components(
    grid: Grid,
    excluded_color: int,
    connectivity: int,
) -> list[tuple[int, list[tuple[int, int]]]]:
    height, width = len(grid), len(grid[0])
    deltas = [
        (-1, 0),
        (1, 0),
        (0, -1),
        (0, 1),
    ]
    if connectivity == 8:
        deltas += [
            (-1, -1),
            (-1, 1),
            (1, -1),
            (1, 1),
        ]
    seen: set[tuple[int, int]] = set()
    found: list[tuple[int, list[tuple[int, int]]]] = []
    for start_row in range(height):
        for start_column in range(width):
            start = start_row, start_column
            if (
                start in seen
                or grid[start_row][start_column] == excluded_color
            ):
                continue
            color = grid[start_row][start_column]
            queue = [start]
            seen.add(start)
            group: list[tuple[int, int]] = []
            cursor = 0
            while cursor < len(queue):
                row, column = queue[cursor]
                cursor += 1
                group.append((row, column))
                for delta_row, delta_column in deltas:
                    neighbor = row + delta_row, column + delta_column
                    nr, nc = neighbor
                    if (
                        0 <= nr < height
                        and 0 <= nc < width
                        and neighbor not in seen
                        and grid[nr][nc] == color
                    ):
                        seen.add(neighbor)
                        queue.append(neighbor)
            found.append((color, group))
    return found


def point_bbox(
    points: list[tuple[int, int]],
) -> tuple[int, int, int, int]:
    return (
        min(row for row, _ in points),
        max(row for row, _ in points),
        min(column for _, column in points),
        max(column for _, column in points),
    )


def multicolor_components(
    grid: Grid,
) -> list[list[tuple[int, int]]]:
    """Return four-connected components of all non-background cells."""
    background = mode_color(grid)
    height, width = len(grid), len(grid[0])
    seen: set[tuple[int, int]] = set()
    found: list[list[tuple[int, int]]] = []
    for start_row in range(height):
        for start_column in range(width):
            start = start_row, start_column
            if start in seen or grid[start_row][start_column] == background:
                continue
            queue = [start]
            seen.add(start)
            group: list[tuple[int, int]] = []
            cursor = 0
            while cursor < len(queue):
                row, column = queue[cursor]
                cursor += 1
                group.append((row, column))
                for delta_row, delta_column in (
                    (-1, 0),
                    (1, 0),
                    (0, -1),
                    (0, 1),
                ):
                    neighbor = row + delta_row, column + delta_column
                    nr, nc = neighbor
                    if (
                        0 <= nr < height
                        and 0 <= nc < width
                        and neighbor not in seen
                        and grid[nr][nc] != background
                    ):
                        seen.add(neighbor)
                        queue.append(neighbor)
            found.append(group)
    return found


def normalized_component_mask(
    points: list[tuple[int, int]],
) -> tuple[tuple[int, ...], ...]:
    top, bottom, left, right = point_bbox(points)
    point_set = set(points)
    return tuple(
        tuple(
            int((row, column) in point_set)
            for column in range(left, right + 1)
        )
        for row in range(top, bottom + 1)
    )


def normalized_color_mask(
    grid: Grid, color: int
) -> tuple[tuple[int, ...], ...]:
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == color
    ]
    return () if not points else normalized_component_mask(points)


def cleanup_color_components(
    grid: Grid, color: int, connectivity: int
) -> list[list[tuple[int, int]]]:
    return [
        points
        for component_color, points in colored_components(
            grid, -1, connectivity
        )
        if component_color == color
    ]


def restore_minimum_description_period(grid: Grid) -> Grid:
    """Restore a small repeated tile under sparse corruption."""
    height, width = len(grid), len(grid[0])
    best_key: tuple[int, int, int] | None = None
    best_result: Grid | None = None
    for row_period in range(1, min(height, 4) + 1):
        for column_period in range(1, min(width, 4) + 1):
            result = [[0] * width for _ in range(height)]
            for row_residue in range(row_period):
                for column_residue in range(column_period):
                    counts = Counter(
                        grid[row][column]
                        for row in range(
                            row_residue, height, row_period
                        )
                        for column in range(
                            column_residue, width, column_period
                        )
                    )
                    target = min(
                        counts,
                        key=lambda color: (-counts[color], color),
                    )
                    for row in range(
                        row_residue, height, row_period
                    ):
                        for column in range(
                            column_residue,
                            width,
                            column_period,
                        ):
                            result[row][column] = target
            errors = sum(
                result[row][column] != grid[row][column]
                for row in range(height)
                for column in range(width)
            )
            area = row_period * column_period
            key = errors + area, area, errors
            if best_key is None or key < best_key:
                best_key = key
                best_result = result
    return best_result if best_result is not None else [row[:] for row in grid]


def cleanup_speckle_cardinal_consensus(grid: Grid) -> Grid:
    """Replace dispersed colors using nearest cardinal evidence."""
    height, width = len(grid), len(grid[0])
    counts = Counter(value for row in grid for value in row)
    noise = {
        color
        for color, count in counts.items()
        if count <= 0.15 * height * width
        and max(
            (
                len(group)
                for group in cleanup_color_components(
                    grid, color, 8
                )
            ),
            default=0,
        )
        <= 2
    }
    result = [row[:] for row in grid]
    for row in range(height):
        for column in range(width):
            if grid[row][column] not in noise:
                continue
            scores: dict[int, float] = {}
            for delta_row, delta_column in (
                (-1, 0),
                (1, 0),
                (0, -1),
                (0, 1),
            ):
                for distance in range(1, max(height, width)):
                    neighbor_row = row + delta_row * distance
                    neighbor_column = column + delta_column * distance
                    if not (
                        0 <= neighbor_row < height
                        and 0 <= neighbor_column < width
                    ):
                        break
                    color = grid[neighbor_row][neighbor_column]
                    if color in noise:
                        continue
                    scores[color] = (
                        scores.get(color, 0.0) + 1.0 / distance
                    )
                    break
            if scores:
                result[row][column] = min(
                    scores,
                    key=lambda color: (
                        -scores[color],
                        -counts[color],
                        color,
                    ),
                )
    return result


def reconstruct_noisy_dense_rectangles(
    grid: Grid,
) -> Grid | None:
    """Keep noisy dense components as filled rectangles."""
    height, width = len(grid), len(grid[0])
    if min(height, width) < 8:
        return None
    background = mode_color(grid)
    colors = {value for row in grid for value in row}
    if len(colors) < 3 and background == 0:
        return None
    result = [[background] * width for _ in range(height)]
    for color in sorted(colors - {background}):
        for group in cleanup_color_components(grid, color, 4):
            top, bottom, left, right = point_bbox(group)
            rectangle_height = bottom - top + 1
            rectangle_width = right - left + 1
            area = rectangle_height * rectangle_width
            if (
                area < 4
                or min(rectangle_height, rectangle_width) < 2
                or len(group) < 0.3 * area
            ):
                continue
            for row in range(top, bottom + 1):
                for column in range(left, right + 1):
                    result[row][column] = color
    return result


def reconstruct_hollow_outline_rectangles(
    grid: Grid,
) -> Grid | None:
    """Recover complete hollow rectangle outlines from corruption."""
    height, width = len(grid), len(grid[0])
    background = mode_color(grid)
    intervals: dict[tuple[int, int], list[int]] = {}
    for row in range(height):
        for left in range(width):
            if grid[row][left] == background:
                continue
            for right in range(left + 2, width):
                if any(
                    grid[row][column] == background
                    for column in range(left, right + 1)
                ):
                    break
                intervals.setdefault((left, right), []).append(row)
    candidates = []
    for (left, right), rows in intervals.items():
        for first_index, top in enumerate(rows):
            for bottom in rows[first_index + 1 :]:
                if bottom - top + 1 < 3:
                    continue
                if any(
                    grid[row][left] == background
                    or grid[row][right] == background
                    for row in range(top, bottom + 1)
                ):
                    continue
                border = {
                    (row, column)
                    for row in range(top, bottom + 1)
                    for column in range(left, right + 1)
                    if row in (top, bottom)
                    or column in (left, right)
                }
                counts = Counter(grid[row][column] for row, column in border)
                color = min(
                    counts,
                    key=lambda value: (-counts[value], value),
                )
                purity = counts[color] / len(border)
                if purity < 0.5:
                    continue
                interior = [
                    grid[row][column]
                    for row in range(top + 1, bottom)
                    for column in range(left + 1, right)
                ]
                if (
                    interior
                    and sum(value == background for value in interior)
                    < 0.5 * len(interior)
                ):
                    continue
                candidates.append(
                    (
                        purity,
                        len(border),
                        top,
                        bottom,
                        left,
                        right,
                        color,
                        border,
                    )
                )
    candidates.sort(
        key=lambda item: (
            -item[0],
            -item[1],
            item[2],
            item[4],
            item[6],
        )
    )
    selected = []
    for candidate in candidates:
        _, _, top, bottom, left, right, _, _ = candidate
        if any(
            not (
                bottom < other[2]
                or other[3] < top
                or right < other[4]
                or other[5] < left
            )
            for other in selected
        ):
            continue
        selected.append(candidate)
    if not selected:
        return None
    result = [[background] * width for _ in range(height)]
    for candidate in selected:
        color, border = candidate[6], candidate[7]
        for row, column in border:
            result[row][column] = color
    return result


def cleanup_has_repeated_component_geometry(grid: Grid) -> bool:
    components = [
        group
        for color in sorted(
            {value for row in grid for value in row} - {0}
        )
        for group in cleanup_color_components(grid, color, 8)
        if len(group) >= 5
    ]
    for first_index, first in enumerate(components):
        first_box = point_bbox(first)
        first_shape = (
            first_box[1] - first_box[0] + 1,
            first_box[3] - first_box[2] + 1,
        )
        for second in components[first_index + 1 :]:
            second_box = point_bbox(second)
            second_shape = (
                second_box[1] - second_box[0] + 1,
                second_box[3] - second_box[2] + 1,
            )
            if (
                first_shape == second_shape
                and min(len(first), len(second))
                >= 0.75 * max(len(first), len(second))
            ):
                return True
    return False


def cleanup_nonrepeated_opposite_components(
    grid: Grid,
) -> Grid | None:
    """Retain signal components and repair only bracketed gaps."""
    if cleanup_has_repeated_component_geometry(grid):
        return None
    height, width = len(grid), len(grid[0])
    by_color = {
        color: cleanup_color_components(grid, color, 8)
        for color in sorted(
            {value for row in grid for value in row} - {0}
        )
    }
    maximum = max(
        (
            len(group)
            for groups in by_color.values()
            for group in groups
        ),
        default=0,
    )
    reliable_colors = {
        color
        for color, groups in by_color.items()
        if max(map(len, groups), default=0) >= 0.5 * maximum
    }
    result = [[0] * width for _ in range(height)]
    kept: set[tuple[int, int]] = set()
    for color in sorted(reliable_colors):
        for group in by_color[color]:
            if len(group) < 2:
                continue
            for row, column in group:
                result[row][column] = color
                kept.add((row, column))
    axes = (
        ((-1, 0), (1, 0)),
        ((0, -1), (0, 1)),
        ((-1, -1), (1, 1)),
        ((-1, 1), (1, -1)),
    )
    for row in range(height):
        for column in range(width):
            if (row, column) in kept or grid[row][column] == 0:
                continue
            supported = []
            for first, second in axes:
                first_point = row + first[0], column + first[1]
                second_point = row + second[0], column + second[1]
                if (
                    first_point in kept
                    and second_point in kept
                    and result[first_point[0]][first_point[1]]
                    == result[second_point[0]][second_point[1]]
                ):
                    supported.append(
                        result[first_point[0]][first_point[1]]
                    )
            if supported:
                counts = Counter(supported)
                result[row][column] = min(
                    counts,
                    key=lambda color: (-counts[color], color),
                )
    return result


def cleanup_flip_mask(
    mask: set[tuple[int, int]],
    height: int,
    width: int,
    flip_horizontal: bool,
    flip_vertical: bool,
) -> set[tuple[int, int]]:
    return {
        (
            height - 1 - row if flip_vertical else row,
            width - 1 - column if flip_horizontal else column,
        )
        for row, column in mask
    }


def reconstruct_repeated_mirrored_components(
    grid: Grid,
) -> Grid | None:
    """Union repeated component templates after mirror alignment."""
    height, width = len(grid), len(grid[0])
    components = [
        (color, group)
        for color in sorted(
            {value for row in grid for value in row} - {0}
        )
        for group in cleanup_color_components(grid, color, 8)
    ]
    maximum = max(
        (len(group) for _, group in components), default=0
    )
    components = [
        (color, group)
        for color, group in components
        if len(group) >= 2 and len(group) >= 0.5 * maximum
    ]
    if len(components) < 2:
        return None
    component_height = max(
        point_bbox(group)[1] - point_bbox(group)[0] + 1
        for _, group in components
    )
    component_width = max(
        point_bbox(group)[3] - point_bbox(group)[2] + 1
        for _, group in components
    )
    normalized = []
    for color, group in sorted(
        components,
        key=lambda item: (
            point_bbox(item[1])[0],
            point_bbox(item[1])[2],
            item[0],
        ),
    ):
        top, _, left, _ = point_bbox(group)
        normalized.append(
            (
                color,
                top,
                left,
                {(row - top, column - left) for row, column in group},
            )
        )
    reference = normalized[0][3]
    aligned = []
    for color, top, left, mask in normalized:
        options = []
        for flip_horizontal in (False, True):
            for flip_vertical in (False, True):
                candidate = cleanup_flip_mask(
                    mask,
                    component_height,
                    component_width,
                    flip_horizontal,
                    flip_vertical,
                )
                options.append(
                    (
                        -len(candidate & reference),
                        len(candidate ^ reference),
                        flip_horizontal,
                        flip_vertical,
                        candidate,
                    )
                )
        selected = min(options, key=lambda item: item[:4])
        aligned.append(
            (
                color,
                top,
                left,
                selected[2],
                selected[3],
                selected[4],
            )
        )
    template: set[tuple[int, int]] = set()
    for item in aligned:
        template.update(item[5])
    result = [[0] * width for _ in range(height)]
    for color, top, left, flip_horizontal, flip_vertical, _ in aligned:
        rendered = cleanup_flip_mask(
            template,
            component_height,
            component_width,
            flip_horizontal,
            flip_vertical,
        )
        for row, column in rendered:
            target_row, target_column = top + row, left + column
            if 0 <= target_row < height and 0 <= target_column < width:
                result[target_row][target_column] = color
    return result


def reconstruct_dense_square_blocks(grid: Grid) -> Grid | None:
    """Find the largest repeated dense-square scale and complete it."""
    height, width = len(grid), len(grid[0])
    background = mode_color(grid)
    colors = sorted(
        {value for row in grid for value in row} - {background}
    )
    for size in range(min(6, height, width), 1, -1):
        windows = []
        for color in colors:
            options = []
            for top in range(height - size + 1):
                for left in range(width - size + 1):
                    count = sum(
                        grid[row][column] == color
                        for row in range(top, top + size)
                        for column in range(left, left + size)
                    )
                    options.append((-count, top, left))
            negative_count, top, left = min(options)
            count = -negative_count
            required = (55 * size * size + 99) // 100
            if count >= required:
                windows.append((color, top, left, count))
        windows.sort(
            key=lambda item: (
                -item[3],
                item[1],
                item[2],
                item[0],
            )
        )
        selected = []
        for window in windows:
            _, top, left, _ = window
            if any(
                not (
                    top + size - 1 < other[1]
                    or other[1] + size - 1 < top
                    or left + size - 1 < other[2]
                    or other[2] + size - 1 < left
                )
                for other in selected
            ):
                continue
            selected.append(window)
        if len(selected) < 2:
            continue
        result = [[background] * width for _ in range(height)]
        for color, top, left, _ in selected:
            for row in range(top, top + size):
                for column in range(left, left + size):
                    result[row][column] = color
        return result
    return None


def reconstruct_occluded_small_template(
    grid: Grid,
) -> Grid | None:
    """Inpaint color-8 occlusion from a repeated small component."""
    height, width = len(grid), len(grid[0])
    signal_colors = sorted(
        {value for row in grid for value in row} - {0, 8}
    )
    if len(signal_colors) != 1:
        return None
    signal = signal_colors[0]
    signal_points = {
        (row, column)
        for row in range(height)
        for column in range(width)
        if grid[row][column] == signal
    }
    occluded = {
        (row, column)
        for row in range(height)
        for column in range(width)
        if grid[row][column] == 8
    }
    if not occluded:
        return None
    templates = []
    for group in cleanup_color_components(grid, signal, 8):
        top, bottom, left, right = point_bbox(group)
        component_height = bottom - top + 1
        component_width = right - left + 1
        if component_height > 3 or component_width > 3:
            continue
        templates.append(
            (
                len(group),
                -component_height * component_width,
                -top,
                -left,
                {(row - top, column - left) for row, column in group},
                component_height,
                component_width,
            )
        )
    if not templates:
        return None
    selected = max(templates, key=lambda item: item[:4])
    template = selected[4]
    template_height, template_width = selected[5], selected[6]
    restored: set[tuple[int, int]] = set()
    for anchor_row in range(-template_height + 1, height):
        for anchor_column in range(
            -template_width + 1, width
        ):
            points = {
                (
                    anchor_row + row,
                    anchor_column + column,
                )
                for row, column in template
                if 0 <= anchor_row + row < height
                and 0 <= anchor_column + column < width
            }
            visible = points - occluded
            if len(visible) >= 3 and visible <= signal_points:
                restored.update(points & occluded)
    result = [row[:] for row in grid]
    for row, column in occluded:
        result[row][column] = (
            signal if (row, column) in restored else 0
        )
    return result


def keep_best_intersecting_full_lines(grid: Grid) -> Grid:
    """Keep the strongest intersecting pair of complete straight lines."""
    height, width = len(grid), len(grid[0])
    lines: list[tuple[str, list[tuple[int, int]]]] = []
    lines.extend(
        (
            "horizontal",
            [(row, column) for column in range(width)],
        )
        for row in range(height)
    )
    lines.extend(
        (
            "vertical",
            [(row, column) for row in range(height)],
        )
        for column in range(width)
    )
    for orientation, delta_column, starts in (
        (
            "down_right",
            1,
            [(0, column) for column in range(width)]
            + [(row, 0) for row in range(1, height)],
        ),
        (
            "down_left",
            -1,
            [(0, column) for column in range(width)]
            + [(row, width - 1) for row in range(1, height)],
        ),
    ):
        for start_row, start_column in starts:
            points = []
            row, column = start_row, start_column
            while 0 <= row < height and 0 <= column < width:
                points.append((row, column))
                row += 1
                column += delta_column
            lines.append((orientation, points))
    complete = []
    for orientation, points in lines:
        values = {grid[row][column] for row, column in points}
        if len(points) >= 2 and len(values) == 1 and 0 not in values:
            complete.append((orientation, points, next(iter(values))))
    pairs = []
    for first_index, first in enumerate(complete):
        for second in complete[first_index + 1 :]:
            if first[0] == second[0] or first[2] != second[2]:
                continue
            union = set(first[1]) | set(second[1])
            if not (set(first[1]) & set(second[1])):
                continue
            pairs.append(
                (
                    -len(first[1]) * len(second[1]),
                    -len(union),
                    first[0],
                    second[0],
                    first,
                    second,
                )
            )
    result = [[0] * width for _ in range(height)]
    if not pairs:
        return result
    selected = min(pairs, key=lambda item: item[:4])
    first, second = selected[4], selected[5]
    for row, column in set(first[1]) | set(second[1]):
        result[row][column] = first[2]
    return result


def sort_objects_by_size_ascending(grid: Grid) -> Grid | None:
    """Sort aligned objects by occupied-cell count along the layout axis."""
    height, width = len(grid), len(grid[0])
    colors = sorted(
        {value for row in grid for value in row} - {0}
    )
    if not colors:
        return None
    objects: list[tuple[int, list[tuple[int, int]]]] = []
    if len(colors) > 1:
        for color in colors:
            objects.append(
                (
                    color,
                    [
                        (row, column)
                        for row in range(height)
                        for column in range(width)
                        if grid[row][column] == color
                    ],
                )
            )
    else:
        color = colors[0]
        objects.extend(
            (color, group)
            for group in cleanup_color_components(grid, color, 8)
        )
    if len(objects) < 2:
        return None
    boxes = [point_bbox(points) for _, points in objects]
    row_centers = [(box[0] + box[1]) / 2 for box in boxes]
    column_centers = [(box[2] + box[3]) / 2 for box in boxes]
    horizontal = (
        max(column_centers) - min(column_centers)
        > max(row_centers) - min(row_centers)
    )
    original_order = sorted(
        range(len(objects)),
        key=lambda index: (
            boxes[index][2] if horizontal else boxes[index][0],
            boxes[index][0] if horizontal else boxes[index][2],
            objects[index][0],
        ),
    )
    gaps = [
        (
            boxes[second][2] - boxes[first][3] - 1
            if horizontal
            else boxes[second][0] - boxes[first][1] - 1
        )
        for first, second in zip(
            original_order, original_order[1:]
        )
    ]
    gap = min(gaps)
    cursor = min(
        box[2] if horizontal else box[0] for box in boxes
    )
    ordered = sorted(
        range(len(objects)),
        key=lambda index: (
            len(objects[index][1]),
            objects[index][0],
            boxes[index],
        ),
    )
    result = [[0] * width for _ in range(height)]
    for index in ordered:
        color, points = objects[index]
        box = boxes[index]
        delta = cursor - (box[2] if horizontal else box[0])
        for row, column in points:
            target_row = row if horizontal else row + delta
            target_column = column + delta if horizontal else column
            if not (
                0 <= target_row < height
                and 0 <= target_column < width
            ):
                return None
            result[target_row][target_column] = color
        cursor += (
            box[3] - box[2] + 1
            if horizontal
            else box[1] - box[0] + 1
        ) + gap
    return result


def top_down_component_color_sequence(
    grid: Grid,
) -> Grid | None:
    """Emit one color per monochrome component in reading order."""
    components = [
        (
            min(row for row, _ in points),
            min(column for _, column in points),
            color,
        )
        for color, points in colored_components(grid, 0, 4)
    ]
    if len(components) < 2:
        return None
    return [[item[2] for item in sorted(components)]]


def sort_uniform_row_runs_descending(grid: Grid) -> Grid | None:
    """Sort full-width nonzero row runs by descending length."""
    height, width = len(grid), len(grid[0])
    if any(len(set(row)) != 1 for row in grid):
        return None
    row_colors = [row[0] for row in grid]
    signal_colors = set(row_colors) - {0}
    if len(signal_colors) != 1:
        return None
    runs: list[tuple[int, int]] = []
    for color in row_colors:
        if runs and runs[-1][0] == color:
            runs[-1] = color, runs[-1][1] + 1
        else:
            runs.append((color, 1))
    nonzero_lengths = sorted(
        (length for color, length in runs if color != 0),
        reverse=True,
    )
    if len(nonzero_lengths) < 2:
        return None
    signal = next(iter(signal_colors))
    rebuilt = []
    cursor = 0
    for color, length in runs:
        if color == 0:
            rebuilt.extend([0] * length)
        else:
            rebuilt.extend([signal] * nonzero_lengths[cursor])
            cursor += 1
    if len(rebuilt) != height:
        return None
    return [[color] * width for color in rebuilt]


def component_sizes_as_bottom_aligned_columns(
    grid: Grid,
) -> Grid | None:
    """Render component sizes as ascending bottom-aligned columns."""
    height, width = len(grid), len(grid[0])
    colors = sorted(
        {value for row in grid for value in row} - {0}
    )
    if len(colors) != 1:
        return None
    color = colors[0]
    components = cleanup_color_components(grid, color, 4)
    if len(components) < 2 or len(components) > width:
        return None
    sizes = sorted(map(len, components))
    if max(sizes) > height:
        return None
    result = [[0] * width for _ in range(height)]
    for column, size in enumerate(sizes):
        for row in range(height - size, height):
            result[row][column] = color
    return result


def sort_vertical_panels_by_nonmodal_count(
    grid: Grid,
) -> Grid | None:
    """Sort equal-width vertical panels by their anomaly count."""
    height, width = len(grid), len(grid[0])
    separator_columns = {
        column
        for column in range(width)
        if all(grid[row][column] == 0 for row in range(height))
    }
    runs = []
    column = 0
    while column < width:
        if column in separator_columns:
            column += 1
            continue
        left = column
        while column < width and column not in separator_columns:
            column += 1
        runs.append((left, column))
    if len(runs) < 2 or len(
        {right - left for left, right in runs}
    ) != 1:
        return None
    panels = []
    for left, right in runs:
        panel = [
            row[left:right] for row in grid
        ]
        counts = Counter(value for row in panel for value in row)
        modal = min(
            counts,
            key=lambda color: (-counts[color], color),
        )
        anomalies = sum(len(row) for row in panel) - counts[modal]
        panels.append((anomalies, panel))
    ordered = sorted(panels, key=lambda item: (item[0], item[1]))
    result = [row[:] for row in grid]
    for (left, right), (_, panel) in zip(runs, ordered):
        for row in range(height):
            result[row][left:right] = panel[row]
    return result


def order_panels_by_distractor_position(
    grid: Grid,
) -> Grid | None:
    """Order panel colors by the vertical position of a distractor."""
    height, width = len(grid), len(grid[0])
    separator_columns = {
        column
        for column in range(width)
        if all(grid[row][column] == 0 for row in range(height))
    }
    runs = []
    column = 0
    while column < width:
        if column in separator_columns:
            column += 1
            continue
        left = column
        while column < width and column not in separator_columns:
            column += 1
        runs.append((left, column))
    if len(runs) < 2:
        return None
    panels = []
    base_colors = []
    for left, right in runs:
        counts = Counter(
            grid[row][column]
            for row in range(height)
            for column in range(left, right)
            if grid[row][column] != 0
        )
        if not counts:
            return None
        base = min(
            counts,
            key=lambda color: (-counts[color], color),
        )
        panels.append((left, right, base))
        base_colors.append(base)
    extras = {
        value for row in grid for value in row
    } - {0} - set(base_colors)
    distractor = next(iter(extras)) if len(extras) == 1 else 0
    base_points = [
        (row, column)
        for left, right, base in panels
        for row in range(height)
        for column in range(left, right)
        if grid[row][column] == base
    ]
    if not base_points:
        return None
    top = min(row for row, _ in base_points)
    bottom = max(row for row, _ in base_points)
    ranked = []
    for left, right, base in panels:
        positions = [
            row
            for row in range(height)
            for column in range(left, right)
            if grid[row][column] == distractor
            and (distractor != 0 or top <= row <= bottom)
        ]
        score = min(positions) if positions else height
        ranked.append((-score, base, left, right))
    ranked.sort()
    result = [[0] * width for _ in range(height)]
    for (left, right), (_, base, _, _) in zip(runs, ranked):
        for row in range(top, bottom + 1):
            result[row][left:right] = [base] * (right - left)
    return result


def order_two_panels_by_component_count(
    grid: Grid,
) -> Grid | None:
    """Place the panel with fewer identical objects to the left."""
    height, width = len(grid), len(grid[0])
    divider_columns = []
    for column in range(width):
        values = {grid[row][column] for row in range(height)}
        if len(values) == 1 and next(iter(values)) != 0:
            divider_columns.append(column)
    if len(divider_columns) != 1:
        return None
    divider = divider_columns[0]
    if (
        divider == 0
        or divider == width - 1
        or divider != width - divider - 1
    ):
        return None
    divider_color = grid[0][divider]
    panels = [
        [row[:divider] for row in grid],
        [row[divider + 1 :] for row in grid],
    ]
    colors = {
        value for panel in panels for row in panel for value in row
    }
    signal_colors = colors - {0}
    if len(signal_colors) != 1 or divider_color in signal_colors:
        return None
    signal = next(iter(signal_colors))
    component_sets = [
        cleanup_color_components(panel, signal, 4) for panel in panels
    ]
    if any(not components for components in component_sets):
        return None
    shapes = []
    for components in component_sets:
        for points in components:
            top = min(row for row, _ in points)
            bottom = max(row for row, _ in points)
            left = min(column for _, column in points)
            right = max(column for _, column in points)
            normalized = tuple(
                sorted(
                    (row - top, column - left)
                    for row, column in points
                )
            )
            if len(points) != (bottom - top + 1) * (right - left + 1):
                return None
            shapes.append(normalized)
    if len(set(shapes)) != 1:
        return None
    if len(component_sets[0]) <= len(component_sets[1]):
        return [row[:] for row in grid]
    result = [row[:] for row in grid]
    for row in range(height):
        result[row][:divider] = panels[1][row]
        result[row][divider + 1 :] = panels[0][row]
    return result


def sort_marker_panels_by_count(
    grid: Grid,
) -> Grid | None:
    """Sort panels bounded by uniform bars by ascending marker count."""
    height, width = len(grid), len(grid[0])
    separators = []
    for column in range(width):
        values = {grid[row][column] for row in range(height)}
        if len(values) == 1 and next(iter(values)) != 0:
            separators.append(column)
    if (
        len(separators) < 3
        or separators[0] != 0
        or separators[-1] != width - 1
    ):
        return None
    separator_colors = {grid[0][column] for column in separators}
    if len(separator_colors) != 1:
        return None
    separator_color = next(iter(separator_colors))
    widths = [
        right - left - 1
        for left, right in zip(separators, separators[1:])
    ]
    if not widths or min(widths) < 1 or len(set(widths)) != 1:
        return None
    if any(
        right - left != widths[0] + 1
        for left, right in zip(separators, separators[1:])
    ):
        return None
    panels = [
        [row[left + 1 : right] for row in grid]
        for left, right in zip(separators, separators[1:])
    ]
    colors = {
        value for panel in panels for row in panel for value in row
    } - {0}
    if len(colors) != 1 or separator_color in colors:
        return None
    signal = next(iter(colors))
    ordered = sorted(
        panels,
        key=lambda panel: (
            sum(value == signal for row in panel for value in row),
            panel,
        ),
    )
    result = [row[:] for row in grid]
    for (left, right), panel in zip(
        zip(separators, separators[1:]), ordered
    ):
        for row in range(height):
            result[row][left + 1 : right] = panel[row]
    return result


def copy_motif_into_hollow_frame(grid: Grid) -> Grid | None:
    """Center a separate motif inside a monochrome hollow rectangle."""
    height, width = len(grid), len(grid[0])
    frames = []
    for color in sorted(
        {value for row in grid for value in row} - {0}
    ):
        for component in cleanup_color_components(grid, color, 4):
            top = min(row for row, _ in component)
            bottom = max(row for row, _ in component)
            left = min(column for _, column in component)
            right = max(column for _, column in component)
            if bottom - top < 2 or right - left < 2:
                continue
            perimeter = {
                (row, column)
                for row in range(top, bottom + 1)
                for column in range(left, right + 1)
                if row in (top, bottom) or column in (left, right)
            }
            if set(component) == perimeter:
                frames.append(
                    (color, component, (top, bottom, left, right))
                )
    if not frames:
        return None
    maximum_area = max(
        (bottom - top + 1) * (right - left + 1)
        for _, _, (top, bottom, left, right) in frames
    )
    frames = [
        item
        for item in frames
        if (item[2][1] - item[2][0] + 1)
        * (item[2][3] - item[2][2] + 1)
        == maximum_area
    ]
    if len(frames) != 1:
        return None
    _, component, (top, bottom, left, right) = frames[0]
    frame_points = set(component)
    source_points = [
        (row, column)
        for row in range(height)
        for column in range(width)
        if grid[row][column] != 0
        and (row, column) not in frame_points
        and not (top < row < bottom and left < column < right)
    ]
    if not source_points:
        return None
    source_top = min(row for row, _ in source_points)
    source_bottom = max(row for row, _ in source_points)
    source_left = min(column for _, column in source_points)
    source_right = max(column for _, column in source_points)
    source_height = source_bottom - source_top + 1
    source_width = source_right - source_left + 1
    interior_height = bottom - top - 1
    interior_width = right - left - 1
    if source_height > interior_height or source_width > interior_width:
        return None
    target_top = top + 1 + (interior_height - source_height) // 2
    target_left = left + 1 + (interior_width - source_width) // 2
    result = [row[:] for row in grid]
    for row in range(source_height):
        for column in range(source_width):
            value = grid[source_top + row][source_left + column]
            if value != 0:
                result[target_top + row][target_left + column] = value
    return result


def stamp_template_at_singletons(grid: Grid) -> Grid | None:
    """Use same-color singleton cells as top-left copy anchors."""
    height, width = len(grid), len(grid[0])
    candidates = []
    for color in sorted(
        {value for row in grid for value in row} - {0}
    ):
        components = cleanup_color_components(grid, color, 4)
        large = [component for component in components if len(component) > 1]
        singletons = [
            component[0] for component in components if len(component) == 1
        ]
        if len(large) != 1 or not singletons:
            continue
        top = min(row for row, _ in large[0])
        bottom = max(row for row, _ in large[0])
        left = min(column for _, column in large[0])
        right = max(column for _, column in large[0])
        if grid[top][left] != color:
            continue
        crop = [row[left : right + 1] for row in grid[top : bottom + 1]]
        if len(crop) * len(crop[0]) <= 1:
            continue
        if any(
            row + len(crop) > height
            or column + len(crop[0]) > width
            for row, column in singletons
        ):
            continue
        candidates.append((crop, singletons))
    if len(candidates) != 1:
        return None
    crop, singletons = candidates[0]
    result = [row[:] for row in grid]
    for target_top, target_left in singletons:
        for row in range(len(crop)):
            for column in range(len(crop[0])):
                value = crop[row][column]
                if value != 0:
                    existing = result[target_top + row][target_left + column]
                    if existing not in (0, value):
                        return None
                    result[target_top + row][target_left + column] = value
    return result


def repeat_template_from_unit_markers(grid: Grid) -> Grid | None:
    """Repeat a template once for each trailing unit-color marker."""
    height, width = len(grid), len(grid[0])
    horizontal_columns = []
    column = width - 1
    while column >= 0:
        values = {grid[row][column] for row in range(height)}
        if (
            values <= {0, 1}
            and sum(grid[row][column] == 1 for row in range(height)) == 1
        ):
            horizontal_columns.append(column)
            column -= 1
        else:
            break
    vertical_rows = []
    row = height - 1
    while row >= 0:
        values = set(grid[row])
        if values <= {0, 1} and grid[row].count(1) == 1:
            vertical_rows.append(row)
            row -= 1
        else:
            break
    candidates = []
    if horizontal_columns:
        start = min(horizontal_columns)
        template = [row[:start] for row in grid]
        markers = sum(
            grid[row][column] == 1
            for row in range(height)
            for column in range(start, width)
        )
        if template and template[0] and any(
            value not in (0, 1) for row in template for value in row
        ):
            candidates.append(("horizontal", template, markers))
    if vertical_rows:
        start = min(vertical_rows)
        template = [row[:] for row in grid[:start]]
        markers = sum(
            grid[row][column] == 1
            for row in range(start, height)
            for column in range(width)
        )
        if template and any(
            value not in (0, 1) for row in template for value in row
        ):
            candidates.append(("vertical", template, markers))
    if len(candidates) != 1:
        return None
    orientation, template, markers = candidates[0]
    if markers < 1:
        return None
    copies = markers + 1
    if orientation == "horizontal":
        result = []
        for row in template:
            output_row = []
            for index in range(copies):
                if index:
                    output_row.append(0)
                output_row.extend(row)
            result.append(output_row)
        return result
    result = []
    for index in range(copies):
        if index:
            result.append([0] * len(template[0]))
        result.extend(row[:] for row in template)
    return result


def duplicate_grid_along_short_axis(grid: Grid) -> Grid | None:
    """Duplicate a rectangular grid across its shorter dimension."""
    height, width = len(grid), len(grid[0])
    if height == width:
        return None
    if height < width:
        return (
            [row[:] for row in grid]
            + [[0] * width]
            + [row[:] for row in grid]
        )
    return [row[:] + [0] + row[:] for row in grid]


def copy_container_around_repeated_interior(
    grid: Grid,
) -> Grid | None:
    """Copy a surrounding scaffold around a standalone interior motif."""
    height, width = len(grid), len(grid[0])
    candidates = []
    colors = sorted(
        {value for row in grid for value in row} - {0}
    )
    for outer in colors:
        outer_points = [
            (row, column)
            for row in range(height)
            for column in range(width)
            if grid[row][column] == outer
        ]
        if len(outer_points) < 2:
            continue
        top = min(row for row, _ in outer_points)
        bottom = max(row for row, _ in outer_points)
        left = min(column for _, column in outer_points)
        right = max(column for _, column in outer_points)
        inner_points = [
            (row, column)
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
            if grid[row][column] not in (0, outer)
        ]
        if not inner_points:
            continue
        inner_colors = {
            grid[row][column] for row, column in inner_points
        }
        outside_points = [
            (row, column)
            for row in range(height)
            for column in range(width)
            if not (top <= row <= bottom and left <= column <= right)
            and grid[row][column] in inner_colors
        ]
        if not outside_points:
            continue
        inner_top = min(row for row, _ in inner_points)
        inner_bottom = max(row for row, _ in inner_points)
        inner_left = min(column for _, column in inner_points)
        inner_right = max(column for _, column in inner_points)
        target_top = min(row for row, _ in outside_points)
        target_bottom = max(row for row, _ in outside_points)
        target_left = min(column for _, column in outside_points)
        target_right = max(column for _, column in outside_points)
        if (
            inner_bottom - inner_top != target_bottom - target_top
            or inner_right - inner_left != target_right - target_left
        ):
            continue
        delta_row = target_top - inner_top
        delta_column = target_left - inner_left
        if any(
            grid[row][column]
            != grid[row - delta_row][column - delta_column]
            for row in range(target_top, target_bottom + 1)
            for column in range(target_left, target_right + 1)
        ):
            continue
        shifted_outer = [
            (row + delta_row, column + delta_column)
            for row, column in outer_points
        ]
        if not all(
            0 <= row < height and 0 <= column < width
            for row, column in shifted_outer
        ):
            continue
        if any(
            grid[row][column] not in (0, outer)
            for row, column in shifted_outer
        ):
            continue
        candidates.append((outer, shifted_outer))
    if len(candidates) != 1:
        return None
    outer, shifted_outer = candidates[0]
    result = [row[:] for row in grid]
    for row, column in shifted_outer:
        result[row][column] = outer
    return result


def copy_richer_panel_to_matching_panel(grid: Grid) -> Grid | None:
    """Complete a poorer panel from a translated richer matching panel."""
    height, width = len(grid), len(grid[0])

    def occupied_runs(flags: list[bool]) -> list[tuple[int, int]]:
        runs = []
        index = 0
        while index < len(flags):
            if not flags[index]:
                index += 1
                continue
            start = index
            while index < len(flags) and flags[index]:
                index += 1
            runs.append((start, index))
        return runs

    column_runs = occupied_runs(
        [
            any(grid[row][column] != 0 for row in range(height))
            for column in range(width)
        ]
    )
    row_runs = occupied_runs(
        [
            any(grid[row][column] != 0 for column in range(width))
            for row in range(height)
        ]
    )
    axes = []
    if len(column_runs) == 2 and len(row_runs) == 1:
        axes.append(("horizontal", column_runs))
    if len(row_runs) == 2 and len(column_runs) == 1:
        axes.append(("vertical", row_runs))
    if len(axes) != 1:
        return None
    orientation, runs = axes[0]
    panel_points = []
    for start, end in runs:
        points = [
            (row, column, grid[row][column])
            for row in range(height)
            for column in range(width)
            if grid[row][column] != 0
            and (
                start <= column < end
                if orientation == "horizontal"
                else start <= row < end
            )
        ]
        panel_points.append(points)
    counts = [len(points) for points in panel_points]
    if counts[0] == counts[1]:
        return None
    source_index = 0 if counts[0] > counts[1] else 1
    target_index = 1 - source_index
    source = panel_points[source_index]
    target = panel_points[target_index]
    target_colors = {value for _, _, value in target}
    source_colors = {value for _, _, value in source}
    source_start, source_end = runs[source_index]
    region = {
        (row, column)
        for row in range(height)
        for column in range(width)
        if (
            source_start <= column < source_end
            if orientation == "horizontal"
            else source_start <= row < source_end
        )
    }
    common_source_points = {
        (row, column)
        for row, column, value in source
        if value in target_colors
    }
    for exclusive_color in source_colors - target_colors:
        obstacles = {
            (row, column)
            for row, column, value in source
            if value == exclusive_color
        }
        boundary = {
            point
            for point in region
            if (
                point[0] in (0, height - 1)
                or point[1] in (source_start, source_end - 1)
                if orientation == "horizontal"
                else point[0] in (source_start, source_end - 1)
                or point[1] in (0, width - 1)
            )
            and point not in obstacles
        }
        reachable = set(boundary)
        queue = deque(boundary)
        while queue:
            row, column = queue.popleft()
            for delta_row, delta_column in (
                (-1, 0),
                (1, 0),
                (0, -1),
                (0, 1),
            ):
                point = row + delta_row, column + delta_column
                if (
                    point in region
                    and point not in obstacles
                    and point not in reachable
                ):
                    reachable.add(point)
                    queue.append(point)
        if common_source_points - reachable:
            return None
    target_lookup = {
        (row, column): value for row, column, value in target
    }
    deltas = set()
    for source_row, source_column, source_value in source:
        for target_row, target_column, target_value in target:
            if source_value != target_value:
                continue
            delta_row = target_row - source_row
            delta_column = target_column - source_column
            if (
                orientation == "horizontal" and delta_row == 0
            ) or (
                orientation == "vertical" and delta_column == 0
            ):
                deltas.add((delta_row, delta_column))
    valid = []
    for delta_row, delta_column in deltas:
        shifted_lookup = {
            (row + delta_row, column + delta_column): value
            for row, column, value in source
            if 0 <= row + delta_row < height
            and 0 <= column + delta_column < width
        }
        if len(shifted_lookup) != len(source):
            continue
        if not all(
            shifted_lookup.get(point) == value
            for point, value in target_lookup.items()
        ):
            continue
        if any(
            grid[row][column] not in (0, value)
            for (row, column), value in shifted_lookup.items()
        ):
            continue
        valid.append(shifted_lookup)
    if len(valid) != 1:
        return None
    result = [row[:] for row in grid]
    for (row, column), value in valid[0].items():
        result[row][column] = value
    return result


def complete_partial_same_color_copies(grid: Grid) -> Grid | None:
    """Complete smaller same-color components from a unique full template."""
    height, width = len(grid), len(grid[0])
    result = [row[:] for row in grid]
    changed = False
    for color in sorted(
        {value for row in grid for value in row} - {0}
    ):
        components = cleanup_color_components(grid, color, 8)
        if len(components) < 2:
            continue
        maximum = max(map(len, components))
        templates = [
            component for component in components if len(component) == maximum
        ]
        partials = [
            component for component in components if len(component) < maximum
        ]
        if len(templates) != 1 or not partials:
            continue
        template = templates[0]
        template_top = min(row for row, _ in template)
        template_bottom = max(row for row, _ in template)
        template_left = min(column for _, column in template)
        template_right = max(column for _, column in template)
        for partial in partials:
            partial_top = min(row for row, _ in partial)
            partial_bottom = max(row for row, _ in partial)
            partial_left = min(column for _, column in partial)
            partial_right = max(column for _, column in partial)
            row_numerator = (
                partial_top
                + partial_bottom
                - template_top
                - template_bottom
            )
            column_numerator = (
                partial_left
                + partial_right
                - template_left
                - template_right
            )
            if row_numerator % 2 or column_numerator % 2:
                continue
            delta_row = row_numerator // 2
            delta_column = column_numerator // 2
            shifted = {
                (row + delta_row, column + delta_column)
                for row, column in template
            }
            if not all(
                0 <= row < height and 0 <= column < width
                for row, column in shifted
            ):
                continue
            partial_marks_center = (
                len(partial) == 1
                and 2 * partial[0][0]
                == min(row for row, _ in shifted)
                + max(row for row, _ in shifted)
                and 2 * partial[0][1]
                == min(column for _, column in shifted)
                + max(column for _, column in shifted)
            )
            if not set(partial) <= shifted and not partial_marks_center:
                continue
            if any(
                result[row][column] not in (0, color)
                for row, column in shifted
            ):
                continue
            for row, column in partial:
                result[row][column] = 0
            for row, column in shifted:
                result[row][column] = color
            changed = True
    return result if changed else None


def transfer_secondary_pattern_to_other_shape(
    grid: Grid,
) -> Grid | None:
    """Transfer an embedded secondary pattern to a second base shape."""
    height, width = len(grid), len(grid[0])
    remaining = {
        (row, column)
        for row in range(height)
        for column in range(width)
        if grid[row][column] != 0
    }
    components = []
    deltas = [
        (-1, 0),
        (1, 0),
        (0, -1),
        (0, 1),
        (-1, -1),
        (-1, 1),
        (1, -1),
        (1, 1),
    ]
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        queue = deque([start])
        component = []
        while queue:
            row, column = queue.popleft()
            component.append((row, column))
            for delta_row, delta_column in deltas:
                point = row + delta_row, column + delta_column
                if point in remaining:
                    remaining.remove(point)
                    queue.append(point)
        components.append(component)
    if len(components) != 2:
        return None
    color_sets = [
        {grid[row][column] for row, column in component}
        for component in components
    ]
    source_indices = [
        index for index, colors in enumerate(color_sets) if len(colors) == 2
    ]
    target_indices = [
        index for index, colors in enumerate(color_sets) if len(colors) == 1
    ]
    if len(source_indices) != 1 or len(target_indices) != 1:
        return None
    source_index = source_indices[0]
    target_index = target_indices[0]
    source_points = components[source_index]
    target_points = components[target_index]
    source_counts = {
        color: sum(
            grid[row][column] == color
            for row, column in source_points
        )
        for color in color_sets[source_index]
    }
    base = min(
        source_counts,
        key=lambda color: (-source_counts[color], color),
    )
    secondary_colors = color_sets[source_index] - {base}
    if len(secondary_colors) != 1:
        return None
    secondary = next(iter(secondary_colors))
    source_top = min(row for row, _ in source_points)
    source_bottom = max(row for row, _ in source_points)
    source_left = min(column for _, column in source_points)
    source_right = max(column for _, column in source_points)
    target_top = min(row for row, _ in target_points)
    target_bottom = max(row for row, _ in target_points)
    target_left = min(column for _, column in target_points)
    target_right = max(column for _, column in target_points)
    source_crop = [
        row[source_left : source_right + 1]
        for row in grid[source_top : source_bottom + 1]
    ]
    source_occupancy = [
        [value != 0 for value in row] for row in source_crop
    ]
    source_secondary = [
        [value == secondary for value in row] for row in source_crop
    ]
    target_crop = [
        row[target_left : target_right + 1]
        for row in grid[target_top : target_bottom + 1]
    ]
    target_occupancy = [
        [value != 0 for value in row] for row in target_crop
    ]
    variants = [
        (source_occupancy, source_secondary),
        (
            flip_horizontal(source_occupancy),
            flip_horizontal(source_secondary),
        ),
        (
            flip_vertical(source_occupancy),
            flip_vertical(source_secondary),
        ),
        (
            rotate_180(source_occupancy),
            rotate_180(source_secondary),
        ),
        (
            transpose(source_occupancy),
            transpose(source_secondary),
        ),
        (
            anti_transpose(source_occupancy),
            anti_transpose(source_secondary),
        ),
        (
            rotate_90(source_occupancy),
            rotate_90(source_secondary),
        ),
        (
            rotate_270(source_occupancy),
            rotate_270(source_secondary),
        ),
    ]

    def resize_nearest(array: Grid) -> Grid:
        source_height, source_width = len(array), len(array[0])
        target_height, target_width = (
            len(target_occupancy),
            len(target_occupancy[0]),
        )
        rows = [
            0
            if target_height == 1
            else round(
                row * (source_height - 1) / (target_height - 1)
            )
            for row in range(target_height)
        ]
        columns = [
            0
            if target_width == 1
            else round(
                column * (source_width - 1) / (target_width - 1)
            )
            for column in range(target_width)
        ]
        return [
            [array[row][column] for column in columns] for row in rows
        ]

    matches = []
    for occupancy, secondary_mask in variants:
        resized_occupancy = resize_nearest(occupancy)
        mismatch = sum(
            resized_occupancy[row][column]
            != target_occupancy[row][column]
            for row in range(len(target_occupancy))
            for column in range(len(target_occupancy[0]))
        )
        matches.append((mismatch, resize_nearest(secondary_mask)))
    minimum_mismatch = min(item[0] for item in matches)
    secondary_mask = next(
        mask for mismatch, mask in matches if mismatch == minimum_mismatch
    )
    result = [row[:] for row in grid]
    for row in range(len(secondary_mask)):
        for column in range(len(secondary_mask[0])):
            if secondary_mask[row][column]:
                result[target_top + row][target_left + column] = secondary
    return result


def copy_by_repeated_anchor_translation(grid: Grid) -> Grid | None:
    """Copy all visible source cells along a repeated-anchor translation."""
    height, width = len(grid), len(grid[0])
    points = [
        (row, column, grid[row][column])
        for row in range(height)
        for column in range(width)
        if grid[row][column] != 0
    ]
    if len(points) > 64:
        return None
    deltas = {
        (target_row - source_row, target_column - source_column)
        for source_row, source_column, source_value in points
        for target_row, target_column, target_value in points
        if source_value == target_value
        and (
            abs(target_row - source_row)
            + abs(target_column - source_column)
            >= 3
        )
    }
    point_lookup = {
        (row, column): value for row, column, value in points
    }
    candidates = []
    for delta_row, delta_column in deltas:
        shifted = [
            (row + delta_row, column + delta_column, value)
            for row, column, value in points
            if 0 <= row + delta_row < height
            and 0 <= column + delta_column < width
            and point_lookup.get(
                (row - delta_row, column - delta_column)
            )
            != value
        ]
        if not shifted:
            continue
        if any(
            grid[row][column] not in (0, value)
            for row, column, value in shifted
        ):
            continue
        overlap = sum(
            grid[row][column] == value
            for row, column, value in shifted
        )
        additions = sum(
            grid[row][column] == 0 for row, column, _ in shifted
        )
        if overlap < 2 or additions < 1:
            continue
        result = [row[:] for row in grid]
        for row, column, value in shifted:
            result[row][column] = value
        distance = abs(delta_row) + abs(delta_column)
        candidates.append(
            (
                overlap * additions * distance,
                overlap,
                additions,
                distance,
                result,
            )
        )
    if not candidates:
        return None
    best_score = max(item[:4] for item in candidates)
    predictions = {
        tuple(tuple(row) for row in item[4]): item[4]
        for item in candidates
        if item[:4] == best_score
    }
    return next(iter(predictions.values())) if len(predictions) == 1 else None


def complete_sparse_cross_lines(grid: Grid) -> Grid | None:
    """Complete orthogonal period-two dotted lines into a solid cross."""
    height, width = len(grid), len(grid[0])
    horizontal = []
    vertical = []
    for row in range(height):
        points = [
            (column, grid[row][column])
            for column in range(width)
            if grid[row][column] != 0
        ]
        if len(points) < 3 or len({value for _, value in points}) != 1:
            continue
        columns = [column for column, _ in points]
        if all(
            second - first == 2
            for first, second in zip(columns, columns[1:])
        ):
            horizontal.append((points[0][1], row))
    for column in range(width):
        points = [
            (row, grid[row][column])
            for row in range(height)
            if grid[row][column] != 0
        ]
        if len(points) < 2 or len({value for _, value in points}) != 1:
            continue
        rows = [row for row, _ in points]
        if all(
            second - first == 2
            for first, second in zip(rows, rows[1:])
        ):
            vertical.append((points[0][1], column))
    if len(horizontal) != 1 or len(vertical) != 1:
        return None
    horizontal_color, row = horizontal[0]
    vertical_color, column = vertical[0]
    result = [values[:] for values in grid]
    for target_row in range(height):
        result[target_row][column] = vertical_color
    result[row] = [horizontal_color] * width
    return result


def replace_parallel_sides_with_missing_sides(
    grid: Grid,
) -> Grid | None:
    """Replace two parallel rectangle sides with the missing pair."""
    height, width = len(grid), len(grid[0])
    colors = sorted(
        {value for row in grid for value in row} - {0}
    )
    if len(colors) != 1:
        return None
    color = colors[0]
    points = [
        (row, column)
        for row in range(height)
        for column in range(width)
        if grid[row][column] == color
    ]
    rows = sorted({row for row, _ in points})
    columns = sorted({column for _, column in points})
    result = [[0] * width for _ in range(height)]
    if len(rows) == 2:
        column_sets = [
            {
                column
                for point_row, column in points
                if point_row == row
            }
            for row in rows
        ]
        if column_sets[0] != column_sets[1] or len(column_sets[0]) < 2:
            return None
        ordered = sorted(column_sets[0])
        if ordered != list(range(ordered[0], ordered[-1] + 1)):
            return None
        for row in range(rows[0] + 1, rows[1]):
            result[row][ordered[0]] = color
            result[row][ordered[-1]] = color
        return result
    if len(columns) == 2:
        row_sets = [
            {
                row
                for row, point_column in points
                if point_column == column
            }
            for column in columns
        ]
        if row_sets[0] != row_sets[1] or len(row_sets[0]) < 2:
            return None
        ordered = sorted(row_sets[0])
        if ordered != list(range(ordered[0], ordered[-1] + 1)):
            return None
        for column in range(columns[0] + 1, columns[1]):
            result[ordered[0]][column] = color
            result[ordered[-1]][column] = color
        return result
    return None


def complete_l_trominoes_with_other_color(
    grid: Grid,
) -> Grid | None:
    """Complete each monochrome 2x2 L with color three or four."""
    height, width = len(grid), len(grid[0])
    colors = sorted(
        {value for row in grid for value in row} - {0}
    )
    if not colors or not set(colors) <= {3, 4}:
        return None
    proposals: dict[tuple[int, int], int] = {}
    for top in range(height - 1):
        for left in range(width - 1):
            points = [
                (top + row, left + column)
                for row in range(2)
                for column in range(2)
            ]
            values = [grid[row][column] for row, column in points]
            nonzero = [value for value in values if value != 0]
            if (
                len(nonzero) != 3
                or len(set(nonzero)) != 1
                or nonzero[0] not in (3, 4)
            ):
                continue
            target = 7 - nonzero[0]
            missing = points[values.index(0)]
            previous = proposals.get(missing)
            if previous is not None and previous != target:
                return None
            proposals[missing] = target
    if not proposals:
        return None
    result = [row[:] for row in grid]
    for (row, column), color in proposals.items():
        result[row][column] = color
    return result


def complete_from_color_five_template(grid: Grid) -> Grid | None:
    """Complete partial colored copies of a color-five template."""
    height, width = len(grid), len(grid[0])
    remaining_five = {
        (row, column)
        for row in range(height)
        for column in range(width)
        if grid[row][column] == 5
    }
    if not remaining_five:
        return None
    template_components = []
    while remaining_five:
        start = min(remaining_five)
        remaining_five.remove(start)
        queue = deque([start])
        component = []
        while queue:
            point = queue.popleft()
            component.append(point)
            neighbors = {
                candidate
                for candidate in remaining_five
                if max(
                    abs(candidate[0] - point[0]),
                    abs(candidate[1] - point[1]),
                )
                <= 2
            }
            remaining_five -= neighbors
            queue.extend(neighbors)
        template_components.append(component)
    maximum = max(map(len, template_components))
    templates = [
        component
        for component in template_components
        if len(component) == maximum
    ]
    if len(templates) != 1 or maximum < 3:
        return None
    template = templates[0]
    template_set = set(template)
    top = min(row for row, _ in template)
    left = min(column for _, column in template)
    mask = {
        (row - top, column - left) for row, column in template
    }
    mask_height = max(row for row, _ in mask) + 1
    mask_width = max(column for _, column in mask) + 1
    result = [row[:] for row in grid]
    for row, column in template:
        result[row][column] = 0
    target_colors = sorted(
        {value for row in grid for value in row} - {0}
    )
    completed = 0
    for color in target_colors:
        points = [
            (row, column)
            for row in range(height)
            for column in range(width)
            if grid[row][column] == color
            and (color != 5 or (row, column) not in template_set)
        ]
        if not points:
            continue
        first = points[0]
        candidates = []
        for mask_row, mask_column in mask:
            target_top = first[0] - mask_row
            target_left = first[1] - mask_column
            shifted = {
                (target_top + row, target_left + column)
                for row, column in mask
            }
            if not (
                0 <= target_top
                and target_top + mask_height <= height
                and 0 <= target_left
                and target_left + mask_width <= width
            ):
                continue
            if not set(points) <= shifted:
                continue
            if any(
                grid[row][column] not in (0, color, 5)
                for row, column in shifted
            ):
                continue
            candidates.append(shifted)
        unique = {
            tuple(sorted(candidate)): candidate for candidate in candidates
        }
        if not unique:
            return None
        chosen = max(
            unique.values(),
            key=lambda candidate: (
                min(row for row, _ in candidate),
                min(column for _, column in candidate),
            ),
        )
        for row, column in chosen:
            result[row][column] = color
        completed += 1
    return result if completed else None


def fill_single_missing_symmetry_cell(grid: Grid) -> Grid | None:
    """Fill the unique zero bracketed by the shape on opposite sides."""
    height, width = len(grid), len(grid[0])
    colors = sorted(
        {value for row in grid for value in row} - {0}
    )
    if len(colors) != 1:
        return None
    color = colors[0]
    points = [
        (row, column)
        for row in range(height)
        for column in range(width)
        if grid[row][column] == color
    ]
    top = min(row for row, _ in points)
    bottom = max(row for row, _ in points)
    left = min(column for _, column in points)
    right = max(column for _, column in points)
    candidates = []
    for row in range(top, bottom + 1):
        for column in range(left, right + 1):
            if grid[row][column] != 0:
                continue
            horizontal = (
                column > 0
                and column + 1 < width
                and grid[row][column - 1] == color
                and grid[row][column + 1] == color
            )
            vertical = (
                row > 0
                and row + 1 < height
                and grid[row - 1][column] == color
                and grid[row + 1][column] == color
            )
            if horizontal or vertical:
                candidates.append((row, column))
    if len(candidates) != 1:
        return None
    result = [row[:] for row in grid]
    row, column = candidates[0]
    result[row][column] = color
    return result


def reflection_completion_about_axis(
    grid: Grid,
    center_twice: int,
    axis: str,
) -> Grid | None:
    """Reflect every colored cell about one possibly half-cell axis."""
    height, width = len(grid), len(grid[0])
    result = [row[:] for row in grid]
    proposals: dict[tuple[int, int], int] = {}
    for row in range(height):
        for column in range(width):
            color = grid[row][column]
            if color == 0:
                continue
            if axis == "rows":
                target = center_twice - row, column
            else:
                target = row, center_twice - column
            target_row, target_column = target
            if not (
                0 <= target_row < height
                and 0 <= target_column < width
            ):
                return None
            existing = grid[target_row][target_column]
            if existing not in (0, color):
                return None
            previous = proposals.get(target)
            if previous is not None and previous != color:
                return None
            proposals[target] = color
    for (row, column), color in proposals.items():
        result[row][column] = color
    return result


def complete_largest_color_reflection(grid: Grid) -> Grid | None:
    """Complete the richer reflection around the dominant color's center."""
    colors = sorted(
        {value for row in grid for value in row} - {0}
    )
    if not colors:
        return None
    counts = Counter(
        value for row in grid for value in row if value != 0
    )
    maximum = max(counts.values())
    dominant = [
        color for color, count in counts.items() if count == maximum
    ]
    if len(dominant) != 1:
        return None
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == dominant[0]
    ]
    top, bottom, left, right = point_bbox(points)
    candidates: list[tuple[int, Grid]] = []
    for axis, center_twice in (
        ("rows", top + bottom),
        ("columns", left + right),
    ):
        result = reflection_completion_about_axis(
            grid, center_twice, axis
        )
        if result is None:
            continue
        additions = sum(
            source == 0 and target != 0
            for source_row, target_row in zip(grid, result)
            for source, target in zip(source_row, target_row)
        )
        if additions:
            candidates.append((additions, result))
    if not candidates:
        return None
    best_count = max(additions for additions, _ in candidates)
    if len(colors) == 1 and best_count == 1:
        return None
    best = [
        result
        for additions, result in candidates
        if additions == best_count
    ]
    if any(result != best[0] for result in best[1:]):
        return None
    return best[0]


def repair_monochrome_bilateral_symmetry(
    grid: Grid,
) -> Grid | None:
    """Repair the smallest nonempty reflection defect in one solid shape."""
    colors = sorted(
        {value for row in grid for value in row} - {0}
    )
    if len(colors) != 1:
        return None
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == colors[0]
    ]
    top, bottom, left, right = point_bbox(points)
    candidates: list[tuple[int, Grid]] = []
    for axis, center_twice in (
        ("rows", top + bottom),
        ("columns", left + right),
    ):
        result = reflection_completion_about_axis(
            grid, center_twice, axis
        )
        if result is None:
            continue
        additions = sum(
            source == 0 and target != 0
            for source_row, target_row in zip(grid, result)
            for source, target in zip(source_row, target_row)
        )
        if additions:
            candidates.append((additions, result))
    if not candidates:
        return None
    best_count = min(additions for additions, _ in candidates)
    if best_count == 1:
        return None
    best = [
        result
        for additions, result in candidates
        if additions == best_count
    ]
    if any(result != best[0] for result in best[1:]):
        return None
    return best[0]


def extend_center_toward_largest_margin(
    grid: Grid,
) -> Grid | None:
    """Extend a shape's central axis into its uniquely largest margin."""
    background = mode_color(grid)
    colors = sorted(
        {value for row in grid for value in row} - {background}
    )
    if len(colors) != 1:
        return None
    height, width = len(grid), len(grid[0])
    points = [
        (row, column)
        for row in range(height)
        for column in range(width)
        if grid[row][column] != background
    ]
    top, bottom, left, right = point_bbox(points)
    margins = {
        "up": top,
        "down": height - 1 - bottom,
        "left": left,
        "right": width - 1 - right,
    }
    maximum = max(margins.values())
    directions = [
        direction
        for direction, margin in margins.items()
        if margin == maximum
    ]
    if maximum == 0 or len(directions) != 1:
        return None
    direction = directions[0]
    color = colors[0]
    result = [row[:] for row in grid]
    if direction in ("left", "right"):
        row = (top + bottom) // 2
        columns = (
            range(0, left)
            if direction == "left"
            else range(right + 1, width)
        )
        for column in columns:
            if result[row][column] != background:
                return None
            result[row][column] = color
    else:
        column = (left + right) // 2
        rows = (
            range(0, top)
            if direction == "up"
            else range(bottom + 1, height)
        )
        for row in rows:
            if result[row][column] != background:
                return None
            result[row][column] = color
    return result


def extend_unique_marker_vertical_until_blocked(
    grid: Grid,
) -> Grid | None:
    """Extend a unique marker vertically to blockers on both sides."""
    background = mode_color(grid)
    counts = Counter(
        value
        for row in grid
        for value in row
        if value != background
    )
    markers = [
        color for color, count in counts.items() if count == 1
    ]
    if len(counts) < 2 or len(markers) != 1:
        return None
    marker = markers[0]
    row, column = next(
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == marker
    )
    result = [values[:] for values in grid]
    additions = 0
    for delta_row in (-1, 1):
        cursor = row + delta_row
        blocked = False
        while 0 <= cursor < len(grid):
            value = grid[cursor][column]
            if value != background:
                blocked = True
                break
            result[cursor][column] = marker
            additions += 1
            cursor += delta_row
        if not blocked:
            return None
    return result if additions else None


def periodic_line_candidates(
    grid: Grid,
) -> list[tuple[str, int, set[tuple[int, int]]]]:
    """Return period-two straight-line point sets."""
    background = mode_color(grid)
    found: dict[
        tuple[str, int, tuple[tuple[int, int], ...]],
        tuple[str, int, set[tuple[int, int]]],
    ] = {}
    for color in sorted(
        {value for row in grid for value in row} - {background}
    ):
        points = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ]
        buckets: list[
            tuple[
                str,
                Callable[[tuple[int, int]], int],
            ]
        ] = [
            ("vertical", lambda point: point[1]),
            ("horizontal", lambda point: point[0]),
            ("diagonal_down", lambda point: point[0] - point[1]),
            ("diagonal_up", lambda point: point[0] + point[1]),
        ]
        for kind, key_function in buckets:
            grouped: dict[int, list[tuple[int, int]]] = {}
            for point in points:
                grouped.setdefault(key_function(point), []).append(
                    point
                )
            for key, group in grouped.items():
                ordered = sorted(group)
                if len(ordered) < 3:
                    continue
                values = (
                    [column for _, column in ordered]
                    if kind == "horizontal"
                    else [row for row, _ in ordered]
                )
                if all(
                    second - first == 2
                    for first, second in zip(values, values[1:])
                ):
                    point_set = set(group)
                    signature = kind, key, tuple(sorted(point_set))
                    found[signature] = kind, key, point_set
    return list(found.values())


def extend_marker_to_periodic_boundary(
    grid: Grid,
) -> Grid | None:
    """Extend one marker toward a dotted orthogonal or diagonal line."""
    background = mode_color(grid)
    height, width = len(grid), len(grid[0])
    nonbackground = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != background
    }
    candidates = []
    for kind, key, boundary in periodic_line_candidates(grid):
        markers = sorted(nonbackground - boundary)
        if len(markers) != 1:
            continue
        row, column = markers[0]
        marker = grid[row][column]
        if kind == "vertical":
            delta_row, delta_column = (
                0,
                1 if column < key else -1,
            )
            on_line = lambda r, c: c == key
        elif kind == "horizontal":
            delta_row, delta_column = (
                1 if row < key else -1,
                0,
            )
            on_line = lambda r, c: r == key
        elif kind == "diagonal_down":
            if row - column < key:
                delta_row, delta_column = 1, -1
            else:
                delta_row, delta_column = -1, 1
            on_line = lambda r, c: r - c == key
        else:
            if row + column < key:
                delta_row, delta_column = 1, 1
            else:
                delta_row, delta_column = -1, -1
            on_line = lambda r, c: r + c == key
        result = [values[:] for values in grid]
        additions = 0
        cursor_row = row + delta_row
        cursor_column = column + delta_column
        valid = False
        while (
            0 <= cursor_row < height
            and 0 <= cursor_column < width
        ):
            if on_line(cursor_row, cursor_column):
                valid = True
                break
            if grid[cursor_row][cursor_column] != background:
                break
            result[cursor_row][cursor_column] = marker
            additions += 1
            cursor_row += delta_row
            cursor_column += delta_column
        if valid and additions:
            candidates.append(result)
    if not candidates or any(
        result != candidates[0] for result in candidates[1:]
    ):
        return None
    return candidates[0]


def contiguous_line_directions(
    group: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Return undirected unit directions that exactly span a component."""
    directions = ((1, 0), (0, 1), (1, 1), (1, -1))
    if len(group) == 1:
        return list(directions)
    points = set(group)
    found = []
    for delta_row, delta_column in directions:
        projections = sorted(
            row * delta_row + column * delta_column
            for row, column in points
        )
        orthogonal = {
            row * (-delta_column) + column * delta_row
            for row, column in points
        }
        if len(orthogonal) != 1:
            continue
        step = delta_row * delta_row + delta_column * delta_column
        if all(
            second - first == step
            for first, second in zip(projections, projections[1:])
        ):
            found.append((delta_row, delta_column))
    return found


def extend_component_to_perpendicular_line(
    grid: Grid,
) -> Grid | None:
    """Extend one straight component until it touches the other."""
    background = mode_color(grid)
    colors = sorted(
        {value for row in grid for value in row} - {background}
    )
    if len(colors) != 2:
        return None
    height, width = len(grid), len(grid[0])
    groups = [
        [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ]
        for color in colors
    ]
    candidates = []
    for mover_index, mover in enumerate(groups):
        anchor = set(groups[1 - mover_index])
        anchor_directions = contiguous_line_directions(list(anchor))
        if not anchor_directions:
            continue
        color = grid[mover[0][0]][mover[0][1]]
        for direction in contiguous_line_directions(mover):
            if not any(
                direction[0] * anchor_direction[0]
                + direction[1] * anchor_direction[1]
                == 0
                for anchor_direction in anchor_directions
            ):
                continue
            projections = [
                (
                    row * direction[0] + column * direction[1],
                    (row, column),
                )
                for row, column in mover
            ]
            endpoints = [min(projections)[1], max(projections)[1]]
            for endpoint, sign in zip(endpoints, (-1, 1)):
                delta_row = sign * direction[0]
                delta_column = sign * direction[1]
                cursor = (
                    endpoint[0] + delta_row,
                    endpoint[1] + delta_column,
                )
                path = []
                while (
                    0 <= cursor[0] < height
                    and 0 <= cursor[1] < width
                ):
                    if grid[cursor[0]][cursor[1]] != background:
                        break
                    path.append(cursor)
                    if any(
                        (
                            cursor[0] + neighbor_row,
                            cursor[1] + neighbor_column,
                        )
                        in anchor
                        for neighbor_row, neighbor_column in (
                            (-1, 0),
                            (1, 0),
                            (0, -1),
                            (0, 1),
                        )
                    ):
                        result = [values[:] for values in grid]
                        for row, column in path:
                            result[row][column] = color
                        candidates.append(result)
                        break
                    cursor = (
                        cursor[0] + delta_row,
                        cursor[1] + delta_column,
                    )
    unique = {
        tuple(tuple(row) for row in result): result
        for result in candidates
    }
    return next(iter(unique.values())) if len(unique) == 1 else None


def connect_markers_to_spanning_line(
    grid: Grid,
) -> Grid | None:
    """Connect sparse markers to a row-spanning or column-spanning line."""
    background = mode_color(grid)
    colors = sorted(
        {value for row in grid for value in row} - {background}
    )
    if len(colors) != 2:
        return None
    height, width = len(grid), len(grid[0])
    candidates = []
    for boundary_color in colors:
        points = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == boundary_color
        ]
        marker_color = next(
            color for color in colors if color != boundary_color
        )
        markers = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == marker_color
        ]
        by_row = {row: [] for row in range(height)}
        by_column = {column: [] for column in range(width)}
        for row, column in points:
            by_row[row].append(column)
            by_column[column].append(row)
        if all(len(columns) == 1 for columns in by_row.values()):
            result = [values[:] for values in grid]
            valid = True
            for row, column in markers:
                target = by_row[row][0]
                for fill_column in range(
                    min(column, target) + 1,
                    max(column, target),
                ):
                    if result[row][fill_column] != background:
                        valid = False
                        break
                    result[row][fill_column] = marker_color
            if valid and result != grid:
                candidates.append(result)
        if all(len(rows) == 1 for rows in by_column.values()):
            result = [values[:] for values in grid]
            valid = True
            for row, column in markers:
                target = by_column[column][0]
                for fill_row in range(
                    min(row, target) + 1,
                    max(row, target),
                ):
                    if result[fill_row][column] != background:
                        valid = False
                        break
                    result[fill_row][column] = marker_color
            if valid and result != grid:
                candidates.append(result)
    unique = {
        tuple(tuple(row) for row in result): result
        for result in candidates
    }
    return next(iter(unique.values())) if len(unique) == 1 else None


def extend_inner_rectangle_cardinal_to_frame(
    grid: Grid,
) -> Grid | None:
    """Extend a solid inner rectangle in four directions to its frame."""
    background = mode_color(grid)
    colors = sorted(
        {value for row in grid for value in row} - {background}
    )
    height, width = len(grid), len(grid[0])
    if len(colors) == 2:
        counts = Counter(
            value
            for row in grid
            for value in row
            if value != background
        )
        minimum = min(counts.values())
        rare = [
            color for color, count in counts.items()
            if count == minimum
        ]
        if len(rare) != 1:
            return None
        color = rare[0]
        frame_color = next(
            candidate for candidate in colors if candidate != color
        )
        points = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ]
        frame_points = {
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == frame_color
        }
    elif len(colors) == 1:
        groups = [
            group
            for _, group in colored_components(
                grid, background, 4
            )
        ]
        if len(groups) != 2 or len(groups[0]) == len(groups[1]):
            return None
        points = min(groups, key=len)
        frame_points = set(max(groups, key=len))
        color = colors[0]
    else:
        return None
    top, bottom, left, right = point_bbox(points)
    if len(points) != (bottom - top + 1) * (right - left + 1):
        return None
    result = [values[:] for values in grid]
    for start, delta in ((left, -1), (right, 1)):
        column = start + delta
        blocked = False
        while 0 <= column < width:
            band = {
                (row, column) for row in range(top, bottom + 1)
            }
            if band & frame_points:
                blocked = True
                break
            if any(
                grid[row][point_column] != background
                for row, point_column in band
            ):
                return None
            for row in range(top, bottom + 1):
                result[row][column] = color
            column += delta
        if not blocked:
            return None
    for start, delta in ((top, -1), (bottom, 1)):
        row = start + delta
        blocked = False
        while 0 <= row < height:
            band = {
                (row, column) for column in range(left, right + 1)
            }
            if band & frame_points:
                blocked = True
                break
            if any(
                grid[point_row][column] != background
                for point_row, column in band
            ):
                return None
            for column in range(left, right + 1):
                result[row][column] = color
            row += delta
        if not blocked:
            return None
    return result if result != grid else None


def extend_external_markers_through_frame(
    grid: Grid,
) -> Grid | None:
    """Send external markers through aligned openings to the opposite wall."""
    background = mode_color(grid)
    colors = sorted(
        {value for row in grid for value in row} - {background}
    )
    if len(colors) != 2:
        return None
    counts = Counter(
        value
        for row in grid
        for value in row
        if value != background
    )
    frame = max(colors, key=lambda color: counts[color])
    marker = min(colors, key=lambda color: counts[color])
    if counts[frame] == counts[marker]:
        return None
    frame_points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == frame
    ]
    top, bottom, left, right = point_bbox(frame_points)
    markers = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == marker
    ]
    height, width = len(grid), len(grid[0])
    result = [values[:] for values in grid]
    for row, column in markers:
        if column < left and top <= row <= bottom:
            delta_row, delta_column = 0, 1
        elif column > right and top <= row <= bottom:
            delta_row, delta_column = 0, -1
        elif row < top and left <= column <= right:
            delta_row, delta_column = 1, 0
        elif row > bottom and left <= column <= right:
            delta_row, delta_column = -1, 0
        else:
            return None
        cursor_row = row + delta_row
        cursor_column = column + delta_column
        crossed_bbox = False
        blocked = False
        while (
            0 <= cursor_row < height
            and 0 <= cursor_column < width
        ):
            if (
                top <= cursor_row <= bottom
                and left <= cursor_column <= right
            ):
                crossed_bbox = True
            value = grid[cursor_row][cursor_column]
            if value == frame:
                blocked = True
                break
            if value not in (background, marker):
                break
            result[cursor_row][cursor_column] = marker
            cursor_row += delta_row
            cursor_column += delta_column
        if not crossed_bbox or not blocked:
            return None
    return result if result != grid else None


def components_for_any_color(
    grid: Grid,
    color: int,
) -> list[list[tuple[int, int]]]:
    """Return four-connected components for any color, including zero."""
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == color
    }
    found = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        queue = [start]
        group = []
        cursor = 0
        while cursor < len(queue):
            row, column = queue[cursor]
            cursor += 1
            group.append((row, column))
            for delta_row, delta_column in (
                (-1, 0),
                (1, 0),
                (0, -1),
                (0, 1),
            ):
                point = row + delta_row, column + delta_column
                if point in remaining:
                    remaining.remove(point)
                    queue.append(point)
        found.append(group)
    return found


def crop_selected_points(
    grid: Grid,
    points: list[tuple[int, int]],
    color: int | None = None,
) -> Grid:
    top, bottom, left, right = point_bbox(points)
    result = [
        [0] * (right - left + 1)
        for _ in range(bottom - top + 1)
    ]
    for row, column in points:
        result[row - top][column - left] = (
            grid[row][column] if color is None else color
        )
    return result


def crop_unique_bounded_color_component(
    grid: Grid,
) -> Grid | None:
    """Crop the sole color whose entire pattern is edge-free."""
    height, width = len(grid), len(grid[0])
    candidates = []
    for color in sorted({value for row in grid for value in row}):
        group = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ]
        if any(
            row in (0, height - 1)
            or column in (0, width - 1)
            for row, column in group
        ):
            continue
        candidates.append((color, group))
    if len(candidates) != 1:
        return None
    color, group = candidates[0]
    return crop_selected_points(grid, group, color)


def crop_color_with_unique_component_count(
    grid: Grid,
) -> Grid | None:
    """Crop the nonzero color occurring as one component among repeats."""
    colors = sorted(
        {value for row in grid for value in row} - {0}
    )
    if len(colors) != 2:
        return None
    grouped = {
        color: components_for_any_color(grid, color)
        for color in colors
    }
    singles = [
        color for color, groups in grouped.items() if len(groups) == 1
    ]
    if len(singles) != 1:
        return None
    other = next(color for color in colors if color != singles[0])
    if len(grouped[other]) < 2:
        return None
    color = singles[0]
    return crop_selected_points(grid, grouped[color][0], color)


def crop_rarest_nonzero_color_bbox(grid: Grid) -> Grid | None:
    """Crop the uniquely rarest nonzero color and erase its container."""
    counts = Counter(
        value for row in grid for value in row if value != 0
    )
    if len(counts) < 2:
        return None
    minimum = min(counts.values())
    colors = [
        color for color, count in counts.items() if count == minimum
    ]
    if len(colors) != 1:
        return None
    color = colors[0]
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == color
    ]
    other_points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value not in (0, color)
    ]
    if not other_points:
        return None
    rare_box = point_bbox(points)
    other_box = point_bbox(other_points)
    if not (
        other_box[0] <= rare_box[0] <= rare_box[1] <= other_box[1]
        and other_box[2] <= rare_box[2] <= rare_box[3] <= other_box[3]
    ):
        return None
    return crop_selected_points(grid, points, color)


def crop_largest_solid_nonzero_rectangle(
    grid: Grid,
) -> Grid | None:
    """Extract the unique largest solid rectangle at least 2x2."""
    height, width = len(grid), len(grid[0])
    candidates = []
    for color in sorted(
        {value for row in grid for value in row} - {0}
    ):
        for top in range(height - 1):
            valid_columns = [True] * width
            for bottom in range(top, height):
                valid_columns = [
                    valid and grid[bottom][column] == color
                    for column, valid in enumerate(valid_columns)
                ]
                if bottom == top:
                    continue
                start = 0
                while start < width:
                    while start < width and not valid_columns[start]:
                        start += 1
                    end = start
                    while end < width and valid_columns[end]:
                        end += 1
                    if end - start >= 2:
                        candidates.append(
                            (
                                (bottom - top + 1) * (end - start),
                                top,
                                bottom,
                                start,
                                end - 1,
                                color,
                            )
                        )
                    start = max(end, start + 1)
    if not candidates:
        return None
    maximum = max(candidate[0] for candidate in candidates)
    best = {
        candidate[1:]
        for candidate in candidates
        if candidate[0] == maximum
    }
    if len(best) != 1:
        return None
    top, bottom, left, right, color = next(iter(best))
    return [
        [color] * (right - left + 1)
        for _ in range(bottom - top + 1)
    ]


def pack_large_components_horizontally(
    grid: Grid,
) -> Grid | None:
    """Crop substantial objects and pack them in left-to-right order."""
    selected = []
    colors = sorted(
        {value for row in grid for value in row} - {0}
    )
    groups = [
        group
        for color in colors
        for group in components_for_any_color(grid, color)
    ]
    for original in groups:
        group = original[:]
        while group:
            row_counts = Counter(row for row, _ in group)
            column_counts = Counter(column for _, column in group)
            top = min(row_counts)
            bottom = max(row_counts)
            left = min(column_counts)
            right = max(column_counts)
            removable = {
                point
                for point in group
                if (
                    point[0] in (top, bottom)
                    and row_counts[point[0]] <= 1
                )
                or (
                    point[1] in (left, right)
                    and column_counts[point[1]] <= 1
                )
            }
            if not removable:
                break
            group = [
                point for point in group if point not in removable
            ]
        if not group:
            continue
        top, bottom, left, right = point_bbox(group)
        if bottom - top + 1 < 3 or right - left + 1 < 3:
            continue
        selected.append((left, top, group))
    if not selected:
        return None
    size_counts = Counter(len(group) for _, _, group in selected)
    maximum_frequency = max(size_counts.values())
    sizes = [
        size
        for size, frequency in size_counts.items()
        if frequency == maximum_frequency
    ]
    if len(sizes) != 1 or maximum_frequency < 2:
        return None
    selected = [
        item for item in selected if len(item[2]) == sizes[0]
    ]
    selected.sort(key=lambda item: (item[0], item[1]))
    crops = []
    heights = set()
    for _, _, group in selected:
        crop = crop_selected_points(grid, group)
        crops.append(crop)
        heights.add(len(crop))
    if len(heights) != 1:
        return None
    result = []
    for row in range(len(crops[0])):
        result.append([
            value
            for crop in crops
            for value in crop[row]
        ])
    return result


def extract_panel_object(panel: Grid) -> Grid | None:
    counts = Counter(value for row in panel for value in row)
    background = (
        0
        if 0 in counts
        else min(counts, key=lambda color: (-counts[color], color))
    )
    points = [
        (row, column)
        for row, values in enumerate(panel)
        for column, value in enumerate(values)
        if value != background
    ]
    if not points:
        return None
    top, bottom, left, right = point_bbox(points)
    return [
        [
            0 if value == background else value
            for value in row[left : right + 1]
        ]
        for row in panel[top : bottom + 1]
    ]


def centered_pack(
    first: Grid,
    second: Grid,
    vertical: bool,
) -> Grid:
    if vertical:
        width = max(len(first[0]), len(second[0]))
        result = [
            [0] * width for _ in range(len(first) + len(second))
        ]
        first_left = (width - len(first[0])) // 2
        second_left = (width - len(second[0])) // 2
        for row, values in enumerate(first):
            result[row][first_left : first_left + len(values)] = values
        for offset, values in enumerate(second):
            row = len(first) + offset
            result[row][
                second_left : second_left + len(values)
            ] = values
        return result
    height = max(len(first), len(second))
    width = len(first[0]) + len(second[0])
    result = [[0] * width for _ in range(height)]
    first_top = (height - len(first)) // 2
    second_top = (height - len(second)) // 2
    for offset, values in enumerate(first):
        result[first_top + offset][: len(values)] = values
    for offset, values in enumerate(second):
        result[second_top + offset][len(first[0]) :] = values
    return result


def extract_objects_across_separator(grid: Grid) -> Grid | None:
    """Remove a dedicated separator band and pack the panel objects."""
    height, width = len(grid), len(grid[0])
    candidates = []
    for color in sorted(
        {value for row in grid for value in row} - {0}
    ):
        points = {
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        }
        rows = sorted({row for row, _ in points})
        columns = sorted({column for _, column in points})
        if (
            rows
            and rows == list(range(rows[0], rows[-1] + 1))
            and points
            == {
                (row, column)
                for row in rows
                for column in range(width)
            }
            and rows[0] > 0
            and rows[-1] + 1 < height
        ):
            first = extract_panel_object(grid[: rows[0]])
            second = extract_panel_object(grid[rows[-1] + 1 :])
            if first is not None and second is not None:
                candidates.append(centered_pack(first, second, True))
        if (
            columns
            and columns
            == list(range(columns[0], columns[-1] + 1))
            and points
            == {
                (row, column)
                for row in range(height)
                for column in columns
            }
            and columns[0] > 0
            and columns[-1] + 1 < width
        ):
            first = extract_panel_object([
                row[: columns[0]] for row in grid
            ])
            second = extract_panel_object([
                row[columns[-1] + 1 :] for row in grid
            ])
            if first is not None and second is not None:
                candidates.append(centered_pack(first, second, False))
    unique = {
        tuple(tuple(row) for row in result): result
        for result in candidates
    }
    return next(iter(unique.values())) if len(unique) == 1 else None


def extract_regions_enclosed_by_zero(grid: Grid) -> Grid | None:
    """Crop and pack nonzero regions enclosed by zero walls."""
    height, width = len(grid), len(grid[0])
    exterior = {
        (row, column)
        for row in range(height)
        for column in range(width)
        if (
            row in (0, height - 1)
            or column in (0, width - 1)
        )
        and grid[row][column] != 0
    }
    queue = list(sorted(exterior))
    cursor = 0
    while cursor < len(queue):
        row, column = queue[cursor]
        cursor += 1
        for delta_row, delta_column in (
            (-1, 0),
            (1, 0),
            (0, -1),
            (0, 1),
        ):
            point = row + delta_row, column + delta_column
            if (
                0 <= point[0] < height
                and 0 <= point[1] < width
                and point not in exterior
                and grid[point[0]][point[1]] != 0
            ):
                exterior.add(point)
                queue.append(point)
    remaining = {
        (row, column)
        for row in range(height)
        for column in range(width)
        if grid[row][column] != 0
        and (row, column) not in exterior
    }
    if not remaining:
        return None
    groups = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        queue = [start]
        group = []
        cursor = 0
        while cursor < len(queue):
            point = queue[cursor]
            cursor += 1
            group.append(point)
            for delta_row, delta_column in (
                (-1, 0),
                (1, 0),
                (0, -1),
                (0, 1),
            ):
                neighbor = (
                    point[0] + delta_row,
                    point[1] + delta_column,
                )
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    queue.append(neighbor)
        groups.append(group)
    groups.sort(key=lambda group: (
        min(column for _, column in group),
        min(row for row, _ in group),
    ))
    crops = [crop_selected_points(grid, group) for group in groups]
    result = crops[0]
    for crop in crops[1:]:
        result = centered_pack(result, crop, False)
    return result


def crop_topmost_color(grid: Grid) -> Grid | None:
    """Crop all cells of the uniquely topmost nonzero color."""
    colors = sorted(
        {value for row in grid for value in row} - {0}
    )
    if len(colors) < 2:
        return None
    ranges = {}
    for color in colors:
        points = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ]
        ranges[color] = (
            min(row for row, _ in points),
            max(row for row, _ in points),
        )
    if any(
        not (
            ranges[first][1] < ranges[second][0]
            or ranges[second][1] < ranges[first][0]
        )
        for index, first in enumerate(colors)
        for second in colors[index + 1 :]
    ):
        return None
    minimum = min(top for top, _ in ranges.values())
    selected = [
        color for color, (top, _) in ranges.items() if top == minimum
    ]
    if len(selected) != 1:
        return None
    color = selected[0]
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == color
    ]
    return crop_selected_points(grid, points, color)


def recolor_top_occupied_row_two(grid: Grid) -> Grid | None:
    """Recolor the globally top occupied row to ARC red."""
    rows = [
        row
        for row, values in enumerate(grid)
        if any(value != 0 for value in values)
    ]
    if not rows:
        return None
    top = min(rows)
    result = [values[:] for values in grid]
    changed = False
    for column, value in enumerate(result[top]):
        if value != 0:
            changed |= value != 2
            result[top][column] = 2
    return result if changed else None


def remove_top_and_bottom_colors(grid: Grid) -> Grid | None:
    """Remove the colors defining the topmost and bottommost objects."""
    colors = sorted(
        {value for row in grid for value in row} - {0}
    )
    if len(colors) < 2:
        return None
    tops = {}
    bottoms = {}
    for color in colors:
        rows = [
            row
            for row, values in enumerate(grid)
            if color in values
        ]
        tops[color] = min(rows)
        bottoms[color] = max(rows)
    top_colors = [
        color for color, row in tops.items() if row == min(tops.values())
    ]
    bottom_colors = [
        color
        for color, row in bottoms.items()
        if row == max(bottoms.values())
    ]
    if len(top_colors) != 1 or len(bottom_colors) != 1:
        return None
    remove = {top_colors[0], bottom_colors[0]}
    return [
        [0 if value in remove else value for value in row]
        for row in grid
    ]


def keep_bottommost_component_bbox(grid: Grid) -> Grid | None:
    """Keep the bbox content of the same-color object ending lowest."""
    groups = [
        group for _, group in colored_components(grid, 0, 8)
    ]
    if len(groups) < 2:
        return None
    bottoms = [max(row for row, _ in group) for group in groups]
    maximum = max(bottoms)
    selected = [
        group
        for group, bottom in zip(groups, bottoms)
        if bottom == maximum
    ]
    if len(selected) != 1:
        return None
    top, bottom, left, right = point_bbox(selected[0])
    result = [[0 for _ in row] for row in grid]
    for row in range(top, bottom + 1):
        result[row][left : right + 1] = grid[row][left : right + 1]
    return result


def lowest_top_color(grid: Grid) -> int | None:
    colors = sorted(
        {value for row in grid for value in row} - {0}
    )
    if len(colors) < 2:
        return None
    tops = {
        color: min(
            row
            for row, values in enumerate(grid)
            if color in values
        )
        for color in colors
    }
    maximum = max(tops.values())
    selected = [
        color for color, top in tops.items() if top == maximum
    ]
    return selected[0] if len(selected) == 1 else None


def recolor_all_to_color_with_lowest_top(
    grid: Grid,
) -> Grid | None:
    """Recolor every object using the lowest-starting object's color."""
    color = lowest_top_color(grid)
    if color is None:
        return None
    return [
        [0 if value == 0 else color for value in row]
        for row in grid
    ]


def nonzero_components_eight(
    grid: Grid,
) -> list[list[tuple[int, int]]]:
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    }
    found = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        queue = [start]
        group = []
        cursor = 0
        while cursor < len(queue):
            point = queue[cursor]
            cursor += 1
            group.append(point)
            for delta_row in (-1, 0, 1):
                for delta_column in (-1, 0, 1):
                    if delta_row == delta_column == 0:
                        continue
                    neighbor = (
                        point[0] + delta_row,
                        point[1] + delta_column,
                    )
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        queue.append(neighbor)
        found.append(group)
    return found


def recolor_highest_ending_component_five(
    grid: Grid,
) -> Grid | None:
    """Recolor the 8-connected object ending highest to ARC grey."""
    groups = nonzero_components_eight(grid)
    if len(groups) < 2:
        return None
    bottoms = [max(row for row, _ in group) for group in groups]
    minimum = min(bottoms)
    selected = [
        group
        for group, bottom in zip(groups, bottoms)
        if bottom == minimum
    ]
    if len(selected) != 1:
        return None
    result = [values[:] for values in grid]
    for row, column in selected[0]:
        result[row][column] = 5
    return result


def swap_top_bottom_color_bands(grid: Grid) -> Grid | None:
    """Swap the top and bottom color bands while retaining middle bands."""
    colors = sorted(
        {value for row in grid for value in row} - {0}
    )
    if len(colors) < 2:
        return None
    groups = []
    occupied_rows: set[int] = set()
    for color in colors:
        points = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ]
        rows = sorted({row for row, _ in points})
        if rows != list(range(rows[0], rows[-1] + 1)):
            return None
        if occupied_rows & set(rows):
            return None
        occupied_rows.update(rows)
        groups.append((rows[0], rows[-1], color, points))
    groups.sort()
    top = groups[0][0]
    bottom = groups[-1][1]
    if sorted(occupied_rows) != list(range(top, bottom + 1)):
        return None
    order = [groups[-1], *groups[1:-1], groups[0]]
    result = [
        [0 if value != 0 else value for value in row]
        for row in grid
    ]
    cursor = top
    for source_top, source_bottom, color, points in order:
        for row, column in points:
            result[cursor + row - source_top][column] = color
        cursor += source_bottom - source_top + 1
    return result


def tb3_nonzero_components(grid: Grid) -> list[set[tuple[int, int]]]:
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    }
    found = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        queue = deque([start])
        group = {start}
        while queue:
            row, column = queue.popleft()
            for delta_row, delta_column in (
                (-1, 0),
                (1, 0),
                (0, -1),
                (0, 1),
            ):
                neighbor = row + delta_row, column + delta_column
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    group.add(neighbor)
                    queue.append(neighbor)
        found.append(group)
    return found


def tb3_layer_components(
    grid: Grid,
) -> list[set[tuple[int, int]]]:
    groups = tb3_nonzero_components(grid)
    color_sets = [
        {grid[row][column] for row, column in group}
        for group in groups
    ]
    colors = {value for row in grid for value in row} - {0}
    if (
        len(colors) == 2
        and sum(len(values) == 2 for values in color_sets) == 1
        and any(len(values) == 1 for values in color_sets)
    ):
        return [set().union(*groups)]
    return groups


def tb3_mask_candidates(
    points: set[tuple[int, int]],
    include_border: bool = False,
) -> list[set[tuple[int, int]]]:
    top, bottom, left, right = point_bbox(list(points))
    found = {frozenset(points)}
    found.add(
        frozenset(
            (row, column)
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
        )
    )
    if include_border and bottom > top and right > left:
        found.add(
            frozenset(
                (row, column)
                for row in range(top, bottom + 1)
                for column in range(left, right + 1)
                if row in (top, bottom) or column in (left, right)
            )
        )
    if bottom - top == right - left:
        downward = {
            (top + offset, left + offset)
            for offset in range(bottom - top + 1)
        }
        upward = {
            (top + offset, right - offset)
            for offset in range(bottom - top + 1)
        }
        if points <= downward:
            found.add(frozenset(downward))
        if points <= upward:
            found.add(frozenset(upward))
    for row in range(top, bottom + 1):
        columns = {
            column for point_row, column in points if point_row == row
        }
        if columns:
            found.add(
                frozenset(
                    (target_row, column)
                    for target_row in range(top, bottom + 1)
                    for column in columns
                )
            )
    for column in range(left, right + 1):
        rows = {
            row for row, point_column in points
            if point_column == column
        }
        if rows:
            found.add(
                frozenset(
                    (row, target_column)
                    for row in rows
                    for target_column in range(left, right + 1)
                )
            )
    return [set(mask) for mask in found]


def tb3_infer_component_layers(
    grid: Grid,
    component: set[tuple[int, int]],
    include_border: bool = False,
) -> tuple[
    int,
    set[tuple[int, int]],
    int,
    set[tuple[int, int]],
] | None:
    colors = sorted(
        {grid[row][column] for row, column in component}
    )
    if len(colors) != 2:
        return None
    visible = {
        color: {
            point
            for point in component
            if grid[point[0]][point[1]] == color
        }
        for color in colors
    }
    options = []
    for first_mask in tb3_mask_candidates(
        visible[colors[0]], include_border
    ):
        for second_mask in tb3_mask_candidates(
            visible[colors[1]], include_border
        ):
            masks = {
                colors[0]: first_mask,
                colors[1]: second_mask,
            }
            if first_mask | second_mask != component:
                continue
            intersection = first_mask & second_mask
            if not intersection:
                continue
            shown = {
                grid[row][column] for row, column in intersection
            }
            if len(shown) != 1:
                continue
            top = next(iter(shown))
            bottom = colors[0] if top == colors[1] else colors[1]
            added = sum(
                len(masks[color] - visible[color]) for color in colors
            )
            options.append(
                (
                    added,
                    -len(intersection),
                    top,
                    masks[top],
                    bottom,
                    masks[bottom],
                )
            )
    if not options:
        return None
    options.sort(key=lambda item: item[:2])
    best = options[0]
    if any(
        option[:2] == best[:2] and option[2:] != best[2:]
        for option in options[1:]
    ):
        return None
    return best[2], best[3], best[4], best[5]


def swap_occlusion_order(grid: Grid) -> Grid | None:
    """Reverse which of two simple objects is visible at every overlap."""
    result = [row[:] for row in grid]
    changed = False
    for component in tb3_layer_components(grid):
        inferred = tb3_infer_component_layers(grid, component)
        if inferred is None:
            return None
        _, top_mask, bottom, bottom_mask = inferred
        for row, column in top_mask & bottom_mask:
            if result[row][column] != bottom:
                result[row][column] = bottom
                changed = True
    return result if changed else None


def remove_top_layer_reveal_bottom(grid: Grid) -> Grid | None:
    """Remove the visible top object and reveal the complete bottom object."""
    result = [row[:] for row in grid]
    for component in tb3_layer_components(grid):
        inferred = tb3_infer_component_layers(grid, component)
        if inferred is None:
            return None
        _, _, bottom, bottom_mask = inferred
        for row, column in component:
            result[row][column] = 0
        for row, column in bottom_mask:
            result[row][column] = bottom
    return result


def shift_top_layer_left(grid: Grid) -> Grid | None:
    """Move the visible top object left one cell, revealing the bottom."""
    result = [row[:] for row in grid]
    for component in tb3_layer_components(grid):
        inferred = tb3_infer_component_layers(
            grid, component, include_border=True
        )
        if inferred is None:
            return None
        top, top_mask, bottom, bottom_mask = inferred
        shifted = {(row, column - 1) for row, column in top_mask}
        if any(column < 0 for _, column in shifted):
            return None
        for row, column in component:
            result[row][column] = 0
        for row, column in bottom_mask:
            result[row][column] = bottom
        for row, column in shifted:
            result[row][column] = top
    return result


def tb3_orientation_score(grid: Grid, color: int) -> int:
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == color
    ]
    row_counts = Counter(row for row, _ in points)
    column_counts = Counter(column for _, column in points)
    return max(row_counts.values()) - max(column_counts.values())


def tb3_horizontal_vertical_colors(
    grid: Grid,
) -> tuple[int, int] | None:
    colors = sorted({value for row in grid for value in row} - {0})
    if len(colors) != 2:
        return None
    scores = {
        color: tb3_orientation_score(grid, color) for color in colors
    }
    horizontal = max(colors, key=lambda color: scores[color])
    vertical = min(colors, key=lambda color: scores[color])
    if scores[horizontal] <= scores[vertical]:
        return None
    return horizontal, vertical


def remove_hidden_vertical_strands(grid: Grid) -> Grid | None:
    """Delete vertical strands hidden wherever they cross horizontal bars."""
    selected = tb3_horizontal_vertical_colors(grid)
    if selected is None:
        return None
    horizontal, vertical = selected
    horizontal_rows = {
        row
        for row, values in enumerate(grid)
        if horizontal in values
    }
    vertical_columns = sorted(
        {
            column
            for values in grid
            for column, value in enumerate(values)
            if value == vertical
        }
    )
    groups: list[list[int]] = []
    for column in vertical_columns:
        if groups and column == groups[-1][-1] + 1:
            groups[-1].append(column)
        else:
            groups.append([column])
    result = [row[:] for row in grid]
    removed = False
    kept = False
    for group in groups:
        visible = any(
            grid[row][column] == vertical
            for row in horizontal_rows
            for column in group
        )
        if visible:
            kept = True
            continue
        for row in range(len(grid)):
            for column in group:
                if result[row][column] == vertical:
                    result[row][column] = 0
        removed = True
    return result if removed and (kept or len(groups) == 1) else None


def propagate_vertical_pattern_over_horizontal_bands(
    grid: Grid,
) -> Grid | None:
    """Make a repeated vertical pattern topmost at every horizontal band."""
    selected = tb3_horizontal_vertical_colors(grid)
    if selected is None:
        return None
    horizontal, vertical = selected
    horizontal_rows = {
        row
        for row, values in enumerate(grid)
        if horizontal in values
    }
    if len(horizontal_rows) < 2:
        return None
    pattern_columns = {
        column
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == vertical and row not in horizontal_rows
    }
    if not pattern_columns:
        return None
    result = [row[:] for row in grid]
    changed = False
    for row in horizontal_rows:
        for column in pattern_columns:
            if grid[row][column] == horizontal:
                result[row][column] = vertical
                changed = True
    return result if changed else None


def swap_vertical_line_crossings(grid: Grid) -> Grid | None:
    """Reverse each crossing of one vertical backbone and other lines."""
    colors = sorted({value for row in grid for value in row} - {0})
    if len(colors) < 2:
        return None
    choices = []
    for color in colors:
        points = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ]
        counts = Counter(column for _, column in points)
        column, count = counts.most_common(1)[0]
        rows = {row for row, point_column in points if point_column == column}
        span = max(rows) - min(rows) + 1
        choices.append((span, count / span, count, color, column))
    choices.sort(reverse=True)
    span, _, count, backbone, column = choices[0]
    if span < max(3, len(grid) - 2) or count < 2:
        return None
    result = [row[:] for row in grid]
    changed = False
    crossings = 0
    for color in colors:
        if color == backbone:
            continue
        for row, values in enumerate(grid):
            columns = [
                point_column
                for point_column, value in enumerate(values)
                if value == color
            ]
            horizontal_crossing = (
                len(columns) >= 2
                and min(columns) <= column <= max(columns)
            )
            visible_crossing = grid[row][column] == color
            if not (horizontal_crossing or visible_crossing):
                continue
            if visible_crossing:
                result[row][column] = backbone
            elif grid[row][column] == backbone:
                result[row][column] = color
            else:
                continue
            changed = True
            crossings += 1
    return result if changed and crossings else None


def crop_most_occluded_filled_bbox(grid: Grid) -> Grid | None:
    """Reconstruct and crop the most-covered solid rectangle."""
    colors = sorted({value for row in grid for value in row} - {0})
    options = []
    for color in colors:
        points = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ]
        top, bottom, left, right = point_bbox(points)
        values = [
            grid[row][column]
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
        ]
        if 0 in values:
            continue
        missing = sum(value != color for value in values)
        if missing:
            options.append(
                (
                    missing,
                    len(values),
                    color,
                    top,
                    bottom,
                    left,
                    right,
                )
            )
    if not options:
        return None
    options.sort(reverse=True)
    if len(options) > 1 and options[0][:2] == options[1][:2]:
        return None
    _, _, color, top, bottom, left, right = options[0]
    return [
        [color] * (right - left + 1)
        for _ in range(bottom - top + 1)
    ]


def tb3_is_complete_straight_line(
    points: set[tuple[int, int]],
) -> bool:
    if len(points) < 2:
        return False
    top, bottom, left, right = point_bbox(list(points))
    candidates = []
    if top == bottom:
        candidates.append(
            {(top, column) for column in range(left, right + 1)}
        )
    if left == right:
        candidates.append(
            {(row, left) for row in range(top, bottom + 1)}
        )
    if bottom - top == right - left:
        candidates.extend(
            [
                {
                    (top + offset, left + offset)
                    for offset in range(bottom - top + 1)
                },
                {
                    (top + offset, right - offset)
                    for offset in range(bottom - top + 1)
                },
            ]
        )
    return any(points == candidate for candidate in candidates)


def crop_topmost_bbox_graph_object(grid: Grid) -> Grid | None:
    """Crop the complete object at the top of an occlusion graph."""
    colors = sorted({value for row in grid for value in row} - {0})
    if len(colors) < 2:
        return None
    points = {
        color: {
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        }
        for color in colors
    }
    graph = {}
    for color in colors:
        if tb3_is_complete_straight_line(points[color]):
            graph[color] = set()
            continue
        top, bottom, left, right = point_bbox(list(points[color]))
        graph[color] = (
            {
                grid[row][column]
                for row in range(top, bottom + 1)
                for column in range(left, right + 1)
            }
            - {0, color}
        )
    sinks = [color for color in colors if not graph[color]]
    incoming = {
        color: sum(color in targets for targets in graph.values())
        for color in colors
    }
    if not sinks:
        return None
    maximum = max(incoming[color] for color in sinks)
    selected = [
        color for color in sinks if incoming[color] == maximum
    ]
    if len(selected) != 1 or maximum == 0:
        return None
    color = selected[0]
    top, bottom, left, right = point_bbox(list(points[color]))
    result = [
        [0] * (right - left + 1)
        for _ in range(bottom - top + 1)
    ]
    for row, column in points[color]:
        result[row - top][column - left] = color
    return result


def recolor_union_to_smallest_bbox_color(
    grid: Grid,
) -> Grid | None:
    """Recolor an overlapping pair using the smaller object's color."""
    colors = sorted({value for row in grid for value in row} - {0})
    if len(colors) != 2:
        return None
    areas = {}
    for color in colors:
        points = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ]
        top, bottom, left, right = point_bbox(points)
        areas[color] = (bottom - top + 1) * (right - left + 1)
    minimum = min(areas.values())
    selected = [
        color for color, area in areas.items() if area == minimum
    ]
    if len(selected) != 1:
        return None
    return [
        [0 if value == 0 else selected[0] for value in row]
        for row in grid
    ]


def tb3_longest_run(values: list[int], color: int) -> int:
    maximum = 0
    current = 0
    for value in values:
        if value == color:
            current += 1
            maximum = max(maximum, current)
        else:
            current = 0
    return maximum


def restore_occluded_grid_layer(grid: Grid) -> Grid | None:
    """Restore a large striped/grid layer through a smaller foreground."""
    colors = sorted({value for row in grid for value in row} - {0})
    if len(colors) < 2:
        return None
    bounds = {}
    for color in colors:
        points = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ]
        top, bottom, left, right = point_bbox(points)
        bounds[color] = (
            top,
            bottom,
            left,
            right,
            (bottom - top + 1) * (right - left + 1),
        )
    maximum = max(item[4] for item in bounds.values())
    selected = [
        color for color, item in bounds.items() if item[4] == maximum
    ]
    if len(selected) != 1:
        return None
    color = selected[0]
    top, bottom, left, right, _ = bounds[color]
    horizontal_rows = {
        row
        for row in range(top, bottom + 1)
        if tb3_longest_run(grid[row][left : right + 1], color) >= 3
    }
    if len(horizontal_rows) < 2:
        return None
    if len(horizontal_rows) >= 3:
        ordered = sorted(horizontal_rows)
        period = 0
        for first, second in zip(ordered, ordered[1:]):
            period = gcd(period, second - first)
        if period > 1:
            horizontal_rows.update(
                range(ordered[0], ordered[-1] + 1, period)
            )
    vertical_columns = {
        column
        for column in range(left, right + 1)
        if sum(
            grid[row][column] == color
            for row in range(top, bottom + 1)
            if row not in horizontal_rows
        )
        >= 2
    }
    if not vertical_columns:
        return None
    result = [row[:] for row in grid]
    changed = False
    for row in range(top, bottom + 1):
        columns = (
            range(left, right + 1)
            if row in horizontal_rows
            else vertical_columns
        )
        for column in columns:
            if result[row][column] != color:
                result[row][column] = color
                changed = True
    return result if changed else None


def keep_colors_with_multiple_components(grid: Grid) -> Grid:
    """Keep colors represented by at least two four-connected objects."""
    background = mode_color(grid)
    components = colored_components(grid, background, 4)
    counts = Counter(color for color, _ in components)
    repeated = {color for color, count in counts.items() if count >= 2}
    return [
        [
            value
            if value == background or value in repeated
            else background
            for value in row
        ]
        for row in grid
    ]


def line_orientation(
    points: list[tuple[int, int]],
) -> str | None:
    if len(points) < 2:
        return None
    rows = {row for row, _ in points}
    columns = {column for _, column in points}
    if len(rows) == 1:
        return "horizontal"
    if len(columns) == 1:
        return "vertical"
    if len({row - column for row, column in points}) == 1:
        return "diagonal_down"
    if len({row + column for row, column in points}) == 1:
        return "diagonal_up"
    return None


def keep_repeated_line_orientations(grid: Grid) -> Grid | None:
    """Keep straight-line objects whose orientation occurs at least twice."""
    background = mode_color(grid)
    components = [
        group for _, group in colored_components(grid, background, 8)
    ]
    orientations = [line_orientation(group) for group in components]
    if any(orientation is None for orientation in orientations):
        return None
    counts = Counter(orientations)
    repeated = {
        orientation for orientation, count in counts.items() if count >= 2
    }
    result = [row[:] for row in grid]
    for group, orientation in zip(components, orientations):
        if orientation not in repeated:
            for row, column in group:
                result[row][column] = background
    return result


def bounded_regions_not_color(
    grid: Grid, frame_color: int
) -> list[list[tuple[int, int]]]:
    """Return four-connected complement regions enclosed by a color."""
    height, width = len(grid), len(grid[0])
    seen: set[tuple[int, int]] = set()
    bounded: list[list[tuple[int, int]]] = []
    for start_row in range(height):
        for start_column in range(width):
            start = start_row, start_column
            if start in seen or grid[start_row][start_column] == frame_color:
                continue
            queue = [start]
            seen.add(start)
            group: list[tuple[int, int]] = []
            touches_boundary = False
            cursor = 0
            while cursor < len(queue):
                row, column = queue[cursor]
                cursor += 1
                group.append((row, column))
                touches_boundary = (
                    touches_boundary
                    or row in (0, height - 1)
                    or column in (0, width - 1)
                )
                for delta_row, delta_column in (
                    (-1, 0),
                    (1, 0),
                    (0, -1),
                    (0, 1),
                ):
                    neighbor = row + delta_row, column + delta_column
                    nr, nc = neighbor
                    if (
                        0 <= nr < height
                        and 0 <= nc < width
                        and neighbor not in seen
                        and grid[nr][nc] != frame_color
                    ):
                        seen.add(neighbor)
                        queue.append(neighbor)
            if not touches_boundary:
                bounded.append(group)
    return bounded


def repeated_component_interior_color(grid: Grid) -> Grid | None:
    """Return the one color enclosed by at least two distinct frames."""
    background = mode_color(grid)
    colors = sorted(
        {value for row in grid for value in row} - {background}
    )
    appearances: Counter[int] = Counter()
    for frame_color in colors:
        for region in bounded_regions_not_color(grid, frame_color):
            interior = {
                grid[row][column] for row, column in region
            } - {background, frame_color}
            if len(interior) == 1:
                appearances[next(iter(interior))] += 1
    repeated = [
        color for color, count in appearances.items() if count >= 2
    ]
    return [[repeated[0]]] if len(repeated) == 1 else None


def extract_repeated_inner_shapes(grid: Grid) -> Grid | None:
    """Keep exact monochrome shapes that occur at least twice."""
    background = mode_color(grid)
    components = [
        group
        for _, group in colored_components(grid, background, 4)
        if len(group) >= 2
    ]
    signatures = [
        normalized_component_mask(group) for group in components
    ]
    counts = Counter(signatures)
    if not any(count >= 2 for count in counts.values()):
        return None
    result = [
        [background for _ in range(len(grid[0]))]
        for _ in range(len(grid))
    ]
    for group, signature in zip(components, signatures):
        if counts[signature] >= 2:
            for row, column in group:
                result[row][column] = grid[row][column]
            top, bottom, left, right = point_bbox(group)
            wall = set(group)
            seen: set[tuple[int, int]] = set()
            for start_row in range(top, bottom + 1):
                for start_column in range(left, right + 1):
                    start = start_row, start_column
                    if start in wall or start in seen:
                        continue
                    queue = [start]
                    seen.add(start)
                    region: list[tuple[int, int]] = []
                    touches_bbox = False
                    cursor = 0
                    while cursor < len(queue):
                        row, column = queue[cursor]
                        cursor += 1
                        region.append((row, column))
                        touches_bbox = (
                            touches_bbox
                            or row in (top, bottom)
                            or column in (left, right)
                        )
                        for delta_row, delta_column in (
                            (-1, 0),
                            (1, 0),
                            (0, -1),
                            (0, 1),
                        ):
                            neighbor = (
                                row + delta_row,
                                column + delta_column,
                            )
                            if (
                                top <= neighbor[0] <= bottom
                                and left <= neighbor[1] <= right
                                and neighbor not in wall
                                and neighbor not in seen
                            ):
                                seen.add(neighbor)
                                queue.append(neighbor)
                    if not touches_bbox:
                        for row, column in region:
                            if grid[row][column] != background:
                                result[row][column] = grid[row][column]
    return result


def remove_repeated_frame_color(grid: Grid) -> Grid | None:
    """Remove the unique color that encloses two or more regions."""
    background = mode_color(grid)
    colors = sorted(
        {value for row in grid for value in row} - {background}
    )
    candidates = [
        (color, bounded_regions_not_color(grid, color))
        for color in colors
    ]
    candidates = [
        (color, regions)
        for color, regions in candidates
        if len(regions) >= 2
    ]
    if len(candidates) != 1:
        return None
    frame_color, regions = candidates[0]
    result = [
        [
            background if value == frame_color else value
            for value in row
        ]
        for row in grid
    ]
    for region in regions:
        for row, column in region:
            result[row][column] = background
    return result


def recolor_two_shapes_by_equality(grid: Grid) -> Grid | None:
    """Recolor two shapes by exact translation-normalized equality."""
    background = mode_color(grid)
    colors = sorted(
        {value for row in grid for value in row} - {background}
    )
    if len(colors) != 2:
        return None
    same = (
        normalized_color_mask(grid, colors[0])
        == normalized_color_mask(grid, colors[1])
    )
    replacement = 8 if same else 5
    return [
        [
            background if value == background else replacement
            for value in row
        ]
        for row in grid
    ]


def compare_equal_panels_keep_or_erase_second(
    grid: Grid,
) -> Grid | None:
    """Erase the second half when two centered comparison panels differ."""
    background = mode_color(grid)
    height, width = len(grid), len(grid[0])
    dividers: list[tuple[str, int]] = []
    for column in range(width):
        values = {grid[row][column] for row in range(height)}
        if (
            len(values) == 1
            and next(iter(values)) != background
            and column == width - 1 - column
        ):
            dividers.append(("column", column))
    for row in range(height):
        values = set(grid[row])
        if (
            len(values) == 1
            and next(iter(values)) != background
            and row == height - 1 - row
        ):
            dividers.append(("row", row))
    if len(dividers) != 1:
        return None
    axis, index = dividers[0]
    result = [row[:] for row in grid]
    if axis == "column":
        first = [row[:index] for row in grid]
        second = [row[index + 1 :] for row in grid]
        if first != second:
            for row in range(height):
                for column in range(index + 1, width):
                    result[row][column] = background
    else:
        first = grid[:index]
        second = grid[index + 1 :]
        if first != second:
            for row in range(index + 1, height):
                result[row] = [background] * width
    return result


def panel_pattern(
    panel: Grid,
) -> tuple[tuple[tuple[int, ...], ...], Grid] | None:
    background = mode_color(panel)
    points = [
        (row, column)
        for row, values in enumerate(panel)
        for column, value in enumerate(values)
        if value != background
    ]
    if not points:
        return None
    top, bottom, left, right = point_bbox(points)
    crop = [
        values[left : right + 1]
        for values in panel[top : bottom + 1]
    ]
    signature = tuple(
        tuple(int(value != background) for value in row)
        for row in crop
    )
    normalized = [
        [
            value if value != background else 0
            for value in row
        ]
        for row in crop
    ]
    return signature, normalized


def compare_two_panels_extract_same_pattern(
    grid: Grid,
) -> Grid | None:
    """Extract equal binary patterns from two zero-separated panels."""
    height, width = len(grid), len(grid[0])
    candidates: list[tuple[Grid, Grid]] = []
    for column in range(1, width - 1):
        if {grid[row][column] for row in range(height)} == {0}:
            first = [row[:column] for row in grid]
            second = [row[column + 1 :] for row in grid]
            if 0 not in (mode_color(first), mode_color(second)):
                candidates.append((first, second))
    for row in range(1, height - 1):
        if set(grid[row]) == {0}:
            first = [values[:] for values in grid[:row]]
            second = [values[:] for values in grid[row + 1 :]]
            if 0 not in (mode_color(first), mode_color(second)):
                candidates.append((first, second))
    if len(candidates) != 1:
        return None
    first_pattern = panel_pattern(candidates[0][0])
    second_pattern = panel_pattern(candidates[0][1])
    if first_pattern is None or second_pattern is None:
        return None
    if first_pattern[0] != second_pattern[0]:
        return [[0]]
    return first_pattern[1]


def blank_bbox_of_unique_filled_rectangle(
    grid: Grid,
) -> Grid | None:
    """Return a zero grid matching the unique solid rectangle's dimensions."""
    candidates = []
    for _, group in colored_components(grid, 0, 4):
        top, bottom, left, right = point_bbox(group)
        height, width = bottom - top + 1, right - left + 1
        if height >= 2 and width >= 2 and len(group) == height * width:
            candidates.append((height, width))
    if len(candidates) != 1:
        return None
    return [[0] * candidates[0][1] for _ in range(candidates[0][0])]


def extract_unique_enclosed_region(grid: Grid) -> Grid | None:
    """Crop the unique region enclosed by a nonzero frame color."""
    regions = []
    colors = sorted({value for row in grid for value in row} - {0})
    for color in colors:
        regions.extend(bounded_regions_not_color(grid, color))
    if len(regions) != 1:
        return None
    top, bottom, left, right = point_bbox(regions[0])
    return [row[left : right + 1] for row in grid[top : bottom + 1]]


def toggle_scanline_fill_each_shape(grid: Grid) -> Grid | None:
    """Toggle row-convex shapes between filled and four-neighbor outlines."""
    groups = [
        group for _, group in colored_components(grid, 0, 8)
    ]
    if not groups:
        return None
    result = [row[:] for row in grid]
    for group in groups:
        color = grid[group[0][0]][group[0][1]]
        point_set = set(group)
        rows: dict[int, list[int]] = {}
        for row, column in group:
            rows.setdefault(row, []).append(column)
        has_gap = any(
            any(
                (row, column) not in point_set
                for column in range(min(columns), max(columns) + 1)
            )
            for row, columns in rows.items()
        )
        if has_gap:
            for row, columns in rows.items():
                for column in range(min(columns), max(columns) + 1):
                    result[row][column] = color
        else:
            for row, column in group:
                if all(
                    (row + delta_row, column + delta_column) in point_set
                    for delta_row, delta_column in (
                        (-1, 0),
                        (1, 0),
                        (0, -1),
                        (0, 1),
                    )
                ):
                    result[row][column] = 0
    return result


def lattice_cross(
    origin: tuple[int, int],
    first: tuple[int, int],
    second: tuple[int, int],
) -> int:
    return (
        (first[0] - origin[0]) * (second[1] - origin[1])
        - (first[1] - origin[1]) * (second[0] - origin[0])
    )


def lattice_convex_hull(
    points: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    ordered = sorted(points)
    if len(ordered) <= 1:
        return ordered
    lower: list[tuple[int, int]] = []
    for point in ordered:
        while (
            len(lower) >= 2
            and lattice_cross(lower[-2], lower[-1], point) <= 0
        ):
            lower.pop()
        lower.append(point)
    upper: list[tuple[int, int]] = []
    for point in reversed(ordered):
        while (
            len(upper) >= 2
            and lattice_cross(upper[-2], upper[-1], point) <= 0
        ):
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def lattice_convex_fill(
    hull: list[tuple[int, int]],
) -> set[tuple[int, int]]:
    if len(hull) < 3:
        return set(hull)
    top, bottom, left, right = point_bbox(hull)
    result = set()
    for point in (
        (row, column)
        for row in range(top, bottom + 1)
        for column in range(left, right + 1)
    ):
        values = [
            lattice_cross(
                hull[index],
                hull[(index + 1) % len(hull)],
                point,
            )
            for index in range(len(hull))
        ]
        if all(value >= 0 for value in values) or all(
            value <= 0 for value in values
        ):
            result.add(point)
    return result


def rasterized_edge(
    first: tuple[int, int], second: tuple[int, int]
) -> set[tuple[int, int]]:
    delta_row = second[0] - first[0]
    delta_column = second[1] - first[1]
    steps = gcd(abs(delta_row), abs(delta_column))
    if steps == 0:
        return {first}
    return {
        (
            first[0] + offset * delta_row // steps,
            first[1] + offset * delta_column // steps,
        )
        for offset in range(steps + 1)
    }


def toggle_convex_fill_long_edges(grid: Grid) -> Grid | None:
    """Toggle slanted parallelograms between fill and longest parallel edges."""
    colors = sorted({value for row in grid for value in row} - {0})
    if len(colors) != 1:
        return None
    color = colors[0]
    points = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == color
    }
    top, bottom, left, right = point_bbox(list(points))
    horizontal_pair = {
        (row, column)
        for row in (top, bottom)
        for column in range(left, right + 1)
    }
    if bottom > top and points == horizontal_pair:
        result = [[0 for _ in values] for values in grid]
        for row in range(top, bottom + 1):
            for column in range(left, right + 1):
                result[row][column] = color
        return result
    hull = lattice_convex_hull(points)
    if len(hull) < 3:
        return None
    edges = [
        (hull[index], hull[(index + 1) % len(hull)])
        for index in range(len(hull))
    ]
    lengths = [
        (second[0] - first[0]) ** 2
        + (second[1] - first[1]) ** 2
        for first, second in edges
    ]
    maximum = max(lengths)
    longest = [
        edge for edge, length in zip(edges, lengths) if length == maximum
    ]
    if (
        len(longest) != 2
        or any(
            first[0] == second[0] or first[1] == second[1]
            for first, second in longest
        )
    ):
        return None
    first_vector = (
        longest[0][1][0] - longest[0][0][0],
        longest[0][1][1] - longest[0][0][1],
    )
    second_vector = (
        longest[1][1][0] - longest[1][0][0],
        longest[1][1][1] - longest[1][0][1],
    )
    if (
        first_vector[0] * second_vector[1]
        != first_vector[1] * second_vector[0]
    ):
        return None
    filled = lattice_convex_fill(hull)
    if points != filled:
        selected = filled
    else:
        selected: set[tuple[int, int]] = set()
        for edge in longest:
            selected.update(rasterized_edge(*edge))
    result = [[0 for _ in values] for values in grid]
    for row, column in selected:
        result[row][column] = color
    return result


def toggle_horizontal_band(grid: Grid) -> Grid | None:
    """Toggle a solid horizontal band and its top/bottom boundary rows."""
    colors = sorted({value for row in grid for value in row} - {0})
    if len(colors) != 1:
        return None
    color = colors[0]
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == color
    ]
    top, bottom, left, right = point_bbox(points)
    if bottom <= top:
        return None
    point_set = set(points)
    full_rows = {
        row
        for row in range(top, bottom + 1)
        if all(
            (row, column) in point_set
            for column in range(left, right + 1)
        )
    }
    result = [[0 for _ in values] for values in grid]
    if (
        full_rows == {top, bottom}
        and len(points) == 2 * (right - left + 1)
    ):
        for row in range(top, bottom + 1):
            for column in range(left, right + 1):
                result[row][column] = color
    elif full_rows == set(range(top, bottom + 1)):
        for column in range(left, right + 1):
            result[top][column] = color
            result[bottom][column] = color
    else:
        return None
    return result


def fill_between_border_with_second_color(
    grid: Grid,
) -> Grid | None:
    """Fill zero cells between same-color row boundaries with a second color."""
    colors = sorted({value for row in grid for value in row} - {0})
    if len(colors) != 2:
        return None
    extreme_counts: Counter[int] = Counter()
    for values in grid:
        occupied = [
            column for column, value in enumerate(values) if value != 0
        ]
        if len(occupied) >= 2:
            extreme_counts[values[occupied[0]]] += 1
            extreme_counts[values[occupied[-1]]] += 1
    maximum = max(extreme_counts.values(), default=0)
    candidates = [
        color for color, count in extreme_counts.items()
        if count == maximum
    ]
    if len(candidates) != 1:
        return None
    border = candidates[0]
    fill = colors[0] if colors[1] == border else colors[1]
    result = [row[:] for row in grid]
    for row, values in enumerate(grid):
        boundary = [
            column for column, value in enumerate(values)
            if value == border
        ]
        if len(boundary) < 2:
            continue
        for column in range(boundary[0] + 1, boundary[-1]):
            if result[row][column] == 0:
                result[row][column] = fill
    return result


def complete_checkerboard_in_border(
    grid: Grid,
) -> Grid | None:
    """Complete one checkerboard parity between row-wise frame boundaries."""
    colors = sorted({value for row in grid for value in row} - {0})
    if len(colors) != 2:
        return None
    parity_sets = {
        color: {
            (row + column) % 2
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        }
        for color in colors
    }
    patterned = [
        color for color, parities in parity_sets.items()
        if len(parities) == 1
    ]
    if len(patterned) != 1:
        return None
    pattern = patterned[0]
    border = colors[0] if colors[1] == pattern else colors[1]
    parity = next(iter(parity_sets[pattern]))
    result = [row[:] for row in grid]
    for row, values in enumerate(grid):
        boundary = [
            column for column, value in enumerate(values)
            if value == border
        ]
        if len(boundary) < 2:
            continue
        for column in range(boundary[0] + 1, boundary[-1]):
            if result[row][column] == 0 and (row + column) % 2 == parity:
                result[row][column] = pattern
    return result


def above_below_separator_row(
    grid: Grid,
) -> tuple[int, int] | None:
    """Find a unique strongest solid or alternating horizontal divider."""
    background = mode_color(grid)
    width = len(grid[0])
    candidates: list[tuple[int, int, int]] = []
    for row, values in enumerate(grid):
        occupied = [
            column
            for column, value in enumerate(values)
            if value != background
        ]
        colors = {values[column] for column in occupied}
        if len(colors) != 1 or len(occupied) < (width + 1) // 2:
            continue
        steps = {
            second - first
            for first, second in zip(occupied, occupied[1:])
        }
        if steps and steps not in ({1}, {2}):
            continue
        if not steps and width > 1:
            continue
        candidates.append((row, next(iter(colors)), len(occupied)))
    if not candidates:
        return None
    maximum = max(count for _, _, count in candidates)
    strongest = [
        (row, color)
        for row, color, count in candidates
        if count == maximum
    ]
    return strongest[0] if len(strongest) == 1 else None


def erase_below_separator(grid: Grid) -> Grid | None:
    """Keep a divider and everything above it; erase everything below."""
    separator = above_below_separator_row(grid)
    if separator is None:
        return None
    row, _ = separator
    background = mode_color(grid)
    result = [values[:] for values in grid]
    for target_row in range(row + 1, len(grid)):
        result[target_row] = [background] * len(grid[0])
    return result


def keep_at_or_below_color_three(grid: Grid) -> Grid | None:
    """Use the first literal ARC-green row as a horizontal keep boundary."""
    rows = [
        row
        for row, values in enumerate(grid)
        if 3 in values
    ]
    if not rows:
        return None
    background = mode_color(grid)
    result = [values[:] for values in grid]
    for row in range(min(rows)):
        result[row] = [background] * len(grid[0])
    return result


def move_top_component_down_to_touch(grid: Grid) -> Grid | None:
    """Move the sole object above the unique largest object down to touch."""
    background = mode_color(grid)
    groups = colored_components(grid, background, 4)
    if len(groups) < 2:
        return None
    maximum = max(len(group) for _, group in groups)
    anchors = [
        group for _, group in groups if len(group) == maximum
    ]
    if len(anchors) != 1:
        return None
    anchor_top = point_bbox(anchors[0])[0]
    moving = [
        (color, group)
        for color, group in groups
        if point_bbox(group)[1] < anchor_top
    ]
    if len(moving) != 1:
        return None
    color, group = moving[0]
    delta = anchor_top - 1 - point_bbox(group)[1]
    if delta <= 0:
        return None
    result = [row[:] for row in grid]
    for row, column in group:
        result[row][column] = background
    targets = [(row + delta, column) for row, column in group]
    if any(
        not 0 <= row < len(grid)
        or not 0 <= column < len(grid[0])
        or result[row][column] != background
        for row, column in targets
    ):
        return None
    for row, column in targets:
        result[row][column] = color
    return result


def mark_above_below_components(grid: Grid) -> Grid | None:
    """Mark left ends above a divider and right ends below it."""
    separator = above_below_separator_row(grid)
    if separator is None:
        return None
    separator_index, marker = separator
    background = mode_color(grid)
    groups = [
        group
        for _, group in colored_components(grid, background, 4)
        if not all(row == separator_index for row, _ in group)
    ]
    if not groups:
        return None
    result = [row[:] for row in grid]
    for group in groups:
        top, bottom, left, right = point_bbox(group)
        if bottom < separator_index:
            candidates = [
                point for point in group if point[1] == left
            ]
        elif top > separator_index:
            candidates = [
                point for point in group if point[1] == right
            ]
        else:
            return None
        row, column = min(candidates)
        result[row][column] = marker
    return result


def propagate_unique_rarest_vertical(
    grid: Grid, direction: int
) -> Grid | None:
    """Propagate the rarer nonzero color through the other color vertically."""
    counts = Counter(
        value for row in grid for value in row if value != 0
    )
    if len(counts) != 2:
        return None
    minimum = min(counts.values())
    rare = [
        color for color, count in counts.items() if count == minimum
    ]
    if len(rare) != 1:
        return None
    marker = rare[0]
    base = next(color for color in counts if color != marker)
    result = [row[:] for row in grid]
    sources = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == marker
    ]
    for row, column in sources:
        target = row + direction
        while 0 <= target < len(grid) and grid[target][column] == base:
            result[target][column] = marker
            target += direction
    return result


def propagate_unique_rarest_up(grid: Grid) -> Grid | None:
    return propagate_unique_rarest_vertical(grid, -1)


def propagate_unique_rarest_down(grid: Grid) -> Grid | None:
    return propagate_unique_rarest_vertical(grid, 1)


def move_components_from_above_to_below_frame(
    grid: Grid,
) -> Grid | None:
    """Move eight-connected minority objects below the majority-color frame."""
    counts = Counter(
        value for row in grid for value in row if value != 0
    )
    if len(counts) != 2:
        return None
    frame = max(counts, key=lambda color: (counts[color], -color))
    movable = next(color for color in counts if color != frame)
    groups = [
        group
        for color, group in colored_components(grid, 0, 8)
        if color == movable
    ]
    if not groups:
        return None
    result = [row[:] for row in grid]
    for group in groups:
        for row, column in group:
            result[row][column] = 0
    destinations: list[list[tuple[int, int]]] = []
    for group in groups:
        top, bottom, left, right = point_bbox(group)
        obstacles = [
            row
            for row in range(len(grid))
            for column in range(left, right + 1)
            if grid[row][column] == frame
        ]
        obstacle_bottom = max(obstacles, default=-1)
        if obstacle_bottom < bottom:
            return None
        delta = obstacle_bottom + 1 - top
        target = [(row + delta, column) for row, column in group]
        if any(
            row >= len(grid)
            or result[row][column] != 0
            for row, column in target
        ):
            return None
        destinations.append(target)
    occupied = [
        point for destination in destinations for point in destination
    ]
    if len(occupied) != len(set(occupied)):
        return None
    for destination in destinations:
        for row, column in destination:
            result[row][column] = movable
    return result


def keep_azure_below_top_band(grid: Grid) -> Grid | None:
    """Extract azure pixels below the first non-azure colored band."""
    if not any(value == 8 for row in grid for value in row):
        return None
    top_rows = [
        row
        for row, values in enumerate(grid)
        if any(value not in (0, 8) for value in values)
    ]
    if not top_rows:
        return None
    first_row = min(top_rows)
    colors = {
        value for value in grid[first_row] if value not in (0, 8)
    }
    if len(colors) != 1:
        return None
    top_color = next(iter(colors))
    last_top_row = max(
        row
        for row, values in enumerate(grid)
        if top_color in values
    )
    return [
        [
            8 if row > last_top_row and value == 8 else 0
            for value in values
        ]
        for row, values in enumerate(grid)
    ]


def fill_region_below_line(grid: Grid) -> Grid | None:
    """Fill the side below a horizontal or 45-degree monochrome line."""
    background = mode_color(grid)
    colors = sorted(
        {value for row in grid for value in row} - {background}
    )
    if len(colors) != 1:
        return None
    color = colors[0]
    points = sorted(
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == color
    )
    rows = sorted({row for row, _ in points})
    columns = sorted({column for _, column in points})
    result = [values[:] for values in grid]
    if (
        len(rows) == 1
        and columns == list(range(columns[0], columns[-1] + 1))
    ):
        for row in range(rows[0], len(grid)):
            result[row] = [color] * len(grid[0])
        return result
    if len(points) < 2 or len(rows) != len(points):
        return None
    if rows != list(range(rows[0], rows[-1] + 1)):
        return None
    row_columns = {row: column for row, column in points}
    deltas = [
        row_columns[row + 1] - row_columns[row]
        for row in rows[:-1]
    ]
    if len(set(deltas)) != 1 or deltas[0] not in (-1, 1):
        return None
    for row in rows:
        column = row_columns[row]
        if deltas[0] == 1:
            result[row][: column + 1] = [color] * (column + 1)
        else:
            result[row][column:] = [color] * (len(grid[0]) - column)
    for row in range(rows[-1] + 1, len(grid)):
        result[row] = [color] * len(grid[0])
    return result


def nonzero_point_bbox(
    grid: Grid,
) -> tuple[int, int, int, int] | None:
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    ]
    return None if not points else point_bbox(points)


def fill_oriented_hollow_rectangles(grid: Grid) -> Grid | None:
    """Fill tall rectangular frames green and wide frames orange."""
    groups = colored_components(grid, 0, 4)
    if not groups:
        return None
    result = [row[:] for row in grid]
    for color, group in groups:
        top, bottom, left, right = point_bbox(group)
        height, width = bottom - top + 1, right - left + 1
        if height < 3 or width < 3 or height == width:
            return None
        border = {
            (row, column)
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
            if row in (top, bottom) or column in (left, right)
        }
        if set(group) != border:
            return None
        fill = 3 if height > width else 7
        for row in range(top + 1, bottom):
            for column in range(left + 1, right):
                result[row][column] = fill
    return result


def keep_horizontal_stripe_components(grid: Grid) -> Grid | None:
    """Keep multicolor objects whose occupied rows each have one color."""
    groups = multicolor_components(grid)
    if not groups:
        return None
    selected: list[list[tuple[int, int]]] = []
    for group in groups:
        colors = {grid[row][column] for row, column in group}
        if len(colors) < 2:
            return None
        row_colors = {
            row: {
                grid[group_row][column]
                for group_row, column in group
                if group_row == row
            }
            for row in {row for row, _ in group}
        }
        if all(len(values) == 1 for values in row_colors.values()):
            selected.append(group)
    result = [[0 for _ in row] for row in grid]
    for group in selected:
        for row, column in group:
            result[row][column] = grid[row][column]
    return result


def mark_nonzero_bbox_orientation_red(grid: Grid) -> Grid | None:
    """Mark wide layouts at the top and tall layouts at the left in red."""
    bounds = nonzero_point_bbox(grid)
    if bounds is None:
        return None
    top, bottom, left, right = bounds
    height, width = bottom - top + 1, right - left + 1
    result = [row[:] for row in grid]
    if width > height:
        result[0] = [1] * len(grid[0])
    elif height > width:
        for row in range(len(grid)):
            result[row][0] = 1
    else:
        return None
    return result


def recolor_horizontal_two_runs_green(grid: Grid) -> Grid | None:
    """Recolor horizontal runs of two or more ARC-red cells green."""
    if not any(value == 2 for row in grid for value in row):
        return None
    result = [row[:] for row in grid]
    changed = False
    for row, values in enumerate(grid):
        column = 0
        while column < len(values):
            if values[column] != 2:
                column += 1
                continue
            end = column
            while end + 1 < len(values) and values[end + 1] == 2:
                end += 1
            if end > column:
                for target in range(column, end + 1):
                    result[row][target] = 3
                changed = True
            column = end + 1
    return result if changed else None


def mark_parallel_rails_green(grid: Grid) -> Grid | None:
    """Mark the axis selected by opposite-boundary rails in green."""
    if {value for row in grid for value in row} - {0} != {4}:
        return None
    bounds = nonzero_point_bbox(grid)
    if bounds is None:
        return None
    top, bottom, left, right = bounds
    top_columns = {
        column for column in range(left, right + 1)
        if grid[top][column] != 0
    }
    bottom_columns = {
        column for column in range(left, right + 1)
        if grid[bottom][column] != 0
    }
    left_rows = {
        row for row in range(top, bottom + 1)
        if grid[row][left] != 0
    }
    right_rows = {
        row for row in range(top, bottom + 1)
        if grid[row][right] != 0
    }
    horizontal = len(top_columns & bottom_columns)
    vertical = len(left_rows & right_rows)
    if horizontal == vertical:
        return None
    result = [row[:] for row in grid]
    if horizontal > vertical:
        result[0] = [3] * len(grid[0])
    else:
        for row in range(len(grid)):
            result[row][-1] = 3
    return result


def mark_bbox_long_axis_green(grid: Grid) -> Grid | None:
    """Mark wide ARC-blue layouts at top and tall layouts at right."""
    if {value for row in grid for value in row} - {0} != {1}:
        return None
    bounds = nonzero_point_bbox(grid)
    if bounds is None:
        return None
    top, bottom, left, right = bounds
    height, width = bottom - top + 1, right - left + 1
    if height == width:
        return None
    result = [row[:] for row in grid]
    if width > height:
        result[0] = [3] * len(grid[0])
    else:
        for row in range(len(grid)):
            result[row][-1] = 3
    return result


def mark_marker_axis_at_boundary(grid: Grid) -> Grid | None:
    """Project the rarer color's horizontal or vertical axis to a boundary."""
    counts = Counter(
        value for row in grid for value in row if value != 0
    )
    if len(counts) != 2:
        return None
    minimum = min(counts.values())
    markers = [
        color for color, count in counts.items() if count == minimum
    ]
    if len(markers) != 1:
        return None
    marker = markers[0]
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == marker
    ]
    if len(points) < 2:
        return None
    top, bottom, left, right = point_bbox(points)
    height, width = bottom - top + 1, right - left + 1
    if height == width:
        return None
    result = [row[:] for row in grid]
    if width > height:
        result[0] = [marker] * len(grid[0])
    else:
        for row in range(len(grid)):
            result[row][0] = marker
    return result


def remove_above_below_green_core(grid: Grid) -> Grid | None:
    """Erase everything strictly above and below the ARC-green core."""
    rows = [
        row
        for row, values in enumerate(grid)
        if 3 in values
    ]
    if not rows:
        return None
    top, bottom = min(rows), max(rows)
    result = [row[:] for row in grid]
    for row in range(top):
        result[row] = [0] * len(grid[0])
    for row in range(bottom + 1, len(grid)):
        result[row] = [0] * len(grid[0])
    return result


def recolor_line_components_by_orientation(grid: Grid) -> Grid | None:
    """Recolor horizontal monochrome lines orange and vertical lines yellow."""
    groups = colored_components(grid, 0, 4)
    if not groups:
        return None
    result = [row[:] for row in grid]
    for _, group in groups:
        top, bottom, left, right = point_bbox(group)
        height, width = bottom - top + 1, right - left + 1
        if height == width:
            return None
        color = 7 if width > height else 4
        for row, column in group:
            result[row][column] = color
    return result


def mark_color_band_orientation_azure(grid: Grid) -> Grid | None:
    """Mark horizontal color bands at right and vertical bands at top."""
    bounds = nonzero_point_bbox(grid)
    if bounds is None:
        return None
    top, bottom, left, right = bounds
    occupied_rows = [
        {
            grid[row][column]
            for column in range(left, right + 1)
            if grid[row][column] != 0
        }
        for row in range(top, bottom + 1)
    ]
    occupied_columns = [
        {
            grid[row][column]
            for row in range(top, bottom + 1)
            if grid[row][column] != 0
        }
        for column in range(left, right + 1)
    ]
    rows_uniform = all(len(colors) == 1 for colors in occupied_rows)
    columns_uniform = all(
        len(colors) == 1 for colors in occupied_columns
    )
    if rows_uniform == columns_uniform:
        return None
    result = [row[:] for row in grid]
    if rows_uniform:
        for row in range(len(grid)):
            result[row][-1] = 8
    else:
        result[0] = [8] * len(grid[0])
    return result


def inside_outside_exterior_cells(
    grid: Grid,
    walls: set[int],
) -> set[tuple[int, int]]:
    """Return four-connected cells reachable from the outer boundary."""
    height, width = len(grid), len(grid[0])
    exterior: set[tuple[int, int]] = set()
    queue: list[tuple[int, int]] = []
    for row in range(height):
        for column in (0, width - 1):
            point = row, column
            if grid[row][column] not in walls and point not in exterior:
                exterior.add(point)
                queue.append(point)
    for column in range(width):
        for row in (0, height - 1):
            point = row, column
            if grid[row][column] not in walls and point not in exterior:
                exterior.add(point)
                queue.append(point)
    cursor = 0
    while cursor < len(queue):
        row, column = queue[cursor]
        cursor += 1
        for delta_row, delta_column in (
            (-1, 0),
            (1, 0),
            (0, -1),
            (0, 1),
        ):
            neighbor = row + delta_row, column + delta_column
            nr, nc = neighbor
            if (
                0 <= nr < height
                and 0 <= nc < width
                and neighbor not in exterior
                and grid[nr][nc] not in walls
            ):
                exterior.add(neighbor)
                queue.append(neighbor)
    return exterior


def clip_crossing_line_to_repaired_frame(
    grid: Grid,
) -> Grid | None:
    """Clip a crossing color inside a repaired rectangle, diamond, or loop."""
    counts = Counter(
        value for row in grid for value in row if value != 0
    )
    if len(counts) != 2:
        return None
    height, width = len(grid), len(grid[0])
    boundary_counts = {
        color: sum(
            grid[row][column] == color
            for row in range(height)
            for column in range(width)
            if row in (0, height - 1)
            or column in (0, width - 1)
        )
        for color in counts
    }
    minimum = min(boundary_counts.values())
    structures = [
        color
        for color, count in boundary_counts.items()
        if count == minimum
    ]
    if len(structures) != 1:
        return None
    structure = structures[0]
    crossing = next(color for color in counts if color != structure)
    structure_points = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == structure
    }
    top, bottom, left, right = point_bbox(list(structure_points))
    candidates: list[
        tuple[str, set[tuple[int, int]]]
    ] = []
    for thickness in range(
        1,
        min(bottom - top + 1, right - left + 1) // 2 + 1,
    ):
        mask = {
            (row, column)
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
            if row < top + thickness
            or row > bottom - thickness
            or column < left + thickness
            or column > right - thickness
        }
        if structure_points <= mask and all(
            grid[row][column] == crossing
            for row, column in mask - structure_points
        ):
            candidates.append(("rectangle", mask))
    for doubled_row in range(2 * height - 1):
        for doubled_column in range(2 * width - 1):
            radii = {
                abs(2 * row - doubled_row)
                + abs(2 * column - doubled_column)
                for row, column in structure_points
            }
            if len(radii) != 1:
                continue
            radius = next(iter(radii))
            mask = {
                (row, column)
                for row in range(height)
                for column in range(width)
                if (
                    abs(2 * row - doubled_row)
                    + abs(2 * column - doubled_column)
                    == radius
                )
            }
            if structure_points <= mask and all(
                grid[row][column] == crossing
                for row, column in mask - structure_points
            ):
                candidates.append(("diamond", mask))
    distinct = {
        (kind, frozenset(mask)) for kind, mask in candidates
    }
    if len(distinct) == 1:
        kind, frozen_mask = next(iter(distinct))
        frame = set(frozen_mask)
    elif not distinct:
        exterior = inside_outside_exterior_cells(grid, {structure})
        interior = {
            (row, column)
            for row in range(height)
            for column in range(width)
            if (row, column) not in exterior
            and grid[row][column] != structure
        }
        if len(interior) < 2:
            return None
        kind = "existing"
        frame = structure_points
    else:
        return None
    result = [row[:] for row in grid]
    for row, column in frame:
        result[row][column] = structure
    exterior = inside_outside_exterior_cells(result, {structure})
    for row, values in enumerate(result):
        for column, value in enumerate(values):
            if value == crossing and (row, column) in exterior:
                result[row][column] = 0
    if kind == "diamond":
        for row, values in enumerate(result):
            runs = []
            column = 0
            while column < width:
                if values[column] != crossing:
                    column += 1
                    continue
                end = column
                while (
                    end + 1 < width
                    and values[end + 1] == crossing
                ):
                    end += 1
                runs.append((column, end))
                column = end + 1
            if len(runs) == 2 and runs[0][1] + 2 == runs[1][0]:
                result[row][runs[1][0]] = 0
    return result


def grid_cross(
    origin: tuple[int, int],
    first: tuple[int, int],
    second: tuple[int, int],
) -> int:
    return (
        (first[0] - origin[0]) * (second[1] - origin[1])
        - (first[1] - origin[1]) * (second[0] - origin[0])
    )


def grid_convex_hull(
    points: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    ordered = sorted(points)
    if len(ordered) <= 1:
        return ordered
    lower: list[tuple[int, int]] = []
    for point in ordered:
        while (
            len(lower) >= 2
            and grid_cross(lower[-2], lower[-1], point) <= 0
        ):
            lower.pop()
        lower.append(point)
    upper: list[tuple[int, int]] = []
    for point in reversed(ordered):
        while (
            len(upper) >= 2
            and grid_cross(upper[-2], upper[-1], point) <= 0
        ):
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def point_inside_convex_hull(
    point: tuple[int, int],
    hull: list[tuple[int, int]],
) -> bool:
    values = [
        grid_cross(
            hull[index],
            hull[(index + 1) % len(hull)],
            point,
        )
        for index in range(len(hull))
    ]
    return all(value >= 0 for value in values) or all(
        value <= 0 for value in values
    )


def count_markers_outside_frame(grid: Grid) -> Grid | None:
    """Encode the number of marker cells outside the majority-color frame."""
    counts = Counter(
        value for row in grid for value in row if value != 0
    )
    if len(counts) != 2:
        return None
    frame = max(counts, key=lambda color: (counts[color], -color))
    marker = next(color for color in counts if color != frame)
    exterior = inside_outside_exterior_cells(grid, {frame})
    count = sum(
        (row, column) in exterior
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == marker
    )
    return [[0] for _ in range(count)] if 1 <= count <= 30 else None


def keep_segment_or_collinear_marker(grid: Grid) -> Grid | None:
    """Keep a green marker only when it lies on the red point segment."""
    twos = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 2
    ]
    fours = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 4
    ]
    if len(twos) != 2 or len(fours) != 1:
        return None
    first, second = twos
    marker = fours[0]
    delta = second[0] - first[0], second[1] - first[1]
    marker_delta = marker[0] - first[0], marker[1] - first[1]
    collinear = (
        delta[0] * marker_delta[1]
        == delta[1] * marker_delta[0]
    )
    between = (
        min(first[0], second[0]) <= marker[0] <= max(first[0], second[0])
        and min(first[1], second[1])
        <= marker[1]
        <= max(first[1], second[1])
    )
    result = [[0 for _ in row] for row in grid]
    if collinear and between:
        result[marker[0]][marker[1]] = 4
    else:
        for row, column in twos:
            result[row][column] = 2
    return result


def keep_marker_inside_sparse_bbox(grid: Grid) -> Grid | None:
    """Keep green when strictly inside the sparse red frame, else keep red."""
    twos = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 2
    ]
    fours = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 4
    ]
    if len(twos) < 4 or len(fours) != 1:
        return None
    marker = fours[0]
    top, bottom, left, right = point_bbox(twos)
    inside = (
        top < marker[0] < bottom
        and left < marker[1] < right
    )
    result = [[0 for _ in row] for row in grid]
    if inside:
        result[marker[0]][marker[1]] = 4
    else:
        for row, column in twos:
            result[row][column] = 2
    return result


def keep_marker_only_if_inside_all_frames(grid: Grid) -> Grid | None:
    """Remove a singleton unless every other color encloses it."""
    counts = Counter(
        value for row in grid for value in row if value != 0
    )
    singleton = [
        color for color, count in counts.items() if count == 1
    ]
    if len(counts) != 3 or len(singleton) != 1:
        return None
    marker = singleton[0]
    point = next(
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == marker
    )
    frames = sorted(set(counts) - {marker})
    inside_all = all(
        point not in inside_outside_exterior_cells(grid, {frame})
        for frame in frames
    )
    result = [row[:] for row in grid]
    if not inside_all:
        result[point[0]][point[1]] = 0
    return result


def keep_objects_inside_other_color(grid: Grid) -> Grid | None:
    """Keep every cell enclosed by at least one different color."""
    colors = sorted(
        {value for row in grid for value in row} - {0}
    )
    if len(colors) < 2:
        return None
    exterior = {
        color: inside_outside_exterior_cells(grid, {color})
        for color in colors
    }
    result = [[0 for _ in row] for row in grid]
    kept = False
    for row, values in enumerate(grid):
        for column, color in enumerate(values):
            if color == 0:
                continue
            point = row, column
            if any(
                point not in exterior[other]
                for other in colors
                if other != color
            ):
                result[row][column] = color
                kept = True
    return result if kept else None


def rarest_structure_colors(
    grid: Grid,
) -> tuple[int, int] | None:
    counts = Counter(
        value for row in grid for value in row if value != 0
    )
    if len(counts) != 2:
        return None
    minimum = min(counts.values())
    markers = [
        color for color, count in counts.items() if count == minimum
    ]
    if len(markers) != 1:
        return None
    marker = markers[0]
    structure = next(color for color in counts if color != marker)
    return marker, structure


def keep_rarest_inside_structure(grid: Grid) -> Grid | None:
    """Keep rare markers inside or on the majority-color convex hull."""
    colors = rarest_structure_colors(grid)
    if colors is None:
        return None
    marker, structure = colors
    hull = grid_convex_hull(
        {
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == structure
        }
    )
    if len(hull) < 3:
        return None
    result = [[0 for _ in row] for row in grid]
    for row, values in enumerate(grid):
        for column, value in enumerate(values):
            if (
                value == marker
                and point_inside_convex_hull((row, column), hull)
            ):
                result[row][column] = marker
    return result


def has_upward_structure_support(
    grid: Grid,
    point: tuple[int, int],
    structure: int,
) -> bool:
    for delta_row, delta_column in (
        (-1, 0),
        (-1, -1),
        (-1, 1),
    ):
        row = point[0] + delta_row
        column = point[1] + delta_column
        while 0 <= row < len(grid) and 0 <= column < len(grid[0]):
            if grid[row][column] == structure:
                return True
            row += delta_row
            column += delta_column
    return False


def keep_rarest_outside_structure(grid: Grid) -> Grid | None:
    """Keep rare markers outside the supported majority-color hull."""
    colors = rarest_structure_colors(grid)
    if colors is None:
        return None
    marker, structure = colors
    hull = grid_convex_hull(
        {
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == structure
        }
    )
    if len(hull) < 3:
        return None
    result = [[0 for _ in row] for row in grid]
    for row, values in enumerate(grid):
        for column, value in enumerate(values):
            if value != marker:
                continue
            point = row, column
            inside = (
                point_inside_convex_hull(point, hull)
                and has_upward_structure_support(
                    grid,
                    point,
                    structure,
                )
            )
            if not inside:
                result[row][column] = marker
    return result


def count_panel_markers_inside_frames(grid: Grid) -> Grid | None:
    """Count marker cells enclosed by left-to-right frame colors."""
    counts = Counter(
        value for row in grid for value in row if value != 0
    )
    if len(counts) != 3:
        return None
    minimum = min(counts.values())
    markers = [
        color for color, count in counts.items() if count == minimum
    ]
    if len(markers) != 1:
        return None
    marker = markers[0]
    frames = sorted(
        set(counts) - {marker},
        key=lambda color: min(
            column
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ),
    )
    output: list[int] = []
    for frame in frames:
        exterior = inside_outside_exterior_cells(grid, {frame})
        count = sum(
            (row, column) not in exterior
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == marker
        )
        output.extend([frame] * count)
    return [output] if output else None


def keep_markers_between_parallel_lines(grid: Grid) -> Grid | None:
    """Keep green markers lying strictly between red parallel lines."""
    if not any(2 in row for row in grid) or not any(
        4 in row for row in grid
    ):
        return None
    result = [
        [0 if value == 4 else value for value in row]
        for row in grid
    ]
    kept = 0
    for row, values in enumerate(grid):
        for column, value in enumerate(values):
            if value != 4:
                continue
            same_row = [
                index
                for index, candidate in enumerate(grid[row])
                if candidate == 2
            ]
            same_column = [
                index
                for index in range(len(grid))
                if grid[index][column] == 2
            ]
            between_row = (
                len(same_row) >= 2
                and min(same_row) < column < max(same_row)
            )
            between_column = (
                len(same_column) >= 2
                and min(same_column) < row < max(same_column)
            )
            if between_row or between_column:
                result[row][column] = 4
                kept += 1
    return result if kept else None


def center_cell_row(grid: Grid) -> Grid | None:
    if len(grid) != 1 or len(grid[0]) % 2 != 1:
        return None
    return [[grid[0][len(grid[0]) // 2]]]


def crop_middle_nonzero_row(grid: Grid) -> Grid | None:
    row = grid[len(grid) // 2]
    occupied = [index for index, value in enumerate(row) if value != 0]
    return (
        None
        if not occupied
        else [row[occupied[0] : occupied[-1] + 1]]
    )


def remove_nearest_center_component_zero(grid: Grid) -> Grid | None:
    groups = colored_components(grid, 0, 4)
    if not groups:
        return None
    center_row = (len(grid) - 1) / 2
    center_column = (len(grid[0]) - 1) / 2
    scores: list[float] = []
    for _, group in groups:
        top, bottom, left, right = point_bbox(group)
        row_distance = (
            top - center_row
            if center_row < top
            else center_row - bottom
            if center_row > bottom
            else 0
        )
        column_distance = (
            left - center_column
            if center_column < left
            else center_column - right
            if center_column > right
            else 0
        )
        scores.append(row_distance**2 + column_distance**2)
    minimum = min(scores)
    matches = [index for index, score in enumerate(scores) if score == minimum]
    if len(matches) > 1:
        minimum_size = min(len(groups[index][1]) for index in matches)
        matches = [
            index
            for index in matches
            if len(groups[index][1]) == minimum_size
        ]
    if len(matches) != 1:
        return None
    result = [row[:] for row in grid]
    for row, column in groups[matches[0]][1]:
        result[row][column] = 0
    return result


def move_unique_rarest_to_dominant_center(grid: Grid) -> Grid | None:
    background = mode_color(grid)
    counts = Counter(
        value
        for row in grid
        for value in row
        if value != background
    )
    if len(counts) != 2:
        return None
    minimum = min(counts.values())
    rare = [color for color, count in counts.items() if count == minimum]
    if len(rare) != 1:
        return None
    marker = rare[0]
    marker_points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == marker
    ]
    dominant_points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value not in (background, marker)
    ]
    if not marker_points or not dominant_points:
        return None
    marker_top, marker_bottom, marker_left, marker_right = point_bbox(
        marker_points
    )
    top, bottom, left, right = point_bbox(dominant_points)
    marker_height = marker_bottom - marker_top + 1
    marker_width = marker_right - marker_left + 1
    target_top = (top + bottom - marker_height + 1) // 2
    target_left = (left + right - marker_width + 1) // 2
    result = [row[:] for row in grid]
    for row, column in marker_points:
        result[row][column] = background
    for row, column in marker_points:
        target_row = target_top + row - marker_top
        target_column = target_left + column - marker_left
        if not (
            0 <= target_row < len(grid)
            and 0 <= target_column < len(grid[0])
        ):
            return None
        result[target_row][target_column] = marker
    return result


def move_secondary_to_primary_line_center(grid: Grid) -> Grid | None:
    background = mode_color(grid)
    counts = Counter(
        value
        for row in grid
        for value in row
        if value != background
    )
    if len(counts) != 2:
        return None
    maximum = max(counts.values())
    primary_matches = [
        color for color, count in counts.items() if count == maximum
    ]
    if len(primary_matches) != 1:
        return None
    primary = primary_matches[0]
    secondary = next(color for color in counts if color != primary)
    primary_points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == primary
    ]
    marker_points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == secondary
    ]
    top, bottom, left, right = point_bbox(primary_points)
    marker_top, marker_bottom, marker_left, marker_right = point_bbox(
        marker_points
    )
    if top == bottom:
        delta_row = 0
        delta_column = (left + right - marker_left - marker_right) // 2
    elif left == right:
        delta_row = (top + bottom - marker_top - marker_bottom) // 2
        delta_column = 0
    else:
        return None
    result = [row[:] for row in grid]
    for row, column in marker_points:
        result[row][column] = background
    for row, column in marker_points:
        target_row = row + delta_row
        target_column = column + delta_column
        if not (
            0 <= target_row < len(grid)
            and 0 <= target_column < len(grid[0])
        ):
            return None
        result[target_row][target_column] = secondary
    return result


def move_marker_between_parallel_lines_two_color(
    grid: Grid,
) -> Grid | None:
    background = mode_color(grid)
    counts = Counter(
        value
        for row in grid
        for value in row
        if value != background
    )
    if len(counts) != 2:
        return None
    line_color = max(counts, key=counts.get)
    marker_color = next(color for color in counts if color != line_color)
    line_points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == line_color
    ]
    marker_points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == marker_color
    ]
    rows = sorted({row for row, _ in line_points})
    columns = sorted({column for _, column in line_points})
    result = [row[:] for row in grid]
    for row, column in marker_points:
        result[row][column] = background
    if len(rows) == 2:
        delta_row = (rows[0] + rows[1]) // 2 - marker_points[0][0]
        delta_column = 0
    elif len(columns) == 2:
        delta_row = 0
        delta_column = (
            (columns[0] + columns[1]) // 2 - marker_points[0][1]
        )
    else:
        return None
    for row, column in marker_points:
        target_row = row + delta_row
        target_column = column + delta_column
        if not (
            0 <= target_row < len(grid)
            and 0 <= target_column < len(grid[0])
        ):
            return None
        result[target_row][target_column] = marker_color
    return result


def move_same_color_marker_between_full_lines(grid: Grid) -> Grid | None:
    nonzero = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    ]
    if not nonzero or len({grid[row][column] for row, column in nonzero}) != 1:
        return None
    color = grid[nonzero[0][0]][nonzero[0][1]]
    full_rows = [
        row
        for row, values in enumerate(grid)
        if all(value == color for value in values)
    ]
    full_columns = [
        column
        for column in range(len(grid[0]))
        if all(grid[row][column] == color for row in range(len(grid)))
    ]
    result = [row[:] for row in grid]
    if len(full_rows) == 2:
        markers = [point for point in nonzero if point[0] not in full_rows]
        if len(markers) != 1:
            return None
        row, column = markers[0]
        result[row][column] = 0
        result[(full_rows[0] + full_rows[1]) // 2][column] = color
        return result
    if len(full_columns) == 2:
        markers = [
            point for point in nonzero if point[1] not in full_columns
        ]
        if len(markers) != 1:
            return None
        row, column = markers[0]
        result[row][column] = 0
        result[row][(full_columns[0] + full_columns[1]) // 2] = color
        return result
    return None


def move_marker_between_parallel_lines(grid: Grid) -> Grid | None:
    nonzero_colors = {
        value for row in grid for value in row if value != 0
    }
    return (
        move_same_color_marker_between_full_lines(grid)
        if len(nonzero_colors) == 1
        else move_marker_between_parallel_lines_two_color(grid)
    )


def mark_components_and_singleton_color_bbox_centers(grid: Grid) -> Grid | None:
    groups = colored_components(grid, mode_color(grid), 8)
    if not groups:
        return None
    result = [row[:] for row in grid]
    by_color: dict[int, list[list[tuple[int, int]]]] = {}
    for color, group in groups:
        by_color.setdefault(color, []).append(group)
    for color, color_groups in by_color.items():
        if len(color_groups) > 1 and all(
            len(group) == 1 for group in color_groups
        ):
            combined = [point for group in color_groups for point in group]
            top, bottom, left, right = point_bbox(combined)
            result[(top + bottom) // 2][(left + right) // 2] = color
            continue
        for group in color_groups:
            top, bottom, left, right = point_bbox(group)
            result[(top + bottom) // 2][(left + right) // 2] = color
    return result


def add_one_at_nonzero_bbox_center(grid: Grid) -> Grid | None:
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    ]
    if not points:
        return None
    top, bottom, left, right = point_bbox(points)
    result = [row[:] for row in grid]
    result[(top + bottom) // 2][(left + right) // 2] = 1
    return result


def center_markers_across_lines(grid: Grid) -> Grid | None:
    background = mode_color(grid)
    counts = Counter(
        value
        for row in grid
        for value in row
        if value != background
    )
    if len(counts) != 2:
        return None
    line_color = max(counts, key=counts.get)
    marker_color = next(color for color in counts if color != line_color)
    line_groups = [
        group
        for color, group in colored_components(grid, background, 4)
        if color == line_color
    ]
    marker_points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == marker_color
    ]
    if not line_groups or len(marker_points) != len(line_groups):
        return None
    result = [row[:] for row in grid]
    for row, column in marker_points:
        result[row][column] = background
    unused = set(marker_points)
    for group in line_groups:
        top, bottom, left, right = point_bbox(group)
        if top != bottom and left != right:
            return None
        center = (top + bottom) // 2, (left + right) // 2
        marker = min(
            unused,
            key=lambda point: (
                (point[0] - center[0]) ** 2
                + (point[1] - center[1]) ** 2,
                point,
            ),
        )
        unused.remove(marker)
        offsets = (
            ((-1, 0), (0, 0), (1, 0))
            if top == bottom
            else ((0, -1), (0, 0), (0, 1))
        )
        for delta_row, delta_column in offsets:
            target_row = center[0] + delta_row
            target_column = center[1] + delta_column
            if not (
                0 <= target_row < len(grid)
                and 0 <= target_column < len(grid[0])
            ):
                return None
            result[target_row][target_column] = marker_color
    return result


def crop_nearest_center_component_excluding_largest(
    grid: Grid,
) -> Grid | None:
    background = mode_color(grid)
    groups = colored_components(grid, background, 8)
    if len(groups) < 2:
        return None
    sizes = [len(group) for _, group in groups]
    maximum = max(sizes)
    if sizes.count(maximum) != 1:
        return None
    center_row = (len(grid) - 1) / 2
    center_column = (len(grid[0]) - 1) / 2
    scored: list[tuple[float, int, list[tuple[int, int]]]] = []
    for color, group in groups:
        if len(group) == maximum:
            continue
        top, bottom, left, right = point_bbox(group)
        row_distance = (
            top - center_row
            if center_row < top
            else center_row - bottom
            if center_row > bottom
            else 0
        )
        column_distance = (
            left - center_column
            if center_column < left
            else center_column - right
            if center_column > right
            else 0
        )
        scored.append(
            (row_distance**2 + column_distance**2, color, group)
        )
    minimum = min(item[0] for item in scored)
    matches = [item for item in scored if item[0] == minimum]
    if len(matches) != 1:
        return None
    _, color, selected = matches[0]
    top, bottom, left, right = point_bbox(selected)
    result = [
        [background for _ in range(left, right + 1)]
        for _ in range(top, bottom + 1)
    ]
    for row, column in selected:
        result[row - top][column - left] = color
    return result


def translate_point_groups(
    grid: Grid,
    shifts: list[tuple[list[tuple[int, int]], int, int]],
    remove_other: bool = False,
) -> Grid | None:
    background = mode_color(grid)
    result = (
        [[background for _ in row] for row in grid]
        if remove_other
        else [row[:] for row in grid]
    )
    for group, _, _ in shifts:
        for row, column in group:
            result[row][column] = background
    for group, delta_row, delta_column in shifts:
        for row, column in group:
            target_row = row + delta_row
            target_column = column + delta_column
            if not (
                0 <= target_row < len(grid)
                and 0 <= target_column < len(grid[0])
            ):
                return None
            result[target_row][target_column] = grid[row][column]
    return result


def move_two_horizontal_clusters_outward(grid: Grid) -> Grid | None:
    background = mode_color(grid)
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != background
    ]
    by_color: dict[int, list[tuple[int, int]]] = {}
    for row, column in points:
        by_color.setdefault(grid[row][column], []).append((row, column))
    if len(by_color) == 2:
        color_groups = sorted(
            by_color.values(), key=lambda group: point_bbox(group)[2]
        )
        first_bbox = point_bbox(color_groups[0])
        second_bbox = point_bbox(color_groups[1])
        if first_bbox[3] < second_bbox[2]:
            return translate_point_groups(
                grid,
                [
                    (color_groups[0], 0, -first_bbox[2]),
                    (
                        color_groups[1],
                        0,
                        len(grid[0]) - 1 - second_bbox[3],
                    ),
                ],
            )
    occupied_columns = sorted({column for _, column in points})
    gaps = [
        (
            occupied_columns[index + 1] - occupied_columns[index] - 1,
            index,
        )
        for index in range(len(occupied_columns) - 1)
    ]
    if not gaps:
        return None
    maximum = max(gap for gap, _ in gaps)
    if maximum < 1:
        return None
    split_index = min(index for gap, index in gaps if gap == maximum)
    left_edge = occupied_columns[split_index]
    right_edge = occupied_columns[split_index + 1]
    left_group = [point for point in points if point[1] <= left_edge]
    right_group = [point for point in points if point[1] >= right_edge]
    return translate_point_groups(
        grid,
        [
            (left_group, 0, -point_bbox(left_group)[2]),
            (
                right_group,
                0,
                len(grid[0]) - 1 - point_bbox(right_group)[3],
            ),
        ],
    )


def straight_group(group: list[tuple[int, int]]) -> bool:
    top, bottom, left, right = point_bbox(group)
    return top == bottom or left == right


def move_color_group_to_touch_other(grid: Grid) -> Grid | None:
    background = mode_color(grid)
    by_color: dict[int, list[tuple[int, int]]] = {}
    for row, values in enumerate(grid):
        for column, value in enumerate(values):
            if value != background:
                by_color.setdefault(value, []).append((row, column))
    if len(by_color) != 2:
        return None
    groups = list(by_color.values())
    straight = [
        index for index, group in enumerate(groups) if straight_group(group)
    ]
    if len(straight) == 1:
        stationary = groups[straight[0]]
        moving = groups[1 - straight[0]]
    else:
        sizes = [len(group) for group in groups]
        minimum = min(sizes)
        if sizes.count(minimum) != 1:
            return None
        moving_index = sizes.index(minimum)
        moving = groups[moving_index]
        stationary = groups[1 - moving_index]
    mt, mb, ml, mr = point_bbox(moving)
    st, sb, sl, sr = point_bbox(stationary)
    options: list[tuple[int, int, int]] = []
    if mr < sl:
        options.append((sl - mr - 1, 0, sl - mr - 1))
    if sr < ml:
        options.append((ml - sr - 1, 0, -(ml - sr - 1)))
    if mb < st:
        options.append((st - mb - 1, st - mb - 1, 0))
    if sb < mt:
        options.append((mt - sb - 1, -(mt - sb - 1), 0))
    if not options:
        return [row[:] for row in grid]
    _, delta_row, delta_column = min(options)
    return translate_point_groups(
        grid, [(moving, delta_row, delta_column)]
    )


def move_two_spatial_clusters_to_touch(grid: Grid) -> Grid | None:
    background = mode_color(grid)
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != background
    ]
    occupied_rows = sorted({row for row, _ in points})
    occupied_columns = sorted({column for _, column in points})

    def largest_gap(values: list[int]) -> tuple[int, int] | None:
        gaps = [
            (values[index + 1] - values[index] - 1, index)
            for index in range(len(values) - 1)
        ]
        return max(gaps) if gaps else None

    row_gap = largest_gap(occupied_rows)
    column_gap = largest_gap(occupied_columns)
    candidates = [
        ("row", row_gap) if row_gap is not None else None,
        ("column", column_gap) if column_gap is not None else None,
    ]
    candidates = [
        item for item in candidates if item is not None and item[1][0] > 0
    ]
    if not candidates:
        return None
    axis, (_, split_index) = max(candidates, key=lambda item: item[1][0])
    if axis == "row":
        edge = occupied_rows[split_index]
        first = [point for point in points if point[0] <= edge]
        second = [point for point in points if point[0] > edge]
    else:
        edge = occupied_columns[split_index]
        first = [point for point in points if point[1] <= edge]
        second = [point for point in points if point[1] > edge]
    colors = {grid[row][column] for row, column in points}
    if len(colors) > 1:
        first_colors = {grid[row][column] for row, column in first}
        second_colors = {grid[row][column] for row, column in second}
        if first_colors & second_colors:
            return None
    if len(first) == len(second):
        return None
    moving, stationary = (
        (first, second) if len(first) < len(second) else (second, first)
    )
    mt, mb, ml, mr = point_bbox(moving)
    st, sb, sl, sr = point_bbox(stationary)
    if mr < sl:
        shift = 0, sl - mr - 1
    elif sr < ml:
        shift = 0, -(ml - sr - 1)
    elif mb < st:
        shift = st - mb - 1, 0
    elif sb < mt:
        shift = -(mt - sb - 1), 0
    else:
        return None
    return translate_point_groups(grid, [(moving, shift[0], shift[1])])


def move_marker_opposite_boundary_remove_line(grid: Grid) -> Grid | None:
    background = mode_color(grid)
    groups = colored_components(grid, background, 4)
    full_lines: list[tuple[int, str]] = []
    for index, (_, group) in enumerate(groups):
        top, bottom, left, right = point_bbox(group)
        if top == bottom and len(group) == len(grid[0]):
            full_lines.append((index, "horizontal"))
        if left == right and len(group) == len(grid):
            full_lines.append((index, "vertical"))
    if len(full_lines) != 1:
        return None
    line_index, orientation = full_lines[0]
    marker = [
        point
        for index, (_, group) in enumerate(groups)
        if index != line_index
        for point in group
    ]
    if not marker:
        return None
    top, bottom, left, right = point_bbox(marker)
    if orientation == "vertical":
        if top == 0:
            delta_row = len(grid) - 1 - bottom
        elif bottom == len(grid) - 1:
            delta_row = -top
        else:
            return None
        delta_column = 0
    else:
        delta_row = 0
        if left == 0:
            delta_column = len(grid[0]) - 1 - right
        elif right == len(grid[0]) - 1:
            delta_column = -left
        else:
            return None
    return translate_point_groups(
        grid,
        [(marker, delta_row, delta_column)],
        remove_other=True,
    )


def move_markers_to_touch_line_along_alignment(
    grid: Grid,
) -> Grid | None:
    background = mode_color(grid)
    groups = colored_components(grid, background, 4)
    straight_groups = [
        group
        for _, group in groups
        if straight_group(group) and len(group) >= 3
    ]
    if len(straight_groups) != 1:
        return None
    line = straight_groups[0]
    marker = [
        point
        for _, group in groups
        if group is not line
        for point in group
    ]
    if not marker:
        return None
    lt, lb, ll, lr = point_bbox(line)
    mt, mb, ml, mr = point_bbox(marker)
    if lt == lb:
        delta_row = (
            lt - mb - 1
            if mb < lt
            else lb - mt + 1
            if mt > lb
            else 0
        )
        if len(marker) > 1 and len(
            {row + column for row, column in marker}
        ) == 1:
            delta_column = -delta_row
        elif len(marker) > 1 and len(
            {row - column for row, column in marker}
        ) == 1:
            delta_column = delta_row
        else:
            delta_column = 0
    elif ll == lr:
        delta_column = (
            ll - mr - 1
            if mr < ll
            else lr - ml + 1
            if ml > lr
            else 0
        )
        if len(marker) > 1 and len(
            {row + column for row, column in marker}
        ) == 1:
            delta_row = -delta_column
        elif len(marker) > 1 and len(
            {row - column for row, column in marker}
        ) == 1:
            delta_row = delta_column
        else:
            delta_row = 0
    else:
        return None
    return translate_point_groups(
        grid, [(marker, delta_row, delta_column)]
    )


def arrow_pointing_direction(
    group: list[tuple[int, int]],
) -> tuple[int, int] | None:
    rows: dict[int, list[int]] = {}
    columns: dict[int, list[int]] = {}
    for row, column in group:
        rows.setdefault(row, []).append(column)
        columns.setdefault(column, []).append(row)
    row, row_values = max(rows.items(), key=lambda item: len(item[1]))
    column, column_values = max(
        columns.items(), key=lambda item: len(item[1])
    )
    if len(row_values) < 3 or len(column_values) < 3:
        return None
    left, right = min(row_values), max(row_values)
    top, bottom = min(column_values), max(column_values)
    horizontal_endpoint = column in (left, right)
    vertical_endpoint = row in (top, bottom)
    if horizontal_endpoint == vertical_endpoint:
        return None
    if horizontal_endpoint:
        return (0, 1) if column == left else (0, -1)
    return (1, 0) if row == top else (-1, 0)


def move_arrows_to_pointing_boundary(grid: Grid) -> Grid | None:
    groups = [
        group
        for _, group in colored_components(grid, mode_color(grid), 4)
    ]
    if not groups:
        return None
    shifts: list[tuple[list[tuple[int, int]], int, int]] = []
    for group in groups:
        direction = arrow_pointing_direction(group)
        if direction is None:
            return None
        top, bottom, left, right = point_bbox(group)
        if direction == (0, 1):
            delta = 0, len(grid[0]) - 1 - right
        elif direction == (0, -1):
            delta = 0, -left
        elif direction == (1, 0):
            delta = len(grid) - 1 - bottom, 0
        else:
            delta = -top, 0
        shifts.append((group, delta[0], delta[1]))
    return translate_point_groups(grid, shifts)


def adaptive_gravity_down_or_right(grid: Grid) -> Grid:
    background = mode_color(grid)
    vertical_adjacencies = sum(
        grid[row][column] != background
        and grid[row + 1][column] != background
        for row in range(len(grid) - 1)
        for column in range(len(grid[0]))
    )
    horizontal_adjacencies = sum(
        grid[row][column] != background
        and grid[row][column + 1] != background
        for row in range(len(grid))
        for column in range(len(grid[0]) - 1)
    )
    result = [[background for _ in row] for row in grid]
    if vertical_adjacencies > horizontal_adjacencies:
        for column in range(len(grid[0])):
            values = [
                grid[row][column]
                for row in range(len(grid))
                if grid[row][column] != background
            ]
            for offset, value in enumerate(reversed(values), start=1):
                result[-offset][column] = value
    else:
        for row, values in enumerate(grid):
            occupied = [value for value in values if value != background]
            for offset, value in enumerate(reversed(occupied), start=1):
                result[row][-offset] = value
    return result


def symmetric_component_shape(
    component: list[tuple[int, int]],
) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Return the complete normalized dihedral orbit of a component."""
    top = min(row for row, _ in component)
    left = min(column for _, column in component)
    points = [(row - top, column - left) for row, column in component]
    variants: set[tuple[tuple[int, int], ...]] = set()
    for swap in (False, True):
        working = [
            (column, row) if swap else (row, column)
            for row, column in points
        ]
        for flip_row in (False, True):
            for flip_column in (False, True):
                transformed = [
                    (
                        -row if flip_row else row,
                        -column if flip_column else column,
                    )
                    for row, column in working
                ]
                minimum_row = min(row for row, _ in transformed)
                minimum_column = min(column for _, column in transformed)
                variants.add(
                    tuple(
                        sorted(
                            (
                                row - minimum_row,
                                column - minimum_column,
                            )
                            for row, column in transformed
                        )
                    )
                )
    return tuple(sorted(variants))


def keep_repeated_symmetric_monochrome_shapes(
    grid: Grid,
) -> Grid | None:
    """Keep objects whose shape occurs at least twice up to D4 symmetry."""
    components = monochrome_components(grid)
    if not components:
        return None
    signatures = [
        symmetric_component_shape(component)
        for component in components
    ]
    counts = Counter(signatures)
    selected = [
        index
        for index, signature in enumerate(signatures)
        if counts[signature] > 1
    ]
    if not selected:
        return None
    background = mode_color(grid)
    result = [
        [background for _ in row]
        for row in grid
    ]
    for index in selected:
        for row, column in components[index]:
            result[row][column] = grid[row][column]
    return result


def fill_grid_mode_color(grid: Grid) -> Grid:
    """Replace the entire grid with its deterministic modal input color."""
    color = mode_color(grid)
    return [[color for _ in row] for row in grid]


def rigid_monochrome_components_horizontal(
    grid: Grid, direction: str
) -> Grid | None:
    """Move each same-color object rigidly to the requested side."""
    components = monochrome_components(grid)
    if not components:
        return None
    width = len(grid[0])
    delta = -1 if direction == "left" else 1
    order = sorted(
        range(len(components)),
        key=lambda index: (
            min(column for _, column in components[index])
            if direction == "left"
            else -max(column for _, column in components[index]),
            index,
        ),
    )
    current = {
        index: component[:]
        for index, component in enumerate(components)
    }
    occupancy = {
        point: index
        for index, component in current.items()
        for point in component
    }
    for index in order:
        points = current[index]
        while True:
            targets = [
                (row, column + delta) for row, column in points
            ]
            if any(
                column < 0
                or column >= width
                or (
                    (row, column) in occupancy
                    and occupancy[(row, column)] != index
                )
                for row, column in targets
            ):
                break
            for point in points:
                occupancy.pop(point)
            for point in targets:
                occupancy[point] = index
            points = targets
        current[index] = points
    background = mode_color(grid)
    result = [
        [background for _ in range(width)]
        for _ in range(len(grid))
    ]
    for index, original in enumerate(components):
        for source, target in zip(original, current[index]):
            row, column = source
            result[target[0]][target[1]] = grid[row][column]
    return result


def monochrome_nearest_corner_consensus(grid: Grid) -> Grid | None:
    """Move same-color objects to unique nearest corners; reject all ties."""
    components = monochrome_components(grid)
    if not components:
        return None
    height, width = len(grid), len(grid[0])
    destinations: list[list[tuple[int, int]]] = []
    for component in components:
        top = min(row for row, _ in component)
        bottom = max(row for row, _ in component)
        left = min(column for _, column in component)
        right = max(column for _, column in component)
        down = height - 1 - bottom
        rightward = width - 1 - right
        if top == down or left == rightward:
            return None
        delta_row = -top if top < down else down
        delta_column = -left if left < rightward else rightward
        destinations.append(
            [
                (row + delta_row, column + delta_column)
                for row, column in component
            ]
        )
    points = [
        point for destination in destinations for point in destination
    ]
    if len(points) != len(set(points)):
        return None
    background = mode_color(grid)
    result = [
        [background for _ in range(width)]
        for _ in range(height)
    ]
    for component, destination in zip(components, destinations):
        for source, target in zip(component, destination):
            row, column = source
            result[target[0]][target[1]] = grid[row][column]
    return result


def connect_same_color_axis(grid: Grid, axis: str) -> Grid:
    """Fill background gaps between matching colors along one axis."""
    result = [row[:] for row in grid]
    background = mode_color(grid)
    height, width = len(grid), len(grid[0])
    line_count = height if axis == "row" else width
    line_length = width if axis == "row" else height
    for line_index in range(line_count):
        line = (
            grid[line_index]
            if axis == "row"
            else [grid[row][line_index] for row in range(height)]
        )
        colors = sorted(set(line) - {background})
        for color in colors:
            positions = [
                index
                for index, value in enumerate(line)
                if value == color
            ]
            if len(positions) < 2:
                continue
            for position in range(min(positions), max(positions) + 1):
                if line[position] != background:
                    continue
                if axis == "row":
                    result[line_index][position] = color
                else:
                    result[position][line_index] = color
    return result


def connect_same_color_columns_then_rows(grid: Grid) -> Grid:
    """Connect vertical pairs first, then horizontal pairs without overwrite."""
    return connect_same_color_axis(
        connect_same_color_axis(grid, "column"),
        "row",
    )


def fill_each_color_bounding_box(grid: Grid) -> Grid:
    """Fill each non-background color's box, preserving existing objects."""
    result = [row[:] for row in grid]
    background = mode_color(grid)
    colors = sorted(
        set(value for row in grid for value in row) - {background}
    )
    for color in colors:
        points = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ]
        top = min(row for row, _ in points)
        bottom = max(row for row, _ in points)
        left = min(column for _, column in points)
        right = max(column for _, column in points)
        for row in range(top, bottom + 1):
            for column in range(left, right + 1):
                if result[row][column] == background:
                    result[row][column] = color
    return result


def extend_uniform_columns_down(grid: Grid) -> Grid:
    """Extend each single-color column downward from its topmost cell."""
    result = [row[:] for row in grid]
    background = mode_color(grid)
    height, width = len(grid), len(grid[0])
    for column in range(width):
        positions = [
            row
            for row in range(height)
            if grid[row][column] != background
        ]
        if not positions:
            continue
        colors = {grid[row][column] for row in positions}
        if len(colors) != 1:
            continue
        color = next(iter(colors))
        for row in range(min(positions), height):
            if result[row][column] == background:
                result[row][column] = color
    return result


def recolor_outer_frame_azure(grid: Grid) -> Grid:
    """Color the one-cell outer frame with ARC azure (color 8)."""
    result = [row[:] for row in grid]
    height, width = len(grid), len(grid[0])
    for column in range(width):
        result[0][column] = 8
        result[height - 1][column] = 8
    for row in range(height):
        result[row][0] = 8
        result[row][width - 1] = 8
    return result


def unique_rarest_nonbackground_color(grid: Grid) -> int | None:
    """Return the unique least frequent non-background color."""
    background = mode_color(grid)
    counts = Counter(
        value
        for row in grid
        for value in row
        if value != background
    )
    if not counts:
        return None
    minimum = min(counts.values())
    matches = [
        color for color, count in counts.items() if count == minimum
    ]
    return matches[0] if len(matches) == 1 else None


def ray_unique_rarest(
    grid: Grid, directions: tuple[str, ...]
) -> Grid | None:
    """Extend the unique rarest color along selected rays until blocked."""
    background = mode_color(grid)
    color = unique_rarest_nonbackground_color(grid)
    if color is None:
        return None
    deltas = {
        "up": (-1, 0),
        "down": (1, 0),
        "left": (0, -1),
        "right": (0, 1),
        "up_left": (-1, -1),
        "up_right": (-1, 1),
        "down_left": (1, -1),
        "down_right": (1, 1),
    }
    height, width = len(grid), len(grid[0])
    result = [row[:] for row in grid]
    sources = [
        (row, column)
        for row in range(height)
        for column in range(width)
        if grid[row][column] == color
    ]
    for row, column in sources:
        for direction in directions:
            delta_row, delta_column = deltas[direction]
            target_row = row + delta_row
            target_column = column + delta_column
            while (
                0 <= target_row < height
                and 0 <= target_column < width
                and result[target_row][target_column] == background
            ):
                result[target_row][target_column] = color
                target_row += delta_row
                target_column += delta_column
    return result


def connect_same_color_diagonals(grid: Grid, anti: bool) -> Grid:
    """Fill gaps between matching colors on every diagonal."""
    result = [row[:] for row in grid]
    background = mode_color(grid)
    height, width = len(grid), len(grid[0])
    keys = (
        range(-(width - 1), height)
        if not anti
        else range(height + width - 1)
    )
    for key in keys:
        points = [
            (row, column)
            for row in range(height)
            for column in range(width)
            if (
                row - column == key
                if not anti
                else row + column == key
            )
        ]
        colors = sorted(
            {
                grid[row][column]
                for row, column in points
                if grid[row][column] != background
            }
        )
        for color in colors:
            positions = [
                index
                for index, (row, column) in enumerate(points)
                if grid[row][column] == color
            ]
            if len(positions) < 2:
                continue
            for index in range(min(positions), max(positions) + 1):
                row, column = points[index]
                if grid[row][column] == background:
                    result[row][column] = color
    return result


def connect_same_color_diagonal_consensus(grid: Grid) -> Grid | None:
    """Connect both diagonal families only when draw order agrees."""
    main_then_anti = connect_same_color_diagonals(
        connect_same_color_diagonals(grid, False),
        True,
    )
    anti_then_main = connect_same_color_diagonals(
        connect_same_color_diagonals(grid, True),
        False,
    )
    return main_then_anti if main_then_anti == anti_then_main else None


def bounding_box(grid: Grid, filled: bool) -> Grid:
    background = mode_color(grid)
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != background
    ]
    if not points:
        return [row[:] for row in grid]
    top = min(row for row, _ in points)
    bottom = max(row for row, _ in points)
    left = min(column for _, column in points)
    right = max(column for _, column in points)
    colors = [
        value for row in grid for value in row if value != background
    ]
    color = Counter(colors).most_common(1)[0][0]
    result = [row[:] for row in grid]
    if filled:
        for row in range(top, bottom + 1):
            for column in range(left, right + 1):
                result[row][column] = color
    else:
        for column in range(left, right + 1):
            result[top][column] = color
            result[bottom][column] = color
        for row in range(top, bottom + 1):
            result[row][left] = color
            result[row][right] = color
    return result


def fill_holes(grid: Grid) -> Grid:
    background = mode_color(grid)
    height, width = len(grid), len(grid[0])
    exterior: set[tuple[int, int]] = set()
    queue: list[tuple[int, int]] = []
    for row in range(height):
        for column in (0, width - 1):
            if grid[row][column] == background and (row, column) not in exterior:
                exterior.add((row, column))
                queue.append((row, column))
    for column in range(width):
        for row in (0, height - 1):
            if grid[row][column] == background and (row, column) not in exterior:
                exterior.add((row, column))
                queue.append((row, column))
    cursor = 0
    while cursor < len(queue):
        row, column = queue[cursor]
        cursor += 1
        for delta_row, delta_column in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbor = row + delta_row, column + delta_column
            nr, nc = neighbor
            if (
                0 <= nr < height
                and 0 <= nc < width
                and grid[nr][nc] == background
                and neighbor not in exterior
            ):
                exterior.add(neighbor)
                queue.append(neighbor)
    colors = [
        value for row in grid for value in row if value != background
    ]
    fill = Counter(colors).most_common(1)[0][0] if colors else background
    result = [row[:] for row in grid]
    for row in range(height):
        for column in range(width):
            if (
                grid[row][column] == background
                and (row, column) not in exterior
            ):
                result[row][column] = fill
    return result


def overlay_symmetry(
    grid: Grid, transforms: list[Callable[[Grid], Grid]]
) -> Grid:
    """Fill background cells from one or more same-sized symmetries."""
    background = mode_color(grid)
    result = [row[:] for row in grid]
    for transform in transforms:
        transformed = transform(grid)
        if (
            len(transformed) != len(result)
            or len(transformed[0]) != len(result[0])
        ):
            return [row[:] for row in grid]
        for row in range(len(result)):
            for column in range(len(result[0])):
                if (
                    result[row][column] == background
                    and transformed[row][column] != background
                ):
                    result[row][column] = transformed[row][column]
    return result


SYMMETRY_COMPLETIONS: dict[str, Callable[[Grid], Grid]] = {
    "horizontal": lambda grid: overlay_symmetry(
        grid, [flip_horizontal]
    ),
    "vertical": lambda grid: overlay_symmetry(grid, [flip_vertical]),
    "central": lambda grid: overlay_symmetry(grid, [rotate_180]),
    "all_reflections": lambda grid: overlay_symmetry(
        grid, [flip_horizontal, flip_vertical, rotate_180]
    ),
}


def crop_bottom_color_component(grid: Grid) -> Grid:
    background = mode_color(grid)
    height, width = len(grid), len(grid[0])
    seen: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []
    for start_row in range(height):
        for start_column in range(width):
            if (
                grid[start_row][start_column] == background
                or (start_row, start_column) in seen
            ):
                continue
            color = grid[start_row][start_column]
            queue = [(start_row, start_column)]
            seen.add((start_row, start_column))
            component: list[tuple[int, int]] = []
            cursor = 0
            while cursor < len(queue):
                row, column = queue[cursor]
                cursor += 1
                component.append((row, column))
                for delta_row, delta_column in (
                    (1, 0),
                    (-1, 0),
                    (0, 1),
                    (0, -1),
                ):
                    neighbor = row + delta_row, column + delta_column
                    nr, nc = neighbor
                    if (
                        0 <= nr < height
                        and 0 <= nc < width
                        and neighbor not in seen
                        and grid[nr][nc] != background
                        and grid[nr][nc] == color
                    ):
                        seen.add(neighbor)
                        queue.append(neighbor)
            components.append(component)
    if not components:
        return [row[:] for row in grid]
    component = min(
        components,
        key=lambda item: (
            -max(row for row, _ in item),
            min(column for _, column in item),
            -len(item),
        ),
    )
    top = min(row for row, _ in component)
    bottom = max(row for row, _ in component)
    left = min(column for _, column in component)
    right = max(column for _, column in component)
    result = [
        [background for _ in range(left, right + 1)]
        for _ in range(top, bottom + 1)
    ]
    for row, column in component:
        result[row - top][column - left] = grid[row][column]
    return result


def crop_bottom_component(grid: Grid) -> Grid:
    """Crop the lowest 4-connected non-background object, colors preserved."""
    background = mode_color(grid)
    height, width = len(grid), len(grid[0])
    seen: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []
    for start_row in range(height):
        for start_column in range(width):
            if (
                grid[start_row][start_column] == background
                or (start_row, start_column) in seen
            ):
                continue
            queue = [(start_row, start_column)]
            seen.add((start_row, start_column))
            component: list[tuple[int, int]] = []
            cursor = 0
            while cursor < len(queue):
                row, column = queue[cursor]
                cursor += 1
                component.append((row, column))
                for delta_row, delta_column in (
                    (1, 0),
                    (-1, 0),
                    (0, 1),
                    (0, -1),
                ):
                    neighbor = row + delta_row, column + delta_column
                    nr, nc = neighbor
                    if (
                        0 <= nr < height
                        and 0 <= nc < width
                        and neighbor not in seen
                        and grid[nr][nc] != background
                    ):
                        seen.add(neighbor)
                        queue.append(neighbor)
            components.append(component)
    if not components:
        return [row[:] for row in grid]
    component = min(
        components,
        key=lambda item: (
            -max(row for row, _ in item),
            min(column for _, column in item),
            -len(item),
        ),
    )
    top = min(row for row, _ in component)
    bottom = max(row for row, _ in component)
    left = min(column for _, column in component)
    right = max(column for _, column in component)
    result = [
        [background for _ in range(left, right + 1)]
        for _ in range(top, bottom + 1)
    ]
    for row, column in component:
        result[row - top][column - left] = grid[row][column]
    return result


def crop_largest_monochrome_component(grid: Grid) -> Grid | None:
    """Crop a unique largest object when its selected component is one color."""
    background = mode_color(grid)
    height, width = len(grid), len(grid[0])
    seen: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []
    for start_row in range(height):
        for start_column in range(width):
            if (
                grid[start_row][start_column] == background
                or (start_row, start_column) in seen
            ):
                continue
            queue = [(start_row, start_column)]
            seen.add((start_row, start_column))
            component: list[tuple[int, int]] = []
            cursor = 0
            while cursor < len(queue):
                row, column = queue[cursor]
                cursor += 1
                component.append((row, column))
                for delta_row, delta_column in (
                    (1, 0),
                    (-1, 0),
                    (0, 1),
                    (0, -1),
                ):
                    neighbor = row + delta_row, column + delta_column
                    nr, nc = neighbor
                    if (
                        0 <= nr < height
                        and 0 <= nc < width
                        and neighbor not in seen
                        and grid[nr][nc] != background
                    ):
                        seen.add(neighbor)
                        queue.append(neighbor)
            components.append(component)
    if not components:
        return None
    largest_size = max(len(component) for component in components)
    largest = [
        component
        for component in components
        if len(component) == largest_size
    ]
    if len(largest) != 1:
        return None
    component = largest[0]
    colors = {grid[row][column] for row, column in component}
    if len(colors) != 1:
        return None
    top = min(row for row, _ in component)
    bottom = max(row for row, _ in component)
    left = min(column for _, column in component)
    right = max(column for _, column in component)
    result = [
        [background for _ in range(left, right + 1)]
        for _ in range(top, bottom + 1)
    ]
    for row, column in component:
        result[row - top][column - left] = grid[row][column]
    return result


def crop_unique_widest_color_component(grid: Grid) -> Grid | None:
    """Crop the unique widest same-color component, preserving its shape."""
    background = mode_color(grid)
    height, width = len(grid), len(grid[0])
    seen: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []
    for start_row in range(height):
        for start_column in range(width):
            if (
                grid[start_row][start_column] == background
                or (start_row, start_column) in seen
            ):
                continue
            color = grid[start_row][start_column]
            queue = [(start_row, start_column)]
            seen.add((start_row, start_column))
            component: list[tuple[int, int]] = []
            cursor = 0
            while cursor < len(queue):
                row, column = queue[cursor]
                cursor += 1
                component.append((row, column))
                for delta_row, delta_column in (
                    (1, 0),
                    (-1, 0),
                    (0, 1),
                    (0, -1),
                ):
                    neighbor = row + delta_row, column + delta_column
                    nr, nc = neighbor
                    if (
                        0 <= nr < height
                        and 0 <= nc < width
                        and neighbor not in seen
                        and grid[nr][nc] == color
                    ):
                        seen.add(neighbor)
                        queue.append(neighbor)
            components.append(component)
    if not components:
        return None

    def component_width(component: list[tuple[int, int]]) -> int:
        columns = [column for _, column in component]
        return max(columns) - min(columns) + 1

    widest = max(component_width(component) for component in components)
    widest_matches = [
        component
        for component in components
        if component_width(component) == widest
    ]
    largest_at_width = max(
        len(component) for component in widest_matches
    )
    matches = [
        component
        for component in widest_matches
        if len(component) == largest_at_width
    ]
    if len(matches) != 1:
        return None
    component = matches[0]
    top = min(row for row, _ in component)
    bottom = max(row for row, _ in component)
    left = min(column for _, column in component)
    right = max(column for _, column in component)
    result = [
        [background for _ in range(left, right + 1)]
        for _ in range(top, bottom + 1)
    ]
    for row, column in component:
        result[row - top][column - left] = grid[row][column]
    return result


def crop_unique_smallest_color_component(grid: Grid) -> Grid | None:
    """Crop a same-color component only when it is uniquely smallest."""
    background = mode_color(grid)
    height, width = len(grid), len(grid[0])
    seen: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []
    for start_row in range(height):
        for start_column in range(width):
            if (
                grid[start_row][start_column] == background
                or (start_row, start_column) in seen
            ):
                continue
            color = grid[start_row][start_column]
            queue = [(start_row, start_column)]
            seen.add((start_row, start_column))
            component: list[tuple[int, int]] = []
            cursor = 0
            while cursor < len(queue):
                row, column = queue[cursor]
                cursor += 1
                component.append((row, column))
                for delta_row, delta_column in (
                    (1, 0),
                    (-1, 0),
                    (0, 1),
                    (0, -1),
                ):
                    neighbor = row + delta_row, column + delta_column
                    nr, nc = neighbor
                    if (
                        0 <= nr < height
                        and 0 <= nc < width
                        and neighbor not in seen
                        and grid[nr][nc] == color
                    ):
                        seen.add(neighbor)
                        queue.append(neighbor)
            components.append(component)
    if not components:
        return None
    smallest = min(len(component) for component in components)
    matches = [
        component
        for component in components
        if len(component) == smallest
    ]
    if len(matches) != 1:
        return None
    component = matches[0]
    top = min(row for row, _ in component)
    bottom = max(row for row, _ in component)
    left = min(column for _, column in component)
    right = max(column for _, column in component)
    result = [
        [background for _ in range(left, right + 1)]
        for _ in range(top, bottom + 1)
    ]
    for row, column in component:
        result[row - top][column - left] = grid[row][column]
    return result


def crop_unique_top_color_component(grid: Grid) -> Grid | None:
    """Crop a same-color component only when it is uniquely topmost."""
    background = mode_color(grid)
    height, width = len(grid), len(grid[0])
    seen: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []
    for start_row in range(height):
        for start_column in range(width):
            if (
                grid[start_row][start_column] == background
                or (start_row, start_column) in seen
            ):
                continue
            color = grid[start_row][start_column]
            queue = [(start_row, start_column)]
            seen.add((start_row, start_column))
            component: list[tuple[int, int]] = []
            cursor = 0
            while cursor < len(queue):
                row, column = queue[cursor]
                cursor += 1
                component.append((row, column))
                for delta_row, delta_column in (
                    (1, 0),
                    (-1, 0),
                    (0, 1),
                    (0, -1),
                ):
                    neighbor = row + delta_row, column + delta_column
                    nr, nc = neighbor
                    if (
                        0 <= nr < height
                        and 0 <= nc < width
                        and neighbor not in seen
                        and grid[nr][nc] == color
                    ):
                        seen.add(neighbor)
                        queue.append(neighbor)
            components.append(component)
    if not components:
        return None
    top = min(min(row for row, _ in component) for component in components)
    matches = [
        component
        for component in components
        if min(row for row, _ in component) == top
    ]
    if len(matches) != 1:
        return None
    component = matches[0]
    bottom = max(row for row, _ in component)
    left = min(column for _, column in component)
    right = max(column for _, column in component)
    result = [
        [background for _ in range(left, right + 1)]
        for _ in range(top, bottom + 1)
    ]
    for row, column in component:
        result[row - top][column - left] = grid[row][column]
    return result


def most_disconnected_color_singleton(grid: Grid) -> Grid | None:
    """Return the color split into the uniquely largest number of objects."""
    background = mode_color(grid)
    height, width = len(grid), len(grid[0])
    component_counts: Counter[int] = Counter()
    color_cells: Counter[int] = Counter()
    seen: set[tuple[int, int]] = set()
    for start_row in range(height):
        for start_column in range(width):
            color = grid[start_row][start_column]
            if (
                color == background
                or (start_row, start_column) in seen
            ):
                continue
            component_counts[color] += 1
            queue = [(start_row, start_column)]
            seen.add((start_row, start_column))
            cursor = 0
            while cursor < len(queue):
                row, column = queue[cursor]
                cursor += 1
                for delta_row, delta_column in (
                    (1, 0),
                    (-1, 0),
                    (0, 1),
                    (0, -1),
                ):
                    neighbor = row + delta_row, column + delta_column
                    nr, nc = neighbor
                    if (
                        0 <= nr < height
                        and 0 <= nc < width
                        and neighbor not in seen
                        and grid[nr][nc] == color
                    ):
                        seen.add(neighbor)
                        queue.append(neighbor)
            color_cells[color] += len(queue)
    if not component_counts:
        return None
    maximum = max(component_counts.values())
    colors = [
        color
        for color, count in component_counts.items()
        if count == maximum
    ]
    if maximum <= 1:
        return None
    if len(colors) > 1:
        minimum_cells = min(color_cells[color] for color in colors)
        colors = [
            color
            for color in colors
            if color_cells[color] == minimum_cells
        ]
    if len(colors) != 1:
        return None
    return [[colors[0]]]


def split_panels(grid: Grid) -> list[Grid]:
    separator_rows = [
        row for row, values in enumerate(grid) if all(value == values[0] for value in values)
    ]
    separator_columns = [
        column
        for column in range(len(grid[0]))
        if all(grid[row][column] == grid[0][column] for row in range(len(grid)))
    ]

    def ranges(length: int, separators: list[int]) -> list[tuple[int, int]]:
        answer: list[tuple[int, int]] = []
        start = 0
        for separator in separators:
            if separator > start:
                answer.append((start, separator))
            start = separator + 1
        if start < length:
            answer.append((start, length))
        return answer

    row_ranges = ranges(len(grid), separator_rows)
    column_ranges = ranges(len(grid[0]), separator_columns)
    panels = [
        [row[left:right] for row in grid[top:bottom]]
        for top, bottom in row_ranges
        for left, right in column_ranges
    ]
    return panels if len(panels) > 1 else []


def select_first_panel_rotate_counterclockwise(grid: Grid) -> Grid | None:
    panels = split_panels(grid)
    return None if not panels else rotate_270(panels[0])


def reduce_3x3_top_left(grid: Grid) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if height % 3 or width % 3:
        return None
    return [
        [grid[row][column] for column in range(0, width, 3)]
        for row in range(0, height, 3)
    ]


def exact_transform_prediction(
    train_pairs: list[dict],
    test_input: Grid,
    function: Callable[[Grid], Grid | None],
) -> Grid | None:
    produced = [function(pair["input"]) for pair in train_pairs]
    if not all(
        prediction is not None and prediction == pair["output"]
        for prediction, pair in zip(produced, train_pairs)
    ):
        return None
    return function(test_input)


def near_exact_transform_prediction(
    train_pairs: list[dict],
    test_input: Grid,
    function: Callable[[Grid], Grid | None],
    max_cell_errors: int,
    min_exact_pairs: int,
) -> Grid | None:
    """Apply an audited transform despite a tightly bounded noisy label."""
    produced = [function(pair["input"]) for pair in train_pairs]
    total_errors = 0
    exact_pairs = 0
    for prediction, pair in zip(produced, train_pairs):
        output = pair["output"]
        if (
            prediction is None
            or len(prediction) != len(output)
            or not prediction
            or not output
            or len(prediction[0]) != len(output[0])
        ):
            return None
        errors = sum(
            source != target
            for source_row, target_row in zip(prediction, output)
            for source, target in zip(source_row, target_row)
        )
        total_errors += errors
        exact_pairs += int(errors == 0)
    if total_errors > max_cell_errors or exact_pairs < min_exact_pairs:
        return None
    return function(test_input)


def infer_color_map(
    train_pairs: list[dict],
    spatial: Callable[[Grid], Grid | None],
) -> dict[int, int] | None:
    mapping: dict[int, int] = {}
    for pair in train_pairs:
        transformed = spatial(pair["input"])
        output = pair["output"]
        if (
            transformed is None
            or
            len(transformed) != len(output)
            or len(transformed[0]) != len(output[0])
        ):
            return None
        for source_row, target_row in zip(transformed, output):
            for source, target in zip(source_row, target_row):
                previous = mapping.get(source)
                if previous is not None and previous != target:
                    return None
                mapping[source] = target
    return mapping


def apply_color_map(grid: Grid, mapping: dict[int, int]) -> Grid | None:
    if any(value not in mapping for row in grid for value in row):
        return None
    return [[mapping[value] for value in row] for row in grid]


def apply_color_map_with_identity_default(
    grid: Grid, mapping: dict[int, int]
) -> Grid:
    return [[mapping.get(value, value) for value in row] for row in grid]


def translate_nonzero_one_down(grid: Grid) -> Grid | None:
    """Translate every nonzero cell down by one on the same canvas."""
    height = len(grid)
    width = len(grid[0])
    points = [
        (row, column)
        for row in range(height)
        for column in range(width)
        if grid[row][column] != 0
    ]
    if not points or any(row + 1 >= height for row, _ in points):
        return None
    result = [[0 for _ in range(width)] for _ in range(height)]
    for row, column in points:
        result[row + 1][column] = grid[row][column]
    return result


def count_nonzero_cells_horizontal_source(
    grid: Grid,
) -> Grid | None:
    colors = sorted({value for row in grid for value in row} - {0})
    if len(colors) != 1:
        return None
    count = sum(value != 0 for row in grid for value in row)
    if not 1 <= count <= 30:
        return None
    return [[colors[0] for _ in range(count)]]


def recolor_nonmodal_cells_five(grid: Grid) -> Grid | None:
    counts = Counter(
        value for row in grid for value in row if value != 0
    )
    if len(counts) < 2:
        return None
    maximum = max(counts.values())
    modes = [
        color for color, count in counts.items() if count == maximum
    ]
    if len(modes) != 1:
        return None
    mode = modes[0]
    result = [row[:] for row in grid]
    changed = False
    for row, values in enumerate(grid):
        for column, value in enumerate(values):
            if value not in (0, mode):
                result[row][column] = 5
                changed = True
    return result if changed else None


def mark_uniform_rows_five(grid: Grid) -> Grid | None:
    height = len(grid)
    width = len(grid[0])
    result = [[0 for _ in range(width)] for _ in range(height)]
    marked = 0
    for row, values in enumerate(grid):
        if len(set(values)) == 1 and values[0] != 0:
            result[row] = [5 for _ in range(width)]
            marked += 1
    return result if 0 < marked < height else None


def weave_two_uniform_rows_checkerboard(grid: Grid) -> Grid | None:
    if len(grid) != 2 or len(grid[0]) < 2:
        return None
    if len(set(grid[0])) != 1 or len(set(grid[1])) != 1:
        return None
    first, second = grid[0][0], grid[1][0]
    if 0 in (first, second) or first == second:
        return None
    return [
        [
            first if (row + column) % 2 == 0 else second
            for column in range(len(grid[0]))
        ]
        for row in range(2)
    ]


def expand_gray_marker_rows_by_column_code(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 3
        or len(grid[0]) != 3
        or ({value for row in grid for value in row} - {0}) != {5}
        or any(row.count(5) != 1 for row in grid)
    ):
        return None
    mapping = {0: 2, 1: 4, 2: 3}
    return [
        [mapping[row.index(5)] for _ in range(3)]
        for row in grid
    ]


def classify_vertical_symmetry_one_else_seven(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 3 or len(grid[0]) != 3:
        return None
    colors = {value for row in grid for value in row} - {0}
    if len(colors) != 1:
        return None
    symmetric = all(row == row[::-1] for row in grid)
    return [[1 if symmetric else 7]]


def render_nonzero_count_two(grid: Grid) -> Grid | None:
    if (
        len(grid) != 3
        or len(grid[0]) != 3
        or ({value for row in grid for value in row} - {0}) != {1}
    ):
        return None
    count = sum(value != 0 for row in grid for value in row)
    if not 1 <= count <= 4:
        return None
    result = [[0, 0, 0] for _ in range(3)]
    for column in range(min(count, 3)):
        result[0][column] = 2
    if count == 4:
        result[1][1] = 2
    return result


def render_distinct_color_count_template_five(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 3
        or len(grid[0]) != 3
        or any(value == 0 for row in grid for value in row)
    ):
        return None
    count = len({value for row in grid for value in row})
    if not 1 <= count <= 3:
        return None
    result = [[0, 0, 0] for _ in range(3)]
    if count == 1:
        result[0] = [5, 5, 5]
    elif count == 2:
        for index in range(3):
            result[index][index] = 5
    else:
        for index in range(3):
            result[index][2 - index] = 5
    return result


def union_horizontal_panels_six(grid: Grid) -> Grid | None:
    width = len(grid[0])
    if width < 2 or width % 2:
        return None
    middle = width // 2
    first = [row[:middle] for row in grid]
    second = [row[middle:] for row in grid]
    first_colors = {
        value for row in first for value in row if value != 0
    }
    second_colors = {
        value for row in second for value in row if value != 0
    }
    if (
        len(first_colors) != 1
        or len(second_colors) != 1
        or first_colors == second_colors
    ):
        return None
    return [
        [
            6 if first[row][column] != 0
            or second[row][column] != 0 else 0
            for column in range(middle)
        ]
        for row in range(len(grid))
    ]


def mark_double_background_vertical_panels_two(
    grid: Grid,
) -> Grid | None:
    height = len(grid)
    width = len(grid[0])
    if height < 2 or height % 2:
        return None
    middle = height // 2
    first = grid[:middle]
    second = grid[middle:]
    first_colors = {
        value for row in first for value in row if value != 0
    }
    second_colors = {
        value for row in second for value in row if value != 0
    }
    if (
        len(first_colors) != 1
        or len(second_colors) != 1
        or first_colors == second_colors
    ):
        return None
    result = [
        [
            2 if first[row][column] == 0
            and second[row][column] == 0 else 0
            for column in range(width)
        ]
        for row in range(middle)
    ]
    count = sum(value == 2 for row in result for value in row)
    if count == 0 or count == middle * width:
        return None
    return result


def append_horizontal_mirror(grid: Grid) -> Grid | None:
    if len(grid[0]) * 2 > 30:
        return None
    return [row + row[::-1] for row in grid]


def append_vertical_mirror(grid: Grid) -> Grid | None:
    if len(grid) * 2 > 30:
        return None
    return [row[:] for row in grid] + [
        row[:] for row in grid[::-1]
    ]


def prepend_vertical_mirror(grid: Grid) -> Grid | None:
    if len(grid) * 2 > 30:
        return None
    return [row[:] for row in grid[::-1]] + [
        row[:] for row in grid
    ]


def recolor_singleton_components_one(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row} - {0}
    if len(colors) != 1 or 1 in colors:
        return None
    color = next(iter(colors))
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == color
    }
    components: list[list[tuple[int, int]]] = []
    while remaining:
        start = remaining.pop()
        stack = [start]
        component = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    stack.append(point)
                    component.append(point)
        components.append(component)
    singletons = [
        component[0] for component in components if len(component) == 1
    ]
    if (
        not singletons
        or not any(len(component) > 1 for component in components)
    ):
        return None
    result = [row[:] for row in grid]
    for row, column in singletons:
        result[row][column] = 1
    return result


def intersect_horizontal_panels_across_separator_two(
    grid: Grid,
) -> Grid | None:
    width = len(grid[0])
    if width % 2 != 1:
        return None
    separator = width // 2
    line = [row[separator] for row in grid]
    if len(set(line)) != 1 or line[0] == 0:
        return None
    first = [row[:separator] for row in grid]
    second = [row[separator + 1 :] for row in grid]
    first_colors = {
        value for row in first for value in row if value != 0
    }
    second_colors = {
        value for row in second for value in row if value != 0
    }
    if (
        len(first_colors) != 1
        or first_colors != second_colors
        or line[0] in first_colors
    ):
        return None
    result = [
        [
            2 if first[row][column] != 0
            and second[row][column] != 0 else 0
            for column in range(separator)
        ]
        for row in range(len(grid))
    ]
    count = sum(value == 2 for row in result for value in row)
    if count == 0 or count == len(grid) * separator:
        return None
    return result


def translate_eight_down_recolor_two(grid: Grid) -> Grid | None:
    if ({value for row in grid for value in row} - {0}) != {8}:
        return None
    height = len(grid)
    width = len(grid[0])
    points = [
        (row, column)
        for row in range(height)
        for column in range(width)
        if grid[row][column] == 8
    ]
    if not points or any(row + 1 >= height for row, _ in points):
        return None
    result = [[0 for _ in range(width)] for _ in range(height)]
    for row, column in points:
        result[row + 1][column] = 2
    return result


def expand_with_edge_duplicates(grid: Grid) -> Grid | None:
    height = len(grid)
    width = len(grid[0])
    if height < 2 or width < 2 or height + 2 > 30 or width + 2 > 30:
        return None
    result = [[0] + grid[0][:] + [0]]
    for row in grid:
        result.append([row[0]] + row[:] + [row[-1]])
    result.append([0] + grid[-1][:] + [0])
    return result


def drop_one_markers_through_bottom_five_bar(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 1, 5}:
        return None
    if any(value != 5 for value in grid[-1]):
        return None
    markers = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 1
    ]
    if not markers:
        return None
    for row, column in markers:
        if row >= len(grid) - 1:
            return None
        if any(
            grid[next_row][column] != 5
            for next_row in range(row + 1, len(grid))
        ):
            return None
    result = [
        [0 if value == 1 else value for value in row]
        for row in grid
    ]
    for _, column in markers:
        result[-1][column] = 1
    return result


def replace_red_two_with_diagonal_colors(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 2}:
        return None
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 2
    ]
    if len(points) != 1:
        return None
    row, column = points[0]
    result = [[0 for _ in values] for values in grid]
    mapping = {
        (-1, -1): 3,
        (-1, 1): 6,
        (1, -1): 8,
        (1, 1): 7,
    }
    painted = 0
    for (delta_row, delta_column), color in mapping.items():
        target_row = row + delta_row
        target_column = column + delta_column
        if (
            0 <= target_row < len(grid)
            and 0 <= target_column < len(grid[0])
        ):
            result[target_row][target_column] = color
            painted += 1
    return result if painted else None


def select_unique_quadrant(grid: Grid) -> Grid | None:
    height = len(grid)
    width = len(grid[0])
    if height % 2 != 1 or width % 2 != 1 or height < 3 or width < 3:
        return None
    middle_row = height // 2
    middle_column = width // 2
    if (
        any(value != 0 for value in grid[middle_row])
        or any(grid[row][middle_column] != 0 for row in range(height))
    ):
        return None
    panels = [
        [row[:middle_column] for row in grid[:middle_row]],
        [row[middle_column + 1 :] for row in grid[:middle_row]],
        [row[:middle_column] for row in grid[middle_row + 1 :]],
        [
            row[middle_column + 1 :]
            for row in grid[middle_row + 1 :]
        ],
    ]
    signatures = [
        tuple(tuple(row) for row in panel) for panel in panels
    ]
    counts = Counter(signatures)
    unique = [
        index
        for index, signature in enumerate(signatures)
        if counts[signature] == 1
    ]
    repeated = [count for count in counts.values() if count > 1]
    if len(unique) != 1 or repeated != [3]:
        return None
    return [row[:] for row in panels[unique[0]]]


def render_source_color_glyph_five(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row} - {0}
    if len(grid) != 5 or len(grid[0]) != 5 or len(colors) != 1:
        return None
    glyphs = {
        1: [[0, 5, 0], [5, 5, 5], [0, 5, 0]],
        2: [[5, 5, 5], [0, 5, 0], [0, 5, 0]],
        3: [[0, 0, 5], [0, 0, 5], [5, 5, 5]],
    }
    glyph = glyphs.get(next(iter(colors)))
    return None if glyph is None else [row[:] for row in glyph]


def mask_color_five_with_other_color(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row}
    if 0 in colors or 5 not in colors or len(colors) != 2:
        return None
    other = next(color for color in colors if color != 5)
    return [
        [other if value == 5 else 0 for value in row]
        for row in grid
    ]


def extend_vertical_period_by_half_recolor_two(
    grid: Grid,
) -> Grid | None:
    height = len(grid)
    if (
        height % 2
        or {value for row in grid for value in row} != {0, 1}
    ):
        return None
    period = next(
        (
            candidate
            for candidate in range(1, height + 1)
            if all(
                grid[row] == grid[row % candidate]
                for row in range(height)
            )
        ),
        None,
    )
    if period is None:
        return None
    target_height = height + height // 2
    if target_height > 30:
        return None
    return [
        [
            2 if value != 0 else 0
            for value in grid[row % period]
        ]
        for row in range(target_height)
    ]


def recolor_nonsingleton_components_eight(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 3}:
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 3
    }
    components: list[list[tuple[int, int]]] = []
    while remaining:
        start = remaining.pop()
        stack = [start]
        component = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    stack.append(point)
                    component.append(point)
        components.append(component)
    if (
        not any(len(component) == 1 for component in components)
        or not any(len(component) > 1 for component in components)
    ):
        return None
    result = [row[:] for row in grid]
    for component in components:
        if len(component) > 1:
            for row, column in component:
                result[row][column] = 8
    return result


def extract_repeated_half(grid: Grid) -> Grid | None:
    height = len(grid)
    width = len(grid[0])
    candidates: list[Grid] = []
    if width % 2 == 0:
        middle = width // 2
        first = [row[:middle] for row in grid]
        second = [row[middle:] for row in grid]
        if first == second:
            candidates.append(first)
    if height % 2 == 0:
        middle = height // 2
        first = [row[:] for row in grid[:middle]]
        second = [row[:] for row in grid[middle:]]
        if first == second:
            candidates.append(first)
    if (
        not candidates
        or any(candidate != candidates[0] for candidate in candidates[1:])
    ):
        return None
    return [row[:] for row in candidates[0]]


def collapse_uniform_duplicate_lines(
    grid: Grid,
) -> Grid | None:
    candidates: list[Grid] = []
    if all(row == grid[0] for row in grid):
        values = [
            value
            for index, value in enumerate(grid[0])
            if index == 0 or value != grid[0][index - 1]
        ]
        candidates.append([values])
    if all(len(set(row)) == 1 for row in grid):
        values = [
            row[0]
            for index, row in enumerate(grid)
            if index == 0 or row[0] != grid[index - 1][0]
        ]
        candidates.append([[value] for value in values])
    if (
        not candidates
        or any(candidate != candidates[0] for candidate in candidates[1:])
    ):
        return None
    return candidates[0]


def compare_panels_across_separator(
    grid: Grid,
    axis: int,
    mode: str,
    output_color: int,
) -> Grid | None:
    height = len(grid)
    width = len(grid[0])
    size = width if axis == 1 else height
    if size % 2 != 1:
        return None
    separator = size // 2
    line = (
        [grid[row][separator] for row in range(height)]
        if axis == 1
        else grid[separator][:]
    )
    if len(set(line)) != 1 or line[0] == 0:
        return None
    if axis == 1:
        first = [row[:separator] for row in grid]
        second = [row[separator + 1 :] for row in grid]
    else:
        first = [row[:] for row in grid[:separator]]
        second = [row[:] for row in grid[separator + 1 :]]
    first_colors = {
        value for row in first for value in row if value != 0
    }
    second_colors = {
        value for row in second for value in row if value != 0
    }
    if (
        len(first_colors) != 1
        or len(second_colors) != 1
        or line[0] in first_colors
        or line[0] in second_colors
    ):
        return None
    result: Grid = []
    selected = 0
    total = len(first) * len(first[0])
    for row in range(len(first)):
        values: list[int] = []
        for column in range(len(first[0])):
            if mode == "double_background":
                match = (
                    first[row][column] == 0
                    and second[row][column] == 0
                )
            elif mode == "xor_occupancy":
                match = (
                    (first[row][column] != 0)
                    != (second[row][column] != 0)
                )
            elif mode == "union_occupancy":
                match = (
                    first[row][column] != 0
                    or second[row][column] != 0
                )
            else:
                return None
            values.append(output_color if match else 0)
            selected += int(match)
        result.append(values)
    if selected == 0 or selected == total:
        return None
    return result


def mark_double_background_horizontal_separator_eight(
    grid: Grid,
) -> Grid | None:
    return compare_panels_across_separator(
        grid, 1, "double_background", 8
    )


def mark_double_background_horizontal_separator_three(
    grid: Grid,
) -> Grid | None:
    return compare_panels_across_separator(
        grid, 1, "double_background", 3
    )


def mark_double_background_vertical_separator_three(
    grid: Grid,
) -> Grid | None:
    return compare_panels_across_separator(
        grid, 0, "double_background", 3
    )


def xor_vertical_panels_across_separator_three(
    grid: Grid,
) -> Grid | None:
    return compare_panels_across_separator(
        grid, 0, "xor_occupancy", 3
    )


def union_vertical_panels_across_separator_three(
    grid: Grid,
) -> Grid | None:
    return compare_panels_across_separator(
        grid, 0, "union_occupancy", 3
    )


def fill_three_panels_rotate90_rotate180(
    grid: Grid,
) -> Grid | None:
    height = len(grid)
    width = len(grid[0])
    if (width - 2) % 3 != 0:
        return None
    panel_width = (width - 2) // 3
    if panel_width < 1 or height != panel_width:
        return None
    first_separator = panel_width
    second_separator = 2 * panel_width + 1
    first_line = [
        grid[row][first_separator] for row in range(height)
    ]
    second_line = [
        grid[row][second_separator] for row in range(height)
    ]
    if (
        len(set(first_line)) != 1
        or len(set(second_line)) != 1
        or first_line[0] == 0
        or first_line != second_line
    ):
        return None
    first = [row[:panel_width] for row in grid]
    second = [
        row[panel_width + 1 : second_separator] for row in grid
    ]
    third = [row[second_separator + 1 :] for row in grid]
    if (
        any(value != 0 for row in second for value in row)
        or any(value != 0 for row in third for value in row)
    ):
        return None
    rotated_90 = rotate_90(first)
    rotated_180 = rotate_180(first)
    return [
        first[row][:]
        + [first_line[0]]
        + rotated_90[row][:]
        + [first_line[0]]
        + rotated_180[row][:]
        for row in range(height)
    ]


def merge_four_corner_panels_overlap(
    grid: Grid,
) -> Grid | None:
    height = len(grid)
    width = len(grid[0])
    if height % 2 != 1 or (width - 3) % 2 != 0:
        return None
    panel_height = (height - 1) // 2
    panel_width = (width - 3) // 2
    if panel_height < 1 or panel_width < 1:
        return None
    if (
        any(value != 0 for value in grid[panel_height])
        or any(
            grid[row][column] != 0
            for row in range(height)
            for column in range(panel_width, panel_width + 3)
        )
    ):
        return None
    colors = {value for row in grid for value in row} - {0}
    if len(colors) != 1:
        return None
    panels = [
        [row[:panel_width] for row in grid[:panel_height]],
        [row[panel_width + 3 :] for row in grid[:panel_height]],
        [row[:panel_width] for row in grid[panel_height + 1 :]],
        [
            row[panel_width + 3 :]
            for row in grid[panel_height + 1 :]
        ],
    ]
    offsets = ((0, 0), (0, 1), (1, 0), (1, 1))
    result = [
        [0 for _ in range(panel_width + 1)]
        for _ in range(panel_height + 1)
    ]
    for panel, (offset_row, offset_column) in zip(panels, offsets):
        for row in range(panel_height):
            for column in range(panel_width):
                value = panel[row][column]
                target_row = row + offset_row
                target_column = column + offset_column
                if (
                    result[target_row][target_column] != 0
                    and value != 0
                    and result[target_row][target_column] != value
                ):
                    return None
                if value != 0:
                    result[target_row][target_column] = value
    return (
        result
        if any(value != 0 for row in result for value in row)
        else None
    )


def extend_two_full_lines_cross_four(
    grid: Grid,
) -> Grid | None:
    values = {value for row in grid for value in row}
    if values != {0, 2, 8}:
        return None
    twos = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 2
    ]
    eights = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 8
    ]
    if len(twos) != 2 or len(eights) != 2:
        return None
    two_rows = {row for row, _ in twos}
    two_columns = sorted(column for _, column in twos)
    eight_rows = sorted(row for row, _ in eights)
    eight_columns = {column for _, column in eights}
    if (
        len(two_rows) != 1
        or two_columns[1] != two_columns[0] + 1
        or len(eight_columns) != 1
        or eight_rows[1] != eight_rows[0] + 1
    ):
        return None
    target_row = next(iter(two_rows))
    target_column = next(iter(eight_columns))
    result = [[0 for _ in row] for row in grid]
    for column in range(len(result[0])):
        result[target_row][column] = 2
    for row in range(len(result)):
        result[row][target_column] = 8
    result[target_row][target_column] = 4
    return result


def append_both_axis_mirror(grid: Grid) -> Grid | None:
    height = len(grid)
    width = len(grid[0])
    if height * 2 > 30 or width * 2 > 30:
        return None
    top = [row[:] + row[::-1] for row in grid]
    return top + [row[:] for row in top[::-1]]


def rotate_90_counterclockwise(grid: Grid) -> Grid:
    return [list(row) for row in zip(*grid)][::-1]


def tile_four_rotations(grid: Grid) -> Grid | None:
    size = len(grid)
    if size != len(grid[0]) or size * 2 > 30:
        return None
    clockwise = rotate_90(grid)
    counterclockwise = rotate_90_counterclockwise(grid)
    half_turn = rotate_180(grid)
    return [
        grid[row][:] + clockwise[row][:]
        for row in range(size)
    ] + [
        counterclockwise[row][:] + half_turn[row][:]
        for row in range(size)
    ]


def frame_with_vertical_flips_and_horizontal_mirrors(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 3 or len(grid[0]) != 2:
        return None
    middle = [row[::-1] + row[:] for row in grid]
    flipped = [row[:] for row in middle[::-1]]
    return flipped + [row[:] for row in middle] + [
        row[:] for row in flipped
    ]


def stamp_grid_down_right_diagonal(
    grid: Grid,
) -> Grid | None:
    size = len(grid)
    if size != len(grid[0]) or size * 2 > 30:
        return None
    result = [
        [0 for _ in range(size * 2)]
        for _ in range(size * 2)
    ]
    for offset in range(size * 2):
        span = min(size, size * 2 - offset)
        for row in range(span):
            for column in range(span):
                value = grid[row][column]
                target_row = offset + row
                target_column = offset + column
                if (
                    result[target_row][target_column] != 0
                    and value != 0
                    and result[target_row][target_column] != value
                ):
                    return None
                if value != 0:
                    result[target_row][target_column] = value
    return result


def select_unique_binary_shape_tile(
    grid: Grid,
) -> Grid | None:
    height = len(grid)
    width = len(grid[0])
    tiles: list[Grid]
    if height == 3 and width >= 9 and width % 3 == 0:
        tiles = [
            [row[column : column + 3] for row in grid]
            for column in range(0, width, 3)
        ]
    elif width == 3 and height >= 9 and height % 3 == 0:
        tiles = [
            [row[:] for row in grid[top : top + 3]]
            for top in range(0, height, 3)
        ]
    else:
        return None
    colors: list[int] = []
    signatures: list[tuple[tuple[int, ...], ...]] = []
    for tile in tiles:
        tile_colors = {
            value for row in tile for value in row if value != 0
        }
        if len(tile_colors) != 1:
            return None
        colors.append(next(iter(tile_colors)))
        signatures.append(
            tuple(
                tuple(int(value != 0) for value in row)
                for row in tile
            )
        )
    if len(set(colors)) != len(colors):
        return None
    counts = Counter(signatures)
    if (
        len(counts) != 2
        or sorted(counts.values()) != [1, len(tiles) - 1]
    ):
        return None
    unique_signature = next(
        signature for signature, count in counts.items() if count == 1
    )
    return [
        row[:] for row in tiles[signatures.index(unique_signature)]
    ]


def replace_object_with_bottom_left_marker_color(
    grid: Grid,
) -> Grid | None:
    colors = {
        value for row in grid for value in row if value != 0
    }
    if len(colors) != 2:
        return None
    marker = grid[-1][0]
    if (
        marker == 0
        or sum(value == marker for row in grid for value in row) != 1
    ):
        return None
    object_colors = colors - {marker}
    if len(object_colors) != 1:
        return None
    object_color = next(iter(object_colors))
    if sum(
        value == object_color for row in grid for value in row
    ) < 2:
        return None
    return [
        [marker if value == object_color else 0 for value in row]
        for row in grid
    ]


def complete_l_tromino_bounding_boxes_one(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 8}:
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 8
    }
    components: list[list[tuple[int, int]]] = []
    while remaining:
        start = remaining.pop()
        stack = [start]
        component = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    stack.append(point)
                    component.append(point)
        components.append(component)
    if not components:
        return None
    result = [row[:] for row in grid]
    for component in components:
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        if (
            len(component) != 3
            or bottom - top != 1
            or right - left != 1
        ):
            return None
        missing = [
            (row, column)
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
            if grid[row][column] == 0
        ]
        if len(missing) != 1:
            return None
        row, column = missing[0]
        result[row][column] = 1
    return result


def project_distinct_two_by_two_to_opposite_corners(
    grid: Grid,
) -> Grid | None:
    occupied = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    ]
    if len(occupied) != 4:
        return None
    top = min(row for row, _ in occupied)
    bottom = max(row for row, _ in occupied)
    left = min(column for _, column in occupied)
    right = max(column for _, column in occupied)
    if bottom - top != 1 or right - left != 1:
        return None
    block = [
        [grid[row][column] for column in range(left, right + 1)]
        for row in range(top, bottom + 1)
    ]
    if (
        any(value == 0 for row in block for value in row)
        or len({value for row in block for value in row}) != 4
    ):
        return None
    result = [row[:] for row in grid]
    destinations = (
        (block[0][0], range(bottom + 1, bottom + 3), range(right + 1, right + 3)),
        (block[0][1], range(bottom + 1, bottom + 3), range(left - 2, left)),
        (block[1][0], range(top - 2, top), range(right + 1, right + 3)),
        (block[1][1], range(top - 2, top), range(left - 2, left)),
    )
    painted = 0
    for color, rows, columns in destinations:
        for row in rows:
            for column in columns:
                if 0 <= row < len(grid) and 0 <= column < len(grid[0]):
                    result[row][column] = color
                    painted += 1
    return result if painted else None


def fill_diagonal_residue_period_three(
    grid: Grid,
) -> Grid | None:
    observed: dict[int, set[int]] = {0: set(), 1: set(), 2: set()}
    for row, values in enumerate(grid):
        for column, value in enumerate(values):
            if value != 0:
                observed[(row + column) % 3].add(value)
    if any(len(values) != 1 for values in observed.values()):
        return None
    mapping = {
        residue: next(iter(values))
        for residue, values in observed.items()
    }
    if len(set(mapping.values())) != 3:
        return None
    return [
        [
            mapping[(row + column) % 3]
            for column in range(len(grid[0]))
        ]
        for row in range(len(grid))
    ]


def bounce_singleton_one_upward(
    grid: Grid,
    background: int,
) -> Grid | None:
    height = len(grid)
    width = len(grid[0])
    if (
        height < 2
        or width < 2
        or sum(value == 1 for row in grid for value in row) != 1
        or any(value not in (0, 1) for row in grid for value in row)
        or grid[-1][0] != 1
    ):
        return None
    result = [[background for _ in row] for row in grid]
    period = 2 * (width - 1)
    for row in range(height - 1, -1, -1):
        offset = (height - 1 - row) % period
        column = min(offset, period - offset)
        result[row][column] = 1
    return result


def bounce_singleton_one_upward_zero_background(
    grid: Grid,
) -> Grid | None:
    return bounce_singleton_one_upward(grid, 0)


def bounce_singleton_one_upward_eight_background(
    grid: Grid,
) -> Grid | None:
    return bounce_singleton_one_upward(grid, 8)


def render_two_by_two_component_count_five_spots(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 2}:
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 2
    }
    components: list[list[tuple[int, int]]] = []
    while remaining:
        start = remaining.pop()
        stack = [start]
        component = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    stack.append(point)
                    component.append(point)
        components.append(component)
    if not 1 <= len(components) <= 5:
        return None
    for component in components:
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        if (
            len(component) != 4
            or max(rows) - min(rows) != 1
            or max(columns) - min(columns) != 1
        ):
            return None
    spots = ((0, 0), (0, 2), (1, 1), (2, 0), (2, 2))
    result = [[0, 0, 0] for _ in range(3)]
    for row, column in spots[: len(components)]:
        result[row][column] = 1
    return result


def keep_center_column(grid: Grid) -> Grid | None:
    width = len(grid[0])
    if width < 3 or width % 2 != 1:
        return None
    middle = width // 2
    if not any(row[middle] != 0 for row in grid):
        return None
    if not any(
        value != 0
        for row in grid
        for column, value in enumerate(row)
        if column != middle
    ):
        return None
    return [
        [value if column == middle else 0 for column, value in enumerate(row)]
        for row in grid
    ]


def crop_top_left_two_by_two(grid: Grid) -> Grid | None:
    if len(grid) < 4 or len(grid[0]) < 4:
        return None
    return [row[:2] for row in grid[:2]]


def grow_left_prefix_run_triangle(
    grid: Grid,
) -> Grid | None:
    width = len(grid[0])
    if len(grid) != 1 or width < 4 or width % 2:
        return None
    colors = {value for value in grid[0] if value != 0}
    if len(colors) != 1:
        return None
    color = next(iter(colors))
    occupied = [
        column for column, value in enumerate(grid[0]) if value == color
    ]
    if not occupied or occupied != list(range(len(occupied))):
        return None
    height = width // 2
    if len(occupied) + height - 1 > width:
        return None
    return [
        [color if column < len(occupied) + row else 0 for column in range(width)]
        for row in range(height)
    ]


def overlay_three_panels_left_priority(
    grid: Grid,
) -> Grid | None:
    height = len(grid)
    width = len(grid[0])
    if width != 3 * height + 2:
        return None
    separators = height, 2 * height + 1
    first_line = [row[separators[0]] for row in grid]
    second_line = [row[separators[1]] for row in grid]
    if (
        len(set(first_line)) != 1
        or first_line != second_line
        or first_line[0] == 0
    ):
        return None
    panels = (
        [row[:height] for row in grid],
        [row[height + 1 : 2 * height + 1] for row in grid],
        [row[2 * height + 2 :] for row in grid],
    )
    panel_colors = [
        {value for row in panel for value in row if value != 0}
        for panel in panels
    ]
    if (
        any(len(colors) != 1 for colors in panel_colors)
        or len({next(iter(colors)) for colors in panel_colors}) != 3
        or first_line[0] in set().union(*panel_colors)
    ):
        return None
    result = [[0 for _ in range(height)] for _ in range(height)]
    for panel in panels[::-1]:
        for row in range(height):
            for column in range(height):
                if panel[row][column] != 0:
                    result[row][column] = panel[row][column]
    return result


def overlay_four_quadrants_fixed_priority(
    grid: Grid,
) -> Grid | None:
    height = len(grid)
    width = len(grid[0])
    if height % 2 or width % 2 or height != width:
        return None
    half = height // 2
    quadrants = (
        [row[:half] for row in grid[:half]],
        [row[half:] for row in grid[:half]],
        [row[:half] for row in grid[half:]],
        [row[half:] for row in grid[half:]],
    )
    colors = [
        {value for row in quadrant for value in row if value != 0}
        for quadrant in quadrants
    ]
    if (
        any(len(values) != 1 for values in colors)
        or len({next(iter(values)) for values in colors}) != 4
    ):
        return None
    result = [[0 for _ in range(half)] for _ in range(half)]
    for index in (0, 3, 2, 1):
        quadrant = quadrants[index]
        for row in range(half):
            for column in range(half):
                if quadrant[row][column] != 0:
                    result[row][column] = quadrant[row][column]
    return result


def tile_twice_mark_diagonal_neighbors_eight(
    grid: Grid,
) -> Grid | None:
    height = len(grid)
    width = len(grid[0])
    if height * 2 > 30 or width * 2 > 30:
        return None
    colors = {
        value for row in grid for value in row if value != 0
    }
    if len(colors) != 1 or 8 in colors:
        return None
    tiled = [
        grid[row % height][column % width]
        for row in range(height * 2)
        for column in range(width * 2)
    ]
    tiled_grid = [
        tiled[row * width * 2 : (row + 1) * width * 2]
        for row in range(height * 2)
    ]
    result = [row[:] for row in tiled_grid]
    for row in range(height * 2):
        for column in range(width * 2):
            if tiled_grid[row][column] == 0:
                continue
            for delta_row, delta_column in (
                (-1, -1),
                (-1, 1),
                (1, -1),
                (1, 1),
            ):
                target_row = row + delta_row
                target_column = column + delta_column
                if (
                    0 <= target_row < height * 2
                    and 0 <= target_column < width * 2
                    and tiled_grid[target_row][target_column] == 0
                ):
                    result[target_row][target_column] = 8
    return result


def extract_missing_periodic_rectangle(
    grid: Grid,
) -> Grid | None:
    height = len(grid)
    width = len(grid[0])
    missing = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 0
    ]
    if not missing:
        return None
    top = min(row for row, _ in missing)
    bottom = max(row for row, _ in missing)
    left = min(column for _, column in missing)
    right = max(column for _, column in missing)
    if len(missing) != (bottom - top + 1) * (right - left + 1):
        return None
    if not (
        top == 0
        or left == 0
        or bottom == height - 1
        or right == width - 1
    ):
        return None
    candidates: list[
        tuple[int, int, int, int, dict[tuple[int, int], int]]
    ] = []
    for row_period in range(1, height + 1):
        for column_period in range(1, width + 1):
            mapping: dict[tuple[int, int], int] = {}
            consistent = True
            for row, values in enumerate(grid):
                for column, value in enumerate(values):
                    if value == 0:
                        continue
                    key = row % row_period, column % column_period
                    if key in mapping and mapping[key] != value:
                        consistent = False
                        break
                    mapping[key] = value
                if not consistent:
                    break
            if not consistent or not all(
                (row % row_period, column % column_period) in mapping
                for row, column in missing
            ):
                continue
            candidates.append(
                (
                    row_period * column_period,
                    row_period + column_period,
                    row_period,
                    column_period,
                    mapping,
                )
            )
    if not candidates:
        return None
    _, _, row_period, column_period, mapping = min(
        candidates,
        key=lambda item: item[:4],
    )
    return [
        [
            mapping[(row % row_period, column % column_period)]
            for column in range(left, right + 1)
        ]
        for row in range(top, bottom + 1)
    ]


def classify_eight_path_between_two_red_blocks(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 2, 8}:
        return None

    def components(color: int) -> list[set[tuple[int, int]]]:
        remaining = {
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        }
        found: list[set[tuple[int, int]]] = []
        while remaining:
            start = remaining.pop()
            component = {start}
            stack = [start]
            while stack:
                row, column = stack.pop()
                for point in (
                    (row - 1, column),
                    (row + 1, column),
                    (row, column - 1),
                    (row, column + 1),
                ):
                    if point in remaining:
                        remaining.remove(point)
                        component.add(point)
                        stack.append(point)
            found.append(component)
        return found

    blocks = components(2)
    if len(blocks) != 2:
        return None
    for block in blocks:
        rows = [row for row, _ in block]
        columns = [column for _, column in block]
        if (
            len(block) != 4
            or max(rows) - min(rows) != 1
            or max(columns) - min(columns) != 1
        ):
            return None

    def neighbors(block: set[tuple[int, int]]) -> set[tuple[int, int]]:
        return {
            point
            for row, column in block
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            )
        }

    boundaries = [neighbors(block) for block in blocks]
    connected = any(
        bool(component & boundaries[0])
        and bool(component & boundaries[1])
        for component in components(8)
    )
    return [[8 if connected else 0]]


def connect_edge_color_pairs_with_five(
    grid: Grid,
) -> Grid | None:
    width = len(grid[0])
    if width < 5 or width % 2 != 1:
        return None
    active_rows = []
    for row, values in enumerate(grid):
        if all(value == 0 for value in values):
            continue
        if (
            values[0] == 0
            or values[-1] == 0
            or values[0] == values[-1]
            or values[0] == 5
            or values[-1] == 5
            or any(value != 0 for value in values[1:-1])
        ):
            return None
        active_rows.append(row)
    if not active_rows:
        return None
    middle = width // 2
    result = [[0 for _ in row] for row in grid]
    for row in active_rows:
        result[row][:middle] = [grid[row][0]] * middle
        result[row][middle] = 5
        result[row][middle + 1 :] = [grid[row][-1]] * middle
    return result


def ray_each_marker_right_then_down(
    grid: Grid,
) -> Grid | None:
    occupied = [
        (row, column, value)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    ]
    if (
        not occupied
        or len({row for row, _, _ in occupied}) != len(occupied)
        or len({color for _, _, color in occupied}) != len(occupied)
    ):
        return None
    result = [[0 for _ in row] for row in grid]
    width = len(grid[0])
    for row, column, color in sorted(occupied):
        for target_column in range(column, width):
            result[row][target_column] = color
        for target_row in range(row, len(grid)):
            result[target_row][-1] = color
    return result


def repeat_header_colors_below_five_bar(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) < 4
        or any(value == 0 for value in grid[0])
        or any(value == 5 for value in grid[0])
        or any(value != 5 for value in grid[1])
        or any(value != 0 for row in grid[2:] for value in row)
    ):
        return None
    result = [row[:] for row in grid]
    for row in range(2, len(grid)):
        result[row] = [
            grid[0][(row - 2) % len(grid[0])]
            for _ in grid[0]
        ]
    return result


def repeat_marker_row_and_diagonal_neighbors(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) < 2
        or any(value != 0 for row in grid[1:] for value in row)
    ):
        return None
    markers = [
        (column, value)
        for column, value in enumerate(grid[0])
        if value != 0
    ]
    if not markers:
        return None
    diagonal = [0 for _ in grid[0]]
    for column, color in markers:
        for target in (column - 1, column + 1):
            if not 0 <= target < len(diagonal):
                continue
            if diagonal[target] not in (0, color):
                return None
            diagonal[target] = color
    return [
        grid[0][:] if row % 2 == 0 else diagonal[:]
        for row in range(len(grid))
    ]


def cycle_three_concentric_ring_colors(
    grid: Grid,
) -> Grid | None:
    size = len(grid)
    if size != len(grid[0]) or size < 6:
        return None
    rings = []
    for layer in range((size + 1) // 2):
        values = {
            grid[row][column]
            for row in range(layer, size - layer)
            for column in range(layer, size - layer)
            if (
                row in (layer, size - layer - 1)
                or column in (layer, size - layer - 1)
            )
        }
        if len(values) != 1:
            return None
        rings.append(next(iter(values)))
    colors: list[int] = []
    for color in rings:
        if color not in colors:
            colors.append(color)
    if (
        len(colors) != 3
        or any(
            color != colors[index % 3]
            for index, color in enumerate(rings)
        )
    ):
        return None
    mapping = {
        colors[0]: colors[2],
        colors[1]: colors[0],
        colors[2]: colors[1],
    }
    return [[mapping[value] for value in row] for row in grid]


def duplicate_eight_shape_opposite_four_marker(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 4, 8}:
        return None
    eights = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 8
    ]
    fours = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 4
    ]
    if not eights or not fours:
        return None
    eight_top = min(row for row, _ in eights)
    eight_bottom = max(row for row, _ in eights)
    eight_left = min(column for _, column in eights)
    eight_right = max(column for _, column in eights)
    four_top = min(row for row, _ in fours)
    four_left = min(column for _, column in fours)
    four_right = max(column for _, column in fours)
    if eight_bottom >= four_top:
        return None
    top_four_columns = [
        column for row, column in fours if row == four_top
    ]
    if len(top_four_columns) != 1:
        return None
    center = (four_left + four_right) / 2
    direction = -1 if top_four_columns[0] < center else 1
    shape = [
        row[eight_left : eight_right + 1]
        for row in grid[eight_top : eight_bottom + 1]
    ]
    flipped = [row[::-1] for row in shape]
    width = len(shape[0])
    target_left = (
        eight_left - width if direction < 0 else eight_right + 1
    )
    if target_left < 0 or target_left + width > len(grid[0]):
        return None
    result = [row[:] for row in grid]
    for row in range(len(flipped)):
        for column in range(width):
            target_row = eight_top + row
            target_column = target_left + column
            value = flipped[row][column]
            if result[target_row][target_column] != 0 and value != 0:
                return None
            if value != 0:
                result[target_row][target_column] = value
    return result


def connect_matching_panel_feature_markers(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 8 or len(grid[0]) != 8:
        return None
    if (
        any(value != 0 for row in (2, 5) for value in grid[row])
        or any(grid[row][column] != 0 for row in range(8) for column in (2, 5))
    ):
        return None
    result = [row[:] for row in grid]
    markers: dict[
        tuple[int, int, int], set[tuple[int, int]]
    ] = {}
    for tile_row in range(3):
        for tile_column in range(3):
            for internal_row in range(2):
                for internal_column in range(2):
                    row = tile_row * 3 + internal_row
                    column = tile_column * 3 + internal_column
                    value = grid[row][column]
                    if value == 0:
                        return None
                    if value != 1:
                        markers.setdefault(
                            (internal_row, internal_column, value),
                            set(),
                        ).add((tile_row, tile_column))
    if not markers:
        return None
    for (internal_row, internal_column, value), points in markers.items():
        additions = set(points)
        for tile_row in range(3):
            columns = [
                column for row, column in points if row == tile_row
            ]
            if len(columns) >= 2:
                additions.update(
                    (tile_row, column)
                    for column in range(min(columns), max(columns) + 1)
                )
        for tile_column in range(3):
            rows = [
                row for row, column in points if column == tile_column
            ]
            if len(rows) >= 2:
                additions.update(
                    (row, tile_column)
                    for row in range(min(rows), max(rows) + 1)
                )
        for tile_row, tile_column in additions:
            row = tile_row * 3 + internal_row
            column = tile_column * 3 + internal_column
            if result[row][column] not in (1, value):
                return None
            result[row][column] = value
    return result


def recolor_mixed_red_green_components(
    grid: Grid,
) -> Grid | None:
    if not {
        value for row in grid for value in row
    }.issubset({0, 2, 3, 5}):
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value in (2, 3)
    }
    if not remaining:
        return None
    result = [row[:] for row in grid]
    changed = False
    while remaining:
        start = remaining.pop()
        component = [start]
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.append(point)
                    stack.append(point)
        colors = {grid[row][column] for row, column in component}
        if colors != {2, 3}:
            continue
        for row, column in component:
            result[row][column] = 8 if grid[row][column] == 3 else 0
            changed = True
    return result if changed else None


def extract_three_repeated_horizontal_panels(
    grid: Grid,
) -> Grid | None:
    width = len(grid[0])
    if width % 3:
        return None
    panel_width = width // 3
    if panel_width < 1:
        return None
    return [row[:panel_width] for row in grid]


def crop_top_right_three_by_three(
    grid: Grid,
) -> Grid | None:
    if len(grid) < 5 or len(grid[0]) < 5:
        return None
    return [row[-3:] for row in grid[:3]]


def crop_nonzero_bbox_top_left_three_by_three(
    grid: Grid,
) -> Grid | None:
    occupied = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    ]
    if not occupied:
        return None
    top = min(row for row, _ in occupied)
    bottom = max(row for row, _ in occupied)
    left = min(column for _, column in occupied)
    right = max(column for _, column in occupied)
    if bottom - top + 1 < 3 or right - left + 1 < 3:
        return None
    return [row[left : left + 3] for row in grid[top : top + 3]]


def crop_unique_horizontally_symmetric_component(
    grid: Grid,
) -> Grid | None:
    candidates: list[Grid] = []
    colors = sorted(
        {value for row in grid for value in row if value != 0}
    )
    for color in colors:
        points = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ]
        top = min(row for row, _ in points)
        bottom = max(row for row, _ in points)
        left = min(column for _, column in points)
        right = max(column for _, column in points)
        cropped = [
            row[left : right + 1]
            for row in grid[top : bottom + 1]
        ]
        if cropped == [row[::-1] for row in cropped]:
            candidates.append(cropped)
    if len(candidates) != 1:
        return None
    return [row[:] for row in candidates[0]]


def render_largest_hollow_rectangle_color_two_by_two(
    grid: Grid,
) -> Grid | None:
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    }
    rectangles: list[tuple[int, int]] = []
    while remaining:
        start = remaining.pop()
        color = grid[start[0]][start[1]]
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if (
                    point in remaining
                    and grid[point[0]][point[1]] == color
                ):
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        border = {
            (row, column)
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
            if row in (top, bottom) or column in (left, right)
        }
        if component != border:
            return None
        rectangles.append(
            ((bottom - top + 1) * (right - left + 1), color)
        )
    if len(rectangles) != 2:
        return None
    maximum = max(area for area, _ in rectangles)
    colors = [color for area, color in rectangles if area == maximum]
    if len(colors) != 1:
        return None
    return [[colors[0], colors[0]], [colors[0], colors[0]]]


def count_solid_two_by_two_one_components_five_bar(
    grid: Grid,
) -> Grid | None:
    if not {
        value for row in grid for value in row
    }.issubset({0, 1, 2}):
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 1
    }
    components: list[set[tuple[int, int]]] = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        components.append(component)
    blocks = 0
    for component in components:
        if len(component) == 1:
            continue
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        if (
            len(component) != 4
            or max(rows) - min(rows) != 1
            or max(columns) - min(columns) != 1
        ):
            return None
        blocks += 1
    if not 1 <= blocks <= 5:
        return None
    return [[1] * blocks + [0] * (5 - blocks)]


def select_dense_three_by_three_with_most_ones(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) < 3
        or len(grid[0]) < 3
        or not {
            value for row in grid for value in row
        }.issubset({0, 1, 8})
    ):
        return None
    candidates: list[tuple[int, int, int, Grid]] = []
    for row in range(len(grid) - 2):
        for column in range(len(grid[0]) - 2):
            window = [
                values[column : column + 3]
                for values in grid[row : row + 3]
            ]
            if all(value != 0 for values in window for value in values):
                candidates.append(
                    (
                        sum(
                            value == 1
                            for values in window
                            for value in values
                        ),
                        row,
                        column,
                        window,
                    )
                )
    if not candidates:
        return None
    maximum = max(count for count, _, _, _ in candidates)
    winners = [
        window for count, _, _, window in candidates if count == maximum
    ]
    if len(winners) != 1:
        return None
    return [row[:] for row in winners[0]]


def render_empty_rows_above_eight_in_five_container(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 5, 8}:
        return None
    fives = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    ]
    eights = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 8
    ]
    top = min(row for row, _ in fives)
    bottom = max(row for row, _ in fives)
    left = min(column for _, column in fives)
    right = max(column for _, column in fives)
    if bottom - top < 2 or right - left < 2:
        return None
    expected_fives = {
        (row, column)
        for row in range(top, bottom + 1)
        for column in range(left, right + 1)
        if column in (left, right) or row == bottom
    }
    if set(fives) != expected_fives:
        return None
    eight_top = min(row for row, _ in eights)
    eight_bottom = max(row for row, _ in eights)
    eight_left = min(column for _, column in eights)
    eight_right = max(column for _, column in eights)
    if (
        eight_left != left + 1
        or eight_right != right - 1
        or eight_bottom != bottom - 1
    ):
        return None
    expected_eights = {
        (row, column)
        for row in range(eight_top, eight_bottom + 1)
        for column in range(eight_left, eight_right + 1)
    }
    if set(eights) != expected_eights:
        return None
    count = eight_top - top
    if not 1 <= count <= 9:
        return None
    path = (
        (0, 0),
        (0, 1),
        (0, 2),
        (1, 2),
        (1, 1),
        (1, 0),
        (2, 0),
        (2, 1),
        (2, 2),
    )
    result = [[0, 0, 0] for _ in range(3)]
    for row, column in path[:count]:
        result[row][column] = 8
    return result


def overlay_four_panels_across_one_cross(
    grid: Grid,
) -> Grid | None:
    height = len(grid)
    width = len(grid[0])
    if height % 2 != 1 or width % 2 != 1:
        return None
    middle_row = height // 2
    middle_column = width // 2
    if (
        height != width
        or any(value != 1 for value in grid[middle_row])
        or any(grid[row][middle_column] != 1 for row in range(height))
    ):
        return None
    panels = (
        [row[:middle_column] for row in grid[:middle_row]],
        [row[middle_column + 1 :] for row in grid[:middle_row]],
        [row[:middle_column] for row in grid[middle_row + 1 :]],
        [row[middle_column + 1 :] for row in grid[middle_row + 1 :]],
    )
    colors = [
        {value for row in panel for value in row if value != 0}
        for panel in panels
    ]
    if (
        any(len(values) != 1 for values in colors)
        or len({next(iter(values)) for values in colors}) != 4
        or any(1 in values for values in colors)
    ):
        return None
    result = [
        [0 for _ in range(middle_column)]
        for _ in range(middle_row)
    ]
    for panel in panels[::-1]:
        for row in range(middle_row):
            for column in range(middle_column):
                if panel[row][column] != 0:
                    result[row][column] = panel[row][column]
    return result


def recolor_six_by_six_pattern_from_two_by_two_key(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 9 or len(grid[0]) != 9:
        return None
    separator_rows = [
        row for row in range(9) if all(value == 8 for value in grid[row])
    ]
    separator_columns = [
        column
        for column in range(9)
        if all(grid[row][column] == 8 for row in range(9))
    ]
    if len(separator_rows) != 1 or len(separator_columns) != 1:
        return None
    separator_row = separator_rows[0]
    separator_column = separator_columns[0]
    if separator_row not in (2, 6) or separator_column not in (2, 6):
        return None
    row_ranges = (
        (0, separator_row),
        (separator_row + 1, 9),
    )
    column_ranges = (
        (0, separator_column),
        (separator_column + 1, 9),
    )
    quadrants = [
        [
            row[column_start:column_end]
            for row in grid[row_start:row_end]
        ]
        for row_start, row_end in row_ranges
        for column_start, column_end in column_ranges
    ]
    key_candidates = [
        quadrant
        for quadrant in quadrants
        if len(quadrant) == 2
        and len(quadrant[0]) == 2
        and all(value != 0 for row in quadrant for value in row)
    ]
    pattern_candidates = [
        quadrant
        for quadrant in quadrants
        if len(quadrant) == 6
        and len(quadrant[0]) == 6
        and {
            value for row in quadrant for value in row
        }.issubset({0, 3})
        and any(value == 3 for row in quadrant for value in row)
    ]
    if len(key_candidates) != 1 or len(pattern_candidates) != 1:
        return None
    key = key_candidates[0]
    pattern = pattern_candidates[0]
    result = [[0 for _ in range(6)] for _ in range(6)]
    for key_row in range(2):
        for key_column in range(2):
            for row in range(3):
                for column in range(3):
                    source_row = key_row * 3 + row
                    source_column = key_column * 3 + column
                    if pattern[source_row][source_column] == 3:
                        result[source_row][source_column] = (
                            key[key_row][key_column]
                        )
    return result


def stamp_pattern_at_mask(
    pattern: Grid,
    mask: list[list[bool]],
) -> Grid:
    size = len(pattern)
    result = [
        [0 for _ in range(size * len(mask[0]))]
        for _ in range(size * len(mask))
    ]
    for mask_row, values in enumerate(mask):
        for mask_column, selected in enumerate(values):
            if not selected:
                continue
            for row in range(size):
                for column in range(size):
                    result[mask_row * size + row][
                        mask_column * size + column
                    ] = pattern[row][column]
    return result


def stamp_cropped_three_by_three_at_its_nonzero_mask(
    grid: Grid,
) -> Grid | None:
    occupied = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    ]
    if not occupied:
        return None
    top = min(row for row, _ in occupied)
    bottom = max(row for row, _ in occupied)
    left = min(column for _, column in occupied)
    right = max(column for _, column in occupied)
    if bottom - top != 2 or right - left != 2:
        return None
    pattern = [row[left : right + 1] for row in grid[top : bottom + 1]]
    colors = {
        value for row in pattern for value in row if value != 0
    }
    if len(colors) != 1:
        return None
    mask = [[value != 0 for value in row] for row in pattern]
    return stamp_pattern_at_mask(pattern, mask)


def stamp_three_by_three_at_its_nonzero_mask(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 3 or len(grid[0]) != 3:
        return None
    colors = {value for row in grid for value in row if value != 0}
    if len(colors) != 1:
        return None
    mask = [[value != 0 for value in row] for row in grid]
    return stamp_pattern_at_mask(grid, mask)


def stamp_three_by_three_at_modal_color_cells(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 3
        or len(grid[0]) != 3
        or any(value == 0 for row in grid for value in row)
    ):
        return None
    counts = Counter(value for row in grid for value in row)
    maximum = max(counts.values())
    modes = [color for color, count in counts.items() if count == maximum]
    if len(modes) != 1 or maximum < 2:
        return None
    mask = [[value == modes[0] for value in row] for row in grid]
    return stamp_pattern_at_mask(grid, mask)


def recolor_vertical_bars_by_descending_length(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 5}:
        return None
    bars: list[tuple[int, int, list[int]]] = []
    for column in range(len(grid[0])):
        rows = [
            row for row in range(len(grid)) if grid[row][column] == 5
        ]
        if not rows:
            continue
        if rows != list(range(rows[0], rows[-1] + 1)):
            return None
        bars.append((len(rows), column, rows))
    if (
        not 1 <= len(bars) <= 9
        or len({length for length, _, _ in bars}) != len(bars)
    ):
        return None
    result = [[0 for _ in row] for row in grid]
    for rank, (_, column, rows) in enumerate(
        sorted(bars, reverse=True),
        start=1,
    ):
        for row in rows:
            result[row][column] = rank
    return result


def mark_two_diagonals_four_and_one_cardinals_seven(
    grid: Grid,
) -> Grid | None:
    values = {value for row in grid for value in row}
    if 1 not in values or 2 not in values or 4 in values or 7 in values:
        return None
    result = [row[:] for row in grid]
    additions: list[tuple[int, int, int]] = []
    for row, values in enumerate(grid):
        for column, value in enumerate(values):
            if value == 2:
                for delta_row, delta_column in (
                    (-1, -1),
                    (-1, 1),
                    (1, -1),
                    (1, 1),
                ):
                    additions.append(
                        (row + delta_row, column + delta_column, 4)
                    )
            elif value == 1:
                for delta_row, delta_column in (
                    (-1, 0),
                    (1, 0),
                    (0, -1),
                    (0, 1),
                ):
                    additions.append(
                        (row + delta_row, column + delta_column, 7)
                    )
    for row, column, color in additions:
        if not (0 <= row < len(grid) and 0 <= column < len(grid[0])):
            continue
        if result[row][column] not in (0, color):
            return None
        result[row][column] = color
    return result


def fill_two_by_two_and_stamp_from_twos_diagonally(
    grid: Grid,
) -> Grid | None:
    occupied = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    ]
    if len(occupied) != 4:
        return None
    top = min(row for row, _ in occupied)
    bottom = max(row for row, _ in occupied)
    left = min(column for _, column in occupied)
    right = max(column for _, column in occupied)
    if bottom - top != 1 or right - left != 1:
        return None
    block = [row[left : right + 1] for row in grid[top : bottom + 1]]
    colors = {value for row in block for value in row}
    if 2 not in colors or len(colors) != 2:
        return None
    paint = next(color for color in colors if color != 2)
    guides = [
        (row, column)
        for row in range(2)
        for column in range(2)
        if block[row][column] == 2
    ]
    result = [[0 for _ in row] for row in grid]
    for row in range(top, bottom + 1):
        for column in range(left, right + 1):
            result[row][column] = paint
    for guide_row, guide_column in guides:
        delta_row = -1 if guide_row == 0 else 1
        delta_column = -1 if guide_column == 0 else 1
        for offset in range(1, max(len(grid), len(grid[0])) + 2):
            stamp_top = top + delta_row * offset
            stamp_left = left + delta_column * offset
            painted = False
            for row in range(stamp_top, stamp_top + 2):
                for column in range(stamp_left, stamp_left + 2):
                    if (
                        0 <= row < len(grid)
                        and 0 <= column < len(grid[0])
                    ):
                        result[row][column] = paint
                        painted = True
            if not painted:
                break
    return result


def expand_five_markers_three_by_three_center_five(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 5}:
        return None
    markers = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    ]
    result = [[0 for _ in row] for row in grid]
    for marker_row, marker_column in markers:
        for row in range(marker_row - 1, marker_row + 2):
            for column in range(marker_column - 1, marker_column + 2):
                if not (
                    0 <= row < len(grid)
                    and 0 <= column < len(grid[0])
                ):
                    continue
                value = (
                    5
                    if (row, column) == (marker_row, marker_column)
                    else 1
                )
                if result[row][column] not in (0, value):
                    return None
                result[row][column] = value
    return result


def expand_five_markers_three_by_three_one(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 5}:
        return None
    result = [[0 for _ in row] for row in grid]
    for marker_row, values in enumerate(grid):
        for marker_column, value in enumerate(values):
            if value != 5:
                continue
            for row in range(marker_row - 1, marker_row + 2):
                for column in range(marker_column - 1, marker_column + 2):
                    if (
                        0 <= row < len(grid)
                        and 0 <= column < len(grid[0])
                    ):
                        result[row][column] = 1
    return result


def replace_five_markers_with_diagonal_five_cardinal_one(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 5}:
        return None
    result = [[0 for _ in row] for row in grid]
    for marker_row, values in enumerate(grid):
        for marker_column, value in enumerate(values):
            if value != 5:
                continue
            for delta_row, delta_column, color in (
                (-1, -1, 5),
                (-1, 0, 1),
                (-1, 1, 5),
                (0, -1, 1),
                (0, 1, 1),
                (1, -1, 5),
                (1, 0, 1),
                (1, 1, 5),
            ):
                row = marker_row + delta_row
                column = marker_column + delta_column
                if not (
                    0 <= row < len(grid)
                    and 0 <= column < len(grid[0])
                ):
                    continue
                if result[row][column] not in (0, color):
                    return None
                result[row][column] = color
    return result


def fill_eight_connected_four_component_bboxes_seven(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 4}:
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 4
    }
    components: list[set[tuple[int, int]]] = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for delta_row in (-1, 0, 1):
                for delta_column in (-1, 0, 1):
                    if delta_row == delta_column == 0:
                        continue
                    point = row + delta_row, column + delta_column
                    if point in remaining:
                        remaining.remove(point)
                        component.add(point)
                        stack.append(point)
        components.append(component)
    result = [row[:] for row in grid]
    for component in components:
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        for row in range(min(rows), max(rows) + 1):
            for column in range(min(columns), max(columns) + 1):
                if result[row][column] == 0:
                    result[row][column] = 7
    return result


def draw_two_singleton_crosses_intersections_two(
    grid: Grid,
) -> Grid | None:
    occupied = [
        (row, column, value)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    ]
    if (
        len(occupied) != 2
        or occupied[0][2] == occupied[1][2]
        or 2 in (occupied[0][2], occupied[1][2])
    ):
        return None
    result = [[0 for _ in row] for row in grid]
    for row in range(len(grid)):
        for column in range(len(grid[0])):
            colors = [
                color
                for marker_row, marker_column, color in occupied
                if row == marker_row or column == marker_column
            ]
            if len(colors) == 1:
                result[row][column] = colors[0]
            elif len(colors) == 2:
                result[row][column] = 2
    return result


def keep_longest_and_shortest_vertical_bars_one_two(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 5}:
        return None
    bars = []
    for column in range(len(grid[0])):
        rows = [
            row for row in range(len(grid))
            if grid[row][column] == 5
        ]
        if not rows:
            continue
        if rows != list(range(rows[0], rows[-1] + 1)):
            return None
        bars.append((len(rows), column, rows))
    if (
        len(bars) < 3
        or len({length for length, _, _ in bars}) != len(bars)
    ):
        return None
    shortest = min(bars)
    longest = max(bars)
    result = [[0 for _ in row] for row in grid]
    for row in longest[2]:
        result[row][longest[1]] = 1
    for row in shortest[2]:
        result[row][shortest[1]] = 2
    return result


def sort_uniform_color_bars_by_length_bottom_right(
    grid: Grid,
) -> Grid | None:
    bars = []
    seen_colors = set()
    for row in grid:
        occupied = [
            column for column, value in enumerate(row)
            if value != 0
        ]
        if not occupied:
            continue
        if occupied != list(range(occupied[0], occupied[-1] + 1)):
            return None
        colors = {row[column] for column in occupied}
        if len(colors) != 1:
            return None
        color = next(iter(colors))
        if color in seen_colors:
            return None
        seen_colors.add(color)
        bars.append((len(occupied), color))
    if (
        not bars
        or len(bars) > len(grid)
        or len({length for length, _ in bars}) != len(bars)
    ):
        return None
    result = [[0 for _ in row] for row in grid]
    start_row = len(grid) - len(bars)
    for offset, (length, color) in enumerate(sorted(bars)):
        for column in range(len(grid[0]) - length, len(grid[0])):
            result[start_row + offset][column] = color
    return result


def overlay_left_panel_with_mirrored_right_panel(
    grid: Grid,
) -> Grid | None:
    if len(grid[0]) % 2 != 1:
        return None
    middle = len(grid[0]) // 2
    if any(row[middle] != 5 for row in grid):
        return None
    left = [row[:middle] for row in grid]
    right = [list(reversed(row[middle + 1 :])) for row in grid]
    result = [row[:] for row in left]
    for row in range(len(grid)):
        for column in range(middle):
            if (
                left[row][column] != 0
                and right[row][column] != 0
                and left[row][column] != right[row][column]
            ):
                return None
            if right[row][column] != 0:
                result[row][column] = right[row][column]
    return result


def center_red_object_inside_four_green_corners(
    grid: Grid,
) -> Grid | None:
    if not {value for row in grid for value in row}.issubset({0, 2, 3}):
        return None
    markers = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 3
    }
    reds = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 2
    ]
    if len(markers) != 4 or not reds:
        return None
    top = min(row for row, _ in markers)
    bottom = max(row for row, _ in markers)
    left = min(column for _, column in markers)
    right = max(column for _, column in markers)
    if markers != {
        (top, left),
        (top, right),
        (bottom, left),
        (bottom, right),
    }:
        return None
    red_top = min(row for row, _ in reds)
    red_bottom = max(row for row, _ in reds)
    red_left = min(column for _, column in reds)
    red_right = max(column for _, column in reds)
    if (
        red_bottom - red_top + 1 != bottom - top - 1
        or red_right - red_left + 1 != right - left - 1
    ):
        return None
    delta_row = top + 1 - red_top
    delta_column = left + 1 - red_left
    result = [[0 for _ in row] for row in grid]
    for row, column in markers:
        result[row][column] = 3
    for row, column in reds:
        target_row = row + delta_row
        target_column = column + delta_column
        if (
            not 0 <= target_row < len(grid)
            or not 0 <= target_column < len(grid[0])
            or result[target_row][target_column] != 0
        ):
            return None
        result[target_row][target_column] = 2
    return result


def move_green_shape_to_red_line_add_opposite_eight_line(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 2, 3}:
        return None
    full_rows = [
        row for row, values in enumerate(grid)
        if all(value == 2 for value in values)
    ]
    full_columns = [
        column for column in range(len(grid[0]))
        if all(grid[row][column] == 2 for row in range(len(grid)))
    ]
    if len(full_rows) + len(full_columns) != 1:
        return None
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 3
    ]
    if not points:
        return None
    top = min(row for row, _ in points)
    bottom = max(row for row, _ in points)
    left = min(column for _, column in points)
    right = max(column for _, column in points)
    result = [
        [2 if value == 2 else 0 for value in row]
        for row in grid
    ]
    if full_columns:
        line = full_columns[0]
        if right < line:
            target_left = line - (right - left + 1)
            eight_column = target_left - 1
        elif left > line:
            target_left = line + 1
            eight_column = target_left + (right - left + 1)
        else:
            return None
        delta_column = target_left - left
        if not 0 <= eight_column < len(grid[0]):
            return None
        for row in range(len(grid)):
            result[row][eight_column] = 8
        for row, column in points:
            target_column = column + delta_column
            if (
                not 0 <= target_column < len(grid[0])
                or result[row][target_column] != 0
            ):
                return None
            result[row][target_column] = 3
    else:
        line = full_rows[0]
        if bottom < line:
            target_top = line - (bottom - top + 1)
            eight_row = target_top - 1
        elif top > line:
            target_top = line + 1
            eight_row = target_top + (bottom - top + 1)
        else:
            return None
        delta_row = target_top - top
        if not 0 <= eight_row < len(grid):
            return None
        result[eight_row] = [8 for _ in result[eight_row]]
        for row, column in points:
            target_row = row + delta_row
            if (
                not 0 <= target_row < len(grid)
                or result[target_row][column] != 0
            ):
                return None
            result[target_row][column] = 3
    return result


def recolor_bottom_half_of_vertical_two_bars_eight(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 2}:
        return None
    result = [row[:] for row in grid]
    bars = 0
    for column in range(len(grid[0])):
        rows = [
            row for row in range(len(grid))
            if grid[row][column] == 2
        ]
        if not rows:
            continue
        if rows != list(range(rows[0], rows[-1] + 1)):
            return None
        bars += 1
        count = len(rows) // 2
        if count:
            for row in rows[-count:]:
                result[row][column] = 8
    return result if bars else None


def classify_five_cell_three_by_three_glyph(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 3 or len(grid[0]) != 3:
        return None
    colors = {value for row in grid for value in row}
    if (
        0 not in colors
        or len(colors) != 2
        or sum(value != 0 for row in grid for value in row) != 5
    ):
        return None

    def canonical(values: Grid) -> tuple[int, ...]:
        current = [[int(value != 0) for value in row] for row in values]
        variants = []
        for _ in range(4):
            variants.append(tuple(value for row in current for value in row))
            variants.append(
                tuple(value for row in current for value in row[::-1])
            )
            current = rotate_90(current)
        return min(variants)

    labels = {
        canonical(
            [
                [0, 1, 0],
                [1, 1, 1],
                [0, 1, 0],
            ]
        ): 6,
        canonical(
            [
                [1, 0, 1],
                [0, 1, 0],
                [1, 0, 1],
            ]
        ): 2,
        canonical(
            [
                [1, 1, 0],
                [1, 0, 1],
                [0, 1, 0],
            ]
        ): 1,
        canonical(
            [
                [0, 1, 1],
                [0, 1, 1],
                [1, 0, 0],
            ]
        ): 3,
    }
    label = labels.get(canonical(grid))
    return [[label]] if label is not None else None


def render_color_frequencies_as_top_aligned_columns(
    grid: Grid,
) -> Grid | None:
    if any(value == 0 for row in grid for value in row):
        return None
    counts = Counter(value for row in grid for value in row)
    if len(counts) < 2 or len(set(counts.values())) != len(counts):
        return None
    ordered = sorted(
        ((count, color) for color, count in counts.items()),
        reverse=True,
    )
    result = [
        [0 for _ in ordered]
        for _ in range(ordered[0][0])
    ]
    for column, (count, color) in enumerate(ordered):
        for row in range(count):
            result[row][column] = color
    return result


def select_unique_non_main_diagonal_symmetric_panel(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 3 * len(grid[0]):
        return None
    size = len(grid[0])
    panels = [
        [row[:] for row in grid[index * size : (index + 1) * size]]
        for index in range(3)
    ]
    asymmetric = [
        panel for panel in panels
        if panel != transpose(panel)
    ]
    symmetric = [
        panel for panel in panels
        if panel == transpose(panel)
    ]
    if len(asymmetric) != 1 or len(symmetric) != 2:
        return None
    return asymmetric[0]


def classify_three_four_by_four_five_glyphs(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 4
        or len(grid[0]) != 14
        or {value for row in grid for value in row} != {0, 5}
        or any(row[4] != 0 or row[9] != 0 for row in grid)
    ):
        return None
    panels = (
        [row[:4] for row in grid],
        [row[5:9] for row in grid],
        [row[10:14] for row in grid],
    )
    templates = {
        (
            (5, 5, 5, 5),
            (5, 5, 5, 5),
            (5, 5, 5, 5),
            (5, 5, 5, 5),
        ): 2,
        (
            (5, 5, 5, 5),
            (5, 5, 5, 5),
            (5, 0, 0, 5),
            (5, 0, 0, 5),
        ): 4,
        (
            (5, 5, 5, 5),
            (0, 5, 5, 0),
            (0, 5, 5, 0),
            (5, 5, 5, 5),
        ): 3,
        (
            (5, 5, 5, 5),
            (5, 0, 0, 5),
            (5, 0, 0, 5),
            (5, 5, 5, 5),
        ): 8,
    }
    labels = []
    for panel in panels:
        label = templates.get(tuple(tuple(row) for row in panel))
        if label is None:
            return None
        labels.append(label)
    return [[label] * 3 for label in labels]


def recolor_alternating_singletons_from_right_three(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 3
        or {value for row in grid for value in row} != {0, 5}
        or any(
            sum(grid[row][column] == 5 for row in range(3)) != 1
            for column in range(len(grid[0]))
        )
    ):
        return None
    result = [row[:] for row in grid]
    for column in range(len(grid[0]) - 1, -1, -2):
        for row in range(3):
            if result[row][column] == 5:
                result[row][column] = 3
    return result


def recolor_every_third_column_sixes(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 3
        or {value for row in grid for value in row} != {0, 4}
        or any(value != 4 for value in grid[1])
        or any(
            (grid[0][column] == 4) == (grid[2][column] == 4)
            for column in range(len(grid[0]))
        )
    ):
        return None
    top_starts_zero = grid[0][0] == 0
    expected_top = [
        4 if (column + int(top_starts_zero)) % 2 == 0 else 0
        for column in range(len(grid[0]))
    ]
    if grid[0] != expected_top:
        return None
    result = [row[:] for row in grid]
    for column in range(0, len(grid[0]), 3):
        for row in range(3):
            if result[row][column] == 4:
                result[row][column] = 6
    return result


def fill_unique_largest_zero_rectangle_six(
    grid: Grid,
) -> Grid | None:
    height = len(grid)
    width = len(grid[0])
    if height < 2 or width < 2 or not any(
        value == 0 for row in grid for value in row
    ):
        return None
    nonzero_prefix = [[0 for _ in range(width)]]
    for row in grid:
        nonzero_prefix.append(
            [
                nonzero_prefix[-1][column] + int(row[column] != 0)
                for column in range(width)
            ]
        )
    best_area = 0
    best_rectangles = set()
    for top in range(height - 1):
        for bottom in range(top + 1, height):
            zero_columns = [
                nonzero_prefix[bottom + 1][column]
                - nonzero_prefix[top][column] == 0
                for column in range(width)
            ]
            column = 0
            while column < width:
                if not zero_columns[column]:
                    column += 1
                    continue
                start = column
                while column < width and zero_columns[column]:
                    column += 1
                span = column - start
                if span < 2:
                    continue
                area = (bottom - top + 1) * span
                rectangle = (top, bottom, start, column - 1)
                if area > best_area:
                    best_area = area
                    best_rectangles = {rectangle}
                elif area == best_area:
                    best_rectangles.add(rectangle)
    if best_area == 0 or len(best_rectangles) != 1:
        return None
    top, bottom, left, right = next(iter(best_rectangles))
    result = [row[:] for row in grid]
    for row in range(top, bottom + 1):
        for column in range(left, right + 1):
            result[row][column] = 6
    return result


def crop_component_directly_below_five_marker(
    grid: Grid,
) -> Grid | None:
    markers = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    ]
    if len(markers) != 1:
        return None
    marker_row, marker_column = markers[0]
    start = marker_row + 1, marker_column
    if (
        start[0] >= len(grid)
        or grid[start[0]][start[1]] in (0, 5)
    ):
        return None
    color = grid[start[0]][start[1]]
    component = {start}
    stack = [start]
    while stack:
        row, column = stack.pop()
        for delta_row in (-1, 0, 1):
            for delta_column in (-1, 0, 1):
                if delta_row == delta_column == 0:
                    continue
                point = row + delta_row, column + delta_column
                if (
                    0 <= point[0] < len(grid)
                    and 0 <= point[1] < len(grid[0])
                    and point not in component
                    and grid[point[0]][point[1]] == color
                ):
                    component.add(point)
                    stack.append(point)
    rows = [row for row, _ in component]
    columns = [column for _, column in component]
    top, bottom = min(rows), max(rows)
    left, right = min(columns), max(columns)
    result = [
        [0 for _ in range(right - left + 1)]
        for _ in range(bottom - top + 1)
    ]
    for row, column in component:
        result[row - top][column - left] = color
    return result


def pack_two_components_into_three_by_three(
    grid: Grid,
) -> Grid | None:
    colors = sorted({value for row in grid for value in row} - {0})
    if (
        len(colors) != 2
        or sum(value != 0 for row in grid for value in row) != 9
    ):
        return None
    normalized_shapes = []
    for color in colors:
        points = {
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        }
        remaining = set(points)
        connected = {remaining.pop()}
        stack = list(connected)
        while stack:
            row, column = stack.pop()
            for delta_row in (-1, 0, 1):
                for delta_column in (-1, 0, 1):
                    if delta_row == delta_column == 0:
                        continue
                    point = row + delta_row, column + delta_column
                    if point in remaining:
                        remaining.remove(point)
                        connected.add(point)
                        stack.append(point)
        if remaining:
            return None
        top = min(row for row, _ in points)
        left = min(column for _, column in points)
        shape = {
            (row - top, column - left)
            for row, column in points
        }
        if (
            max(row for row, _ in shape) >= 3
            or max(column for _, column in shape) >= 3
        ):
            return None
        normalized_shapes.append(shape)
    placements = []
    for shape in normalized_shapes:
        shape_height = max(row for row, _ in shape) + 1
        shape_width = max(column for _, column in shape) + 1
        placements.append(
            [
                {
                    (row + row_offset, column + column_offset)
                    for row, column in shape
                }
                for row_offset in range(4 - shape_height)
                for column_offset in range(4 - shape_width)
            ]
        )
    outputs = set()
    board = {(row, column) for row in range(3) for column in range(3)}
    for first in placements[0]:
        for second in placements[1]:
            if first & second or first | second != board:
                continue
            result = [[0, 0, 0] for _ in range(3)]
            for row, column in first:
                result[row][column] = colors[0]
            for row, column in second:
                result[row][column] = colors[1]
            outputs.add(tuple(tuple(row) for row in result))
    if len(outputs) != 1:
        return None
    return [list(row) for row in next(iter(outputs))]


def grow_center_marker_diagonals_to_sides(
    grid: Grid,
) -> Grid | None:
    height = len(grid)
    width = len(grid[0])
    if height < 3 or width < 3 or width % 2 == 0:
        return None
    colors = {value for row in grid for value in row} - {0}
    if (
        len(colors) != 2
        or any(value != 0 for row in grid[:-2] for value in row)
    ):
        return None
    bottom = grid[-1]
    if any(value == 0 for value in bottom):
        return None
    counts = Counter(bottom)
    valid = []
    for marker in [
        color for color in colors
        if 0 < counts[color] < width
    ]:
        other = next(color for color in colors if color != marker)
        columns = [
            column for column, value in enumerate(bottom)
            if value == marker
        ]
        if columns != list(range(columns[0], columns[-1] + 1)):
            continue
        left, right = columns[0], columns[-1]
        if left != width - 1 - right:
            continue
        expected_above = [0 for _ in range(width)]
        for column in range(left, right + 1):
            expected_above[column] = other
        if grid[-2] != expected_above:
            continue
        valid.append((marker, left, right))
    if len(valid) != 1:
        return None
    marker, left, right = valid[0]
    result = [row[:] for row in grid]
    row = height - 3
    left -= 1
    right += 1
    while row >= 0 and left >= 0 and right < width:
        result[row][left] = marker
        result[row][right] = marker
        row -= 1
        left -= 1
        right += 1
    return result


def expand_vertical_seven_run_triangle_alternating_eight(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 7}:
        return None
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 7
    ]
    rows = [row for row, _ in points]
    columns = {column for _, column in points}
    if (
        len(columns) != 1
        or rows != list(range(len(rows)))
        or len(rows) < 2
    ):
        return None
    center = next(iter(columns))
    result = [row[:] for row in grid]
    for row in rows:
        radius = len(rows) - 1 - row
        for column in range(
            max(0, center - radius),
            min(len(grid[0]), center + radius + 1),
        ):
            result[row][column] = (
                7 if (column - center) % 2 == 0 else 8
            )
    return result


def expand_left_prefix_two_run_triangles_three_one(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 2}:
        return None
    occupied_rows = [
        row for row, values in enumerate(grid)
        if any(value != 0 for value in values)
    ]
    if len(occupied_rows) != 1:
        return None
    source_row = occupied_rows[0]
    columns = [
        column for column, value in enumerate(grid[source_row])
        if value == 2
    ]
    if (
        not columns
        or columns != list(range(len(columns)))
        or len(columns) + source_row > len(grid[0])
    ):
        return None
    result = [row[:] for row in grid]
    for row in range(source_row):
        length = len(columns) + source_row - row
        for column in range(length):
            result[row][column] = 3
    for row in range(source_row + 1, len(grid)):
        length = len(columns) - (row - source_row)
        for column in range(max(0, length)):
            result[row][column] = 1
    return result


def expand_l_tromino_marker_to_two_four_squares(
    grid: Grid,
) -> Grid | None:
    current = [
        [3, 3, 0],
        [3, 2, 0],
        [0, 0, 0],
    ]
    current_output = [[0 for _ in range(9)] for _ in range(9)]
    for row in range(4):
        for column in range(4):
            current_output[row][column] = 3
            current_output[row + 4][column + 4] = 3
    for _ in range(4):
        if grid == current:
            return [row[:] for row in current_output]
        current = rotate_90(current)
        current_output = rotate_90(current_output)
    return None


def fill_periodic_four_triangles_between_two_pattern(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 3
        or {value for row in grid for value in row} != {0, 2}
    ):
        return None
    expected = [[0 for _ in grid[0]] for _ in range(3)]
    for column in range(0, len(grid[0]), 4):
        expected[0][column] = 2
    for column in range(1, len(grid[0]), 2):
        expected[1][column] = 2
    for column in range(2, len(grid[0]), 4):
        expected[2][column] = 2
    if grid != expected:
        return None
    four_residues = (
        {5, 6, 7},
        {0, 6},
        {0, 1, 11},
    )
    result = [row[:] for row in grid]
    for row in range(3):
        for column in range(len(grid[0])):
            if (
                grid[row][column] == 0
                and column % 12 in four_residues[row]
            ):
                result[row][column] = 4
    return result


def extend_repeated_column_prefix_to_width(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 5:
        return None
    occupied_columns = [
        column for column in range(len(grid[0]))
        if any(grid[row][column] != 0 for row in range(5))
    ]
    if not occupied_columns:
        return None
    active_width = occupied_columns[-1] + 1
    if active_width >= len(grid[0]):
        return None
    period = next(
        (
            candidate
            for candidate in range(1, active_width)
            if active_width >= candidate + 2
            and all(
                all(
                    grid[row][column]
                    == grid[row][column % candidate]
                    for row in range(5)
                )
                for column in range(active_width)
            )
        ),
        None,
    )
    if period is None or len(
        {
            tuple(grid[row][column] for row in range(5))
            for column in range(period)
        }
    ) < 2:
        return None
    return [
        [
            grid[row][column % period]
            for column in range(len(grid[0]))
        ]
        for row in range(5)
    ]


def mark_bottom_centers_of_inverted_u_components_four(
    grid: Grid,
) -> Grid | None:
    if (
        any(value == 4 for row in grid for value in row)
        or any(value != 0 for value in grid[-1])
    ):
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    }
    if not remaining:
        return None
    centers = []
    while remaining:
        start = remaining.pop()
        color = grid[start[0]][start[1]]
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if (
                    point in remaining
                    and grid[point[0]][point[1]] == color
                ):
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        expected = {
            (top, left),
            (top, left + 1),
            (top, right),
            (bottom, left),
            (bottom, right),
        }
        if (
            bottom - top != 1
            or right - left != 2
            or component != expected
        ):
            return None
        centers.append(left + 1)
    result = [row[:] for row in grid]
    for column in centers:
        result[-1][column] = 4
    return result


def expand_panel_center_colors_plus_five(
    grid: Grid,
) -> Grid | None:
    height = len(grid)
    width = len(grid[0])
    if height % 4 != 3 or width % 4 != 3:
        return None
    separator_rows = set(range(3, height, 4))
    separator_columns = set(range(3, width, 4))
    result = [[0 for _ in row] for row in grid]
    for row in range(height):
        for column in range(width):
            if (
                row in separator_rows
                or column in separator_columns
            ):
                if grid[row][column] != 5:
                    return None
                result[row][column] = 5
    for top in range(0, height, 4):
        for left in range(0, width, 4):
            panel = [
                row[left : left + 3]
                for row in grid[top : top + 3]
            ]
            marker = panel[1][1]
            if (
                marker not in (1, 2, 3, 4)
                or sum(
                    value != 0
                    for row in panel
                    for value in row
                ) != 1
            ):
                return None
            for row in range(top, top + 3):
                for column in range(left, left + 3):
                    result[row][column] = marker + 5
    return result


def extend_horizontal_period_to_double_width(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 5:
        return None
    width = len(grid[0])
    period = next(
        (
            candidate
            for candidate in range(1, width)
            if all(
                all(
                    grid[row][column]
                    == grid[row][column % candidate]
                    for row in range(5)
                )
                for column in range(width)
            )
        ),
        None,
    )
    if (
        period is None
        or width < 2 * period
        or len(
            {
                tuple(grid[row][column] for row in range(5))
                for column in range(period)
            }
        ) < 2
    ):
        return None
    return [
        [
            grid[row][column % period]
            for column in range(2 * width)
        ]
        for row in range(5)
    ]


def pack_column_order_markers_snake_three_by_three(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 10 or len(grid[0]) != 10:
        return None
    markers = []
    for column in range(10):
        rows = [
            row for row in range(10)
            if grid[row][column] != 0
        ]
        if len(rows) > 1:
            return None
        if rows:
            markers.append(grid[rows[0]][column])
    if not 1 <= len(markers) <= 9:
        return None
    padded = markers + [0] * (9 - len(markers))
    return [
        padded[:3],
        list(reversed(padded[3:6])),
        padded[6:9],
    ]


def color_inner_mask_by_frame_corner_quadrants(
    grid: Grid,
) -> Grid | None:
    size = len(grid)
    if size != len(grid[0]) or size < 6 or size % 2 != 0:
        return None
    if (
        any(value != 1 for value in grid[1])
        or any(value != 1 for value in grid[-2])
        or any(grid[row][1] != 1 for row in range(size))
        or any(grid[row][-2] != 1 for row in range(size))
    ):
        return None
    corners = (
        grid[0][0],
        grid[0][-1],
        grid[-1][0],
        grid[-1][-1],
    )
    if (
        len(set(corners)) != 4
        or any(color in (0, 1, 8) for color in corners)
    ):
        return None
    for row in range(size):
        for column in range(size):
            if 2 <= row < size - 2 and 2 <= column < size - 2:
                continue
            expected = 0
            if row in (1, size - 2) or column in (1, size - 2):
                expected = 1
            if (row, column) == (0, 0):
                expected = corners[0]
            elif (row, column) == (0, size - 1):
                expected = corners[1]
            elif (row, column) == (size - 1, 0):
                expected = corners[2]
            elif (row, column) == (size - 1, size - 1):
                expected = corners[3]
            if grid[row][column] != expected:
                return None
    mask = [
        row[2:-2]
        for row in grid[2:-2]
    ]
    if not {
        value for row in mask for value in row
    }.issubset({0, 8}):
        return None
    half = len(mask) // 2
    result = [[0 for _ in row] for row in mask]
    for row in range(len(mask)):
        for column in range(len(mask[0])):
            if mask[row][column] == 8:
                result[row][column] = corners[
                    2 * int(row >= half) + int(column >= half)
                ]
    return result


def render_largest_color_counts_left_to_right(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 10 or len(grid[0]) != 10:
        return None
    colors = sorted({value for row in grid for value in row} - {0})
    if len(colors) < 2:
        return None
    items = []
    for color in colors:
        points = {
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        }
        remaining = set(points)
        connected = {remaining.pop()}
        stack = list(connected)
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    connected.add(point)
                    stack.append(point)
        if remaining:
            return None
        items.append(
            (
                len(points),
                min(column for _, column in points),
                color,
            )
        )
    maximum = max(count for count, _, _ in items)
    selected = sorted(
        (left, color)
        for count, left, color in items
        if count == maximum
    )
    if len({left for left, _ in selected}) != len(selected):
        return None
    row = [color for _, color in selected]
    return [row[:] for _ in range(maximum)]


def crop_component_with_most_twos(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or not {
            value for row in grid for value in row
        }.issubset({0, 1, 2, 8})
        or not any(value == 2 for row in grid for value in row)
    ):
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    }
    components = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        components.append(component)
    if len(components) < 2:
        return None
    counts = [
        sum(grid[row][column] == 2 for row, column in component)
        for component in components
    ]
    maximum = max(counts)
    if maximum == 0 or counts.count(maximum) != 1:
        return None
    component = components[counts.index(maximum)]
    rows = [row for row, _ in component]
    columns = [column for _, column in component]
    top, bottom = min(rows), max(rows)
    left, right = min(columns), max(columns)
    result = [
        row[left : right + 1]
        for row in grid[top : bottom + 1]
    ]
    if any(value == 0 for row in result for value in row):
        return None
    return result


def surround_each_two_with_ones_three_by_three(
    grid: Grid,
) -> Grid | None:
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 2
    ]
    if (
        not points
        or any(value == 1 for row in grid for value in row)
    ):
        return None
    result = [row[:] for row in grid]
    for row, column in points:
        for target_row in range(
            max(0, row - 1),
            min(len(grid), row + 2),
        ):
            for target_column in range(
                max(0, column - 1),
                min(len(grid[0]), column + 2),
            ):
                if result[target_row][target_column] == 0:
                    result[target_row][target_column] = 1
    return result


def replace_hollow_three_by_three_one_squares_with_two_pluses(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or {value for row in grid for value in row} != {0, 1}
    ):
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 1
    }
    components = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        components.append(component)
    targets = []
    for component in components:
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        perimeter = {
            (row, column)
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
            if row in (top, bottom) or column in (left, right)
        }
        if (
            bottom - top == 2
            and right - left == 2
            and component == perimeter
        ):
            targets.append((component, top + 1, left + 1))
    if not targets:
        return None
    result = [row[:] for row in grid]
    for component, center_row, center_column in targets:
        for row, column in component:
            result[row][column] = 0
        for row, column in (
            (center_row, center_column),
            (center_row - 1, center_column),
            (center_row + 1, center_column),
            (center_row, center_column - 1),
            (center_row, center_column + 1),
        ):
            result[row][column] = 2
    return result


def project_five_markers_to_expanded_two_bbox(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 2, 5}:
        return None
    twos = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 2
    ]
    markers = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    ]
    if len(twos) != 4 or not markers:
        return None
    top = min(row for row, _ in twos)
    bottom = max(row for row, _ in twos)
    left = min(column for _, column in twos)
    right = max(column for _, column in twos)
    if (
        bottom - top != 1
        or right - left != 1
        or any(
            grid[row][column] != 2
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
        )
    ):
        return None
    result = [[0 for _ in row] for row in grid]
    for row in range(top, bottom + 1):
        for column in range(left, right + 1):
            result[row][column] = 2
    for row, column in markers:
        target_row = min(max(row, top - 1), bottom + 1)
        target_column = min(max(column, left - 1), right + 1)
        if (
            not 0 <= target_row < len(grid)
            or not 0 <= target_column < len(grid[0])
            or (
                top <= target_row <= bottom
                and left <= target_column <= right
            )
            or result[target_row][target_column] != 0
        ):
            return None
        result[target_row][target_column] = 5
    return result


def recolor_solid_five_rectangle_interiors_two(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 5}:
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    }
    rectangles = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        expected = {
            (row, column)
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
        }
        if (
            component != expected
            or bottom - top < 2
            or right - left < 2
        ):
            return None
        rectangles.append((top, bottom, left, right))
    result = [row[:] for row in grid]
    for top, bottom, left, right in rectangles:
        for row in range(top + 1, bottom):
            for column in range(left + 1, right):
                result[row][column] = 2
    return result


def fill_horizontal_gaps_between_red_runs_nine(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or {value for row in grid for value in row} != {0, 2}
    ):
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 2
    }
    rectangles = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        expected = {
            (row, column)
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
        }
        if component != expected:
            return None
        rectangles.append((top, bottom, left, right))
    if len(rectangles) < 3:
        return None
    pairs = set()
    for index, (top, bottom, left, right) in enumerate(rectangles):
        for direction in (-1, 1):
            candidates = []
            for other_index, other in enumerate(rectangles):
                if other_index == index:
                    continue
                other_top, other_bottom, other_left, other_right = other
                if min(bottom, other_bottom) < max(top, other_top):
                    continue
                if direction < 0 and other_right < left:
                    candidates.append((left - other_right - 1, other_index))
                elif direction > 0 and other_left > right:
                    candidates.append((other_left - right - 1, other_index))
            if not candidates:
                continue
            nearest = min(distance for distance, _ in candidates)
            for distance, other_index in candidates:
                if distance == nearest:
                    pairs.add(tuple(sorted((index, other_index))))
    if not pairs:
        return None
    result = [row[:] for row in grid]
    for first, second in pairs:
        a = rectangles[first]
        b = rectangles[second]
        if a[2] > b[2]:
            a, b = b, a
        top = max(a[0], b[0])
        bottom = min(a[1], b[1])
        for row in range(top, bottom + 1):
            for column in range(a[3] + 1, b[2]):
                result[row][column] = 9
    return result


def rank_two_solid_gray_rectangles_interiors(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or {value for row in grid for value in row} != {0, 4}
    ):
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 4
    }
    rectangles = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        expected = {
            (row, column)
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
        }
        if (
            component != expected
            or bottom - top < 2
            or right - left < 2
        ):
            return None
        rectangles.append(
            (
                len(component),
                top,
                bottom,
                left,
                right,
            )
        )
    if len(rectangles) != 2 or rectangles[0][0] == rectangles[1][0]:
        return None
    rectangles.sort()
    result = [row[:] for row in grid]
    for fill, (_, top, bottom, left, right) in enumerate(
        rectangles, start=1
    ):
        for row in range(top + 1, bottom):
            for column in range(left + 1, right):
                result[row][column] = fill
    return result


def extend_l_tromino_bisector_rays(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row} - {0}
    if len(grid) != 10 or len(grid[0]) != 10 or len(colors) != 1:
        return None
    color = next(iter(colors))
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == color
    }
    components = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        if len(component) != 3:
            return None
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        if max(rows) - min(rows) != 1 or max(columns) - min(columns) != 1:
            return None
        components.append(component)
    if len(components) < 2:
        return None
    result = [row[:] for row in grid]
    painted = 0
    for component in components:
        elbows = []
        for row, column in component:
            neighbors = {
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            } & component
            if len(neighbors) == 2:
                elbows.append((row, column))
        if len(elbows) != 1:
            return None
        elbow_row, elbow_column = elbows[0]
        endpoints = component - {elbows[0]}
        delta_row = sum(row - elbow_row for row, _ in endpoints)
        delta_column = sum(
            column - elbow_column for _, column in endpoints
        )
        if abs(delta_row) != 1 or abs(delta_column) != 1:
            return None
        step = 2
        while True:
            row = elbow_row + step * delta_row
            column = elbow_column + step * delta_column
            if not (0 <= row < len(grid) and 0 <= column < len(grid[0])):
                break
            if result[row][column] != 0:
                return None
            result[row][column] = color
            painted += 1
            step += 1
    return result if painted else None


def extend_one_two_around_horizontal_five_divider(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or {value for row in grid for value in row} != {0, 1, 2, 5}
    ):
        return None
    divider_rows = [
        row
        for row, values in enumerate(grid)
        if all(value == 5 for value in values)
    ]
    if (
        len(divider_rows) != 1
        or any(
            value == 5
            for row, values in enumerate(grid)
            if row != divider_rows[0]
            for value in values
        )
    ):
        return None
    divider = divider_rows[0]
    result = [row[:] for row in grid]
    for color in (1, 2):
        points = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ]
        for row, column in points:
            if row == divider:
                return None
            if color == 1:
                rows = (
                    range(0, row + 1)
                    if row < divider
                    else range(row, len(grid))
                )
            else:
                rows = (
                    range(row, divider)
                    if row < divider
                    else range(divider + 1, row + 1)
                )
            for target_row in rows:
                if result[target_row][column] not in (0, color):
                    return None
                result[target_row][column] = color
    return result


def align_component_shapes_to_color_one_rows(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 1, 2, 4}:
        return None
    groups: dict[tuple, list] = {}
    for color in (1, 2, 4):
        remaining = {
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        }
        while remaining:
            start = remaining.pop()
            component = {start}
            stack = [start]
            while stack:
                row, column = stack.pop()
                for point in (
                    (row - 1, column),
                    (row + 1, column),
                    (row, column - 1),
                    (row, column + 1),
                ):
                    if point in remaining:
                        remaining.remove(point)
                        component.add(point)
                        stack.append(point)
            top = min(row for row, _ in component)
            left = min(column for _, column in component)
            shape = tuple(
                sorted(
                    (row - top, column - left)
                    for row, column in component
                )
            )
            item = (color, top, left, shape)
            groups.setdefault(shape, []).append(item)
    if not groups:
        return None
    for items in groups.values():
        if (
            len(items) != 3
            or {item[0] for item in items} != {1, 2, 4}
        ):
            return None
    result = [[0 for _ in row] for row in grid]
    for shape, items in groups.items():
        target_top = next(item[1] for item in items if item[0] == 1)
        for color, _, left, _ in items:
            for delta_row, delta_column in shape:
                row = target_top + delta_row
                column = left + delta_column
                if (
                    not 0 <= row < len(grid)
                    or not 0 <= column < len(grid[0])
                    or result[row][column] != 0
                ):
                    return None
                result[row][column] = color
    return result


def recolor_repeated_eight_component_shapes_one_else_two(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or {value for row in grid for value in row} != {0, 8}
    ):
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 8
    }
    components = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        top = min(row for row, _ in component)
        left = min(column for _, column in component)
        shape = tuple(
            sorted(
                (row - top, column - left)
                for row, column in component
            )
        )
        components.append((component, shape))
    counts = Counter(shape for _, shape in components)
    if (
        len(components) < 3
        or not any(count > 1 for count in counts.values())
        or not any(count == 1 for count in counts.values())
    ):
        return None
    result = [row[:] for row in grid]
    for component, shape in components:
        fill = 1 if counts[shape] > 1 else 2
        for row, column in component:
            result[row][column] = fill
    return result


def recolor_six_cell_fives_two_others_one(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or {value for row in grid for value in row} != {0, 5}
    ):
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    }
    components = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        components.append(component)
    if (
        len(components) < 3
        or not any(len(component) == 6 for component in components)
        or not any(len(component) != 6 for component in components)
    ):
        return None
    result = [row[:] for row in grid]
    for component in components:
        fill = 2 if len(component) == 6 else 1
        for row, column in component:
            result[row][column] = fill
    return result


def recolor_solid_five_rectangles_corners_edges_interiors(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or {value for row in grid for value in row} != {0, 5}
    ):
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    }
    rectangles = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        expected = {
            (row, column)
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
        }
        if (
            component != expected
            or bottom - top < 2
            or right - left < 2
        ):
            return None
        rectangles.append((top, bottom, left, right))
    if len(rectangles) != 2:
        return None
    result = [row[:] for row in grid]
    for top, bottom, left, right in rectangles:
        for row in range(top, bottom + 1):
            for column in range(left, right + 1):
                result[row][column] = 2
        for column in range(left, right + 1):
            result[top][column] = 4
            result[bottom][column] = 4
        for row in range(top, bottom + 1):
            result[row][left] = 4
            result[row][right] = 4
        for row, column in (
            (top, left),
            (top, right),
            (bottom, left),
            (bottom, right),
        ):
            result[row][column] = 1
    return result


def recolor_five_components_by_size_four_three_two(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or {value for row in grid for value in row} != {0, 5}
    ):
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    }
    components = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        components.append(component)
    if {len(component) for component in components} != {2, 3, 4}:
        return None
    result = [row[:] for row in grid]
    for component in components:
        fill = 5 - len(component)
        for row, column in component:
            result[row][column] = fill
    return result


def extend_diagonal_markers_from_two_square(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row} - {0}
    if len(grid) != 10 or len(grid[0]) != 10 or len(colors) != 1:
        return None
    color = next(iter(colors))
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == color
    }
    components = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        components.append(component)
    squares = []
    markers = []
    for component in components:
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        if (
            len(component) == 4
            and bottom - top == 1
            and right - left == 1
        ):
            squares.append((top, bottom, left, right))
        elif len(component) == 1:
            markers.append(next(iter(component)))
        else:
            return None
    if len(squares) != 1 or not markers:
        return None
    top, bottom, left, right = squares[0]
    directions = {
        (top - 1, left - 1): (-1, -1),
        (top - 1, right + 1): (-1, 1),
        (bottom + 1, left - 1): (1, -1),
        (bottom + 1, right + 1): (1, 1),
    }
    if any(marker not in directions for marker in markers):
        return None
    result = [row[:] for row in grid]
    painted = 0
    for marker in markers:
        delta_row, delta_column = directions[marker]
        row, column = marker
        while True:
            row += delta_row
            column += delta_column
            if not (0 <= row < len(grid) and 0 <= column < len(grid[0])):
                break
            if result[row][column] != 0:
                return None
            result[row][column] = color
            painted += 1
    return result if painted else None


def color_corner_center_grid_regions_one_two_three(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or {value for row in grid for value in row} != {0, 5}
    ):
        return None
    separator_rows = [
        row
        for row, values in enumerate(grid)
        if all(value == 5 for value in values)
    ]
    separator_columns = [
        column
        for column in range(len(grid[0]))
        if all(grid[row][column] == 5 for row in range(len(grid)))
    ]
    if not separator_rows or not separator_columns:
        return None
    row_set = set(separator_rows)
    column_set = set(separator_columns)
    if any(
        value != (5 if row in row_set or column in column_set else 0)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
    ):
        return None

    def bands(length: int, separators: list[int]) -> list[range]:
        result = []
        start = 0
        for separator in separators:
            if separator > start:
                result.append(range(start, separator))
            start = separator + 1
        if start < length:
            result.append(range(start, length))
        return result

    row_bands = bands(len(grid), separator_rows)
    column_bands = bands(len(grid[0]), separator_columns)
    if (
        len(row_bands) < 3
        or len(row_bands) % 2 == 0
        or len(column_bands) < 3
        or len(column_bands) % 2 == 0
    ):
        return None
    result = [row[:] for row in grid]
    targets = (
        (row_bands[0], column_bands[0], 1),
        (
            row_bands[len(row_bands) // 2],
            column_bands[len(column_bands) // 2],
            2,
        ),
        (row_bands[-1], column_bands[-1], 3),
    )
    for rows, columns, color in targets:
        for row in rows:
            for column in columns:
                result[row][column] = color
    return result


def rank_three_five_components_colors_one_four_two(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or {value for row in grid for value in row} != {0, 5}
    ):
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    }
    components = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        components.append(component)
    if (
        len(components) != 3
        or len({len(component) for component in components}) != 3
    ):
        return None
    components.sort(key=len)
    result = [row[:] for row in grid]
    for component, fill in zip(components, (2, 4, 1)):
        for row, column in component:
            result[row][column] = fill
    return result


def recolor_zero_components_by_size_three_two_one(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or {value for row in grid for value in row} != {0, 5}
    ):
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 0
    }
    components = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        components.append(component)
    if {len(component) for component in components} != {1, 2, 3}:
        return None
    result = [row[:] for row in grid]
    for component in components:
        fill = 4 - len(component)
        for row, column in component:
            result[row][column] = fill
    return result


def stamp_cardinal_colors_around_ones(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or {value for row in grid for value in row} != {0, 1}
    ):
        return None
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 1
    ]
    if len(points) < 2:
        return None
    result = [row[:] for row in grid]
    for row, column in points:
        for delta_row, delta_column, color in (
            (-1, 0, 2),
            (1, 0, 8),
            (0, -1, 7),
            (0, 1, 6),
        ):
            target_row = row + delta_row
            target_column = column + delta_column
            if not (
                0 <= target_row < len(grid)
                and 0 <= target_column < len(grid[0])
            ):
                continue
            if result[target_row][target_column] not in (0, color):
                return None
            result[target_row][target_column] = color
    return result


def complete_quarter_turn_color_orbits(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row}
    if len(grid) != 10 or len(grid[0]) != 10 or len(colors) != 4 or 0 not in colors:
        return None
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    ]
    top = min(row for row, _ in points)
    bottom = max(row for row, _ in points)
    left = min(column for _, column in points)
    right = max(column for _, column in points)
    if bottom - top != right - left or (bottom - top) % 2:
        return None
    center_row = (top + bottom) // 2
    center_column = (left + right) // 2
    result = [row[:] for row in grid]
    painted = 0
    for row, column in points:
        color = grid[row][column]
        delta_row = row - center_row
        delta_column = column - center_column
        orbit = (
            (delta_row, delta_column),
            (-delta_column, delta_row),
            (-delta_row, -delta_column),
            (delta_column, -delta_row),
        )
        for target_delta_row, target_delta_column in orbit:
            target_row = center_row + target_delta_row
            target_column = center_column + target_delta_column
            if (
                not 0 <= target_row < len(grid)
                or not 0 <= target_column < len(grid[0])
                or result[target_row][target_column] not in (0, color)
            ):
                return None
            if result[target_row][target_column] == 0:
                result[target_row][target_column] = color
                painted += 1
    return result if painted else None


def generate_vertical_lattice_from_bottom_marker(
    grid: Grid,
) -> Grid | None:
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    ]
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or len(points) != 1
        or points[0][0] != len(grid) - 1
    ):
        return None
    _, source_column = points[0]
    color = grid[-1][source_column]
    if color in (0, 5):
        return None
    result = [[0 for _ in row] for row in grid]
    for column in range(source_column, len(grid[0]), 2):
        for row in range(len(grid)):
            result[row][column] = color
    for column in range(source_column + 1, len(grid[0]), 4):
        result[0][column] = 5
    for column in range(source_column + 3, len(grid[0]), 4):
        result[-1][column] = 5
    return result


def replace_five_triangles_with_parallel_diagonals(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row} - {0, 5}
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or len(colors) != 1
        or not any(value == 5 for row in grid for value in row)
    ):
        return None
    color = next(iter(colors))
    source_points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == color
    ]
    offsets = {column - row for row, column in source_points}
    if len(source_points) < 4 or len(offsets) != 1:
        return None
    source_offset = next(iter(offsets))
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    }
    targets = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        size = bottom - top + 1
        if right - left + 1 != size:
            return None
        upper_right = {
            (top + row, left + column)
            for row in range(size)
            for column in range(row, size)
        }
        lower_left = {
            (top + row, left + column)
            for row in range(size)
            for column in range(row + 1)
        }
        if component == upper_right:
            direction = 1
        elif component == lower_left:
            direction = -1
        else:
            return None
        targets.append(source_offset + direction * (size + 2))
    if not targets or len(targets) != len(set(targets)):
        return None
    result = [[0 for _ in row] for row in grid]
    for row, column in source_points:
        result[row][column] = color
    painted = 0
    for target in targets:
        for row in range(len(grid)):
            column = row + target
            if 0 <= column < len(grid[0]):
                if result[row][column] not in (0, color):
                    return None
                if result[row][column] == 0:
                    result[row][column] = color
                    painted += 1
    return result if painted else None


def render_two_five_row_frames_from_markers(
    grid: Grid,
) -> Grid | None:
    points = [
        (row, column, value)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    ]
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or len(points) != 2
        or {row for row, _, _ in points} != {2, 7}
        or len({color for _, _, color in points}) != 2
    ):
        return None
    top_color = next(color for row, _, color in points if row == 2)
    bottom_color = next(color for row, _, color in points if row == 7)
    result = [[0 for _ in row] for row in grid]
    for row in range(0, 5):
        result[row][0] = top_color
        result[row][-1] = top_color
    result[0] = [top_color] * len(grid[0])
    result[2] = [top_color] * len(grid[0])
    for row in range(5, 10):
        result[row][0] = bottom_color
        result[row][-1] = bottom_color
    result[7] = [bottom_color] * len(grid[0])
    result[9] = [bottom_color] * len(grid[0])
    return result


def stamp_multicolor_template_over_eight_masks(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row}
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or 0 not in colors
        or 8 not in colors
        or not (colors - {0, 8})
    ):
        return None
    template_points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value not in (0, 8)
    ]
    template_top = min(row for row, _ in template_points)
    template_left = min(column for _, column in template_points)
    template = {
        (row - template_top, column - template_left): grid[row][column]
        for row, column in template_points
    }
    mask = set(template)
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 8
    }
    targets = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        top = min(row for row, _ in component)
        left = min(column for _, column in component)
        normalized = {
            (row - top, column - left)
            for row, column in component
        }
        if normalized != mask:
            return None
        targets.append((top, left))
    if len(targets) < 2:
        return None
    result = [[0 for _ in row] for row in grid]
    for top, left in targets:
        for (delta_row, delta_column), color in template.items():
            row = top + delta_row
            column = left + delta_column
            if result[row][column] != 0:
                return None
            result[row][column] = color
    return result


def stamp_template_over_solid_five_rectangles(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row}
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or 0 not in colors
        or 5 not in colors
        or not (colors - {0, 5})
    ):
        return None
    template_points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value not in (0, 5)
    ]
    top = min(row for row, _ in template_points)
    bottom = max(row for row, _ in template_points)
    left = min(column for _, column in template_points)
    right = max(column for _, column in template_points)
    template = [
        row[left : right + 1]
        for row in grid[top : bottom + 1]
    ]
    if any(value in (0, 5) for row in template for value in row):
        return None
    height = len(template)
    width = len(template[0])
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    }
    targets = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        target_top, target_bottom = min(rows), max(rows)
        target_left, target_right = min(columns), max(columns)
        expected = {
            (row, column)
            for row in range(target_top, target_bottom + 1)
            for column in range(target_left, target_right + 1)
        }
        if (
            component != expected
            or target_bottom - target_top + 1 != height
            or target_right - target_left + 1 != width
        ):
            return None
        targets.append((target_top, target_left))
    if len(targets) < 2:
        return None
    result = [row[:] for row in grid]
    for target_top, target_left in targets:
        for delta_row, values in enumerate(template):
            for delta_column, value in enumerate(values):
                result[target_top + delta_row][
                    target_left + delta_column
                ] = value
    return result


def connect_gray_block_to_aligned_markers(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 10 or len(grid[0]) != 10 or not any(
        value == 3 for row in grid for value in row
    ):
        return None
    threes = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 3
    }
    rows = [row for row, _ in threes]
    columns = [column for _, column in threes]
    top, bottom = min(rows), max(rows)
    left, right = min(columns), max(columns)
    if (
        threes
        != {
            (row, column)
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
        }
        or bottom - top != 1
        or right - left != 1
    ):
        return None
    markers = [
        (row, column, value)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value not in (0, 3)
    ]
    result = [row[:] for row in grid]
    painted = 0
    for row, column, color in markers:
        targets = []
        if row in (top, bottom):
            if column < left:
                targets = [(row, value) for value in range(column + 1, left)]
            elif column > right:
                targets = [(row, value) for value in range(right + 1, column)]
        elif column in (left, right):
            if row < top:
                targets = [(value, column) for value in range(row + 1, top)]
            elif row > bottom:
                targets = [(value, column) for value in range(bottom + 1, row)]
        for target_row, target_column in targets:
            if result[target_row][target_column] not in (0, color):
                return None
            if result[target_row][target_column] == 0:
                result[target_row][target_column] = color
                painted += 1
    return result if painted else None


def shift_cross_down_left_by_five_count(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row} - {0, 5}
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or len(colors) != 1
        or not any(value == 5 for row in grid for value in row)
    ):
        return None
    color = next(iter(colors))
    five_points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    ]
    shift = len(five_points)
    if (
        not shift
        or five_points != [(row, len(grid[0]) - 1) for row in range(shift)]
    ):
        return None
    full_rows = [
        row for row, values in enumerate(grid) if all(value == color for value in values)
    ]
    full_columns = [
        column
        for column in range(len(grid[0]))
        if all(grid[row][column] == color for row in range(len(grid)))
    ]
    if len(full_rows) != 1 or len(full_columns) != 1:
        return None
    source_row = full_rows[0]
    source_column = full_columns[0]
    expected = [[0 for _ in row] for row in grid]
    expected[source_row] = [color] * len(grid[0])
    for row in range(len(grid)):
        expected[row][source_column] = color
    for row, column in five_points:
        expected[row][column] = 5
    if grid != expected:
        return None
    target_row = source_row + shift
    target_column = source_column - shift
    if not (
        0 <= target_row < len(grid)
        and 0 <= target_column < len(grid[0])
    ):
        return None
    result = [[0 for _ in row] for row in grid]
    result[target_row] = [color] * len(grid[0])
    for row in range(len(grid)):
        result[row][target_column] = color
    return result


def fill_marked_open_one_frames(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row}
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or 0 not in colors
        or 1 not in colors
    ):
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 1
    }
    frames = []
    assigned_markers = set()
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        if (
            top == 0
            or bottom - top < 2
            or right - left < 2
            or (right - left) % 2
        ):
            return None
        center_column = (left + right) // 2
        expected = {
            (row, column)
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
            if (
                column in (left, right)
                or row == bottom
                or row == top and column != center_column
            )
        }
        if component != expected:
            return None
        markers = [
            (row, column)
            for row in range(top + 1, bottom)
            for column in range(left + 1, right)
            if grid[row][column] not in (0, 1)
        ]
        if len(markers) != 1 or markers[0][1] != center_column:
            return None
        marker = markers[0]
        marker_color = grid[marker[0]][marker[1]]
        assigned_markers.add(marker)
        frames.append(
            (top, bottom, left, right, center_column, marker_color)
        )
    all_markers = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value not in (0, 1)
    }
    if not frames or assigned_markers != all_markers:
        return None
    result = [row[:] for row in grid]
    for top, bottom, left, right, center_column, marker_color in frames:
        for column in range(left, right + 1):
            if result[top - 1][column] != 0:
                return None
            result[top - 1][column] = marker_color
        result[top][center_column] = marker_color
        for row in range(top + 1, bottom):
            for column in range(left + 1, right):
                result[row][column] = marker_color
    return result


def project_external_markers_onto_eight_rectangle(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or not any(value == 8 for row in grid for value in row)
    ):
        return None
    eights = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 8
    }
    rows = [row for row, _ in eights]
    columns = [column for _, column in eights]
    top, bottom = min(rows), max(rows)
    left, right = min(columns), max(columns)
    expected = {
        (row, column)
        for row in range(top, bottom + 1)
        for column in range(left, right + 1)
    }
    if eights != expected or bottom - top < 1 or right - left < 1:
        return None
    markers = [
        (row, column, value)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value not in (0, 8)
    ]
    if not markers:
        return None
    result = [row[:] for row in grid]
    targets = set()
    for row, column, color in markers:
        target = None
        if top <= row <= bottom:
            if column < left:
                target = (row, left)
            elif column > right:
                target = (row, right)
        elif left <= column <= right:
            if row < top:
                target = (top, column)
            elif row > bottom:
                target = (bottom, column)
        if target is None or target in targets:
            return None
        targets.add(target)
        result[target[0]][target[1]] = color
    return result


def recolor_three_markers_by_nearest_colored_border(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 10 or len(grid[0]) != 10:
        return None
    horizontal = (
        len(set(grid[0])) == 1
        and grid[0][0] != 0
        and len(set(grid[-1])) == 1
        and grid[-1][0] != 0
        and grid[0][0] != grid[-1][0]
    )
    vertical = (
        len({row[0] for row in grid}) == 1
        and grid[0][0] != 0
        and len({row[-1] for row in grid}) == 1
        and grid[0][0] != grid[0][-1]
    )
    if horizontal == vertical:
        return None
    result = [row[:] for row in grid]
    markers = []
    if horizontal:
        first_color = grid[0][0]
        second_color = grid[-1][0]
        for row in range(len(grid)):
            for column in range(len(grid[0])):
                border_value = (
                    first_color
                    if row == 0
                    else second_color if row == len(grid) - 1 else 0
                )
                value = grid[row][column]
                if value != border_value and value != 0:
                    if value != 3:
                        return None
                    markers.append((row, column))
        for row, column in markers:
            first_distance = row
            second_distance = len(grid) - 1 - row
            if first_distance == second_distance:
                return None
            result[row][column] = (
                first_color
                if first_distance < second_distance
                else second_color
            )
    else:
        first_color = grid[0][0]
        second_color = grid[0][-1]
        for row in range(len(grid)):
            for column in range(len(grid[0])):
                border_value = (
                    first_color
                    if column == 0
                    else second_color if column == len(grid[0]) - 1 else 0
                )
                value = grid[row][column]
                if value != border_value and value != 0:
                    if value != 3:
                        return None
                    markers.append((row, column))
        for row, column in markers:
            first_distance = column
            second_distance = len(grid[0]) - 1 - column
            if first_distance == second_distance:
                return None
            result[row][column] = (
                first_color
                if first_distance < second_distance
                else second_color
            )
    return result if len(markers) >= 2 else None


def bridge_two_solid_rectangles_with_eight(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row} - {0}
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or len(colors) != 2
        or 8 in colors
    ):
        return None
    rectangles = []
    for color in colors:
        component = {
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        }
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        expected = {
            (row, column)
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
        }
        if component != expected:
            return None
        rectangles.append((top, bottom, left, right))
    first, second = rectangles
    result = [row[:] for row in grid]
    painted = 0
    if first[3] < second[2] or second[3] < first[2]:
        if first[2] > second[2]:
            first, second = second, first
        top = max(first[0] + 1, second[0] + 1)
        bottom = min(first[1] - 1, second[1] - 1)
        if top > bottom:
            return None
        for row in range(top, bottom + 1):
            for column in range(first[3] + 1, second[2]):
                if result[row][column] != 0:
                    return None
                result[row][column] = 8
                painted += 1
    elif first[1] < second[0] or second[1] < first[0]:
        if first[0] > second[0]:
            first, second = second, first
        left = max(first[2] + 1, second[2] + 1)
        right = min(first[3] - 1, second[3] - 1)
        if left > right:
            return None
        for row in range(first[1] + 1, second[0]):
            for column in range(left, right + 1):
                if result[row][column] != 0:
                    return None
                result[row][column] = 8
                painted += 1
    else:
        return None
    return result if painted else None


def frame_unique_singleton_color_with_twos(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 10 or len(grid[0]) != 10:
        return None
    counts = Counter(value for row in grid for value in row if value)
    singleton_colors = [
        color for color, count in counts.items() if count == 1
    ]
    if len(singleton_colors) != 1:
        return None
    color = singleton_colors[0]
    point = next(
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == color
    )
    row, column = point
    if (
        color == 2
        or row == 0
        or row == len(grid) - 1
        or column == 0
        or column == len(grid[0]) - 1
    ):
        return None
    result = [[0] * len(grid[0]) for _ in grid]
    for target_row in range(row - 1, row + 2):
        for target_column in range(column - 1, column + 2):
            result[target_row][target_column] = 2
    result[row][column] = color
    return result


def move_four_inner_markers_to_opposite_frame_corners(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 10 or len(grid[0]) != 10:
        return None
    counts = Counter(value for row in grid for value in row)
    frame_colors = [
        color
        for color, count in counts.items()
        if color != 0 and count >= 8
    ]
    if len(frame_colors) != 1:
        return None
    frame_color = frame_colors[0]
    frame_points = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == frame_color
    }
    rows = [row for row, _ in frame_points]
    columns = [column for _, column in frame_points]
    top, bottom = min(rows), max(rows)
    left, right = min(columns), max(columns)
    boundary = {
        (row, column)
        for row in range(top, bottom + 1)
        for column in range(left, right + 1)
        if row in (top, bottom) or column in (left, right)
    }
    if (
        frame_points != boundary
        or top == 0
        or left == 0
        or bottom == len(grid) - 1
        or right == len(grid[0]) - 1
    ):
        return None
    markers = [
        (row, column, value)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value not in (0, frame_color)
    ]
    if (
        len(markers) != 4
        or len({color for _, _, color in markers}) != 4
        or any(
            not (top < row < bottom and left < column < right)
            for row, column, _ in markers
        )
    ):
        return None
    row_midpoint = (top + bottom) / 2
    column_midpoint = (left + right) / 2
    quadrants = {}
    for row, column, color in markers:
        if row == row_midpoint or column == column_midpoint:
            return None
        quadrant = (
            0 if row < row_midpoint else 1,
            0 if column < column_midpoint else 1,
        )
        if quadrant in quadrants:
            return None
        quadrants[quadrant] = color
    if len(quadrants) != 4:
        return None
    result = [[0] * len(grid[0]) for _ in grid]
    for row, column in boundary:
        result[row][column] = frame_color
    opposite_targets = {
        (1, 1): (top - 1, left - 1),
        (1, 0): (top - 1, right + 1),
        (0, 1): (bottom + 1, left - 1),
        (0, 0): (bottom + 1, right + 1),
    }
    for quadrant, (row, column) in opposite_targets.items():
        result[row][column] = quadrants[quadrant]
    return result


def place_quadrant_singletons_into_two_by_two_eight_block(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 10 or len(grid[0]) != 10:
        return None
    eights = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 8
    }
    if len(eights) != 4:
        return None
    rows = [row for row, _ in eights]
    columns = [column for _, column in eights]
    top, bottom = min(rows), max(rows)
    left, right = min(columns), max(columns)
    if (
        eights
        != {
            (top, left),
            (top, right),
            (bottom, left),
            (bottom, right),
        }
        or bottom - top != 1
        or right - left != 1
    ):
        return None
    markers = [
        (row, column, value)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value not in (0, 8)
    ]
    if (
        len(markers) != 4
        or len({color for _, _, color in markers}) != 4
    ):
        return None
    quadrants = {}
    for row, column, color in markers:
        if row < top and column < left:
            quadrant = (0, 0)
        elif row < top and column > right:
            quadrant = (0, 1)
        elif row > bottom and column < left:
            quadrant = (1, 0)
        elif row > bottom and column > right:
            quadrant = (1, 1)
        else:
            return None
        if quadrant in quadrants:
            return None
        quadrants[quadrant] = color
    if len(quadrants) != 4:
        return None
    result = [[0] * len(grid[0]) for _ in grid]
    for (delta_row, delta_column), color in quadrants.items():
        result[top + delta_row][left + delta_column] = color
    return result


def recolor_solid_five_rectangles_by_top_markers(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or any(value != 0 for value in grid[1])
        or not any(value == 5 for row in grid for value in row)
    ):
        return None
    markers = [
        (column, value)
        for column, value in enumerate(grid[0])
        if value != 0
    ]
    if (
        len(markers) < 2
        or len({color for _, color in markers}) != len(markers)
        or any(
            value not in (0, 5)
            for row in grid[2:]
            for value in row
        )
    ):
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid[2:], start=2)
        for column, value in enumerate(values)
        if value == 5
    }
    rectangles = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        if component != {
            (row, column)
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
        }:
            return None
        rectangles.append((component, (left + right) / 2))
    if len(rectangles) != len(markers):
        return None
    assignments = []
    used_markers = set()
    for component, center in rectangles:
        distances = [
            (abs(column - center), index, color)
            for index, (column, color) in enumerate(markers)
        ]
        minimum = min(distance for distance, _, _ in distances)
        closest = [
            (index, color)
            for distance, index, color in distances
            if distance == minimum
        ]
        if len(closest) != 1 or closest[0][0] in used_markers:
            return None
        index, color = closest[0]
        used_markers.add(index)
        assignments.append((component, color))
    result = [row[:] for row in grid]
    for component, color in assignments:
        for row, column in component:
            result[row][column] = color
    return result


def recolor_component_matching_five_corner_template(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 10 or len(grid[0]) != 10:
        return None
    fives = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    }
    separators = []
    for separator_row in range(2, len(grid) - 1):
        for separator_column in range(2, len(grid[0]) - 1):
            for right in range(separator_column, len(grid[0])):
                expected = {
                    (row, separator_column)
                    for row in range(separator_row + 1)
                } | {
                    (separator_row, column)
                    for column in range(right + 1)
                }
                if fives == expected:
                    separators.append(
                        (separator_row, separator_column)
                    )
    if len(separators) != 1:
        return None
    separator_row, separator_column = separators[0]
    source = {
        (row, column)
        for row in range(separator_row)
        for column in range(separator_column)
        if grid[row][column] not in (0, 5)
    }
    if (
        not source
        or len({grid[row][column] for row, column in source}) != 1
    ):
        return None

    def connected(points: set[tuple[int, int]]) -> bool:
        reached = {next(iter(points))}
        stack = list(reached)
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in points and point not in reached:
                    reached.add(point)
                    stack.append(point)
        return reached == points

    if not connected(source):
        return None

    def canonical(points: set[tuple[int, int]]) -> tuple:
        min_row = min(row for row, _ in points)
        min_column = min(column for _, column in points)
        return tuple(
            sorted(
                (row - min_row, column - min_column)
                for row, column in points
            )
        )

    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value not in (0, 5) and (row, column) not in source
    }
    components = []
    while remaining:
        start = remaining.pop()
        color = grid[start[0]][start[1]]
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if (
                    point in remaining
                    and grid[point[0]][point[1]] == color
                ):
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        components.append(component)
    source_shape = canonical(source)
    matches = [
        component
        for component in components
        if len(component) == len(source)
        and canonical(component) == source_shape
    ]
    if len(matches) != 1:
        return None
    result = [row[:] for row in grid]
    for row, column in matches[0]:
        result[row][column] = 5
    return result


def stamp_three_by_three_source_in_marked_tiles(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) % 3
        or len(grid[0]) < 7
        or (len(grid[0]) - 4) % 3
    ):
        return None
    divider_columns = [
        column
        for column in range(len(grid[0]))
        if all(row[column] == 5 for row in grid)
    ]
    if divider_columns != [3]:
        return None
    source = [row[:3] for row in grid[:3]]
    if any(value in (0, 5) for row in source for value in row):
        return None
    if any(value != 0 for row in grid[3:] for value in row[:3]):
        return None
    right_values = {
        value for row in grid for value in row[4:]
    }
    if not right_values.issubset({0, 1}):
        return None
    result = [row[:] for row in grid]
    marked = 0
    for top in range(0, len(grid), 3):
        for left in range(4, len(grid[0]), 3):
            marker_count = sum(
                grid[row][column] == 1
                for row in range(top, top + 3)
                for column in range(left, left + 3)
            )
            if marker_count > 1:
                return None
            if marker_count:
                for delta_row, values in enumerate(source):
                    for delta_column, value in enumerate(values):
                        result[top + delta_row][
                            left + delta_column
                        ] = value
                marked += 1
    return result if marked else None


def move_three_by_three_two_block_to_next_three_marker(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 2, 3}:
        return None
    twos = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 2
    }
    if len(twos) != 8:
        return None
    rows = [row for row, _ in twos]
    columns = [column for _, column in twos]
    top, bottom = min(rows), max(rows)
    left, right = min(columns), max(columns)
    if bottom - top != 2 or right - left != 2:
        return None
    center = (top + 1, left + 1)
    expected_twos = {
        (row, column)
        for row in range(top, bottom + 1)
        for column in range(left, right + 1)
        if (row, column) != center
    }
    if twos != expected_twos or grid[center[0]][center[1]] != 3:
        return None
    threes = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 3
    }
    if len(threes) < 2:
        return None
    if all(row == center[0] for row, _ in threes):
        candidates = [
            column
            for row, column in threes
            if column > center[1]
        ]
        if not candidates:
            return None
        target = (center[0], min(candidates))
    elif all(column == center[1] for _, column in threes):
        candidates = [
            row
            for row, column in threes
            if row > center[0]
        ]
        if not candidates:
            return None
        target = (min(candidates), center[1])
    else:
        return None
    target_top, target_left = target[0] - 1, target[1] - 1
    if (
        target_top < 0
        or target_left < 0
        or target_top + 3 > len(grid)
        or target_left + 3 > len(grid[0])
    ):
        return None
    result = [row[:] for row in grid]
    for row in range(top, bottom + 1):
        for column in range(left, right + 1):
            result[row][column] = 0
    result[center[0]][center[1]] = 3
    for row in range(target_top, target_top + 3):
        for column in range(target_left, target_left + 3):
            is_center = (row, column) == target
            if is_center:
                if result[row][column] != 3:
                    return None
            elif result[row][column] != 0:
                return None
    for row in range(target_top, target_top + 3):
        for column in range(target_left, target_left + 3):
            result[row][column] = 2
    result[target[0]][target[1]] = 3
    return result


def extend_singleton_rows_alternating_color_five(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row} - {0}
    if not colors or 5 in colors:
        return None
    sources = []
    for row, values in enumerate(grid):
        points = [
            column
            for column, value in enumerate(values)
            if value != 0
        ]
        if len(points) > 1:
            return None
        if len(points) == 1:
            column = points[0]
            sources.append((row, column, grid[row][column]))
    if not sources:
        return None
    result = [row[:] for row in grid]
    for row, column, color in sources:
        for target_column in range(column, len(grid[0])):
            result[row][target_column] = (
                color if (target_column - column) % 2 == 0 else 5
            )
    return result


def move_three_one_step_toward_four(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 3, 4}:
        return None
    threes = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 3
    ]
    fours = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 4
    ]
    if len(threes) != 1 or len(fours) != 1:
        return None
    row, column = threes[0]
    target_row, target_column = fours[0]
    delta_row = (target_row > row) - (target_row < row)
    delta_column = (target_column > column) - (target_column < column)
    moved = (row + delta_row, column + delta_column)
    if moved == (target_row, target_column):
        return None
    result = [values[:] for values in grid]
    result[row][column] = 0
    result[moved[0]][moved[1]] = 3
    return result


def copy_three_by_three_shape_to_five_center(
    grid: Grid,
) -> Grid | None:
    fives = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    ]
    if len(fives) != 1:
        return None
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value not in (0, 5)
    ]
    if len(points) < 3:
        return None
    top = min(row for row, _ in points)
    bottom = max(row for row, _ in points)
    left = min(column for _, column in points)
    right = max(column for _, column in points)
    if bottom - top != 2 or right - left != 2:
        return None
    source = [
        row[left : right + 1]
        for row in grid[top : bottom + 1]
    ]
    if len({value for row in source for value in row} - {0}) < 2:
        return None
    source_points = {
        (row, column)
        for row, values in enumerate(source)
        for column, value in enumerate(values)
        if value != 0
    }
    reached = {next(iter(source_points))}
    stack = list(reached)
    while stack:
        row, column = stack.pop()
        for point in (
            (row - 1, column),
            (row + 1, column),
            (row, column - 1),
            (row, column + 1),
        ):
            if point in source_points and point not in reached:
                reached.add(point)
                stack.append(point)
    if reached != source_points:
        return None
    target_row, target_column = fives[0]
    target_top, target_left = target_row - 1, target_column - 1
    if (
        target_top < 0
        or target_left < 0
        or target_top + 3 > len(grid)
        or target_left + 3 > len(grid[0])
    ):
        return None
    for delta_row in range(3):
        for delta_column in range(3):
            value = grid[target_top + delta_row][
                target_left + delta_column
            ]
            if (delta_row, delta_column) == (1, 1):
                if value != 5:
                    return None
            elif value != 0:
                return None
    result = [row[:] for row in grid]
    for delta_row, values in enumerate(source):
        for delta_column, value in enumerate(values):
            result[target_top + delta_row][
                target_left + delta_column
            ] = value
    return result


def move_two_shape_to_touch_solid_eight_square(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 2, 8}:
        return None
    moving = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 2
    }
    target = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 8
    }
    if len(moving) < 3 or len(target) != 4:
        return None
    target_rows = [row for row, _ in target]
    target_columns = [column for _, column in target]
    target_top, target_bottom = min(target_rows), max(target_rows)
    target_left, target_right = min(target_columns), max(target_columns)
    if (
        target_bottom - target_top != 1
        or target_right - target_left != 1
        or target
        != {
            (target_top, target_left),
            (target_top, target_right),
            (target_bottom, target_left),
            (target_bottom, target_right),
        }
    ):
        return None

    def distance(points: set[tuple[int, int]]) -> int:
        return min(
            abs(row - other_row) + abs(column - other_column)
            for row, column in points
            for other_row, other_column in target
        )

    current_distance = distance(moving)
    if current_distance <= 1:
        return None
    candidates = []
    for delta_row, delta_column in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        translated = {
            (row + delta_row, column + delta_column)
            for row, column in moving
        }
        if (
            all(
                0 <= row < len(grid)
                and 0 <= column < len(grid[0])
                for row, column in translated
            )
            and translated.isdisjoint(target)
            and distance(translated) < current_distance
        ):
            candidates.append((delta_row, delta_column))
    if len(candidates) != 1:
        return None
    delta_row, delta_column = candidates[0]
    shifted = set(moving)
    while distance(shifted) > 1:
        shifted = {
            (row + delta_row, column + delta_column)
            for row, column in shifted
        }
        if (
            not all(
                0 <= row < len(grid)
                and 0 <= column < len(grid[0])
                for row, column in shifted
            )
            or not shifted.isdisjoint(target)
        ):
            return None
    result = [row[:] for row in grid]
    for row, column in moving:
        result[row][column] = 0
    for row, column in shifted:
        result[row][column] = 2
    return result


def fill_most_occupied_three_by_three_panels(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 11 or len(grid[0]) != 11:
        return None
    separators = {
        (row, column)
        for row in (3, 7)
        for column in range(11)
    } | {
        (row, column)
        for row in range(11)
        for column in (3, 7)
    }
    fives = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    }
    colors = {value for row in grid for value in row} - {0, 5}
    if fives != separators or len(colors) != 1:
        return None
    color = next(iter(colors))
    panels = []
    for top in (0, 4, 8):
        for left in (0, 4, 8):
            count = sum(
                grid[row][column] == color
                for row in range(top, top + 3)
                for column in range(left, left + 3)
            )
            panels.append((count, top, left))
    maximum = max(count for count, _, _ in panels)
    if maximum < 2 or all(count == maximum for count, _, _ in panels):
        return None
    result = [row[:] for row in grid]
    for _, top, left in panels:
        for row in range(top, top + 3):
            for column in range(left, left + 3):
                result[row][column] = 0
    for count, top, left in panels:
        if count == maximum:
            for row in range(top, top + 3):
                for column in range(left, left + 3):
                    result[row][column] = color
    return result


def project_one_three_rows_and_two_columns(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row} - {0}
    if (
        not colors
        or not colors.issubset({1, 2, 3})
        or 2 not in colors
        or not colors.intersection({1, 3})
    ):
        return None
    points = [
        (row, column, value)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    ]
    if any(
        any(
            abs(row - other_row) + abs(column - other_column) == 1
            for other_row, other_column, _ in points
            if (other_row, other_column) != (row, column)
        )
        for row, column, _ in points
    ):
        return None
    result = [[0] * len(grid[0]) for _ in grid]
    for _, column, color in points:
        if color == 2:
            for row in range(len(grid)):
                result[row][column] = 2
    for row, _, color in points:
        if color in (1, 3):
            result[row] = [color] * len(grid[0])
    return result


def extend_rows_by_reference_two_color_pattern(
    grid: Grid,
) -> Grid | None:
    full_rows = [
        row
        for row, values in enumerate(grid)
        if all(value != 0 for value in values)
    ]
    if len(full_rows) != 1:
        return None
    reference_row = full_rows[0]
    reference = grid[reference_row]
    reference_colors = []
    for value in reference:
        if value not in reference_colors:
            reference_colors.append(value)
    if len(reference_colors) != 2:
        return None
    result = [row[:] for row in grid]
    expanded = 0
    for row, values in enumerate(grid):
        if row == reference_row or not any(value != 0 for value in values):
            continue
        last = max(index for index, value in enumerate(values) if value)
        if any(values[index] == 0 for index in range(last + 1)):
            return None
        mapping = {}
        reverse = {}
        for source, target in zip(
            reference[: last + 1],
            values[: last + 1],
        ):
            if (
                source in mapping and mapping[source] != target
                or target in reverse and reverse[target] != source
            ):
                return None
            mapping[source] = target
            reverse[target] = source
        if len(mapping) != 2:
            return None
        result[row] = [mapping[value] for value in reference]
        expanded += 1
    return result if expanded else None


def fill_eight_bounding_box_holes_two(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 8}:
        return None
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 8
    ]
    top = min(row for row, _ in points)
    bottom = max(row for row, _ in points)
    left = min(column for _, column in points)
    right = max(column for _, column in points)
    if bottom == top or right == left:
        return None
    result = [row[:] for row in grid]
    changed = False
    for row in range(top, bottom + 1):
        for column in range(left, right + 1):
            if result[row][column] == 0:
                result[row][column] = 2
                changed = True
    return result if changed else None


def recolor_alternating_down_right_runs_four(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row} - {0}
    if len(colors) != 1 or 4 in colors:
        return None
    color = next(iter(colors))
    points = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == color
    }
    starts = sorted(
        point
        for point in points
        if (point[0] - 1, point[1] - 1) not in points
    )
    runs = []
    covered = set()
    for start in starts:
        run = []
        row, column = start
        while (row, column) in points:
            run.append((row, column))
            covered.add((row, column))
            row += 1
            column += 1
        runs.append(run)
    if covered != points or not runs or any(len(run) < 2 for run in runs):
        return None
    result = [row[:] for row in grid]
    changed = False
    for run in runs:
        for index, (row, column) in enumerate(run):
            if index % 2:
                result[row][column] = 4
                changed = True
    return result if changed else None


def mark_full_line_intersection_neighborhood_four(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if any(value == 4 for row in grid for value in row):
        return None
    full_rows = [
        row for row, values in enumerate(grid)
        if all(value != 0 for value in values)
    ]
    full_columns = [
        column for column in range(width)
        if all(grid[row][column] != 0 for row in range(height))
    ]
    if len(full_rows) != 1 or len(full_columns) != 1:
        return None
    row, column = full_rows[0], full_columns[0]
    if row in (0, height - 1) or column in (0, width - 1):
        return None
    result = [values[:] for values in grid]
    center = grid[row][column]
    for target_row in range(row - 1, row + 2):
        for target_column in range(column - 1, column + 2):
            result[target_row][target_column] = 4
    result[row][column] = center
    return result


def shift_singleton_down_fill_above_parity_four(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    ]
    if len(points) != 1:
        return None
    row, column = points[0]
    color = grid[row][column]
    if color == 4 or row + 1 >= height:
        return None
    result = [[0 for _ in range(width)] for _ in range(height)]
    for target_row in range(row + 1):
        for target_column in range(column % 2, width, 2):
            result[target_row][target_column] = 4
    result[row + 1][column] = color
    return result


def place_three_plus_at_midpoint_between_ones(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if {value for row in grid for value in row} != {0, 1}:
        return None
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 1
    ]
    if len(points) != 2:
        return None
    first, second = points
    if first[0] == second[0]:
        if (first[1] + second[1]) % 2:
            return None
        center = (first[0], (first[1] + second[1]) // 2)
    elif first[1] == second[1]:
        if (first[0] + second[0]) % 2:
            return None
        center = ((first[0] + second[0]) // 2, first[1])
    else:
        return None
    row, column = center
    plus = {
        (row, column),
        (row - 1, column),
        (row + 1, column),
        (row, column - 1),
        (row, column + 1),
    }
    if (
        not all(
            0 <= target_row < height and 0 <= target_column < width
            for target_row, target_column in plus
        )
        or plus.intersection(points)
        or any(grid[target_row][target_column] != 0
               for target_row, target_column in plus)
    ):
        return None
    result = [values[:] for values in grid]
    for target_row, target_column in plus:
        result[target_row][target_column] = 3
    return result


def fill_enclosed_zero_regions_one(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if {value for row in grid for value in row} != {0, 2}:
        return None
    exterior = set()
    stack = []
    for row in range(height):
        for column in (0, width - 1):
            if grid[row][column] == 0:
                exterior.add((row, column))
                stack.append((row, column))
    for column in range(width):
        for row in (0, height - 1):
            if grid[row][column] == 0 and (row, column) not in exterior:
                exterior.add((row, column))
                stack.append((row, column))
    while stack:
        row, column = stack.pop()
        for target in (
            (row - 1, column),
            (row + 1, column),
            (row, column - 1),
            (row, column + 1),
        ):
            target_row, target_column = target
            if (
                0 <= target_row < height
                and 0 <= target_column < width
                and target not in exterior
                and grid[target_row][target_column] == 0
            ):
                exterior.add(target)
                stack.append(target)
    result = [values[:] for values in grid]
    changed = False
    for row in range(height):
        for column in range(width):
            if grid[row][column] == 0 and (row, column) not in exterior:
                result[row][column] = 1
                changed = True
    return result if changed else None


def connect_aligned_eights_with_threes_any_size(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if {value for row in grid for value in row} != {0, 8}:
        return None
    points = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 8
    }
    if not points:
        return None
    result = [values[:] for values in grid]
    for row in range(height):
        columns = sorted(
            column for point_row, column in points if point_row == row
        )
        if len(columns) >= 2:
            for column in range(columns[0] + 1, columns[-1]):
                if result[row][column] == 0:
                    result[row][column] = 3
    for column in range(width):
        rows = sorted(
            row for row, point_column in points if point_column == column
        )
        if len(rows) >= 2:
            for row in range(rows[0] + 1, rows[-1]):
                if result[row][column] == 0:
                    result[row][column] = 3
    return result


def draw_four_l_path_between_eight_and_two(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 2, 8}:
        return None
    eights = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 8
    ]
    twos = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 2
    ]
    if len(eights) != 1 or len(twos) != 1:
        return None
    eight_row, eight_column = eights[0]
    two_row, two_column = twos[0]
    if eight_row == two_row or eight_column == two_column:
        return None
    path = {
        (row, eight_column)
        for row in range(
            min(eight_row, two_row),
            max(eight_row, two_row) + 1,
        )
    } | {
        (two_row, column)
        for column in range(
            min(eight_column, two_column),
            max(eight_column, two_column) + 1,
        )
    }
    path -= {(eight_row, eight_column), (two_row, two_column)}
    if (
        not path
        or any(grid[row][column] != 0 for row, column in path)
    ):
        return None
    result = [values[:] for values in grid]
    for row, column in path:
        result[row][column] = 4
    return result


def _enclosed_zero_components_list(
    grid: Grid,
) -> list[set[tuple[int, int]]]:
    height, width = len(grid), len(grid[0])
    exterior = set()
    stack = []
    for row in range(height):
        for column in (0, width - 1):
            if grid[row][column] == 0 and (row, column) not in exterior:
                exterior.add((row, column))
                stack.append((row, column))
    for column in range(width):
        for row in (0, height - 1):
            if grid[row][column] == 0 and (row, column) not in exterior:
                exterior.add((row, column))
                stack.append((row, column))
    while stack:
        row, column = stack.pop()
        for target in (
            (row - 1, column),
            (row + 1, column),
            (row, column - 1),
            (row, column + 1),
        ):
            target_row, target_column = target
            if (
                0 <= target_row < height
                and 0 <= target_column < width
                and grid[target_row][target_column] == 0
                and target not in exterior
            ):
                exterior.add(target)
                stack.append(target)
    remaining = {
        (row, column)
        for row in range(height)
        for column in range(width)
        if grid[row][column] == 0 and (row, column) not in exterior
    }
    components = []
    while remaining:
        seed = remaining.pop()
        component = {seed}
        stack = [seed]
        while stack:
            row, column = stack.pop()
            for target in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if target in remaining:
                    remaining.remove(target)
                    component.add(target)
                    stack.append(target)
        components.append(component)
    return components


def fill_square_enclosed_zero_regions_two(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 12
        or len(grid[0]) != 12
        or {value for row in grid for value in row} != {0, 5}
    ):
        return None
    components = _enclosed_zero_components_list(grid)
    if len(components) not in (2, 3):
        return None
    result = [values[:] for values in grid]
    for component in components:
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        height = max(rows) - min(rows) + 1
        width = max(columns) - min(columns) + 1
        if height == width and len(component) == height * width:
            for row, column in component:
                result[row][column] = 2
    return result


def fill_square_five_interiors_by_side(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 12
        or len(grid[0]) != 12
        or {value for row in grid for value in row} != {0, 5}
    ):
        return None
    components = _enclosed_zero_components_list(grid)
    if len(components) not in (2, 3):
        return None
    result = [values[:] for values in grid]
    for component in components:
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        height = max(rows) - min(rows) + 1
        width = max(columns) - min(columns) + 1
        if (
            height != width
            or len(component) != height * width
            or not 1 <= height <= 4
        ):
            return None
        for row, column in component:
            result[row][column] = 5 + height
    return result


def bounce_diagonal_eight_ray_off_two_wall_three(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if (
        (height, width) != (12, 12)
        or {value for row in grid for value in row} != {0, 2, 8}
    ):
        return None
    walls = []
    wall_columns = [
        column for column in range(width)
        if all(grid[row][column] == 2 for row in range(height))
    ]
    if (
        wall_columns
        and all(
            wall_columns[index + 1] == wall_columns[index] + 1
            for index in range(len(wall_columns) - 1)
        )
        and (wall_columns[0] == 0 or wall_columns[-1] == width - 1)
        and all(
            (grid[row][column] == 2) == (column in wall_columns)
            for row in range(height)
            for column in range(width)
        )
    ):
        walls.append("vertical")
    wall_rows = [
        row for row in range(height)
        if all(grid[row][column] == 2 for column in range(width))
    ]
    if (
        wall_rows
        and all(
            wall_rows[index + 1] == wall_rows[index] + 1
            for index in range(len(wall_rows) - 1)
        )
        and (wall_rows[0] == 0 or wall_rows[-1] == height - 1)
        and all(
            (grid[row][column] == 2) == (row in wall_rows)
            for row in range(height)
            for column in range(width)
        )
    ):
        walls.append("horizontal")
    if len(walls) != 1:
        return None
    points = sorted(
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 8
    )
    if len(points) < 2:
        return None
    column_step = points[1][1] - points[0][1]
    if (
        column_step not in (-1, 1)
        or any(
            points[index + 1][0] - points[index][0] != 1
            or points[index + 1][1] - points[index][1] != column_step
            for index in range(len(points) - 1)
        )
    ):
        return None
    wall_rays = []
    for endpoint, row_step, endpoint_column_step in (
        (points[0], -1, -column_step),
        (points[-1], 1, column_step),
    ):
        row, column = endpoint
        cells = []
        hit_wall = False
        while True:
            row += row_step
            column += endpoint_column_step
            if not (0 <= row < height and 0 <= column < width):
                break
            if grid[row][column] == 2:
                hit_wall = True
                break
            if grid[row][column] != 0:
                break
            cells.append((row, column))
        if hit_wall:
            wall_rays.append((cells, row_step, endpoint_column_step))
    if len(wall_rays) != 1 or not wall_rays[0][0]:
        return None
    cells, row_step, column_step = wall_rays[0]
    result = [values[:] for values in grid]
    for row, column in cells:
        result[row][column] = 3
    row, column = cells[-1]
    if walls[0] == "vertical":
        column_step = -column_step
    else:
        row_step = -row_step
    while True:
        row += row_step
        column += column_step
        if (
            not 0 <= row < height
            or not 0 <= column < width
            or result[row][column] != 0
        ):
            break
        result[row][column] = 3
    return result


def expand_two_small_pluses_to_five_by_five(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if (height, width) != (12, 12):
        return None
    colors = {value for row in grid for value in row} - {0}
    if len(colors) != 2:
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    }
    components = []
    while remaining:
        seed = remaining.pop()
        component = {seed}
        stack = [seed]
        while stack:
            row, column = stack.pop()
            for target in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if target in remaining:
                    remaining.remove(target)
                    component.add(target)
                    stack.append(target)
        components.append(component)
    if len(components) != 2:
        return None
    pluses = []
    for component in components:
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        center_row = (min(rows) + max(rows)) // 2
        center_column = (min(columns) + max(columns)) // 2
        center = (center_row, center_column)
        expected = {
            center,
            (center_row - 1, center_column),
            (center_row + 1, center_column),
            (center_row, center_column - 1),
            (center_row, center_column + 1),
        }
        if component != expected:
            return None
        center_color = grid[center_row][center_column]
        arm_colors = {
            grid[row][column]
            for row, column in component - {center}
        }
        if len(arm_colors) != 1 or center_color in arm_colors:
            return None
        pluses.append(
            (
                center_row,
                center_column,
                center_color,
                next(iter(arm_colors)),
            )
        )
    if len({plus[2:] for plus in pluses}) != 1:
        return None
    result = [values[:] for values in grid]
    changed = False
    for center_row, center_column, center_color, arm_color in pluses:
        targets = []
        for distance in (1, 2):
            targets.extend(
                (
                    center_row + delta_row,
                    center_column + delta_column,
                    center_color,
                )
                for delta_row, delta_column in (
                    (-distance, -distance),
                    (-distance, distance),
                    (distance, -distance),
                    (distance, distance),
                )
            )
        targets.extend(
            (
                (center_row - 2, center_column, arm_color),
                (center_row + 2, center_column, arm_color),
                (center_row, center_column - 2, arm_color),
                (center_row, center_column + 2, arm_color),
            )
        )
        for row, column, color in targets:
            if (
                not 0 <= row < height
                or not 0 <= column < width
                or result[row][column] not in (0, color)
            ):
                return None
            if result[row][column] == 0:
                result[row][column] = color
                changed = True
    return result if changed else None


def recolor_five_cells_by_row_guide(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if (height, width) != (12, 12):
        return None
    colors = {value for row in grid for value in row}
    if 0 not in colors or 5 not in colors or len(colors) < 4:
        return None
    result = [values[:] for values in grid]
    guide_colors = set()
    changed = False
    for row, values in enumerate(grid):
        if 5 not in values:
            continue
        guides = set(values) - {0, 5}
        if len(guides) != 1:
            return None
        color = next(iter(guides))
        guide_colors.add(color)
        for column, value in enumerate(values):
            if value == 5:
                result[row][column] = color
                changed = True
    if not changed or len(guide_colors) < 2:
        return None
    return result


def project_contained_color_from_opposite_bbox_corners(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    colors = {value for row in grid for value in row} - {0}
    if len(colors) != 2:
        return None
    assignments = []
    for frame_color in colors:
        payload_color = next(iter(colors - {frame_color}))
        frame = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == frame_color
        ]
        payload = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == payload_color
        ]
        top = min(row for row, _ in frame)
        bottom = max(row for row, _ in frame)
        left = min(column for _, column in frame)
        right = max(column for _, column in frame)
        if bottom == top or right == left:
            continue
        if not all(
            top <= row <= bottom and left <= column <= right
            for row, column in payload
        ):
            continue
        assignments.append(
            (payload_color, top, bottom, left, right, payload)
        )
    if len(assignments) != 1:
        return None
    payload_color, top, bottom, left, right, payload = assignments[0]
    payload_row = sum(row for row, _ in payload) / len(payload)
    payload_column = sum(column for _, column in payload) / len(payload)
    box_row = (top + bottom) / 2
    box_column = (left + right) / 2
    corner_rows = (
        [bottom] if payload_row < box_row
        else [top] if payload_row > box_row
        else [top, bottom]
    )
    corner_columns = (
        [right] if payload_column < box_column
        else [left] if payload_column > box_column
        else [left, right]
    )
    result = [values[:] for values in grid]
    changed = False
    for corner_row in corner_rows:
        for corner_column in corner_columns:
            row_step = -1 if corner_row == top else 1
            column_step = -1 if corner_column == left else 1
            row = corner_row + row_step
            column = corner_column + column_step
            while 0 <= row < height and 0 <= column < width:
                if result[row][column] != 0:
                    return None
                result[row][column] = payload_color
                changed = True
                row += row_step
                column += column_step
    return result if changed else None


def fill_occupied_columns_eight_then_tile_two_by_two(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    colors = {value for row in grid for value in row} - {0}
    if len(colors) != 1 or 8 in colors:
        return None
    occupied_columns = [
        column for column in range(width)
        if any(grid[row][column] != 0 for row in range(height))
    ]
    if not occupied_columns:
        return None
    tile = [values[:] for values in grid]
    for column in occupied_columns:
        for row in range(height):
            if tile[row][column] == 0:
                tile[row][column] = 8
    horizontal = [values + values for values in tile]
    return horizontal + [values[:] for values in horizontal]


def draw_alternating_two_step_five_arms_from_singleton(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    ]
    if (height, width) != (13, 13) or len(points) != 1:
        return None
    source_row, source_column = points[0]
    color = grid[source_row][source_column]
    if color == 5:
        return None
    result = [[0 for _ in range(width)] for _ in range(height)]
    result[source_row][source_column] = color
    for directions in (
        ((-1, 0), (0, 1)),
        ((1, 0), (0, -1)),
    ):
        row, column = source_row, source_column
        for segment in range(2 * max(height, width)):
            delta_row, delta_column = directions[segment % 2]
            complete = True
            for _ in range(2):
                target_row = row + delta_row
                target_column = column + delta_column
                if not (
                    0 <= target_row < height
                    and 0 <= target_column < width
                ):
                    complete = False
                    break
                row, column = target_row, target_column
                result[row][column] = 5
            if not complete:
                break
    return result


def complete_dense_rows_columns_with_two(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if {value for row in grid for value in row} != {0, 1}:
        return None
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 1
    ]
    top = min(row for row, _ in points)
    bottom = max(row for row, _ in points)
    left = min(column for _, column in points)
    right = max(column for _, column in points)
    result = [values[:] for values in grid]
    changed = False
    for row, values in enumerate(grid):
        if sum(value == 1 for value in values) < 4:
            continue
        for column in range(left, right + 1):
            if result[row][column] == 0:
                result[row][column] = 2
                changed = True
    for column in range(width):
        if sum(grid[row][column] == 1 for row in range(height)) < 4:
            continue
        for row in range(top, bottom + 1):
            if result[row][column] == 0:
                result[row][column] = 2
                changed = True
    return result if changed else None


def extend_marker_ray_from_opposite_object_side(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    colors = {value for row in grid for value in row} - {0}
    if len(colors) != 2:
        return None
    counts = {
        color: sum(
            value == color for row in grid for value in row
        )
        for color in colors
    }
    singleton_colors = [
        color for color, count in counts.items() if count == 1
    ]
    if len(singleton_colors) != 1:
        return None
    marker = singleton_colors[0]
    marker_row, marker_column = next(
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == marker
    )
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    ]
    top = min(row for row, _ in points)
    bottom = max(row for row, _ in points)
    left = min(column for _, column in points)
    right = max(column for _, column in points)
    sides = []
    if marker_row == top:
        sides.append("top")
    if marker_row == bottom:
        sides.append("bottom")
    if marker_column == left:
        sides.append("left")
    if marker_column == right:
        sides.append("right")
    if len(sides) != 1:
        return None
    if sides[0] == "top":
        ray = [
            (row, marker_column)
            for row in range(bottom + 1, height)
        ]
    elif sides[0] == "bottom":
        ray = [
            (row, marker_column)
            for row in range(top - 1, -1, -1)
        ]
    elif sides[0] == "left":
        ray = [
            (marker_row, column)
            for column in range(right + 1, width)
        ]
    else:
        ray = [
            (marker_row, column)
            for column in range(left - 1, -1, -1)
        ]
    if (
        not ray
        or any(grid[row][column] != 0 for row, column in ray)
    ):
        return None
    result = [values[:] for values in grid]
    for row, column in ray:
        result[row][column] = marker
    return result


def fill_solid_rectangle_interiors_eight(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row} - {0}
    if not colors or 8 in colors:
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    }
    components = []
    while remaining:
        seed = remaining.pop()
        component = {seed}
        stack = [seed]
        while stack:
            row, column = stack.pop()
            for target in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if target in remaining:
                    remaining.remove(target)
                    component.add(target)
                    stack.append(target)
        components.append(component)
    if len(components) < 2:
        return None
    result = [values[:] for values in grid]
    changed = False
    for component in components:
        component_colors = {
            grid[row][column] for row, column in component
        }
        if len(component_colors) != 1:
            return None
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        if len(component) != (bottom - top + 1) * (right - left + 1):
            return None
        if bottom - top >= 2 and right - left >= 2:
            for row in range(top + 1, bottom):
                for column in range(left + 1, right):
                    result[row][column] = 8
            changed = True
    return result if changed else None


def render_eight_component_count_diagonal(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 8}:
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 8
    }
    count = 0
    while remaining:
        seed = remaining.pop()
        stack = [seed]
        count += 1
        while stack:
            row, column = stack.pop()
            for target in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if target in remaining:
                    remaining.remove(target)
                    stack.append(target)
    if not count:
        return None
    return [
        [8 if row == column else 0 for column in range(count)]
        for row in range(count)
    ]


def rank_nonmodal_colors_by_frequency_column(
    grid: Grid,
) -> Grid | None:
    counts = {}
    for row in grid:
        for value in row:
            if value != 0:
                counts[value] = counts.get(value, 0) + 1
    if len(counts) != 4:
        return None
    ranked = sorted(
        counts.items(),
        key=lambda item: (-item[1], item[0]),
    )
    if ranked[0][1] <= ranked[1][1]:
        return None
    return [[color] for color, _ in ranked[1:]]


def read_color_bands_by_centroid_order(
    grid: Grid,
) -> Grid | None:
    colors = sorted({value for row in grid for value in row})
    if 0 in colors or len(colors) < 3:
        return None
    centroids = []
    for color in colors:
        points = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ]
        centroids.append(
            (
                color,
                sum(row for row, _ in points) / len(points),
                sum(column for _, column in points) / len(points),
            )
        )
    row_range = (
        max(item[1] for item in centroids)
        - min(item[1] for item in centroids)
    )
    column_range = (
        max(item[2] for item in centroids)
        - min(item[2] for item in centroids)
    )
    if row_range == column_range:
        return None
    axis = 1 if row_range > column_range else 2
    ordered = [
        item[0] for item in sorted(centroids, key=lambda item: item[axis])
    ]
    if axis == 1:
        return [[color] for color in ordered]
    return [ordered]


def extract_mixed_component_recolor_dominant(
    grid: Grid,
) -> Grid | None:
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    }
    components = []
    while remaining:
        seed = remaining.pop()
        component = {seed}
        stack = [seed]
        while stack:
            row, column = stack.pop()
            for target in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if target in remaining:
                    remaining.remove(target)
                    component.add(target)
                    stack.append(target)
        components.append(component)
    mixed = []
    for component in components:
        component_colors = [
            grid[row][column] for row, column in component
        ]
        if len(set(component_colors)) > 1:
            mixed.append((component, component_colors))
    if len(mixed) != 1:
        return None
    component, component_colors = mixed[0]
    counts = {}
    for color in component_colors:
        counts[color] = counts.get(color, 0) + 1
    if len(counts) != 2 or len(set(counts.values())) != 2:
        return None
    dominant = max(counts, key=counts.get)
    rows = [row for row, _ in component]
    columns = [column for _, column in component]
    top, bottom = min(rows), max(rows)
    left, right = min(columns), max(columns)
    result = [
        [0 for _ in range(right - left + 1)]
        for _ in range(bottom - top + 1)
    ]
    for row, column in component:
        result[row - top][column - left] = dominant
    return result


def extend_two_color_rectangle_to_marker_eight(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row} - {0}
    if (
        len(colors) != 3
        or 8 not in colors
        or sum(value == 8 for row in grid for value in row) != 1
    ):
        return None
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value not in (0, 8)
    ]
    top = min(row for row, _ in points)
    bottom = max(row for row, _ in points)
    left = min(column for _, column in points)
    right = max(column for _, column in points)
    rectangle_colors = colors - {8}
    outer = grid[top][left]
    if outer not in rectangle_colors:
        return None
    inner_colors = rectangle_colors - {outer}
    if len(inner_colors) != 1:
        return None
    inner = next(iter(inner_colors))
    for row in range(top, bottom + 1):
        for column in range(left, right + 1):
            expected = (
                outer
                if row in (top, bottom) or column in (left, right)
                else inner
            )
            if grid[row][column] != expected:
                return None
    marker_row, marker_column = next(
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 8
    )
    sides = []
    if marker_row < top and left <= marker_column <= right:
        sides.append("top")
    if marker_row > bottom and left <= marker_column <= right:
        sides.append("bottom")
    if marker_column < left and top <= marker_row <= bottom:
        sides.append("left")
    if marker_column > right and top <= marker_row <= bottom:
        sides.append("right")
    if len(sides) != 1:
        return None
    if sides[0] == "top":
        top = marker_row
    elif sides[0] == "bottom":
        bottom = marker_row
    elif sides[0] == "left":
        left = marker_column
    else:
        right = marker_column
    result = [values[:] for values in grid]
    for row in range(top, bottom + 1):
        for column in range(left, right + 1):
            result[row][column] = (
                outer
                if row in (top, bottom) or column in (left, right)
                else inner
            )
    return result


def draw_outer_rectangle_one_inside_four_five_markers(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row} - {0, 5}
    markers = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    ]
    if len(colors) != 1 or len(markers) != 4:
        return None
    color = next(iter(colors))
    top_marker = min(markers, key=lambda point: point[0])
    bottom_marker = max(markers, key=lambda point: point[0])
    left_marker = min(markers, key=lambda point: point[1])
    right_marker = max(markers, key=lambda point: point[1])
    if len({top_marker, bottom_marker, left_marker, right_marker}) != 4:
        return None
    top = top_marker[0] + 1
    bottom = bottom_marker[0] - 1
    left = left_marker[1] + 1
    right = right_marker[1] - 1
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == color
    ]
    inner_top = min(row for row, _ in points)
    inner_bottom = max(row for row, _ in points)
    inner_left = min(column for _, column in points)
    inner_right = max(column for _, column in points)
    if not (
        top < inner_top <= inner_bottom < bottom
        and left < inner_left <= inner_right < right
    ):
        return None
    result = [values[:] for values in grid]
    for column in range(left, right + 1):
        result[top][column] = color
        result[bottom][column] = color
    for row in range(top, bottom + 1):
        result[row][left] = color
        result[row][right] = color
    return result


def denoise_uniform_row_or_column_bands(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    candidates = []
    row_result = [[0 for _ in range(width)] for _ in range(height)]
    valid = True
    for row, values in enumerate(grid):
        counts = {}
        for value in values:
            counts[value] = counts.get(value, 0) + 1
        maximum = max(counts.values())
        modes = [
            color for color, count in counts.items() if count == maximum
        ]
        if len(modes) != 1:
            valid = False
            break
        row_result[row] = [modes[0] for _ in range(width)]
    if valid:
        candidates.append(
            (
                sum(
                    row_result[row][column] != grid[row][column]
                    for row in range(height)
                    for column in range(width)
                ),
                row_result,
            )
        )
    column_result = [[0 for _ in range(width)] for _ in range(height)]
    valid = True
    for column in range(width):
        counts = {}
        for row in range(height):
            value = grid[row][column]
            counts[value] = counts.get(value, 0) + 1
        maximum = max(counts.values())
        modes = [
            color for color, count in counts.items() if count == maximum
        ]
        if len(modes) != 1:
            valid = False
            break
        for row in range(height):
            column_result[row][column] = modes[0]
    if valid:
        candidates.append(
            (
                sum(
                    column_result[row][column] != grid[row][column]
                    for row in range(height)
                    for column in range(width)
                ),
                column_result,
            )
        )
    if not candidates:
        return None
    minimum = min(changes for changes, _ in candidates)
    best = [
        result for changes, result in candidates if changes == minimum
    ]
    if len(best) != 1 or minimum == 0:
        return None
    return best[0]


def draw_six_crosses_through_odd_one_rectangles(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if {value for row in grid for value in row} != {1, 8}:
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 1
    }
    result = [values[:] for values in grid]
    count = 0
    while remaining:
        seed = remaining.pop()
        component = {seed}
        stack = [seed]
        while stack:
            row, column = stack.pop()
            for target in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if target in remaining:
                    remaining.remove(target)
                    component.add(target)
                    stack.append(target)
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        border = {
            (row, column)
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
            if row in (top, bottom) or column in (left, right)
        }
        if (
            component != border
            or (bottom - top) % 2
            or (right - left) % 2
        ):
            return None
        center_row = (top + bottom) // 2
        center_column = (left + right) // 2
        for row in range(height):
            if result[row][center_column] == 8:
                result[row][center_column] = 6
        for column in range(width):
            if result[center_row][column] == 8:
                result[center_row][column] = 6
        count += 1
    return result if count else None


def recolor_rectangular_one_loops_three(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 1}:
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 1
    }
    result = [values[:] for values in grid]
    changed = False
    while remaining:
        seed = remaining.pop()
        component = {seed}
        stack = [seed]
        while stack:
            row, column = stack.pop()
            for target in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if target in remaining:
                    remaining.remove(target)
                    component.add(target)
                    stack.append(target)
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        border = {
            (row, column)
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
            if row in (top, bottom) or column in (left, right)
        }
        if (
            component == border
            and bottom > top + 1
            and right > left + 1
        ):
            for row, column in component:
                result[row][column] = 3
            changed = True
    return result if changed else None


def outline_six_components_three_fill_bbox_holes_four(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if {value for row in grid for value in row} != {6, 8}:
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 6
    }
    result = [values[:] for values in grid]
    count = 0
    while remaining:
        seed = remaining.pop()
        component = {seed}
        stack = [seed]
        while stack:
            row, column = stack.pop()
            for target in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if target in remaining:
                    remaining.remove(target)
                    component.add(target)
                    stack.append(target)
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        if top == 0 or left == 0 or bottom == height - 1 or right == width - 1:
            return None
        for row in range(top, bottom + 1):
            for column in range(left, right + 1):
                if result[row][column] == 8:
                    result[row][column] = 4
        for row in range(top - 1, bottom + 2):
            for column in range(left - 1, right + 2):
                if row in (top - 1, bottom + 1) or column in (
                    left - 1,
                    right + 1,
                ):
                    if result[row][column] != 8:
                        return None
                    result[row][column] = 3
        count += 1
    return result if count else None


def vertically_place_solid_rectangles_by_height(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    colors = {value for row in grid for value in row} - {0}
    if len(colors) < 2:
        return None
    result = [[0 for _ in range(width)] for _ in range(height)]
    for color in colors:
        points = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ]
        top = min(row for row, _ in points)
        bottom = max(row for row, _ in points)
        left = min(column for _, column in points)
        right = max(column for _, column in points)
        object_height = bottom - top + 1
        if len(points) != object_height * (right - left + 1):
            return None
        target_top = height - 2 * object_height
        if target_top < 0:
            return None
        for row in range(target_top, target_top + object_height):
            for column in range(left, right + 1):
                result[row][column] = color
    return result


def reflect_outside_fives_inside_two_frame(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if {value for row in grid for value in row} != {0, 2, 5}:
        return None
    twos = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 2
    ]
    top = min(row for row, _ in twos)
    bottom = max(row for row, _ in twos)
    left = min(column for _, column in twos)
    right = max(column for _, column in twos)
    targets = []
    axes = set()
    for row, values in enumerate(grid):
        for column, value in enumerate(values):
            if value != 5:
                continue
            options = []
            if row < top:
                options.append((2 * top - row, column, "vertical"))
            if row > bottom:
                options.append((2 * bottom - row, column, "vertical"))
            if column < left:
                options.append((row, 2 * left - column, "horizontal"))
            if column > right:
                options.append((row, 2 * right - column, "horizontal"))
            if len(options) != 1:
                return None
            targets.append(options[0])
            axes.add(options[0][2])
    if len(axes) != 1:
        return None
    result = [
        [0 if value == 5 else value for value in values]
        for values in grid
    ]
    for row, column, _ in targets:
        if (
            not 0 <= row < height
            or not 0 <= column < width
            or result[row][column] != 0
        ):
            return None
        result[row][column] = 5
    return result


def reflect_inside_fives_outside_two_frame(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if {value for row in grid for value in row} != {0, 2, 5}:
        return None
    twos = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 2
    ]
    top = min(row for row, _ in twos)
    bottom = max(row for row, _ in twos)
    left = min(column for _, column in twos)
    right = max(column for _, column in twos)
    fives = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    ]
    if not all(
        top < row < bottom and left < column < right
        for row, column in fives
    ):
        return None
    horizontal_border = (
        sum(value == 2 for value in grid[top])
        + sum(value == 2 for value in grid[bottom])
    )
    vertical_border = (
        sum(grid[row][left] == 2 for row in range(height))
        + sum(grid[row][right] == 2 for row in range(height))
    )
    if horizontal_border == vertical_border:
        return None
    targets = []
    for row, column in fives:
        if horizontal_border > vertical_border:
            top_distance = row - top
            bottom_distance = bottom - row
            if top_distance == bottom_distance:
                return None
            targets.append(
                (2 * top - row, column)
                if top_distance < bottom_distance
                else (2 * bottom - row, column)
            )
        else:
            left_distance = column - left
            right_distance = right - column
            if left_distance == right_distance:
                return None
            targets.append(
                (row, 2 * left - column)
                if left_distance < right_distance
                else (row, 2 * right - column)
            )
    result = [
        [0 if value == 5 else value for value in values]
        for values in grid
    ]
    for row, column in targets:
        if (
            not 0 <= row < height
            or not 0 <= column < width
            or result[row][column] != 0
        ):
            return None
        result[row][column] = 5
    return result


def collapse_aligned_arm_markers_to_one_two_centers(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    palette = {value for row in grid for value in row}
    if not palette.issubset({0, 1, 2, 3, 7}) or not ({1, 2} & palette):
        return None
    centers = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value in (1, 2)
    ]
    result = [[0 for _ in range(width)] for _ in range(height)]
    used = set()
    for center_row, center_column in centers:
        result[center_row][center_column] = grid[center_row][center_column]
        aligned = []
        for row, values in enumerate(grid):
            for column, value in enumerate(values):
                if value not in (0, 1, 2) and (
                    row == center_row or column == center_column
                ):
                    aligned.append((row, column, value))
        arm_colors = {color for _, _, color in aligned}
        if not aligned or len(arm_colors) != 1:
            return None
        arm_color = next(iter(arm_colors))
        for row, column, _ in aligned:
            if row == center_row:
                target = (
                    center_row,
                    center_column - 1 if column < center_column
                    else center_column + 1,
                )
            else:
                target = (
                    center_row - 1 if row < center_row else center_row + 1,
                    center_column,
                )
            target_row, target_column = target
            if (
                not 0 <= target_row < height
                or not 0 <= target_column < width
                or result[target_row][target_column] not in (0, arm_color)
            ):
                return None
            result[target_row][target_column] = arm_color
            used.add((row, column))
    arm_points = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value not in (0, 1, 2)
    }
    if used != arm_points:
        return None
    return result


def mark_two_by_two_fives_diagonal_corners_one_two_three_four(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if {value for row in grid for value in row} != {0, 5}:
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    }
    components = []
    while remaining:
        seed = remaining.pop()
        component = {seed}
        stack = [seed]
        while stack:
            row, column = stack.pop()
            for target in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if target in remaining:
                    remaining.remove(target)
                    component.add(target)
                    stack.append(target)
        components.append(component)
    result = [values[:] for values in grid]
    for component in components:
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        if (
            component != {
                (top, left),
                (top, right),
                (bottom, left),
                (bottom, right),
            }
            or bottom != top + 1
            or right != left + 1
        ):
            return None
        for row, column, color in (
            (top - 1, left - 1, 1),
            (top - 1, right + 1, 2),
            (bottom + 1, left - 1, 3),
            (bottom + 1, right + 1, 4),
        ):
            if 0 <= row < height and 0 <= column < width:
                if result[row][column] not in (0, color):
                    return None
                result[row][column] = color
    return result


def complete_left_line_with_bottom_four_antidiagonal_two(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if height != width:
        return None
    colors = {value for row in grid for value in row} - {0}
    if len(colors) != 1 or 2 in colors or 4 in colors:
        return None
    color = next(iter(colors))
    if (
        not all(grid[row][0] == color for row in range(height))
        or any(
            grid[row][column] != 0
            for row in range(height)
            for column in range(1, width)
        )
    ):
        return None
    result = [values[:] for values in grid]
    for column in range(1, width):
        result[-1][column] = 4
    for row in range(height - 1):
        result[row][width - 1 - row] = 2
    return result


def stamp_singletons_as_mapped_three_by_three_squares(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    mapping = {2: 1, 3: 6, 8: 4}
    colors = {value for row in grid for value in row} - {0}
    if not colors or not colors.issubset(mapping):
        return None
    result = [[0 for _ in range(width)] for _ in range(height)]
    for row, values in enumerate(grid):
        for column, source in enumerate(values):
            if source == 0:
                continue
            fill = mapping[source]
            for target_row in range(max(0, row - 1), min(height, row + 2)):
                for target_column in range(
                    max(0, column - 1), min(width, column + 2)
                ):
                    value = (
                        source
                        if (target_row, target_column) == (row, column)
                        else fill
                    )
                    if result[target_row][target_column] not in (0, value):
                        return None
                    result[target_row][target_column] = value
    return result


def restore_latin_diagonal_periodic_square(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if (height, width) != (16, 16):
        return None
    colors = {value for row in grid for value in row} - {0}
    count = max(colors) if colors else 0
    if count < 3 or colors != set(range(1, count + 1)):
        return None
    expected = [
        [(row + column) % count + 1 for column in range(width)]
        for row in range(height)
    ]
    if any(
        grid[row][column] not in (0, expected[row][column])
        for row in range(height)
        for column in range(width)
    ):
        return None
    return expected


def keep_unique_largest_solid_rectangle_in_noise(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if (
        (height, width) != (16, 16)
        or {value for row in grid for value in row} != set(range(10))
    ):
        return None
    best_area = 0
    best_boxes = []
    for color in range(1, 10):
        for top in range(height):
            valid = [True for _ in range(width)]
            for bottom in range(top, height):
                valid = [
                    valid[column] and grid[bottom][column] == color
                    for column in range(width)
                ]
                column = 0
                while column < width:
                    if not valid[column]:
                        column += 1
                        continue
                    left = column
                    while column < width and valid[column]:
                        column += 1
                    right = column - 1
                    if bottom == top or right == left:
                        continue
                    area = (bottom - top + 1) * (right - left + 1)
                    box = (color, top, bottom, left, right)
                    if area > best_area:
                        best_area = area
                        best_boxes = [box]
                    elif area == best_area:
                        best_boxes.append(box)
    best_boxes = list(dict.fromkeys(best_boxes))
    if best_area < 6 or len(best_boxes) != 1:
        return None
    color, top, bottom, left, right = best_boxes[0]
    result = [[0 for _ in range(width)] for _ in range(height)]
    for row in range(top, bottom + 1):
        for column in range(left, right + 1):
            result[row][column] = color
    return result


def tile_contiguous_active_row_pattern_by_global_phase(
    grid: Grid,
) -> Grid | None:
    height = len(grid)
    colors = {value for row in grid for value in row} - {0}
    if len(colors) != 1:
        return None
    active_rows = [
        row for row, values in enumerate(grid) if any(value != 0 for value in values)
    ]
    if (
        not active_rows
        or active_rows != list(range(active_rows[0], active_rows[-1] + 1))
    ):
        return None
    period = len(active_rows)
    phases = {
        row % period: grid[row][:]
        for row in active_rows
    }
    if len(phases) != period:
        return None
    return [phases[row % period][:] for row in range(height)]


def render_unique_nonfilled_color_one_cell(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row} - {0}
    nonfilled = []
    for color in colors:
        points = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ]
        top = min(row for row, _ in points)
        bottom = max(row for row, _ in points)
        left = min(column for _, column in points)
        right = max(column for _, column in points)
        if any(
            grid[row][column] not in (0, color)
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
        ):
            return None
        if len(points) < (bottom - top + 1) * (right - left + 1):
            nonfilled.append(color)
    if len(nonfilled) != 1:
        return None
    return [[nonfilled[0]]]


def propagate_zero_holes_across_color_bands(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row} - {0}
    if len(colors) < 2:
        return None
    result = [values[:] for values in grid]
    changed = False
    for color in colors:
        points = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ]
        top = min(row for row, _ in points)
        bottom = max(row for row, _ in points)
        left = min(column for _, column in points)
        right = max(column for _, column in points)
        holes = []
        for row in range(top, bottom + 1):
            for column in range(left, right + 1):
                if grid[row][column] not in (0, color):
                    return None
                if grid[row][column] == 0:
                    holes.append((row, column))
        if not holes:
            continue
        if right - left > bottom - top:
            for column in {column for _, column in holes}:
                for row in range(top, bottom + 1):
                    result[row][column] = 0
        elif bottom - top > right - left:
            for row in {row for row, _ in holes}:
                for column in range(left, right + 1):
                    result[row][column] = 0
        else:
            return None
        changed = True
    return result if changed else None


def pack_external_markers_adjacent_to_five_band(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    colors = {value for row in grid for value in row} - {0}
    if len(colors) != 2 or 5 not in colors:
        return None
    marker = next(iter(colors - {5}))
    fives = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    ]
    top = min(row for row, _ in fives)
    bottom = max(row for row, _ in fives)
    left = min(column for _, column in fives)
    right = max(column for _, column in fives)
    if len(fives) != (bottom - top + 1) * (right - left + 1):
        return None
    result = [[0 for _ in range(width)] for _ in range(height)]
    for row in range(top, bottom + 1):
        for column in range(left, right + 1):
            result[row][column] = 5
    markers = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == marker
    ]
    if right - left > bottom - top:
        groups = {}
        for row, column in markers:
            if not left <= column <= right or top <= row <= bottom:
                return None
            side = "above" if row < top else "below"
            key = (column, side)
            groups[key] = groups.get(key, 0) + 1
        for (column, side), count in groups.items():
            rows = (
                range(top - count, top)
                if side == "above"
                else range(bottom + 1, bottom + count + 1)
            )
            for row in rows:
                if not 0 <= row < height:
                    return None
                result[row][column] = 5
    elif bottom - top > right - left:
        groups = {}
        for row, column in markers:
            if not top <= row <= bottom or left <= column <= right:
                return None
            side = "left" if column < left else "right"
            key = (row, side)
            groups[key] = groups.get(key, 0) + 1
        for (row, side), count in groups.items():
            columns = (
                range(left - count, left)
                if side == "left"
                else range(right + 1, right + count + 1)
            )
            for column in columns:
                if not 0 <= column < width:
                    return None
                result[row][column] = 5
    else:
        return None
    return result


def move_nonsolid_color_rectangle_to_touch_solid_rectangle(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    colors = {value for row in grid for value in row} - {0}
    if len(colors) != 2:
        return None
    solid = []
    nonsolid = []
    for color in colors:
        points = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ]
        top = min(row for row, _ in points)
        bottom = max(row for row, _ in points)
        left = min(column for _, column in points)
        right = max(column for _, column in points)
        item = (color, top, bottom, left, right)
        if len(points) == (bottom - top + 1) * (right - left + 1):
            solid.append(item)
        else:
            nonsolid.append(item)
    if len(solid) != 1 or len(nonsolid) != 1:
        return None
    anchor_color, anchor_top, anchor_bottom, anchor_left, anchor_right = (
        solid[0]
    )
    moving_color = nonsolid[0][0]
    best_area = 0
    best_boxes = []
    for top in range(height):
        valid = [True for _ in range(width)]
        for bottom in range(top, height):
            valid = [
                valid[column] and grid[bottom][column] == moving_color
                for column in range(width)
            ]
            column = 0
            while column < width:
                if not valid[column]:
                    column += 1
                    continue
                left = column
                while column < width and valid[column]:
                    column += 1
                right = column - 1
                if bottom == top or right == left:
                    continue
                area = (bottom - top + 1) * (right - left + 1)
                box = (top, bottom, left, right)
                if area > best_area:
                    best_area = area
                    best_boxes = [box]
                elif area == best_area:
                    best_boxes.append(box)
    best_boxes = list(dict.fromkeys(best_boxes))
    if len(best_boxes) != 1:
        return None
    top, bottom, left, right = best_boxes[0]
    rectangle_height = bottom - top + 1
    rectangle_width = right - left + 1
    if bottom < anchor_top:
        target_top, target_left = anchor_top - rectangle_height, left
    elif top > anchor_bottom:
        target_top, target_left = anchor_bottom + 1, left
    elif right < anchor_left:
        target_top, target_left = top, anchor_left - rectangle_width
    elif left > anchor_right:
        target_top, target_left = top, anchor_right + 1
    else:
        return None
    if not (
        0 <= target_top <= height - rectangle_height
        and 0 <= target_left <= width - rectangle_width
    ):
        return None
    result = [[0 for _ in range(width)] for _ in range(height)]
    for row in range(anchor_top, anchor_bottom + 1):
        for column in range(anchor_left, anchor_right + 1):
            result[row][column] = anchor_color
    for row in range(target_top, target_top + rectangle_height):
        for column in range(target_left, target_left + rectangle_width):
            result[row][column] = moving_color
    return result


def reflect_source_across_center_x_shape(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    colors = {value for row in grid for value in row} - {0}
    if len(colors) != 2:
        return None
    centers = []
    for color in colors:
        points = {
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        }
        rows = [row for row, _ in points]
        columns = [column for _, column in points]
        center_row = (min(rows) + max(rows)) // 2
        center_column = (min(columns) + max(columns)) // 2
        expected = {
            (center_row, center_column),
            (center_row - 1, center_column - 1),
            (center_row - 1, center_column + 1),
            (center_row + 1, center_column - 1),
            (center_row + 1, center_column + 1),
        }
        if points == expected:
            centers.append((color, center_row, center_column))
    if len(centers) != 1:
        return None
    center_color, center_row, center_column = centers[0]
    source_color = next(iter(colors - {center_color}))
    result = [values[:] for values in grid]
    source_points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == source_color
    ]
    for row, column in source_points:
        for target_row, target_column in (
            (row, column),
            (2 * center_row - row, column),
            (row, 2 * center_column - column),
            (2 * center_row - row, 2 * center_column - column),
        ):
            if (
                not 0 <= target_row < height
                or not 0 <= target_column < width
                or result[target_row][target_column] not in (0, source_color)
            ):
                return None
            result[target_row][target_column] = source_color
    return result


def punch_alternating_middle_cells_in_three_row_rectangles(
    grid: Grid,
) -> Grid | None:
    if len({value for row in grid for value in row} - {0}) < 2:
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    }
    result = [values[:] for values in grid]
    count = 0
    while remaining:
        seed = remaining.pop()
        component = {seed}
        stack = [seed]
        while stack:
            row, column = stack.pop()
            for target in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if target in remaining:
                    remaining.remove(target)
                    component.add(target)
                    stack.append(target)
        component_colors = {grid[row][column] for row, column in component}
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        if (
            len(component_colors) != 1
            or bottom - top != 2
            or len(component) != 3 * (right - left + 1)
        ):
            return None
        for column in range(left + 1, right + 1, 2):
            result[top + 1][column] = 0
        count += 1
    return result if count else None


def copy_marker_ray_offsets_between_opposite_two_lines(
    grid: Grid,
) -> Grid | None:
    width = len(grid[0])
    if {value for row in grid for value in row} != {0, 2, 8}:
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 2
    }
    lines = []
    while remaining:
        seed = remaining.pop()
        component = {seed}
        stack = [seed]
        while stack:
            row, column = stack.pop()
            for target in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if target in remaining:
                    remaining.remove(target)
                    component.add(target)
                    stack.append(target)
        columns = {column for _, column in component}
        rows = sorted(row for row, _ in component)
        if (
            len(columns) != 1
            or rows != list(range(rows[0], rows[-1] + 1))
        ):
            return None
        lines.append((rows[0], rows[-1], next(iter(columns))))
    if len(lines) != 2:
        return None
    markers = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 8
    ]
    marked = []
    plain = []
    for line in lines:
        top, bottom, _ = line
        line_markers = [
            point for point in markers if top <= point[0] <= bottom
        ]
        if line_markers:
            marked.append((line, line_markers))
        else:
            plain.append(line)
    if len(marked) != 1 or len(plain) != 1:
        return None
    (top, bottom, column), line_markers = marked[0]
    plain_top, plain_bottom, plain_column = plain[0]
    if (
        bottom - top != plain_bottom - plain_top
        or {column, plain_column} != {0, width - 1}
    ):
        return None
    result = [values[:] for values in grid]
    offsets = []
    for row, marker_column in line_markers:
        if (
            marker_column == column
            or (marker_column > column) != (column < plain_column)
        ):
            return None
        step = 1 if marker_column > column else -1
        for target_column in range(column + step, marker_column, step):
            if result[row][target_column] != 0:
                return None
            result[row][target_column] = 8
        result[row][marker_column] = 4
        offsets.append(row - top)
    for offset in offsets:
        row = plain_top + offset
        step = 1 if plain_column == 0 else -1
        end = width if step == 1 else -1
        for target_column in range(plain_column + step, end, step):
            if result[row][target_column] != 0:
                return None
            result[row][target_column] = 8
    return result


def recover_rectangular_zero_hole_from_fourfold_symmetry(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 16 or len(grid[0]) != 16:
        return None
    zeros = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 0
    ]
    if not zeros:
        return None
    top = min(row for row, _ in zeros)
    bottom = max(row for row, _ in zeros)
    left = min(column for _, column in zeros)
    right = max(column for _, column in zeros)
    if len(zeros) != (bottom - top + 1) * (right - left + 1):
        return None
    result = [
        [0 for _ in range(right - left + 1)]
        for _ in range(bottom - top + 1)
    ]
    for row in range(top, bottom + 1):
        for column in range(left, right + 1):
            values = {
                grid[target_row][target_column]
                for target_row, target_column in (
                    (15 - row, column),
                    (row, 15 - column),
                    (15 - row, 15 - column),
                )
                if grid[target_row][target_column] != 0
            }
            if len(values) != 1:
                return None
            result[row - top][column - left] = next(iter(values))
    return result


def draw_eight_l_path_between_two_and_three(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 2, 3}:
        return None
    twos = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 2
    ]
    threes = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 3
    ]
    if len(twos) != 1 or len(threes) != 1:
        return None
    two_row, two_column = twos[0]
    three_row, three_column = threes[0]
    if two_row == three_row or two_column == three_column:
        return None
    path = {
        (two_row, column)
        for column in range(
            min(two_column, three_column),
            max(two_column, three_column) + 1,
        )
    } | {
        (row, three_column)
        for row in range(
            min(two_row, three_row),
            max(two_row, three_row) + 1,
        )
    }
    path -= {(two_row, two_column), (three_row, three_column)}
    if (
        not path
        or any(grid[row][column] != 0 for row, column in path)
    ):
        return None
    result = [values[:] for values in grid]
    for row, column in path:
        result[row][column] = 8
    return result


def upscale_three_by_three_by_nonzero_count(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 3 or len(grid[0]) != 3:
        return None
    factor = sum(value != 0 for row in grid for value in row)
    if not 1 <= factor <= 9:
        return None
    result = []
    for values in grid:
        expanded = [
            value
            for value in values
            for _ in range(factor)
        ]
        result.extend(expanded[:] for _ in range(factor))
    return result


def slide_five_cell_row_down_left_in_nonzero_count_square(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 1 or len(grid[0]) != 5:
        return None
    count = sum(value != 0 for value in grid[0])
    if not 1 <= count <= 5:
        return None
    size = 5 * count
    result = [[0 for _ in range(size)] for _ in range(size)]
    for row in range(size):
        for source_column, value in enumerate(grid[0]):
            target_column = size - 1 - row + source_column
            if 0 <= target_column < size:
                result[row][target_column] = value
    return result


def render_three_by_three_panels_with_duplicate_sixes_one(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 11
        or len(grid[0]) != 11
        or {value for row in grid for value in row} != {0, 6, 8}
    ):
        return None
    separators = {
        (row, column)
        for row in (3, 7)
        for column in range(11)
    } | {
        (row, column)
        for row in range(11)
        for column in (3, 7)
    }
    eights = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 8
    }
    if eights != separators:
        return None
    result = [[0 for _ in range(3)] for _ in range(3)]
    for output_row, top in enumerate((0, 4, 8)):
        for output_column, left in enumerate((0, 4, 8)):
            count = sum(
                grid[row][column] == 6
                for row in range(top, top + 3)
                for column in range(left, left + 3)
            )
            if count not in (1, 2):
                return None
            result[output_row][output_column] = int(count == 2)
    return result


def align_shapes_at_five_markers_in_three_by_three(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 11 or len(grid[0]) != 11:
        return None
    markers = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    ]
    colored = [
        (row, column, value)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value not in (0, 5)
    ]
    if len(markers) < 2 or not colored:
        return None
    result = [[0 for _ in range(3)] for _ in range(3)]
    result[1][1] = 5
    used_markers = set()
    for row, column, color in colored:
        owners = [
            marker
            for marker in markers
            if max(abs(row - marker[0]), abs(column - marker[1])) <= 1
        ]
        if len(owners) != 1:
            return None
        marker_row, marker_column = owners[0]
        used_markers.add((marker_row, marker_column))
        target_row = row - marker_row + 1
        target_column = column - marker_column + 1
        if result[target_row][target_column] not in (0, color):
            return None
        result[target_row][target_column] = color
    if used_markers != set(markers):
        return None
    return result


def overlay_panels_across_horizontal_five_separator_bottom_priority(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 11 or len(grid[0]) != 11:
        return None
    if (
        any(value != 5 for value in grid[5])
        or any(5 in row for row in grid[:5])
        or any(5 in row for row in grid[6:])
    ):
        return None
    top_colors = {value for row in grid[:5] for value in row} - {0}
    bottom_colors = {value for row in grid[6:] for value in row} - {0}
    if (
        len(top_colors) != 1
        or len(bottom_colors) != 1
        or top_colors == bottom_colors
    ):
        return None
    result = [values[:] for values in grid[:5]]
    for row, values in enumerate(grid[6:]):
        for column, value in enumerate(values):
            if value != 0:
                result[row][column] = value
    return result


def extend_row_sequence_by_periodic_horizontal_shift_to_ten(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if (
        width != 10
        or not 2 <= height < 10
        or len({value for row in grid for value in row} - {0}) != 1
    ):
        return None

    def shifted(row: list[int], delta: int) -> list[int]:
        result = [0 for _ in range(width)]
        for column, value in enumerate(row):
            target_column = column + delta
            if 0 <= target_column < width:
                result[target_column] = value
        return result

    patterns = []
    for period in range(1, height):
        for delta in range(-width + 1, width):
            if all(
                grid[row] == shifted(grid[row - period], delta)
                for row in range(period, height)
            ):
                patterns.append((period, delta))
        if patterns:
            break
    if len(patterns) != 1:
        return None
    period, delta = patterns[0]
    result = [values[:] for values in grid]
    while len(result) < 10:
        result.append(shifted(result[-period], delta))
    return result


def extend_max_index_diagonal_sequence_to_ten(
    grid: Grid,
) -> Grid | None:
    if len(grid) != 5 or len(grid[0]) != 5:
        return None
    diagonal = [grid[index][index] for index in range(5)]
    if not any(diagonal):
        return None
    active = next(
        (index for index, value in enumerate(diagonal) if value == 0),
        len(diagonal),
    )
    if active == 0 or any(diagonal[index] != 0 for index in range(active, 5)):
        return None
    if any(
        grid[row][column]
        != (diagonal[max(row, column)] if max(row, column) < active else 0)
        for row in range(5)
        for column in range(5)
    ):
        return None
    sequence = diagonal[:active]
    return [
        [
            sequence[max(row, column) % len(sequence)]
            for column in range(10)
        ]
        for row in range(10)
    ]


def complete_minimal_colored_quarter_turn_symmetry(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or len({value for row in grid for value in row} - {0}) != 2
    ):
        return None
    points = [
        (row, column, value)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    ]
    candidates = []
    for center_row_twice in range(2 * len(grid) - 1):
        for center_column_twice in range(2 * len(grid[0]) - 1):
            closure = {}
            valid = True
            for row, column, color in points:
                row_twice = 2 * row
                column_twice = 2 * column
                for _ in range(4):
                    if (
                        row_twice % 2
                        or column_twice % 2
                        or not (
                            0 <= row_twice // 2 < len(grid)
                            and 0
                            <= column_twice // 2
                            < len(grid[0])
                        )
                    ):
                        valid = False
                        break
                    target = (row_twice // 2, column_twice // 2)
                    if (
                        target in closure
                        and closure[target] != color
                        or grid[target[0]][target[1]] not in (0, color)
                    ):
                        valid = False
                        break
                    closure[target] = color
                    row_twice, column_twice = (
                        center_row_twice
                        - (column_twice - center_column_twice),
                        center_column_twice
                        + (row_twice - center_row_twice),
                    )
                if not valid:
                    break
            additions = sum(
                grid[row][column] == 0
                for row, column in closure
            )
            if valid and additions:
                candidates.append(
                    (additions, tuple(sorted(closure.items())))
                )
    if not candidates:
        return None
    minimum = min(additions for additions, _ in candidates)
    best = {
        closure
        for additions, closure in candidates
        if additions == minimum
    }
    if len(best) != 1:
        return None
    result = [values[:] for values in grid]
    for (row, column), color in next(iter(best)):
        result[row][column] = color
    return result


def extend_two_by_two_objects_down_by_distinct_color_count(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or any(value == 3 for row in grid for value in row)
    ):
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    }
    components = []
    while remaining:
        seed = remaining.pop()
        component = {seed}
        stack = [seed]
        while stack:
            row, column = stack.pop()
            for target in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if target in remaining:
                    remaining.remove(target)
                    component.add(target)
                    stack.append(target)
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        if (
            bottom - top != 1
            or right - left != 1
            or component
            != {
                (row, column)
                for row in range(top, bottom + 1)
                for column in range(left, right + 1)
            }
        ):
            return None
        components.append((component, bottom, left, right))
    if not components:
        return None
    result = [values[:] for values in grid]
    for component, bottom, left, right in components:
        count = len({grid[row][column] for row, column in component})
        if bottom + count >= len(grid):
            return None
        for row in range(bottom + 1, bottom + count + 1):
            for column in range(left, right + 1):
                if result[row][column] != 0:
                    return None
                result[row][column] = 3
    return result


def arrange_nine_three_by_three_tiles_by_nonfive_centroid(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    points = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    }
    if len(points) != 81:
        return None
    windows = []
    for top in range(height - 2):
        for left in range(width - 2):
            window = {
                (row, column)
                for row in range(top, top + 3)
                for column in range(left, left + 3)
            }
            if window.issubset(points):
                windows.append((top, left, window))
    solutions = []

    def search(
        uncovered: set[tuple[int, int]],
        selected: list[tuple[int, int, set[tuple[int, int]]]],
    ) -> None:
        if len(solutions) > 1:
            return
        if not uncovered:
            solutions.append(selected[:])
            return
        point = min(uncovered)
        for item in windows:
            if point in item[2] and item[2].issubset(uncovered):
                search(uncovered - item[2], selected + [item])

    search(points, [])
    if len(solutions) != 1 or len(solutions[0]) != 9:
        return None
    components = []
    for top, left, _ in solutions[0]:
        tile = [
            values[left : left + 3]
            for values in grid[top : top + 3]
        ]
        colors = {value for values in tile for value in values}
        if 5 not in colors or len(colors - {5}) > 1:
            return None
        motif = [
            (row, column)
            for row, values in enumerate(tile)
            for column, value in enumerate(values)
            if value != 5
        ]
        if motif:
            target_row = int(
                round(sum(row for row, _ in motif) / len(motif))
            )
            target_column = int(
                round(sum(column for _, column in motif) / len(motif))
            )
        else:
            target_row = target_column = 1
        components.append((target_row, target_column, tile))
    if (
        len(components) != 9
        or len({(row, column) for row, column, _ in components}) != 9
    ):
        return None
    result = [[0 for _ in range(9)] for _ in range(9)]
    for target_row, target_column, tile in components:
        for row in range(3):
            for column in range(3):
                result[3 * target_row + row][
                    3 * target_column + column
                ] = tile[row][column]
    return result


def project_matching_interior_markers_to_colored_frame(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if height < 5 or width < 5 or any(
        grid[row][column] != 0
        for row, column in (
            (0, 0),
            (0, width - 1),
            (height - 1, 0),
            (height - 1, width - 1),
        )
    ):
        return None
    sides = (
        grid[0][1],
        grid[height - 1][1],
        grid[1][0],
        grid[1][width - 1],
    )
    if len(set(sides)) != 4 or 0 in sides:
        return None
    top, bottom, left, right = sides
    if (
        any(value != top for value in grid[0][1:-1])
        or any(value != bottom for value in grid[-1][1:-1])
        or any(grid[row][0] != left for row in range(1, height - 1))
        or any(grid[row][-1] != right for row in range(1, height - 1))
    ):
        return None
    markers = [
        (row, column, grid[row][column])
        for row in range(1, height - 1)
        for column in range(1, width - 1)
        if grid[row][column] != 0
    ]
    if not markers:
        return None
    result = [values[:] for values in grid]
    for row in range(1, height - 1):
        for column in range(1, width - 1):
            result[row][column] = 0
    for row, column, color in markers:
        target = None
        if color == top:
            target = (1, column)
        elif color == bottom:
            target = (height - 2, column)
        elif color == left:
            target = (row, 1)
        elif color == right:
            target = (row, width - 2)
        if target is not None:
            target_row, target_column = target
            if result[target_row][target_column] not in (0, color):
                return None
            result[target_row][target_column] = color
    return result


def recolor_one_components_enclosing_nines_eight(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {1, 9}:
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 1
    }
    components = []
    while remaining:
        seed = remaining.pop()
        component = {seed}
        stack = [seed]
        while stack:
            row, column = stack.pop()
            for target in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if target in remaining:
                    remaining.remove(target)
                    component.add(target)
                    stack.append(target)
        components.append(component)
    result = [values[:] for values in grid]
    changed = False
    for component in components:
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        exterior = set()
        stack = []
        for row in range(top, bottom + 1):
            for column in (left, right):
                if (row, column) not in component:
                    exterior.add((row, column))
                    stack.append((row, column))
        for column in range(left, right + 1):
            for row in (top, bottom):
                if (row, column) not in component:
                    exterior.add((row, column))
                    stack.append((row, column))
        while stack:
            row, column = stack.pop()
            for target in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                target_row, target_column = target
                if (
                    top <= target_row <= bottom
                    and left <= target_column <= right
                    and target not in component
                    and target not in exterior
                ):
                    exterior.add(target)
                    stack.append(target)
        has_hole = any(
            (row, column) not in component
            and (row, column) not in exterior
            for row in range(top, bottom + 1)
            for column in range(left, right + 1)
        )
        if has_hole:
            for row, column in component:
                result[row][column] = 8
            changed = True
    return result if changed else None


def kronecker_multicolor_panel_with_monochrome_mask(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if width == 2 * height:
        size = height
        panels = (
            [values[:size] for values in grid],
            [values[size:] for values in grid],
        )
    elif height == 2 * width:
        size = width
        panels = (
            [values[:] for values in grid[:size]],
            [values[:] for values in grid[size:]],
        )
    else:
        return None
    monochrome = [
        panel
        for panel in panels
        if len({value for row in panel for value in row} - {0}) == 1
    ]
    multicolor = [
        panel
        for panel in panels
        if len({value for row in panel for value in row} - {0}) >= 2
    ]
    if len(monochrome) != 1 or len(multicolor) != 1:
        return None
    mask = [
        [value != 0 for value in values]
        for values in monochrome[0]
    ]
    values = multicolor[0]
    result = [
        [0 for _ in range(size * size)]
        for _ in range(size * size)
    ]
    for row in range(size):
        for column in range(size):
            color = values[row][column]
            for mask_row in range(size):
                for mask_column in range(size):
                    if mask[mask_row][mask_column]:
                        result[row * size + mask_row][
                            column * size + mask_column
                        ] = color
    return result


def color_largest_zero_region_one_smallest_eight(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 2}:
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 0
    }
    components = []
    while remaining:
        seed = remaining.pop()
        component = {seed}
        stack = [seed]
        while stack:
            row, column = stack.pop()
            for target in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if target in remaining:
                    remaining.remove(target)
                    component.add(target)
                    stack.append(target)
        components.append(component)
    sizes = [len(component) for component in components]
    if len(components) < 3 or min(sizes) == max(sizes):
        return None
    minimum, maximum = min(sizes), max(sizes)
    result = [values[:] for values in grid]
    for component in components:
        color = (
            8
            if len(component) == minimum
            else 1
            if len(component) == maximum
            else 0
        )
        if color:
            for row, column in component:
                result[row][column] = color
    return result


def recolor_zero_components_touching_one(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    colors = {value for row in grid for value in row}
    if 0 not in colors or 1 not in colors:
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 0
    }
    result = [values[:] for values in grid]
    changed = False
    while remaining:
        seed = remaining.pop()
        component = {seed}
        stack = [seed]
        while stack:
            row, column = stack.pop()
            for target in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if target in remaining:
                    remaining.remove(target)
                    component.add(target)
                    stack.append(target)
        touches_one = any(
            0 <= target_row < height
            and 0 <= target_column < width
            and grid[target_row][target_column] == 1
            for row, column in component
            for target_row, target_column in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            )
        )
        if touches_one:
            for row, column in component:
                result[row][column] = 1
            changed = True
    return result if changed else None


def restore_fourfold_symmetry_over_color_four_masks(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 16
        or len(grid[0]) != 16
        or not any(value == 4 for row in grid for value in row)
    ):
        return None
    result = [values[:] for values in grid]
    changed = False
    for row in range(16):
        for column in range(16):
            orbit = {
                (row, column),
                (15 - row, column),
                (row, 15 - column),
                (15 - row, 15 - column),
            }
            values = {
                grid[target_row][target_column]
                for target_row, target_column in orbit
                if grid[target_row][target_column] != 4
            }
            if len(values) != 1:
                return None
            value = next(iter(values))
            for target_row, target_column in orbit:
                if result[target_row][target_column] == 4:
                    result[target_row][target_column] = value
                    changed = True
                elif result[target_row][target_column] != value:
                    return None
    return result if changed else None


def outline_two_dominoes_one_cell_three(
    grid: Grid,
) -> Grid | None:
    height, width = len(grid), len(grid[0])
    if {value for row in grid for value in row} != {0, 2}:
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 2
    }
    components = []
    while remaining:
        seed = remaining.pop()
        component = {seed}
        stack = [seed]
        while stack:
            row, column = stack.pop()
            for target in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if target in remaining:
                    remaining.remove(target)
                    component.add(target)
                    stack.append(target)
        if len(component) not in (1, 2):
            return None
        components.append(component)
    dominoes = [component for component in components if len(component) == 2]
    if not dominoes:
        return None
    result = [values[:] for values in grid]
    for component in dominoes:
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows) - 1, max(rows) + 1
        left, right = min(columns) - 1, max(columns) + 1
        for row in range(top, bottom + 1):
            for column in range(left, right + 1):
                if (
                    not 0 <= row < height
                    or not 0 <= column < width
                    or row not in (top, bottom)
                    and column not in (left, right)
                ):
                    continue
                if result[row][column] not in (0, 3):
                    return None
                result[row][column] = 3
    return result


def fill_rectangle_and_extend_through_single_gap_eight(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 5}:
        return None
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    ]
    top = min(row for row, _ in points)
    bottom = max(row for row, _ in points)
    left = min(column for _, column in points)
    right = max(column for _, column in points)
    if bottom - top < 2 or right - left < 2:
        return None
    boundary = {
        (row, column)
        for row in range(top, bottom + 1)
        for column in range(left, right + 1)
        if row in (top, bottom) or column in (left, right)
    }
    fives = set(points)
    gaps = boundary - fives
    if len(gaps) != 1 or not fives.issubset(boundary):
        return None
    gap_row, gap_column = next(iter(gaps))
    if gap_row in (top, bottom) and gap_column in (left, right):
        return None
    result = [row[:] for row in grid]
    for row in range(top + 1, bottom):
        for column in range(left + 1, right):
            result[row][column] = 8
    if gap_row == top:
        for row in range(top + 1):
            result[row][gap_column] = 8
    elif gap_row == bottom:
        for row in range(bottom, len(grid)):
            result[row][gap_column] = 8
    elif gap_column == left:
        for column in range(left + 1):
            result[gap_row][column] = 8
    elif gap_column == right:
        for column in range(right, len(grid[0])):
            result[gap_row][column] = 8
    else:
        return None
    return result


def extend_bottom_two_rays_up_detour_right_fives(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or {value for row in grid for value in row} != {0, 2, 5}
        or any(value == 2 for row in grid[:-1] for value in row)
    ):
        return None
    source_columns = [
        column for column, value in enumerate(grid[-1])
        if value == 2
    ]
    if not source_columns:
        return None
    result = [row[:] for row in grid]
    for source_column in source_columns:
        column = source_column
        for row in range(len(grid) - 2, -1, -1):
            if grid[row][column] == 5:
                if column + 1 >= len(grid[0]):
                    return None
                if result[row + 1][column + 1] not in (0, 2):
                    return None
                column += 1
                if result[row][column] not in (0, 2):
                    return None
                result[row + 1][column] = 2
                result[row][column] = 2
            else:
                if result[row][column] not in (0, 2):
                    return None
                result[row][column] = 2
    return result


def extend_two_diagonal_three_squares_with_eight(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row}
    if not colors.issubset({0, 3}) or 3 not in colors:
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 3
    }
    squares = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        rows = [row for row, _ in component]
        columns = [column for _, column in component]
        top, bottom = min(rows), max(rows)
        left, right = min(columns), max(columns)
        size = bottom - top + 1
        if (
            right - left + 1 != size
            or component
            != {
                (row, column)
                for row in range(top, bottom + 1)
                for column in range(left, right + 1)
            }
        ):
            return None
        squares.append((top, left, size))
    if (
        len(squares) < 2
        or len(squares) % 2
        or len({size for _, _, size in squares}) != 1
    ):
        return None
    size = squares[0][2]
    unpaired = set(squares)
    pairs = []
    while unpaired:
        first = min(unpaired)
        candidates = [
            second
            for second in unpaired
            if second != first
            and second[0] - first[0] == size
            and abs(second[1] - first[1]) == size
        ]
        if len(candidates) != 1:
            return None
        second = candidates[0]
        unpaired.remove(first)
        unpaired.remove(second)
        pairs.append((first, second))
    result = [row[:] for row in grid]
    painted = 0
    for first, second in pairs:
        top, left, _ = first
        direction = 1 if second[1] > left else -1
        anchors = (
            (top - size, left + 2 * direction * size),
            (top + 2 * size, left - direction * size),
        )
        for anchor_row, anchor_column in anchors:
            for row in range(anchor_row, anchor_row + size):
                for column in range(anchor_column, anchor_column + size):
                    if (
                        0 <= row < len(grid)
                        and 0 <= column < len(grid[0])
                    ):
                        if result[row][column] != 0:
                            return None
                        result[row][column] = 8
                        painted += 1
    return result if painted else None


def copy_top_five_mask_at_right_edge_markers_two(
    grid: Grid,
) -> Grid | None:
    if (
        {value for row in grid for value in row} != {0, 5}
        or grid[0][-1] != 0
        or any(
            value != 0
            for row in grid[1:]
            for value in row[:-1]
        )
    ):
        return None
    source_columns = [
        column for column, value in enumerate(grid[0])
        if value == 5
    ]
    target_rows = [
        row for row in range(1, len(grid))
        if grid[row][-1] == 5
    ]
    if not source_columns or not target_rows:
        return None
    result = [row[:] for row in grid]
    for row in target_rows:
        for column in source_columns:
            result[row][column] = 2
    return result


def extend_one_square_up_left_two_square_down_right(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 1, 2}:
        return None
    boxes = {}
    for color in (1, 2):
        points = [
            (row, column)
            for row, values in enumerate(grid)
            for column, value in enumerate(values)
            if value == color
        ]
        if len(points) != 4:
            return None
        top = min(row for row, _ in points)
        bottom = max(row for row, _ in points)
        left = min(column for _, column in points)
        right = max(column for _, column in points)
        if (
            bottom - top != 1
            or right - left != 1
            or any(
                grid[row][column] != color
                for row in range(top, bottom + 1)
                for column in range(left, right + 1)
            )
        ):
            return None
        boxes[color] = (top, bottom, left, right)
    result = [row[:] for row in grid]
    row, column = boxes[1][0] - 1, boxes[1][2] - 1
    while row >= 0 and column >= 0:
        if result[row][column] != 0:
            return None
        result[row][column] = 1
        row -= 1
        column -= 1
    row, column = boxes[2][1] + 1, boxes[2][3] + 1
    while row < len(grid) and column < len(grid[0]):
        if result[row][column] != 0:
            return None
        result[row][column] = 2
        row += 1
        column += 1
    return result


def fill_single_horizontal_gaps_between_ones_two(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 1}:
        return None
    result = [row[:] for row in grid]
    occupied_rows = 0
    for row, values in enumerate(grid):
        columns = [
            column for column, value in enumerate(values)
            if value == 1
        ]
        if not columns:
            continue
        occupied_rows += 1
        if (
            len(columns) < 2
            or any(
                right - left != 2
                for left, right in zip(columns, columns[1:])
            )
        ):
            return None
        for left, right in zip(columns, columns[1:]):
            result[row][(left + right) // 2] = 2
    return result if occupied_rows else None


def fill_four_marker_rectangle_interiors_two(
    grid: Grid,
) -> Grid | None:
    if {value for row in grid for value in row} != {0, 4}:
        return None
    grouped = {}
    for row, values in enumerate(grid):
        columns = tuple(
            column for column, value in enumerate(values)
            if value == 4
        )
        if not columns:
            continue
        if len(columns) != 2:
            return None
        grouped.setdefault(columns, []).append(row)
    if (
        not grouped
        or any(len(rows) != 2 for rows in grouped.values())
    ):
        return None
    result = [row[:] for row in grid]
    for (left, right), (top, bottom) in grouped.items():
        if bottom - top < 2 or right - left < 2:
            return None
        if any(
            result[row][column] != 0
            for row in range(top + 1, bottom)
            for column in range(left + 1, right)
        ):
            return None
        for row in range(top + 1, bottom):
            for column in range(left + 1, right):
                result[row][column] = 2
    return result


def replicate_red_shape_into_zero_matches(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or {value for row in grid for value in row} != {0, 2, 5}
    ):
        return None
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 2
    ]
    if len(points) < 2:
        return None
    top = min(row for row, _ in points)
    bottom = max(row for row, _ in points)
    left = min(column for _, column in points)
    right = max(column for _, column in points)
    height = bottom - top + 1
    width = right - left + 1
    shape = {
        (row - top, column - left)
        for row, column in points
    }
    if len(shape) != len(points):
        return None
    internal_fives = {
        (row, column)
        for row in range(1, height - 1)
        for column in range(1, width - 1)
        if grid[top + row][left + column] == 5
    }
    result = [row[:] for row in grid]
    painted = 0
    target_rows = (
        (top,)
        if height == 1
        else range(len(grid) - height + 1)
    )
    for target_top in target_rows:
        for target_left in range(len(grid[0]) - width + 1):
            if (target_top, target_left) == (top, left):
                continue
            if not all(
                grid[target_top + row][target_left + column] == 0
                and result[target_top + row][target_left + column] == 0
                for row, column in shape
            ):
                continue
            if not all(
                grid[target_top + row][target_left + column] == 5
                for row, column in internal_fives
            ):
                continue
            for row, column in shape:
                result[target_top + row][target_left + column] = 2
            painted += 1
    return result if painted else None


def connect_aligned_eights_rows_and_columns(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or {value for row in grid for value in row} != {0, 8}
    ):
        return None
    points = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 8
    }
    if len(points) < 3:
        return None
    result = [row[:] for row in grid]
    connected = False
    for row in range(len(grid)):
        columns = sorted(column for r, column in points if r == row)
        if len(columns) >= 2:
            for column in range(columns[0], columns[-1] + 1):
                result[row][column] = 8
            connected = True
    for column in range(len(grid[0])):
        rows = sorted(row for row, c in points if c == column)
        if len(rows) >= 2:
            for row in range(rows[0], rows[-1] + 1):
                result[row][column] = 8
            connected = True
    return result if connected else None


def stamp_three_by_three_grid_at_two_cells(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row}
    if (
        len(grid) != 3
        or len(grid[0]) != 3
        or not colors.issubset({0, 1, 2})
        or 2 not in colors
    ):
        return None
    result = [[0 for _ in range(9)] for _ in range(9)]
    for row, values in enumerate(grid):
        for column, value in enumerate(values):
            if value != 2:
                continue
            top = 3 * row
            left = 3 * column
            for source_row in range(3):
                for source_column in range(3):
                    result[top + source_row][left + source_column] = (
                        grid[source_row][source_column]
                    )
    return result


def tile_gray_shape_with_two_bars_and_eight_squares(
    grid: Grid,
) -> Grid | None:
    if (
        {value for row in grid for value in row} != {0, 5}
        or max(len(grid), len(grid[0])) > 15
    ):
        return None
    cells = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 5
    }
    if not 3 <= len(cells) <= 60:
        return None
    pieces = []
    for row in range(len(grid)):
        for column in range(len(grid[0])):
            candidates = (
                (
                    {
                        (row + dr, column + dc)
                        for dr in range(2)
                        for dc in range(2)
                    },
                    8,
                ),
                (
                    {(row, column + dc) for dc in range(3)},
                    2,
                ),
                (
                    {(row + dr, column) for dr in range(3)},
                    2,
                ),
            )
            for piece, color in candidates:
                if piece.issubset(cells):
                    pieces.append((piece, color))
    by_cell = {cell: [] for cell in cells}
    for index, (piece, _) in enumerate(pieces):
        for cell in piece:
            by_cell[cell].append(index)
    colorings = {}
    nodes = 0
    aborted = False

    def search(
        remaining: set[tuple[int, int]],
        chosen: list[int],
    ) -> None:
        nonlocal nodes, aborted
        nodes += 1
        if nodes > 50000:
            aborted = True
            return
        if len(colorings) > 1 or aborted:
            return
        if not remaining:
            result = [
                [0 for _ in row]
                for row in grid
            ]
            for index in chosen:
                piece, color = pieces[index]
                for row, column in piece:
                    result[row][column] = color
            key = tuple(tuple(row) for row in result)
            colorings[key] = result
            return
        cell = min(
            remaining,
            key=lambda item: sum(
                pieces[index][0].issubset(remaining)
                for index in by_cell[item]
            ),
        )
        for index in by_cell[cell]:
            piece, _ = pieces[index]
            if piece.issubset(remaining):
                search(remaining - piece, chosen + [index])

    search(cells, [])
    if aborted or len(colorings) != 1:
        return None
    return next(iter(colorings.values()))


def fill_c_shape_and_extend_opening_four(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row} - {0}
    if len(colors) != 1 or 4 in colors:
        return None
    color = next(iter(colors))
    points = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == color
    ]
    top = min(row for row, _ in points)
    bottom = max(row for row, _ in points)
    left = min(column for _, column in points)
    right = max(column for _, column in points)
    if bottom - top < 2 or right - left < 2:
        return None
    if any(
        grid[row][column] != 0
        for row in range(top + 1, bottom)
        for column in range(left + 1, right)
    ):
        return None
    sides = {
        "top": [
            (top, column)
            for column in range(left, right + 1)
        ],
        "bottom": [
            (bottom, column)
            for column in range(left, right + 1)
        ],
        "left": [
            (row, left)
            for row in range(top, bottom + 1)
        ],
        "right": [
            (row, right)
            for row in range(top, bottom + 1)
        ],
    }
    openings = []
    for side, cells in sides.items():
        missing = [
            index
            for index, (row, column) in enumerate(cells)
            if grid[row][column] == 0
        ]
        if not missing:
            continue
        if (
            missing
            != list(range(min(missing), max(missing) + 1))
            or min(missing) == 0
            or max(missing) == len(cells) - 1
        ):
            return None
        openings.append((side, missing))
    if len(openings) != 1:
        return None
    side, missing = openings[0]
    result = [row[:] for row in grid]
    for row in range(top, bottom + 1):
        for column in range(left, right + 1):
            if result[row][column] == 0:
                result[row][column] = 4
    if side in ("top", "bottom"):
        start = left + min(missing)
        end = left + max(missing)
        step = -1 if side == "top" else 1
        edge = top if side == "top" else bottom
        if not 0 <= edge + step < len(grid):
            return None
        for row in range(
            edge + step,
            -1 if step < 0 else len(grid),
            step,
        ):
            for column in range(start, end + 1):
                result[row][column] = 4
        for column, delta_column in (
            (start - 1, -1),
            (end + 1, 1),
        ):
            row = edge + step
            while (
                0 <= row < len(grid)
                and 0 <= column < len(grid[0])
            ):
                result[row][column] = 4
                row += step
                column += delta_column
    else:
        start = top + min(missing)
        end = top + max(missing)
        step = -1 if side == "left" else 1
        edge = left if side == "left" else right
        if not 0 <= edge + step < len(grid[0]):
            return None
        for column in range(
            edge + step,
            -1 if step < 0 else len(grid[0]),
            step,
        ):
            for row in range(start, end + 1):
                result[row][column] = 4
        for row, delta_row in (
            (start - 1, -1),
            (end + 1, 1),
        ):
            column = edge + step
            while (
                0 <= row < len(grid)
                and 0 <= column < len(grid[0])
            ):
                result[row][column] = 4
                row += delta_row
                column += step
    return result


def complete_minimal_quarter_turn_symmetry_two(
    grid: Grid,
) -> Grid | None:
    if (
        len(grid) != 10
        or len(grid[0]) != 10
        or {value for row in grid for value in row} != {0, 1}
    ):
        return None
    points = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == 1
    }
    candidates = []
    for center_row_twice in range(2 * len(grid) - 1):
        for center_column_twice in range(2 * len(grid[0]) - 1):
            closure = set()
            valid = True
            for row, column in points:
                row_twice = 2 * row
                column_twice = 2 * column
                for _ in range(4):
                    if (
                        row_twice % 2
                        or column_twice % 2
                        or not (
                            0 <= row_twice // 2 < len(grid)
                            and 0
                            <= column_twice // 2
                            < len(grid[0])
                        )
                    ):
                        valid = False
                        break
                    closure.add(
                        (row_twice // 2, column_twice // 2)
                    )
                    row_twice, column_twice = (
                        center_row_twice
                        - (column_twice - center_column_twice),
                        center_column_twice
                        + (row_twice - center_row_twice),
                    )
                if not valid:
                    break
            if valid and closure != points:
                candidates.append((len(closure - points), closure))
    if not candidates:
        return None
    minimum = min(additions for additions, _ in candidates)
    best = {
        frozenset(closure)
        for additions, closure in candidates
        if additions == minimum
    }
    if len(best) != 1:
        return None
    result = [row[:] for row in grid]
    for row, column in next(iter(best)):
        if result[row][column] == 0:
            result[row][column] = 2
    return result


def recolor_and_chain_gray_endpoint_components(
    grid: Grid,
) -> Grid | None:
    colors = {value for row in grid for value in row}
    if (
        len(grid) != 3
        or 5 not in colors
        or len(colors - {0, 5}) < 2
    ):
        return None
    remaining = {
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value != 0
    }
    components = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        component = {start}
        stack = [start]
        while stack:
            row, column = stack.pop()
            for point in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    stack.append(point)
        components.append(component)
    components.sort(
        key=lambda item: min(column for _, column in item)
    )
    if len(components) < 2:
        return None
    descriptions = []
    for index, component in enumerate(components):
        component_colors = {
            grid[row][column]
            for row, column in component
        } - {5}
        gray = {
            (row, column)
            for row, column in component
            if grid[row][column] == 5
        }
        expected_markers = (
            1 if index in (0, len(components) - 1) else 2
        )
        if (
            len(component_colors) != 1
            or len(gray) != expected_markers
        ):
            return None
        descriptions.append(
            (component, gray, next(iter(component_colors)))
        )
    first, first_gray, first_color = descriptions[0]
    column_shift = -min(column for _, column in first)
    first_placed = {
        (row, column + column_shift)
        for row, column in first
    }
    outgoing = next(
        iter(
            {
                (row, column + column_shift)
                for row, column in first_gray
            }
        )
    )
    outputs = {}

    def place(
        index: int,
        placed: list[tuple[set[tuple[int, int]], int]],
        previous_outgoing: tuple[int, int],
    ) -> None:
        if len(outputs) > 1:
            return
        if index == len(descriptions):
            width = (
                max(
                    column
                    for component, _ in placed
                    for _, column in component
                )
                + 1
            )
            result = [
                [0 for _ in range(width)]
                for _ in range(len(grid))
            ]
            for component, color in placed:
                for row, column in component:
                    result[row][column] = color
            key = tuple(tuple(row) for row in result)
            outputs[key] = result
            return
        component, gray, color = descriptions[index]
        occupied = set().union(
            *(item for item, _ in placed)
        )
        for incoming in gray:
            row_shift = previous_outgoing[0] - incoming[0]
            column_shift = previous_outgoing[1] + 1 - incoming[1]
            translated = {
                (row + row_shift, column + column_shift)
                for row, column in component
            }
            if (
                translated & occupied
                or any(
                    not 0 <= row < len(grid) or column < 0
                    for row, column in translated
                )
            ):
                continue
            translated_gray = {
                (row + row_shift, column + column_shift)
                for row, column in gray
            }
            incoming_translated = (
                incoming[0] + row_shift,
                incoming[1] + column_shift,
            )
            if index == len(descriptions) - 1:
                place(
                    index + 1,
                    placed + [(translated, color)],
                    incoming_translated,
                )
            else:
                remaining_gray = translated_gray - {
                    incoming_translated
                }
                if len(remaining_gray) == 1:
                    place(
                        index + 1,
                        placed + [(translated, color)],
                        next(iter(remaining_gray)),
                    )

    place(1, [(first_placed, first_color)], outgoing)
    if len(outputs) != 1:
        return None
    return next(iter(outputs.values()))


def exact_predictions(task: dict, test_input: Grid) -> dict[str, Grid]:
    """Return candidates generated by rules exact on every training pair."""
    train_pairs = task["train"]
    predictions: dict[str, Grid] = {}

    for name, spatial in SPATIAL_TRANSFORMS.items():
        if all(spatial(pair["input"]) == pair["output"] for pair in train_pairs):
            predictions[f"spatial:{name}"] = spatial(test_input)
        mapping = infer_color_map(train_pairs, spatial)
        if mapping is not None:
            mapped = apply_color_map(spatial(test_input), mapping)
            if mapped is not None:
                predictions[f"spatial_color_map:{name}"] = mapped

    crop_mapping = infer_color_map(train_pairs, crop_mode_background)
    if crop_mapping is not None:
        mapped_crop = apply_color_map(
            crop_mode_background(test_input), crop_mapping
        )
        if mapped_crop is not None:
            predictions["crop_mode_color_map"] = mapped_crop

    reduce_mapping = infer_color_map(train_pairs, reduce_3x3_top_left)
    reduced_test = reduce_3x3_top_left(test_input)
    if reduce_mapping is not None and reduced_test is not None:
        predictions["reduce_3x3_top_left_color_map"] = (
            apply_color_map_with_identity_default(
                reduced_test, reduce_mapping
            )
        )

    for factor in range(2, 5):
        if all(scale(pair["input"], factor) == pair["output"] for pair in train_pairs):
            predictions[f"scale:{factor}"] = scale(test_input, factor)

    for row_tiles in range(1, 5):
        for column_tiles in range(1, 5):
            if row_tiles == column_tiles == 1:
                continue
            if all(
                tile(pair["input"], row_tiles, column_tiles) == pair["output"]
                for pair in train_pairs
            ):
                predictions[
                    f"tile:{row_tiles}x{column_tiles}"
                ] = tile(test_input, row_tiles, column_tiles)

    exact_completions = [
        (name, function)
        for name, function in SYMMETRY_COMPLETIONS.items()
        if all(
            function(pair["input"]) == pair["output"]
            for pair in train_pairs
        )
    ]
    completion_predictions = [
        function(test_input)
        for _, function in exact_completions
    ]
    completion_signature = tuple(
        name for name, _ in exact_completions
    )
    audited_completion_signatures = {
        ("vertical",),
        ("central",),
        ("vertical", "central", "all_reflections"),
    }
    if (
        completion_signature in audited_completion_signatures
        and
        completion_predictions
        and all(
            prediction == completion_predictions[0]
            for prediction in completion_predictions[1:]
        )
    ):
        predictions[
            "symmetry_completion_consensus"
        ] = completion_predictions[0]

    for color in range(10):
        cropped_train = [
            crop_not_color(pair["input"], color) for pair in train_pairs
        ]
        if all(
            cropped is not None and cropped == pair["output"]
            for cropped, pair in zip(cropped_train, train_pairs)
        ):
            prediction = crop_not_color(test_input, color)
            if prediction is not None:
                predictions[f"crop_not_color:{color}"] = prediction

        bbox_train = [
            crop_color_bbox(pair["input"], color) for pair in train_pairs
        ]
        if all(
            cropped is not None and cropped == pair["output"]
            for cropped, pair in zip(bbox_train, train_pairs)
        ):
            prediction = crop_color_bbox(test_input, color)
            if prediction is not None:
                predictions[f"crop_color_bbox:{color}"] = prediction

    composed_train = [
        crop_nonbackground_flip_horizontal(pair["input"])
        for pair in train_pairs
    ]
    if all(
        transformed is not None and transformed == pair["output"]
        for transformed, pair in zip(composed_train, train_pairs)
    ):
        prediction = crop_nonbackground_flip_horizontal(test_input)
        if prediction is not None:
            predictions[
                "crop_nonbackground_flip_horizontal"
            ] = prediction

    audited_transforms: dict[str, Callable[[Grid], Grid | None]] = {
        "adaptive_gravity_down_or_right": (
            adaptive_gravity_down_or_right
        ),
        "append_horizontal_mirror": append_horizontal_mirror,
        "append_vertical_mirror": append_vertical_mirror,
        "classify_vertical_symmetry_one_else_seven": (
            classify_vertical_symmetry_one_else_seven
        ),
        "collapse_uniform_duplicate_lines": (
            collapse_uniform_duplicate_lines
        ),
        "count_nonzero_cells_horizontal_source": (
            count_nonzero_cells_horizontal_source
        ),
        "expand_gray_marker_rows_by_column_code": (
            expand_gray_marker_rows_by_column_code
        ),
        "extend_vertical_period_by_half_recolor_two": (
            extend_vertical_period_by_half_recolor_two
        ),
        "drop_one_markers_through_bottom_five_bar": (
            drop_one_markers_through_bottom_five_bar
        ),
        "expand_with_edge_duplicates": expand_with_edge_duplicates,
        "extend_two_full_lines_cross_four": (
            extend_two_full_lines_cross_four
        ),
        "extract_repeated_half": extract_repeated_half,
        "fill_three_panels_rotate90_rotate180": (
            fill_three_panels_rotate90_rotate180
        ),
        "intersect_horizontal_panels_across_separator_two": (
            intersect_horizontal_panels_across_separator_two
        ),
        "mark_uniform_rows_five": mark_uniform_rows_five,
        "mask_color_five_with_other_color": (
            mask_color_five_with_other_color
        ),
        "merge_four_corner_panels_overlap": (
            merge_four_corner_panels_overlap
        ),
        "append_both_axis_mirror": append_both_axis_mirror,
        "tile_four_rotations": tile_four_rotations,
        "frame_with_vertical_flips_and_horizontal_mirrors": (
            frame_with_vertical_flips_and_horizontal_mirrors
        ),
        "stamp_grid_down_right_diagonal": (
            stamp_grid_down_right_diagonal
        ),
        "select_unique_binary_shape_tile": (
            select_unique_binary_shape_tile
        ),
        "replace_object_with_bottom_left_marker_color": (
            replace_object_with_bottom_left_marker_color
        ),
        "complete_l_tromino_bounding_boxes_one": (
            complete_l_tromino_bounding_boxes_one
        ),
        "project_distinct_two_by_two_to_opposite_corners": (
            project_distinct_two_by_two_to_opposite_corners
        ),
        "fill_diagonal_residue_period_three": (
            fill_diagonal_residue_period_three
        ),
        "bounce_singleton_one_upward_zero_background": (
            bounce_singleton_one_upward_zero_background
        ),
        "bounce_singleton_one_upward_eight_background": (
            bounce_singleton_one_upward_eight_background
        ),
        "render_two_by_two_component_count_five_spots": (
            render_two_by_two_component_count_five_spots
        ),
        "keep_center_column": keep_center_column,
        "crop_top_left_two_by_two": crop_top_left_two_by_two,
        "grow_left_prefix_run_triangle": grow_left_prefix_run_triangle,
        "overlay_three_panels_left_priority": (
            overlay_three_panels_left_priority
        ),
        "overlay_four_quadrants_fixed_priority": (
            overlay_four_quadrants_fixed_priority
        ),
        "tile_twice_mark_diagonal_neighbors_eight": (
            tile_twice_mark_diagonal_neighbors_eight
        ),
        "extract_missing_periodic_rectangle": (
            extract_missing_periodic_rectangle
        ),
        "classify_eight_path_between_two_red_blocks": (
            classify_eight_path_between_two_red_blocks
        ),
        "connect_edge_color_pairs_with_five": (
            connect_edge_color_pairs_with_five
        ),
        "ray_each_marker_right_then_down": (
            ray_each_marker_right_then_down
        ),
        "repeat_header_colors_below_five_bar": (
            repeat_header_colors_below_five_bar
        ),
        "repeat_marker_row_and_diagonal_neighbors": (
            repeat_marker_row_and_diagonal_neighbors
        ),
        "cycle_three_concentric_ring_colors": (
            cycle_three_concentric_ring_colors
        ),
        "duplicate_eight_shape_opposite_four_marker": (
            duplicate_eight_shape_opposite_four_marker
        ),
        "connect_matching_panel_feature_markers": (
            connect_matching_panel_feature_markers
        ),
        "recolor_mixed_red_green_components": (
            recolor_mixed_red_green_components
        ),
        "extract_three_repeated_horizontal_panels": (
            extract_three_repeated_horizontal_panels
        ),
        "crop_top_right_three_by_three": (
            crop_top_right_three_by_three
        ),
        "crop_nonzero_bbox_top_left_three_by_three": (
            crop_nonzero_bbox_top_left_three_by_three
        ),
        "crop_unique_horizontally_symmetric_component": (
            crop_unique_horizontally_symmetric_component
        ),
        "render_largest_hollow_rectangle_color_two_by_two": (
            render_largest_hollow_rectangle_color_two_by_two
        ),
        "count_solid_two_by_two_one_components_five_bar": (
            count_solid_two_by_two_one_components_five_bar
        ),
        "select_dense_three_by_three_with_most_ones": (
            select_dense_three_by_three_with_most_ones
        ),
        "render_empty_rows_above_eight_in_five_container": (
            render_empty_rows_above_eight_in_five_container
        ),
        "overlay_four_panels_across_one_cross": (
            overlay_four_panels_across_one_cross
        ),
        "recolor_six_by_six_pattern_from_two_by_two_key": (
            recolor_six_by_six_pattern_from_two_by_two_key
        ),
        "stamp_cropped_three_by_three_at_its_nonzero_mask": (
            stamp_cropped_three_by_three_at_its_nonzero_mask
        ),
        "stamp_three_by_three_at_its_nonzero_mask": (
            stamp_three_by_three_at_its_nonzero_mask
        ),
        "stamp_three_by_three_at_modal_color_cells": (
            stamp_three_by_three_at_modal_color_cells
        ),
        "recolor_vertical_bars_by_descending_length": (
            recolor_vertical_bars_by_descending_length
        ),
        "mark_two_diagonals_four_and_one_cardinals_seven": (
            mark_two_diagonals_four_and_one_cardinals_seven
        ),
        "fill_two_by_two_and_stamp_from_twos_diagonally": (
            fill_two_by_two_and_stamp_from_twos_diagonally
        ),
        "expand_five_markers_three_by_three_center_five": (
            expand_five_markers_three_by_three_center_five
        ),
        "expand_five_markers_three_by_three_one": (
            expand_five_markers_three_by_three_one
        ),
        "replace_five_markers_with_diagonal_five_cardinal_one": (
            replace_five_markers_with_diagonal_five_cardinal_one
        ),
        "fill_eight_connected_four_component_bboxes_seven": (
            fill_eight_connected_four_component_bboxes_seven
        ),
        "draw_two_singleton_crosses_intersections_two": (
            draw_two_singleton_crosses_intersections_two
        ),
        "keep_longest_and_shortest_vertical_bars_one_two": (
            keep_longest_and_shortest_vertical_bars_one_two
        ),
        "sort_uniform_color_bars_by_length_bottom_right": (
            sort_uniform_color_bars_by_length_bottom_right
        ),
        "overlay_left_panel_with_mirrored_right_panel": (
            overlay_left_panel_with_mirrored_right_panel
        ),
        "center_red_object_inside_four_green_corners": (
            center_red_object_inside_four_green_corners
        ),
        "move_green_shape_to_red_line_add_opposite_eight_line": (
            move_green_shape_to_red_line_add_opposite_eight_line
        ),
        "recolor_bottom_half_of_vertical_two_bars_eight": (
            recolor_bottom_half_of_vertical_two_bars_eight
        ),
        "classify_five_cell_three_by_three_glyph": (
            classify_five_cell_three_by_three_glyph
        ),
        "render_color_frequencies_as_top_aligned_columns": (
            render_color_frequencies_as_top_aligned_columns
        ),
        "select_unique_non_main_diagonal_symmetric_panel": (
            select_unique_non_main_diagonal_symmetric_panel
        ),
        "classify_three_four_by_four_five_glyphs": (
            classify_three_four_by_four_five_glyphs
        ),
        "recolor_alternating_singletons_from_right_three": (
            recolor_alternating_singletons_from_right_three
        ),
        "recolor_every_third_column_sixes": (
            recolor_every_third_column_sixes
        ),
        "fill_unique_largest_zero_rectangle_six": (
            fill_unique_largest_zero_rectangle_six
        ),
        "crop_component_directly_below_five_marker": (
            crop_component_directly_below_five_marker
        ),
        "pack_two_components_into_three_by_three": (
            pack_two_components_into_three_by_three
        ),
        "grow_center_marker_diagonals_to_sides": (
            grow_center_marker_diagonals_to_sides
        ),
        "expand_vertical_seven_run_triangle_alternating_eight": (
            expand_vertical_seven_run_triangle_alternating_eight
        ),
        "expand_left_prefix_two_run_triangles_three_one": (
            expand_left_prefix_two_run_triangles_three_one
        ),
        "expand_l_tromino_marker_to_two_four_squares": (
            expand_l_tromino_marker_to_two_four_squares
        ),
        "fill_periodic_four_triangles_between_two_pattern": (
            fill_periodic_four_triangles_between_two_pattern
        ),
        "extend_repeated_column_prefix_to_width": (
            extend_repeated_column_prefix_to_width
        ),
        "mark_bottom_centers_of_inverted_u_components_four": (
            mark_bottom_centers_of_inverted_u_components_four
        ),
        "expand_panel_center_colors_plus_five": (
            expand_panel_center_colors_plus_five
        ),
        "extend_horizontal_period_to_double_width": (
            extend_horizontal_period_to_double_width
        ),
        "pack_column_order_markers_snake_three_by_three": (
            pack_column_order_markers_snake_three_by_three
        ),
        "color_inner_mask_by_frame_corner_quadrants": (
            color_inner_mask_by_frame_corner_quadrants
        ),
        "render_largest_color_counts_left_to_right": (
            render_largest_color_counts_left_to_right
        ),
        "crop_component_with_most_twos": (
            crop_component_with_most_twos
        ),
        "surround_each_two_with_ones_three_by_three": (
            surround_each_two_with_ones_three_by_three
        ),
        "replace_hollow_three_by_three_one_squares_with_two_pluses": (
            replace_hollow_three_by_three_one_squares_with_two_pluses
        ),
        "project_five_markers_to_expanded_two_bbox": (
            project_five_markers_to_expanded_two_bbox
        ),
        "recolor_solid_five_rectangle_interiors_two": (
            recolor_solid_five_rectangle_interiors_two
        ),
        "fill_horizontal_gaps_between_red_runs_nine": (
            fill_horizontal_gaps_between_red_runs_nine
        ),
        "rank_two_solid_gray_rectangles_interiors": (
            rank_two_solid_gray_rectangles_interiors
        ),
        "extend_l_tromino_bisector_rays": (
            extend_l_tromino_bisector_rays
        ),
        "extend_one_two_around_horizontal_five_divider": (
            extend_one_two_around_horizontal_five_divider
        ),
        "align_component_shapes_to_color_one_rows": (
            align_component_shapes_to_color_one_rows
        ),
        "recolor_repeated_eight_component_shapes_one_else_two": (
            recolor_repeated_eight_component_shapes_one_else_two
        ),
        "recolor_six_cell_fives_two_others_one": (
            recolor_six_cell_fives_two_others_one
        ),
        "recolor_solid_five_rectangles_corners_edges_interiors": (
            recolor_solid_five_rectangles_corners_edges_interiors
        ),
        "recolor_five_components_by_size_four_three_two": (
            recolor_five_components_by_size_four_three_two
        ),
        "extend_diagonal_markers_from_two_square": (
            extend_diagonal_markers_from_two_square
        ),
        "color_corner_center_grid_regions_one_two_three": (
            color_corner_center_grid_regions_one_two_three
        ),
        "rank_three_five_components_colors_one_four_two": (
            rank_three_five_components_colors_one_four_two
        ),
        "recolor_zero_components_by_size_three_two_one": (
            recolor_zero_components_by_size_three_two_one
        ),
        "stamp_cardinal_colors_around_ones": (
            stamp_cardinal_colors_around_ones
        ),
        "complete_quarter_turn_color_orbits": (
            complete_quarter_turn_color_orbits
        ),
        "generate_vertical_lattice_from_bottom_marker": (
            generate_vertical_lattice_from_bottom_marker
        ),
        "replace_five_triangles_with_parallel_diagonals": (
            replace_five_triangles_with_parallel_diagonals
        ),
        "render_two_five_row_frames_from_markers": (
            render_two_five_row_frames_from_markers
        ),
        "stamp_multicolor_template_over_eight_masks": (
            stamp_multicolor_template_over_eight_masks
        ),
        "stamp_template_over_solid_five_rectangles": (
            stamp_template_over_solid_five_rectangles
        ),
        "connect_gray_block_to_aligned_markers": (
            connect_gray_block_to_aligned_markers
        ),
        "shift_cross_down_left_by_five_count": (
            shift_cross_down_left_by_five_count
        ),
        "fill_marked_open_one_frames": (
            fill_marked_open_one_frames
        ),
        "project_external_markers_onto_eight_rectangle": (
            project_external_markers_onto_eight_rectangle
        ),
        "recolor_three_markers_by_nearest_colored_border": (
            recolor_three_markers_by_nearest_colored_border
        ),
        "bridge_two_solid_rectangles_with_eight": (
            bridge_two_solid_rectangles_with_eight
        ),
        "frame_unique_singleton_color_with_twos": (
            frame_unique_singleton_color_with_twos
        ),
        "move_four_inner_markers_to_opposite_frame_corners": (
            move_four_inner_markers_to_opposite_frame_corners
        ),
        "place_quadrant_singletons_into_two_by_two_eight_block": (
            place_quadrant_singletons_into_two_by_two_eight_block
        ),
        "recolor_solid_five_rectangles_by_top_markers": (
            recolor_solid_five_rectangles_by_top_markers
        ),
        "recolor_component_matching_five_corner_template": (
            recolor_component_matching_five_corner_template
        ),
        "stamp_three_by_three_source_in_marked_tiles": (
            stamp_three_by_three_source_in_marked_tiles
        ),
        "move_three_by_three_two_block_to_next_three_marker": (
            move_three_by_three_two_block_to_next_three_marker
        ),
        "extend_singleton_rows_alternating_color_five": (
            extend_singleton_rows_alternating_color_five
        ),
        "move_three_one_step_toward_four": (
            move_three_one_step_toward_four
        ),
        "copy_three_by_three_shape_to_five_center": (
            copy_three_by_three_shape_to_five_center
        ),
        "move_two_shape_to_touch_solid_eight_square": (
            move_two_shape_to_touch_solid_eight_square
        ),
        "fill_most_occupied_three_by_three_panels": (
            fill_most_occupied_three_by_three_panels
        ),
        "project_one_three_rows_and_two_columns": (
            project_one_three_rows_and_two_columns
        ),
        "extend_rows_by_reference_two_color_pattern": (
            extend_rows_by_reference_two_color_pattern
        ),
        "fill_eight_bounding_box_holes_two": (
            fill_eight_bounding_box_holes_two
        ),
        "recolor_alternating_down_right_runs_four": (
            recolor_alternating_down_right_runs_four
        ),
        "mark_full_line_intersection_neighborhood_four": (
            mark_full_line_intersection_neighborhood_four
        ),
        "shift_singleton_down_fill_above_parity_four": (
            shift_singleton_down_fill_above_parity_four
        ),
        "place_three_plus_at_midpoint_between_ones": (
            place_three_plus_at_midpoint_between_ones
        ),
        "fill_enclosed_zero_regions_one": (
            fill_enclosed_zero_regions_one
        ),
        "connect_aligned_eights_with_threes_any_size": (
            connect_aligned_eights_with_threes_any_size
        ),
        "draw_four_l_path_between_eight_and_two": (
            draw_four_l_path_between_eight_and_two
        ),
        "bounce_diagonal_eight_ray_off_two_wall_three": (
            bounce_diagonal_eight_ray_off_two_wall_three
        ),
        "expand_two_small_pluses_to_five_by_five": (
            expand_two_small_pluses_to_five_by_five
        ),
        "fill_square_enclosed_zero_regions_two": (
            fill_square_enclosed_zero_regions_two
        ),
        "fill_square_five_interiors_by_side": (
            fill_square_five_interiors_by_side
        ),
        "project_contained_color_from_opposite_bbox_corners": (
            project_contained_color_from_opposite_bbox_corners
        ),
        "recolor_five_cells_by_row_guide": (
            recolor_five_cells_by_row_guide
        ),
        "complete_dense_rows_columns_with_two": (
            complete_dense_rows_columns_with_two
        ),
        "draw_alternating_two_step_five_arms_from_singleton": (
            draw_alternating_two_step_five_arms_from_singleton
        ),
        "extend_marker_ray_from_opposite_object_side": (
            extend_marker_ray_from_opposite_object_side
        ),
        "extract_mixed_component_recolor_dominant": (
            extract_mixed_component_recolor_dominant
        ),
        "fill_occupied_columns_eight_then_tile_two_by_two": (
            fill_occupied_columns_eight_then_tile_two_by_two
        ),
        "fill_solid_rectangle_interiors_eight": (
            fill_solid_rectangle_interiors_eight
        ),
        "rank_nonmodal_colors_by_frequency_column": (
            rank_nonmodal_colors_by_frequency_column
        ),
        "read_color_bands_by_centroid_order": (
            read_color_bands_by_centroid_order
        ),
        "render_eight_component_count_diagonal": (
            render_eight_component_count_diagonal
        ),
        "denoise_uniform_row_or_column_bands": (
            denoise_uniform_row_or_column_bands
        ),
        "draw_outer_rectangle_one_inside_four_five_markers": (
            draw_outer_rectangle_one_inside_four_five_markers
        ),
        "draw_six_crosses_through_odd_one_rectangles": (
            draw_six_crosses_through_odd_one_rectangles
        ),
        "extend_two_color_rectangle_to_marker_eight": (
            extend_two_color_rectangle_to_marker_eight
        ),
        "outline_six_components_three_fill_bbox_holes_four": (
            outline_six_components_three_fill_bbox_holes_four
        ),
        "recolor_rectangular_one_loops_three": (
            recolor_rectangular_one_loops_three
        ),
        "reflect_inside_fives_outside_two_frame": (
            reflect_inside_fives_outside_two_frame
        ),
        "reflect_outside_fives_inside_two_frame": (
            reflect_outside_fives_inside_two_frame
        ),
        "vertically_place_solid_rectangles_by_height": (
            vertically_place_solid_rectangles_by_height
        ),
        "collapse_aligned_arm_markers_to_one_two_centers": (
            collapse_aligned_arm_markers_to_one_two_centers
        ),
        "complete_left_line_with_bottom_four_antidiagonal_two": (
            complete_left_line_with_bottom_four_antidiagonal_two
        ),
        "keep_unique_largest_solid_rectangle_in_noise": (
            keep_unique_largest_solid_rectangle_in_noise
        ),
        "mark_two_by_two_fives_diagonal_corners_one_two_three_four": (
            mark_two_by_two_fives_diagonal_corners_one_two_three_four
        ),
        "pack_external_markers_adjacent_to_five_band": (
            pack_external_markers_adjacent_to_five_band
        ),
        "move_nonsolid_color_rectangle_to_touch_solid_rectangle": (
            move_nonsolid_color_rectangle_to_touch_solid_rectangle
        ),
        "reflect_source_across_center_x_shape": (
            reflect_source_across_center_x_shape
        ),
        "punch_alternating_middle_cells_in_three_row_rectangles": (
            punch_alternating_middle_cells_in_three_row_rectangles
        ),
        "copy_marker_ray_offsets_between_opposite_two_lines": (
            copy_marker_ray_offsets_between_opposite_two_lines
        ),
        "recover_rectangular_zero_hole_from_fourfold_symmetry": (
            recover_rectangular_zero_hole_from_fourfold_symmetry
        ),
        "draw_eight_l_path_between_two_and_three": (
            draw_eight_l_path_between_two_and_three
        ),
        "upscale_three_by_three_by_nonzero_count": (
            upscale_three_by_three_by_nonzero_count
        ),
        "slide_five_cell_row_down_left_in_nonzero_count_square": (
            slide_five_cell_row_down_left_in_nonzero_count_square
        ),
        "render_three_by_three_panels_with_duplicate_sixes_one": (
            render_three_by_three_panels_with_duplicate_sixes_one
        ),
        "align_shapes_at_five_markers_in_three_by_three": (
            align_shapes_at_five_markers_in_three_by_three
        ),
        "overlay_panels_across_horizontal_five_separator_bottom_priority": (
            overlay_panels_across_horizontal_five_separator_bottom_priority
        ),
        "extend_row_sequence_by_periodic_horizontal_shift_to_ten": (
            extend_row_sequence_by_periodic_horizontal_shift_to_ten
        ),
        "extend_max_index_diagonal_sequence_to_ten": (
            extend_max_index_diagonal_sequence_to_ten
        ),
        "complete_minimal_colored_quarter_turn_symmetry": (
            complete_minimal_colored_quarter_turn_symmetry
        ),
        "extend_two_by_two_objects_down_by_distinct_color_count": (
            extend_two_by_two_objects_down_by_distinct_color_count
        ),
        "arrange_nine_three_by_three_tiles_by_nonfive_centroid": (
            arrange_nine_three_by_three_tiles_by_nonfive_centroid
        ),
        "project_matching_interior_markers_to_colored_frame": (
            project_matching_interior_markers_to_colored_frame
        ),
        "recolor_one_components_enclosing_nines_eight": (
            recolor_one_components_enclosing_nines_eight
        ),
        "kronecker_multicolor_panel_with_monochrome_mask": (
            kronecker_multicolor_panel_with_monochrome_mask
        ),
        "color_largest_zero_region_one_smallest_eight": (
            color_largest_zero_region_one_smallest_eight
        ),
        "recolor_zero_components_touching_one": (
            recolor_zero_components_touching_one
        ),
        "restore_fourfold_symmetry_over_color_four_masks": (
            restore_fourfold_symmetry_over_color_four_masks
        ),
        "outline_two_dominoes_one_cell_three": (
            outline_two_dominoes_one_cell_three
        ),
        "propagate_zero_holes_across_color_bands": (
            propagate_zero_holes_across_color_bands
        ),
        "render_unique_nonfilled_color_one_cell": (
            render_unique_nonfilled_color_one_cell
        ),
        "restore_latin_diagonal_periodic_square": (
            restore_latin_diagonal_periodic_square
        ),
        "stamp_singletons_as_mapped_three_by_three_squares": (
            stamp_singletons_as_mapped_three_by_three_squares
        ),
        "tile_contiguous_active_row_pattern_by_global_phase": (
            tile_contiguous_active_row_pattern_by_global_phase
        ),
        "fill_rectangle_and_extend_through_single_gap_eight": (
            fill_rectangle_and_extend_through_single_gap_eight
        ),
        "extend_bottom_two_rays_up_detour_right_fives": (
            extend_bottom_two_rays_up_detour_right_fives
        ),
        "extend_two_diagonal_three_squares_with_eight": (
            extend_two_diagonal_three_squares_with_eight
        ),
        "copy_top_five_mask_at_right_edge_markers_two": (
            copy_top_five_mask_at_right_edge_markers_two
        ),
        "extend_one_square_up_left_two_square_down_right": (
            extend_one_square_up_left_two_square_down_right
        ),
        "fill_single_horizontal_gaps_between_ones_two": (
            fill_single_horizontal_gaps_between_ones_two
        ),
        "fill_four_marker_rectangle_interiors_two": (
            fill_four_marker_rectangle_interiors_two
        ),
        "replicate_red_shape_into_zero_matches": (
            replicate_red_shape_into_zero_matches
        ),
        "connect_aligned_eights_rows_and_columns": (
            connect_aligned_eights_rows_and_columns
        ),
        "stamp_three_by_three_grid_at_two_cells": (
            stamp_three_by_three_grid_at_two_cells
        ),
        "tile_gray_shape_with_two_bars_and_eight_squares": (
            tile_gray_shape_with_two_bars_and_eight_squares
        ),
        "fill_c_shape_and_extend_opening_four": (
            fill_c_shape_and_extend_opening_four
        ),
        "complete_minimal_quarter_turn_symmetry_two": (
            complete_minimal_quarter_turn_symmetry_two
        ),
        "recolor_and_chain_gray_endpoint_components": (
            recolor_and_chain_gray_endpoint_components
        ),
        "mark_double_background_vertical_panels_two": (
            mark_double_background_vertical_panels_two
        ),
        "mark_double_background_horizontal_separator_eight": (
            mark_double_background_horizontal_separator_eight
        ),
        "mark_double_background_horizontal_separator_three": (
            mark_double_background_horizontal_separator_three
        ),
        "mark_double_background_vertical_separator_three": (
            mark_double_background_vertical_separator_three
        ),
        "recolor_nonmodal_cells_five": recolor_nonmodal_cells_five,
        "prepend_vertical_mirror": prepend_vertical_mirror,
        "recolor_singleton_components_one": (
            recolor_singleton_components_one
        ),
        "recolor_nonsingleton_components_eight": (
            recolor_nonsingleton_components_eight
        ),
        "render_source_color_glyph_five": (
            render_source_color_glyph_five
        ),
        "replace_red_two_with_diagonal_colors": (
            replace_red_two_with_diagonal_colors
        ),
        "render_distinct_color_count_template_five": (
            render_distinct_color_count_template_five
        ),
        "render_nonzero_count_two": render_nonzero_count_two,
        "select_unique_quadrant": select_unique_quadrant,
        "union_horizontal_panels_six": union_horizontal_panels_six,
        "union_vertical_panels_across_separator_three": (
            union_vertical_panels_across_separator_three
        ),
        "weave_two_uniform_rows_checkerboard": (
            weave_two_uniform_rows_checkerboard
        ),
        "xor_vertical_panels_across_separator_three": (
            xor_vertical_panels_across_separator_three
        ),
        "add_one_at_nonzero_bbox_center": (
            add_one_at_nonzero_bbox_center
        ),
        "blank_bbox_of_unique_filled_rectangle": (
            blank_bbox_of_unique_filled_rectangle
        ),
        "connect_same_color_diagonal_consensus": (
            connect_same_color_diagonal_consensus
        ),
        "connect_same_color_columns_then_rows": (
            connect_same_color_columns_then_rows
        ),
        "center_cell_row": center_cell_row,
        "center_markers_across_lines": center_markers_across_lines,
        "compare_equal_panels_keep_or_erase_second": (
            compare_equal_panels_keep_or_erase_second
        ),
        "compare_two_panels_extract_same_pattern": (
            compare_two_panels_extract_same_pattern
        ),
        "component_sizes_as_bottom_aligned_columns": (
            component_sizes_as_bottom_aligned_columns
        ),
        "cleanup_nonrepeated_opposite_components": (
            cleanup_nonrepeated_opposite_components
        ),
        "cleanup_speckle_cardinal_consensus": (
            cleanup_speckle_cardinal_consensus
        ),
        "copy_container_around_repeated_interior": (
            copy_container_around_repeated_interior
        ),
        "copy_by_repeated_anchor_translation": (
            copy_by_repeated_anchor_translation
        ),
        "complete_partial_same_color_copies": (
            complete_partial_same_color_copies
        ),
        "complete_sparse_cross_lines": complete_sparse_cross_lines,
        "replace_parallel_sides_with_missing_sides": (
            replace_parallel_sides_with_missing_sides
        ),
        "complete_l_trominoes_with_other_color": (
            complete_l_trominoes_with_other_color
        ),
        "complete_from_color_five_template": (
            complete_from_color_five_template
        ),
        "complete_largest_color_reflection": (
            complete_largest_color_reflection
        ),
        "fill_single_missing_symmetry_cell": (
            fill_single_missing_symmetry_cell
        ),
        "connect_markers_to_spanning_line": (
            connect_markers_to_spanning_line
        ),
        "extend_center_toward_largest_margin": (
            extend_center_toward_largest_margin
        ),
        "extend_component_to_perpendicular_line": (
            extend_component_to_perpendicular_line
        ),
        "extend_external_markers_through_frame": (
            extend_external_markers_through_frame
        ),
        "extend_inner_rectangle_cardinal_to_frame": (
            extend_inner_rectangle_cardinal_to_frame
        ),
        "extend_marker_to_periodic_boundary": (
            extend_marker_to_periodic_boundary
        ),
        "extend_unique_marker_vertical_until_blocked": (
            extend_unique_marker_vertical_until_blocked
        ),
        "repair_monochrome_bilateral_symmetry": (
            repair_monochrome_bilateral_symmetry
        ),
        "copy_motif_into_hollow_frame": copy_motif_into_hollow_frame,
        "copy_richer_panel_to_matching_panel": (
            copy_richer_panel_to_matching_panel
        ),
        "complete_checkerboard_in_border": (
            complete_checkerboard_in_border
        ),
        "count_distinct_nonzero_colors_zero_bar": (
            count_distinct_nonzero_colors_zero_bar
        ),
        "count_markers_outside_frame": count_markers_outside_frame,
        "clip_crossing_line_to_repaired_frame": (
            clip_crossing_line_to_repaired_frame
        ),
        "count_panel_markers_inside_frames": (
            count_panel_markers_inside_frames
        ),
        "crop_middle_nonzero_row": crop_middle_nonzero_row,
        "crop_nearest_center_component_excluding_largest": (
            crop_nearest_center_component_excluding_largest
        ),
        "crop_bottom_component": crop_bottom_component,
        "crop_bottom_color_component": crop_bottom_color_component,
        "crop_largest_monochrome_component": (
            crop_largest_monochrome_component
        ),
        "crop_unique_widest_color_component": (
            crop_unique_widest_color_component
        ),
        "crop_unique_smallest_color_component": (
            crop_unique_smallest_color_component
        ),
        "crop_unique_top_color_component": (
            crop_unique_top_color_component
        ),
        "crop_unique_bounded_color_component": (
            crop_unique_bounded_color_component
        ),
        "crop_color_with_unique_component_count": (
            crop_color_with_unique_component_count
        ),
        "crop_rarest_nonzero_color_bbox": (
            crop_rarest_nonzero_color_bbox
        ),
        "crop_largest_solid_nonzero_rectangle": (
            crop_largest_solid_nonzero_rectangle
        ),
        "crop_topmost_color": crop_topmost_color,
        "pack_large_components_horizontally": (
            pack_large_components_horizontally
        ),
        "extract_objects_across_separator": (
            extract_objects_across_separator
        ),
        "extract_regions_enclosed_by_zero": (
            extract_regions_enclosed_by_zero
        ),
        "fill_bounding_box": lambda grid: bounding_box(grid, True),
        "keep_bottommost_component_bbox": (
            keep_bottommost_component_bbox
        ),
        "recolor_all_to_color_with_lowest_top": (
            recolor_all_to_color_with_lowest_top
        ),
        "recolor_highest_ending_component_five": (
            recolor_highest_ending_component_five
        ),
        "recolor_top_occupied_row_two": (
            recolor_top_occupied_row_two
        ),
        "remove_top_and_bottom_colors": (
            remove_top_and_bottom_colors
        ),
        "swap_top_bottom_color_bands": (
            swap_top_bottom_color_bands
        ),
        "crop_most_occluded_filled_bbox": (
            crop_most_occluded_filled_bbox
        ),
        "crop_topmost_bbox_graph_object": (
            crop_topmost_bbox_graph_object
        ),
        "propagate_vertical_pattern_over_horizontal_bands": (
            propagate_vertical_pattern_over_horizontal_bands
        ),
        "recolor_union_to_smallest_bbox_color": (
            recolor_union_to_smallest_bbox_color
        ),
        "remove_hidden_vertical_strands": (
            remove_hidden_vertical_strands
        ),
        "remove_top_layer_reveal_bottom": (
            remove_top_layer_reveal_bottom
        ),
        "restore_occluded_grid_layer": restore_occluded_grid_layer,
        "shift_top_layer_left": shift_top_layer_left,
        "swap_occlusion_order": swap_occlusion_order,
        "swap_vertical_line_crossings": (
            swap_vertical_line_crossings
        ),
        "fill_each_color_bounding_box": fill_each_color_bounding_box,
        "fill_grid_mode_color": fill_grid_mode_color,
        "fill_holes": fill_holes,
        "fill_oriented_hollow_rectangles": (
            fill_oriented_hollow_rectangles
        ),
        "extract_repeated_inner_shapes": extract_repeated_inner_shapes,
        "extract_unique_enclosed_region": extract_unique_enclosed_region,
        "erase_below_separator": erase_below_separator,
        "fill_between_border_with_second_color": (
            fill_between_border_with_second_color
        ),
        "fill_region_below_line": fill_region_below_line,
        "gravity_cells_down": lambda grid: gravity_cells_vertical(
            grid, "down"
        ),
        "gravity_cells_up": lambda grid: gravity_cells_vertical(
            grid, "up"
        ),
        "gravity_unique_rarest_left": gravity_unique_rarest_left,
        "keep_colors_with_multiple_components": (
            keep_colors_with_multiple_components
        ),
        "keep_at_or_below_color_three": (
            keep_at_or_below_color_three
        ),
        "keep_azure_below_top_band": keep_azure_below_top_band,
        "keep_horizontal_stripe_components": (
            keep_horizontal_stripe_components
        ),
        "keep_marker_inside_sparse_bbox": (
            keep_marker_inside_sparse_bbox
        ),
        "keep_marker_only_if_inside_all_frames": (
            keep_marker_only_if_inside_all_frames
        ),
        "keep_markers_between_parallel_lines": (
            keep_markers_between_parallel_lines
        ),
        "keep_objects_inside_other_color": (
            keep_objects_inside_other_color
        ),
        "keep_rarest_inside_structure": (
            keep_rarest_inside_structure
        ),
        "keep_rarest_outside_structure": (
            keep_rarest_outside_structure
        ),
        "keep_segment_or_collinear_marker": (
            keep_segment_or_collinear_marker
        ),
        "keep_repeated_symmetric_monochrome_shapes": (
            keep_repeated_symmetric_monochrome_shapes
        ),
        "keep_repeated_line_orientations": (
            keep_repeated_line_orientations
        ),
        "mark_components_and_singleton_color_bbox_centers": (
            mark_components_and_singleton_color_bbox_centers
        ),
        "most_disconnected_color_singleton": (
            most_disconnected_color_singleton
        ),
        "monochrome_nearest_corner_consensus": (
            monochrome_nearest_corner_consensus
        ),
        "move_arrows_to_pointing_boundary": (
            move_arrows_to_pointing_boundary
        ),
        "mark_above_below_components": mark_above_below_components,
        "mark_bbox_long_axis_green": mark_bbox_long_axis_green,
        "mark_color_band_orientation_azure": (
            mark_color_band_orientation_azure
        ),
        "mark_marker_axis_at_boundary": mark_marker_axis_at_boundary,
        "mark_nonzero_bbox_orientation_red": (
            mark_nonzero_bbox_orientation_red
        ),
        "mark_parallel_rails_green": mark_parallel_rails_green,
        "move_components_from_above_to_below_frame": (
            move_components_from_above_to_below_frame
        ),
        "move_color_group_to_touch_other": (
            move_color_group_to_touch_other
        ),
        "move_marker_opposite_boundary_remove_line": (
            move_marker_opposite_boundary_remove_line
        ),
        "move_markers_to_touch_line_along_alignment": (
            move_markers_to_touch_line_along_alignment
        ),
        "move_marker_between_parallel_lines": (
            move_marker_between_parallel_lines
        ),
        "move_secondary_to_primary_line_center": (
            move_secondary_to_primary_line_center
        ),
        "move_unique_rarest_to_dominant_center": (
            move_unique_rarest_to_dominant_center
        ),
        "move_two_horizontal_clusters_outward": (
            move_two_horizontal_clusters_outward
        ),
        "move_two_spatial_clusters_to_touch": (
            move_two_spatial_clusters_to_touch
        ),
        "move_top_component_down_to_touch": (
            move_top_component_down_to_touch
        ),
        "translate_nonzero_one_down": translate_nonzero_one_down,
        "translate_eight_down_recolor_two": (
            translate_eight_down_recolor_two
        ),
        "outline_bounding_box": lambda grid: bounding_box(grid, False),
        "recolor_outer_frame_azure": recolor_outer_frame_azure,
        "recolor_horizontal_two_runs_green": (
            recolor_horizontal_two_runs_green
        ),
        "recolor_line_components_by_orientation": (
            recolor_line_components_by_orientation
        ),
        "ray_unique_rarest_cardinal_cross": lambda grid: (
            ray_unique_rarest(
                grid,
                ("up", "down", "left", "right"),
            )
        ),
        "ray_unique_rarest_diagonal_x": lambda grid: (
            ray_unique_rarest(
                grid,
                (
                    "up_left",
                    "up_right",
                    "down_left",
                    "down_right",
                ),
            )
        ),
        "ray_unique_rarest_up_right": lambda grid: (
            ray_unique_rarest(grid, ("up_right",))
        ),
        "recolor_two_shapes_by_equality": (
            recolor_two_shapes_by_equality
        ),
        "reconstruct_dense_square_blocks": (
            reconstruct_dense_square_blocks
        ),
        "reconstruct_hollow_outline_rectangles": (
            reconstruct_hollow_outline_rectangles
        ),
        "reconstruct_noisy_dense_rectangles": (
            reconstruct_noisy_dense_rectangles
        ),
        "reconstruct_occluded_small_template": (
            reconstruct_occluded_small_template
        ),
        "reconstruct_repeated_mirrored_components": (
            reconstruct_repeated_mirrored_components
        ),
        "remove_nonmodal_8_connected_singletons": (
            remove_nonmodal_8_connected_singletons
        ),
        "remove_nearest_center_component_zero": (
            remove_nearest_center_component_zero
        ),
        "remove_above_below_green_core": (
            remove_above_below_green_core
        ),
        "remove_repeated_frame_color": remove_repeated_frame_color,
        "remove_uniform_lines": remove_uniform_lines,
        "repeated_component_interior_color": (
            repeated_component_interior_color
        ),
        "repeat_template_from_unit_markers": (
            repeat_template_from_unit_markers
        ),
        "restore_minimum_description_period": (
            restore_minimum_description_period
        ),
        "propagate_unique_rarest_down": propagate_unique_rarest_down,
        "propagate_unique_rarest_up": propagate_unique_rarest_up,
        "extend_uniform_columns_down": extend_uniform_columns_down,
        "rigid_monochrome_all_left": lambda grid: (
            rigid_monochrome_components_horizontal(grid, "left")
        ),
        "rigid_monochrome_all_right": lambda grid: (
            rigid_monochrome_components_horizontal(grid, "right")
        ),
        "scale_2x2_remove_uniform_lines": (
            scale_2x2_remove_uniform_lines
        ),
        "select_first_panel_rotate_counterclockwise": (
            select_first_panel_rotate_counterclockwise
        ),
        "sort_objects_by_size_ascending": (
            sort_objects_by_size_ascending
        ),
        "stamp_template_at_singletons": stamp_template_at_singletons,
        "sort_uniform_row_runs_descending": (
            sort_uniform_row_runs_descending
        ),
        "sort_vertical_panels_by_nonmodal_count": (
            sort_vertical_panels_by_nonmodal_count
        ),
        "order_panels_by_distractor_position": (
            order_panels_by_distractor_position
        ),
        "order_two_panels_by_component_count": (
            order_two_panels_by_component_count
        ),
        "tile_1x2_remove_uniform_lines": (
            tile_1x2_remove_uniform_lines
        ),
        "transfer_secondary_pattern_to_other_shape": (
            transfer_secondary_pattern_to_other_shape
        ),
        "duplicate_grid_along_short_axis": (
            duplicate_grid_along_short_axis
        ),
        "top_down_component_color_sequence": (
            top_down_component_color_sequence
        ),
        "toggle_convex_fill_long_edges": toggle_convex_fill_long_edges,
        "keep_best_intersecting_full_lines": (
            keep_best_intersecting_full_lines
        ),
        "toggle_horizontal_band": toggle_horizontal_band,
        "toggle_scanline_fill_each_shape": (
            toggle_scanline_fill_each_shape
        ),
    }
    for name, function in audited_transforms.items():
        prediction = exact_transform_prediction(
            train_pairs, test_input, function
        )
        if prediction is not None:
            predictions[name] = prediction
    marker_panel_prediction = near_exact_transform_prediction(
        train_pairs,
        test_input,
        sort_marker_panels_by_count,
        max_cell_errors=2,
        min_exact_pairs=1,
    )
    if marker_panel_prediction is not None:
        predictions["near2:sort_marker_panels_by_count"] = (
            marker_panel_prediction
        )

    mapped_count_transforms: dict[
        str, Callable[[Grid], Grid | None]
    ] = {
        "count_distinct_occupied_row_widths": (
            count_distinct_occupied_row_widths_bar
        ),
        "count_hole_cells_4": count_hole_cells_4_bar,
        "count_interior_nonzero_markers7_vertical": (
            count_interior_nonzero_markers7_vertical
        ),
        "count_nonzero_component8_markers6_horizontal": (
            count_nonzero_component8_markers6_horizontal
        ),
        "count_nonzero_components_4": (
            count_nonzero_components_4_bar
        ),
        "count_occlusion_restored_nonzero_objects": (
            count_occlusion_restored_nonzero_objects_bar
        ),
        "count_rare_pixels_vertical": count_rare_pixels_vertical_bar,
        "count_simplified_convex_hull_sides": (
            count_simplified_convex_hull_sides_bar
        ),
    }
    for name, function in mapped_count_transforms.items():
        mapping = infer_color_map(train_pairs, function)
        prediction = function(test_input)
        if mapping is None or prediction is None:
            continue
        mapped = apply_color_map(prediction, mapping)
        if mapped is not None:
            predictions[f"{name}_color_map"] = mapped

    return predictions


def exact_reasons(predictions: dict[str, Grid], candidate: Grid) -> list[str]:
    return sorted(
        reason for reason, prediction in predictions.items() if prediction == candidate
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--challenge", type=Path, required=True)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--trm-early", type=Path, required=True)
    parser.add_argument("--trm-final", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument(
        "--policy",
        choices=("agreement", "aggressive", "evidence"),
        default="agreement",
    )
    args = parser.parse_args()

    challenge = load(args.challenge)
    proof = load(args.proof)
    early = load(args.trm_early)
    final = load(args.trm_final)
    if not (set(challenge) == set(proof) == set(early) == set(final)):
        raise ValueError("submission task IDs do not match the challenge")

    merged: dict[str, list[dict[str, list[list[int]]]]] = {}
    counts = {
        "agreement_selected": 0,
        "aggressive_trm_selected": 0,
        "nvarc_second_retained": 0,
        "duplicate_slot_filled_by_trm": 0,
        "cross_solver_agreement_selected": 0,
        "exact_rule_nvarc_selected": 0,
        "exact_rule_trm_selected": 0,
        "exact_rule_tie_nvarc_selected": 0,
        "direct_exact_rule_selected": 0,
        "trm_rank2_fallback_selected": 0,
        "fallback_used": 0,
    }
    evidence_rows = []
    for task_id, task in challenge.items():
        rows = []
        if not (
            len(proof[task_id])
            == len(early[task_id])
            == len(final[task_id])
            == len(task["test"])
        ):
            raise ValueError(f"wrong output count for {task_id}")
        for index, test_case in enumerate(task["test"]):
            fallback = test_case["input"]
            prow = proof[task_id][index]
            erow = early[task_id][index]
            frow = final[task_id][index]
            n1 = prow.get("attempt_1", fallback)
            n2 = prow.get("attempt_2", fallback)
            t1_early = erow.get("attempt_1", fallback)
            t1_final = frow.get("attempt_1", fallback)
            t2_final = frow.get("attempt_2", fallback)
            n1 = n1 if valid_grid(n1) else fallback
            n2 = n2 if valid_grid(n2) else fallback
            t1_early = t1_early if valid_grid(t1_early) else fallback
            t1_final = t1_final if valid_grid(t1_final) else fallback
            t2_final = t2_final if valid_grid(t2_final) else fallback

            predictions = (
                exact_predictions(task, test_case["input"])
                if args.policy == "evidence"
                else {}
            )
            n2_reasons = exact_reasons(predictions, n2)
            t1_reasons = exact_reasons(predictions, t1_final)
            prediction_groups: dict[str, dict[str, object]] = {}
            for reason, prediction in predictions.items():
                key = json.dumps(prediction, separators=(",", ":"))
                group = prediction_groups.setdefault(
                    key, {"grid": prediction, "reasons": []}
                )
                group["reasons"].append(reason)
            unique_exact = (
                next(iter(prediction_groups.values()))
                if len(prediction_groups) == 1
                else None
            )

            if (
                args.policy == "evidence"
                and unique_exact is not None
                and unique_exact["grid"] != n1
            ):
                second = unique_exact["grid"]
                if second == n2:
                    counts["exact_rule_nvarc_selected"] += 1
                    decision = "unambiguous_exact_rule_nvarc"
                elif second == t1_final:
                    counts["exact_rule_trm_selected"] += 1
                    decision = "unambiguous_exact_rule_trm"
                else:
                    counts["direct_exact_rule_selected"] += 1
                    decision = "unambiguous_direct_exact_rule"
            elif (
                args.policy == "evidence"
                and n2 == t1_final
                and n2 != n1
            ):
                second = n2
                counts["cross_solver_agreement_selected"] += 1
                decision = "cross_solver_agreement"
            elif (
                args.policy == "evidence"
                and n2_reasons
                and not t1_reasons
                and n2 != n1
            ):
                second = n2
                counts["exact_rule_nvarc_selected"] += 1
                decision = "exact_rule_nvarc"
            elif (
                args.policy == "evidence"
                and t1_reasons
                and not n2_reasons
                and t1_final != n1
            ):
                second = t1_final
                counts["exact_rule_trm_selected"] += 1
                decision = "exact_rule_trm"
            elif (
                args.policy == "evidence"
                and n2_reasons
                and t1_reasons
                and n2 != n1
            ):
                if len(t1_reasons) > len(n2_reasons) and t1_final != n1:
                    second = t1_final
                    counts["exact_rule_trm_selected"] += 1
                    decision = "exact_rule_count_trm"
                else:
                    second = n2
                    counts["exact_rule_tie_nvarc_selected"] += 1
                    decision = "exact_rule_tie_nvarc"
            elif (
                args.policy == "evidence"
                and t1_final != n1
            ):
                second = t1_final
                counts["aggressive_trm_selected"] += 1
                decision = "evidence_aggressive_trm"
            elif (
                args.policy == "evidence"
                and t1_early == t1_final
                and t1_final != n1
            ):
                second = t1_final
                counts["agreement_selected"] += 1
                decision = "trm_checkpoint_agreement"
            elif args.policy == "evidence" and n2 != n1:
                second = n2
                counts["nvarc_second_retained"] += 1
                decision = "nvarc_second_default"
            elif args.policy == "evidence" and t1_final != n1:
                second = t1_final
                counts["duplicate_slot_filled_by_trm"] += 1
                decision = "trm_distinct_fallback"
            elif args.policy == "evidence" and t2_final != n1:
                second = t2_final
                counts["trm_rank2_fallback_selected"] += 1
                decision = "trm_rank2_distinct_fallback"
            elif args.policy == "aggressive" and t1_final != n1:
                second = t1_final
                counts["aggressive_trm_selected"] += 1
                decision = "aggressive_trm"
            elif args.policy == "aggressive" and n2 != n1:
                second = n2
                counts["nvarc_second_retained"] += 1
                decision = "aggressive_nvarc_fallback"
            elif args.policy == "aggressive" and t2_final != n1:
                second = t2_final
                counts["duplicate_slot_filled_by_trm"] += 1
                decision = "aggressive_trm_rank2_fallback"
            elif t1_early == t1_final and t1_final != n1:
                second = t1_final
                counts["agreement_selected"] += 1
                decision = "trm_checkpoint_agreement"
            elif n2 != n1:
                second = n2
                counts["nvarc_second_retained"] += 1
                decision = "nvarc_second_default"
            elif t1_final != n1:
                second = t1_final
                counts["duplicate_slot_filled_by_trm"] += 1
                decision = "trm_distinct_fallback"
            else:
                second = fallback
                counts["fallback_used"] += 1
                decision = "input_fallback"
            if args.policy == "evidence":
                evidence_rows.append(
                    {
                        "task_id": task_id,
                        "output_index": index,
                        "decision": decision,
                        "nvarc_exact_reasons": n2_reasons,
                        "trm_exact_reasons": t1_reasons,
                        "trm_checkpoint_agreement": t1_early == t1_final,
                        "cross_solver_agreement": n2 == t1_final,
                        "unambiguous_exact_rule": (
                            unique_exact["reasons"]
                            if unique_exact is not None
                            else []
                        ),
                    }
                )
            rows.append({"attempt_1": n1, "attempt_2": second})
        merged[task_id] = rows

    args.output.write_text(json.dumps(merged), encoding="utf-8")
    receipt = {
        "policy": (
            "nvarc_rank1_plus_trm_rank1"
            if args.policy == "aggressive"
            else (
                "nvarc_rank1_plus_exact_evidence_else_trm_rank1"
                if args.policy == "evidence"
                else "nvarc_rank1_plus_agreed_trm_else_nvarc_rank2"
            )
        ),
        "task_count": len(challenge),
        "test_output_count": sum(len(task["test"]) for task in challenge.values()),
        **counts,
    }
    if args.policy == "evidence":
        receipt["label_free"] = True
        receipt["evidence_rows"] = evidence_rows
    receipt_path = args.receipt or args.output.with_name("selector-receipt.json")
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
