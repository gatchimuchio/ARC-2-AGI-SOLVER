"""Existing colour-ray family plus a completed no-source lattice input view.

Legacy positive fits, prediction records, observers, and errors are delegated
unchanged. Only a completed empty legacy fit whose every teacher has solely
the recognized no_sources role failure opens the strict lattice fitter.
The local-scene extension is prediction-only; teacher fitting stays strict133.
"""
from copy import deepcopy
from dataclasses import dataclass

from . import 色線反射教材 as legacy
from . import 局所格子側線候補 as lattice


def _no_source_boundary(teachers, models, record):
    count = record.get('teacher_count', 0)
    total = len(legacy.core.PROGRAMS)
    if (models or count < 2 or record.get('failure') != 'no_model_fits_all_teachers'
            or record.get('retained_count') != 0
            or record.get('declared_models') != total
            or record.get('evaluated_models') != total
            or record.get('evaluated_teacher_returns') != total*count):
        return None
    witnesses = []
    for index, pair in enumerate(teachers):
        scene, roles = legacy.core.parse_input(pair['input'])
        if (scene is not None or roles.get('failure') != 'role_coverage_failed'
                or roles.get('failed_roles') != [{'failure': 'no_sources'}]
                or roles.get('sources') != [] or not roles.get('glyphs')
                or any(g.get('kind') not in ('point', 'bar') for g in roles['glyphs'])):
            return None
        witnesses.append(dict(teacher=index, roles=roles))
    if len(witnesses) != count:
        return None
    return dict(completed_models=total, completed_teacher_returns=total*count,
                teachers=witnesses)


def _common_spacer_guard(teachers):
    witnesses, common = [], None
    for index, pair in enumerate(teachers):
        grid = pair['input']
        cells = {(r, c) for r in range(len(grid)) for c in range(len(grid[0]))}
        candidates = []
        for colour in sorted({grid[r][c] for r, c in cells}):
            positions = {p for p in cells if grid[p[0]][p[1]] == colour}
            phases = {(r+c) % 2 for r, c in positions}
            if len(phases) == 1:
                phase = next(iter(phases))
                if positions == {p for p in cells if sum(p) % 2 == phase}:
                    candidates.append(dict(colour=colour, parity=phase,
                                           pixel_count=len(positions)))
        colours = {c['colour'] for c in candidates}
        common = colours if common is None else common & colours
        witnesses.append(dict(teacher=index, spacer_candidates=candidates))
    return dict(teachers=witnesses, common_spacer_colours=sorted(common or ()),
                necessary_condition=bool(common), guard_render_calls=0)


def fit(teachers, observer=None):
    models, old_record = legacy.fit(teachers, observer)
    boundary = _no_source_boundary(teachers, models, old_record)
    if boundary is None:
        return models, old_record
    guard = _common_spacer_guard(teachers)
    if not guard['necessary_condition']:
        guard['failure'] = 'no_common_complete_parity_spacer'
        guard['logical_no_fit'] = True
        guard['new_render_calls'] = 0
        legacy.emit(observer, 'lattice_necessary_condition_return', record=guard)
        return models, dict(old_record, lattice_view_guard=guard)
    view_models, view_record = lattice.fit(teachers, observer)
    record = dict(teacher_count=old_record['teacher_count'], teacher_fit_minimum=2,
                  declared_models=len(view_record['declared_models']),
                  evaluated_models=len(view_record['returns']),
                  evaluated_teacher_returns=sum(len(r['teachers']) for r in view_record['returns']),
                  retained_count=len(view_models),
                  failure=None if view_models else 'no_model_fits_all_teachers',
                  input_view='complete_local_lattice_scenes',
                  legacy_fit=old_record, legacy_boundary=boundary,
                  lattice_view_guard=guard, lattice_fit=view_record)
    legacy.emit(observer, 'lattice_family_fit_completed', models=view_models, record=record)
    return view_models, record


def predict(grid, models, observer=None):
    if models and all(len(model) == 5 for model in models):
        return lattice.predict(grid, models, observer)
    return legacy.predict(grid, models, observer)


@dataclass(frozen=True, init=False, slots=True)
class 色線反射教材:
    モデル群: tuple
    教師数: int
    適合数: int
    不足理由: str | None

    def __init__(self, 教師群, 監査=None, 観測=None):
        models, record = fit(教師群, 観測)
        object.__setattr__(self, 'モデル群', models)
        object.__setattr__(self, '教師数', record['teacher_count'])
        object.__setattr__(self, '適合数', len(models))
        object.__setattr__(self, '不足理由', record.get('failure'))
        if 監査 is not None:
            監査.update(deepcopy(record))

    def 候補(self, 格子, policy, 観測=None):
        return predict(格子, self.モデル群, 観測)

    def 記録(self):
        record = legacy.色線反射教材.記録(self)
        if self.モデル群 and all(len(m) == 5 for m in self.モデル群):
            record['固定prior'] = ('完了した旧no_sources境界・共通完全parity spacer必要条件・'
                                 'strict133全教師fit・全局所枠と側棒の一意完全所有・'
                                 'canvas外source非入域証明・元の有限ray graph')
        return record
