"""Prospective conservative composition; distinct from additive flow.

The query evaluator is the frozen finite policy. Teacher-only refutations
below are necessary conditions of its unchanged terminal outputs.
"""
from collections import Counter
from .有限量流路候補 import compact, settle


def valid_grid(grid):
    return (type(grid) is list and 1 <= len(grid) <= 30
            and type(grid[0]) is list and 1 <= len(grid[0]) <= 30
            and all(type(row) is list and len(row) == len(grid[0])
                    and all(type(v) is int and 0 <= v <= 9 for v in row)
                    for row in grid))


def valid_teachers(teachers):
    return (type(teachers) in (list, tuple) and bool(teachers)
            and all(type(pair) is dict and set(pair) == {'input', 'output'}
                    and valid_grid(pair['input']) and valid_grid(pair['output'])
                    for pair in teachers))


def expected_terminal(grid, background, material):
    """No legal successor exists iff the frozen compact-state scan has no gap.

This is solely a teacher refutation, never a query destination generator.
Every legal gap has empty space immediately below it, so subsequent compaction
strictly increases potential. Therefore one gap refutes terminality.
"""
    height, width = len(grid), len(grid[0])
    state = frozenset((r, c) for r, row in enumerate(grid)
                      for c, value in enumerate(row) if value == material)
    walls = frozenset((r, c) for r, row in enumerate(grid)
                      for c, value in enumerate(row) if value not in (background, material))
    if compact(state, walls, height, width) != state:
        return False
    occupied = state | walls
    for r, c in state:
        if r + 1 >= height:
            continue
        left = right = c
        while left > 0 and (r + 1, left - 1) in occupied:
            left -= 1
        while right + 1 < width and (r + 1, right + 1) in occupied:
            right += 1
        for gap in (left - 1, right + 1):
            if (0 <= gap < width and
                    not any((r, x) in walls for x in range(min(c, gap), max(c, gap) + 1))):
                return False
    return True


def render(grid, role):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_arc_grid'}
    if (type(role) is not tuple or len(role) != 2
            or any(type(v) is not int or not 0 <= v <= 9 for v in role)
            or role[0] == role[1]):
        return None, {'failure': 'invalid_finite_roles'}
    if not any(v == role[1] for row in grid for v in row):
        return None, {'failure': 'material_absent'}
    return settle(grid, *role)


def fit(teachers):
    if not valid_teachers(teachers) or len(teachers) < 2:
        return ()
    if len({tuple(map(tuple, p['input'])) for p in teachers}) != len(teachers):
        return ()
    for pair in teachers:
        inp, out = pair['input'], pair['output']
        if (len(inp), len(inp[0])) != (len(out), len(out[0])):
            return ()
        if Counter(v for row in inp for v in row) != Counter(v for row in out for v in row):
            return ()
    roles = []
    for background in range(10):
        for material in range(10):
            if background == material:
                continue
            role = (background, material)
            admissible = True
            for pair in teachers:
                inp, out = pair['input'], pair['output']
                if not any(v == material for row in inp for v in row):
                    admissible = False
                    break
                # Frozen walls have identical coordinates/colors in every state.
                if any(a != b and (a not in role or b not in role)
                       for ra, rb in zip(inp, out) for a, b in zip(ra, rb)):
                    admissible = False
                    break
                if not expected_terminal(out, *role):
                    admissible = False
                    break
            if not admissible:
                continue
            results = [render(pair['input'], role)[0] for pair in teachers]
            if all(output is not None and output == pair['output']
                   for output, pair in zip(results, teachers)):
                roles.append(role)
    # No partial models escape if a call fails or exhausts external resources.
    return tuple(roles)


def consensus(grid, roles):
    if not roles:
        return None, {'failure': 'no_finite_teacher_role'}
    results = [render(grid, role) for role in roles]
    record = {'mode': 'prospective_finite_material_composition',
              'roles': roles, 'records': [rec for out, rec in results]}
    if any(out is None for out, rec in results):
        return None, {**record, 'failure': 'retained_finite_role_HOLD'}
    if any(out != results[0][0] for out, rec in results[1:]):
        return None, {**record, 'failure': 'retained_finite_roles_disagree'}
    return results[0][0], record
