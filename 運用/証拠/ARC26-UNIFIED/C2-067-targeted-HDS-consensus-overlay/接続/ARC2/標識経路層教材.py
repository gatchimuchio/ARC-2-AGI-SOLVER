"""全教師適合の標識経路層関係。空prior通常HDS境界。"""
from itertools import permutations
from dataclasses import dataclass
from . import 標識経路層核 as core
from .二軸補完教材 import valid_grid

def render(grid, *model):
    return core.render(grid, *model)

def valid_teachers(teachers):
    if type(teachers) is not list or len(teachers) < 2:
        return False
    seen = set()
    for pair in teachers:
        if type(pair) is not dict:
            return False
        source, target = pair.get('input'), pair.get('output')
        if not valid_grid(source) or not valid_grid(target):
            return False
        if (len(source), len(source[0])) != (len(target), len(target[0])):
            return False
        key = tuple(map(tuple, source))
        if key in seen:
            return False
        seen.add(key)
    return True


def fit(teachers):
    if not valid_teachers(teachers):
        return (), {'failure': 'invalid_teachers'}
    inputs = {v for p in teachers for row in p['input'] for v in row}
    outputs = {v for p in teachers for row in p['output'] for v in row}
    markers = inputs - outputs
    # Both disappearing marker roles and all possible backgrounds are tested.
    # Retain every complete teacher fit; never select a successful subset.
    retained, records = [], []
    for repair, control in permutations(sorted(markers), 2):
        for background in sorted(outputs - {repair, control}):
            model = (background, repair, control)
            results = [render(p['input'], *model) for p in teachers]
            flags = [out == p['output'] for p, (out, rec) in zip(teachers, results)]
            records.append({'model': model, 'teacher_equal': flags,
                            'failures': [rec.get('failure') for out, rec in results]})
            if all(flags):
                retained.append(model)
    return tuple(retained), {'complete': True, 'trials': records}


def valid_models(models):
    return (type(models) is tuple and all(type(m) is tuple and len(m) == 3
            and all(type(v) is int and 0 <= v <= 9 for v in m)
            and len(set(m)) == 3 for m in models)
            and len(set(models)) == len(models))


def consensus(grid, models):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_grid'}
    if not valid_models(models):
        return None, {'failure': 'invalid_retained_state'}
    if not models:
        return None, {'failure': 'no_teacher_fit_model'}
    results = [render(grid, *m) for m in models]
    records = [{'model': m, 'candidate': out, 'detail': rec}
               for m, (out, rec) in zip(models, results)]
    if any(out is None for out, rec in results):
        return None, {'failure': 'retained_model_hold', 'retained_results': records}
    if len({tuple(map(tuple, out)) for out, rec in results}) != 1:
        return None, {'failure': 'retained_models_disagree', 'retained_results': records}
    return results[0][0], {'models': len(models), 'retained_results': records}


@dataclass(frozen=True, slots=True, init=False)
class 標識経路層教材:
    model: tuple

    def __init__(self, teachers):
        object.__setattr__(self, 'model', fit(teachers)[0])

    def 候補(self, grid, _policy=None):
        return consensus(grid, self.model)

    def 記録(self):
        return {'全教師再現': bool(self.model), '事前支持数': 0,
                '保持候補': self.model}
