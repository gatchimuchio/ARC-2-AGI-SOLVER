"""Frozen input-derived growth composition with an all-teacher gate and empty prior."""
from .観測成長 import growth_series as api


class 観測成長教材:
    def __init__(self, teachers):
        self.fitted = api.fit(teachers)
        self.teacher_count = len(teachers)

    def _valid(self):
        return self.fitted == {'kind': 'observed_series_composition', 'version': 4}

    def 候補(self, grid, _policy):
        if not self._valid():
            return None, {'status': 'HOLD', 'failure': 'no_fitted_program'}
        return api.predict(grid, with_evidence=True)

    def 記録(self):
        return {'全教師再現': self._valid(), '教師数': self.teacher_count,
                '事前支持数': 0, '保持候補': [dict(self.fitted)] if self._valid() else []}
