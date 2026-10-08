"""Existing open-frame ownership and ray packing with explicit cell conservation."""
from collections import Counter
from 接続.ARC2.既存領域転写 import mixed_region_dicts_for_grid
from 接続.ARC2.既存枠計数 import color_components, render_frame_component_count_slots
from 接続.ARC2.既存凡例穴対応 import clone_grid

DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))

def frame_views(grid, bg):
    h, w = len(grid), len(grid[0])
    views = []
    for color in sorted({v for row in grid for v in row} - {bg}):
        mask = [[1 if v == color else 0 for v in row] for row in grid]
        for comp in mixed_region_dicts_for_grid(mask, 0, True):
            cells = set(comp['cells'])
            if len(cells) < 3:
                continue
            for dr, dc in DIRECTIONS:
                # u increases behind the outward-facing tip; v is transverse.
                uv = {p: (-p[0]*dr-p[1]*dc, -p[0]*dc+p[1]*dr) for p in cells}
                u0, u1 = min(u for u,v in uv.values()), max(u for u,v in uv.values())
                slices = {u: sorted(v for uu,v in uv.values() if uu == u) for u in range(u0,u1+1)}
                if len(slices[u0]) != 1 or any(not s for s in slices.values()):
                    continue
                lo = hi = slices[u0][0]
                tip = next(p for p in cells if uv[p][0] == u0)
                interior = set(); opened = False; invalid = False
                envelope = []
                for u, vs in slices.items():
                    newlo, newhi = min(lo,min(vs)), max(hi,max(vs))
                    lo, hi = newlo, newhi
                    whole = set(range(lo,hi+1))
                    actual = set(vs)
                    missing = set(range(lo+1,hi)) - actual
                    if missing:
                        opened = True
                    if opened:
                        left=lo
                        while left in actual and left <= hi: left+=1
                        right=hi
                        while right in actual and right >= lo: right-=1
                        if any(left <= v <= right for v in actual) or not missing:
                            invalid = True; break
                    envelope.append((u,lo,hi))
                    if opened:
                        for v in sorted(missing):
                            # Orthogonal inverse of the canonical coordinate map.
                            r, c = -dr*u-dc*v, -dc*u+dr*v
                            if 0 <= r < h and 0 <= c < w:
                                interior.add((r,c))
                if invalid or not opened or not interior:
                    continue
                payload = {p for p in interior if grid[p[0]][p[1]] != bg}
                if not payload or any(grid[r][c] == color for r,c in payload):
                    continue
                payload_colors = {grid[r][c] for r,c in payload}
                if len(payload_colors) != 1:
                    continue
                views.append(dict(color=color,cells=cells,interior=interior,payload=payload,
                                  payload_color=next(iter(payload_colors)),tip=tip,direction=(dr,dc),envelope=envelope))
    return views

def render(grid, count_mode='pixels', ownership='visible_envelope'):
    frequencies=Counter(v for row in grid for v in row)
    modes=[v for v,n in frequencies.items() if n==max(frequencies.values())]
    if len(modes)!=1:
        return None, {'failure':'background_tie'}
    bg=modes[0]; views=frame_views(grid,bg)
    if not views:
        return None, {'failure':'no_open_frame'}
    # All recognised frames participate; no successful-view subset selection.
    owners={}; records=[]
    for i,view in enumerate(views):
        for p in view['cells']|view['payload']:
            if p in owners:
                return None, {'failure':'frame_or_payload_ownership_ambiguity'}
            owners[p]=i
        payload=view['payload']; color=view['payload_color']
        if any(set(comp['cells']) & payload and not set(comp['cells']) <= payload
               for comp in color_components(grid,color)):
            return None, {'failure':'partial_payload_component'}
        mask=[[color if (r,c) in payload else bg for c in range(len(grid[0]))] for r in range(len(grid))]
        if count_mode in ('axis_slices', 'transverse_slices'):
            dr, dc = view['direction']
            if count_mode == 'transverse_slices': dr, dc = -dc, dr
            units = {}
            for r, c in sorted(payload):
                units.setdefault(r*dr+c*dc, []).append((r,c))
            view['projected_units'] = [{'coordinate': k, 'cells': units[k]} for k in sorted(units)]
            count = len(units)
        elif count_mode=='pixels': count=len(payload)
        elif count_mode=='components4': count=len(color_components(mask,color))
        elif count_mode=='components8': count=len(mixed_region_dicts_for_grid(mask,bg,True))
        else: return None, {'failure':'unknown_count_mode'}
        if ownership=='strict_paired':
            # Earlier direct interval composition: missing arm has no ownership.
            dr,dc=view['direction']; frame=view['cells']
            for r,c in payload:
                if dr:
                    witnesses=[cc for rr,cc in frame if rr==r]
                    paired=witnesses and min(witnesses)<c<max(witnesses)
                else:
                    witnesses=[rr for rr,cc in frame if cc==c]
                    paired=witnesses and min(witnesses)<r<max(witnesses)
                if not paired:return None,{'failure':'missing_same_slice_arm','cell':(r,c)}
        elif ownership!='visible_envelope':return None,{'failure':'unknown_ownership'}
        records.append(dict(view,count=count))
    output=clone_grid(grid); changes={}; latent=0
    for view in records:
        for p in view['payload']:changes[p]=bg
    for view in records:
        dr,dc=view['direction'];r,c=view['tip']
        view['ray_cells']=[(r+dr*k,c+dc*k) for k in range(1,view['count']+1)]
        view['visible_ray_cells']=[p for p in view['ray_cells'] if 0<=p[0]<len(grid) and 0<=p[1]<len(grid[0])]
        view['outside_ray_cells']=[p for p in view['ray_cells'] if p not in view['visible_ray_cells']]
        for step in range(1,view['count']+1):
            p=(r+dr*step,c+dc*step)
            if not (0<=p[0]<len(grid) and 0<=p[1]<len(grid[0])):
                latent += 1
                continue # Rasterise full count ray, then crop to the visible canvas.
            if grid[p[0]][p[1]]!=bg or p in changes:
                return None,{'failure':'count_ray_collision'}
            changes[p]=view['payload_color']
    for (r,c),value in changes.items():output[r][c]=value
    return output,{'failure':None,'background':bg,'frames':records,'latent_ray_cells':latent}

def fit(teachers):
    retained=[]; attempts=[]
    for mode in ('pixels','components4','components8','axis_slices','transverse_slices'):
        results=[render(pair['input'],mode) for pair in teachers]
        exact=[out==pair['output'] and rec['failure'] is None for (out,rec),pair in zip(results,teachers)]
        attempts.append({'mode':mode,'exact':exact,'results':results})
        if teachers and all(exact):retained.append(mode)
    return retained,attempts

def apply_retained(grid,retained):
    results=[render(grid,mode) for mode in retained]
    if not retained or any(rec['failure'] for out,rec in results):
        return None,{'failure':'retained_failure_or_empty','results':results}
    if any(out!=results[0][0] for out,rec in results):
        return None,{'failure':'retained_disagreement','results':results}
    return results[0][0],{'failure':None,'results':results}



def fit_payload_conservation(teachers):
    """Explicit prior: every owned colored cell is one transported unit.

    Full emitted mass equals erased payload mass before canvas crop. This is
    an inductive prior, not identification from censored teacher outputs.
    Raw count-model ambiguity remains in diagnostics. No query/score enters.
    """
    raw, attempts = fit(teachers)
    retained = ['pixels'] if 'pixels' in raw else []
    return retained, {'raw_retained': raw, 'attempts': attempts,
                      'retained': retained,
                      'prior': 'one_owned_cell_one_transported_unit_before_crop',
                      'identification': 'explicit_prior_not_logically_unique'}
