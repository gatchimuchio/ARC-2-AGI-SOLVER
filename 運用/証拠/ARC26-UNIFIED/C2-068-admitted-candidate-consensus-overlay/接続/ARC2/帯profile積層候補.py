"""Frozen input-only profile-stack grammar; six semantic function ASTs unchanged."""
from __future__ import annotations
from collections import Counter
from .既存穴充填 import _orthogonal_components as components
from .既存格子操作 import transform_grid_by_name as transform
from .標点組立教材 import valid_grid, oriented_cells as normalize_cells

def gridkey(grid):
    return tuple(map(tuple, grid))

def profile(cells):
    r0, r1 = min(r for r,c in cells), max(r for r,c in cells)
    c0, c1 = min(c for r,c in cells), max(c for r,c in cells)
    top, bottom = [], []
    holes = []
    for c in range(c0, c1+1):
        rows = {r for r,k in cells if k == c}
        if not rows:
            holes.append({'column': c, 'failure': 'empty_column'})
            continue
        lo, hi = min(rows), max(rows)
        top.append(lo)
        bottom.append(hi)
        missing = sorted(set(range(lo,hi+1))-rows)
        if missing:
            holes.append({'column': c, 'missing_normal_cells': missing})
    return {'bbox': [r0,c0,r1,c1], 'width': c1-c0+1, 'top': top, 'bottom': bottom, 'holes': holes}

def enumerate_roles(grid):
    """Every background/axis/band role is determined before any packing."""
    roles, diagnostics = [], []
    for axis in (0, 1):
        g = transform(grid, 'identity' if axis == 0 else 'transpose')
        h, w = len(g), len(g[0])
        colored = []
        for color in sorted({v for row in g for v in row}):
            for cells in sorted(components({(r,c) for r,row in enumerate(g) for c,v in enumerate(row) if v == color}), key=lambda c: sorted(c)):
                colored.append({'color': color, 'cells': cells, **profile(cells)})
        for bg in sorted({v for row in g for v in row}):
            foreground = [o for o in colored if o['color'] != bg]
            observed = {(r,c) for r,row in enumerate(g) for c,v in enumerate(row) if v != bg}
            for bi, band in enumerate(foreground):
                failures = []
                if band['bbox'][1] != 0 or band['bbox'][3] != w-1:
                    failures.append('not_spanning_opposite_tangent_edges')
                if band['holes']:
                    failures.append('band_not_normal_convex')
                if band['top'] and (min(band['top']) <= 0 or max(band['bottom']) >= h-1):
                    failures.append('band_not_strictly_interior_in_normal_axis')
                ps = [o for i,o in enumerate(foreground) if i != bi]
                if not ps:
                    failures.append('empty_piece_inventory')
                invalid_pieces = [{'index': i, 'bbox': p['bbox'], 'holes': p['holes'], 'width': p['width']} for i,p in enumerate(ps) if p['holes'] or p['width'] >= w]
                if invalid_pieces:
                    failures.append('nonband_piece_outside_convex_narrow_inventory')
                owners = Counter(q for o in foreground for q in o['cells'])
                if set(owners) != observed or any(v != 1 for v in owners.values()):
                    failures.append('foreground_ownership_failed')
                diag = {'axis': axis, 'background': bg, 'band_index': bi, 'band_color': band['color'], 'band_bbox': band['bbox'], 'band_area': len(band['cells']), 'failures': failures, 'invalid_pieces': invalid_pieces}
                diagnostics.append(diag)
                if failures:
                    continue
                pieces = []
                for i,p in enumerate(ps):
                    local = normalize_cells(tuple((r,c,p['color']) for r,c in p['cells']), 0)
                    cells = {(r,c) for r,c,_ in local}
                    pieces.append({'id': i, 'color': p['color'], 'source_bbox': p['bbox'], 'source_cells': sorted(p['cells']), 'cells': cells, **profile(cells)})
                roles.append({'role_id': len(roles), 'axis': axis, 'background': bg, 'shape': [h,w], 'band': band, 'pieces': pieces, 'source': g})
                diag['role_id'] = roles[-1]['role_id']
    return roles, diagnostics

def public_piece(p):
    return {k: (sorted(v) if isinstance(v,set) else v) for k,v in p.items()}

def solve_role(role):
    h,w = role['shape']
    band, pieces = role['band'], role['pieces']
    record = {'role_id': role['role_id'], 'axis': role['axis'], 'background': role['background'], 'band': public_piece(band), 'pieces': [public_piece(p) for p in pieces], 'slots': [], 'chain_prefixes': [], 'chains': [], 'cover_trials': [], 'arrangements': []}
    chains = []

    def extend(side, col, width, facing, chosen, occupied, placements, slot_id):
        # facing is the absolute exposed normal profile of the band/last piece.
        for p in pieces:
            if p['width'] != width or p['id'] in chosen:
                continue
            inward = p['top'] if side == 1 else p['bottom']
            offsets = [a + side - b for a,b in zip(facing,inward)]
            step = {'slot_id': slot_id, 'prefix_piece_ids': list(chosen), 'next_piece_id': p['id'], 'offsets': offsets}
            record['chain_prefixes'].append(step)
            if len(set(offsets)) != 1:
                step['failure'] = 'profile_mismatch'
                continue
            row = offsets[0]
            cells = {(row+r,col+c) for r,c in p['cells']}
            placement = {'piece_id': p['id'], 'origin': [row,col], 'translation': [row-p['source_bbox'][0],col-p['source_bbox'][1]], 'cells': sorted(cells)}
            step['placement'] = placement
            if any(not (0 <= r < h and 0 <= c < w) for r,c in cells):
                step['failure'] = 'out_of_bounds'
                continue
            if cells & band['cells']:
                step['failure'] = 'band_collision'
                step['witness_cells'] = sorted(cells & band['cells'])
                continue
            if cells & occupied:
                step['failure'] = 'chain_collision'
                step['witness_cells'] = sorted(cells & occupied)
                continue
            next_chosen = chosen + [p['id']]
            next_placements = placements + [placement]
            next_cells = occupied | cells
            outward = [row+v for v in (p['bottom'] if side == 1 else p['top'])]
            step['outward_profile'] = outward
            step['terminal_flat'] = len(set(outward)) == 1
            if step['terminal_flat']:
                chain = {'chain_id': len(chains), 'slot_id': slot_id, 'side': side, 'tangent_origin': col, 'width': width, 'piece_ids': next_chosen, 'placements': next_placements, 'cells': sorted(next_cells)}
                chains.append(chain)
            # Do not stop at a flat endpoint or the first complete chain.
            extend(side,col,width,outward,next_chosen,next_cells,next_placements,slot_id)

    for side in (-1, 1):
        boundary = band['top'] if side == -1 else band['bottom']
        for width in sorted({p['width'] for p in pieces}):
            for col in range(w-width+1):
                facing = boundary[col:col+width]
                slot = {'slot_id': len(record['slots']), 'side': side, 'width': width, 'tangent_origin': col, 'facing_profile': facing}
                record['slots'].append(slot)
                if len(set(facing)) == 1:
                    slot['failure'] = 'flat_root_profile'
                    continue
                extend(side,col,width,facing,[],set(),[],slot['slot_id'])
    record['chains'] = chains
    all_ids = set(range(len(pieces)))

    def cover(start, used, occupied, chosen):
        if used == all_ids:
            output = [[role['background']]*w for _ in range(h)]
            for r,c in band['cells']:
                output[r][c] = band['color']
            for cid in chosen:
                for placement in chains[cid]['placements']:
                    p = pieces[placement['piece_id']]
                    for r,c in placement['cells']:
                        output[r][c] = p['color']
            if Counter(v for row in output for v in row) != Counter(v for row in role['source'] for v in row):
                raise RuntimeError('internal_conservation_violation')
            final = output if role['axis'] == 0 else transform(output, 'transpose')
            record['arrangements'].append({'chain_ids': chosen, 'grid': final, 'conservation': True, 'foreground_ownership': True})
            return
        for ci in range(start,len(chains)):
            chain = chains[ci]
            ids, cells = set(chain['piece_ids']), set(map(tuple,chain['cells']))
            trial = {'prefix_chain_ids': chosen, 'next_chain_id': ci}
            record['cover_trials'].append(trial)
            if ids & used:
                trial['failure'] = 'piece_reuse'
                trial['witness_piece_ids'] = sorted(ids & used)
                continue
            if cells & occupied:
                trial['failure'] = 'destination_collision'
                trial['witness_cells'] = sorted(cells & occupied)
                continue
            cover(ci+1,used|ids,occupied|cells,chosen+[ci])
    cover(0,set(),set(),[])
    used_by_any_chain = {i for chain in chains for i in chain['piece_ids']}
    record['uncovered_piece_witnesses'] = sorted(all_ids-used_by_any_chain)
    record['search_complete'] = True
    record['domain_counts'] = {'slots': len(record['slots']), 'tested_chain_extensions': len(record['chain_prefixes']), 'terminal_chains': len(chains), 'cover_extensions': len(record['cover_trials']), 'complete_arrangements': len(record['arrangements'])}
    return record

def infer(grid):
    if not valid_grid(grid):
        return None, {'status': 'HOLD', 'failure': 'invalid_arc_grid', 'search_complete': True}
    roles, diagnostics = enumerate_roles(grid)
    record = {'status': None, 'role_diagnostics': diagnostics, 'roles': [], 'search_complete': False}
    if not roles:
        return None, {**record, 'status': 'HOLD', 'failure': 'no_structural_band_role', 'search_complete': True}
    grids = {}
    for role in roles:
        rr = solve_role(role)
        record['roles'].append(rr)
        for arrangement in rr['arrangements']:
            grids[gridkey(arrangement['grid'])] = arrangement['grid']
    record['search_complete'] = True
    record['unique_grid_count'] = len(grids)
    record['full_grids'] = list(grids.values())
    failed_roles = [r['role_id'] for r in record['roles'] if not r['arrangements']]
    if failed_roles:
        return None, {**record, 'status': 'HOLD', 'failure': 'role_has_no_complete_inventory_arrangement', 'failed_roles': failed_roles}
    if len(grids) != 1:
        return None, {**record, 'status': 'HOLD', 'failure': 'complete_grids_disagree'}
    return next(iter(grids.values())), {**record, 'status': 'UNIQUE'}
