#!/usr/bin/env python3
"""Portable public teacher/control fixtures; no query, original challenge, or scorer."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse, ast, copy, dataclasses, enum, gzip, hashlib, importlib, itertools, json, tempfile, time, traceback, types
from pathlib import Path
P=Path(__file__).resolve().parents[1]; F=Path(__file__).resolve().parent/'境界点周期資料'
PASSED=[]
def serial(v):
    if dataclasses.is_dataclass(v):return serial(dataclasses.asdict(v))
    if isinstance(v,enum.Enum):return serial(v.value)
    if isinstance(v,dict):return {str(k):serial(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [serial(x) for x in v]
    if isinstance(v,(set,frozenset)):return [serial(x) for x in sorted(v)]
    if v is None or isinstance(v,(str,int,float,bool)):return v
    raise TypeError(type(v).__name__)
def encoded(v):return json.dumps(serial(v),ensure_ascii=False,sort_keys=True,separators=(',',':'))
def equal(a,b):return encoded(a)==encoded(b)
def check(name,value):
    if not value:raise AssertionError(name)
    PASSED.append(name)
def read(name):return json.loads(gzip.decompress((F/name).read_bytes()))
def save(out,name,value):
    data=encoded(value).encode();(out/name).write_bytes(gzip.compress(data,mtime=0) if name.endswith('.gz') else data)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class Journal:
    def __init__(self,path):self.file=gzip.open(path,'wt',compresslevel=1);self.counts={}
    def __call__(self,event):
        self.file.write(encoded(event)+'\n');self.file.flush()
        k=event['kind'];self.counts[k]=self.counts.get(k,0)+1
    def close(self):self.file.close()

def load(out,repository_root=None):
    deployed=(P/'HDS/学習系統/v0.4.2/hds学習系統').is_dir()
    repo=Path(repository_root).resolve() if repository_root else P if deployed else P.parent/'source-evidence/repository'
    snapshot=not deployed and repository_root is None
    manifest=read('依存固定.json.gz')
    for item in manifest['pure_dependencies']+manifest['native']['core']:
        assert sha(repo/item['path'])==item['sha256'],item['path']
    bridge=repo/'接続/ARC2/HDS接続.py';data=bridge.read_bytes();fixed=manifest['native']
    if snapshot:assert sha(bridge)==fixed['bridge_sha256']
    nodes={n.name:n for n in ast.parse(data).body if isinstance(n,ast.FunctionDef) and n.name in fixed['ast']}
    check('three native helper ASTs and accepted dependency bytes', {k:ast.dump(n,include_attributes=False) for k,n in nodes.items()}==fixed['ast'])
    old=ast.parse(gzip.decompress((F/'prototype.py.gz').read_bytes()))
    now=ast.parse((P/'接続/ARC2/境界点周期候補.py').read_bytes())
    functions=lambda tree:{n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,ast.FunctionDef)}
    check('every original pure semantic function AST unchanged',functions(old)==functions(now))
    pkg=types.ModuleType('_candidate022_regression');pkg.__path__=[str(P/'接続/ARC2'),str(repo/'接続/ARC2')];sys.modules[pkg.__name__]=pkg
    adapter=importlib.import_module(pkg.__name__+'.境界点周期教材')
    for module,names in [('既存凡例穴対応',('clone_grid','grid_shape')),('既存行周期',('superposed_cell_value',))]:
        source=ast.parse((repo/'接続/ARC2'/f'{module}.py').read_text())
        actual={n.name:ast.dump(n,include_attributes=False) for n in source.body if isinstance(n,ast.FunctionDef) and n.name in names}
        imported=importlib.import_module(pkg.__name__+'.'+module)
        for name in names:
            assert actual[name]==manifest['helper_ast'][name]
            assert getattr(adapter.core,name) is getattr(imported,name)
    check('three original helpers direct-import identity and exact AST',True)
    grammar=read('frozen-grammar.json.gz')
    check('exact frozen8 grammar tuples',equal(adapter.core.PROGRAMS,[tuple(m[k] for k in adapter.core.MODEL_KEYS) for m in grammar['models']]))
    sys.path.insert(0,str(repo/'HDS/学習系統/v0.4.2'));native=importlib.import_module('hds学習系統');nt=importlib.import_module('hds学習系統.型')
    scope={'deepcopy':copy.deepcopy,'学習入力':nt.学習入力,'観測事実':nt.観測事実}
    exec(compile(ast.Module(body=list(nodes.values()),type_ignores=[]),str(bridge),'exec'),scope)
    save(out,'source-verification.json',{'repo':str(repo),'deployed_mode':deployed,'actual_repository_argument':repository_root is not None,'dependency_manifest':manifest,'bridge_actual_sha256':sha(bridge),'runtime_sha256':sha(P/'接続/ARC2/境界点周期候補.py'),'wrapper_sha256':sha(P/'接続/ARC2/境界点周期教材.py')})
    return adapter,native,scope

def controls(adapter,teachers,fitted,out):
    frozen=read('controls-all-results.json.gz');assert len(frozen)==295
    models=[dict(zip(adapter.core.MODEL_KEYS,m)) for m in fitted.モデル群]
    actual=[];journal=Journal(out/'all-control-events.jsonl.gz');wrapped=0
    try:
        for case in frozen:
            if case['kind']=='fit_guard':
                raw,detail=adapter.core.fit(case['input'],read('frozen-grammar.json.gz')['models'])
                obj=adapter.境界点周期教材(case['input'],観測=journal)
                assert equal(raw,case['actual_models']) and equal(detail,case['record']) and obj.モデル群==()
                row={**case,'wrapper_models':obj.モデル群,'wrapper_record':obj.記録()}
            elif case['kind']=='proposal_collision':
                output,detail=adapter.core.merge_proposals(case['input'],case['proposals'])
                assert equal(output,case['actual_output']) and equal(detail,case['record'])
                row={**case,'replay_record':detail}
            else:
                raw,detail=adapter.core.predict(case['input'],models)
                output,record=fitted.候補(case['input'],{},journal)
                assert equal(raw,case['actual_output']) and equal(detail,case['record']) and output==case['expected_output']
                if adapter.valid_grid(case['input']):
                    assert equal([r['record'] for r in record['returns']],[r['record'] for r in detail['alternatives']])
                wrapped+=1;row={**case,'wrapper_output':output,'wrapper_record':record}
            actual.append(row)
    finally:journal.close()
    save(out,'all295-controls-full-inputs-outputs.json.gz',actual)
    check('all295 controls exact full-record replay and every eligible wrapper return',wrapped==290 and all(r['passed'] for r in actual))
    diagnostics=read('fit-diagnostics.json.gz');loo=[];orders=[]
    for i,pair in enumerate(teachers):
        left=[p for j,p in enumerate(teachers) if i!=j];obj=adapter.境界点周期教材(left)
        output,record=obj.候補(pair['input'],{})
        expected=diagnostics['leave_one_out'][i]
        assert equal(obj.モデル群,[tuple(m[k] for k in adapter.core.MODEL_KEYS) for m in expected['fitted_models']])
        assert equal(output,expected['output'])
        loo.append({'held_out_teacher':i,'models':obj.モデル群,'output':output,'record':record,'exact':output==pair['output']})
    for perm in itertools.permutations(range(len(teachers))):
        obj=adapter.境界点周期教材([teachers[i] for i in perm]);assert obj.モデル群==fitted.モデル群
        orders.append({'permutation':perm,'models':obj.モデル群})
    save(out,'loo-and-teacher-order.json.gz',{'loo':loo,'orders':orders,'interpretation':'All teachers were observed before grammar freeze. Two LOO folds remain unidentifiable and correctly HOLD.'})
    check('six teacher orders and original two-fold LOO unidentifiability retained',[r['exact'] for r in loo]==[False,False,True] and len(orders)==6)

def schema(adapter,teachers,fitted,out):
    bad=[None,{},[],teachers[:1],[teachers[0],teachers[0]],[dict(teachers[0],extra=1),teachers[1]],[{'input':teachers[0]['input']},teachers[1]],[None,teachers[1]]]
    grids=[None,[],[[]],[[True]],[[1.0]],[['1']],[[-1]],[[10]],[[0],[0,1]],((0,),),[(0,)],[[0]]*31,[[0]*31]]
    for field in ('input','output'):
        for grid in grids:
            pairs=copy.deepcopy(teachers[:2]);pairs[0][field]=grid;bad.append(pairs)
    rows=[];original=adapter.core.render
    def forbidden(*a,**k):raise AssertionError('invalid teacher entered grammar')
    adapter.core.render=forbidden
    try:
        for value in bad:
            audit={};events=[];before=copy.deepcopy(value);obj=adapter.境界点周期教材(value,audit,events.append)
            assert obj.モデル群==() and audit.get('failure') and value==before and len(events)==1
            rows.append({'input':value,'record':audit})
    finally:adapter.core.render=original
    assert adapter.validate_teachers(tuple(teachers))[0]
    altered=copy.deepcopy(teachers[:2]);altered[0]['output']=[[0]];events=[];audit={}
    obj=adapter.境界点周期教材(altered,audit,events.append)
    assert obj.モデル群==() and audit['evaluated_models']==8 and audit['evaluated_teacher_returns']==16
    rows.append({'name':'valid mismatched output shape exhausts8x2','teachers':altered,'record':audit,'events':events})
    for grid in grids:assert fitted.候補(grid,{})[0] is None
    before=dataclasses.asdict(fitted)
    def immutable(v):return type(v) is tuple and all(immutable(x) for x in v) or v is None or type(v) in (str,int)
    assert all(immutable(v) for v in dataclasses.astuple(fitted)) and not hasattr(fitted,'__dict__')
    detached=fitted.記録();detached['保持候補'].clear();assert dataclasses.asdict(fitted)==before
    try:fitted.教師数=0
    except dataclasses.FrozenInstanceError:pass
    else:raise AssertionError('mutable state')
    source=copy.deepcopy(teachers);f=adapter.境界点周期教材(source);state=dataclasses.asdict(f)
    source[0]['input'][0][0]=(source[0]['input'][0][0]+1)%10;source[0]['output'].clear()
    assert dataclasses.asdict(f)==state
    two=[]
    for width in (9,11):
        grid=[[2,0,2]+[0]*(width-3)];output=[[2 if c%2==0 else 0 for c in range(width)]]
        two.append({'input':grid,'output':output})
    multi=adapter.境界点周期教材(two);assert multi.モデル群==adapter.core.PROGRAMS
    output,record=multi.候補(teachers[0]['input'],{})
    assert output is None and record['failure']=='model_disagreement' and len(record['returns'])==8
    rows.append({'name':'all8 retained without semantic deduplication; later disagreement','teachers':two,'models':multi.モデル群,'input':teachers[0]['input'],'record':record})
    calls=[]
    def first_fails(grid,model):
        calls.append(model)
        if model['model_id']=='m00':return None,{'failure':'injected_semantic_failure'}
        return original(grid,model)
    adapter.core.render=first_fails
    try:output,record=multi.候補(teachers[0]['input'],{})
    finally:adapter.core.render=original
    assert output is None and record['failure']=='model_failure' and len(calls)==len(record['returns'])==8
    rows.append({'name':'first retained failure still exhausts all8','calls':calls,'record':record})
    hostile=[]
    def mutate(event):
        hostile.append(event['kind']);event.clear()
    observed=adapter.境界点周期教材(teachers,観測=mutate)
    assert observed.モデル群==fitted.モデル群 and all(observed.候補(t['input'],{},mutate)[0]==t['output'] for t in teachers)
    save(out,'schema-immutability-all-retained.json.gz',rows)
    check('strict schema immutable target-free state and detached observers',True)
    check('all8 retained; whole disagreement; semantic failure never skips later models',True)
    return multi

def resources(adapter,teachers,multi,out):
    rows=[];original=adapter.core.render
    for error_type in (MemoryError,RecursionError,TimeoutError):
        for mode,stop in [('fit',4),('prediction',2)]:
            calls=[0];events=[]
            def interrupt(grid,model):
                if calls[0]==stop:raise error_type('injected after complete return prefix')
                calls[0]+=1;return original(grid,model)
            adapter.core.render=interrupt
            try:
                if mode=='fit':adapter.境界点周期教材(teachers,観測=events.append)
                else:multi.候補(teachers[0]['input'],{},events.append)
            except error_type:
                event=events[-1];assert event['kind']=='evaluation_exception' and event['resource_failure'] is True and event['semantic_HOLD'] is False
                assert event['active_call'] and event['exception']==error_type.__name__
                assert len(event['completed_model_prefix'])==(1 if mode=='fit' else 2)
                assert len(event['current_model_return_prefix'])==(1 if mode=='fit' else 0)
                if mode=='fit':assert len(event['completed_model_prefix'][0]['teachers'])==3
                assert sum(e['kind']=='render_return' for e in events)==stop
                rows.append({'mode':mode,'exception':error_type.__name__,'events':events})
            else:raise AssertionError('resource exception swallowed')
            finally:adapter.core.render=original
    save(out,'resource-exception-prefix-controls.json.gz',rows)
    check('MemoryError RecursionError TimeoutError propagate with complete model teacher prefix',len(rows)==6)

def native_cycles(adapter,native,helpers,fitted,teachers,out):
    identity=fitted.モデル群;before=dataclasses.asdict(fitted);results=[]
    class Recording(native.HDS学習実行系):
        def __init__(self,minimum):super().__init__(最小支持数=minimum);self.calls=[]
        def 実行(self,value):
            result=super().実行(value);exhaust=native.最小排気系().排出する(result)
            self.calls.append({'input':value,'result':result,'exhaust':exhaust});return result
        def 照会(self,*a,**k):raise AssertionError('query prohibited')
    original=adapter.fit
    def no_refit(*a,**k):raise AssertionError('reuse identical fitted tuple')
    adapter.fit=no_refit
    try:
        for minimum in (3,4):
            machine=Recording(minimum);assert machine.台帳.全取得()=={};calls=[]
            def candidate(grid,policy):
                assert fitted.モデル群 is identity
                output,detail=fitted.候補(grid,policy);calls.append({'input':grid,'output':output,'record':detail});return output,detail
            boundary='ARC境界点周期';record=helpers['候補機構を学習'](machine,{'train':teachers},(),boundary,candidate)
            assert record['採用可'] and record['同値採用']==(minimum==3)
            assert record['現在観測数']==3 and record['事前観測数']==0 and record['隔離数']==0
            observations=machine.台帳.取得('観測台帳');assert len(observations)==len(calls)==3
            assert len({encoded(o.原入力) for o in observations})==3
            references=tuple(o.経験識別子 for o in observations);last=machine.calls[-1]['result']
            equality=[p for p in last.有効原理群 if helpers['同値原理あり']([p],boundary)]
            assert bool(equality)==(minimum==3)
            assert all(p.根拠参照群==references and not p.反証参照群 for p in equality)
            for pair,observation,call in zip(teachers,observations,calls):assert observation.原入力=={'候補':pair['output'],'出力':pair['output']} and call['output']==pair['output']
            save(out,f'native-support-{minimum}.json.gz',{'support':minimum,'models':fitted.モデル群,'record':record,'candidate_calls':calls,'native_calls':machine.calls,'ledger':machine.台帳.JSON相当(),'raw_exhaust':machine.calls[-1]['exhaust'],'references':references,'equality':equality,'query_calls':0})
            results.append({'support':minimum,'equality':record['同値採用'],'current':3,'prior':0,'quarantine':0,'raw_exhaust':machine.calls[-1]['exhaust'].状態})
            assert fitted.モデル群 is identity and dataclasses.asdict(fitted)==before
    finally:adapter.fit=original
    check('same fit same3 distinct teachers fresh native support3 equality true support4 false raw exhaust separate',len(results)==2)
    return results

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output-base');ap.add_argument('--repository-root');args=ap.parse_args()
    out=Path(tempfile.mkdtemp(prefix='arc2-candidate022-',dir=args.output_base));summary={'artifact_directory':str(out)}
    try:
        adapter,native,helpers=load(out,args.repository_root);teachers=read('selected-teachers.json.gz')['train'];original=read('teacher-all-hypotheses.json.gz')
        audit={};journal=Journal(out/'full-teacher-fit-events.jsonl.gz');records=[]
        def observer(event):
            journal(event)
            if event['kind']=='model_completed':records.append(event['record'])
        start=time.process_time()
        try:fitted=adapter.境界点周期教材(teachers,audit,observer)
        finally:journal.close()
        assert equal(records,original['hypotheses'])
        assert equal([dict(zip(adapter.core.MODEL_KEYS,m)) for m in fitted.モデル群],original['fitted_models'])
        check('all8 programs all24 complete teacher returns and sole m00 exact',len(records)==8 and fitted.適合数==1)
        plain=adapter.境界点周期教材(teachers);assert plain.モデル群==fitted.モデル群
        returns=[fitted.候補(p['input'],{}) for p in teachers]
        assert all(r[0]==p['output'] for r,p in zip(returns,teachers))
        save(out,'full-teacher-fit-and-returns.json.gz',{'fit_record':audit,'models':fitted.モデル群,'records':records,'returns':returns,'cpu_seconds':time.process_time()-start})
        controls(adapter,teachers,fitted,out);multi=schema(adapter,teachers,fitted,out);resources(adapter,teachers,multi,out)
        summary['native']=native_cycles(adapter,native,helpers,fitted,teachers,out)
        summary.update(successful=True,tests_run=len(PASSED),passed_cases=PASSED)
    except BaseException as error:
        summary.update(successful=False,tests_run=len(PASSED),passed_cases=PASSED,error=type(error).__name__,message=str(error),traceback=traceback.format_exc())
    save(out,'summary.json',summary);print(json.dumps(summary,ensure_ascii=False,sort_keys=True));return 0 if summary['successful'] else 1
if __name__=='__main__':raise SystemExit(main())
