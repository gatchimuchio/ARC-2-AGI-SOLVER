"""Repeated panel pattern matching as a conservative second-answer candidate.

This family recognizes a header of small pattern cards and a repeated panel
grid below it. It is candidate-only: training must show the panel and footer
transforms exactly, with at most one small unexplained residual confined to a
single header card. The primary HDS answer is never replaced by this module.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from itertools import product


def _有効格子(grid: object) -> bool:
    return (
        isinstance(grid, list)
        and bool(grid)
        and all(isinstance(row, list) and row for row in grid)
        and len({len(row) for row in grid}) == 1
        and all(type(value) is int and 0 <= value <= 9 for row in grid for value in row)
    )


def _配置を読む(grid: list[list[int]], core_h: int, core_w: int) -> dict | None:
    if not _有効格子(grid):
        return None
    height, width = len(grid), len(grid[0])
    if core_h < 1 or core_w < 1 or core_h > 5 or core_w > 5:
        return None

    background = Counter(value for row in grid for value in row).most_common(1)[0][0]
    separators = [
        row_index
        for row_index, row in enumerate(grid)
        if len(set(row)) == 1 and row[0] != background
    ]
    pairs = [
        (upper, lower)
        for upper, lower in product(separators, repeat=2)
        if upper < lower
        and upper < height / 3
        and lower >= 2 * height / 3
        and grid[upper][0] == grid[lower][0]
    ]
    if not pairs:
        return None
    largest_gap = max(lower - upper for upper, lower in pairs)
    best_pairs = [(upper, lower) for upper, lower in pairs if lower - upper == largest_gap]
    if len(best_pairs) != 1:
        return None
    upper, lower = best_pairs[0]

    pitch_h, pitch_w = core_h + 2, core_w + 2
    key_y = (upper - core_h) // 2
    if key_y < 0 or key_y + core_h > upper:
        return None

    ncols = (width - 2) // pitch_w
    if ncols < 2:
        return None
    key_x = (width - ((ncols - 1) * pitch_w + core_w)) // 2
    if key_x < 1 or key_x + (ncols - 1) * pitch_w + core_w > width - 1:
        return None

    # One blank row follows the upper separator, then each card has a one-cell
    # border around its core. The same border convention applies horizontally.
    board_y = upper + 2 + 1
    last_core_end = lower - 2
    nrows = (last_core_end - (board_y + core_h - 1)) // pitch_h + 1
    if nrows < 2 or board_y + (nrows - 1) * pitch_h + core_h - 1 > last_core_end:
        return None

    keys = [
        tuple(tuple(row[key_x + col * pitch_w:key_x + col * pitch_w + core_w])
              for row in grid[key_y:key_y + core_h])
        for col in range(ncols)
    ]
    if any(len(key) != core_h or any(len(row) != core_w for row in key) for key in keys):
        return None

    return {
        "background": background,
        "upper_separator": upper,
        "lower_separator": lower,
        "core_h": core_h,
        "core_w": core_w,
        "pitch_h": pitch_h,
        "pitch_w": pitch_w,
        "key_y": key_y,
        "key_x": key_x,
        "board_y": board_y,
        "board_x": key_x,
        "nrows": nrows,
        "ncols": ncols,
        "keys": keys,
    }


def _識別(layout: dict) -> tuple:
    return tuple(layout[key] for key in (
        "background", "upper_separator", "lower_separator", "core_h", "core_w",
        "pitch_h", "pitch_w", "key_y", "key_x", "board_y", "board_x", "nrows", "ncols",
    ))


def _一致位置(grid: list[list[int]], layout: dict) -> list[tuple[int, int]]:
    background = layout["background"]
    keys = {
        tuple(tuple(row) for row in key)
        for key in layout["keys"]
        if any(value != background for row in key for value in row)
    }
    matches = []
    for tile_row in range(layout["nrows"]):
        for tile_col in range(layout["ncols"]):
            y = layout["board_y"] + tile_row * layout["pitch_h"]
            x = layout["board_x"] + tile_col * layout["pitch_w"]
            patch = tuple(
                tuple(row[x:x + layout["core_w"]])
                for row in grid[y:y + layout["core_h"]]
            )
            if patch in keys:
                matches.append((tile_row, tile_col))
    return matches


def _一直線(matches: list[tuple[int, int]], nrows: int, ncols: int) -> bool:
    if len(matches) != ncols and len(matches) != nrows:
        return False
    full_row = len(matches) == ncols and len({row for row, _ in matches}) == 1
    full_col = len(matches) == nrows and len({col for _, col in matches}) == 1
    return full_row or full_col


def _描画(
    grid: list[list[int]],
    layout: dict,
    *,
    panel_fill: int,
    aligned_header_fill: int,
    aligned_footer_fill: int,
    scattered_footer_fill: int,
) -> tuple[list[list[int]], list[tuple[int, int]], bool]:
    output = deepcopy(grid)
    background = layout["background"]
    matches = _一致位置(grid, layout)
    aligned = _一直線(matches, layout["nrows"], layout["ncols"])

    for tile_row, tile_col in matches:
        y = layout["board_y"] + tile_row * layout["pitch_h"]
        x = layout["board_x"] + tile_col * layout["pitch_w"]
        for row in range(y - 1, y + layout["core_h"] + 1):
            for col in range(x - 1, x + layout["core_w"] + 1):
                if grid[row][col] == background:
                    output[row][col] = panel_fill

    if aligned:
        for row in range(layout["upper_separator"]):
            for col in range(len(grid[0])):
                if grid[row][col] == background:
                    output[row][col] = aligned_header_fill

    footer_fill = aligned_footer_fill if aligned else scattered_footer_fill
    for row in range(layout["lower_separator"] + 1, len(grid)):
        for col in range(len(grid[0])):
            if grid[row][col] == background:
                output[row][col] = footer_fill
    return output, matches, aligned


def _色を推定(pairs: list[dict], layouts: list[dict]) -> dict | None:
    panel_values: set[int] = set()
    aligned_header_values: set[int] = set()
    aligned_footer_values: set[int] = set()
    scattered_footer_values: set[int] = set()

    for pair, layout in zip(pairs, layouts):
        source, target = pair["input"], pair["output"]
        background = layout["background"]
        matches = _一致位置(source, layout)
        if not matches:
            return None
        aligned = _一直線(matches, layout["nrows"], layout["ncols"])
        key_core_cells = {
            (row, col)
            for key_index in range(layout["ncols"])
            for row in range(layout["key_y"], layout["key_y"] + layout["core_h"])
            for col in range(layout["key_x"] + key_index * layout["pitch_w"],
                              layout["key_x"] + key_index * layout["pitch_w"] + layout["core_w"])
        }

        for tile_row, tile_col in matches:
            y = layout["board_y"] + tile_row * layout["pitch_h"]
            x = layout["board_x"] + tile_col * layout["pitch_w"]
            for row in range(y - 1, y + layout["core_h"] + 1):
                for col in range(x - 1, x + layout["core_w"] + 1):
                    if source[row][col] == background:
                        panel_values.add(target[row][col])

        for row in range(layout["upper_separator"]):
            for col in range(len(source[0])):
                if source[row][col] != background or (row, col) in key_core_cells:
                    continue
                if aligned:
                    aligned_header_values.add(target[row][col])
                elif target[row][col] != background:
                    return None

        for row in range(layout["lower_separator"] + 1, len(source)):
            for col in range(len(source[0])):
                if source[row][col] != background:
                    continue
                if aligned:
                    aligned_footer_values.add(target[row][col])
                else:
                    scattered_footer_values.add(target[row][col])

    groups = (panel_values, aligned_header_values, aligned_footer_values, scattered_footer_values)
    if any(len(values) != 1 for values in groups):
        return None
    panel, header, aligned_footer, scattered_footer = (next(iter(values)) for values in groups)
    if any(color == layouts[0]["background"] for color in (panel, header, aligned_footer, scattered_footer)):
        return None
    return {
        "panel_fill": panel,
        "aligned_header_fill": header,
        "aligned_footer_fill": aligned_footer,
        "scattered_footer_fill": scattered_footer,
    }


def fit_candidate(train: object) -> tuple[dict | None, dict]:
    """Fit the shared panel rule; return only a high-support second-candidate model."""
    if not isinstance(train, list) or len(train) < 4:
        return None, {"failure": "insufficient_teacher_support"}
    if any(
        not isinstance(pair, dict)
        or set(pair) != {"input", "output"}
        or not _有効格子(pair["input"])
        or not _有効格子(pair["output"])
        or len(pair["input"]) != len(pair["output"])
        or len(pair["input"][0]) != len(pair["output"][0])
        for pair in train
    ):
        return None, {"failure": "invalid_teacher"}

    accepted = []
    diagnostics = []
    for core_h in range(1, 6):
        for core_w in range(1, 6):
            layouts = [_配置を読む(pair["input"], core_h, core_w) for pair in train]
            if any(layout is None for layout in layouts):
                continue
            if len({_識別(layout) for layout in layouts}) != 1:
                continue
            colors = _色を推定(train, layouts)
            if colors is None:
                continue

            exact = 0
            residual_examples = []
            residual_cells = []
            valid = True
            for index, (pair, layout) in enumerate(zip(train, layouts)):
                predicted, matches, _ = _描画(pair["input"], layout, **colors)
                if not matches:
                    valid = False
                    break
                target = pair["output"]
                differences = {
                    (row, col)
                    for row in range(len(target))
                    for col in range(len(target[0]))
                    if predicted[row][col] != target[row][col]
                }
                if not differences:
                    exact += 1
                    continue

                key_cores = [
                    {
                        (row, col)
                        for row in range(layout["key_y"], layout["key_y"] + layout["core_h"])
                        for col in range(layout["key_x"] + key_index * layout["pitch_w"],
                                         layout["key_x"] + key_index * layout["pitch_w"] + layout["core_w"])
                    }
                    for key_index in range(layout["ncols"])
                ]
                containing = [core for core in key_cores if differences <= core]
                if len(differences) > layout["core_h"] * layout["core_w"] or len(containing) != 1:
                    valid = False
                    break
                residual_examples.append(index)
                residual_cells.append(len(differences))

            if not valid or len(residual_examples) > 1 or exact < len(train) - 1:
                continue
            model = {**layouts[0], **colors}
            accepted.append(model)
            diagnostics.append({
                "core": [core_h, core_w],
                "teacher_count": len(train),
                "exact_teacher_count": exact,
                "residual_teacher_indices": residual_examples,
                "residual_cell_counts": residual_cells,
                "match_counts": [len(_一致位置(pair["input"], layout))
                                 for pair, layout in zip(train, layouts)],
            })

    if len(accepted) != 1:
        return None, {
            "failure": "no_unique_high_support_panel_model" if not accepted else "ambiguous_panel_models",
            "candidate_models": diagnostics,
        }
    model = accepted[0]
    return model, {
        "status": "candidate_only_soft_teacher_fit",
        "teacher_count": len(train),
        "exact_teacher_count": diagnostics[0]["exact_teacher_count"],
        "residual_teacher_indices": diagnostics[0]["residual_teacher_indices"],
        "residual_cell_counts": diagnostics[0]["residual_cell_counts"],
        "core": [model["core_h"], model["core_w"]],
        "board_shape": [model["nrows"], model["ncols"]],
    }


def predict_candidate(grid: object, model: object) -> tuple[list[list[int]] | None, dict]:
    if not isinstance(model, dict) or not _有効格子(grid):
        return None, {"failure": "invalid_candidate_request"}
    layout = _配置を読む(grid, model.get("core_h", 0), model.get("core_w", 0))
    if layout is None or _識別(layout) != _識別(model):
        return None, {"failure": "panel_layout_mismatch"}
    output, matches, aligned = _描画(grid, layout, **{
        key: model[key]
        for key in ("panel_fill", "aligned_header_fill", "aligned_footer_fill", "scattered_footer_fill")
    })
    if not matches:
        return None, {"failure": "no_matching_panels"}
    return output, {"matches": len(matches), "aligned": aligned}
