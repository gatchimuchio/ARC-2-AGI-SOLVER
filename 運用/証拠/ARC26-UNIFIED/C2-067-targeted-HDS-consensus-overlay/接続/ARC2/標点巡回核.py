"""入力から所有した矢印を疎標点に沿って剛体移動する純粋kernel。

明示prior: 単一矢印と単点群。矢印は反射対称軸の狭い一端が前方。
標点の軸方向到達でその一点だけ消費し、全消費を終端とする。
入力panel群は全行程の等間隔snapshotであり、最後の終端を省いている。
この終端priorは教師整合であって論理的一意ではない。
初panelでのみ所有を決め、以後の接触を再分割しない。
追加prior: actorに一時遮蔽された標点は論理所有を維持し、tip到達だけで消費。
"""
from dataclasses import dataclass
from collections import Counter
from 接続.ARC2.既存物体特徴 import color_components
from 接続.ARC2.既存周期組修復 import full_separator_lines
from 接続.ARC2.既存格子操作 import separator_lattice_segments
from 接続.ARC2.既存疎点転写 import shifted_sparse_point_mask
from 接続.ARC2.矢印到達候補 import valid_grid
from 接続.ARC2.境界点周期候補 import merge_proposals

DIRECTIONS = ((-1, 0), (0, 1), (1, 0), (0, -1))
PROGRAMS = tuple((order, route) for order in ('ascending', 'descending')
                 for route in ('straight_then_turn', 'nearest_nonbackward', 'any_nonbackward'))


class SearchIncomplete(RuntimeError):
    pass


@dataclass(frozen=True)
class Fitted:
    models: tuple


def panel_views(grid):
    """全適格separator所有を保持。二色単panelも同じview型へ。"""
    if not valid_grid(grid):
        return []
    h, w = len(grid), len(grid[0])
    palette = {v for row in grid for v in row}
    views = []
    if len(palette) == 2:
        views.append({'separator': None, 'axis': None, 'panels': [grid]})
    for sep, lines in full_separator_lines(grid).items():
        rows, cols = lines['rows'], lines['cols']
        if bool(rows) == bool(cols):
            continue
        axis = 0 if rows else 1
        positions, length = (rows, h) if rows else (cols, w)
        if 0 in positions or length - 1 in positions:
            continue
        bands = separator_lattice_segments(length, positions)
        panels = ([grid[a:b+1] for a,b in bands] if axis == 0 else
                  [[row[a:b+1] for row in grid] for a,b in bands])
        if len(panels) < 2 or len({(len(p), len(p[0])) for p in panels}) != 1:
            continue
        palettes = [{v for row in p for v in row} for p in panels]
        if any(len(p) != 2 or sep in p for p in palettes) or any(p != palettes[0] for p in palettes):
            continue
        views.append({'separator': sep, 'axis': axis, 'panels': panels})
    return views


def arrow_roles(cells):
    roles = []
    for dr, dc in DIRECTIONS:
        longitudinal = lambda p: p[0]*dr+p[1]*dc
        side = lambda p: p[0]*dc-p[1]*dr
        hi, lo = max(map(longitudinal,cells)), min(map(longitudinal,cells))
        front = [p for p in cells if longitudinal(p) == hi]
        rear = [p for p in cells if longitudinal(p) == lo]
        if hi == lo or len(front) != 1 or len(rear) < 2:
            continue
        tip = front[0]
        lateral = side(tip)
        offsets = frozenset((longitudinal(p)-hi, side(p)-lateral) for p in cells)
        if {(u,-v) for u,v in offsets} != set(offsets):
            continue
        if {u for u,v in offsets} != set(range(lo-hi,1)):
            continue
        roles.append({'tip': tip, 'direction': (dr,dc), 'offsets': tuple(sorted(offsets))})
    return roles


def first_roles(panel):
    counts = Counter(v for row in panel for v in row)
    if len(counts) != 2:
        return []
    # Unique modal background is an explicit input-role prior, never a color constant.
    modes = [v for v,n in counts.items() if n == max(counts.values())]
    if len(modes) != 1:
        return []
    bg = modes[0]; fg = next(v for v in counts if v != bg)
    components = color_components(panel, fg, include_diagonal=True)
    actors = [c for c in components if c['size'] > 1]
    if len(actors) != 1:
        return []
    markers = frozenset(next(iter(c['cells'])) for c in components if c['size'] == 1)
    if not markers:
        return []
    cells = actors[0]['cells']
    return [dict(role, background=bg, foreground=fg, markers=markers,
                 actor_cells=tuple(sorted(cells))) for role in arrow_roles(cells)]


def paint(shape, role, tip, direction, markers):
    dr,dc = direction
    relative = {(u*dr+v*dc, u*dc-v*dr) for u,v in role['offsets']}
    cells = shifted_sparse_point_mask(relative, tip[0], tip[1], *shape)
    if cells is None:
        return None, 'actor_out_of_bounds'
    g = [[role['background']]*shape[1] for _ in range(shape[0])]
    writes = [(r,c,role['foreground']) for group in (cells,markers) for r,c in group]
    output, record = merge_proposals(g, writes)
    return output, record.get('failure')


def next_steps(tip, direction, markers, route):
    choices = []
    for dr,dc in DIRECTIONS:
        if (dr,dc) == (-direction[0],-direction[1]):
            continue
        aligned = []
        for r,c in markers:
            rr,cc = r-tip[0],c-tip[1]
            distance = rr*dr+cc*dc
            if distance > 0 and rr*dc-cc*dr == 0:
                aligned.append((distance,(r,c)))
        if aligned:
            distance, point = min(aligned)
            choices.append((point,(dr,dc),distance))
    if route == 'straight_then_turn':
        straight = [x for x in choices if x[1] == direction]
        return straight or choices
    if route == 'nearest_nonbackward' and choices:
        nearest = min(x[2] for x in choices)
        return [x for x in choices if x[2] == nearest]
    return choices


def walk(panels, role, route, max_nodes):
    """分岐の失敗も完成も全保持。snapshot不一致で枝を黙って除かない。"""
    shape = len(panels[0]),len(panels[0][0])
    n = len(role['markers']); k = len(panels)
    if n % k:
        return None, {'failure':'nonintegral_snapshot_stride', 'marker_count':n, 'panel_count':k}
    stride = n//k
    initial, error = paint(shape,role,role['tip'],role['direction'],role['markers'])
    if error or initial != panels[0]:
        return None, {'failure':error or 'initial_ownership_mismatch'}
    returns = []; nodes = 0
    stack = [(role['tip'],role['direction'],role['markers'],[initial],[])]
    while stack:
        tip,direction,markers,states,steps = stack.pop()
        nodes += 1
        if nodes > max_nodes:
            raise SearchIncomplete('marker traversal node budget exceeded')
        if not markers:
            matches = [states[i*stride] == p for i,p in enumerate(panels)]
            returns.append({'output':states[-1] if all(matches) else None,
                            'failure':None if all(matches) else 'snapshot_mismatch',
                            'steps':steps, 'snapshot_steps':[i*stride for i in range(k)],
                            'snapshot_matches':matches, 'consumed':n})
            continue
        choices = next_steps(tip,direction,markers,route)
        if not choices:
            returns.append({'output':None,'failure':'unreachable_remaining_markers',
                            'steps':steps,'remaining':sorted(markers)})
        for point,new_direction,distance in reversed(choices):
            remaining = markers-{point}
            state,error = paint(shape,role,point,new_direction,remaining)
            step = {'tip':point,'direction':new_direction,'distance':distance,
                    'remaining_count':len(remaining)}
            if error:
                returns.append({'output':None,'failure':error,'steps':steps+[step]})
            else:
                stack.append((point,new_direction,remaining,states+[state],steps+[step]))
    reason = ('retained_walk_failed' if any(r['output'] is None for r in returns)
              else 'retained_walk_disagreement' if any(r['output'] != returns[0]['output'] for r in returns)
              else None)
    return (None if reason else returns[0]['output']), {'failure':reason, 'nodes':nodes,
            'stride':stride, 'terminal':'all_markers_consumed', 'returns':returns}


def render(grid, model, max_nodes=100000):
    if model not in PROGRAMS:
        return None, {'failure':'invalid_model'}
    views = panel_views(grid); returns = []
    for view in views:
        panels = view['panels'] if model[0]=='ascending' else list(reversed(view['panels']))
        roles = first_roles(panels[0])
        if not roles:
            returns.append({'output':None,'failure':'no_initial_actor_role',
                            'separator':view['separator'],'axis':view['axis']})
        for role in roles:
            output,record = walk(panels,role,model[1],max_nodes)
            returns.append({'output':output,'record':record,'role':role,
                            'separator':view['separator'],'axis':view['axis']})
    reason = ('no_panel_view' if not returns else
              'retained_role_failed' if any(r['output'] is None for r in returns) else
              'retained_role_disagreement' if any(r['output'] != returns[0]['output'] for r in returns) else None)
    return (None if reason else returns[0]['output']), {'failure':reason,'returns':returns}


def fit(teachers, max_nodes=100000):
    if (not isinstance(teachers,list) or len(teachers)<2 or
        any(not isinstance(p,dict) or not valid_grid(p.get('input')) or not valid_grid(p.get('output')) for p in teachers)):
        return None, {'complete':True,'failure':'invalid_teachers','returns':[]}
    if len({tuple(map(tuple,p['input'])) for p in teachers}) != len(teachers):
        return None, {'complete':True,'failure':'duplicate_teachers','returns':[]}
    records = []; models = []
    for model in PROGRAMS:
        rows = []
        for p in teachers:
            output,record = render(p['input'],model,max_nodes)
            rows.append({'output':output,'record':record,'exact':output == p['output']})
        exact = all(r['exact'] for r in rows)
        records.append({'model':model,'returns':rows,'all_exact':exact})
        if exact:
            models.append(model)
    return (Fitted(tuple(models)) if models else None), {'complete':True,
        'failure':None if models else 'no_all_teacher_model','models':models,'returns':records}


def predict(grid, fitted, max_nodes=100000):
    if (not isinstance(fitted,Fitted) or not fitted.models or
        fitted.models != tuple(p for p in PROGRAMS if p in fitted.models)):
        return None, {'failure':'invalid_fitted_state','returns':[]}
    rows = []
    for model in fitted.models:
        output,record = render(grid,model,max_nodes)
        rows.append({'model':model,'output':output,'record':record})
    reason = ('retained_model_failed' if any(r['output'] is None for r in rows) else
              'retained_model_disagreement' if any(r['output'] != rows[0]['output'] for r in rows) else None)
    return (None if reason else rows[0]['output']), {'failure':reason,'returns':rows}
