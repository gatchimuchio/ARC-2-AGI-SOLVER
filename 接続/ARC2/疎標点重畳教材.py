"""Sparse pin view inside the existing completed overlap-assembly family."""


class ExistingOverlapIncomplete(RuntimeError):
    def __init__(self, record):
        super().__init__(str(record.get('failure', 'incomplete_existing_overlap')))
        self.record = record


_COMPLETED_NO_FIT = frozenset({
    'invalid_grid', 'background_tie', 'too_few_fragments',
    'foreign_foreground_in_fragment_bbox', 'overlap graph is not connected',
    'placement conflict or no-op output', 'output_outside_arc_bounds',
    'selected_edge_offset_not_unique', 'unresolved_maximum_tree',
    'simultaneous_crop_conflict',
})
_CROP_CONFLICT = frozenset({'placement conflict or no-op output',
                           'simultaneous_crop_conflict'})


def completed_existing_return(output, record):
    def inspect(value):
        if isinstance(value, dict):
            if (('failure' in value and value['failure'] not in _COMPLETED_NO_FIT)
                    or value.get('complete') is False or 'exception_type' in value
                    or 'error' in value or value.get('incomplete') is True):
                raise ExistingOverlapIncomplete(value)
            for child in value.values():
                inspect(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                inspect(child)
    if not isinstance(record, dict):
        raise ExistingOverlapIncomplete({'failure': 'missing_existing_record'})
    inspect(record)
    if output is None and record.get('failure') not in _COMPLETED_NO_FIT:
        raise ExistingOverlapIncomplete(record)
    if output is not None and 'failure' in record:
        raise ExistingOverlapIncomplete(record)


def extend_overlap_family(original_type, original_render):
    class 重畳組立教材(original_type):
        def __init__(self, 教師群):
            super().__init__(教師群)
            if self.全教師再現:
                return
            from .疎標点重畳候補 import valid_grid, fit_teachers
            if (not isinstance(教師群, (list, tuple)) or not 教師群
                    or any(not isinstance(pair, dict) or not valid_grid(pair.get('input'))
                           or not valid_grid(pair.get('output')) for pair in 教師群)
                    or len({tuple(map(tuple, pair['input'])) for pair in 教師群}) != len(教師群)):
                return
            # The old constructor may short-circuit at its first mismatch.
            # Complete every legacy teacher call before considering this view.
            original_returns = [original_render(pair['input']) for pair in 教師群]
            for output, record in original_returns:
                completed_existing_return(output, record)
            if not any(output is None and record.get('failure') in _CROP_CONFLICT
                       for output, record in original_returns):
                return
            policies, _ = fit_teachers(教師群)
            if policies:
                self.疎標点規則 = policies

        def 候補(self, 格子, _policy):
            if self.全教師再現 or not hasattr(self, '疎標点規則'):
                return super().候補(格子, _policy)
            from .疎標点重畳候補 import render
            return render(格子, self.疎標点規則)

        def 記録(self):
            original = super().記録()
            if self.全教師再現 or not hasattr(self, '疎標点規則'):
                return original
            return {**original, 'sparse_marker_overlap': {'policies': self.疎標点規則}}

    return 重畳組立教材
