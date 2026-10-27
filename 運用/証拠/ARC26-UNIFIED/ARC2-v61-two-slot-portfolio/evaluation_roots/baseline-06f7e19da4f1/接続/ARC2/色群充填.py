"""元の充填候補が全教師入力で空の場合だけ、色群の入力viewを補う。"""
from itertools import combinations
from .既存色群関係 import scaffold_legend_color_cells, scaffold_legend_bbox, bbox_relation_for_bboxes
from .既存穴充填 import (
    _dominant_color, _orthogonal_components,
    _template_hole_pack_output, _template_hole_pack_candidates,
)

グループ上限 = 55
部品上限 = 12


def 色群候補(格子):
    背景 = _dominant_color(格子)
    色群 = sorted({v for row in 格子 for v in row}-{背景})
    集合 = {c:scaffold_legend_color_cells(格子,c) for c in 色群}
    箱 = {c:scaffold_legend_bbox(集合[c]) for c in 色群}
    前景 = set().union(*集合.values()) if 集合 else set()
    選択肢 = [(c,) for c in 色群]
    for a,b in combinations(色群,2):
        関係 = bbox_relation_for_bboxes(箱[a],箱[b])
        if 関係.aligned_directions and 関係.chebyshev_gap == 0:
            選択肢.append((a,b))
    if len(選択肢) > グループ上限:
        return None, {'failure':'色群上限により未解決'}
    出力候補 = {}
    候補記録 = []
    for 色組 in 選択肢:
        固定セル = set().union(*(集合[c] for c in 色組))
        r0,c0,r1,c1 = scaffold_legend_bbox(固定セル)
        高さ,幅 = r1-r0+1,c1-c0+1
        箱内前景 = {(r,c) for r,c in 前景 if r0<=r<=r1 and c0<=c<=c1}
        部品群 = _orthogonal_components(前景-固定セル)
        if 高さ<3 or 幅<3 or 高さ*幅!=len(前景) or 箱内前景!=固定セル or not 部品群:
            continue
        if len(部品群) > 部品上限:
            return None, {'failure':'部品上限により未解決','pieces':len(部品群)}
        template = [row[c0:c1+1] for row in 格子[r0:r1+1]]
        source = [[背景 if (r,c) in 固定セル else v for c,v in enumerate(row)] for r,row in enumerate(格子)]
        格子候補群 = _template_hole_pack_output(template,source,背景)
        候補記録.append({'色組':色組,'bbox':(r0,c0,r1,c1),'部品数':len(部品群),'解数':len(格子候補群)})
        for y in 格子候補群:
            出力候補.setdefault(tuple(map(tuple,y)),y)
    return (next(iter(出力候補.values())) if len(出力候補)==1 else None), {
        'output_count':len(出力候補),'candidates':候補記録}


class 色群充填教材:
    def __init__(self, 教師群):
        # 適用域は教師入力だけで決定。正解との一致・native HOLD・testは使わない。
        # エラーや時間切れを空候補へ変換しない。
        self.既存候補数 = [len(_template_hole_pack_candidates(p['input'])) for p in 教師群]
        self.適用可 = bool(教師群) and all(n==0 for n in self.既存候補数)

    def 候補(self, 格子, _policy):
        if not self.適用可:
            return None, {'failure':'現在教師入力に既存の充填候補が存在する'}
        return 色群候補(格子)

    def 記録(self):
        return {'適用可':self.適用可,'教師入力の既存候補数':self.既存候補数,
                'グループ上限':グループ上限,'部品上限':部品上限}
