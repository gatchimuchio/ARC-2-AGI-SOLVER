"""Prospective foreach-command grammar, not an equivalence to frozen095.

Every exposed complete strip is a command. Recursively remove a command and
its separator, until exactly one irreducible canvas remains. Keep every complete
partition and every role within each command; never choose by action success.
The original095 source, action, strict fitting and old disagreement are unchanged.
"""
from functools import lru_cache
from . import 関係枠命令配置 as old

strict = old.strict
fit, act, MODELS, D4 = old.fit, old.act, old.MODELS, old.D4


def _shift(box, origin):
    r, c = origin
    return (box[0]+r, box[1]+c, box[2]+r, box[3]+c)


def complete_cuts(grid, origin=(0, 0)):
    """Reuse frozen parsers, retaining all exact strip roles and full ownership."""
    h, w = len(grid), len(grid[0])
    strict_roles, strict_record = strict.parse(grid)
    groups = {}
    for role in strict_roles:
        s = role['separator']
        key = ((0, 0, h-1, s-1), (0, s+1, h-1, w-1))
        group = groups.setdefault(key, {'roles': [], 'parser': 'strict',
                                       'separator_bbox': (0, s, h-1, s)})
        group['roles'].append(role)
    roles, relational_record = old.relational_parse(grid)
    for view in relational_record.get('view_probes', []):
        key = (tuple(view['instruction_bbox']), tuple(view['canvas_bbox']))
        indices = [entry['role_index'] for entry in view.get('background_returns', [])
                   if 'role_index' in entry]
        if not indices:
            continue
        p = view['position']
        sep = (p, 0, p, w-1) if view['axis'] == 'row' else (0, p, h-1, p)
        group = groups.setdefault(key, {'roles': [], 'parser': 'relational',
                                        'separator_bbox': sep})
        if group['parser'] == 'strict':
            group['parser'] = 'strict_and_relational'
        for i in indices:
            if roles[i] not in group['roles']:
                group['roles'].append(roles[i])
    cuts = []
    for (instruction, remainder), group in groups.items():
        cuts.append({**group, 'instruction_bbox': _shift(instruction, origin),
                     'remainder_bbox': _shift(remainder, origin),
                     'separator_bbox': _shift(group['separator_bbox'], origin)})
    return cuts


def partitions(grid):
    if not strict.valid_grid(grid):
        return [], {'complete': True, 'failure': 'invalid_grid'}
    h, w = len(grid), len(grid[0])
    probes = []

    @lru_cache(None)
    def visit(box):
        region = strict.crop_bbox(grid, box)
        cuts = complete_cuts(region, box[:2])
        probes.append({'bbox': box, 'command_bboxes': [c['instruction_bbox'] for c in cuts]})
        if not cuts:
            return ({'canvas_bbox': box, 'commands': []},)
        # A complete partition must own every exposed complete command strip.
        required = {cut['instruction_bbox'] for cut in cuts}
        results = []
        for cut in cuts:
            for child in visit(cut['remainder_bbox']):
                commands = [cut] + child['commands']
                if not required <= {command['instruction_bbox'] for command in commands}:
                    continue
                results.append({'canvas_bbox': child['canvas_bbox'], 'commands': commands})
        return tuple(results)

    candidates = visit((0, 0, h-1, w-1))
    distinct = {}
    for partition in candidates:
        if not partition['commands']:
            continue
        signature = (partition['canvas_bbox'], tuple(sorted(
            (c['instruction_bbox'], c['separator_bbox']) for c in partition['commands'])))
        distinct.setdefault(signature, partition)
    result = list(distinct.values())
    # Recheck literal whole-board coverage, including separators and canvas.
    board = {(r, c) for r in range(h) for c in range(w)}
    for partition in result:
        owned = set()
        boxes = [partition['canvas_bbox']]
        boxes += [c[k] for c in partition['commands']
                  for k in ('instruction_bbox', 'separator_bbox')]
        for r0, c0, r1, c1 in boxes:
            cells = {(r, c) for r in range(r0, r1+1) for c in range(c0, c1+1)}
            if owned & cells:
                raise RuntimeError('partition_ownership_overlap')
            owned |= cells
        if owned != board:
            raise RuntimeError('partition_ownership_incomplete')
    return result, {'complete': True, 'partition_count': len(result), 'inventory': probes}


def command_writes(command, canvas, model):
    """Get the unchanged action's actual writes, including idempotent writes."""
    returns = []
    for role in command['roles']:
        out, record = strict.act({**role, 'canvas': canvas}, model)
        bg = role['background']
        blank = [[bg] * len(canvas[0]) for _ in canvas]
        footprint, footprint_record = strict.act({**role, 'canvas': blank}, model)
        writes = None
        if out is not None and footprint is not None:
            writes = {(r, c): value for r, row in enumerate(footprint)
                      for c, value in enumerate(row) if value != bg}
            reconstructed = [row[:] for row in canvas]
            for (r, c), value in writes.items():
                reconstructed[r][c] = value
            if reconstructed != out or len(writes) != record['painted_cells']:
                raise RuntimeError('unchanged_action_footprint_mismatch')
        written = None if writes is None else [[r, c, value] for (r, c), value in sorted(writes.items())]
        returns.append({'return': out, 'writes': written, 'record': record,
                        'footprint_record': footprint_record})
    record = {'role_returns': returns, 'instruction_bbox': command['instruction_bbox']}
    if not returns or any(r['writes'] is None for r in returns):
        return None, {**record, 'failure': 'command_role_failed'}
    if any(r['writes'] != returns[0]['writes'] for r in returns[1:]):
        return None, {**record, 'failure': 'command_role_disagreement'}
    return {(r, c): value for r, c, value in returns[0]['writes']}, record


def render_partition(grid, partition, model):
    canvas = strict.crop_bbox(grid, partition['canvas_bbox'])
    returns = [command_writes(command, canvas, model) for command in partition['commands']]
    record = {'canvas_bbox': partition['canvas_bbox'], 'command_returns': [r[1] for r in returns]}
    if any(writes is None for writes, _ in returns):
        return None, {**record, 'failure': 'command_failed'}
    merged = {}
    conflicts = set()
    for writes, _ in returns:
        for cell, color in writes.items():
            if cell in merged and merged[cell] != color:
                conflicts.add(cell)
            merged[cell] = color
    if conflicts:
        return None, {**record, 'failure': 'command_write_conflict',
                      'conflicts': sorted(conflicts)}
    out = [row[:] for row in canvas]
    for (r, c), color in merged.items():
        out[r][c] = color
    return out, {**record, 'written_cells': len(merged)}


def render(grid, model):
    views, record = partitions(grid)
    returns = [{'return': out, 'record': rec} for view in views
               for out, rec in [render_partition(grid, view, model)]]
    record.update(model=model, partition_returns=returns)
    if not returns:
        return None, {**record, 'failure': 'no_complete_partition'}
    if any(r['return'] is None for r in returns):
        return None, {**record, 'failure': 'partition_failed'}
    if any(r['return'] != returns[0]['return'] for r in returns[1:]):
        return None, {**record, 'failure': 'partition_disagreement'}
    return returns[0]['return'], record


def consensus(grid, models):
    returns = [{'model': model, 'return': out, 'record': rec}
               for model in models for out, rec in [render(grid, model)]]
    record = {'complete': True, 'model_returns': returns}
    if not returns:
        return None, {**record, 'failure': 'no_models'}
    if any(r['return'] is None for r in returns):
        return None, {**record, 'failure': 'retained_model_failed'}
    if any(r['return'] != returns[0]['return'] for r in returns[1:]):
        return None, {**record, 'failure': 'retained_model_disagreement'}
    return returns[0]['return'], record
