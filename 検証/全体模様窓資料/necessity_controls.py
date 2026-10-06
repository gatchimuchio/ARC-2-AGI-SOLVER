"""Independent SOURCE-ONLY NEW034 necessity controls, pending reviewer release.

This file never imports the candidate, old fitter, helper, or official data.
The caller must supply a separately cleared proof module and saved records.
There is no command-line runner and no fit is performed during import.
Checks raise explicit exceptions and remain active under python -O.

Public interfaces:
  check_certificates(proof, certificate_view=None)
  check_strict_inputs(proof)
  check_inconclusive_fallback(proof)
  check_fit_record(models, record, old_record, teachers=None, record_view=None)
  check_available_complete_records(models, record, saved, record_view=None)
  check_prefix_record(diagnostic, teachers, record_view=None, old_record=None)
  check_observer_fault(proof, teachers, predicate, exception_type=MemoryError,
                       record_view=None, old_record=None)
  check_call_fault(proof, teachers, owner, attribute, ordinal=1,
                  exception_type=MemoryError, record_view=None, old_record=None)

certificate_view and record_view adapt diagnostic vocabulary only. They must
not invent a return, certificate, witness, row, completion or exactness value.
The canonical schemas below let the parent choose its diagnostic field names
without coupling the independent geometric/palette oracle to implementation.
All supplied saved records must be synthetic; no official file is opened here.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import fields, is_dataclass
from enum import IntEnum
from itertools import product
import json
import gzip
from pathlib import Path
from unittest.mock import patch


FIELDS = ('extent', 'window', 'center', 'transform', 'phase', 'overlay', 'base_ink', 'highlight')
TRANSFORMS = ('identity', 'rot90', 'rot180', 'rot270', 'flip_h', 'flip_v', 'transpose', 'anti_transpose')
ENUMS = (('motif5plus1', 'input3minus2'), ('motif2', 'input'), ('floor', 'ceil'),
         TRANSFORMS, ('window', 'canvas'), ('tile', 'scale2'))
DOMAIN = tuple(values for values in product(*ENUMS, range(10), range(10)) if values[-2] != values[-1])


def require(condition, label):
    if not condition:
        raise AssertionError(label)


def equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(f'{label}: actual={actual!r}; expected={expected!r}')


def strict_equal(left, right):
    """Do not equate True/1, 1.0/1, or subclasses at strict boundaries."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(strict_equal(left[key], right[key]) for key in left)
    if type(left) in (tuple, list):
        return len(left) == len(right) and all(strict_equal(a, b) for a, b in zip(left, right))
    return left == right


def stored(value):
    """JSON storage comparison only; never used to authorize a certificate."""
    return json.loads(json.dumps(value, ensure_ascii=False))


def fixtures():
    return json.loads(gzip.decompress((Path(__file__).resolve().parent / 'necessity-fixtures.json.gz').read_bytes()))


def valid_grid(grid):
    return (type(grid) is list and 1 <= len(grid) <= 30 and type(grid[0]) is list
            and 1 <= len(grid[0]) <= 30 and all(type(row) is list and len(row) == len(grid[0])
            and all(type(value) is int and 0 <= value <= 9 for value in row) for row in grid))


def valid_spec(spec):
    return (type(spec) is tuple and len(spec) == 8
            and all(type(value) is str and value in choices for value, choices in zip(spec[:6], ENUMS))
            and all(type(value) is int and 0 <= value <= 9 for value in spec[-2:]) and spec[-2] != spec[-1])


def reference_parse(grid):
    """Independent whole-input strict C8 ownership, no recovered helpers."""
    if not valid_grid(grid):
        return None, 'invalid_arc_grid'
    counts = Counter(value for row in grid for value in row)
    if len(counts) != 2:
        return None, 'not_binary'
    foreground, background = sorted(counts, key=counts.get)
    if counts[foreground] == counts[background]:
        return None, 'background_tie'
    support = {(r, c) for r, row in enumerate(grid) for c, value in enumerate(row) if value == foreground}
    reached = {min(support)}
    frontier = list(reached)
    while frontier:
        r, c = frontier.pop()
        for dr, dc in product((-1, 0, 1), repeat=2):
            neighbor = (r + dr, c + dc)
            if neighbor in support and neighbor not in reached:
                reached.add(neighbor)
                frontier.append(neighbor)
    if reached != support:
        return None, 'not_one_whole_c8_component'
    r0, c0 = min(r for r, c in support), min(c for r, c in support)
    r1, c1 = max(r for r, c in support), max(c for r, c in support)
    return {'background': background, 'foreground': foreground,
            'input_shape': [len(grid), len(grid[0])], 'bbox': [r0, c0, r1, c1],
            'cells': [(r, c, foreground) for r, c in sorted(support)],
            'mask': [[int((r, c) in support) for c in range(c0, c1 + 1)] for r in range(r0, r1 + 1)],
            'foreground_count': len(support), 'background_count': counts[background],
            'ownership': 'complete foreground single C8 + all remaining input background'}, None


def witness(pair, teacher_index=0):
    role, reason = reference_parse(pair['input'])
    target = pair.get('target', pair.get('output'))
    return {'teacher_index': teacher_index, 'input': deepcopy(pair['input']), 'target': deepcopy(target),
            'role': role, 'reason': reason,
            'target_colors': sorted({value for row in target for value in row}) if valid_grid(target) else None,
            'target_shape': [len(target), len(target[0])] if valid_grid(target) else None}


def reference_certificate(value, spec, model_index):
    """Only complete authenticated witnesses prove palette or shape mismatch."""
    unknown = {'complete': False, 'refuted': False, 'causes': [],
               'allowed_colors': None, 'predicted_shape': None}
    if (not valid_spec(spec) or type(model_index) is not int or not 0 <= model_index < len(DOMAIN)
            or DOMAIN[model_index] != spec or type(value) is not dict):
        return unknown
    keys = {'teacher_index', 'input', 'target', 'role', 'reason', 'target_colors', 'target_shape'}
    if not keys <= value.keys() or type(value['teacher_index']) is not int or value['teacher_index'] < 0:
        return unknown
    if not valid_grid(value['input']) or not valid_grid(value['target']):
        return unknown
    parsed, reason = reference_parse(value['input'])
    if parsed is None or reason is not None or value['reason'] is not None or not strict_equal(value['role'], parsed):
        return unknown
    colors = sorted({cell for row in value['target'] for cell in row})
    shape = [len(value['target']), len(value['target'][0])]
    if not strict_equal(value['target_colors'], colors) or not strict_equal(value['target_shape'], shape):
        return unknown
    mh, mw = len(parsed['mask']), len(parsed['mask'][0])
    if spec[3] in ('rot90', 'rot270', 'transpose', 'anti_transpose'):
        mh, mw = mw, mh
    predicted = [5 * mh + 1, 5 * mw + 1] if spec[0] == 'motif5plus1' else [3 * x - 2 for x in parsed['input_shape']]
    allowed = sorted({parsed['background'], spec[6], spec[7]})
    causes = ([] if set(colors) <= set(allowed) else ['palette']) + ([] if shape == predicted else ['shape'])
    return {'complete': True, 'refuted': bool(causes), 'causes': causes,
            'allowed_colors': allowed, 'predicted_shape': predicted}


def canonical_certificate(value):
    """Map only explicit necessity facts from the proof-front's own schema."""
    require(value['necessary_only'] is True, 'certificate never claims an actual output')
    require(type(value['refuted']) is bool, 'certificate exact boolean')
    require(value['status'] in ('inconclusive', 'refuted', 'not_refuted'), 'certificate status vocabulary')
    equal(value['refuted'], value['status'] == 'refuted', 'certificate status/refutation agreement')
    if value['status'] == 'inconclusive':
        return {'complete': False, 'refuted': False, 'causes': [], 'allowed_colors': None, 'predicted_shape': None}
    require(type(value['shape_mismatch']) is bool, 'shape mismatch is exact boolean')
    causes = (['palette'] if value['missing_target_colors'] else []) + (['shape'] if value['shape_mismatch'] else [])
    return {'complete': True, 'refuted': value['refuted'], 'causes': causes,
            'allowed_colors': list(value['allowed_colors']), 'predicted_shape': list(value['expected_output_shape'])}


def _candidate_witness(proof, value):
    """Use the candidate's typed constructor; never patch a returned value."""
    required = {'teacher_index', 'input', 'target', 'role', 'reason', 'target_colors', 'target_shape'}
    if type(value) is not dict or not required <= value.keys():
        return value
    # Cached target summaries are factory-owned. A plain forged record is not
    # a typed witness and must remain inconclusive rather than being repaired.
    if valid_grid(value['target']):
        if (not strict_equal(value['target_colors'], sorted({v for row in value['target'] for v in row}))
                or not strict_equal(value['target_shape'], [len(value['target']), len(value['target'][0])])):
            return value
    return proof.TeacherWitness(value['teacher_index'], {'input': value['input'], 'output': value['target']},
                                {'role': value['role'], 'reason': value['reason']})


def _check_certificate(proof, value, spec, index, view, label):
    before = deepcopy(value)
    typed = _candidate_witness(proof, value)
    actual = proof.certify_teacher(typed, spec, index)
    require(strict_equal(value, before), label + ': input witness unchanged')
    expected = reference_certificate(value, spec, index)
    observed = view(actual)
    equal(observed, expected, label + ': independent necessary conditions')
    require(type(observed['complete']) is bool and type(observed['refuted']) is bool, label + ': exact status types')
    equal(actual['model_index'], index, label + ': certificate model identity')
    if observed['complete']:
        equal(actual['teacher_witness_ref'], value['teacher_index'], label + ': certificate witness identity')
        equal(list(actual['target_colors']), value['target_colors'], label + ': complete target palette')
        equal(list(actual['target_shape']), value['target_shape'], label + ': complete target shape')
        equal(list(actual['missing_target_colors']), sorted(set(value['target_colors']) - set(observed['allowed_colors'])), label + ': exact missing palette')
    return actual


def check_certificates(proof, certificate_view=None):
    """Run only after source clearance; one literal actual apply, no full fit."""
    view = certificate_view or canonical_certificate
    packet = fixtures()
    equal(tuple(proof.SPECS), DOMAIN, 'all23040 ordered alternatives')
    require(len(DOMAIN) == len(set(DOMAIN)) == 23040, 'independent ordered grammar')
    count = 0
    for case in packet['cases']:
        spec = tuple(case['spec'])
        value = witness(case)
        expected = reference_certificate(value, spec, DOMAIN.index(spec))
        equal(expected['refuted'], case['expected_refuted'], case['name'] + ': literal refutation')
        equal(expected['predicted_shape'], case['expected_predicted_shape'], case['name'] + ': literal shape')
        equal(expected['allowed_colors'], case['expected_allowed_colors'], case['name'] + ': literal palette')
        equal(value['target_colors'], case['expected_target_colors'], case['name'] + ': literal target colors')
        if 'expected_causes' in case:
            equal(expected['causes'], case['expected_causes'], case['name'] + ': literal causes')
        _check_certificate(proof, value, spec, DOMAIN.index(spec), view, case['name'])
        count += 1
    literal = packet['cases'][0]
    value = witness(literal)
    spec = tuple(literal['spec'])
    base = getattr(proof, '_base', getattr(proof, 'base', None))
    require(base is not None, 'proof must expose unchanged base for literal fallback check')
    equal(base.apply(value['role'], value['reason'], spec), literal['expected_full_return'], 'all-highlight literal full return')
    rectangle = packet['cases'][3]
    for transform, expected_shape in packet['d4_shapes'].items():
        spec = tuple(rectangle['spec'][:3]) + (transform,) + tuple(rectangle['spec'][4:])
        for target_shape, refuted in ((expected_shape, False), (expected_shape[::-1], True)):
            pair = {'input': rectangle['input'], 'target': [[3] * target_shape[1] for _ in range(target_shape[0])]}
            value = witness(pair)
            expected = reference_certificate(value, spec, DOMAIN.index(spec))
            equal(expected['refuted'], refuted, transform + ': swapped-shape literal')
            _check_certificate(proof, value, spec, DOMAIN.index(spec), view, transform + ':' + str(target_shape))
            count += 1
    # input3minus2 is independent of the D4 motif dimension swap.
    for transform in TRANSFORMS:
        spec = ('input3minus2', 'input', 'floor', transform, 'window', 'tile', 2, 3)
        pair = {'input': packet['nonsquare_input3minus2']['input'], 'target': [[3] * 19 for _ in range(16)]}
        equal(reference_certificate(witness(pair),spec,DOMAIN.index(spec))['predicted_shape'],[16,19],
              'literal nonswapped input extent:'+transform)
        _check_certificate(proof, witness(pair), spec, DOMAIN.index(spec), view, 'input3minus2:' + transform)
        count += 1
    original = witness(packet['cases'][1])
    spec = tuple(packet['cases'][1]['spec'])
    index = DOMAIN.index(spec)
    malformed = [None, {}, dict(original, role=None), dict(original, reason='not_binary'),
                 dict(original, target_colors=[3]), dict(original, target_shape=[7, 6]),
                 dict(original, teacher_index=True), dict(original, teacher_index=-1)]
    for key in original:
        item = deepcopy(original)
        del item[key]
        malformed.append(item)
    for key in original['role']:
        item = deepcopy(original)
        del item['role'][key]
        malformed.append(item)
    for key in ('background', 'foreground', 'foreground_count', 'background_count'):
        item = deepcopy(original)
        item['role'][key] = float(item['role'][key])
        malformed.append(item)
    item = deepcopy(original)
    item['role']['mask'][0][0] = True
    malformed.append(item)
    item = deepcopy(original)
    item['role']['cells'][0] = list(item['role']['cells'][0])
    malformed.append(item)
    item = deepcopy(original)
    item['role']['input_shape'][0] = float(item['role']['input_shape'][0])
    malformed.append(item)
    item = deepcopy(original)
    item['role']['bbox'] = [0, 0, 0, 0]
    malformed.append(item)
    item = deepcopy(original)
    item['role']['ownership'] = 'claimed ownership without complete strict parse'
    malformed.append(item)
    item = witness(rectangle)
    item['role']['mask'] = [[1]]
    malformed.append(item)
    for grid in ([[0]], [[0, 1]], [[0, 0, 0, 0, 0], [0, 1, 0, 1, 0], [0, 0, 0, 0, 0]]):
        malformed.append(witness({'input': grid, 'target': packet['cases'][1]['target']}))
    for i, value in enumerate(malformed):
        equal(reference_certificate(value, spec, index)['complete'], False, 'incomplete fixture:' + str(i))
        _check_certificate(proof, value, spec, index, view, 'missing/failed/inconclusive:' + str(i))
    for wrong_index in (True, 1.0, -1, len(DOMAIN), (index + 1) % len(DOMAIN)):
        _check_certificate(proof, original, spec, wrong_index, view, 'strict certificate model index:' + repr(wrong_index))
    class TS(tuple):
        pass
    class SS(str):
        pass
    class IS(int):
        pass
    for bad_spec in (list(spec), TS(spec), (SS(spec[0]),) + spec[1:], spec[:6] + (IS(2), 3),
                     spec[:6] + (True, 3), spec[:6] + (2.0, 3), spec[:6] + (2, 2)):
        _check_certificate(proof, original, bad_spec, index, view, 'strict certificate spec:' + repr(bad_spec))
    # Necessary conditions alone do not prove success and must not infer
    # extra impossibility predicates from color collision or scale failure.
    eligible_failures = [
        (('motif5plus1', 'input', 'floor', 'identity', 'window', 'tile', 0, 3), 'output_colors_not_new'),
        (('motif5plus1', 'input', 'floor', 'identity', 'window', 'scale2', 2, 3), 'scale_window_mismatch')]
    for candidate_spec, failure in eligible_failures:
        value = witness(literal)
        _check_certificate(proof, value, candidate_spec, DOMAIN.index(candidate_spec), view, 'eligible actual failure:' + failure)
        equal(base.apply(value['role'], value['reason'], candidate_spec),
              {'status': 'failure', 'reason': failure, 'output': None}, 'full unchanged failed fallback:' + failure)
    def immutable(value):
        if type(value) in (type(None), str, int, bool):
            return True
        if type(value) is tuple:
            return all(immutable(item) for item in value)
        return (is_dataclass(value) and type(value).__dataclass_params__.frozen
                and all(immutable(getattr(value, field.name)) for field in fields(value)))
    original = witness(literal)
    typed = _candidate_witness(proof, original)
    require(immutable(typed), 'complete typed witness is deeply immutable')
    saved = proof.witness_record(typed)
    original['input'][0][0] = 9
    original['target'][0][0] = 9
    original['role']['mask'][0][0] = 0
    equal(proof.witness_record(typed), saved, 'typed witness detached from constructor input aliases')
    exported = proof.witness_record(typed)
    exported['role']['mask'][0][0] = 0
    exported['target'][0][0] = 9
    equal(proof.witness_record(typed), saved, 'exported witness record cannot mutate proof witness')
    blocked = False
    try:
        typed.complete = False
    except (AttributeError, TypeError):
        blocked = True
    require(blocked, 'typed witness fields reject assignment')
    return {'literal_and_shape_certificates': count, 'inconclusive_witnesses': len(malformed),
            'literal_complete_actual_returns': 3, 'deep_immutable_witness_checked': True, 'full_teacher_fits': 0}


def check_strict_inputs(proof):
    """Strict teacher and model distinctions; malformed fit never parses."""
    class LS(list):
        pass
    class TS(tuple):
        pass
    class DS(dict):
        pass
    class SS(str):
        pass
    class IS(int):
        pass
    class IE(IntEnum):
        ZERO = 0
    packet = fixtures()
    a = packet['cases'][0]
    b = deepcopy(a)
    b['input'][2][2], b['input'][2][3] = 0, 1
    pairs = [{'input': item['input'], 'output': item['target']} for item in (a, b)]
    grids = [None, (), [[]], [[True]], [[IE.ZERO]], [[IS(0)]], [[0.0]], [["0"]],
             LS([[0]]), [LS([0])], [[0], [0, 0]], [[-1]], [[10]], [[0] * 31], [[0]] * 31]
    spec = tuple(a['spec'])
    specs = [list(spec), TS(spec), spec[:-1], spec + (0,), (SS(spec[0]),) + spec[1:],
             spec[:6] + (True, 3), spec[:6] + (IS(2), 3), spec[:6] + (2.0, 3),
             spec[:6] + (2, 2), spec[:6] + (-1, 3), spec[:6] + (2, 10)]
    for grid in grids:
        require(proof.valid_grid(grid) is False, 'exact strict grid rejection')
    for item in specs:
        require(proof.valid_spec(item) is False, 'exact strict spec rejection')
    invalid = [(None, 'invalid_teacher_container'), (LS(pairs), 'invalid_teacher_container'),
               (TS(pairs), 'invalid_teacher_container'), ([], 'too_few_distinct_teachers'),
               ([pairs[0]], 'too_few_distinct_teachers'), ([pairs[0], deepcopy(pairs[0])], 'duplicate_teacher_inputs'),
               ([DS(pairs[0]), pairs[1]], 'invalid_teacher_pair'),
               ([dict(pairs[0], extra=0), pairs[1]], 'invalid_teacher_pair')]
    for grid in grids:
        invalid.append(([{'input': grid, 'output': a['target']}, pairs[1]], 'invalid_teacher_pair'))
        invalid.append(([{'input': a['input'], 'output': grid}, pairs[1]], 'invalid_teacher_pair'))
    with patch.object(proof.core, 'parse', side_effect=AssertionError('invalid teacher execution reached parser')):
        for teachers, reason in invalid:
            models, record = proof.fit(teachers)
            equal(models, (), 'strict invalid teachers retain nothing')
            equal(record['failure'], reason, 'strict teacher validation reason')
    return {'invalid_grids': len(grids), 'invalid_specs': len(specs), 'invalid_teacher_fits': len(invalid)}


def check_inconclusive_fallback(proof,modes=('absent','failed_role','incomplete_role')):
    """Exercise real unchanged apply for every teacher when proof is absent.

    A fault wrapper supplies the certifier an absent or failed typed witness.
    The real certifier returns inconclusive, then the real apply runs twice.
    All23040 model certificates are precomputed without any refutation. The
    unchanged strict fitter is delegated. An observer stops after its first
    complete model; no full fit is claimed, no model domain is reduced, and
    no renderer return is ever fabricated.
    """
    teachers = fault_teachers()
    original_certificate = proof.certify_teacher
    original_apply = proof.base.apply
    records = []
    for mode in modes:
        primary = RuntimeError('bounded inconclusive fallback stop')
        actual_returns = []
        require(mode in('absent','failed_role','incomplete_role'),'known inconclusive mode')
        supplied_witnesses={}
        for ti,pair in enumerate(teachers):
            if mode=='absent':supplied_witnesses[ti]=None
            else:
                parsed={'role':None,'reason':'not_binary'}if mode=='failed_role'else{'role':{},'reason':None}
                supplied_witnesses[ti]=proof.TeacherWitness(ti,deepcopy(pair),parsed)
                equal(supplied_witnesses[ti].incomplete_reason,
                      'strict_input_role_absent_or_failed'if mode=='failed_role'else'malformed_strict_input_role',
                      mode+': intended role boundary reached after valid grids')
        def inconclusive(value, spec, model_index):
            return original_certificate(supplied_witnesses[value.teacher_index], spec, model_index)
        def observed_apply(*args, **kwargs):
            result = original_apply(*args, **kwargs)
            actual_returns.append(deepcopy(result))
            return result
        def observer(event):
            if event.get('kind') == 'model_completed' and event['model_index'] == 0:
                raise primary
        caught = None
        with patch.object(proof, 'certify_teacher', inconclusive), patch.object(proof.base, 'apply', observed_apply):
            try:
                proof.fit(deepcopy(teachers), observer)
            except BaseException as error:
                caught = error
        require(caught is primary, mode + ': bounded stop preserves original exception')
        diagnostic = getattr(caught, 'evaluation_diagnostic', None)
        require(type(diagnostic) is dict and diagnostic['semantic_HOLD'] is False, mode + ': actual prefix diagnostic')
        equal(len(actual_returns), len(teachers), mode + ': every teacher receives unchanged apply')
        equal(actual_returns, [{'status': 'failure', 'reason': 'output_colors_not_new', 'output': None}] * len(teachers),
              mode + ': complete literal real fallback returns')
        equal(diagnostic['symbolic_model_teacher_slots'], [], mode + ': inconclusive proof skips no teacher')
        require(diagnostic['original_strict_fallback_started'] is True and diagnostic['original_strict_fallback_returned'] is False,
                mode + ': original strict fallback was entered and interrupted')
        equal(diagnostic['phase'], 'exact_strict_fallback', mode + ': original fallback phase')
        equal(diagnostic['model_teacher_returns'], [], mode + ': proof front does not claim original actual calls')
        equal(diagnostic['completed_models'], [], mode + ': proof front does not claim original completed models')
        original_diagnostic = diagnostic['original_strict_diagnostic']
        require(type(original_diagnostic) is dict and original_diagnostic['semantic_HOLD'] is False,
                mode + ': original strict diagnostic preserved')
        equal(len(original_diagnostic['model_teacher_returns']), len(teachers), mode + ': original actual rows all preserved')
        equal(original_diagnostic['completed_models'], [{'model_index': 0, 'teacher_exacts': [False] * len(teachers),
                                                        'retained': False}], mode + ': original real model completion')
        for ti, row in enumerate(original_diagnostic['model_teacher_returns']):
            equal((row['model_index'], row['teacher_index']), (0, ti), mode + ': original exact model/teacher order')
            equal(original_diagnostic['return_pool'][row['return_ref']], actual_returns[ti], mode + ': original full actual return')
        equal(len(diagnostic['model_necessity_certificates']), len(DOMAIN), mode + ': entire unchanged model domain certified before fallback')
        for mi, certificate in enumerate(diagnostic['model_necessity_certificates']):
            equal(certificate['model_index'], mi, mode + ': complete ordered model certificates')
            equal(certificate['refuting_teacher_indices'], [], mode + ': no incomplete refutation')
            require(all(c['status'] == 'inconclusive' and c['refuted'] is False for c in certificate['teacher_witnesses']),
                    mode + ': missing/failed witness certifier remains inconclusive')
        records.append({'mode': mode, 'actual_returns': actual_returns, 'diagnostic': diagnostic})
    return records


def canonical_record(record):
    """Canonical evidence view contract, no interpretation of unknown rows.

    witnesses: complete original witness list
    certificates: per-model {model_index, teacher_certificates, refuted}
    rows: model-major/teacher-minor; each has model_index, teacher_index,
      executed, action_executed and full_grid_fit. An executed row has
      return_ref. An unexecuted row has certificate_ref and fit_knowledge,
      either self_refuted (full_grid_fit is False) or unknown_exact (None).
    return_pool, completed_models: unchanged full values and ordered models.
    completed model: {model_index, teacher_exacts, retained}, where unresolved
      other-teacher exactness remains None for a symbolically refuted model.
    """
    witnesses = []
    for item in record.get('teacher_necessity_witnesses', []):
        require(item['complete'] is True and item['incomplete_reason'] is None,
                'normal synthetic complete-fit witness must be complete')
        witnesses.append({key: item[key] for key in ('teacher_index', 'input', 'target', 'role', 'reason', 'target_colors', 'target_shape')})
    certificates = []
    for item in record.get('model_necessity_certificates', []):
        mi = item['model_index']
        require(type(mi) is int and 0 <= mi < len(DOMAIN), 'model certificate strict index')
        equal(tuple(item['spec']), DOMAIN[mi], 'model certificate exact spec')
        teacher_certificates = item['teacher_witnesses']
        for ti, certificate in enumerate(teacher_certificates):
            equal(certificate['model_index'], mi, 'teacher certificate model identity')
            equal(certificate['teacher_witness_ref'], ti, 'teacher certificate witness identity')
        refuting = [ti for ti, c in enumerate(teacher_certificates) if c['refuted']]
        equal(list(item['refuting_teacher_indices']), refuting, 'complete model refuting witness list')
        certificates.append({'model_index': mi, 'teacher_certificates': [canonical_certificate(c) for c in teacher_certificates],
                             'refuted': bool(refuting)})
    rows = []
    for source_name, executed in (('model_teacher_returns', True), ('symbolic_model_teacher_slots', False)):
        previous = None
        for item in record.get(source_name, []):
            identity = (item['model_index'], item['teacher_index'])
            require(all(type(value) is int for value in identity), 'strict logical slot indices')
            require(previous is None or previous < identity, 'raw actual/symbolic substream order and uniqueness')
            previous = identity
            if executed:
                row = dict(item, executed=True)
            else:
                require(not {'return', 'return_ref', 'output'} & item.keys(), 'source symbolic slot has no invented actual return')
                require(item['actual_return_known'] is False and item['action_executed'] is False, 'source symbolic slot explicitly unexecuted')
                require(item['exactness'] in ('proven_not_exact', 'unknown_model_refuted_elsewhere'), 'source symbolic exactness vocabulary')
                mi, ti = identity
                require(mi < len(certificates), 'symbolic source has complete certificate')
                expected_refuting = [j for j, c in enumerate(certificates[mi]['teacher_certificates']) if c['refuted']]
                equal(list(item['refuting_teacher_indices']), expected_refuting, 'symbolic slot retains complete refuting witness references')
                own = item['exactness'] == 'proven_not_exact'
                row = {'model_index': mi, 'teacher_index': ti, 'executed': False, 'action_executed': False,
                       'certificate_ref': item['model_certificate_ref'],
                       'fit_knowledge': 'self_refuted' if own else 'unknown_exact',
                       'full_grid_fit': False if own else None}
            rows.append(row)
    rows.sort(key=lambda item: (item['model_index'], item['teacher_index']))
    completed = []
    for item in record.get('completed_models', []):
        mi = item['model_index']
        if item['evaluation'] == 'actual':
            completed.append({key: item[key] for key in ('model_index', 'teacher_exacts', 'retained')})
        else:
            equal(item['evaluation'], 'symbolic_refutation', 'symbolic completion vocabulary')
            require('teacher_exacts' not in item, 'symbolic completion does not fabricate actual teacher equality results')
            equal(item['model_certificate_ref'], mi, 'symbolic completion certificate link')
            require(item['retained'] is False, 'symbolic refuted model cannot be retained')
            refuting = list(item['proven_not_exact_teacher_indices'])
            unknown = list(item['unexecuted_unknown_exact_teacher_indices'])
            n = len(certificates[mi]['teacher_certificates'])
            equal(refuting, [j for j, c in enumerate(certificates[mi]['teacher_certificates']) if c['refuted']], 'symbolic completed own refutations')
            equal(unknown, [j for j in range(n) if j not in refuting], 'symbolic completed unknown exactness indices')
            completed.append({'model_index': mi, 'retained': False,
                              'teacher_exacts': [False if ti in refuting else None for ti in range(n)]})
    return {'witnesses': witnesses, 'certificates': certificates, 'rows': rows,
            'return_pool': record.get('return_pool', []), 'completed_models': completed}


def _old_audit(old_record):
    return old_record.get('audit', old_record)


def _independent_model_proof(teachers, model_index, prepared=None):
    """Preparation is independent once per teacher, arithmetic once per model."""
    spec = DOMAIN[model_index]
    prepared = prepared if prepared is not None else [witness(pair, i) for i, pair in enumerate(teachers)]
    proofs = []
    for value in prepared:
        if value['role'] is None or value['reason'] is not None:
            proofs.append({'complete': False, 'refuted': False, 'causes': [], 'allowed_colors': None, 'predicted_shape': None})
            continue
        role = value['role']
        mh, mw = len(role['mask']), len(role['mask'][0])
        if spec[3] in ('rot90', 'rot270', 'transpose', 'anti_transpose'):
            mh, mw = mw, mh
        shape = [5 * mh + 1, 5 * mw + 1] if spec[0] == 'motif5plus1' else [3 * size - 2 for size in role['input_shape']]
        allowed = sorted({role['background'], spec[6], spec[7]})
        causes = ([] if set(value['target_colors']) <= set(allowed) else ['palette']) + ([] if shape == value['target_shape'] else ['shape'])
        proofs.append({'complete': True, 'refuted': bool(causes), 'causes': causes, 'allowed_colors': allowed, 'predicted_shape': shape})
    return proofs, any(item['refuted'] for item in proofs)


def _check_rows(evidence, teachers, old_record=None, complete=False):
    rows, pool = evidence['rows'], evidence['return_pool']
    n = len(teachers)
    require(n >= 2, 'complete/prefix controls need validated distinct teachers')
    old = _old_audit(old_record) if old_record is not None else None
    witnesses = evidence['witnesses']
    require(len(witnesses) <= n, 'witness prefix cannot exceed teacher count')
    for i, actual in enumerate(witnesses):
        equal(stored(actual), stored(witness(teachers[i], i)), 'complete witness input/target/role linkage')
    if rows:
        equal(len(witnesses), n, 'all teachers witnessed before model rows')
    certificates = evidence['certificates']
    prepared = [witness(pair, i) for i, pair in enumerate(teachers)]
    independent = []
    for i, certificate in enumerate(certificates):
        equal(certificate['model_index'], i, 'certificate model prefix order')
        proofs, refuted = _independent_model_proof(teachers, i, prepared)
        independent.append((proofs, refuted))
        equal(certificate['refuted'], refuted, 'whole model refuted iff some complete teacher refutes')
        require(type(certificate['refuted']) is bool, 'exact model proof boolean')
        equal(len(certificate['teacher_certificates']), n, 'complete teacher certificate set per model')
        for ti, actual in enumerate(certificate['teacher_certificates']):
            equal(actual, proofs[ti], 'every teacher certificate independently checked')
    counts = Counter()
    row_exacts = []
    for ordinal, row in enumerate(rows):
        mi, ti = divmod(ordinal, n)
        equal((row['model_index'], row['teacher_index']), (mi, ti), 'complete logical model/teacher order')
        require(mi < len(certificates), 'every logical slot references an available model proof')
        proofs, refuted = independent[mi]
        if row['executed']:
            require(row['executed'] is True and not refuted, 'actual fallback only for non-refuted model')
            require(type(row['return_ref']) is int and 0 <= row['return_ref'] < len(pool), 'actual return pool reference')
            actual_return = pool[row['return_ref']]
            exact = (actual_return['status'] == 'success' and valid_grid(actual_return['output'])
                     and actual_return['output'] == teachers[ti]['output'])
            require(type(row['full_grid_fit']) is bool, 'actual exactness is strict boolean')
            equal(row['full_grid_fit'], exact, 'actual complete-grid equality')
            equal(row['action_executed'], witnesses[ti]['role'] is not None, 'actual unchanged apply parse behavior')
            if old is not None:
                old_row = old['model_teacher_returns'][ordinal]
                equal((old_row['model_index'], old_row['teacher_index']), (mi, ti), 'saved row identity')
                equal(stored(actual_return), old['return_pool'][old_row['return_ref']], 'actual full return and all details vs saved old row')
                equal(row['full_grid_fit'], old_row['full_grid_fit'], 'actual exactness vs saved old row')
            counts['actual'] += 1
        else:
            require(row['executed'] is False and row['action_executed'] is False, 'symbolic slot never executed')
            require(refuted, 'skip only complete model-level proof')
            require('return' not in row and 'return_ref' not in row, 'unexecuted slot has no invented return')
            equal(row['certificate_ref'], mi, 'skipped teacher references full model certificate')
            if proofs[ti]['refuted']:
                equal(row['fit_knowledge'], 'self_refuted', 'own teacher certificate refutes exactness')
                require(row['full_grid_fit'] is False, 'self-refuted teacher exactness is false')
                if old is not None:
                    require(old['model_teacher_returns'][ordinal]['full_grid_fit'] is False, 'every symbolic self-refutation agrees with saved old row')
                counts['self_refuted'] += 1
            else:
                equal(row['fit_knowledge'], 'unknown_exact', 'different-teacher proof does not determine this teacher exactness')
                require(row['full_grid_fit'] is None, 'skipped unrefuted teacher exactness remains unknown')
                counts['unknown_exact'] += 1
        row_exacts.append(row['full_grid_fit'])
    completed = evidence['completed_models']
    require(len(completed) <= len(rows) // n, 'no model completion before all teacher slots committed')
    for mi, item in enumerate(completed):
        equal(item['model_index'], mi, 'completed model order')
        exacts = row_exacts[mi * n:(mi + 1) * n]
        equal(item['teacher_exacts'], exacts, 'completed model preserves unknown exactness')
        equal(item['retained'], all(value is True for value in exacts), 'retain iff every actual teacher is exactly fit')
        if old is not None:
            equal(item['retained'], old['completed_models'][mi]['retained'], 'all completed-model retention agrees with saved old fit')
    if complete:
        equal(len(rows), len(DOMAIN) * n, 'all declared logical slots represented')
        equal(len(completed), len(DOMAIN), 'all declared models completed')
        equal(len(certificates), len(DOMAIN), 'all complete model certificates present')
    return dict(counts)


def check_fit_record(models, record, old_record, teachers=None, record_view=None):
    """Compare already executed new fit to old full matrix; never re-fit."""
    teachers = teachers if teachers is not None else old_record['teachers']
    old = _old_audit(old_record)
    equal(old['program_count'], len(DOMAIN), 'saved complete old model count')
    equal(len(old['model_teacher_returns']), len(DOMAIN) * len(teachers), 'saved old matrix is complete')
    equal(len(old['completed_models']), len(DOMAIN), 'saved old completed models are complete')
    evidence = (record_view or canonical_record)(record)
    counts = _check_rows(evidence, teachers, old_record, complete=True)
    retained = tuple((mi,) + DOMAIN[mi] for mi, item in enumerate(old['completed_models']) if item['retained'])
    equal(models, retained, 'exact old retained set, identity, and order')
    if 'models' in old_record:
        equal(stored(models), old_record['models'], 'saved old all retained alternatives')
    equal(record['program_count'], len(DOMAIN), 'new model cardinality')
    equal(record['retained_count'], len(models), 'new retained count')
    equal(record['complete_program_teacher_evaluations'], counts.get('actual', 0), 'actual teacher calls counted separately')
    equal(record['symbolically_unexecuted_program_teacher_evaluations'], counts.get('self_refuted', 0) + counts.get('unknown_exact', 0), 'symbolic teacher slots counted separately')
    equal(record['accounted_program_teacher_slots'], len(DOMAIN) * len(teachers), 'all logical slots accounted')
    equal(record['certificate_evaluations'], len(DOMAIN) * len(teachers), 'all certificate evaluations accounted')
    equal(record['actual_parse_invocations'], 2 * len(teachers), 'unchanged two strict parse passes')
    equal(record['proof_parse_invocations'], len(teachers), 'unchanged strict prepass count')
    equal(record['actual_action_invocations'], sum(row['action_executed'] for row in evidence['rows']), 'actual action count excludes proof work')
    require(record['original_strict_fit_executed'] is False, 'new wrapper does not claim original fitter execution')
    return {'logical_slots': len(evidence['rows']), 'models': len(DOMAIN), 'retained_count': len(models), **counts}


def check_available_complete_records(models, record, saved, record_view=None):
    """saved maps all four fixture-listed paths to already decoded old records.

    This forces comparison to all available complete synthetic matrices while
    letting the harness decode each once and share it across controls.
    """
    paths = fixtures()['saved_complete_synthetic_fit_records']
    equal(set(saved), set(paths), 'all available complete synthetic saved fits supplied')
    return {path: check_fit_record(models, record, saved[path], record_view=record_view) for path in paths}


def check_prefix_record(diagnostic, teachers, record_view=None, old_record=None):
    """Unknown and incomplete suffixes remain unknown, never semantic HOLD."""
    require(diagnostic.get('semantic_HOLD') is False, 'resource/runtime exception is not semantic HOLD')
    require(diagnostic.get('exception') in ('MemoryError', 'TimeoutError', 'RecursionError', 'RuntimeError'), 'primary fault classification')
    evidence = (record_view or canonical_record)(diagnostic)
    counts = _check_rows(evidence, teachers, old_record, complete=False)
    equal(diagnostic['completed_actual_returns'], counts.get('actual', 0), 'actual prefix count')
    equal(diagnostic['completed_symbolic_slots'], counts.get('self_refuted', 0) + counts.get('unknown_exact', 0), 'symbolic prefix count')
    expected_retained = tuple((item['model_index'],) + DOMAIN[item['model_index']]
                              for item in evidence['completed_models'] if item['retained'])
    equal(diagnostic['retained_prefix'], expected_retained, 'complete retained prefix, not final retained set')
    pending_certificates = diagnostic.get('pending_certificate_rows', [])
    raw_certificate = diagnostic.get('raw_pending_certificate')
    if pending_certificates:
        mi = diagnostic['model_index']
        proofs, _ = _independent_model_proof(teachers, mi)
        for ti, certificate in enumerate(pending_certificates):
            equal(certificate['model_index'], mi, 'pending certificate actual model')
            equal(certificate['teacher_witness_ref'], ti, 'pending complete certificate witness order')
            equal(canonical_certificate(certificate), proofs[ti], 'pending complete certificate independently verified')
        if raw_certificate is not None:
            equal(raw_certificate, pending_certificates[-1], 'raw pending certificate is the last complete returned certificate')
    else:
        require(raw_certificate is None, 'unknown certificate has no invented complete value')
    require(len(evidence['rows']) < len(DOMAIN) * len(teachers) or len(evidence['completed_models']) < len(DOMAIN),
            'prefix test must stop before final full fit completion')
    pending = diagnostic.get('pending_return')
    raw = diagnostic.get('raw_pending_return')
    if pending is not None and 'return' in pending:
        require(type(pending['return']) is dict, 'pending actual return retains full dict')
        equal(raw, pending['return'], 'pending raw complete return preserved before/after row commit')
        result = pending['return']
        if result['status'] == 'success':
            require(valid_grid(result['output']), 'pending successful full grid retained')
            require(all(key in result for key in ('shape', 'window', 'period', 'phase_origin')), 'pending success retains all geometry detail')
        else:
            require('reason' in result and 'output' in result, 'pending failed full return retained')
    elif raw is not None:
        require(type(raw) is dict and 'status' in raw and 'output' in raw, 'raw return exists only after an actual complete apply return')
    return {'completed_models': len(evidence['completed_models']), 'logical_prefix': len(evidence['rows']), **counts}


def check_observer_fault(proof, teachers, predicate, exception_type=MemoryError, record_view=None, old_record=None, reporter_exception_type=None):
    """Inject only an exception at a real event; no renderer result fabricated."""
    primary = exception_type('independent necessity observer boundary')
    events = []
    fired = False
    def observer(event):
        nonlocal fired
        events.append(deepcopy(event))
        if fired and reporter_exception_type is not None and event.get('kind') == 'evaluation_exception':
            raise reporter_exception_type('secondary independent observer reporting failure')
        if not fired and predicate(event):
            fired = True
            raise primary
    caught = None
    try:
        proof.fit(deepcopy(teachers), observer)
    except BaseException as error:
        caught = error
    require(fired, 'requested actual observer boundary was reached')
    require(caught is primary, 'original primary exception object propagated')
    diagnostic = getattr(caught, 'evaluation_diagnostic', None)
    require(type(diagnostic) is dict, 'primary exception retains structured prefix')
    summary = check_prefix_record(diagnostic, teachers, record_view, old_record)
    if reporter_exception_type is not None:
        equal(diagnostic['observer_reporting_error']['exception'], reporter_exception_type.__name__, 'secondary reporter failure recorded without replacing primary')
    return {'summary': summary, 'diagnostic': diagnostic, 'events': events}


def check_call_fault(proof, teachers, owner, attribute, ordinal=1, exception_type=MemoryError, record_view=None, old_record=None):
    """Throw before a real parse/certificate/apply call; suffix return unknown."""
    require(type(ordinal) is int and ordinal >= 1, 'positive fault call ordinal')
    original = getattr(owner, attribute)
    primary = exception_type('independent necessity call boundary:' + attribute)
    calls = 0
    def wrapped(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == ordinal:
            raise primary
        return original(*args, **kwargs)
    caught = None
    with patch.object(owner, attribute, wrapped):
        try:
            proof.fit(deepcopy(teachers))
        except BaseException as error:
            caught = error
    require(calls == ordinal and caught is primary, 'exact call fault preserves original primary')
    diagnostic = getattr(caught, 'evaluation_diagnostic', None)
    require(type(diagnostic) is dict, 'call fault retains structured prefix')
    summary = check_prefix_record(diagnostic, teachers, record_view, old_record)
    return {'summary': summary, 'diagnostic': diagnostic, 'fault_attribute': attribute, 'call_ordinal': ordinal}


def fault_teachers(unknown_exact=False):
    """Small literal-derived teachers for early real success/failure/proof faults."""
    case = fixtures()['cases'][0]
    first = {'input': deepcopy(case['input']), 'output': deepcopy(case['target'])}
    second = deepcopy(first)
    second['input'][2][2], second['input'][2][3] = 0, 1
    if unknown_exact:
        second['output'][0][0] = 4
    return [first, second]


def check_fault_prefix(proof, fault_case, exception_type=MemoryError):
    """Execute one specified source-reviewed prefix fault, never a full sweep.

    Names: parse, certificate, apply, witness, model_certificate, self_refuted,
    unknown_exact, success_raw_return, failure_raw_return, actual_row,
    completed_model, secondary_reporter. Run each exception type separately
    under the unchanged process budget; preserve returned full raw evidence.
    """
    teachers = fault_teachers(unknown_exact=fault_case in ('unknown_exact', 'self_refuted'))
    if fault_case == 'parse':
        return check_call_fault(proof, teachers, proof.core, 'parse', 2, exception_type)
    if fault_case == 'certificate':
        return check_call_fault(proof, teachers, proof, 'certify_teacher', 2, exception_type)
    if fault_case == 'apply':
        return check_call_fault(proof, teachers, proof, 'apply', 2, exception_type)
    predicates = {
        'witness': lambda e: e.get('kind') == 'teacher_necessity_witness',
        'model_certificate': lambda e: e.get('kind') == 'model_necessity_certificate',
        'self_refuted': lambda e: e.get('kind') == 'symbolic_model_teacher_slot' and e['exactness'] == 'proven_not_exact',
        'unknown_exact': lambda e: e.get('kind') == 'symbolic_model_teacher_slot' and e['exactness'] == 'unknown_model_refuted_elsewhere',
        'success_raw_return': lambda e: e.get('kind') == 'return_pool_entry' and e['return']['status'] == 'success',
        'failure_raw_return': lambda e: e.get('kind') == 'return_pool_entry' and e['return']['status'] == 'failure',
        'actual_row': lambda e: e.get('kind') == 'model_teacher_return',
        'completed_model': lambda e: e.get('kind') == 'model_completed',
        'secondary_reporter': lambda e: e.get('kind') == 'model_teacher_return'}
    require(fault_case in predicates, 'recognized bounded prefix fault case')
    return check_observer_fault(proof, teachers, predicates[fault_case], exception_type,
                                reporter_exception_type=RecursionError if fault_case == 'secondary_reporter' else None)
