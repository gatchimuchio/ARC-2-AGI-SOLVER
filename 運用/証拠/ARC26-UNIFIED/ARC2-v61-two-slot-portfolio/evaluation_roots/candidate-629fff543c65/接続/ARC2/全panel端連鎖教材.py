"""Whole-panel port chains, ordinary teacher support and empty prior.

The frozen pure API returns Fit or None; SearchIncomplete propagates.
"""
from dataclasses import asdict
from . import 全panel端連鎖核 as api


class 全panel端連鎖教材:
    def __init__(self, teachers):
        self.fitted = api.fit(teachers)
        self.teacher_count = len(teachers)

    def 候補(self, grid, _policy):
        return api.predict(self.fitted, grid)

    def 記録(self):
        return {'全教師再現': self.fitted is not None,
                '教師数': self.teacher_count, '事前支持数': 0,
                '保持候補': asdict(self.fitted) if self.fitted is not None else None}
