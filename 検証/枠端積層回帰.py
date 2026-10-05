#!/usr/bin/env python3
"""候補008の可搬回帰。sanitized教師再生と自作対照だけを使い、照会しない。

引数不要。配置済みrepo/検証またはproduction-staging/payload/検証から実行する。
cwdに依存しない。stagingではrun-artifacts内、配置済みではOS一時領域に
一意の監査出力を残す。全bridgeを実行せず、固定ASTと一致した公開helperだけを使う。
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import ast
from copy import deepcopy
from dataclasses import asdict, fields, FrozenInstanceError, is_dataclass
from enum import Enum
import gzip
import hashlib
import importlib
import json
from pathlib import Path
import re
import tempfile
import traceback
import types


SCRIPT = Path(__file__).resolve()
PAYLOAD_ROOT = SCRIPT.parents[1]
FIXTURES = SCRIPT.parent / '枠端積層資料'
NATIVE_HELPERS = ('観測へ', '同値原理あり', '候補機構を学習')
PASSED = []
MANIFEST = []


def normalized(value):
    """JSONでtuple/list、整数dictionary key、native dataclassを正規化する。"""
    def convert(item):
        if is_dataclass(item):
            return convert(asdict(item))
        if isinstance(item, Enum):
            return convert(item.value)
        if isinstance(item, dict):
            return {str(k): convert(v) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [convert(v) for v in item]
        return item
    return json.loads(json.dumps(convert(value), ensure_ascii=False, allow_nan=False))


def save(name, value):
    content = json.dumps(normalized(value), ensure_ascii=False, indent=2).encode()
    path = ARTIFACTS / name
    path.write_bytes(gzip.compress(content, mtime=0) if name.endswith('.gz') else content)
    return path


def source(path, purpose):
    path = Path(path).resolve()
    data = path.read_bytes()
    MANIFEST.append({'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(),
                     'bytes': len(data), 'purpose': purpose})
    return data


def fixture(name):
    return json.loads(gzip.decompress(source(FIXTURES / name, 'frozen approved regression fixture')))


def check(name, condition, detail=None):
    if not condition:
        raise AssertionError({'case': name, 'detail': normalized(detail)})
    PASSED.append(name)


def exact(name, actual, expected):
    check(name, normalized(actual) == normalized(expected))


def find_repo():
    candidates = [PAYLOAD_ROOT]
    candidates.extend(parent / 'arc2-second-half' for parent in SCRIPT.parents)
    for path in candidates:
        if ((path / '接続/ARC2/HDS接続.py').is_file()
                and (path / 'HDS/学習系統/v0.4.2/hds学習系統').is_dir()):
            return path.resolve()
    raise RuntimeError('Script-relative actual ARC2 repository and HDS v0.4.2 were not found')


def selected_ast(path, names):
    tree = ast.parse(source(path, 'AST identity check'), filename=str(path))
    nodes = {n.name: n for n in tree.body if getattr(n, 'name', None) in names}
    check('AST definitions complete: ' + path.name, set(nodes) == set(names))
    return nodes


def load_modules(repo):
    root = repo / 'HDS/学習系統/v0.4.2'
    sys.path.insert(0, str(root))
    package_name = '_candidate008_regression_arc2'
    package = types.ModuleType(package_name)
    package.__path__ = [str(PAYLOAD_ROOT / '接続/ARC2'), str(repo / '接続/ARC2')]
    sys.modules[package_name] = package
    adapter = importlib.import_module(package_name + '.枠端積層教材')
    native = importlib.import_module('hds学習系統')
    native_types = importlib.import_module('hds学習系統.型')
    check('isolated staged/deployed adapter import',
          Path(adapter.__file__).resolve() == PAYLOAD_ROOT / '接続/ARC2/枠端積層教材.py')
    for name, module in [('regions', adapter.core.base.regions),
                         ('operations', adapter.core.base.operations),
                         ('holes', adapter.core.base.holes)]:
        check('actual repository primitive: ' + name,
              Path(module.__file__).resolve().parent == repo / '接続/ARC2')
    check('actual HDS class import',
          Path(sys.modules[native.HDS学習実行系.__module__].__file__).resolve().parent
          == root / 'hds学習系統')
    for filename, frozen in fixture('候補固定AST.json.gz').items():
        nodes = selected_ast(PAYLOAD_ROOT / '接続/ARC2' / filename, frozen)
        exact('original prospective AST unchanged: ' + filename,
              {name: ast.dump(node, include_attributes=False) for name, node in nodes.items()}, frozen)
    frozen = fixture('公開helper固定AST.json.gz')
    nodes = selected_ast(repo / '接続/ARC2/HDS接続.py', NATIVE_HELPERS)
    exact('three native helper ASTs unchanged',
          {name: ast.dump(node, include_attributes=False) for name, node in nodes.items()}, frozen)
    # Nothing else in the changing live bridge is imported or executed.
    scope = {'deepcopy': deepcopy, '学習入力': native_types.学習入力,
             '観測事実': native_types.観測事実}
    extracted = ast.Module(body=[nodes[name] for name in NATIVE_HELPERS], type_ignores=[])
    exec(compile(ast.fix_missing_locations(extracted), str(repo / '接続/ARC2/HDS接続.py'), 'exec'), scope)
    save('native-helper-ast-evidence.json', {'scope': list(NATIVE_HELPERS), 'frozen_ast': frozen,
          'live_ast_equal': True, 'whole_bridge_identity_claim': False,
          'bridge_execution': 'only three extracted helpers; no bridge imports or registration'})
    return adapter, native, scope


def validate_teacher_contract(adapter, teachers):
    cases = [('none', None, 'invalid_teacher_container'),
             ('mapping', {}, 'invalid_teacher_container'),
             ('empty', [], 'too_few_distinct_teachers'),
             ('singleton', teachers[:1], 'too_few_distinct_teachers'),
             ('duplicate', [teachers[0], deepcopy(teachers[0])], 'duplicate_teacher_inputs')]
    extra = deepcopy(teachers[:2]); extra[0]['extra'] = 1
    missing = deepcopy(teachers[:2]); del missing[0]['output']
    wrong_pair = [None, teachers[1]]
    cases.extend([('extra_field', extra, 'invalid_teacher_pair'),
                  ('missing_field', missing, 'invalid_teacher_pair'),
                  ('nonmapping_pair', wrong_pair, 'invalid_teacher_pair')])
    invalid_grids = {'bool': [[True]], 'float': [[1.0]], 'string': [['1']],
                     'negative': [[-1]], 'ten': [[10]], 'empty': [], 'empty_row': [[]],
                     'ragged': [[0], [0, 1]], 'tuple_grid': ((0,),),
                     'tuple_row': [(0,)], 'too_tall': [[0]] * 31,
                     'too_wide': [[0] * 31]}
    for field in ('input', 'output'):
        for name, grid in invalid_grids.items():
            bad = deepcopy(teachers[:2]); bad[0][field] = grid
            cases.append((field + '_' + name, bad, 'invalid_teacher_pair'))
    rows = []
    original_evaluate = adapter.core.Evaluator.evaluate
    def forbidden_evaluate(*_args, **_kwargs):
        raise AssertionError('Invalid teacher set must not evaluate any program')
    adapter.core.Evaluator.evaluate = forbidden_evaluate
    try:
        for name, value, reason in cases:
            before = deepcopy(value); events = []
            models, record = adapter.fit(value, observer=lambda e: events.append(deepcopy(e)))
            exact('invalid teachers rejected: ' + name, (models, record.get('failure')), ((), reason))
            check('validation precedes evaluator: ' + name,
                  len(events) == 1 and events[0]['kind'] == 'teacher_validation' and not events[0]['valid'])
            exact('invalid teachers unmodified: ' + name, value, before)
            rows.append({'case': name, 'fit_record': record, 'events': events})
    finally:
        adapter.core.Evaluator.evaluate = original_evaluate
    valid, detail = adapter.validate_teachers(teachers[:2])
    check('two distinct teachers meet fit minimum', valid and detail['teacher_fit_minimum'] == 2)
    valid, _ = adapter.validate_teachers(tuple(teachers[:2]))
    check('tuple of distinct teachers accepted', valid)
    for grid in ([[0]], [[9] * 30] * 30):
        check('inclusive ARC bounds accepted ' + str(len(grid)), adapter.core.base.valid_grid(grid))
    save('teacher-validation.json.gz', rows)


def native_runs(adapter, native, helpers, fitted, teachers):
    model_identity = fitted.モデル群
    all_rows = []
    query_calls = []
    original_query = native.HDS学習実行系.照会
    def forbidden_query(*_args, **_kwargs):
        query_calls.append(True)
        raise AssertionError('HDS query is prohibited in this regression')
    native.HDS学習実行系.照会 = forbidden_query
    try:
        class RecordingHDS(native.HDS学習実行系):
            def __init__(self, minimum):
                super().__init__(最小支持数=minimum)
                self.calls = []

            def 実行(self, value):
                before = deepcopy(value)
                result = super().実行(value)
                exhaust = native.最小排気系().排出する(result)
                self.calls.append({'input': before, 'result': result, 'exhaust': exhaust})
                exact('native execution input immutable', value, before)
                return result

        for minimum in (3, 4, 5):
            machine = RecordingHDS(minimum)
            check('fresh native ledger at minimum ' + str(minimum), machine.台帳.全取得() == {})
            candidates = []
            def candidate(grid, policy):
                check('identical six immutable models reused', fitted.モデル群 is model_identity)
                output, detail = fitted.候補(grid, policy)
                candidates.append({'input': deepcopy(grid), 'output': deepcopy(output), 'detail': deepcopy(detail)})
                return output, detail
            boundary = 'candidate008/approved-sanitized-teacher-replay'
            task = {'train': deepcopy(teachers)}
            before = deepcopy(task)
            learned = helpers['候補機構を学習'](machine, task, [], boundary, candidate)
            exact('native teacher set unmodified at minimum ' + str(minimum), task, before)
            ledger = machine.台帳.JSON相当()
            observations = machine.台帳.取得('観測台帳')
            references = tuple(item.経験識別子 for item in observations)
            result = machine.calls[-1]['result']
            equality = [principle for principle in result.有効原理群
                        if helpers['同値原理あり']([principle], boundary)]
            exhaust = machine.calls[-1]['exhaust']
            admission = ('ADMIT' if learned['採用可'] and learned['同値採用']
                         and not result.係争中原理群 and exhaust.状態 == '出力' else 'HOLD')
            evidence = {'minimum_support': minimum, 'teacher_fit_reused': True,
                        'model_count': len(model_identity), 'native_helper_record': learned,
                        'candidate_replays': candidates, 'native_calls': machine.calls,
                        'ledger': ledger, 'equality_principles': equality,
                        'actual_observation_references': references,
                        'quarantined': result.係争中原理群,
                        'native_equality_admission': learned['同値採用'],
                        'candidate_admission_gate': admission,
                        'gate_basis': 'actual native equality, exact teacher replay, quarantine and exhaust; no support cutoff',
                        'raw_native_exhaust_status': exhaust.状態,
                        'raw_native_exhaust_prediction_count': len(exhaust.内容['予測群']),
                        'query_answer_claim': False}
            save('native-minimum-' + str(minimum) + '.json.gz', evidence)
            all_rows.append(evidence)
            check('all four native observations at minimum ' + str(minimum),
                  len(machine.calls) == len(observations) == 4
                  and learned['現在観測数'] == 4 and learned['事前観測数'] == 0
                  and learned['隔離数'] == 0 and not result.係争中原理群)
            check('candidate exact all4 at minimum ' + str(minimum),
                  learned['採用可'] is True and learned['状態'] == '全教師再現')
            for index, observation in enumerate(observations):
                exact('actual native observation values %d/%d' % (minimum, index),
                      observation.原入力, {'候補': teachers[index]['output'], '出力': teachers[index]['output']})
                check('native observation boundary %d/%d' % (minimum, index), observation.対象系境界 == boundary)
            # Threshold decisions are read from native HDS, never synthesized by a cutoff.
            check('native equality decision at minimum ' + str(minimum),
                  learned['同値採用'] is (minimum in (3, 4)))
            exact('native-derived candidate admission gate at minimum ' + str(minimum),
                  admission, 'ADMIT' if minimum in (3, 4) else 'HOLD')
            if minimum in (3, 4):
                check('native equality principle exists at minimum ' + str(minimum), bool(equality))
                for principle in equality:
                    exact('equality cites exactly all4 observations at minimum ' + str(minimum),
                          principle.根拠参照群, references)
                    check('equality has no counterexample refs at minimum ' + str(minimum),
                          not principle.反証参照群)
            else:
                check('native minimum5 remains without equality admission', not equality)
                check('native minimum5 has no predicted output', not exhaust.内容['予測群'])
            exact('same fitted models after native run', fitted.モデル群, model_identity)
        check('zero HDS queries', query_calls == [])
    finally:
        native.HDS学習実行系.照会 = original_query
    return [{'minimum_support': row['minimum_support'],
             'native_equality_admission': row['native_equality_admission'],
             'candidate_admission_gate': row['candidate_admission_gate'],
             'raw_native_exhaust_status': row['raw_native_exhaust_status'],
             'raw_native_exhaust_prediction_count': row['raw_native_exhaust_prediction_count'],
             'actual_observation_count': len(row['actual_observation_references']),
             'quarantine_count': len(row['quarantined'])} for row in all_rows]


def resource_failures(adapter, teachers, fitted, frozen_fit, frozen_controls):
    outcomes = []
    flat = [(row['program_number'], ti, row['program'], result, row['teacher_exacts'][ti])
            for row in frozen_fit for ti, result in enumerate(row['teacher_returns'])]
    original_evaluate = adapter.core.Evaluator.evaluate
    scenarios = [('predict_after_complete_model_prefix', 2, 6),
                 ('fit_after_complete_model_prefix', 28 * 4, 240 * 4),
                 ('fit_after_complete_teacher', 28 * 4 + 1, 240 * 4)]
    for error_class in (MemoryError, RecursionError, TimeoutError):
        for scenario, fail_after, planned in scenarios:
            events = []; seen = 0
            expected_exception = error_class('injected ' + scenario)
            def injected(evaluator, program):
                nonlocal seen
                if seen == fail_after:
                    raise expected_exception
                result = original_evaluate(evaluator, program)
                seen += 1
                return result
            adapter.core.Evaluator.evaluate = injected
            teacher_input = deepcopy(teachers)
            before = deepcopy(teacher_input)
            raised = None; returned = False
            try:
                if scenario.startswith('predict'):
                    adapter.predict(teacher_input[0]['input'], fitted.モデル群,
                                    observer=lambda event: events.append(deepcopy(event)))
                else:
                    adapter.fit(teacher_input, observer=lambda event: events.append(deepcopy(event)))
                returned = True
            except BaseException as error:
                raised = error
            finally:
                adapter.core.Evaluator.evaluate = original_evaluate
            label = error_class.__name__ + '/' + scenario
            check('resource exception propagates unchanged: ' + label,
                  raised is expected_exception and not returned)
            failures = [event for event in events if event['kind'] == 'evaluation_exception']
            check('one resource exception observer record: ' + label, len(failures) == 1)
            failure = failures[0]
            expected = {'stage': 'retained_model_return' if scenario.startswith('predict') else 'model_teacher_return',
                        'model_index': fail_after if scenario.startswith('predict') else fail_after // 4,
                        'exception': error_class.__name__, 'completed_returns': fail_after,
                        'planned_returns': planned, 'unevaluated_returns': planned - fail_after,
                        'semantic_HOLD': False}
            if not scenario.startswith('predict'):
                expected['teacher_index'] = fail_after % 4
            exact('precise resource failure indices and counts: ' + label,
                  {key: failure[key] for key in expected}, expected)
            check('resource exception never produces semantic HOLD: ' + label,
                  not any(event['kind'] == 'retained_consensus' for event in events))
            if scenario.startswith('predict'):
                returns = [event for event in events if event['kind'] == 'retained_model_return']
                exact('complete prior model returns preserved: ' + label,
                      [event['record'] for event in returns],
                      frozen_controls[0]['result']['returns'][:fail_after])
                exact('resource model return indices: ' + label,
                      [event['model_index'] for event in returns], list(range(fail_after)))
            else:
                returns = [event for event in events if event['kind'] == 'model_teacher_return']
                actual = [(event['model_index'], event['teacher_index'], event['program'],
                           event['result'], event['exact']) for event in returns]
                exact('complete prior teacher returns preserved: ' + label, actual, flat[:fail_after])
                completed = [event['record'] for event in events if event['kind'] == 'model_completed']
                exact('complete model rows preserved: ' + label, completed, frozen_fit[:fail_after // 4])
            exact('resource exception input immutable: ' + label, teacher_input, before)
            record = {'case': label, 'exception_identity_preserved': raised is expected_exception,
                      'returned_semantic_value': returned, 'events': events}
            save('resource-' + label.replace('/', '-') + '.json.gz', record)
            outcomes.append({'case': label, 'failure': failure, 'prior_returns': len(returns)})
    return outcomes


def run():
    repo = find_repo()
    adapter, native, helpers = load_modules(repo)
    teachers = fixture('教師.json.gz')
    original_teachers = deepcopy(teachers)
    frozen_fit = fixture('全240教師返値.json.gz')
    frozen_models = fixture('保持モデル.json.gz')
    frozen_controls = fixture('全対照返値.json.gz')
    expectations = fixture('期待対照.json.gz')
    check('four sanitized training teachers', len(teachers) == 4)
    check('240 complete frozen teacher rows', len(frozen_fit) == 240
          and all(len(row['teacher_returns']) == 4 for row in frozen_fit))
    check('87 complete six-model frozen controls', len(frozen_controls) == 87
          and all(len(row['result']['returns']) == 6 for row in frozen_controls))
    validate_teacher_contract(adapter, teachers)
    audit = {}; events = []
    fitted = adapter.枠端積層教材(teachers, 監査=audit,
                            観測=lambda event: events.append(deepcopy(event)))
    save('all240-teacher-fit.json.gz', audit)
    save('all240-teacher-observer-events.json.gz', events)
    save('fitted-model-state.json', asdict(fitted))
    exact('all 240 x 4 teacher returns exact fixture parity', audit['all_program_teacher_returns'], frozen_fit)
    exact('six retained immutable models exact fixture parity', fitted.展開モデル(), frozen_models)
    check('all4 fit preserves six candidates', fitted.適合数 == 6 and fitted.教師数 == 4 and fitted.不足理由 is None)
    check('fit returns all960 incremental teacher observations',
          sum(event['kind'] == 'model_teacher_return' for event in events) == 960)
    check('fit returns all240 complete rows', sum(event['kind'] == 'model_completed' for event in events) == 240)
    exact('fitted adapter stores only bounded immutable model metadata',
          [field.name for field in fields(fitted)], ['モデル群', '教師数', '教師fit最小数', '適合数', '不足理由'])
    check('immutable nested model tuples', isinstance(fitted.モデル群, tuple)
          and all(isinstance(model, tuple) and len(model) == 5
                  and all(type(v) in (int, str) for v in model) for model in fitted.モデル群))
    check('no dynamic grid storage on adapter', not hasattr(fitted, '__dict__'))
    try:
        fitted.教師数 = 99
    except FrozenInstanceError:
        frozen_rejects = True
    else:
        frozen_rejects = False
    check('adapter frozen assignment rejects mutation', frozen_rejects)
    model_state = deepcopy(fitted.モデル群)
    fit_state = deepcopy(audit)
    controls = []; control_events = []
    expected_by_name = {record['name']: record for record in expectations}
    for frozen in frozen_controls:
        name = frozen['name']
        grid = deepcopy(frozen['result']['input_view']['input'])
        before = deepcopy(grid)
        palette = re.fullmatch(r'palette_shift_(\d+)_teacher_(\d+)', name)
        if palette:
            shift, teacher_index = map(int, palette.groups())
            exact('palette control input cyclic shift: ' + name, grid,
                  [[(v + shift) % 10 for v in row] for row in teachers[teacher_index]['input']])
            models = tuple(((model[0] + shift) % 10,) + model[1:] for model in fitted.モデル群)
            check('palette adjusts cue color only: ' + name,
                  all(new[1:] == old[1:] for old, new in zip(fitted.モデル群, models)))
        else:
            models = fitted.モデル群
        observed = []
        output, record = adapter.predict(grid, models, observer=lambda e: observed.append(deepcopy(e)))
        exact('full six-model control return: ' + name, record, frozen['result'])
        check('control evaluates all six retained models: ' + name,
              sum(event['kind'] == 'retained_model_return' for event in observed) == 6)
        exact('control input unmodified: ' + name, grid, before)
        exact('control output matches record: ' + name, output, record['output'])
        if name in expected_by_name:
            expected = expected_by_name[name]
            exact('independent expected output: ' + name, output, expected['expected_output'])
            check('frozen expected control was passed: ' + name, expected['passed'] is True)
        controls.append({'name': name, 'result': record})
        control_events.append({'name': name, 'events': observed})
    save('all87-control-returns.json.gz', controls)
    save('all87-control-observer-events.json.gz', control_events)
    exact('all87 x 6 full control parity', controls, frozen_controls)
    by_name = {row['name']: row['result'] for row in controls}
    for name in ('diagonal_touch_C4_C8_counterexample', 'odd_center_counterexample'):
        check('mandatory fail-closed HOLD: ' + name,
              by_name[name]['status'] == 'HOLD' and by_name[name]['output'] is None)
    exact('all teachers unmodified after fit and controls', teachers, original_teachers)
    exact('fit audit outputs unmodified by later controls', audit, fit_state)
    exact('immutable models unmodified by controls', fitted.モデル群, model_state)
    native_evidence = native_runs(adapter, native, helpers, fitted, teachers)
    resources = resource_failures(adapter, teachers, fitted, frozen_fit, frozen_controls)
    # Previously returned grids and their evidence must survive later predictions/native use/injections.
    exact('prior control input/output evidence unmodified at end', controls, frozen_controls)
    exact('original teachers unmodified at end', teachers, original_teachers)
    exact('same six model state unmodified at end', fitted.モデル群, model_state)
    for name, module in sorted(sys.modules.items()):
        if name.startswith(('_candidate008_regression_arc2.', 'hds学習系統')):
            path = getattr(module, '__file__', None)
            if path:
                source(path, 'actual imported module ' + name)
    source(SCRIPT, 'executed portable regression')
    save('import-source-manifest.json', {'script_root': str(PAYLOAD_ROOT), 'actual_repo': str(repo),
          'actual_HDS_root': str(repo / 'HDS/学習系統/v0.4.2'), 'sources': MANIFEST})
    return {'repo': str(repo), 'teacher_count': 4, 'enumerated_models': 240,
            'teacher_returns': 960, 'retained_models': 6, 'control_count': 87,
            'control_returns': 522, 'native_runs': native_evidence, 'resource_cases': resources,
            'query_count': 0, 'official_task_test_used': False,
            'fixture_scope': 'sanitized teacher replay and previously authored synthetic controls',
            'bridge_identity_scope': list(NATIVE_HELPERS)}


if __name__ == '__main__':
    staging = PAYLOAD_ROOT.parent if PAYLOAD_ROOT.name == 'payload' else None
    artifact_parent = None
    if staging is not None and (staging / 'native_public.py').is_file():
        artifact_parent = staging / 'run-artifacts'
        artifact_parent.mkdir(exist_ok=True)
    ARTIFACTS = Path(tempfile.mkdtemp(prefix='candidate008-regression-', dir=artifact_parent))
    summary = {'successful': False, 'tests_run': 0, 'passed_cases': [], 'artifacts': str(ARTIFACTS)}
    try:
        summary.update(run())
        summary['successful'] = True
    except BaseException as error:
        summary['failure'] = {'exception': type(error).__name__, 'message': str(error),
                              'traceback': traceback.format_exc()}
    summary.update(tests_run=len(PASSED), passed_cases=PASSED)
    if not (type(summary['successful']) is bool and type(summary['tests_run']) is int
            and type(summary['passed_cases']) is list
            and all(type(case) is str for case in summary['passed_cases'])):
        raise TypeError('Invalid regression summary schema')
    save('summary.json', summary)
    if not (ARTIFACTS / 'import-source-manifest.json').exists():
        save('partial-source-manifest.json', MANIFEST)
    print(json.dumps({'successful': summary['successful'], 'tests_run': summary['tests_run'],
                      'passed_cases': summary['passed_cases'], 'artifacts': str(ARTIFACTS),
                      'failure': summary.get('failure')}, ensure_ascii=False))
    raise SystemExit(0 if summary['successful'] else 1)
