"""Infer a shared crop-plus-geometry program from public teacher pairs.

The candidate is emitted only when at least two distinct teacher inputs fit
one shared D4/crop/geometry/color-map program and every surviving program
produces the same valid test grid.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from .単純変換候補 import (
    _crop_background,
    _fit_color_map,
    orientations,
    valid_grid,
)


Grid = list[list[int]]
GridKey = tuple[tuple[int, ...], ...]
Program = tuple[str, str, str, int, int]

_RATIOS = (
    (1, 2), (2, 1), (2, 2), (1, 3), (3, 1), (2, 3), (3, 2),
    (3, 3), (1, 4), (4, 1), (2, 4), (4, 2), (4, 4),
)
_DOWNSCALES = (
    (2, 1), (1, 2), (2, 2), (3, 1), (1, 3), (3, 3), (4, 1), (1, 4), (4, 4),
)


def _programs() -> tuple[Program, ...]:
    """Enumerate crop followed by one non-identity geometry operation."""
    names = tuple(orientations([[0]]))
    return tuple(
        (orientation, "dominant", operation, rows, columns)
        for orientation in names
        for operation, ratios in (
            ("tile", _RATIOS),
            ("scale", _RATIOS),
            ("downscale", _DOWNSCALES),
        )
        for rows, columns in ratios
    )


def _prepare(grid: Grid, orientation: str, crop: str) -> Grid | None:
    oriented = orientations(grid)[orientation]
    if crop == "none":
        return oriented
    counts = Counter(color for row in oriented for color in row)
    if not counts:
        return None
    background = min(counts, key=lambda color: (-counts[color], color))
    return _crop_background(oriented, background)


def _geometry(grid: Grid, operation: str, row_factor: int, column_factor: int) -> Grid | None:
    if operation == "tile":
        output = [row * column_factor for _ in range(row_factor) for row in grid]
    elif operation == "scale":
        output = []
        for row in grid:
            expanded = [color for color in row for _ in range(column_factor)]
            output.extend([expanded[:] for _ in range(row_factor)])
    elif operation == "downscale":
        height, width = len(grid), len(grid[0])
        if height % row_factor or width % column_factor:
            return None
        output = []
        for row_start in range(0, height, row_factor):
            output_row = []
            for column_start in range(0, width, column_factor):
                block = [
                    grid[row][column]
                    for row in range(row_start, row_start + row_factor)
                    for column in range(column_start, column_start + column_factor)
                ]
                if any(color != block[0] for color in block[1:]):
                    return None
                output_row.append(block[0])
            output.append(output_row)
    else:
        raise ValueError(f"unsupported operation: {operation}")
    return output if valid_grid(output) else None


def _key(grid: Grid) -> GridKey:
    return tuple(tuple(row) for row in grid)


class CompositeGeometryCandidate:
    """Fit and apply one consensus D4 + dominant-crop + geometry program."""

    def __init__(self, teachers: list[dict[str, Grid]]) -> None:
        self.teachers = [
            pair for pair in teachers
            if isinstance(pair, dict)
            and valid_grid(pair.get("input"))
            and valid_grid(pair.get("output"))
        ]
        self.program_count = len(_programs())
        self.orientation_rank = {
            name: index for index, name in enumerate(tuple(orientations([[0]])))
        }
        self.programs: list[tuple[Program, dict[int, int], tuple[int, int, int]]] = []
        self.cache: dict[GridKey, tuple[Grid | None, dict[str, Any]]] = {}
        distinct_inputs = {_key(pair["input"]) for pair in self.teachers}
        if len(self.teachers) < 2 or len(distinct_inputs) < 2:
            return

        oriented_teachers = [
            {name: orientations(pair["input"])[name] for name in tuple(orientations([[0]]))}
            for pair in self.teachers
        ]
        for program in _programs():
            orientation, crop, operation, row_factor, column_factor = program
            color_map: dict[int, int] = {}
            for teacher, oriented in zip(self.teachers, oriented_teachers, strict=True):
                source = oriented[orientation]
                if crop == "dominant":
                    counts = Counter(color for row in source for color in row)
                    if not counts:
                        break
                    background = min(counts, key=lambda color: (-counts[color], color))
                    source = _crop_background(source, background)
                if source is None:
                    break
                transformed = _geometry(source, operation, row_factor, column_factor)
                if transformed is None or not _fit_color_map(
                    transformed, teacher["output"], color_map
                ):
                    break
            else:
                self.programs.append((program, dict(color_map), self._rank(program)))

    def _rank(self, program: Program) -> tuple[int, int, int]:
        orientation, _crop, operation, row_factor, column_factor = program
        operation_rank = {"scale": 2, "downscale": 2, "tile": 3}[operation]
        return (
            operation_rank,
            row_factor * column_factor,
            self.orientation_rank[orientation],
        )

    def 候補(self, grid: Grid, _policy: dict[str, Any]) -> tuple[Grid | None, dict[str, Any]]:
        if not valid_grid(grid):
            return None, {"reason": "invalid_grid"}
        query_key = _key(grid)
        if query_key in self.cache:
            return self.cache[query_key]
        best_rank = min((rank for _, _, rank in self.programs), default=None)
        if best_rank is None:
            record = {"reason": "no_fitted_program", "fitted_programs": 0}
            self.cache[query_key] = (None, record)
            return None, record
        predictions: set[GridKey] = set()
        selected_programs = 0
        for program, color_map, rank in self.programs:
            if rank != best_rank:
                continue
            selected_programs += 1
            orientation, crop, operation, row_factor, column_factor = program
            source = _prepare(grid, orientation, crop)
            if source is None:
                continue
            transformed = _geometry(source, operation, row_factor, column_factor)
            if transformed is None:
                continue
            candidate = [[color_map.get(color, color) for color in row] for row in transformed]
            if valid_grid(candidate):
                predictions.add(_key(candidate))
                if len(predictions) > 1:
                    record = {
                        "reason": "programs_disagree",
                        "fitted_programs": len(self.programs),
                        "selected_programs": selected_programs,
                    }
                    self.cache[query_key] = (None, record)
                    return None, record
        if len(predictions) != 1:
            record = {
                "reason": "no_consensus_program",
                "fitted_programs": len(self.programs),
                "selected_programs": selected_programs,
            }
            self.cache[query_key] = (None, record)
            return None, record
        prediction = [list(row) for row in next(iter(predictions))]
        record = {
            "fitted_programs": len(self.programs),
            "selected_programs": selected_programs,
            "consensus": True,
        }
        self.cache[query_key] = (prediction, record)
        return prediction, record

    def 記録(self) -> dict[str, int]:
        return {
            "training_examples": len(self.teachers),
            "program_descriptors": self.program_count,
            "fitted_programs": len(self.programs),
            "selected_programs": sum(
                rank == min((r for _, _, r in self.programs), default=None)
                for _, _, rank in self.programs
            ),
        }
