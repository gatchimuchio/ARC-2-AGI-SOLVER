#!/usr/bin/env python3
"""Portable candidate021 public teacher/control regression; no query or scoring."""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse, ast, copy, dataclasses, enum, gzip, hashlib, importlib, json, tempfile, traceback, types
from pathlib import Path

P = Path(__file__).resolve().parents[1]
F = Path(__file__).resolve().parent/'有限字形視野資料'
PASSED = []
SCALARS = (type(None), bool, int, float, str)

def serial(v):
    if type(v) in SCALARS: return v
    if dataclasses.is_dataclass(v): return serial(dataclasses.asdict(v))
    if isinstance(v, enum.Enum): return serial(v.value)
    if isinstance(v, dict): return {str(k): serial(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)): return [serial(x) for x in v]
    if isinstance(v, (set, frozenset)): return [serial(x) for x in sorted(v)]
    raise TypeError(type(v).__name__)

def encoded(v): return json.dumps(serial(v), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
def equal(a, b): return encoded(a) == encoded(b)
def tupleize(v): return tuple(tupleize(x) for x in v) if isinstance(v, list) else v
def read(name): return json.loads(gzip.decompress((F/name).read_bytes()))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(out, name, value):
    data = encoded(value).encode()
    with (out/name).open('xb') as file: file.write(gzip.compress(data, mtime=0) if name.endswith('.gz') else data)
def check(name, value=True):
    assert value, name
    PASSED.append(name)

class Journal:
    def __init__(self, path):
        self.file = gzip.open(path, 'xt', compresslevel=1)
        self.counts = {}
    def __call__(self, event):
        self.file.write(encoded(event)+'\n'); self.file.flush()
        kind = event['kind']; self.counts[kind] = self.counts.get(kind, 0)+1
    def close(self): self.file.close()

def load(out, repository_root):
    deployed = (P/'HDS/学習系統/v0.4.2/hds学習系統').is_dir()
    repo = Path(repository_root).resolve() if repository_root else P if deployed else P.parent/'source-evidence/repository'
    snapshot = not deployed and repository_root is None
    manifest = read('依存固定.json.gz')
    for item in manifest['pure_dependencies']+manifest['native']['core']:
        assert sha(repo/item['path']) == item['sha256'], item['path']
    for item in manifest['strict012']:
        assert sha(P/item['path']) == item['sha256'], item['path']
    assert sha(P/'接続/ARC2/有限字形視野候補.py') == manifest['frozen_view_sha256']
    bridge = repo/'接続/ARC2/HDS接続.py'
    if snapshot: assert sha(bridge) == manifest['native']['bridge_sha256']
    fixed = manifest['native']['ast']
    nodes = {n.name: n for n in ast.parse(bridge.read_bytes()).body if isinstance(n, ast.FunctionDef) and n.name in fixed}
    assert {k: ast.dump(n, include_attributes=False) for k, n in nodes.items()} == fixed
    check('exact old012 core adapter memo proof and frozen view bytes; accepted dependencies and native3 ASTs')
    original = ast.parse(gzip.decompress((F/'old012-prototype.py.gz').read_bytes()))
    current = ast.parse((P/'接続/ARC2/符号字形辞書候補.py').read_bytes())
    grammar = lambda tree: ast.dump(next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Grammar'), include_attributes=False)
    assert grammar(original) == grammar(current)
    pkg = types.ModuleType('_candidate021_regression')
    pkg.__path__ = [str(P/'接続/ARC2'), str(repo/'接続/ARC2')]
    sys.modules[pkg.__name__] = pkg
    adapter = importlib.import_module(pkg.__name__+'.有限字形視野教材')
    for module, expected in manifest['helper_ast'].items():
        source = ast.parse((repo/'接続/ARC2'/f'{module}.py').read_bytes())
        actual = {n.name: ast.dump(n, include_attributes=False) for n in source.body if isinstance(n, ast.FunctionDef) and n.name in expected}
        assert actual == expected
        imported = importlib.import_module(pkg.__name__+'.'+module)
        for name in expected:
            used = adapter.crop_grid if name == 'crop_grid' else getattr(adapter.strict.core, name)
            assert used is getattr(imported, name)
    check('original Grammar AST and direct existing strict validator components crop identity')
    sys.path.insert(0, str(repo/'HDS/学習系統/v0.4.2'))
    native = importlib.import_module('hds学習系統'); nt = importlib.import_module('hds学習系統.型')
    helpers = {'deepcopy': copy.deepcopy, '学習入力': nt.学習入力, '観測事実': nt.観測事実}
    exec(compile(ast.Module(body=list(nodes.values()), type_ignores=[]), str(bridge), 'exec'), helpers)
    save(out, 'source-verification.json', {'repository': str(repo), 'snapshot_mode': snapshot, 'deployed_mode': deployed,
         'repository_argument': repository_root, 'bridge_actual_sha256': sha(bridge), 'manifest': manifest,
         'whole_bridge_executed': False, '課題を解く_AST_pinned': False})
    return adapter, native, helpers

def fit_and_teachers(adapter, teachers, out):
    audit = {}; original = copy.deepcopy(teachers); compared = 0
    journal = Journal(out/'strict-fit-events.jsonl.gz')
    raw = gzip.open(F/'strict-fit-all-hypotheses.jsonl.gz', 'rt')
    def observe(event):
        nonlocal compared
        journal(event)
        if event['kind'] == 'hypothesis_completed':
            line = raw.readline(); assert line and equal(event['record'], json.loads(line))
            compared += 1
    try: fitted = adapter.有限字形視野教材(teachers, audit, observe)
    finally: journal.close()
    assert not raw.readline(); raw.close()
    expected = read('strict-fit-result.json.gz')
    assert equal(fitted.モデル群, expected['retained_models']) and equal({k: v for k, v in audit.items() if k not in ('teacher_count', 'teacher_fit_minimum')}, expected['record'])
    assert teachers == original and fitted.適合数 == 1 and compared == 12100
    check('all12100 original strict hypotheses and complete fit returns exact; one immutable retained model')
    returns = []
    saved = read('teacher-returns.json.gz')
    for i, pair in enumerate(teachers):
        events = []; result = fitted.候補(pair['input'], {}, events.append)
        assert equal(result, saved[i]['consensus_return']) and result[0] == pair['output']
        assert sum(e['kind'] == 'view_model_return' for e in events) == fitted.適合数
        returns.append({'teacher_index': i, 'return': result, 'events': events})
    save(out, 'fit-and-four-teacher-returns.json.gz', {'teachers': teachers, 'models': fitted.モデル群, 'fit': audit,
         'returns': returns, 'hypotheses_compared': compared, 'event_counts': journal.counts})
    check('all4 teachers current full view complete returns exactly reproduce original strict teachers')
    return fitted

def source_roles(adapter, grid, model, dr=0, dc=0):
    bg, shape, anchor, corner, entries = model
    keys = dict(entries); parts = []
    for color in sorted({v for row in grid for v in row}-{bg}-set(keys)):
        for part in adapter.strict.core.color_components(grid, color, include_diagonal=True):
            t,l,b,r = part['bbox']
            parts.append({'color': color, 'size': part['size'], 'bbox': (t+dr,l+dc,b+dr,r+dc),
                          'cells': sorted((r+dr,c+dc) for r,c in part['cells'])})
    return {'tokens': sorted((r+dr,c+dc,v) for r,row in enumerate(grid) for c,v in enumerate(row) if v in keys),
            'foreground': sorted((r+dr,c+dc,v) for r,row in enumerate(grid) for c,v in enumerate(row) if v != bg),
            'payload_components': parts}

def views_and_controls(adapter, out):
    rows = []
    original_render = adapter.strict.core.Grammar.render
    for case in read('synthetic-crop-returns.json.gz'):
        model = tupleize(case['model']); grid = case['source_complete_crop']; before = copy.deepcopy(grid)
        calls = []
        def capture(grammar, padded, selected):
            calls.append(copy.deepcopy(padded)); return original_render(grammar, padded, selected)
        adapter.strict.core.Grammar.render = capture
        try: result = adapter.predict(grid, (model,))
        finally: adapter.strict.core.Grammar.render = original_render
        assert result[0] == case['oracle'] and equal(result[1]['returns'][0], case['view_return'])
        assert grid == before and len(calls) == 1 and calls[0] == case['padded_input']
        dr,dc = result[1]['returns'][0][1]['translation']
        roles = source_roles(adapter, grid, model)
        assert equal(roles, source_roles(adapter, calls[0], model, -dr,-dc)) and equal(roles, case['source_roles'])
        assert equal(roles, case['large_source_roles_normalized'])
        rows.append({'model': model, 'input': grid, 'return': result, 'padded_input': calls[0], 'source_roles': roles})
    save(out, 'all32-current-source-role-crops.json.gz', rows)
    check('all32 current view actual crops background padding and complete source roles exact', len(rows) == 32)
    rows = []
    for case in read('independent-controls.json.gz'):
        if case['name'].startswith('resource_exception_'): continue
        grid = case['input']
        if case['name'] == 'tuple_container_invalid': grid = tuple(tuple(r) for r in grid)
        if case['name'] == 'tuple_row_invalid': grid = [tuple(r) for r in grid]
        models = tupleize(case['models']) if 'models' in case else (tupleize(case['model']),)
        events = []; result = adapter.predict(grid, models, events.append)
        expected = case['return'] if 'models' in case else case['view_return']
        assert equal(result if 'models' in case else result[1]['returns'][0], expected), case['name']
        assert result[1]['all_retained_models_evaluated'] == len(models)
        assert sum(e['kind'] == 'view_model_return' for e in events) == len(models)
        rows.append({'name': case['name'], 'input': grid, 'models': models, 'return': result, 'events': events})
    save(out, 'all31-current-view-controls.json.gz', rows)
    check('31 frozen semantic controls including ≤30 label-overpad HOLD source guards full rectangles all-model crop consensus', len(rows) == 31)

def schema_proof_and_immutability(adapter, teachers, fitted, out):
    rows = []; invalid = [None, {}, [], teachers[:1], [teachers[0], teachers[0]], [dict(teachers[0], extra=1), teachers[1]],
             [None, teachers[1]], [{'input': [[0]]}, teachers[1]]]
    grids = [None, [], [[]], [[True]], [[1.0]], [[10]], [[-1]], [[0],[0,0]], ((0,),), [(0,)], [[0]*31], [[0]]*31]
    for key in ('input','output'):
        for grid in grids:
            pair = copy.deepcopy(teachers[:2]); pair[0][key] = grid; invalid.append(pair)
    for value in invalid:
        audit = {}; events = []; obj = adapter.有限字形視野教材(value, audit, events.append)
        assert obj.モデル群 == () and audit.get('failure') and len(events) == 1
        rows.append({'teachers': value, 'record': audit, 'events': events})
    state = dataclasses.asdict(fitted); detached = fitted.記録(); detached['保持候補'].clear()
    assert dataclasses.asdict(fitted) == state and not hasattr(fitted, '__dict__')
    def immutable(v): return (type(v) is tuple and all(immutable(x) for x in v)) or type(v) is int
    assert all(immutable(x) for x in dataclasses.astuple(fitted))
    try: fitted.教師数 = 0
    except dataclasses.FrozenInstanceError: pass
    else: raise AssertionError('mutable fitted state')
    mutated = copy.deepcopy(teachers); obj = adapter.有限字形視野教材(mutated); saved = dataclasses.asdict(obj)
    mutated[0]['input'].clear(); mutated[0]['output'].clear()
    assert dataclasses.asdict(obj) == saved and obj.モデル群 == fitted.モデル群
    def hostile(event): event.clear()
    obj = adapter.有限字形視野教材(teachers, 観測=hostile)
    assert obj.モデル群 == fitted.モデル群 and all(obj.候補(p['input'], {}, hostile)[0] == p['output'] for p in teachers)
    check('strict teacher schema immutable target-free tuple and detached audit/observer records')
    a = adapter.strict._ObservedGrammar(None, 'a'); b = adapter.strict._ObservedGrammar(None, 'b')
    sample = [[4,0],[0,4]]; first = a.components(sample,4,True); first[0]['cells'].clear()
    assert len(a.components(sample,4,True)[0]['cells']) == 2 and not b._component_records
    assert a._modes is not b._modes
    check('exact inherited memoization is invocation-local and returns fresh component records')
    pairs = []
    for coordinates in (((2,1),(2,2)), ((1,2),(2,2))):
        grid = [[0]*5 for _ in range(5)]; grid[0][0] = 2
        outgrid = [[0]*5 for _ in range(5)]
        for r,c in coordinates: grid[r][c] = outgrid[r][c] = 4
        pairs.append({'input':grid,'output':outgrid})
    events = []; models, audit = adapter.fit(pairs, events.append)
    assert models == () and audit['exhausted'] is False and audit['hypotheses'] == 0
    proof = audit['proof']; assert proof['enumerated_hypotheses'] == 0 and proof['proven_rejected_hypotheses'] == 900
    raw = []; grammar = adapter.strict.core.Grammar(adapter.strict.core.valid_grid, adapter.strict.core.color_components)
    rawmodels, rawrecord = grammar.fit(pairs, raw.append)
    assert rawmodels == () and rawrecord['hypotheses'] == len(raw) == 900 and all(not h['accepted'] for h in raw)
    rows.append({'name':'whole-domain shape proof versus complete raw enumeration','teachers':pairs,'proof_fit':audit,
                 'proof_events':events,'raw_record':rawrecord,'raw_hypotheses':raw})
    save(out, 'schema-proof-immutability.json.gz', rows)
    check('exact whole-domain proof:900 symbolically rejected,0 executed; independent raw900 all rejected')

def resources(adapter, teachers, fitted, out):
    rows = []; core = adapter.strict.core
    original_parse = core.Grammar.parse; original_render = core.Grammar.render
    for error in (MemoryError, RecursionError, TimeoutError):
        for stage in ('fit_parse', 'fit_render', 'view_render'):
            events = []; calls = [0]; stop = 5 if stage == 'fit_parse' else 1
            original = original_parse if stage == 'fit_parse' else original_render
            def interrupt(self, *args, **kwargs):
                if calls[0] == stop: raise error('injected after complete prefix')
                calls[0] += 1; return original(self, *args, **kwargs)
            setattr(core.Grammar, 'parse' if stage == 'fit_parse' else 'render', interrupt)
            try:
                if stage == 'view_render': adapter.predict(teachers[0]['input'], fitted.モデル群*3, events.append)
                else: adapter.fit(teachers, events.append)
            except error:
                exception = events[-1]
                assert exception['semantic_HOLD'] is False and exception['exception'] == error.__name__
                if stage == 'view_render':
                    assert exception['kind'] == 'view_evaluation_exception' and len(exception['completed_view_prefix']) == 1
                    assert sum(e['kind'] == 'view_model_return' for e in events) == 1
                    assert exception['completed_view_prefix'][0][0] == teachers[0]['output']
                elif stage == 'fit_parse':
                    assert exception['completed_hypotheses'] == 1 and exception['completed_parse_returns'] == 5
                    assert len(exception['partial_current_hypothesis']) == 1
                else:
                    assert exception['completed_render_returns'] == 1 and len(exception['completed_render_prefix']) == 1
                    assert exception['completed_render_prefix'][0][0] == teachers[0]['output']
                rows.append({'stage':stage,'error':error.__name__,'events':events})
            else: raise AssertionError('resource exception swallowed')
            finally: core.Grammar.parse = original_parse; core.Grammar.render = original_render
    save(out, 'resource-prefix-controls.json.gz', rows)
    check('9 resource controls propagate MemoryError RecursionError TimeoutError with fit/teacher/model prefixes', len(rows) == 9)

def native_cycles(adapter, native, helpers, fitted, teachers, out):
    identity = fitted.モデル群; state = dataclasses.asdict(fitted); results = []
    class Recording(native.HDS学習実行系):
        def __init__(self, minimum): super().__init__(最小支持数=minimum); self.calls = []
        def 実行(self, value):
            result = super().実行(value); exhaust = native.最小排気系().排出する(result)
            self.calls.append({'input':value,'result':result,'exhaust':exhaust}); return result
        def 照会(self,*a,**k): raise AssertionError('query prohibited')
    original_fit = adapter.fit
    def no_refit(*a,**k): raise AssertionError('reuse identical fitted tuple')
    adapter.fit = no_refit
    try:
        for minimum in (3,4,5):
            machine = Recording(minimum); assert machine.台帳.全取得() == {}; calls = []
            def candidate(grid, policy):
                assert fitted.モデル群 is identity
                output, record = fitted.候補(grid, policy)
                calls.append({'input':grid,'output':output,'record':record}); return output,record
            boundary = 'ARC有限字形視野'
            record = helpers['候補機構を学習'](machine, {'train':teachers}, (), boundary, candidate)
            assert record['採用可'] and record['同値採用'] == (minimum <= 4)
            assert record['現在観測数'] == 4 and record['事前観測数'] == record['隔離数'] == 0
            observations = machine.台帳.取得('観測台帳')
            assert len(observations) == len(calls) == 4 and len({encoded(o.原入力) for o in observations}) == 4
            refs = tuple(o.経験識別子 for o in observations)
            equality = [p for p in machine.calls[-1]['result'].有効原理群 if helpers['同値原理あり']([p],boundary)]
            assert bool(equality) == (minimum <= 4)
            assert all(p.根拠参照群 == refs and not p.反証参照群 for p in equality)
            for pair, observation, call in zip(teachers, observations, calls):
                assert observation.原入力 == {'候補':pair['output'],'出力':pair['output']} and call['output'] == pair['output']
            save(out, f'native-support-{minimum}.json.gz', {'support':minimum,'models':fitted.モデル群,'record':record,
                 'candidate_calls':calls,'native_calls':machine.calls,'ledger':machine.台帳.JSON相当(),
                 'raw_exhaust':machine.calls[-1]['exhaust'],'references':refs,'equality':equality,'query_calls':0})
            results.append({'support':minimum,'equality':record['同値採用'],'current':4,'prior':0,'quarantine':0,
                            'raw_exhaust':machine.calls[-1]['exhaust'].状態})
            assert fitted.モデル群 is identity and dataclasses.asdict(fitted) == state
    finally: adapter.fit = original_fit
    check('same4 distinct teachers same fitted tuple fresh native support4 equality true support5 false normal3 true; raw exhaust separate')
    return results

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--output-base'); ap.add_argument('--repository-root'); args = ap.parse_args()
    out = Path(tempfile.mkdtemp(prefix='arc2-candidate021-', dir=args.output_base)); summary = {'artifact_directory':str(out)}
    try:
        adapter,native,helpers = load(out,args.repository_root)
        teachers = read('selected-teachers.json.gz')['train']
        fitted = fit_and_teachers(adapter,teachers,out)
        views_and_controls(adapter,out)
        schema_proof_and_immutability(adapter,teachers,fitted,out)
        resources(adapter,teachers,fitted,out)
        summary['native'] = native_cycles(adapter,native,helpers,fitted,teachers,out)
        summary.update(successful=True,tests_run=len(PASSED),passed_cases=PASSED)
    except BaseException as error:
        summary.update(successful=False,tests_run=len(PASSED),passed_cases=PASSED,error=type(error).__name__,
                       message=str(error),traceback=traceback.format_exc())
    save(out,'summary.json',summary); print(json.dumps(serial(summary),ensure_ascii=False,sort_keys=True))
    return 0 if summary['successful'] else 1

if __name__ == '__main__': raise SystemExit(main())
