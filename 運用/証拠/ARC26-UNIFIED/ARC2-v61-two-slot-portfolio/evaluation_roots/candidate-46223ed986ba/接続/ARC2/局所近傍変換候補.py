"""Learn a translation-invariant cell rule from same-shape teacher examples."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


Grid = list[list[int]]
Context = tuple[int, ...]


def _shape(grid: object) -> tuple[int, int] | None:
    if not isinstance(grid, list) or not grid or not isinstance(grid[0], list) or not grid[0]:
        return None
    width = len(grid[0])
    if any(not isinstance(row, list) or len(row) != width for row in grid):
        return None
    if any(type(color) is not int or not 0 <= color <= 9 for row in grid for color in row):
        return None
    return len(grid), width


def _context(grid: Grid, row: int, column: int) -> Context:
    height, width = len(grid), len(grid[0])
    values = []
    for delta_row in (-1, 0, 1):
        for delta_column in (-1, 0, 1):
            source_row = row + delta_row
            source_column = column + delta_column
            values.append(
                grid[source_row][source_column]
                if 0 <= source_row < height and 0 <= source_column < width
                else -1
            )
    return tuple(values)


class LocalCellContextCandidate:
    """Apply only unambiguous 3x3-context cell mappings learned from teachers.

    Teacher pairs whose input or output dimensions differ from the query are
    ignored. Unknown or contradictory contexts leave the query cell unchanged.
    """

    def __init__(self, teachers: list[dict[str, Grid]]) -> None:
        self.teachers = [
            pair for pair in teachers
            if isinstance(pair, dict)
            and _shape(pair.get("input")) is not None
            and _shape(pair.get("output")) is not None
        ]
        self.cache: dict[tuple[tuple[int, ...], ...], tuple[Grid | None, dict[str, Any]]] = {}

    def 候補(self, grid: Grid, _policy: dict[str, Any] | None = None) -> tuple[Grid | None, dict[str, Any]]:
        shape = _shape(grid)
        if shape is None:
            return None, {"reason": "invalid_grid"}
        query_key = tuple(tuple(row) for row in grid)
        if query_key in self.cache:
            return self.cache[query_key]

        compatible = [
            pair for pair in self.teachers
            if _shape(pair["input"]) == shape and _shape(pair["output"]) == shape
        ]
        if not compatible:
            result = (None, {"reason": "no_same_shape_teacher", "compatible_teachers": 0})
            self.cache[query_key] = result
            return result

        output_counts: dict[Context, Counter[int]] = defaultdict(Counter)
        for pair in compatible:
            source, target = pair["input"], pair["output"]
            for row in range(shape[0]):
                for column in range(shape[1]):
                    output_counts[_context(source, row, column)][target[row][column]] += 1

        mapping = {
            context: next(iter(counts))
            for context, counts in output_counts.items()
            if len(counts) == 1
        }
        prediction = [row[:] for row in grid]
        changed_cells = 0
        for row in range(shape[0]):
            for column in range(shape[1]):
                color = mapping.get(_context(grid, row, column))
                if color is not None and color != grid[row][column]:
                    prediction[row][column] = color
                    changed_cells += 1

        if not changed_cells:
            result = (None, {
                "reason": "no_unambiguous_cell_changes",
                "compatible_teachers": len(compatible),
                "mapped_contexts": len(mapping),
            })
        else:
            result = (prediction, {
                "compatible_teachers": len(compatible),
                "mapped_contexts": len(mapping),
                "changed_cells": changed_cells,
            })
        self.cache[query_key] = result
        return result
