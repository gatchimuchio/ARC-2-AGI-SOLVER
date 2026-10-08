"""Frozen rectangle seam composition, ordinary teacher support and empty prior."""
from .矩形継目 import seam_rectangle as api


def require_complete(record):
    if record.get('status') == 'RESOURCE_INCOMPLETE' or record.get('complete') is False:
        raise api.base.BudgetIncomplete('rectangle_seam_resource_incomplete')


class 矩形継目教材:
    def __init__(self, teachers):
        self.fitted, self.fit_record = api.fit(teachers)
        require_complete(self.fit_record)
        self.teacher_count = len(teachers)

    def 候補(self, grid, _policy):
        if self.fitted is None:
            return None, {'status': 'HOLD', 'failure': 'no_fitted_program'}
        output, record = api.predict(self.fitted, grid)
        require_complete(record)
        return output, record

    def 記録(self):
        return {'全教師再現': self.fitted is not None,
                '教師数': self.teacher_count, '事前支持数': 0,
                '保持候補': list(self.fitted.programs) if self.fitted is not None else []}
