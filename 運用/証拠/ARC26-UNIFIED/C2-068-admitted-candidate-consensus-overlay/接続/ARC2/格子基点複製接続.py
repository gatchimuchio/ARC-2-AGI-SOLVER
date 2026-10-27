"""Existing anchored-motif family; conservative completed-no-fit extension."""
from . import 基点複製教材 as legacy
from . import 格子基点視野 as viewport


def complete_raw_record(record):
    if not isinstance(record, dict):
        return False
    if set(record) == {'failure', 'candidate_count', 'unique_output_count'}:
        count, unique = record['candidate_count'], record['unique_output_count']
        return (record['failure'] == 'anchored_singleton_motif_candidate_not_unique'
                and type(count) is int and type(unique) is int
                and 0 <= unique <= count and unique != 1)
    return (set(record) == {'renderer_case', 'background', 'anchored_source_color',
                            'anchored_marker_color', 'anchored_source_bbox',
                            'anchored_anchor_cell', 'anchored_motif_shape',
                            'anchored_row_step', 'anchored_col_step',
                            'anchored_marker_count', 'anchored_placement_count',
                            'anchored_placements'}
            and record['renderer_case'] == 'anchored_singleton_motif_tiler')


def completed_no_fit(teachers, fitted, record):
    if fitted is not False or not isinstance(record, dict):
        return False
    if set(record) != {'failure', 'raw_pair_fits', 'raw_records'}:
        return False
    fits, records = record['raw_pair_fits'], record['raw_records']
    return (record['failure'] == 'original_teacher_reproduction_failed'
            and isinstance(fits, list) and isinstance(records, list)
            and len(fits) == len(records) == len(teachers) and len(teachers) >= 2
            and all(type(value) is bool for value in fits) and not all(fits)
            and all(complete_raw_record(value) for value in records))


class 基点複製教材(legacy.基点複製教材):
    def __init__(self, 教師群):
        self.適合, record = legacy.fit_teachers(教師群)
        self.格子モデル = None
        if completed_no_fit(教師群, self.適合, record):
            self.格子モデル, _ = viewport.fit(教師群)

    def 候補(self, 格子, _policy):
        if self.適合 or self.格子モデル is None:
            return super().候補(格子, _policy)
        return viewport.consensus(格子, self.格子モデル)

    def 記録(self):
        if self.適合 or self.格子モデル is None:
            return super().記録()
        return {**super().記録(), '全教師共通格子基点展開': self.格子モデル}
