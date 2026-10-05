#!/usr/bin/env python3
"""Portable teacher/control-only regression; never calls a query or whole bridge."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse, ast, contextlib, copy, dataclasses, enum, gzip, hashlib, importlib, json, tempfile, time, traceback, types
from pathlib import Path
P=Path(__file__).resolve().parents[1]; F=Path(__file__).resolve().parent/'色線反射資料'
PASSED=[]

def serial(v):
    if dataclasses.is_dataclass(v):return serial(dataclasses.asdict(v))
    if isinstance(v,enum.Enum):return serial(v.value)
    if isinstance(v,dict):return {str(k):serial(x)for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [serial(x)for x in v]
    if isinstance(v,(set,frozenset)):return [serial(x)for x in sorted(v)]
    if v is None or isinstance(v,(str,int,float,bool)):return v
    raise TypeError(type(v).__name__)
def encoded(v):return json.dumps(serial(v),ensure_ascii=False,sort_keys=True,separators=(',',':'))
def equal(a,b):return encoded(a)==encoded(b)
def check(name,value):
    if not value:raise AssertionError(name)
    PASSED.append(name)
def read(name):return json.loads(gzip.decompress((F/name).read_bytes()))
def save(out,name,value):
    data=encoded(value).encode();(out/name).write_bytes(gzip.compress(data,mtime=0)if name.endswith('.gz')else data)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class Journal:
    def __init__(self,path):self.file=gzip.open(path,'wt',compresslevel=1);self.counts={}
    def __call__(self,event):
        self.file.write(encoded(event)+'\n');self.file.flush()
        kind=event['kind'];self.counts[kind]=self.counts.get(kind,0)+1
    def close(self):self.file.close()

class RemoveHooks(ast.NodeTransformer):
    def visit_Expr(self,node):
        if isinstance(node.value,ast.Call)and isinstance(node.value.func,ast.Name)and node.value.func.id=='_observe':return None
        return self.generic_visit(node)
    def visit_Call(self,node):
        node=self.generic_visit(node);node.keywords=[k for k in node.keywords if k.arg!='observer'];return node
    def visit_FunctionDef(self,node):
        node=self.generic_visit(node)
        if node.args.args and node.args.args[-1].arg=='observer':node.args.args.pop();node.args.defaults.pop()
        return node

def load(out):
    deployed=(P/'HDS/学習系統/v0.4.2/hds学習系統').is_dir()
    repo=P if deployed else P.parent/'source-evidence/repository'
    manifest=read('依存固定.json.gz')
    for item in manifest['pure_dependencies']+manifest['native']['core']:
        assert sha(repo/item['path'])==item['sha256'],item['path']
    pkg=types.ModuleType('_candidate020_regression');pkg.__path__=[str(P/'接続/ARC2'),str(repo/'接続/ARC2')];sys.modules[pkg.__name__]=pkg
    adapter=importlib.import_module(pkg.__name__+'.色線反射教材')
    old=ast.parse(gzip.decompress((F/'prototype.py.gz').read_bytes()))
    now=RemoveHooks().visit(ast.parse((P/'接続/ARC2/色線反射候補.py').read_bytes()))
    old_functions={n.name:ast.dump(n,include_attributes=False)for n in old.body if isinstance(n,ast.FunctionDef)}
    new_functions={n.name:ast.dump(n,include_attributes=False)for n in now.body if isinstance(n,ast.FunctionDef)and n.name!='_observe'}
    check('all original function ASTs unchanged after removing observation hooks',old_functions==new_functions)
    check('direct original helper identity',adapter.core.valid_grid is importlib.import_module(pkg.__name__+'.凡例旋回教材').valid_grid and adapter.core.body_components is importlib.import_module(pkg.__name__+'.凡例旋回教材').body_components and adapter.core.diagonal_segment is importlib.import_module(pkg.__name__+'.既存対角線橋').diagonal_segment and adapter.core.clone_grid is importlib.import_module(pkg.__name__+'.既存凡例穴対応').clone_grid)
    bridge=repo/'接続/ARC2/HDS接続.py';data=bridge.read_bytes();fixed=manifest['native']
    if not deployed:assert sha(bridge)==fixed['bridge_sha256']
    nodes={n.name:n for n in ast.parse(data).body if isinstance(n,ast.FunctionDef)and n.name in fixed['ast']}
    check('three native helper ASTs and frozen dependency bytes', {k:ast.dump(n,include_attributes=False)for k,n in nodes.items()}==fixed['ast'])
    sys.path.insert(0,str(repo/'HDS/学習系統/v0.4.2'));native=importlib.import_module('hds学習系統');nt=importlib.import_module('hds学習系統.型')
    scope={'deepcopy':copy.deepcopy,'学習入力':nt.学習入力,'観測事実':nt.観測事実}
    exec(compile(ast.Module(body=list(nodes.values()),type_ignores=[]),str(bridge),'exec'),scope)
    save(out,'source-verification.json',{'repo':str(repo),'deployed_mode':deployed,'dependency_manifest':manifest,'bridge_actual_sha256':sha(bridge),'runtime_sha256':sha(P/'接続/ARC2/色線反射候補.py'),'wrapper_sha256':sha(P/'接続/ARC2/色線反射教材.py')})
    return adapter,native,scope

def original_controls(adapter,teachers,fitted,out):
    directory=out/'original-controls';directory.mkdir()
    for name in ('teacher-returns.json','selected-teachers.json'):
        (directory/name).write_bytes(gzip.decompress((F/(name+'.gz')).read_bytes()))
    source=gzip.decompress((F/'check_controls.py.gz').read_bytes()).decode()
    source=source.replace('from prototype import render, parse_input, execute_graph, fit_teachers, consensus, PROGRAMS','')
    source=source.replace('from reused_primitives import transform_grid_by_name','')
    names=('render','parse_input','execute_graph','fit_teachers','consensus','PROGRAMS')
    ns={n:getattr(adapter.core,n)for n in names}
    helpers=importlib.import_module(adapter.core.__package__+'.既存格子操作')
    ns.update(transform_grid_by_name=helpers.transform_grid_by_name,__file__=str(directory/'check_controls.py'),__name__='_original_controls')
    with (directory/'stdout.json').open('w') as stream,contextlib.redirect_stdout(stream):
        exec(compile(source,str(F/'check_controls.py.gz'),'exec'),ns)
    check('all70 original controls and all saved full records unchanged',equal(ns['summary'],read('control-summary.json.gz'))and equal(ns['records'],read('control-returns.json.gz'))and ns['summary']['passed']==70)
    journal=Journal(out/'all-control-events.jsonl.gz');actual=[]
    try:
        for case in ns['records']:
            if 'input'not in case or 'initial'in case:continue
            output,detail=fitted.候補(case['input'],{},journal)
            assert output==case['output'],case['name']
            if adapter.valid_grid(case['input']):assert equal(detail['returns'][0]['record'],case['record']),case['name']
            actual.append({**case,'wrapper_output':output,'wrapper_record':detail})
    finally:journal.close()
    save(out,'all-controls-full-inputs-outputs.json.gz',{'all70_original':ns['records'],'wrapper_returns':actual,'cycle_scope':'engine-injected only; L-source reachability unproven'})
    check('every eligible original control through fitted wrapper preserves output and full causal return',len(actual)==65)


def schema(adapter,teachers,fitted,out):
    bad=[None,{},[],teachers[:1],[teachers[0],teachers[0]],[dict(teachers[0],extra=1),teachers[1]],[{'input':teachers[0]['input']},teachers[1]],[None,teachers[1]]]
    grids=[None,[],[[]],[[True]],[[1.0]],[['1']],[[-1]],[[10]],[[0],[0,1]],((0,),),[(0,)],[[0]]*31,[[0]*31]]
    for field in ('input','output'):
        for grid in grids:
            pairs=copy.deepcopy(teachers[:2]);pairs[0][field]=grid;bad.append(pairs)
    rows=[];original=adapter.core.render
    def forbidden(*a,**k):raise AssertionError('invalid schema entered grammar')
    adapter.core.render=forbidden
    try:
        for value in bad:
            audit={};events=[];before=copy.deepcopy(value);invalid=adapter.色線反射教材(value,audit,events.append)
            assert invalid.モデル群==()and 'failure'in audit and value==before and len(events)==1
            rows.append({'input':value,'record':audit})
    finally:adapter.core.render=original
    assert adapter.validate_teachers(tuple(teachers))[0]
    altered=copy.deepcopy(teachers[:2]);altered[0]['output']=[[0]];events=[];audit={}
    other=adapter.色線反射教材(altered,audit,events.append)
    assert other.モデル群==()and audit['evaluated_models']==8 and audit['evaluated_teacher_returns']==16
    rows.append({'name':'valid changed output shape is exhausted across full grammar','input':altered,'events':events,'record':audit})
    for grid in grids:
        assert fitted.候補(grid,{})[0] is None
    before=dataclasses.asdict(fitted)
    def immutable(v):return isinstance(v,tuple)and all(immutable(x)for x in v)or v is None or type(v)in (str,int,float,bool)
    assert all(immutable(v)for v in dataclasses.astuple(fitted))
    detached=fitted.記録();detached['保持候補'].clear();assert dataclasses.asdict(fitted)==before
    try:fitted.教師数=0
    except dataclasses.FrozenInstanceError:pass
    else:raise AssertionError('mutable fitted state')
    # Two distinct boundary-exit teachers retain all four outward programs, even
    # though all teacher grids coincide within each program.
    two=[]
    for h,w in ((7,11),(6,10)):
        g=[[0]*w for _ in range(h)];r,c=h-1,w-1
        for a,b in ((r,c),(r-1,c),(r,c-1)):g[a][b]=1
        two.append({'input':g,'output':copy.deepcopy(g)})
    multi=adapter.色線反射教材(two);assert multi.モデル群==adapter.core.PROGRAMS[:4]
    output,detail=multi.候補(teachers[1]['input'],{})
    assert output is None and detail['failure']=='model_disagreement'and len(detail['returns'])==4
    rows.append({'name':'all4 retained without output deduplication; whole disagreement','teachers':two,'models':multi.モデル群,'input':teachers[1]['input'],'output':output,'record':detail})
    # Runtime failure in an early retained member never skips later members.
    calls=[]
    def one_fails(grid,model,observer=None):
        calls.append(model)
        if model==multi.モデル群[0]:return None,{'failure':'injected_semantic_failure'}
        return original(grid,model,observer=observer)
    adapter.core.render=one_fails
    try:output,detail=multi.候補(teachers[0]['input'],{})
    finally:adapter.core.render=original
    assert output is None and detail['failure']=='model_failure'and tuple(calls)==multi.モデル群 and len(detail['returns'])==4
    rows.append({'name':'whole retained failure still exhausts every retained member','calls':calls,'record':detail})
    save(out,'schema-immutability-all-retained.json.gz',rows)
    check('strict schema, distinct teachers, immutable target-free state, complete valid shape mismatch and all-retained consensus',True)


def resources(adapter,teachers,fitted,out):
    rows=[];original=adapter.core.diagonal_segment
    for exception in (MemoryError,RecursionError,TimeoutError):
        for mode in ('fit','prediction'):
            events=[];count=[0]
            def interrupted(*args,**kwargs):
                if count[0]==2:raise exception('injected after two completed geometric steps')
                count[0]+=1;return original(*args,**kwargs)
            adapter.core.diagonal_segment=interrupted
            try:
                if mode=='fit':adapter.fit(teachers,events.append)
                else:fitted.候補(teachers[0]['input'],{},events.append)
                raise AssertionError('resource exception swallowed')
            except exception:
                e=events[-1];assert e['kind']=='evaluation_exception'and e['semantic_HOLD']is False
                prefix=e['partial_current_render'];assert prefix['kind']=='state_prefix'and len(prefix['states'])==2 and len(prefix['edges'])==2 and prefix['pending']
                assert prefix['role_record']['glyphs'] and e['active_call']
                rows.append({'exception':exception.__name__,'mode':mode,'events':events})
            finally:adapter.core.diagonal_segment=original
    # Capture completed full model and teacher returns before a later interrupt.
    original_render=adapter.core.render;events=[];count=[0]
    def later(grid,model,observer=None):
        if count[0]==4:raise MemoryError('injected after complete model plus next teacher')
        count[0]+=1;return original_render(grid,model,observer=observer)
    adapter.core.render=later
    try:adapter.fit(teachers,events.append)
    except MemoryError:
        e=events[-1];assert len(e['completed_model_prefix'])==1 and len(e['current_model_return_prefix'])==1
        assert len(e['completed_model_prefix'][0]['teachers'])==3
        rows.append({'exception':'MemoryError','mode':'later_fit','events':events})
    else:raise AssertionError('later interrupt swallowed')
    finally:adapter.core.render=original_render
    original_observe=adapter.core._observe
    _,full=adapter.core.parse_input(teachers[0]['input'])
    for exception in (MemoryError,RecursionError,TimeoutError):
        events=[];count=[0]
        def role_interrupt(observer,kind,**values):
            if kind=='role_completed':
                if count[0]==2:raise exception('injected after two completed roles')
                count[0]+=1
            return original_observe(observer,kind,**values)
        adapter.core._observe=role_interrupt
        try:adapter.fit(teachers,events.append)
        except exception:
            e=events[-1];prefix=e['partial_current_render']
            assert prefix['kind']=='role_prefix'and len(prefix['glyphs'])==2
            assert equal(prefix['glyphs'],full['glyphs'][:2])and prefix['failed_roles']==[]
            rows.append({'exception':exception.__name__,'mode':'incremental_role_prefix','events':events})
        else:raise AssertionError('role interruption swallowed')
        finally:adapter.core._observe=original_observe
    save(out,'resource-exception-prefix-controls.json.gz',rows)
    check('resource rethrow preserves completed models/teacher returns and full role/state prefix',len(rows)==10)


def native_cycles(adapter,native,helpers,fitted,teachers,out):
    identity=fitted.モデル群;before=dataclasses.asdict(fitted);results=[]
    class Recording(native.HDS学習実行系):
        def __init__(self,minimum):super().__init__(最小支持数=minimum);self.calls=[]
        def 実行(self,value):
            result=super().実行(value);exhaust=native.最小排気系().排出する(result)
            self.calls.append({'input':value,'result':result,'exhaust':exhaust});return result
        def 照会(self,*a,**k):raise AssertionError('query prohibited')
    original=adapter.fit
    def no_refit(*a,**k):raise AssertionError('reuse identical fitted model tuple')
    adapter.fit=no_refit
    try:
        for minimum in (3,4):
            machine=Recording(minimum);assert machine.台帳.全取得()=={};calls=[]
            def candidate(grid,policy):
                assert fitted.モデル群 is identity
                output,detail=fitted.候補(grid,policy);calls.append({'input':grid,'output':output,'record':detail});return output,detail
            boundary='ARC色線反射';record=helpers['候補機構を学習'](machine,{'train':teachers},(),boundary,candidate)
            assert record['採用可']and record['同値採用']==(minimum==3)
            assert record['現在観測数']==3 and record['事前観測数']==0 and record['隔離数']==0
            observations=machine.台帳.取得('観測台帳');assert len(observations)==len(calls)==3
            assert len({encoded(o.原入力)for o in observations})==3
            references=tuple(o.経験識別子 for o in observations);last=machine.calls[-1]['result']
            equality=[p for p in last.有効原理群 if helpers['同値原理あり']([p],boundary)]
            assert bool(equality)==(minimum==3)
            assert all(p.根拠参照群==references and not p.反証参照群 for p in equality)
            for pair,observation,call in zip(teachers,observations,calls):assert observation.原入力=={'候補':pair['output'],'出力':pair['output']}and call['output']==pair['output']
            save(out,f'native-support-{minimum}.json.gz',{'support':minimum,'models':fitted.モデル群,'record':record,'candidate_calls':calls,'native_calls':machine.calls,'ledger':machine.台帳.JSON相当(),'raw_exhaust':machine.calls[-1]['exhaust'],'references':references,'equality':equality,'query_calls':0})
            results.append({'support':minimum,'equality':record['同値採用'],'current':3,'prior':0,'quarantine':0,'raw_exhaust':machine.calls[-1]['exhaust'].状態})
            assert fitted.モデル群 is identity and dataclasses.asdict(fitted)==before
    finally:adapter.fit=original
    check('same fit same3 distinct teachers fresh native HDS support3 equality true support4 false with raw exhaust separate',len(results)==2)
    return results


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output-base');args=ap.parse_args()
    out=Path(tempfile.mkdtemp(prefix='arc2-candidate020-',dir=args.output_base));summary={'artifact_directory':str(out)}
    try:
        adapter,native,helpers=load(out);teachers=read('selected-teachers.json.gz')['train'];original=read('teacher-returns.json.gz')
        audit={};journal=Journal(out/'full-teacher-fit-events.jsonl.gz');records=[]
        def observer(event):
            journal(event)
            if event['kind']=='model_completed':records.append(event['record'])
        start=time.process_time()
        try:fitted=adapter.色線反射教材(teachers,audit,observer)
        finally:journal.close()
        assert equal(records,original['all_program_returns'])and equal(fitted.モデル群,original['retained'])
        check('all8 programs all24 teacher returns and sole retained match original',len(records)==8 and fitted.適合数==1)
        unobserved,raw_records=adapter.core.fit_teachers(teachers)
        check('observation on/off full output and record parity',equal(raw_records,records)and equal(unobserved,original['retained']))
        returns=[fitted.候補(pair['input'],{})for pair in teachers]
        assert all(x[0]==p['output']for x,p in zip(returns,teachers))
        save(out,'full-teacher-fit-and-returns.json.gz',{'fit_record':audit,'models':fitted.モデル群,'records':records,'returns':returns,'cpu_seconds':time.process_time()-start})
        original_controls(adapter,teachers,fitted,out);schema(adapter,teachers,fitted,out);resources(adapter,teachers,fitted,out)
        summary['native']=native_cycles(adapter,native,helpers,fitted,teachers,out)
        summary.update(successful=True,tests_run=len(PASSED),passed_cases=PASSED)
    except BaseException as error:
        summary.update(successful=False,tests_run=len(PASSED),passed_cases=PASSED,error=type(error).__name__,message=str(error),traceback=traceback.format_exc())
    save(out,'summary.json',summary);print(json.dumps(summary,ensure_ascii=False,sort_keys=True));return 0 if summary['successful']else 1

if __name__=='__main__':raise SystemExit(main())
