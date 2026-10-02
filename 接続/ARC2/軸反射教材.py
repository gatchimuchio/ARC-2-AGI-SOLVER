"""未解決の適格物体を保留し、全教師で整合する標識色を保持する。"""
from collections import Counter
from .既存軸反射 import (
    marker_axis_components, connected_components_for_colors,
    eligible_marker_object_pair, reflection_target, bbox_gap,
    render_axis_marker_reflection_fill,
)


def guarded_reflection(grid, marker_color):
    if not grid or not grid[0] or len(grid)>30 or len(grid[0])>30 or any(len(row)!=len(grid[0])for row in grid):
        return None,{'failure':'invalid_grid'}
    counts=Counter(v for row in grid for v in row)
    backgrounds=[v for v,n in counts.items()if n==max(counts.values())]
    if len(backgrounds)!=1 or marker_color==backgrounds[0]:
        return None,{'failure':'background_or_marker_role_not_unique'}
    background=backgrounds[0]
    markers=marker_axis_components(grid,marker_color)
    if not markers or any(m['kind']=='unsupported'for m in markers):
        return None,{'failure':'marker_shape_unsupported'}
    objects=connected_components_for_colors(grid,set(counts)-{background,marker_color})
    for obj in objects:
        eligible=[m for m in markers if eligible_marker_object_pair(m,obj)]
        if not eligible:
            continue
        costs=[]
        for marker in eligible:
            targets=[reflection_target(marker,*p)for p in obj['cells']]
            if all(p is not None and 0<=p[0]<len(grid) and 0<=p[1]<len(grid[0]) and grid[p[0]][p[1]]==background for p in targets):
                costs.append(bbox_gap(marker['bbox'],obj['bbox']))
        if not costs:
            return None,{'failure':'eligible_object_without_complete_reflection'}
        if costs.count(min(costs))!=1:
            return None,{'failure':'nearest_marker_tie'}
    return render_axis_marker_reflection_fill(grid,marker_color)


class 軸反射教材:
    def __init__(self, 教師群):
        self.標識色候補=()
        if not 教師群 or len({tuple(map(tuple,p['input']))for p in 教師群})!=len(教師群):
            return
        前景色群=[]
        for 対 in 教師群:
            数=Counter(v for row in 対['input']for v in row)
            if not 数:
                return
            背景群=[v for v,n in 数.items()if n==max(数.values())]
            if len(背景群)!=1:
                return
            前景色群.append(set(数)-set(背景群))
        self.標識色候補=tuple(色 for 色 in sorted(set.intersection(*前景色群))
            if all(guarded_reflection(p['input'],色)[0]==p['output']for p in 教師群))

    def 候補(self, 格子, _policy):
        if not self.標識色候補:
            return None,{'failure':'全教師で整合する標識色なし'}
        予測=[]
        記録=[]
        for 色 in self.標識色候補:
            格子予測,詳細=guarded_reflection(格子,色)
            記録.append({'marker_color':色,**詳細})
            if 格子予測 is None:
                return None,{'failure':'保持した標識色候補が未解決','alternatives':記録}
            予測.append(格子予測)
        if any(p!=予測[0]for p in 予測[1:]):
            return None,{'failure':'標識色候補間の完全格子が不一致','alternatives':記録}
        return 予測[0],{'alternatives':記録}

    def 記録(self):
        return {'標識色候補':list(self.標識色候補)}
