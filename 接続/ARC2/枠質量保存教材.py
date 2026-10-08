"""枠質量保存の教師適合と空prior通常HDS境界用adapter。"""
from . import 枠質量保存核 as api
from .境界点周期候補 import valid_grid


def 有効な教師群(teachers):
    if type(teachers) is not list or len(teachers) < 2:
        return False
    seen = set()
    for pair in teachers:
        if type(pair) is not dict:
            return False
        source, target = pair.get('input'), pair.get('output')
        if not valid_grid(source) or not valid_grid(target):
            return False
        if len(source) != len(target) or len(source[0]) != len(target[0]):
            return False
        key = tuple(map(tuple, source))
        if key in seen:
            return False
        seen.add(key)
    return True


class 枠質量保存教材:
    def __init__(self, teachers):
        self.model = ()
        if 有効な教師群(teachers):
            self.model = api.fit_payload_conservation(teachers)[0]

    def 候補(self, grid, _policy=None):
        if not valid_grid(grid):
            return None, {'failure': 'invalid_grid'}
        output, diagnostic = api.apply_retained(grid, self.model)
        return output, JSON診断(diagnostic)

    def 記録(self):
        return {'全教師再現': bool(self.model),
                '事前支持数': 0, '保持候補': self.model}


def JSON診断(value):
    if value is None or type(value) in (str, int, float, bool):
        return value
    if type(value) is dict:
        if not all(type(k) is str for k in value):
            raise TypeError('診断dictionary key must be str')
        return {k: JSON診断(v) for k, v in value.items()}
    if type(value) in (list, tuple):
        return [JSON診断(v) for v in value]
    if type(value) is set:
        return [JSON診断(v) for v in sorted(value)]
    raise TypeError('Unsupported diagnostic type: ' + type(value).__name__)
