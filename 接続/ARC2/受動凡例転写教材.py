"""全教師適合した受動凡例転写。空prior・通常HDS支持を維持する。"""
from . import 受動凡例転写核 as api


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
    raise TypeError('unsupported passive keyed stamp diagnostic: ' + type(value).__name__)


class 受動凡例転写教材:
    def __init__(self, teachers):
        self.fitted, _ = api.fit_teachers(teachers)
        self.teacher_count = len(teachers)

    def 候補(self, grid, _policy):
        output, record = api.predict(grid, self.fitted)
        return output, 診断をJSON値へ(record)

    def 記録(self):
        return {'全教師再現': self.fitted is not None,
                '教師数': self.teacher_count, '事前支持数': 0,
                '保持候補': list(self.fitted["background_rules"])
                if self.fitted is not None else None}
