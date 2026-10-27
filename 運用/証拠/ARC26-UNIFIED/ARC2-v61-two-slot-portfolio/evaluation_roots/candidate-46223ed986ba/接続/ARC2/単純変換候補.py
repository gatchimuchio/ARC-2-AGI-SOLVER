"""Fit small grid transforms to every public teacher pair and predict test grids.

This module is a bounded alternate-candidate generator. It never reads task
identifiers, evaluation solutions, or prior answer tables. Callers should use
only a unique output shared by all fitted models.
"""
from __future__ import annotations

from collections import Counter
from typing import Any


Grid = list[list[int]]
GridKey = tuple[tuple[int, ...], ...]
Model = tuple[tuple[Any, ...], str, tuple[str, int, int, int | None], dict[int, int]]


def key(grid: Grid) -> GridKey:
    return tuple(tuple(row) for row in grid)


def valid_grid(grid: object) -> bool:
    return (
        isinstance(grid, list)
        and 1 <= len(grid) <= 30
        and all(
            isinstance(row, list)
            and 1 <= len(row) <= 30
            and len(row) == len(grid[0])
            and all(type(color) is int and 0 <= color <= 9 for color in row)
            for row in grid
        )
    )


def orientations(grid: Grid) -> dict[str, Grid]:
    transpose = [list(row) for row in zip(*grid)]
    return {
        "identity": [row[:] for row in grid],
        "rotate90": [list(row) for row in zip(*grid[::-1])],
        "rotate180": [row[::-1] for row in grid[::-1]],
        "rotate270": [list(row) for row in zip(*grid)][::-1],
        "reflect_horizontal": [row[::-1] for row in grid],
        "reflect_vertical": grid[::-1],
        "transpose": transpose,
        "anti_transpose": [row[::-1] for row in transpose[::-1]],
    }


def _crop_background(grid: Grid, background: int) -> Grid | None:
    points = [
        (row_index, column_index)
        for row_index, row in enumerate(grid)
        for column_index, color in enumerate(row)
        if color != background
    ]
    if not points:
        return None
    row_start = min(row for row, _ in points)
    row_end = max(row for row, _ in points) + 1
    column_start = min(column for _, column in points)
    column_end = max(column for _, column in points) + 1
    return [row[column_start:column_end] for row in grid[row_start:row_end]]


def _geometry(grid: Grid, descriptor: tuple[str, int, int, int | None]) -> Grid | None:
    mode, row_factor, column_factor, background = descriptor
    if mode == "plain":
        return [row[:] for row in grid]
    if mode == "crop":
        return _crop_background(grid, background)
    if mode == "scale":
        output = []
        for row in grid:
            expanded = [color for color in row for _ in range(column_factor)]
            output.extend([expanded[:] for _ in range(row_factor)])
        return output
    if mode == "tile":
        return [row * column_factor for _ in range(row_factor) for row in grid]
    if mode == "downscale":
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
        return output
    raise ValueError(f"unknown transform mode: {mode}")


def _descriptors(
    teachers: list[dict[str, Grid]],
) -> list[tuple[str, tuple[str, int, int, int | None]]]:
    modes: list[tuple[str, int, int, int | None]] = [("plain", 1, 1, None)]
    ratios = [
        (1, 2), (2, 1), (2, 2), (1, 3), (3, 1), (2, 3),
        (3, 2), (3, 3), (1, 4), (4, 1), (2, 4), (4, 2), (4, 4),
    ]
    modes.extend(("scale", rows, columns, None) for rows, columns in ratios)
    modes.extend(("tile", rows, columns, None) for rows, columns in ratios)
    downs = [(2, 1), (1, 2), (2, 2), (3, 1), (1, 3), (3, 3), (4, 1), (1, 4), (4, 4)]
    modes.extend(("downscale", rows, columns, None) for rows, columns in downs)
    backgrounds = {
        color
        for pair in teachers
        for row in pair["input"]
        for color in row
    }
    modes.extend(("crop", 1, 1, background) for background in sorted(backgrounds))
    return [
        (orientation, descriptor)
        for orientation in orientations(teachers[0]["input"])
        for descriptor in modes
    ]


def _fit_color_map(source: Grid, target: Grid, mapping: dict[int, int]) -> bool:
    if not source or len(source) != len(target) or len(source[0]) != len(target[0]):
        return False
    for source_row, target_row in zip(source, target, strict=True):
        for source_color, target_color in zip(source_row, target_row, strict=True):
            previous = mapping.get(source_color)
            if previous is not None and previous != target_color:
                return False
            mapping[source_color] = target_color
    return True


def fitted_models(teachers: list[dict[str, Grid]]) -> list[Model]:
    if not teachers:
        return []
    if not all(
        isinstance(pair, dict)
        and valid_grid(pair.get("input"))
        and valid_grid(pair.get("output"))
        for pair in teachers
    ):
        return []
    fitted: list[Model] = []
    first_input = teachers[0]["input"]
    orientation_names = list(orientations(first_input))
    for orientation_name, descriptor in _descriptors(teachers):
        mapping: dict[int, int] = {}
        for pair in teachers:
            oriented = orientations(pair["input"])[orientation_name]
            transformed = _geometry(oriented, descriptor)
            if transformed is None or not _fit_color_map(transformed, pair["output"], mapping):
                break
        else:
            if mapping:
                mode, row_factor, column_factor, background = descriptor
                mode_rank = {"plain": 0, "crop": 1, "scale": 2, "downscale": 2, "tile": 3}[mode]
                rank = (
                    mode_rank,
                    row_factor * column_factor,
                    orientation_names.index(orientation_name),
                    mode,
                    background if background is not None else -1,
                )
                fitted.append((rank, orientation_name, descriptor, dict(mapping)))
    fitted.sort(key=lambda model: model[0])
    return fitted


def apply_model(model: Model, grid: Grid) -> Grid | None:
    _, orientation_name, descriptor, mapping = model
    transformed = _geometry(orientations(grid)[orientation_name], descriptor)
    if transformed is None:
        return None
    output = [[mapping.get(color, color) for color in row] for row in transformed]
    return output if valid_grid(output) else None


def predict_pool(
    teachers: list[dict[str, Grid]],
    test_input: Grid,
    *,
    fit_examples: list[dict[str, Grid]] | None = None,
) -> tuple[list[Model], Counter[GridKey], Grid | None, Model | None]:
    if not valid_grid(test_input):
        return [], Counter(), None, None
    models = fitted_models(teachers if fit_examples is None else fit_examples)
    predictions: Counter[GridKey] = Counter()
    simplest = None
    simplest_model = None
    for model in models:
        output = apply_model(model, test_input)
        if output is None:
            continue
        predictions[key(output)] += 1
        if simplest is None:
            simplest = output
            simplest_model = model
    return models, predictions, simplest, simplest_model


def unique_candidate(teachers: list[dict[str, Grid]], test_input: Grid) -> Grid | None:
    """Return a distinct grid only when at least two teacher pairs support one output."""
    if len(teachers) < 2:
        return None
    _, predictions, _, _ = predict_pool(teachers, test_input)
    if len(predictions) != 1:
        return None
    return [list(row) for row in next(iter(predictions))]
