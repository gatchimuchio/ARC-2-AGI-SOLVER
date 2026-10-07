"""Prospective finite policy: column compaction and all bounded lateral spills.

Fixed walls are every color except fitted background/material. Material can
pass laterally through other material, but never through a fixed wall. Both
nearest gaps beside a maximal occupied run below each material cell are tried.
No teacher output enters this function. No branch count or iteration cap.
"""
from collections import Counter, deque
from 接続.ARC2.距離回収候補 import render_prepared


def compact(state, walls, height, width):
    result = set()
    for c in range(width):
        stops = [-1] + [r for r in range(height) if (r, c) in walls] + [height]
        for top, bottom in zip(stops, stops[1:]):
            count = sum((r, c) in state for r in range(top + 1, bottom))
            result.update((r, c) for r in range(bottom - count, bottom))
    assert len(result) == len(state) and not result & walls
    return frozenset(result)


def settle(grid, background, material, progress=None):
    height, width = len(grid), len(grid[0])
    canvas = {(r, c) for r in range(height) for c in range(width)}
    source = frozenset((r, c) for r, row in enumerate(grid)
                       for c, value in enumerate(row) if value == material)
    walls = frozenset((r, c) for r, row in enumerate(grid)
                      for c, value in enumerate(row) if value not in (background, material))
    assert source and material != background
    static = {(r, c): grid[r][c] for r, c in walls}
    report = {'status': 'incomplete', 'states_discovered': 0,
              'states_completed': 0, 'legal_spills': 0, 'checked_actions': 0,
              'initial_material_count': len(source), 'terminal_states': [],
              'potential_upper_bound': len(source) * (height - 1)}
    if progress is not None:
        progress.update(report)

    def draw(state):
        out = [[background] * width for _ in range(height)]
        for (r, c), value in static.items():
            out[r][c] = value
        for r, c in state:
            out[r][c] = material
        return out

    def verify_action(before, after):
        erased, new = before - after, after - before
        assert len(erased) == len(new)
        assert not before & walls and not after & walls
        assert (before | after | walls) <= canvas
        inp = draw(before)
        # Diagnostic-only seed; it does not participate in the action.
        parsed = {'cells': {'source': before, 'wall': walls},
                  'target': new, 'seed': min(before)}
        out, record = render_prepared(
            inp, {'background': background, 'source': material},
            {'ranking': 'nearest', 'overflow': 'require_all_reachable',
             'source_action': 'erase_to_background'},
            parsed, {cell: 0 for cell in erased}, sorted(new))
        assert out == draw(after), record
        assert Counter(v for row in out for v in row) == Counter(v for row in grid for v in row)
        assert all(out[r][c] == value for (r, c), value in static.items())
        assert all(out[r][c] == inp[r][c] for r, c in canvas - erased - new)
        report['checked_actions'] += 1
        if 'first_action_return' not in report:
            report['first_action_return'] = [out, record]

    initial = compact(source, walls, height, width)
    verify_action(source, initial)
    assert sum(r for r, c in initial) >= sum(r for r, c in source)
    seen, queue, terminals = {initial}, deque([initial]), set()
    while queue:
        state = queue.popleft()
        occupied, children = walls | state, set()
        potential = sum(r for r, c in state)
        for r, c in sorted(state):
            if r + 1 >= height:
                continue
            assert (r + 1, c) in occupied
            # Same maximal horizontal run scan used by existing gravity route;
            # occupied here includes both fixed walls and conserved material.
            left = right = c
            while left > 0 and (r + 1, left - 1) in occupied:
                left -= 1
            while right + 1 < width and (r + 1, right + 1) in occupied:
                right += 1
            for gap in (left - 1, right + 1):
                if not 0 <= gap < width:
                    continue
                if any((r, x) in walls for x in range(min(c, gap), max(c, gap) + 1)):
                    continue
                assert (r + 1, gap) not in occupied
                assert (r, gap) not in occupied
                moved = state - {(r, c)} | {(r, gap)}
                following = compact(moved, walls, height, width)
                assert sum(rr for rr, cc in following) > potential
                verify_action(state, following)
                children.add(following)
                report['legal_spills'] += 1
        if not children:
            terminals.add(state)
        for following in sorted(children, key=lambda s: sorted(s)):
            if following not in seen:
                seen.add(following)
                queue.append(following)
        report['states_completed'] += 1
        report['states_discovered'] = len(seen)
        report['terminal_count_so_far'] = len(terminals)
        if progress is not None:
            progress.update(report)
    terminal_states = sorted(terminals, key=lambda s: sorted(s))
    report.update(status='complete', search_complete=True,
                  terminal_states=[sorted(state) for state in terminal_states],
                  terminal_grids=[draw(state) for state in terminal_states],
                  terminal_count=len(terminals),
                  all_action_ownership_and_count_checks=True,
                  consensus=len(terminals) == 1,
                  outcome='UNIQUE' if len(terminals) == 1 else 'HOLD_disagreement')
    if progress is not None:
        progress.update(report)
    return (draw(terminal_states[0]) if len(terminals) == 1 else None), report
