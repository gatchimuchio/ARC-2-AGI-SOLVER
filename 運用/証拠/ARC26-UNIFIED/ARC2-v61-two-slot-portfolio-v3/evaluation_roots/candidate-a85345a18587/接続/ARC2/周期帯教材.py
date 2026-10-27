"""Certify all teacher-fitting periodic-band models; emit only the old minimum."""
from collections import Counter
from copy import deepcopy
from . import 既存周期帯 as old
def fit_models(pairs):
    if len(pairs)<2:return []
    fills=[]
    for p in pairs:
        new=set(sum(p['output'],[]))-set(sum(p['input'],[]))
        if len(new)!=1:return []
        fills.append(next(iter(new)))
    if len(set(fills))!=1:return []
    fill=fills[0];parsed,_=old._periodic_marker_band_parse(pairs[0]['input'])
    if parsed is None:return []
    marker=parsed['marker_color']
    if any(old._periodic_marker_band_parse(p['input'],marker)[0] is None for p in pairs[1:]):return []
    models=[]
    for period in range(2,min(16,max(len(p['input'])for p in pairs)+1)):
        schedule=old._periodic_marker_band_fit_schedule(pairs,fill,period,marker)
        if not schedule:continue
        policy={'fill_color':fill,'marker_color':marker,'period':period,'schedule':schedule}
        outputs=[old._periodic_marker_band_render(p['input'],policy) for p in pairs]
        if all(o is not None and o==p['output']for(o,_),p in zip(outputs,pairs)):
            models.append({'policy':policy,'records':[r for _,r in outputs]})
    return models


def valid_grid(grid):
    return (isinstance(grid, list) and 1 <= len(grid) <= 30
            and isinstance(grid[0], list) and 1 <= len(grid[0]) <= 30
            and all(isinstance(row, list) and len(row) == len(grid[0])
                    and all(type(v) is int and 0 <= v <= 9 for v in row) for row in grid))


def certify_render(grid, model):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_arc_grid'}
    counts = Counter(v for row in grid for v in row)
    if sum(n == max(counts.values()) for n in counts.values()) != 1:
        return None, {'failure': 'background_tie'}
    policy = model['policy']
    fill, marker, period = policy['fill_color'], policy['marker_color'], policy['period']
    if fill in counts:
        return None, {'failure': 'learned_fill_is_not_new'}
    parsed, rejection = old._periodic_marker_band_parse(grid, marker)
    if parsed is None:
        return None, {'failure': 'known_marker_boundary_unresolved', 'source_record': rejection}
    background = parsed['background']
    if len({background, marker, fill}) != 3:
        return None, {'failure': 'role_colors_alias'}
    axis, direction = parsed['axis'], parsed['direction']
    marker_index = parsed['marker_row'] if axis == 'row' else parsed['marker_col']
    band_start = parsed['band_col0'] if axis == 'row' else parsed['band_row0']
    band_end = parsed['band_col1'] if axis == 'row' else parsed['band_row1']
    axis_length = len(grid) if axis == 'row' else len(grid[0])
    span_length = len(grid[0]) if axis == 'row' else len(grid)
    expected = [row[:] for row in grid]
    band_cells, payload_cells, changed_rows, event_count = set(), set(), [], 0
    for index in range(axis_length):
        distance = (index - marker_index) * direction
        if distance < 0:
            return None, {'failure': 'axis_coverage_incomplete'}
        residue = distance % period
        action = policy['schedule'].get(residue)
        evidence = model['evidence'].get(residue)
        if action is None or evidence is None or not evidence['band_teachers']:
            return None, {'failure': 'unobserved_band_action', 'residue': residue}
        band_value = {'marker': marker, 'background': background, 'fill': fill}.get(action['band'])
        if band_value is None:
            return None, {'failure': 'invalid_band_action'}
        row_changed = 0
        for span in range(span_length):
            row, col = (index, span) if axis == 'row' else (span, index)
            before = grid[row][col]
            if band_start <= span <= band_end:
                band_cells.add((row, col))
                after = band_value
            elif before not in (background, marker):
                payload_cells.add((row, col))
                if not evidence['payload_teachers']:
                    return None, {'failure': 'unobserved_outside_payload_action', 'residue': residue}
                after = fill if action['recolor'] else before
            else:
                after = before
            expected[row][col] = after
            row_changed += before != after
        if row_changed:
            changed_rows.append({'axis_index': index, 'distance': distance, 'residue': residue,
                                 'band_action': action['band'], 'recolor': action['recolor'],
                                 'changed_cell_count': row_changed})
            event_count += row_changed
    if len(band_cells) != axis_length * (band_end - band_start + 1):
        return None, {'failure': 'band_coverage_incomplete'}
    output, source_record = old._periodic_marker_band_render(grid, policy)
    if output is None:
        return None, {'failure': 'source_no_candidate', 'source_record': source_record}
    expected_record = {'renderer_case': 'periodic_marker_band_projector',
        'periodic_marker_band_background_color': background,
        'periodic_marker_band_marker_color': marker,
        'periodic_marker_band_fill_color': fill,
        'periodic_marker_band_axis': axis,
        'periodic_marker_band_marker_axis_index': marker_index,
        'periodic_marker_band_span': [band_start, band_end],
        'periodic_marker_band_period': period,
        'periodic_marker_band_schedule': policy['schedule'],
        'periodic_marker_band_event_count': event_count,
        'periodic_marker_band_changed_rows': changed_rows}
    if output != expected or source_record != expected_record:
        return None, {'failure': 'source_output_or_record_disagrees'}
    return output, {'source_record': source_record, 'certificate': {
        'band_cells': len(band_cells), 'outside_payload_cells': len(payload_cells),
        'outside_background_marker_cells_preserved': len(grid) * len(grid[0]) - len(band_cells) - len(payload_cells)}}


def guarded_render(grid, fitted):
    if fitted is None or not fitted['models']:
        return None, {'failure': 'no_teacher_fitted_models'}
    candidates, records = [], []
    for model in fitted['models']:
        output, record = certify_render(grid, model)
        if output is None:
            return None, {'failure': 'retained_model_unresolved',
                          'period': model['policy']['period'], 'reason': record}
        candidates.append(output)
        records.append(record)
    if any(output != candidates[0] for output in candidates[1:]):
        return None, {'failure': 'retained_model_grids_disagree'}
    minimum = min(model['policy']['period'] for model in fitted['models'])
    if fitted['selected_period'] != minimum or fitted['models'][0]['policy']['period'] != minimum:
        return None, {'failure': 'original_minimum_period_disagrees'}
    return candidates[0], {'selected_period': minimum,
                           'retained_periods': [m['policy']['period'] for m in fitted['models']],
                           'models': records}


def fit_guarded(teachers):
    if (not teachers or any(not valid_grid(p['input']) or not valid_grid(p['output']) for p in teachers)
            or len({tuple(map(tuple, p['input'])) for p in teachers}) != len(teachers)):
        return None
    raw_models = fit_models(teachers)
    if not raw_models:
        return None
    marker = raw_models[0]['policy']['marker_color']
    common_roles = set(range(10))
    for pair in teachers:
        counts = Counter(v for row in pair['input'] for v in row)
        if sum(n == max(counts.values()) for n in counts.values()) != 1:
            return None
        roles = {c for c in range(10) if old._periodic_marker_band_parse(pair['input'], c)[0] is not None}
        common_roles &= roles
    if common_roles != {marker}:
        return None
    models = []
    for raw in raw_models:
        policy = deepcopy(raw['policy'])
        period = policy['period']
        evidence = {r: {'band_teachers': set(), 'payload_teachers': set()} for r in range(period)}
        for teacher_index, pair in enumerate(teachers):
            grid = pair['input']
            parsed, _ = old._periodic_marker_band_parse(grid, marker)
            axis = parsed['axis']
            marker_index = parsed['marker_row'] if axis == 'row' else parsed['marker_col']
            start = parsed['band_col0'] if axis == 'row' else parsed['band_row0']
            end = parsed['band_col1'] if axis == 'row' else parsed['band_row1']
            axis_length = len(grid) if axis == 'row' else len(grid[0])
            span_length = len(grid[0]) if axis == 'row' else len(grid)
            for index in range(axis_length):
                residue = ((index - marker_index) * parsed['direction']) % period
                evidence[residue]['band_teachers'].add(teacher_index)
                for span in range(span_length):
                    if start <= span <= end:
                        continue
                    row, col = (index, span) if axis == 'row' else (span, index)
                    if grid[row][col] not in (parsed['background'], marker):
                        evidence[residue]['payload_teachers'].add(teacher_index)
        models.append({'policy': policy, 'evidence': {
            residue: {key: sorted(value) for key, value in data.items()}
            for residue, data in evidence.items()}})
    fitted = {'selected_period': models[0]['policy']['period'], 'models': models,
              'common_marker_color': marker, 'teacher_count': len(teachers)}
    if not all(guarded_render(pair['input'], fitted)[0] == pair['output'] for pair in teachers):
        return None
    return fitted


class 周期帯教材:
    def __init__(self, 教師群):
        self.適合 = fit_guarded(教師群)

    def 候補(self, 格子, _policy):
        return guarded_render(格子, self.適合)

    def 記録(self):
        if self.適合 is None:
            return {"全教師再現": False}
        return {"全教師再現": True, "保持周期": [m["policy"]["period"] for m in self.適合["models"]],
                "選択周期": self.適合["selected_period"], "教師盤面数": self.適合["teacher_count"],
                "marker色": self.適合["common_marker_color"],
                "fill色": self.適合["models"][0]["policy"]["fill_color"]}
