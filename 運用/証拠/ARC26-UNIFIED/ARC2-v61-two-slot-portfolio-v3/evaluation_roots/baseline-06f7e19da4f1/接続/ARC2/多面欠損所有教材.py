"""多面欠損所有の教師適合と空prior通常HDS境界用adapter。"""
from . import 多面欠損所有核 as api


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


class 多面欠損所有教材:
    def __init__(self, teachers):
        self.model = []
        if 有効な教師群(teachers):
            self.model = api.fit_teachers(teachers)

    def 候補(self, grid, _policy=None):
        return api.predict(grid, self.model)

    def 記録(self):
        return {'全教師再現': bool(self.model),
                '事前支持数': 0, '保持候補': self.model}
