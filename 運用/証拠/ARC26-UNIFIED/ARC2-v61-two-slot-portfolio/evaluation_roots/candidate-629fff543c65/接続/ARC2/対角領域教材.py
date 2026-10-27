"""新しい充填色を全教師から選び、既存の領域和候補をHDSへ渡す。"""
from collections import Counter
from .既存対角領域 import (
    infer_single_fill_color, anti_diagonal_segments,
    diagonal_implied_boundary_region_fill,
)


def 対角領域候補(格子, 充填色):
    if not 格子 or not 格子[0] or len(格子)>30 or len(格子[0])>30 or any(len(row)!=len(格子[0])for row in 格子):
        return None,{'failure':'invalid_grid'}
    数=Counter(v for row in 格子 for v in row)
    if sum(n==max(数.values())for n in 数.values())!=1:
        return None,{'failure':'background_tie'}
    if 充填色 is None or 充填色 in 数:
        return None,{'failure':'fill_is_not_new_color'}
    線分=anti_diagonal_segments(格子)
    if not 線分:
        return None,{'failure':'single_foreground_segments_unavailable'}
    候補=diagonal_implied_boundary_region_fill(格子,充填色)
    if 候補 is None:
        return None,{'failure':'no_region_addition'}
    return 候補,{'segments':len(線分),'fill':充填色,'added_pixels':sum(a!=b for x,y in zip(格子,候補)for a,b in zip(x,y))}


class 対角領域教材:
    def __init__(self, 教師群):
        self.充填色=None
        if not 教師群 or len({tuple(map(tuple,p['input']))for p in 教師群})!=len(教師群):
            return
        for 対 in 教師群:
            数=Counter(v for row in 対['input']for v in row)
            if not 数 or sum(n==max(数.values())for n in 数.values())!=1:
                return
        色=infer_single_fill_color(教師群)
        if 色 is not None and all(対角領域候補(p['input'],色)[0]==p['output']for p in 教師群):
            self.充填色=色

    def 候補(self, 格子, _policy):
        return 対角領域候補(格子,self.充填色)

    def 記録(self):
        return {'充填色':self.充填色}
