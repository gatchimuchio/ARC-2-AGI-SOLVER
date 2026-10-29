"""Proof-guided symbolic baseline for ARC Prize 2026 (ARC-AGI-2).

The solver enumerates a small, inspectable language of grid programs.  A
candidate is a proof only when it reproduces every training output exactly.
Surviving programs are ranked by description length; the two shortest
distinct predictions are returned for each test input.

The implementation is deliberately self-contained and uses only NumPy and
the Python standard library so it can run in an offline Kaggle notebook.
"""

from __future__ import annotations

import json
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np


Grid = np.ndarray
GridFunction = Callable[[Grid], Grid | None]


def as_grid(value: Sequence[Sequence[int]] | Grid) -> Grid:
    grid = np.asarray(value, dtype=np.int8)
    if grid.ndim != 2 or not (1 <= grid.shape[0] <= 30 and 1 <= grid.shape[1] <= 30):
        raise ValueError("ARC grids must be rectangular arrays from 1x1 to 30x30")
    return grid


def freeze(grid: Grid) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(cell) for cell in row) for row in grid.tolist())


def background(grid: Grid) -> int:
    counts = Counter(int(cell) for cell in grid.flat)
    return min(counts, key=lambda color: (-counts[color], color))


def safe(function: GridFunction, grid: Grid) -> Grid | None:
    try:
        result = function(grid.copy())
        if result is None:
            return None
        result = np.asarray(result, dtype=np.int8)
        if result.ndim != 2 or result.size == 0:
            return None
        if result.shape[0] > 30 or result.shape[1] > 30:
            return None
        if np.any((result < 0) | (result > 9)):
            return None
        return result
    except (IndexError, ValueError, TypeError, ZeroDivisionError):
        return None


@dataclass(frozen=True)
class Primitive:
    name: str
    cost: float
    function: GridFunction


@dataclass
class Candidate:
    name: str
    cost: float
    function: GridFunction
    exact: bool
    training_score: float


def dihedral_primitives() -> list[Primitive]:
    return [
        Primitive("identity", 0.0, lambda g: g),
        Primitive("rotate90", 1.0, lambda g: np.rot90(g, 1)),
        Primitive("rotate180", 1.0, lambda g: np.rot90(g, 2)),
        Primitive("rotate270", 1.0, lambda g: np.rot90(g, 3)),
        Primitive("flip_horizontal", 1.0, lambda g: np.fliplr(g)),
        Primitive("flip_vertical", 1.0, lambda g: np.flipud(g)),
        Primitive("transpose", 1.0, lambda g: g.T),
        Primitive("anti_transpose", 1.2, lambda g: np.fliplr(np.flipud(g)).T),
    ]


def crop_nonbackground(grid: Grid, forced_background: int | None = None) -> Grid:
    bg = background(grid) if forced_background is None else forced_background
    points = np.argwhere(grid != bg)
    if not len(points):
        return grid.copy()
    r0, c0 = points.min(axis=0)
    r1, c1 = points.max(axis=0)
    return grid[r0 : r1 + 1, c0 : c1 + 1]


def trim_uniform_border(grid: Grid) -> Grid:
    result = grid.copy()
    changed = True
    while changed and min(result.shape) > 1:
        changed = False
        if result.shape[0] > 1 and np.all(result[0] == result[0, 0]):
            result = result[1:]
            changed = True
        if result.shape[0] > 1 and np.all(result[-1] == result[-1, 0]):
            result = result[:-1]
            changed = True
        if result.shape[1] > 1 and np.all(result[:, 0] == result[0, 0]):
            result = result[:, 1:]
            changed = True
        if result.shape[1] > 1 and np.all(result[:, -1] == result[0, -1]):
            result = result[:, :-1]
            changed = True
    return result


def remove_uniform_lines(grid: Grid) -> Grid:
    rows = [index for index, row in enumerate(grid) if not np.all(row == row[0])]
    columns = [
        index for index in range(grid.shape[1])
        if not np.all(grid[:, index] == grid[0, index])
    ]
    if not rows or not columns:
        return grid.copy()
    return grid[np.ix_(rows, columns)]


def fill_holes(grid: Grid) -> Grid:
    bg = background(grid)
    height, width = grid.shape
    exterior = np.zeros_like(grid, dtype=bool)
    queue: deque[tuple[int, int]] = deque()
    for row in range(height):
        for column in (0, width - 1):
            if grid[row, column] == bg and not exterior[row, column]:
                exterior[row, column] = True
                queue.append((row, column))
    for column in range(width):
        for row in (0, height - 1):
            if grid[row, column] == bg and not exterior[row, column]:
                exterior[row, column] = True
                queue.append((row, column))
    while queue:
        row, column = queue.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = row + dr, column + dc
            if (
                0 <= nr < height
                and 0 <= nc < width
                and grid[nr, nc] == bg
                and not exterior[nr, nc]
            ):
                exterior[nr, nc] = True
                queue.append((nr, nc))
    result = grid.copy()
    enclosed = (grid == bg) & ~exterior
    if np.any(enclosed):
        colors = [int(value) for value in grid[grid != bg]]
        fill = Counter(colors).most_common(1)[0][0] if colors else bg
        result[enclosed] = fill
    return result


def bounding_box(grid: Grid, filled: bool) -> Grid:
    bg = background(grid)
    points = np.argwhere(grid != bg)
    if not len(points):
        return grid.copy()
    r0, c0 = points.min(axis=0)
    r1, c1 = points.max(axis=0)
    result = grid.copy()
    colors = [int(value) for value in grid[grid != bg]]
    color = Counter(colors).most_common(1)[0][0]
    if filled:
        result[r0 : r1 + 1, c0 : c1 + 1] = color
    else:
        result[r0, c0 : c1 + 1] = color
        result[r1, c0 : c1 + 1] = color
        result[r0 : r1 + 1, c0] = color
        result[r0 : r1 + 1, c1] = color
    return result


def connected_components(
    grid: Grid, *, same_color: bool = True, diagonal: bool = False
) -> list[list[tuple[int, int]]]:
    bg = background(grid)
    seen = np.zeros_like(grid, dtype=bool)
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if diagonal:
        steps += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    components: list[list[tuple[int, int]]] = []
    for row, column in np.argwhere(grid != bg):
        row, column = int(row), int(column)
        if seen[row, column]:
            continue
        color = grid[row, column]
        queue = deque([(row, column)])
        seen[row, column] = True
        component: list[tuple[int, int]] = []
        while queue:
            r, c = queue.popleft()
            component.append((r, c))
            for dr, dc in steps:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < grid.shape[0] and 0 <= nc < grid.shape[1]):
                    continue
                if seen[nr, nc] or grid[nr, nc] == bg:
                    continue
                if same_color and grid[nr, nc] != color:
                    continue
                seen[nr, nc] = True
                queue.append((nr, nc))
        components.append(component)
    return components


def component_key(component: list[tuple[int, int]], selector: str) -> tuple:
    rows = [point[0] for point in component]
    columns = [point[1] for point in component]
    area = len(component)
    height = max(rows) - min(rows) + 1
    width = max(columns) - min(columns) + 1
    keys = {
        "largest": (-area, min(rows), min(columns)),
        "smallest": (area, min(rows), min(columns)),
        "top": (min(rows), min(columns), -area),
        "bottom": (-max(rows), min(columns), -area),
        "left": (min(columns), min(rows), -area),
        "right": (-max(columns), min(rows), -area),
        "tallest": (-height, -area, min(rows), min(columns)),
        "widest": (-width, -area, min(rows), min(columns)),
    }
    return keys[selector]


def extract_component(
    grid: Grid,
    selector: str,
    *,
    same_color: bool = True,
    diagonal: bool = False,
    crop: bool = True,
) -> Grid:
    components = connected_components(
        grid, same_color=same_color, diagonal=diagonal
    )
    if not components:
        return grid.copy()
    component = min(components, key=lambda item: component_key(item, selector))
    bg = background(grid)
    result = np.full_like(grid, bg)
    for row, column in component:
        result[row, column] = grid[row, column]
    return crop_nonbackground(result, bg) if crop else result


def split_panels(grid: Grid) -> list[Grid]:
    separator_rows = [r for r in range(grid.shape[0]) if np.all(grid[r] == grid[r, 0])]
    separator_columns = [
        c for c in range(grid.shape[1]) if np.all(grid[:, c] == grid[0, c])
    ]

    def ranges(length: int, separators: list[int]) -> list[tuple[int, int]]:
        answer = []
        start = 0
        for separator in separators:
            if separator > start:
                answer.append((start, separator))
            start = separator + 1
        if start < length:
            answer.append((start, length))
        return answer

    row_ranges = ranges(grid.shape[0], separator_rows)
    column_ranges = ranges(grid.shape[1], separator_columns)
    panels = [grid[r0:r1, c0:c1] for r0, r1 in row_ranges for c0, c1 in column_ranges]
    panels = [panel for panel in panels if panel.size]
    if len(panels) <= 1:
        return []
    return panels


def select_panel(grid: Grid, index: int) -> Grid | None:
    panels = split_panels(grid)
    return panels[index].copy() if index < len(panels) else None


def panel_relation(grid: Grid, relation: str) -> Grid | None:
    panels = split_panels(grid)
    if len(panels) != 2 or panels[0].shape != panels[1].shape:
        return None
    first, second = panels
    bg1, bg2 = background(first), background(second)
    a, b = first != bg1, second != bg2
    relations = {
        "equal": first == second,
        "different": first != second,
        "both": a & b,
        "either": a | b,
        "xor": a ^ b,
        "first_only": a & ~b,
        "second_only": b & ~a,
    }
    return relations[relation].astype(np.int8)


def overlay_symmetry(grid: Grid, transforms: Sequence[GridFunction]) -> Grid:
    bg = background(grid)
    result = grid.copy()
    for transform in transforms:
        transformed = transform(grid)
        if transformed.shape != result.shape:
            return grid.copy()
        mask = (result == bg) & (transformed != bg)
        result[mask] = transformed[mask]
    return result


def block_reduce(grid: Grid, factor_rows: int, factor_columns: int, mode: str) -> Grid | None:
    if grid.shape[0] % factor_rows or grid.shape[1] % factor_columns:
        return None
    height = grid.shape[0] // factor_rows
    width = grid.shape[1] // factor_columns
    result = np.zeros((height, width), dtype=np.int8)
    for row in range(height):
        for column in range(width):
            block = grid[
                row * factor_rows : (row + 1) * factor_rows,
                column * factor_columns : (column + 1) * factor_columns,
            ]
            if mode == "first":
                value = block[0, 0]
            elif mode == "mode":
                counts = Counter(int(cell) for cell in block.flat)
                value = min(counts, key=lambda color: (-counts[color], color))
            else:
                bg = background(grid)
                nonbackground = [int(cell) for cell in block.flat if cell != bg]
                value = Counter(nonbackground).most_common(1)[0][0] if nonbackground else bg
            result[row, column] = value
    return result


def base_primitives() -> list[Primitive]:
    primitives = dihedral_primitives()
    primitives.extend(
        [
            Primitive("crop_nonbackground", 1.1, crop_nonbackground),
            Primitive("crop_nonzero", 1.1, lambda g: crop_nonbackground(g, 0)),
            Primitive("trim_uniform_border", 1.2, trim_uniform_border),
            Primitive("remove_uniform_lines", 1.4, remove_uniform_lines),
            Primitive("fill_holes", 1.5, fill_holes),
            Primitive("outline_bounding_box", 1.6, lambda g: bounding_box(g, False)),
            Primitive("fill_bounding_box", 1.6, lambda g: bounding_box(g, True)),
        ]
    )

    for selector in ("largest", "smallest", "top", "bottom", "left", "right", "tallest", "widest"):
        for same_color in (True, False):
            suffix = "color" if same_color else "all"
            primitives.append(
                Primitive(
                    f"crop_component_{selector}_{suffix}",
                    1.8,
                    lambda g, s=selector, same=same_color: extract_component(
                        g, s, same_color=same, crop=True
                    ),
                )
            )
            primitives.append(
                Primitive(
                    f"mask_component_{selector}_{suffix}",
                    2.0,
                    lambda g, s=selector, same=same_color: extract_component(
                        g, s, same_color=same, crop=False
                    ),
                )
            )

    for index in range(4):
        primitives.append(
            Primitive(f"select_panel_{index}", 1.7, lambda g, i=index: select_panel(g, i))
        )
    for relation in (
        "equal",
        "different",
        "both",
        "either",
        "xor",
        "first_only",
        "second_only",
    ):
        primitives.append(
            Primitive(
                f"panel_relation_{relation}",
                2.0,
                lambda g, r=relation: panel_relation(g, r),
            )
        )

    horizontal = lambda g: np.fliplr(g)
    vertical = lambda g: np.flipud(g)
    rotate = lambda g: np.rot90(g, 2)
    primitives.extend(
        [
            Primitive("complete_horizontal", 1.7, lambda g: overlay_symmetry(g, [horizontal])),
            Primitive("complete_vertical", 1.7, lambda g: overlay_symmetry(g, [vertical])),
            Primitive("complete_central", 1.8, lambda g: overlay_symmetry(g, [rotate])),
            Primitive(
                "complete_all_reflections",
                2.1,
                lambda g: overlay_symmetry(g, [horizontal, vertical, rotate]),
            ),
        ]
    )

    for row_factor in range(1, 5):
        for column_factor in range(1, 5):
            if row_factor == column_factor == 1:
                continue
            primitives.append(
                Primitive(
                    f"scale_{row_factor}x{column_factor}",
                    1.5,
                    lambda g, rf=row_factor, cf=column_factor: np.repeat(
                        np.repeat(g, rf, axis=0), cf, axis=1
                    ),
                )
            )
            primitives.append(
                Primitive(
                    f"tile_{row_factor}x{column_factor}",
                    1.7,
                    lambda g, rf=row_factor, cf=column_factor: np.tile(g, (rf, cf)),
                )
            )
            for mode in ("first", "mode", "nonbackground"):
                primitives.append(
                    Primitive(
                        f"reduce_{row_factor}x{column_factor}_{mode}",
                        1.8,
                        lambda g, rf=row_factor, cf=column_factor, m=mode: block_reduce(
                            g, rf, cf, m
                        ),
                    )
                )
    return primitives


def compose_primitives(primitives: list[Primitive]) -> list[Primitive]:
    """Add a focused second layer: crop/object/panel followed by a symmetry."""
    geometries = dihedral_primitives()[1:]
    composable = [
        primitive
        for primitive in primitives
        if primitive.name.startswith(("crop_", "select_panel_", "remove_uniform_lines"))
    ]
    result = list(primitives)
    for first in composable:
        for second in geometries:
            result.append(
                Primitive(
                    f"{first.name}|{second.name}",
                    first.cost + second.cost + 0.3,
                    lambda g, f=first.function, s=second.function: (
                        None if (intermediate := safe(f, g)) is None else safe(s, intermediate)
                    ),
                )
            )
    return result


PRIMITIVES = compose_primitives(base_primitives())


def learn_color_map(
    produced: Sequence[Grid], targets: Sequence[Grid]
) -> tuple[dict[int, int], bool, float]:
    votes: dict[int, Counter[int]] = {}
    total = 0
    for source, target in zip(produced, targets):
        if source.shape != target.shape:
            return {}, False, 0.0
        for old, new in zip(source.flat, target.flat):
            votes.setdefault(int(old), Counter())[int(new)] += 1
            total += 1
    mapping = {
        old: min(counts, key=lambda color: (-counts[color], color))
        for old, counts in votes.items()
    }
    correct = sum(counts[mapping[old]] for old, counts in votes.items())
    exact = correct == total
    return mapping, exact, correct / total if total else 0.0


def apply_color_map(grid: Grid, mapping: dict[int, int]) -> Grid:
    result = grid.copy()
    for old, new in mapping.items():
        result[grid == old] = new
    return result


def synthesize(task: dict) -> list[Candidate]:
    inputs = [as_grid(pair["input"]) for pair in task["train"]]
    targets = [as_grid(pair["output"]) for pair in task["train"]]
    candidates: list[Candidate] = []
    seen_signatures: set[tuple] = set()

    for primitive in PRIMITIVES:
        produced = [safe(primitive.function, grid) for grid in inputs]
        if any(grid is None for grid in produced):
            continue
        concrete = [grid for grid in produced if grid is not None]
        mapping, exact_map, score = learn_color_map(concrete, targets)
        if not mapping and any(a.shape != b.shape for a, b in zip(concrete, targets)):
            continue
        mapped = [apply_color_map(grid, mapping) for grid in concrete]
        signature = tuple(freeze(grid) for grid in mapped)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        exact = exact_map and all(np.array_equal(a, b) for a, b in zip(mapped, targets))
        changes = sum(old != new for old, new in mapping.items())

        def fitted(grid: Grid, function=primitive.function, colors=mapping) -> Grid | None:
            value = safe(function, grid)
            return None if value is None else apply_color_map(value, colors)

        candidates.append(
            Candidate(
                name=primitive.name + (f"|colors={mapping}" if changes else ""),
                cost=primitive.cost + (0.8 + 0.15 * changes if changes else 0),
                function=fitted,
                exact=exact,
                training_score=score,
            )
        )

    candidates.sort(key=lambda item: (not item.exact, -item.training_score, item.cost, item.name))
    return candidates


def solve_task(
    task: dict,
    attempts: int = 2,
    candidates: list[Candidate] | None = None,
) -> tuple[list[list[Grid]], list[str]]:
    candidates = synthesize(task) if candidates is None else candidates
    predictions: list[list[Grid]] = []
    explanations: list[str] = []
    seen: set[tuple] = set()
    tests = [as_grid(pair["input"]) for pair in task["test"]]

    for candidate in candidates:
        outputs = [safe(candidate.function, grid) for grid in tests]
        if any(output is None for output in outputs):
            continue
        concrete = [output for output in outputs if output is not None]
        signature = tuple(freeze(output) for output in concrete)
        if signature in seen:
            continue
        seen.add(signature)
        predictions.append(concrete)
        explanations.append(candidate.name)
        if len(predictions) == attempts:
            break

    fallback_functions: list[tuple[str, GridFunction]] = [
        ("fallback_identity", lambda g: g),
        ("fallback_crop", crop_nonbackground),
    ]
    for name, function in fallback_functions:
        if len(predictions) == attempts:
            break
        concrete = [safe(function, grid) for grid in tests]
        if any(output is None for output in concrete):
            continue
        outputs = [output for output in concrete if output is not None]
        signature = tuple(freeze(output) for output in outputs)
        if signature in seen:
            continue
        seen.add(signature)
        predictions.append(outputs)
        explanations.append(name)

    while len(predictions) < attempts:
        outputs = [grid.copy() for grid in tests]
        predictions.append(outputs)
        explanations.append("fallback_identity_duplicate")
    return predictions, explanations


def load_task(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def score_directory(directory: str | Path) -> dict[str, float | int]:
    paths = sorted(Path(directory).glob("*.json"))
    solved_tasks = 0
    solved_outputs = 0
    total_outputs = 0
    exact_program_tasks = 0
    for task_number, path in enumerate(paths, start=1):
        task = load_task(path)
        candidates = synthesize(task)
        predictions, _ = solve_task(task, candidates=candidates)
        task_correct = True
        if any(candidate.exact for candidate in candidates):
            exact_program_tasks += 1
        for index, pair in enumerate(task["test"]):
            target = as_grid(pair["output"])
            correct = any(
                index < len(attempt) and np.array_equal(attempt[index], target)
                for attempt in predictions
            )
            solved_outputs += int(correct)
            total_outputs += 1
            task_correct &= correct
        solved_tasks += int(task_correct)
        if task_number % 100 == 0:
            print(
                f"scored {task_number}/{len(paths)} tasks; "
                f"solved {solved_tasks}",
                flush=True,
            )
    return {
        "tasks": len(paths),
        "solved_tasks": solved_tasks,
        "task_accuracy": solved_tasks / len(paths) if paths else 0.0,
        "outputs": total_outputs,
        "solved_outputs": solved_outputs,
        "output_accuracy": solved_outputs / total_outputs if total_outputs else 0.0,
        "tasks_with_exact_program": exact_program_tasks,
    }


def make_kaggle_submission(
    challenge_path: str | Path,
    output_path: str | Path = "submission.json",
) -> dict:
    """Solve Kaggle's challenge JSON and write exactly two attempts per output."""
    with Path(challenge_path).open("r", encoding="utf-8") as handle:
        challenges = json.load(handle)
    submission: dict[str, list[dict[str, list[list[int]]]]] = {}
    for task_id, task in challenges.items():
        predictions, _ = solve_task(task)
        outputs = []
        for test_index in range(len(task["test"])):
            outputs.append(
                {
                    "attempt_1": predictions[0][test_index].astype(int).tolist(),
                    "attempt_2": predictions[1][test_index].astype(int).tolist(),
                }
            )
        submission[task_id] = outputs
    with Path(output_path).open("w", encoding="utf-8") as handle:
        json.dump(submission, handle, separators=(",", ":"))
    return submission


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", help="ARC task directory or Kaggle challenge JSON")
    parser.add_argument("--output", default="submission.json")
    arguments = parser.parse_args()
    data_path = Path(arguments.data)
    if data_path.is_dir():
        print(json.dumps(score_directory(data_path), indent=2))
    else:
        make_kaggle_submission(data_path, arguments.output)
        print(f"Wrote {arguments.output}")
