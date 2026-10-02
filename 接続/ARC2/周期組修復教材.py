"""元priorの選択を全modal候補で検査し、別の修復結果へ置き換えない。"""
from collections import Counter
from .既存周期組修復 import (
    framed_panel_bboxes, peel_uniform_borders, repair_tuple_sequence,
    sequence_cell_mismatch, periodic_panel_tuple_repair,
)


def certify_sequence(sequence):
    if not sequence:
        return None,{'failure':'empty_sequence'}
    choices=[]
    for period in range(1,min(6,len(sequence))+1):
        tuple_cost=0
        cell_cost=0
        modal_choices=[]
        for offset in range(period):
            values=sequence[offset::period]
            counts=Counter(values)
            maximum=max(counts.values())
            modes=[v for v,n in counts.items()if n==maximum]
            costs={v:sum(sequence_cell_mismatch(v,x)for x in values)for v in modes}
            best_cell=min(costs.values())
            modal_choices.append([v for v in modes if costs[v]==best_cell])
            tuple_cost+=len(values)-maximum
            cell_cost+=best_cell
        choices.append({'score':(tuple_cost,cell_cost,period),'modes':modal_choices})
    best=min(choices,key=lambda x:x['score'])
    if any(len(v)!=1 for v in best['modes']):
        return None,{'failure':'tied_optimal_modal_tuples','score':best['score']}
    motif=[v[0]for v in best['modes']]
    candidate=[motif[i%len(motif)]for i in range(len(sequence))]
    raw,record=repair_tuple_sequence(sequence)
    raw_score=(record['tuple_mismatch'],record['cell_mismatch'],record['period'])
    if raw!=candidate or raw_score!=best['score']:
        return None,{'failure':'source_choice_not_unique_optimum','score':best['score'],'source_score':raw_score}
    if best['score'][0]>max(1,len(sequence)//3):
        return None,{'failure':'panel_exceeds_original_noise_budget','score':best['score']}
    return raw,{'score':best['score']}


def guarded_tuple_repair(grid):
    if not grid or not grid[0] or len(grid)>30 or len(grid[0])>30 or any(len(row)!=len(grid[0])for row in grid):
        return None,{'failure':'invalid_grid'}
    expected=[row[:]for row in grid]
    certificates=[]
    for bbox in framed_panel_bboxes(grid):
        top,left,bottom,right,_=peel_uniform_borders(grid,bbox)
        height,width=bottom-top+1,right-left+1
        if height<=0 or width<=0:
            return None,{'failure':'empty_pattern_area'}
        columns=width>=height
        sequence=([tuple(grid[r][c]for r in range(top,bottom+1))for c in range(left,right+1)]if columns
                  else [tuple(grid[r][c]for c in range(left,right+1))for r in range(top,bottom+1)])
        repaired,cert=certify_sequence(sequence)
        if repaired is None:
            return None,{'failure':cert['failure'],'bbox':bbox[:4],'certificate':cert}
        certificates.append({'bbox':bbox[:4],'axis':'columns'if columns else 'rows',**cert})
        if columns:
            for c,values in zip(range(left,right+1),repaired):
                for r,value in zip(range(top,bottom+1),values):expected[r][c]=value
        else:
            for r,values in zip(range(top,bottom+1),repaired):
                for c,value in zip(range(left,right+1),values):expected[r][c]=value
    raw,records=periodic_panel_tuple_repair(grid)
    if raw!=expected:
        return None,{'failure':'source_grid_differs_from_certified_panels'}
    if not records or raw==grid:
        return None,{'failure':'no_tuple_repair'}
    return raw,{'certificates':certificates,'source_records':records}


class 周期組修復教材:
    def __init__(self, 教師群):
        self.全教師再現=False
        if not 教師群 or len({tuple(map(tuple,p['input']))for p in 教師群})!=len(教師群):
            return
        self.全教師再現=all(guarded_tuple_repair(p['input'])[0]==p['output']for p in 教師群)

    def 候補(self, 格子, _policy):
        if not self.全教師再現:
            return None,{'failure':'全教師を再現する確定した周期修復なし'}
        return guarded_tuple_repair(格子)

    def 記録(self):
        return {'全教師再現':self.全教師再現}
