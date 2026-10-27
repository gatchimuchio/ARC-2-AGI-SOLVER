"""Shadow HDS family: one global foreground D4, palette map, and translation."""

from __future__ import annotations

from collections import Counter

from .既存格子操作 import transform_grid_by_name


_TRANSFORMS = (
    "identity",
    "rot90",
    "rot180",
    "rot270",
    "flip_h",
    "flip_v",
    "transpose",
    "anti_transpose",
)


def _background_and_bbox(grid):
    counts = Counter(value for row in grid for value in row)
    if not counts:
        return None, None
    maximum = max(counts.values())
    modes = [value for value, count in counts.items() if count == maximum]
    if len(modes) != 1:
        return None, None
    background = modes[0]
    cells = [
        (row, col)
        for row, values in enumerate(grid)
        for col, value in enumerate(values)
        if value != background
    ]
    if not cells:
        return background, None
    return background, (
        min(row for row, _ in cells),
        min(col for _, col in cells),
        max(row for row, _ in cells) + 1,
        max(col for _, col in cells) + 1,
    )


def _pair_programs(pair):
    source = pair.get("input")
    target = pair.get("output")
    if not source or not target or len(source) != len(target):
        return set()
    if any(len(row) != len(source[0]) for row in source + target):
        return set()

    source_bg, source_bbox = _background_and_bbox(source)
    target_bg, target_bbox = _background_and_bbox(target)
    if source_bbox is None or target_bbox is None:
        return set()
    sr0, sc0, sr1, sc1 = source_bbox
    tr0, tc0, tr1, tc1 = target_bbox
    source_crop = [row[sc0:sc1] for row in source[sr0:sr1]]
    target_crop = [row[tc0:tc1] for row in target[tr0:tr1]]
    programs = set()

    for transform in _TRANSFORMS:
        rendered = transform_grid_by_name(source_crop, transform)
        if (
            rendered is None
            or len(rendered) != len(target_crop)
            or any(len(row) != len(target_crop[0]) for row in rendered)
        ):
            continue
        mapping = {source_bg: target_bg}
        reverse = {target_bg: source_bg}
        valid = True
        for source_row, target_row in zip(rendered, target_crop):
            for source_color, target_color in zip(source_row, target_row):
                if source_color == source_bg:
                    if target_color != target_bg:
                        valid = False
                        break
                    continue
                if target_color == target_bg:
                    valid = False
                    break
                if (
                    source_color in mapping
                    and mapping[source_color] != target_color
                ) or (
                    target_color in reverse
                    and reverse[target_color] != source_color
                ):
                    valid = False
                    break
                mapping[source_color] = target_color
                reverse[target_color] = source_color
            if not valid:
                break
        if valid:
            programs.add(
                (
                    transform,
                    tr0 - sr0,
                    tc0 - sc0,
                    tuple(sorted(mapping.items())),
                )
            )
    return programs


def _merge_programs(left, right):
    if left[:3] != right[:3]:
        return None
    mapping = dict(left[3])
    reverse = {target: source for source, target in mapping.items()}
    for source, target in right[3]:
        if source in mapping and mapping[source] != target:
            return None
        if target in reverse and reverse[target] != source:
            return None
        mapping[source] = target
        reverse[target] = source
    return left[:3] + (tuple(sorted(mapping.items())),)


def _fit_programs(teachers):
    states = None
    for pair in teachers:
        candidates = _pair_programs(pair)
        if not candidates:
            return set()
        if states is None:
            states = candidates
            continue
        merged = set()
        for state in states:
            for candidate in candidates:
                result = _merge_programs(state, candidate)
                if result is not None:
                    merged.add(result)
        if not merged:
            return set()
        states = merged
    return states or set()


def _apply_program(grid, program):
    transform, delta_row, delta_col, mapping_items = program
    mapping = dict(mapping_items)
    source_bg, bbox = _background_and_bbox(grid)
    if bbox is None or source_bg not in mapping:
        return None
    r0, c0, r1, c1 = bbox
    crop = [row[c0:c1] for row in grid[r0:r1]]
    rendered = transform_grid_by_name(crop, transform)
    if rendered is None:
        return None
    target_bg = mapping[source_bg]
    height, width = len(grid), len(grid[0])
    out_r0, out_c0 = r0 + delta_row, c0 + delta_col
    if (
        out_r0 < 0
        or out_c0 < 0
        or out_r0 + len(rendered) > height
        or out_c0 + len(rendered[0]) > width
    ):
        return None
    output = [[target_bg for _ in range(width)] for _ in range(height)]
    for row_index, row in enumerate(rendered):
        for col_index, color in enumerate(row):
            if color == source_bg:
                mapped = target_bg
            elif color in mapping and mapping[color] != target_bg:
                mapped = mapping[color]
            else:
                return None
            output[out_r0 + row_index][out_c0 + col_index] = mapped
    return output


def _valid_grid(value):
    return (
        isinstance(value, list)
        and 1 <= len(value) <= 30
        and all(
            isinstance(row, list)
            and 1 <= len(row) <= 30
            and len(row) == len(value[0])
            and all(type(color) is int and 0 <= color <= 9 for color in row)
            for row in value
        )
    )


class CompoundForegroundD4PaletteTranslation:
    """Task-level teacher fit with input-only candidate generation."""

    def __init__(self, teachers):
        self._teachers = len(teachers)
        self._programs = _fit_programs(teachers)

    def 候補(self, grid, _policy):
        if not self._programs:
            return None, {"failure": "no_compound_foreground_program_fits_teachers"}
        outputs = []
        for program in self._programs:
            output = _apply_program(grid, program)
            if output is None:
                return None, {"failure": "compound_program_not_applicable_to_input"}
            outputs.append(tuple(tuple(row) for row in output))
        unique = set(outputs)
        if len(unique) != 1:
            return None, {"failure": "compound_programs_disagree_on_input"}
        answer = [list(row) for row in next(iter(unique))]
        if not _valid_grid(answer):
            return None, {"failure": "compound_output_is_not_a_valid_arc_grid"}
        return answer, {
            "family": "compound_foreground_d4_palette_translation",
            "teacher_pair_count": self._teachers,
            "consistent_program_count": len(self._programs),
        }

    def 記録(self):
        return {
            "teacher_pair_count": self._teachers,
            "consistent_program_count": len(self._programs),
            "foreground_d4_palette_translation": "shadow_only",
        }
