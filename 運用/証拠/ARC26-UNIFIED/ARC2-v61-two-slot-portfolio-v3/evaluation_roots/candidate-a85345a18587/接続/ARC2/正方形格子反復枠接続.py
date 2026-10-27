"""Narrow fallback after a complete old square-grammar structural no-fit."""
from .反復枠タイル本体 import fit


def complete_arc_teachers(teachers):
    if not isinstance(teachers, (list, tuple)) or len(teachers) < 2:
        return False
    keys = []
    for pair in teachers:
        if not isinstance(pair, dict) or set(pair) != {'input', 'output'}:
            return False
        for name in ('input', 'output'):
            grid = pair[name]
            if (type(grid) is not list or not 1 <= len(grid) <= 30
                    or type(grid[0]) is not list or not 1 <= len(grid[0]) <= 30
                    or any(type(row) is not list or len(row) != len(grid[0])
                           or any(type(value) is not int or not 0 <= value <= 9 for value in row)
                           for row in grid)):
                return False
        keys.append(tuple(map(tuple, pair['input'])))
    return len(set(keys)) == len(keys)


def complete_square_structural_no_fit(teachers, old_models, record, models):
    if old_models is not None or not complete_arc_teachers(teachers):
        return False
    if (type(record) is not dict
            or set(record) != {'models', 'teacher_records', 'pair_fits'}
            or record['models'] != []):
        return False
    observations, fits = record['teacher_records'], record['pair_fits']
    if (type(observations) is not dict or type(fits) is not dict
            or not models or set(observations) != set(models) or set(fits) != set(models)):
        return False
    for model in models:
        rows, flags = observations[model], fits[model]
        if (type(rows) is not list or type(flags) is not list
                or len(rows) != len(teachers) or len(flags) != len(teachers)
                or any(flag is not False for flag in flags)
                or any(type(row) is not dict
                       or row != {'failure': 'not_all_solid_squares'} for row in rows)):
            return False
    return True


def fit_after_complete_square_no_fit(teachers, old_models, old_record, models):
    if not complete_square_structural_no_fit(teachers, old_models, old_record, models):
        return None, {'failure': 'old_square_structural_no_fit_not_complete'}
    return fit(teachers)
