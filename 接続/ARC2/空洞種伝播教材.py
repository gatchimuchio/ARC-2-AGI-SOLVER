"""All-teacher cavity-seed propagation, ordinary HDS support and empty prior."""
from . import 空洞種伝播核 as api


class 空洞種伝播教材:
    def __init__(self, teachers):
        self.models, self.fit_record = api.fit(teachers)
        self.teacher_count = len(teachers)

    def 候補(self, grid, _policy):
        return api.predict(grid, self.models)

    def 記録(self):
        return {'全教師再現': bool(self.models), '教師数': self.teacher_count,
                '事前支持数': 0, '保持候補': self.models, '教師診断': self.fit_record}
