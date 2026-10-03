"""固定stripe/ring規約の全cellを証明し、元格子を同じHDSへ渡す。"""
from __future__ import annotations
from .既存帯輪郭 import row_stripe_colors,render_stripe_sequence_nested_square_frames

def valid_grid(grid):
    return(isinstance(grid,list)and 1<=len(grid)<=30 and isinstance(grid[0],list)and 1<=len(grid[0])<=30
           and all(isinstance(row,list)and len(row)==len(grid[0])and all(type(v)is int and 0<=v<=9 for v in row)for row in grid))

def guarded_render(grid):
    if not valid_grid(grid):return None,{'failure':'invalid_arc_grid'}
    raw,raw_record=render_stripe_sequence_nested_square_frames(grid)
    if raw is None:return None,{'failure':'original_renderer_unresolved','raw_record':raw_record}
    height,width=len(grid),len(grid[0]);sequence=[]
    for row in grid:
        if len(set(row))!=1:return None,{'failure':'row_not_uniform'}
        sequence.append(row[0])
    if height<3 or width<2 or sequence[-1]!=sequence[-2]:return None,{'failure':'stripe_terminal_contract_failed'}
    prefix=sequence[:-1];side=2*len(prefix)
    if not 1<=side<=30:return None,{'failure':'output_outside_arc_bounds'}
    if not valid_grid(raw)or len(raw)!=side or len(raw[0])!=side:return None,{'failure':'source_shape_disagreement'}
    expected=[[None]*side for _ in range(side)];coverage=set();layers=[]
    for depth,color in enumerate(prefix):
        high=side-1-depth
        cells={(depth,c)for c in range(depth,high+1)}|{(high,c)for c in range(depth,high+1)}|{(r,depth)for r in range(depth,high+1)}|{(r,high)for r in range(depth,high+1)}
        if coverage&cells:return None,{'failure':'ring_layer_overlap'}
        coverage.update(cells)
        for r,c in cells:expected[r][c]=color
        layers.append({'depth':depth,'color':color,'side':high-depth+1,'cells':len(cells)})
    if len(coverage)!=side*side:return None,{'failure':'ring_coverage_incomplete'}
    reconstructed=[raw[d][d]for d in range(len(prefix))];reconstructed.append(reconstructed[-1])
    if reconstructed!=sequence:return None,{'failure':'source_sequence_reconstruction_failed'}
    expected_record={'renderer_case':'stripe_sequence_nested_square_frames','input_shape':[height,width],
                     'output_shape':[side,side],'ring_count':len(prefix),'ring_colors':prefix,'terminal_duplicate_color':sequence[-1]}
    if raw!=expected or raw_record!=expected_record:return None,{'failure':'original_grid_or_record_disagreement'}
    return raw,{'raw_record':raw_record,'unit_ring_count':len(prefix),'layers':layers,'output_cells':len(coverage),
                'input_rows_reconstructed':len(sequence),'terminal_rows_removed':1,'center_shape':[2,2]}

def fit_teachers(teachers):
    if len(teachers)<2 or any(not valid_grid(p['input'])or not valid_grid(p['output'])for p in teachers):
        return False,{'failure':'insufficient_or_invalid_teachers'}
    if len({tuple(map(tuple,p['input']))for p in teachers})!=len(teachers):return False,{'failure':'duplicate_teacher_inputs'}
    raw=[render_stripe_sequence_nested_square_frames(p['input'])for p in teachers]
    record={'raw_pair_fits':[out is not None and out==p['output']for(out,_),p in zip(raw,teachers)],'raw_records':[r for _,r in raw]}
    if not all(record['raw_pair_fits']):return False,dict(record,failure='original_teacher_reproduction_failed')
    guarded=[guarded_render(p['input'])for p in teachers];record['teacher_records']=[r for _,r in guarded]
    if any(out is None or out!=p['output']for(out,_),p in zip(guarded,teachers)):
        return False,dict(record,failure='teacher_certificate_failed')
    return True,record

class 帯輪郭教材:
    def __init__(self, 教師群):
        self.適合, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if not self.適合:
            return None, {"failure": "全教師を再現する帯輪郭規約なし"}
        return guarded_render(格子)

    def 記録(self):
        return {"全教師共通符号規約": self.適合}
