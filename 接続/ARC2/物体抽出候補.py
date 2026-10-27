"""Fit a train-consistent object-selection and crop transform."""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
from typing import Any


Grid = list[list[int]]
GridKey = tuple[tuple[int, ...], ...]
Segmentation = tuple[int, bool]
Model = tuple[Segmentation, str, str, dict[int, int]]

_SEGMENTATIONS: tuple[Segmentation, ...] = (
    (4, True), (8, True), (4, False), (8, False),
)
_SELECTORS = (
    "area:min", "area:max", "box:min", "box:max",
    "height:min", "height:max", "width:min", "width:max",
    "top:min", "top:max", "left:min", "left:max",
    "bottom:min", "bottom:max", "right:min", "right:max",
    "center_y:min", "center_y:max", "center_x:min", "center_x:max",
    "color_count:min", "color_count:max",
)
_OUTLIER_SELECTORS = (
    "area:unique", "box:unique", "height:unique", "width:unique",
    "color_count:unique", "shape:unique", "perimeter:unique",
    "perimeter:min", "perimeter:max",
    "holes:unique", "holes:min", "holes:max",
    "symmetry:unique", "symmetry:min", "symmetry:max",
    "aspect:unique", "aspect:min", "aspect:max",
    "solidity:unique", "solidity:min", "solidity:max",
    "touches_border:unique",
)
_PALETTE_SELECTORS = (
    "palette:unique",
    "dominant_color:unique", "dominant_color:min", "dominant_color:max",
    "dominant_count:unique", "dominant_count:min", "dominant_count:max",
    "palette_frequency:unique", "palette_frequency:min", "palette_frequency:max",
    "area_palette:unique", "box_palette:unique", "shape_palette:unique",
    "aspect_palette:unique", "holes_palette:unique", "perimeter_palette:unique",
    "symmetry_palette:unique", "shape_area:unique", "shape_box:unique",
    "shape_dominant_color:unique", "area_dominant_color:unique",
    "shape_color_count:unique", "area_dominant_count:unique",
)
_ORIENTATIONS = ("id", "r90", "r180", "r270", "fh", "fv", "t", "at")


def _valid_grid(grid: object) -> bool:
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


def _grid_key(grid: Grid) -> GridKey:
    return tuple(tuple(row) for row in grid)


def _orient(grid: Grid, orientation: str) -> Grid:
    transpose = [list(row) for row in zip(*grid)]
    if orientation == "id":
        return [row[:] for row in grid]
    if orientation == "r90":
        return [list(row) for row in zip(*grid[::-1])]
    if orientation == "r180":
        return [row[::-1] for row in grid[::-1]]
    if orientation == "r270":
        return [list(row) for row in zip(*grid)][::-1]
    if orientation == "fh":
        return [row[::-1] for row in grid]
    if orientation == "fv":
        return grid[::-1]
    if orientation == "t":
        return transpose
    if orientation == "at":
        return [row[::-1] for row in transpose[::-1]]
    raise ValueError(f"unsupported orientation: {orientation}")


def _background(grid: Grid) -> int:
    counts = Counter(color for row in grid for color in row)
    return min(counts, key=lambda color: (-counts[color], color))


def _shape_signature(cells: set[tuple[int, int]]) -> tuple[
    tuple[tuple[int, int], ...], int
]:
    transforms = (
        lambda y, x: (y, x), lambda y, x: (x, -y),
        lambda y, x: (-y, -x), lambda y, x: (-x, y),
        lambda y, x: (y, -x), lambda y, x: (-y, x),
        lambda y, x: (x, y), lambda y, x: (-x, -y),
    )
    signatures = []
    for transform in transforms:
        points = [transform(y, x) for y, x in cells]
        min_y = min(y for y, _ in points)
        min_x = min(x for _, x in points)
        signatures.append(tuple(sorted(
            (y - min_y, x - min_x) for y, x in points
        )))
    original = tuple(sorted(
        (y - min(y for y, _ in cells), x - min(x for _, x in cells))
        for y, x in cells
    ))
    return min(signatures), sum(signature == original for signature in signatures)


def _hole_count(cells: set[tuple[int, int]], height: int, width: int) -> int:
    empty = {
        (y, x)
        for y in range(height)
        for x in range(width)
        if (y, x) not in cells
    }
    outside = {
        point for point in empty
        if point[0] in (0, height - 1) or point[1] in (0, width - 1)
    }
    pending = list(outside)
    while pending:
        y, x = pending.pop()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            point = (y + dy, x + dx)
            if point in empty and point not in outside:
                outside.add(point)
                pending.append(point)
    holes = empty - outside
    count = 0
    while holes:
        count += 1
        pending = [holes.pop()]
        while pending:
            y, x = pending.pop()
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                point = (y + dy, x + dx)
                if point in holes:
                    holes.remove(point)
                    pending.append(point)
    return count


def _components(
    grid: Grid,
    connectivity: int,
    same_color: bool,
    *,
    extended: bool = False,
) -> list[dict[str, Any]]:
    height, width = len(grid), len(grid[0])
    background = _background(grid)
    grid_color_counts = (
        Counter(color for row in grid for color in row) if extended else {}
    )
    visited: set[tuple[int, int]] = set()
    objects: list[dict[str, Any]] = []
    deltas = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if connectivity == 8:
        deltas.extend(((-1, -1), (-1, 1), (1, -1), (1, 1)))

    for row in range(height):
        for column in range(width):
            color = grid[row][column]
            if color == background or (row, column) in visited:
                continue
            pending = [(row, column)]
            visited.add((row, column))
            cells: list[tuple[int, int]] = []
            while pending:
                y, x = pending.pop()
                cells.append((y, x))
                for dy, dx in deltas:
                    yy, xx = y + dy, x + dx
                    if not (0 <= yy < height and 0 <= xx < width):
                        continue
                    if (yy, xx) in visited or grid[yy][xx] == background:
                        continue
                    if same_color and grid[yy][xx] != color:
                        continue
                    visited.add((yy, xx))
                    pending.append((yy, xx))

            top = min(y for y, _ in cells)
            bottom = max(y for y, _ in cells)
            left = min(x for _, x in cells)
            right = max(x for _, x in cells)
            colors = {grid[y][x] for y, x in cells}
            object_height, object_width = bottom - top + 1, right - left + 1
            objects.append({
                "area": len(cells),
                "box": object_height * object_width,
                "height": object_height,
                "width": object_width,
                "top": top,
                "bottom": bottom,
                "left": left,
                "right": right,
                "center_y": sum(y for y, _ in cells) / len(cells),
                "center_x": sum(x for _, x in cells) / len(cells),
                "color_count": len(colors),
                "crop": [line[left:right + 1] for line in grid[top:bottom + 1]],
            })
            if extended:
                local_cells = {(y - top, x - left) for y, x in cells}
                shape, symmetry = _shape_signature(local_cells)
                object_color_counts = Counter(grid[y][x] for y, x in cells)
                palette = tuple(sorted(object_color_counts))
                dominant_color = min(
                    object_color_counts,
                    key=lambda color: (-object_color_counts[color], color),
                )
                perimeter = sum(
                    (y + dy, x + dx) not in local_cells
                    for y, x in local_cells
                    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))
                )
                holes = _hole_count(
                    local_cells, object_height, object_width
                )
                aspect = Fraction(object_width, object_height)
                objects[-1].update({
                    "shape": shape,
                    "perimeter": perimeter,
                    "holes": holes,
                    "symmetry": symmetry,
                    "aspect": aspect,
                    "solidity": Fraction(
                        len(cells), object_height * object_width
                    ),
                    "touches_border": any(
                        y in (0, height - 1) or x in (0, width - 1)
                        for y, x in cells
                    ),
                    "palette": palette,
                    "dominant_color": dominant_color,
                    "dominant_count": object_color_counts[dominant_color],
                    "palette_frequency": sum(
                        grid_color_counts[color] for color in palette
                    ),
                    "area_palette": (len(cells), palette),
                    "box_palette": (object_height * object_width, palette),
                    "shape_palette": (shape, palette),
                    "aspect_palette": (aspect, palette),
                    "holes_palette": (holes, palette),
                    "perimeter_palette": (perimeter, palette),
                    "symmetry_palette": (symmetry, palette),
                    "shape_area": (shape, len(cells)),
                    "shape_box": (shape, object_height * object_width),
                    "shape_dominant_color": (shape, dominant_color),
                    "area_dominant_color": (len(cells), dominant_color),
                    "shape_color_count": (shape, len(colors)),
                    "area_dominant_count": (
                        len(cells), object_color_counts[dominant_color]
                    ),
                })
    return objects


def _select(objects: list[dict[str, Any]], selector: str) -> dict[str, Any] | None:
    if not objects:
        return None
    feature, direction = selector.split(":")
    values = [obj[feature] for obj in objects]
    extreme = min(values) if direction == "min" else max(values)
    matches = [
        obj for obj, value in zip(objects, values, strict=True)
        if value == extreme
    ]
    return matches[0] if len(matches) == 1 else None


def _select_outlier(
    objects: list[dict[str, Any]], selector: str
) -> dict[str, Any] | None:
    feature, mode = selector.split(":")
    if mode != "unique":
        return _select(objects, selector)
    if not objects:
        return None
    frequencies = Counter(obj[feature] for obj in objects)
    singletons = [
        obj for obj in objects if frequencies[obj[feature]] == 1
    ]
    if len(singletons) != 1 or not any(
        count > 1 for count in frequencies.values()
    ):
        return None
    return singletons[0]


def _fit_color_map(source: Grid, target: Grid, mapping: dict[int, int]) -> bool:
    if len(source) != len(target) or len(source[0]) != len(target[0]):
        return False
    for source_row, target_row in zip(source, target, strict=True):
        for source_color, target_color in zip(source_row, target_row, strict=True):
            previous = mapping.get(source_color)
            if previous is not None and previous != target_color:
                return False
            mapping[source_color] = target_color
    return True


def _fit(
    teachers: list[dict[str, Grid]],
    selectors: tuple[str, ...] = _SELECTORS,
    *,
    extended: bool = False,
) -> list[Model]:
    if len(teachers) < 2 or any(
        not isinstance(pair, dict)
        or not _valid_grid(pair.get("input"))
        or not _valid_grid(pair.get("output"))
        for pair in teachers
    ):
        return []

    cached = [
        {
            "output": pair["output"],
            "objects": {
                segmentation: _components(
                    pair["input"], *segmentation, extended=extended
                )
                for segmentation in _SEGMENTATIONS
            },
        }
        for pair in teachers
    ]
    models: list[Model] = []
    for segmentation in _SEGMENTATIONS:
        for selector in selectors:
            for orientation in _ORIENTATIONS:
                color_map: dict[int, int] = {}
                for pair in cached:
                    objects = pair["objects"][segmentation]
                    obj = (
                        _select_outlier(objects, selector)
                        if extended
                        else _select(objects, selector)
                    )
                    if obj is None:
                        break
                    transformed = _orient(obj["crop"], orientation)
                    if not _fit_color_map(transformed, pair["output"], color_map):
                        break
                else:
                    models.append((segmentation, selector, orientation, color_map.copy()))
    return models


def _apply(
    model: Model, grid: Grid, *, outlier: bool = False
) -> Grid | None:
    segmentation, selector, orientation, color_map = model
    objects = _components(grid, *segmentation, extended=outlier)
    obj = (
        _select_outlier(objects, selector)
        if outlier
        else _select(objects, selector)
    )
    if obj is None:
        return None
    transformed = _orient(obj["crop"], orientation)
    result = [
        [color_map.get(color, color) for color in row]
        for row in transformed
    ]
    return result if _valid_grid(result) else None


def _candidate_from_models(
    models: list[Model], test_input: Grid, *, outlier: bool = False
) -> tuple[Grid | None, dict[str, int]]:
    if not _valid_grid(test_input):
        return None, {"fitted_models": len(models), "applicable_models": 0}
    predictions: Counter[GridKey] = Counter()
    grids: dict[GridKey, Grid] = {}
    applicable = 0
    for model in models:
        output = _apply(model, test_input, outlier=outlier)
        if output is None:
            continue
        applicable += 1
        key = _grid_key(output)
        predictions[key] += 1
        grids[key] = output
    if not predictions:
        return None, {"fitted_models": len(models), "applicable_models": 0}
    top_votes = max(predictions.values())
    winners = [key for key, votes in predictions.items() if votes == top_votes]
    candidate = grids[winners[0]] if top_votes >= 2 and len(winners) == 1 else None
    return candidate, {
        "fitted_models": len(models),
        "applicable_models": applicable,
        "distinct_predictions": len(predictions),
        "top_votes": top_votes,
    }


class ObjectExtractionCandidate:
    """Emit teacher-supported object-extraction outputs, including outliers."""

    def __init__(self, teachers: list[dict[str, Grid]]) -> None:
        self.teachers = teachers
        self.models = _fit(teachers)
        self._outlier_models: list[Model] | None = None
        self._palette_models: list[Model] | None = None

    def candidate(self, test_input: Grid) -> tuple[Grid | None, dict[str, int]]:
        return _candidate_from_models(self.models, test_input)

    def outlier_candidate(
        self, test_input: Grid
    ) -> tuple[Grid | None, dict[str, int]]:
        if self._outlier_models is None:
            self._outlier_models = _fit(
                self.teachers, _OUTLIER_SELECTORS, extended=True
            )
        return _candidate_from_models(
            self._outlier_models, test_input, outlier=True
        )

    def palette_candidate(
        self, test_input: Grid
    ) -> tuple[Grid | None, dict[str, int]]:
        if self._palette_models is None:
            self._palette_models = _fit(
                self.teachers, _PALETTE_SELECTORS, extended=True
            )
        return _candidate_from_models(
            self._palette_models, test_input, outlier=True
        )
