"""Pure panel-preserving port-chain composition. No I/O or task identifiers.

Prior: complete internal uniform separator lines partition equal rectangles;
all panels contain one connected monochrome body on a common background.
Opposite boundary occupancy sets are ports. Bodies have no transverse ports.
Every panel is used once in a closed-ended directed chain; whole panels and
separator thickness are retained, without rotation, recoloring, or cropping.
Learned: admission of this schema by exact reproduction of every teacher.
"""
from dataclasses import dataclass
from 接続.ARC2.既存周期組修復 import full_separator_lines
from 接続.ARC2.既存格子操作 import separator_lattice_segments
from 接続.ARC2.既存物体特徴 import color_components


class SearchIncomplete(RuntimeError):
    """Resource interruption, explicitly distinct from semantic HOLD."""


def valid(grid):
    return (isinstance(grid, list) and 1 <= len(grid) <= 30
            and isinstance(grid[0], list) and 1 <= len(grid[0]) <= 30
            and all(isinstance(row, list) and len(row) == len(grid[0])
                    and all(type(v) is int and 0 <= v <= 9 for v in row)
                    for row in grid))


def run_lengths(indices):
    groups = []
    for i in indices:
        if not groups or i != groups[-1][-1] + 1:
            groups.append([])
        groups[-1].append(i)
    return [len(group) for group in groups]


def views(grid):
    if not valid(grid):
        return []
    h, w = len(grid), len(grid[0])
    roles = []
    for sep, lines in full_separator_lines(grid).items():
        rows, cols = lines['rows'], lines['cols']
        if (0 in rows or h-1 in rows or 0 in cols or w-1 in cols):
            continue
        widths = set(run_lengths(rows) + run_lengths(cols))
        if len(widths) != 1:
            continue
        gap = next(iter(widths))
        rs = separator_lattice_segments(h, rows)
        cs = separator_lattice_segments(w, cols)
        panels = [[row[c:d+1] for row in grid[a:b+1]]
                  for a, b in rs for c, d in cs]
        if len(panels) < 2 or len({(len(p), len(p[0])) for p in panels}) != 1:
            continue
        palettes = [{v for row in p for v in row} for p in panels]
        if any(len(s) != 2 or sep in s for s in palettes):
            continue
        for bg in sorted(set.intersection(*palettes)):
            bodies = [next(iter(s - {bg})) for s in palettes]
            if any(len(color_components(p, color)) != 1
                   for p, color in zip(panels, bodies)):
                continue
            ph, pw = len(panels[0]), len(panels[0][0])
            for axis in (0, 1):
                ports = []
                for p in panels:
                    incoming = frozenset(i for i, v in enumerate(
                        p[0] if axis == 0 else [row[0] for row in p]) if v != bg)
                    outgoing = frozenset(i for i, v in enumerate(
                        p[-1] if axis == 0 else [row[-1] for row in p]) if v != bg)
                    transverse = ([row[0] for row in p] + [row[-1] for row in p]
                                  if axis == 0 else p[0] + p[-1])
                    if any(v != bg for v in transverse) or not (incoming or outgoing):
                        break
                    ports.append((incoming, outgoing))
                else:
                    roles.append(dict(separator=sep, background=bg, gap=gap,
                                      panels=panels, axis=axis, ports=ports,
                                      panel_shape=(ph, pw)))
    return roles


def assemble(role, order):
    panels = role['panels']
    ph, pw = role['panel_shape']
    sep, gap = role['separator'], role['gap']
    if role['axis'] == 0:
        out = []
        for i in order:
            if out:
                out.extend([[sep] * pw for _ in range(gap)])
            out.extend([row[:] for row in panels[i]])
    else:
        out = [[] for _ in range(ph)]
        for k, i in enumerate(order):
            for r in range(ph):
                if k:
                    out[r].extend([sep] * gap)
                out[r].extend(panels[i][r])
    return out


def render(grid, max_nodes=100000):
    roles = views(grid)
    if not roles:
        return None, {'status': 'HOLD', 'reason': 'no_eligible_panel_port_view'}
    nodes, answers, certificates = 0, set(), []
    for role in roles:
        ports = role['ports']
        n = len(ports)
        count, local_answers = 0, set()
        def visit(order, used):
            nonlocal nodes, count
            nodes += 1
            if nodes > max_nodes:
                raise SearchIncomplete('panel-chain enumeration resource limit')
            if len(order) == n:
                if ports[order[-1]][1]:
                    return
                output = assemble(role, order)
                if not valid(output):
                    local_answers.add(None)
                else:
                    local_answers.add(tuple(map(tuple, output)))
                count += 1
                return
            for i in range(n):
                if i in used:
                    continue
                incoming = ports[i][0]
                if not order:
                    compatible = not incoming
                else:
                    outgoing = ports[order[-1]][1]
                    compatible = bool(outgoing) and outgoing == incoming
                if compatible:
                    visit(order + [i], used | {i})
        visit([], set())
        if not count or None in local_answers or len(local_answers) != 1:
            return None, {'status': 'HOLD', 'reason': 'eligible_role_failed_or_disagreed',
                          'complete_paths': count, 'complete_outputs': len(local_answers)}
        answers.update(local_answers)
        certificates.append({'separator': role['separator'], 'background': role['background'],
                             'axis': role['axis'], 'gap': role['gap'],
                             'panel_count': n, 'complete_paths': count})
    if len(answers) != 1:
        return None, {'status': 'HOLD', 'reason': 'eligible_roles_disagree'}
    return [list(row) for row in next(iter(answers))], {
        'status': 'OK', 'roles': certificates, 'search_nodes': nodes}


@dataclass(frozen=True)
class Fit:
    schema: str = 'whole_panel_opposite_port_chain'


def fit(teachers, max_nodes=100000):
    if not teachers:
        return None
    for pair in teachers:
        if not valid(pair.get('output')):
            return None
        out, _ = render(pair.get('input'), max_nodes)
        if out is None or out != pair['output']:
            return None
    return Fit()


def predict(model, grid, max_nodes=100000):
    if not isinstance(model, Fit) or model.schema != Fit().schema:
        return None, {'status': 'HOLD', 'reason': 'unfitted_schema'}
    return render(grid, max_nodes)
