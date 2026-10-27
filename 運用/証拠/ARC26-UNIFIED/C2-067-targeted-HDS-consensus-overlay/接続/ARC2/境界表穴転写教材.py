"""境界表穴転写の教師適合と空prior通常HDS境界用adapter。"""
from . import 境界表穴転写核 as api


def 有効な教師群(teachers):
    if type(teachers) is not list or len(teachers) < 2:
        return False
    seen = set()
    for pair in teachers:
        if type(pair) is not dict:
            return False
        source, target = pair.get('input'), pair.get('output')
        if not api.valid_grid(source) or not api.valid_grid(target):
            return False
        if len(source) != len(target) or len(source[0]) != len(target[0]):
            return False
        key = tuple(map(tuple, source))
        if key in seen:
            return False
        seen.add(key)
    return True


class 境界表穴転写教材:
    def __init__(self, teachers):
        self.model = ()
        if 有効な教師群(teachers):
            self.model = api.fit(teachers)[0]

    def 候補(self, grid, _policy=None):
        return api.predict(grid, self.model)

    def 記録(self):
        return {'全教師再現': bool(self.model),
                '事前支持数': 0, '保持候補': self.model}
