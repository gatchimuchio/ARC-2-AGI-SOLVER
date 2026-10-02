"""全認識key・両sideの同時提案を証明して元renderer格子のみHDSへ渡す。"""
from __future__ import annotations
from collections import Counter, defaultdict
from .既存側周期 import (repeated_shape_groups, component_bbox, side_seed_patterns,
    repeated_shape_vertical_side_periodic_extension)

def guarded_render(grid):
    if (not isinstance(grid,list) or not 1<=len(grid)<=30 or not isinstance(grid[0],list)
        or not 1<=len(grid[0])<=30 or any(not isinstance(row,list)or len(row)!=len(grid[0])
        or any(type(v)is not int or not 0<=v<=9 for v in row)for row in grid)):
        return None,{'failure':'invalid_arc_grid'}
    counts=Counter(v for row in grid for v in row)
    leaders=[c for c,n in counts.items()if n==max(counts.values())]
    if len(leaders)!=1:return None,{'failure':'background_tie'}
    background=leaders[0];height,width=len(grid),len(grid[0])
    groups=repeated_shape_groups(grid)
    if not groups:return None,{'failure':'no_recognized_key_groups'}
    all_keys=set().union(*(set().union(*components)for _,_,components in groups))
    proposals=defaultdict(set);seed_cells=set();events=[]
    for key_color,shape,components in groups:
        own_keys=set().union(*components)
        for component in components:
            r0,c0,r1,c1=component_bbox(component)
            for side in ('up','down'):
                step=-1 if side=='up'else 1;start=r0-1 if side=='up'else r1+1
                event={'key_color':key_color,'key_shape_size':len(shape),'bbox':[r0,c0,r1,c1],'side':side}
                if not 0<=start<height:
                    events.append(dict(event,inactive='outside_canvas'));continue
                cols=[c for c in range(c0,c1+1)if grid[start][c]not in (background,key_color)]
                if not cols:
                    events.append(dict(event,inactive='no_adjacent_payload'));continue
                if cols!=list(range(cols[0],cols[-1]+1)):
                    return None,{'failure':'noncontiguous_adjacent_payload','event':event,'columns':cols}
                raw_seed=side_seed_patterns(grid,background,key_color,component,side)
                if raw_seed is None or raw_seed[0]!=cols:
                    return None,{'failure':'source_seed_disagreement','event':event}
                period=raw_seed[1];observed=[];row=start
                while 0<=row<height:
                    if any(grid[row][c]in(background,key_color)for c in cols):break
                    if any(grid[row][c]not in(background,key_color)for c in range(c0,c1+1)if c not in cols):break
                    values=tuple(grid[row][c]for c in cols)
                    if values!=period[len(observed)%len(period)]:
                        return None,{'failure':'source_period_disagreement','event':event}
                    observed.append(values);seed_cells.update((row,c)for c in cols);row+=step
                local_count=0
                for index,row in enumerate(range(start,-1,-1)if side=='up'else range(start,height)):
                    for col,value in zip(cols,period[index%len(period)]):
                        if (row,col)in own_keys:continue
                        proposals[row,col].add(value);local_count+=1
                events.append(dict(event,columns=cols,period=[list(p)for p in period],observed_seed_rows=len(observed),proposal_count=local_count))
    conflicts=[(p,sorted(v))for p,v in sorted(proposals.items())if len(v)!=1]
    record={'background':background,'key_group_count':len(groups),'key_count':sum(len(c)for _,_,c in groups),
            'key_cells':len(all_keys),'seed_cells':len(seed_cells),'events':events,'proposal_cells':len(proposals)}
    if conflicts:return None,dict(record,failure='proposal_colour_conflict',conflicts=conflicts)
    expected=[row[:]for row in grid]
    for (row,col),values in proposals.items():expected[row][col]=next(iter(values))
    if any(expected[r][c]!=grid[r][c]for r,c in all_keys):return None,dict(record,failure='key_changed')
    if any(expected[r][c]!=grid[r][c]for r,c in seed_cells):return None,dict(record,failure='seed_changed')
    if any(expected[r][c]!=grid[r][c]for r in range(height)for c in range(width)if(r,c)not in proposals):
        return None,dict(record,failure='outside_proposals_changed')
    raw,raw_records=repeated_shape_vertical_side_periodic_extension(grid)
    if raw!=expected:return None,dict(record,failure='source_grid_disagreement')
    if raw is None or not raw_records or raw==grid:return None,dict(record,failure='no_change')
    record.update(raw_records=raw_records,changed_pixels=sum(raw[r][c]!=grid[r][c]for r in range(height)for c in range(width)),
                  changed_original_payload=sum(raw[r][c]!=grid[r][c]and grid[r][c]!=background for r in range(height)for c in range(width)))
    return raw,record

class 側周期教材:
    def __init__(self, 教師群):
        self.成立 = False
        if len(教師群)<2:
            return
        if len({tuple(map(tuple,p['input']))for p in 教師群})!=len(教師群):
            return
        for 対 in 教師群:
            候補, _ = guarded_render(対['input'])
            if 候補 is None or 候補 != 対['output']:
                return
        self.成立 = True

    def 候補(self, 格子, _policy):
        if not self.成立:
            return None, {"failure": "全教師を再現する側周期延長なし"}
        return guarded_render(格子)

    def 記録(self):
        return {"全教師再現": self.成立}
