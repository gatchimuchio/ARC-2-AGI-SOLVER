"""Choose a supported simple grid transform by input-derived features.

The selector is task-scoped: it fits transform programs from the current
public training pairs, predicts only by structural input similarity, and
abstains outside the feature range observed among those pairs.
"""
from __future__ import annotations

from collections import Counter, deque
from typing import Any

from .単純変換候補 import apply_model, fitted_models, key, valid_grid


Grid = list[list[int]]
Feature = tuple[float, ...]


def _feature(grid: Grid) -> Feature:
    height, width = len(grid), len(grid[0])
    counts = Counter(color for row in grid for color in row)
    area = height * width
    background = min(counts, key=lambda color: (-counts[color], color))
    points = [
        (row_index, column_index)
        for row_index, row in enumerate(grid)
        for column_index, value in enumerate(row)
        if value != background
    ]
    if points:
        row_start = min(row for row, _ in points)
        row_end = max(row for row, _ in points) + 1
        column_start = min(column for _, column in points)
        column_end = max(column for _, column in points) + 1
        box_height, box_width = row_end - row_start, column_end - column_start
    else:
        box_height = box_width = 0

    seen: set[tuple[int, int]] = set()
    component_sizes = []
    for point in points:
        if point in seen:
            continue
        queue = deque([point])
        seen.add(point)
        size = 0
        while queue:
            row, column = queue.popleft()
            size += 1
            for neighbor in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                neighbor_row, neighbor_column = neighbor
                if (
                    0 <= neighbor_row < height
                    and 0 <= neighbor_column < width
                    and neighbor not in seen
                    and grid[neighbor_row][neighbor_column] != background
                ):
                    seen.add(neighbor)
                    queue.append(neighbor)
        component_sizes.append(size)
    component_sizes.sort(reverse=True)

    horizontal_changes = sum(
        grid[row][column] != grid[row][column + 1]
        for row in range(height)
        for column in range(width - 1)
    )
    vertical_changes = sum(
        grid[row][column] != grid[row + 1][column]
        for row in range(height - 1)
        for column in range(width)
    )
    horizontal_edges = max(1, height * (width - 1))
    vertical_edges = max(1, (height - 1) * width)
    color_profile = sorted((count / area for count in counts.values()), reverse=True)
    color_profile.extend([0.0] * (10 - len(color_profile)))
    size_profile = [size / area for size in component_sizes[:5]]
    size_profile.extend([0.0] * (5 - len(size_profile)))
    return tuple(
        [
            height / 30,
            width / 30,
            height / width,
            len(counts) / 10,
            len(points) / area,
            box_height / 30,
            box_width / 30,
            len(component_sizes) / 30,
            horizontal_changes / horizontal_edges,
            vertical_changes / vertical_edges,
            *color_profile,
            *size_profile,
        ]
    )


def _distance(left: Feature, right: Feature) -> float:
    return sum((a - b) ** 2 for a, b in zip(left, right, strict=True)) / len(left)


class FeatureNeighborTransform:
    """Fit simple per-example transforms and select by structural similarity."""

    def __init__(
        self,
        teachers: list[dict[str, Grid]],
        *,
        precomputed_models: list[list[Any]] | None = None,
        precomputed_features: list[Feature] | None = None,
    ) -> None:
        self.teachers = [
            pair
            for pair in teachers
            if valid_grid(pair.get("input")) and valid_grid(pair.get("output"))
        ]
        self.features = (
            list(precomputed_features)
            if precomputed_features is not None
            else [_feature(pair["input"]) for pair in self.teachers]
        )
        self.models = (
            list(precomputed_models)
            if precomputed_models is not None
            else [fitted_models([pair]) for pair in self.teachers]
        )
        if len(self.features) != len(self.teachers) or len(self.models) != len(self.teachers):
            raise ValueError("precomputed feature/model count must match teachers")
        neighbor_distances = [
            min(
                _distance(self.features[index], other)
                for other_index, other in enumerate(self.features)
                if other_index != index
            )
            for index in range(len(self.features))
            if len(self.features) > 1
        ]
        self.applicability_limit = (
            max(neighbor_distances) * 1.5 + 1e-12
            if neighbor_distances
            else 0.0
        )

    def 候補(self, grid: Grid, _expected: dict[str, Any]) -> tuple[Grid | None, dict[str, Any]]:
        if not valid_grid(grid) or len(self.teachers) < 2:
            return None, {"reason": "insufficient_structural_support"}
        current = _feature(grid)
        distances = [_distance(current, teacher_feature) for teacher_feature in self.features]
        best_distance = min(distances)
        if best_distance > self.applicability_limit:
            return None, {"reason": "outside_training_feature_scope"}
        nearest = [
            index
            for index, distance in enumerate(distances)
            if abs(distance - best_distance) <= 1e-12
        ]
        predictions = set()
        for index in nearest:
            models = self.models[index]
            if not models:
                continue
            simplest_rank = models[0][0]
            for model in models:
                if model[0] != simplest_rank:
                    break
                prediction = apply_model(model, grid)
                if valid_grid(prediction):
                    predictions.add(key(prediction))
        if len(predictions) != 1:
            return None, {"reason": "ambiguous_or_unsupported_transform"}
        return [list(row) for row in next(iter(predictions))], {}

    def 適用範囲内(self, grid: Grid) -> bool:
        candidate, _ = self.候補(grid, {})
        return candidate is not None

    def 最近距離(self, grid: Grid) -> float:
        if not valid_grid(grid) or not self.features:
            return float("inf")
        return self.最近距離特徴量(_feature(grid))
    def 最近距離特徴量(self, feature: Feature | list[float]) -> float:
        if not self.features or len(feature) != len(self.features[0]):
            return float("inf")
        return min(
            _distance(tuple(feature), teacher_feature)
            for teacher_feature in self.features
        )

    def 記録(self) -> dict[str, int | float]:
        return {
            "training_examples": len(self.teachers),
            "transform_supported_examples": sum(bool(models) for models in self.models),
            "applicability_limit": self.applicability_limit,
        }
