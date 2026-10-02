"""旧v58の最大overlap spanning tree組立を原文ASTのまま再利用する。"""
from __future__ import annotations
from collections import Counter
from .既存凡例穴対応 import grid_shape
Grid=list[list[int]]

NEIGHBORS_8 = tuple(
    (delta_row, delta_col)
    for delta_row in (-1, 0, 1)
    for delta_col in (-1, 0, 1)
    if delta_row or delta_col
)

def dominant_color(grid: Grid) -> int:
    return Counter(value for row in grid for value in row).most_common(1)[0][0]

def component_bbox(cells: set[tuple[int, int]]) -> tuple[int, int, int, int]:
    rows = [row for row, _ in cells]
    cols = [col for _, col in cells]
    return min(rows), min(cols), max(rows), max(cols)

def crop_grid(grid: Grid, bbox: tuple[int, int, int, int]) -> Grid:
    row0, col0, row1, col1 = bbox
    return [row[col0 : col1 + 1] for row in grid[row0 : row1 + 1]]

def extract_foreground_components(grid: Grid) -> list[dict]:
    background = dominant_color(grid)
    height, width = grid_shape(grid)
    seen: set[tuple[int, int]] = set()
    components = []
    for row in range(height):
        for col in range(width):
            if (row, col) in seen or grid[row][col] == background:
                continue
            stack = [(row, col)]
            seen.add((row, col))
            cells: set[tuple[int, int]] = set()
            while stack:
                current_row, current_col = stack.pop()
                cells.add((current_row, current_col))
                for delta_row, delta_col in NEIGHBORS_8:
                    next_row = current_row + delta_row
                    next_col = current_col + delta_col
                    if not (0 <= next_row < height and 0 <= next_col < width):
                        continue
                    if (next_row, next_col) in seen:
                        continue
                    if grid[next_row][next_col] == background:
                        continue
                    seen.add((next_row, next_col))
                    stack.append((next_row, next_col))

            bbox = component_bbox(cells)
            crop = crop_grid(grid, bbox)
            components.append(
                {
                    "bbox": bbox,
                    "crop": crop,
                    "height": len(crop),
                    "width": len(crop[0]),
                    "size": len(cells),
                    "colors": dict(
                        sorted(Counter(grid[r][c] for r, c in cells).items())
                    ),
                }
            )
    return sorted(components, key=lambda item: item["bbox"])

def serializable_component(component: dict) -> dict:
    return {
        "bbox": list(component["bbox"]),
        "height": component["height"],
        "width": component["width"],
        "size": component["size"],
        "colors": {str(color): count for color, count in component["colors"].items()},
        "crop": component["crop"],
    }

def exact_overlap_edge(left: dict, right: dict, background: int) -> dict | None:
    left_crop = left["crop"]
    right_crop = right["crop"]
    left_height = left["height"]
    left_width = left["width"]
    right_height = right["height"]
    right_width = right["width"]
    best = None

    for delta_row in range(-right_height + 1, left_height):
        for delta_col in range(-right_width + 1, left_width):
            row0 = max(0, delta_row)
            col0 = max(0, delta_col)
            row1 = min(left_height, delta_row + right_height)
            col1 = min(left_width, delta_col + right_width)
            if row0 >= row1 or col0 >= col1:
                continue

            exact = True
            area = 0
            non_background_overlap = 0
            for row in range(row0, row1):
                for col in range(col0, col1):
                    left_value = left_crop[row][col]
                    right_value = right_crop[row - delta_row][col - delta_col]
                    if left_value != right_value:
                        exact = False
                        break
                    area += 1
                    if left_value != background:
                        non_background_overlap += 1
                if not exact:
                    break

            if not exact or non_background_overlap < 1:
                continue

            key = (
                area,
                non_background_overlap,
                -abs(delta_row),
                -abs(delta_col),
                -max(left_height * left_width, right_height * right_width),
                -min(left["bbox"][0], right["bbox"][0]),
                -min(left["bbox"][1], right["bbox"][1]),
            )
            candidate = {
                "key": key,
                "delta_row": delta_row,
                "delta_col": delta_col,
                "overlap_area": area,
                "non_background_overlap": non_background_overlap,
            }
            if best is None or key > best["key"]:
                best = candidate
    return best

def overlap_mosaic_assembly(grid: Grid) -> tuple[Grid | None, dict | None]:
    background = dominant_color(grid)
    components = extract_foreground_components(grid)
    component_count = len(components)
    if component_count < 2:
        return None, None

    edges = []
    for left_index in range(component_count):
        for right_index in range(left_index + 1, component_count):
            edge = exact_overlap_edge(
                components[left_index], components[right_index], background
            )
            if edge is None:
                continue
            edges.append(
                {
                    **edge,
                    "left_index": left_index,
                    "right_index": right_index,
                }
            )
    edges.sort(key=lambda edge: edge["key"], reverse=True)

    parent = list(range(component_count))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    adjacency: list[list[tuple[int, int, int, dict]]] = [
        [] for _ in range(component_count)
    ]
    selected_edges = []
    for edge in edges:
        left = edge["left_index"]
        right = edge["right_index"]
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            continue
        parent[right_root] = left_root
        adjacency[left].append((right, edge["delta_row"], edge["delta_col"], edge))
        adjacency[right].append((left, -edge["delta_row"], -edge["delta_col"], edge))
        selected_edges.append(edge)

    if len(selected_edges) != component_count - 1:
        return None, {
            "background": background,
            "components": [serializable_component(component) for component in components],
            "candidate_edge_count": len(edges),
            "selected_edge_count": len(selected_edges),
            "failure": "overlap graph is not connected",
        }

    positions: dict[int, tuple[int, int]] = {0: (0, 0)}
    queue = [0]
    while queue:
        current = queue.pop(0)
        current_row, current_col = positions[current]
        for neighbor, delta_row, delta_col, _ in adjacency[current]:
            if neighbor in positions:
                continue
            positions[neighbor] = (
                current_row + delta_row,
                current_col + delta_col,
            )
            queue.append(neighbor)

    min_row = min(row for row, _ in positions.values())
    min_col = min(col for _, col in positions.values())
    normalized_positions = {
        index: (row - min_row, col - min_col)
        for index, (row, col) in positions.items()
    }
    height = max(
        normalized_positions[index][0] + components[index]["height"]
        for index in range(component_count)
    )
    width = max(
        normalized_positions[index][1] + components[index]["width"]
        for index in range(component_count)
    )
    output = [[background for _ in range(width)] for _ in range(height)]
    conflicts = []

    for index, component in enumerate(components):
        row0, col0 = normalized_positions[index]
        for row, crop_row in enumerate(component["crop"]):
            for col, value in enumerate(crop_row):
                out_row = row0 + row
                out_col = col0 + col
                existing = output[out_row][out_col]
                if existing != background and existing != value:
                    conflicts.append(
                        {
                            "component_index": index,
                            "cell": [out_row, out_col],
                            "existing": existing,
                            "candidate": value,
                        }
                    )
                output[out_row][out_col] = value

    if conflicts or output == grid:
        return None, {
            "background": background,
            "components": [serializable_component(component) for component in components],
            "positions": {
                str(index): list(position)
                for index, position in sorted(normalized_positions.items())
            },
            "selected_edges": serialize_edges(selected_edges),
            "conflicts": conflicts,
            "failure": "placement conflict or no-op output",
        }

    return output, {
        "background": background,
        "components": [serializable_component(component) for component in components],
        "positions": {
            str(index): list(position)
            for index, position in sorted(normalized_positions.items())
        },
        "candidate_edge_count": len(edges),
        "selected_edges": serialize_edges(selected_edges),
        "output_shape": [height, width],
    }

def serialize_edges(edges: list[dict]) -> list[dict]:
    return [
        {
            "left_index": edge["left_index"],
            "right_index": edge["right_index"],
            "delta_row": edge["delta_row"],
            "delta_col": edge["delta_col"],
            "overlap_area": edge["overlap_area"],
            "non_background_overlap": edge["non_background_overlap"],
        }
        for edge in edges
    ]
