"""全教師適合した標点巡回。空prior・通常HDS支持を維持する。"""
from . import 標点巡回核 as api


def 診断をJSON値へ(value):
    """集合は全要素を保持する順序付き列へ。未対応型は例外として伝播。"""
    if value is None or type(value) in (str, int, float, bool):
        return value
    if isinstance(value, dict):
        return {key: 診断をJSON値へ(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return [診断をJSON値へ(item) for item in sorted(value)]
    if isinstance(value, (tuple, list)):
        return [診断をJSON値へ(item) for item in value]
    raise TypeError('unsupported marker traversal diagnostic: ' + type(value).__name__)


class 標点巡回教材:
    def __init__(self, teachers):
        self.fitted, _ = api.fit(teachers)
        self.teacher_count = len(teachers)

    def 候補(self, grid, _policy):
        output, record = api.predict(grid, self.fitted)
        return output, 診断をJSON値へ(record)

    def 記録(self):
        return {'全教師再現': self.fitted is not None,
                '教師数': self.teacher_count, '事前支持数': 0,
                '保持候補': [list(model) for model in self.fitted.models]
                if self.fitted is not None else None}
