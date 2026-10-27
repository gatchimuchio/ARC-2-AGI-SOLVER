"""元の最大container選択後に幾何一意性・完全map・出力寸法を確認する。"""
from collections import Counter
from .既存穴形拡大 import _hole_scale_components,_hole_scale_bbox,_hole_scale_render


def guarded_hole_scale(grid):
    if not grid or not grid[0] or len(grid)>30 or len(grid[0])>30 or any(len(row)!=len(grid[0])for row in grid):
        return None,{'failure':'invalid_grid'}
    counts=Counter(v for row in grid for v in row)
    backgrounds=[v for v,n in counts.items()if n==max(counts.values())]
    if len(backgrounds)!=1:
        return None,{'failure':'background_tie'}
    bg=backgrounds[0]
    ranks=[]
    for color in sorted(set(counts)-{bg}):
        for component in _hole_scale_components(grid,color):
            r0,c0,r1,c1=_hole_scale_bbox(component)
            area=(r1-r0+1)*(c1-c0+1)
            holes=sum(grid[r][c]==bg for r in range(r0,r1+1)for c in range(c0,c1+1))
            if area>=16 and holes>=2:
                ranks.append((area,len(component)))
    if ranks and ranks.count(max(ranks))!=1:
        return None,{'failure':'tied_container_geometry_rank'}
    out,record=_hole_scale_render(grid)
    if out is None:
        return None,record
    r0,c0,r1,c1=record['hole_scale_map_bbox']
    color=record['hole_scale_map_color']
    if any(grid[r][c]not in(bg,color)for r in range(r0,r1+1)for c in range(c0,c1+1)):
        return None,{'failure':'foreign_color_inside_map'}
    if any(grid[r][c]!=color for r in range(r0,r1+1)for c in range(c0,c1+1)if r in(r0,r1)or c in(c0,c1)):
        return None,{'failure':'map_border_not_complete'}
    if len(out)>30 or len(out[0])>30:
        return None,{'failure':'scaled_output_exceeds_arc_bounds'}
    return out,record


class 穴形拡大教材:
    def __init__(self, 教師群):
        self.全教師再現=False
        if not 教師群 or len({tuple(map(tuple,p["input"]))for p in 教師群})!=len(教師群):
            return
        self.全教師再現=all(guarded_hole_scale(p["input"])[0]==p["output"]for p in 教師群)

    def 候補(self, 格子, _policy):
        if not self.全教師再現:
            return None,{"failure":"全教師を再現する穴形拡大なし"}
        return guarded_hole_scale(格子)

    def 記録(self):
        return {"全教師再現":self.全教師再現}
