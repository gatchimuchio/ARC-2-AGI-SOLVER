"""元のgroup選択後に一意背景・整数中心・出力寸法を確認する。"""
from collections import Counter
from .既存部分見本転写 import select_panel_exemplar_group,partial_panel_exemplar_transfer


def guarded_panel_exemplar(grid):
    if not grid or not grid[0] or len(grid)>30 or len(grid[0])>30 or any(len(row)!=len(grid[0])for row in grid):
        return None,{'failure':'invalid_grid'}
    counts=Counter(v for row in grid for v in row)
    if sum(n==max(counts.values())for n in counts.values())!=1:
        return None,{'failure':'background_tie'}
    group=select_panel_exemplar_group(grid)
    if group is None:
        return None,{'failure':'no_valid_panel_exemplar_group'}
    h,w=group['panel_height'],group['panel_width']
    if any((h-m['height'])%2 or (w-m['width'])%2 for m in group['masks'].values()):
        return None,{'failure':'mask_bbox_center_not_integer'}
    out_h=len(group['row_positions'])*(h+1)+1
    out_w=len(group['col_positions'])*(w+1)+1
    if out_h>30 or out_w>30:
        return None,{'failure':'normalized_output_exceeds_arc_bounds'}
    out=partial_panel_exemplar_transfer(grid)
    if out is None or (len(out),len(out[0]))!=(out_h,out_w):
        return None,{'failure':'source_output_shape_mismatch'}
    return out,{'panel_shape':[h,w],'panel_count':len(group['panels']),
                'layout':[len(group['row_positions']),len(group['col_positions'])],
                'mask_shapes':[[m['height'],m['width']]for m in group['masks'].values()],
                'output_shape':[out_h,out_w]}


class 部分見本教材:
    def __init__(self, 教師群):
        self.全教師再現=False
        if not 教師群 or len({tuple(map(tuple,p['input']))for p in 教師群})!=len(教師群):
            return
        self.全教師再現=all(guarded_panel_exemplar(p['input'])[0]==p['output']for p in 教師群)

    def 候補(self, 格子, _policy):
        if not self.全教師再現:
            return None,{'failure':'全教師を再現する部分見本転写なし'}
        return guarded_panel_exemplar(格子)

    def 記録(self):
        return {'全教師再現':self.全教師再現}


# Preserve the accepted family and its successful return path verbatim.
from . import 枠見本所有補完 as _framed


_元部分見本教材 = 部分見本教材


class 部分見本教材(_元部分見本教材):
    def __init__(self, 教師群):
        super().__init__(教師群)
        self.枠見本モデル群 = None
        self.枠見本適合 = None
        if self.全教師再現:
            return
        if (not isinstance(教師群, (list, tuple)) or len(教師群) < 2
                or any(not isinstance(pair, dict)
                       or not _framed.valid_grid(pair.get('input'))
                       or not _framed.valid_grid(pair.get('output')) for pair in 教師群)
                or len({tuple(map(tuple, pair['input'])) for pair in 教師群}) != len(教師群)):
            return
        # The original all(...) may stop at its first mismatch. Finish every
        # original teacher return before permitting the framed no-fit fallback.
        failures = {'invalid_grid', 'background_tie', 'no_valid_panel_exemplar_group',
                    'mask_bbox_center_not_integer', 'normalized_output_exceeds_arc_bounds',
                    'source_output_shape_mismatch'}
        matches = []
        for pair in 教師群:
            output, record = guarded_panel_exemplar(pair['input'])
            if (not isinstance(record, dict) or record.get('complete', True) is not True
                    or record.get('exhausted', True) is not True
                    or 'resource_exception' in record or 'exception' in record
                    or (output is None and record.get('failure') not in failures)
                    or (output is not None and (not _framed.valid_grid(output)
                                               or 'failure' in record))):
                raise ValueError('original_panel_fit_incomplete')
            matches.append(output == pair['output'])
        if all(matches):
            raise ValueError('original_panel_fit_replay_inconsistent')
        models, record = _framed.fit_teachers(教師群)
        if not isinstance(record, dict) or record.get('complete') is not True:
            raise ValueError('framed_panel_fit_incomplete')
        if models is not None:
            if not models:
                raise ValueError('framed_panel_fit_empty_models')
            self.枠見本モデル群 = tuple(tuple(model) for model in models)
            self.枠見本適合 = record

    def 候補(self, 格子, _policy):
        if self.全教師再現 or self.枠見本モデル群 is None:
            return super().候補(格子, _policy)
        return _framed.render(格子, self.枠見本モデル群)

    def 記録(self):
        record = super().記録()
        if self.枠見本モデル群 is not None:
            record['枠見本所有補完'] = {'models': self.枠見本モデル群,
                                      'fit': self.枠見本適合}
        return record
