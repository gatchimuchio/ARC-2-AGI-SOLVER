"""全教師で主色を選び、全描画提案の競合を排除した候補だけを渡す。"""
from collections import Counter
from .既存対角線橋 import (
    foreground_colors, foreground_count, diagonal_segment,
    full_diagonal_through, render_diagonal_bridge_crossing,
)


def 対角線橋候補(格子, 主色):
    if not 格子 or not 格子[0] or len(格子)>30 or len(格子[0])>30 or any(len(row)!=len(格子[0])for row in 格子):
        return None, {'failure':'invalid_grid'}
    数=Counter(v for row in 格子 for v in row)
    背景群=[v for v,n in 数.items()if n==max(数.values())]
    if len(背景群)!=1 or 主色==背景群[0]:
        return None, {'failure':'background_or_primary_role_not_unique'}
    背景=背景群[0]
    候補,記録=render_diagonal_bridge_crossing(格子,主色)
    if 候補 is None:
        return None,記録
    提案={}
    def 追加(位置,色):
        r,c=位置
        if 格子[r][c]==背景:
            提案.setdefault(位置,set()).add(色)
    for 橋 in 記録['bridges']:
        for 位置 in diagonal_segment(*橋['endpoints']):
            追加(位置,主色)
    for 交点 in 記録['blockers']:
        r,c=交点['cell']
        for 位置 in full_diagonal_through(len(格子),len(格子[0]),r,c,交点['perpendicular_direction']):
            追加(位置,交点['color'])
    if any(len(色群)>1 for 色群 in 提案.values()):
        return None, {'failure':'conflicting_bridge_ray_proposals'}
    合成=[row[:]for row in 格子]
    for (r,c),色群 in 提案.items():
        合成[r][c]=next(iter(色群))
    if 候補!=合成:
        return None, {'failure':'source_render_does_not_match_proposal_union'}
    return 候補,記録


class 対角線橋教材:
    def __init__(self, 教師群):
        self.主色候補=()
        if not 教師群 or len({tuple(map(tuple,p['input']))for p in 教師群})!=len(教師群):
            return
        色集合=[]
        for 対 in 教師群:
            入力,正解=対['input'],対['output']
            数=Counter(v for row in 入力 for v in row)
            if not 数 or sum(n==max(数.values())for n in 数.values())!=1:
                return
            if (len(入力),len(入力[0]))!=(len(正解),len(正解[0])) or foreground_count(入力)>14:
                return
            色=set(foreground_colors(入力))
            if not 1<=len(色)<=2:
                return
            色集合.append(色)
        if len(set.union(*色集合))>2:
            return
        適合=[]
        for 主色 in sorted(set.intersection(*色集合)):
            結果=[対角線橋候補(p['input'],主色)for p in 教師群]
            if all(候補==p['output'] and 記録.get('bridge_count')==1 for p,(候補,記録)in zip(教師群,結果)):
                適合.append(主色)
        self.主色候補=tuple(適合)

    def 候補(self, 格子, _policy):
        if len(self.主色候補)!=1:
            return None, {'failure':'全教師に適合する主色が一意でない','候補数':len(self.主色候補)}
        return 対角線橋候補(格子,self.主色候補[0])

    def 記録(self):
        return {'主色候補':list(self.主色候補)}
