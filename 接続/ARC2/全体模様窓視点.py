"""One complete-support input view; no fitting, model selection or dataset access."""
from collections import Counter
from . import 周期模様窓候補 as strict
from 接続.ARC2.既存倍率置換 import pattern_from_component


def parse_whole(grid):
    if (not isinstance(grid, list) or not 1 <= len(grid) <= 30
        or not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30
        or any(not isinstance(row, list) or len(row) != len(grid[0]) for row in grid)
        or any(type(value) is not int or not 0 <= value <= 9 for row in grid for value in row)):
        return None, 'invalid_arc_grid'
    counts = Counter(value for row in grid for value in row)
    if len(counts) != 2:
        return None, 'not_binary'
    ranked = counts.most_common()
    if ranked[0][1] == ranked[1][1]:
        return None, 'background_tie'
    background, foreground = ranked[0][0], ranked[1][0]
    cells = [(r, c, foreground) for r, row in enumerate(grid)
             for c, value in enumerate(row) if value == foreground]
    r0 = min(r for r, _, _ in cells)
    c0 = min(c for _, c, _ in cells)
    r1 = max(r for r, _, _ in cells)
    c1 = max(c for _, c, _ in cells)
    bbox = [r0, c0, r1, c1]
    raw = pattern_from_component({'bbox': bbox, 'cells': cells})
    mask = [[int(value is not None) for value in row] for row in raw]
    role = {
        'background': background, 'foreground': foreground,
        'input_shape': [len(grid), len(grid[0])], 'bbox': bbox,
        'cells': cells, 'mask': mask, 'foreground_count': len(cells),
        'background_count': counts[background],
        'ownership': 'complete foreground whole monochrome mask + all remaining input background',
    }
    expected = {(r, c, value) for r, row in enumerate(grid)
                for c, value in enumerate(row) if value != background}
    represented = {(r + r0, c + c0, foreground)
                   for r, row in enumerate(mask) for c, value in enumerate(row) if value}
    reconstructed = [[background] * len(grid[0]) for _ in grid]
    for r, c, value in represented:
        reconstructed[r][c] = value
    tight = (any(mask[0]) and any(mask[-1])
             and any(row[0] for row in mask) and any(row[-1] for row in mask))
    if (not tight or cells != sorted(cells) or len(cells) != len(set(cells))
        or set(cells) != expected or represented != expected or reconstructed != grid
        or len(cells) + counts[background] != len(grid) * len(grid[0])):
        return None, 'whole_mask_ownership_failed'
    strict_role, strict_reason = strict.parse(grid)
    if strict_role is not None:
        if (set(strict_role) != set(role)
            or any(strict_role[key] != role[key] for key in role if key != 'ownership')):
            return None, 'strict_role_parity_failed'
        return strict_role, None
    if strict_reason != 'not_one_whole_c8_component':
        return None, strict_reason
    return role, None
