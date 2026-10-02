"""旧ARCの型付き成分グラフ・唯一最短経路を再利用する。
出典: ARC-Layer-0-Functional-Compliance@454670a1 / arc2_runtime_fit_generator.py。
4近傍同色成分をnode、8近接をedgeとし、edge数で最短を測る。
"""
from __future__ import annotations
from collections import defaultdict, deque
from typing import Any
from .既存領域転写 import Grid, Cell
from .既存凡例穴対応 import clone_grid, grid_shape, bbox_to_list
from .既存物体特徴 import color_components, dominant_background_for_grid as dominant_background

def foreground_components(grid: Grid, background: int) -> list[dict[str, Any]]:
    colors = sorted({value for row in grid for value in row if value != background})
    components: list[dict[str, Any]] = []
    for color in colors:
        components.extend(color_components(grid, color))
    return sorted(components, key=lambda component: (component["bbox"], component["color"]))


def solid_square_component_shape(component: dict[str, Any]) -> tuple[int, int] | None:
    row0, col0, row1, col1 = component["bbox"]
    height = row1 - row0 + 1
    width = col1 - col0 + 1
    if height != width or height < 2:
        return None
    if int(component["size"]) != height * width:
        return None
    return height, width


def terminal_square_path_component_summary(component: dict[str, Any]) -> dict[str, Any]:
    return {
        "color": int(component["color"]),
        "bbox": bbox_to_list(component["bbox"]),
        "size": int(component["size"]),
    }


def component_adjacency_8(components: list[dict[str, Any]]) -> dict[int, list[int]]:
    cell_to_index: dict[Cell, int] = {}
    for index, component in enumerate(components):
        for cell in component["cells"]:
            cell_to_index[cell] = index

    adjacency: dict[int, set[int]] = {index: set() for index in range(len(components))}
    directions = (
        (-1, -1),
        (-1, 0),
        (-1, 1),
        (0, -1),
        (0, 1),
        (1, -1),
        (1, 0),
        (1, 1),
    )
    for (row, col), index in cell_to_index.items():
        for row_delta, col_delta in directions:
            neighbor = cell_to_index.get((row + row_delta, col + col_delta))
            if neighbor is None or neighbor == index:
                continue
            adjacency[index].add(neighbor)
            adjacency[neighbor].add(index)
    return {index: sorted(neighbors) for index, neighbors in adjacency.items()}


def unique_shortest_component_path(
    adjacency: dict[int, list[int]],
    start: int,
    end: int,
) -> tuple[list[int] | None, str]:
    if start == end:
        return [start], "unique_shortest_path"

    distances: dict[int, int] = {start: 0}
    parents: dict[int, list[int]] = defaultdict(list)
    queue: deque[int] = deque([start])
    best_distance: int | None = None
    while queue:
        current = queue.popleft()
        current_distance = distances[current]
        if best_distance is not None and current_distance >= best_distance:
            continue
        for neighbor in adjacency.get(current, []):
            next_distance = current_distance + 1
            if best_distance is not None and next_distance > best_distance:
                continue
            if neighbor not in distances:
                distances[neighbor] = next_distance
                parents[neighbor].append(current)
                queue.append(neighbor)
                if neighbor == end:
                    best_distance = next_distance
            elif distances[neighbor] == next_distance:
                parents[neighbor].append(current)

    if end not in distances:
        return None, "no_path_between_terminal_squares"

    paths: list[list[int]] = []

    def collect(node: int, suffix: list[int]) -> None:
        if len(paths) > 1:
            return
        if node == start:
            paths.append([start] + list(reversed(suffix)))
            return
        for parent in parents.get(node, []):
            collect(parent, suffix + [node])

    collect(end, [])
    if len(paths) != 1:
        return None, "non_unique_shortest_path_between_terminal_squares"
    return paths[0], "unique_shortest_path"


def terminal_square_path_policy(grid: Grid) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    height, width = grid_shape(grid)
    if height < 3 or width < 3:
        return None, {
            "failure": "terminal_square_path_grid_too_small",
            "terminal_square_path_input_shape": [height, width],
        }
    if any(len(row) != width for row in grid):
        return None, {"failure": "terminal_square_path_ragged_grid"}

    background_color = int(dominant_background(grid))
    foreground_colors = sorted({int(value) for row in grid for value in row if int(value) != background_color})
    if len(foreground_colors) != 3:
        return None, {
            "failure": "terminal_square_path_foreground_color_count_not_three",
            "terminal_square_path_foreground_colors": foreground_colors,
        }

    components = foreground_components(grid, background_color)
    components_by_color: dict[int, list[dict[str, Any]]] = defaultdict(list)
    square_components_by_color: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for component in components:
        color = int(component["color"])
        components_by_color[color].append(component)
        if solid_square_component_shape(component) is not None:
            square_components_by_color[color].append(component)

    terminal_candidates: list[tuple[int, tuple[int, int], list[dict[str, Any]]]] = []
    for color in foreground_colors:
        color_components = components_by_color[color]
        square_components = square_components_by_color[color]
        square_shapes = {solid_square_component_shape(component) for component in square_components}
        if (
            len(color_components) == 2
            and len(square_components) == 2
            and len(square_shapes) == 1
            and None not in square_shapes
        ):
            terminal_candidates.append((color, next(iter(square_shapes)), square_components))
    if len(terminal_candidates) != 1:
        return None, {
            "failure": "terminal_square_path_terminal_color_not_unique",
            "terminal_square_path_terminal_candidates": [
                {
                    "color": color,
                    "square_shape": list(square_shape),
                    "components": [terminal_square_path_component_summary(component) for component in components],
                }
                for color, square_shape, components in terminal_candidates
            ],
        }

    terminal_color, square_shape, terminal_components = terminal_candidates[0]
    block_candidates: list[int] = []
    for color in foreground_colors:
        if color == terminal_color:
            continue
        color_components = components_by_color[color]
        if color_components and all(solid_square_component_shape(component) == square_shape for component in color_components):
            block_candidates.append(color)
    if len(block_candidates) != 1:
        return None, {
            "failure": "terminal_square_path_block_color_not_unique",
            "terminal_square_path_terminal_color": terminal_color,
            "terminal_square_path_square_shape": list(square_shape),
            "terminal_square_path_block_candidates": block_candidates,
        }

    block_color = block_candidates[0]
    connector_colors = sorted(set(foreground_colors) - {terminal_color, block_color})
    if len(connector_colors) != 1:
        return None, {
            "failure": "terminal_square_path_connector_color_not_unique",
            "terminal_square_path_foreground_colors": foreground_colors,
            "terminal_square_path_terminal_color": terminal_color,
            "terminal_square_path_block_color": block_color,
        }
    connector_color = connector_colors[0]

    terminal_indices = [components.index(component) for component in terminal_components]
    adjacency = component_adjacency_8(components)
    path_indices, path_status = unique_shortest_component_path(
        adjacency,
        terminal_indices[0],
        terminal_indices[1],
    )
    if path_indices is None:
        return None, {
            "failure": path_status,
            "terminal_square_path_terminal_color": terminal_color,
            "terminal_square_path_terminal_components": [
                terminal_square_path_component_summary(component) for component in terminal_components
            ],
        }

    interior_indices = path_indices[1:-1]
    if not interior_indices:
        return None, {
            "failure": "terminal_square_path_no_interior_components",
            "terminal_square_path_path_length": len(path_indices),
        }
    interior_colors = {int(components[index]["color"]) for index in interior_indices}
    if terminal_color in interior_colors or not {block_color, connector_color}.issubset(interior_colors):
        return None, {
            "failure": "terminal_square_path_interior_color_set_invalid",
            "terminal_square_path_terminal_color": terminal_color,
            "terminal_square_path_block_color": block_color,
            "terminal_square_path_connector_color": connector_color,
            "terminal_square_path_interior_colors": sorted(interior_colors),
        }

    return {
        "background_color": background_color,
        "terminal_color": terminal_color,
        "block_color": block_color,
        "connector_color": connector_color,
        "square_shape": square_shape,
        "components": components,
        "path_indices": path_indices,
    }, {}


def render_terminal_square_component_path_recolorer(
    grid: Grid,
    block_output_color: int,
    connector_output_color: int,
) -> tuple[Grid | None, dict[str, Any]]:
    if block_output_color == connector_output_color:
        return None, {
            "failure": "terminal_square_path_output_colors_not_distinct",
            "terminal_square_path_block_output_color": block_output_color,
            "terminal_square_path_connector_output_color": connector_output_color,
        }

    policy, rejection = terminal_square_path_policy(grid)
    if policy is None:
        return None, rejection

    input_colors = {int(value) for row in grid for value in row}
    if block_output_color in input_colors or connector_output_color in input_colors:
        return None, {
            "failure": "terminal_square_path_output_color_not_new",
            "terminal_square_path_block_output_color": block_output_color,
            "terminal_square_path_connector_output_color": connector_output_color,
            "terminal_square_path_input_colors": sorted(input_colors),
        }

    block_color = int(policy["block_color"])
    connector_color = int(policy["connector_color"])
    components = policy["components"]
    output = clone_grid(grid)
    path_records: list[dict[str, Any]] = []
    event_count = 0
    for index in policy["path_indices"][1:-1]:
        component = components[index]
        color = int(component["color"])
        if color == block_color:
            target_color = block_output_color
            role = "block"
        elif color == connector_color:
            target_color = connector_output_color
            role = "connector"
        else:
            return None, {
                "failure": "terminal_square_path_unexpected_interior_color",
                "terminal_square_path_component": terminal_square_path_component_summary(component),
            }
        for row, col in component["cells"]:
            output[row][col] = target_color
        event_count += int(component["size"])
        path_records.append(
            {
                "role": role,
                "source_color": color,
                "target_color": target_color,
                "bbox": bbox_to_list(component["bbox"]),
                "size": int(component["size"]),
            }
        )

    if event_count == 0:
        return None, {"failure": "terminal_square_path_no_events"}

    height, width = grid_shape(grid)
    changed_cell_count = sum(
        1
        for row in range(height)
        for col in range(width)
        if output[row][col] != grid[row][col]
    )
    return output, {
        "renderer_case": "terminal_square_component_path_recolorer",
        "terminal_square_path_background_color": int(policy["background_color"]),
        "terminal_square_path_terminal_color": int(policy["terminal_color"]),
        "terminal_square_path_block_color": block_color,
        "terminal_square_path_connector_color": connector_color,
        "terminal_square_path_block_output_color": block_output_color,
        "terminal_square_path_connector_output_color": connector_output_color,
        "terminal_square_path_square_shape": list(policy["square_shape"]),
        "terminal_square_path_length": len(policy["path_indices"]),
        "terminal_square_path_event_count": event_count,
        "terminal_square_path_changed_cell_count": changed_cell_count,
        "terminal_square_path_records": path_records,
        "terminal_square_path_input_shape": [height, width],
        "terminal_square_path_output_shape": [height, width],
    }


def terminal_square_path_output_colors(
    input_grid: Grid,
    output_grid: Grid,
    policy: dict[str, Any],
    train_index: int,
) -> tuple[tuple[int, int] | None, dict[str, Any]]:
    height, width = grid_shape(input_grid)
    block_color = int(policy["block_color"])
    connector_color = int(policy["connector_color"])
    terminal_color = int(policy["terminal_color"])
    block_targets: set[int] = set()
    connector_targets: set[int] = set()
    unexpected_pairs: list[dict[str, int]] = []
    for row in range(height):
        for col in range(width):
            source_color = int(input_grid[row][col])
            target_color = int(output_grid[row][col])
            if source_color == target_color:
                continue
            if source_color == block_color:
                block_targets.add(target_color)
            elif source_color == connector_color:
                connector_targets.add(target_color)
            else:
                unexpected_pairs.append(
                    {
                        "row": row,
                        "col": col,
                        "source_color": source_color,
                        "target_color": target_color,
                    }
                )

    if unexpected_pairs:
        return None, {
            "failure": "terminal_square_path_unexpected_changed_source_color",
            "train_index": train_index,
            "terminal_square_path_terminal_color": terminal_color,
            "unexpected_pairs": unexpected_pairs[:12],
        }
    if len(block_targets) != 1 or len(connector_targets) != 1:
        return None, {
            "failure": "terminal_square_path_output_color_mapping_not_unique",
            "train_index": train_index,
            "terminal_square_path_block_targets": sorted(block_targets),
            "terminal_square_path_connector_targets": sorted(connector_targets),
        }
    block_output_color = next(iter(block_targets))
    connector_output_color = next(iter(connector_targets))
    if block_output_color == connector_output_color:
        return None, {
            "failure": "terminal_square_path_output_colors_collide",
            "train_index": train_index,
            "terminal_square_path_output_color": block_output_color,
        }
    return (block_output_color, connector_output_color), {}


