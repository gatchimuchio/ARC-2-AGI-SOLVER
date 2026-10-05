#!/usr/bin/env python3
"""Portable teacher/control-only regression; never calls a query or whole bridge."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse, ast, contextlib, copy, dataclasses, enum, gzip, hashlib, importlib, json, tempfile, time, traceback, types
from pathlib import Path
P=Path(__file__).resolve().parents[1]; F=Path(__file__).resolve().parent/'見本格子分類資料'
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
    def visit_Assign(self,node):
        if isinstance(node.value,ast.Call)and isinstance(node.value.func,ast.Name)and node.value.func.id=='_identical_match_disagreement':return None
        return self.generic_visit(node)
    def visit_If(self,node):
        if isinstance(node.test,ast.Compare)and isinstance(node.test.left,ast.Name)and node.test.left.id=='proof':return None
        return self.generic_visit(node)
    def visit_Expr(self,node):
        if isinstance(node.value,ast.Call)and isinstance(node.value.func,ast.Name)and node.value.func.id=='_observe':return None
        return self.generic_visit(node)
    def visit_Call(self,node):
        node=self.generic_visit(node);node.keywords=[k for k in node.keywords if k.arg!='observer'];return node
    def visit_FunctionDef(self,node):
        if node.name in ('_allocation_witness_output','_identical_match_disagreement'):return None
        node=self.generic_visit(node)
        if node.args.args and node.args.args[-1].arg=='observer':node.args.args.pop();node.args.defaults.pop()
        return node

def load(out):
    deployed=(P/'HDS/学習系統/v0.4.2/hds学習系統').is_dir()
    repo=P if deployed else P.parent/'source-evidence/repository'
    manifest=read('依存固定.json.gz')
    for item in manifest['pure_dependencies']+manifest['native']['core']:
        assert sha(repo/item['path'])==item['sha256'],item['path']
    pkg=types.ModuleType('_candidate018_regression');pkg.__path__=[str(P/'接続/ARC2'),str(repo/'接続/ARC2')];sys.modules[pkg.__name__]=pkg
    adapter=importlib.import_module(pkg.__name__+'.見本格子分類教材')
    old=ast.parse(gzip.decompress((F/'prototype.py.gz').read_bytes()))
    now=RemoveHooks().visit(ast.parse((P/'接続/ARC2/見本格子分類候補.py').read_bytes()))
    old_functions={n.name:ast.dump(n,include_attributes=False)for n in old.body if isinstance(n,ast.FunctionDef)}
    new_functions={n.name:ast.dump(n,include_attributes=False)for n in now.body if isinstance(n,ast.FunctionDef)and n.name!='_observe'}
    check('all original function ASTs unchanged outside observation hooks and reviewed proof branch',old_functions==new_functions)
    check('direct original helper identity',adapter.core.regions is importlib.import_module(pkg.__name__+'.既存領域転写')and adapter.core.features is importlib.import_module(pkg.__name__+'.既存物体特徴')and adapter.core.canonical_shape is importlib.import_module(pkg.__name__+'.既存形状色転写').canonical_shape)
    bridge=repo/'接続/ARC2/HDS接続.py';data=bridge.read_bytes();fixed=manifest['native']
    if not deployed:assert sha(bridge)==fixed['bridge_sha256']
    nodes={n.name:n for n in ast.parse(data).body if isinstance(n,ast.FunctionDef)and n.name in fixed['ast']}
    check('three native helper ASTs and frozen dependency bytes', {k:ast.dump(n,include_attributes=False)for k,n in nodes.items()}==fixed['ast'])
    sys.path.insert(0,str(repo/'HDS/学習系統/v0.4.2'));native=importlib.import_module('hds学習系統');nt=importlib.import_module('hds学習系統.型')
    scope={'deepcopy':copy.deepcopy,'学習入力':nt.学習入力,'観測事実':nt.観測事実}
    exec(compile(ast.Module(body=list(nodes.values()),type_ignores=[]),str(bridge),'exec'),scope)
    save(out,'source-verification.json',{'repo':str(repo),'deployed_mode':deployed,'dependency_manifest':manifest,'bridge_actual_sha256':sha(bridge),'runtime_sha256':sha(P/'接続/ARC2/見本格子分類候補.py'),'wrapper_sha256':sha(P/'接続/ARC2/見本格子分類教材.py')})
    return adapter,native,scope

def original_controls(adapter,teachers,fitted,out):
    directory=out/'original-controls';directory.mkdir()
    for name in ('teacher-returns.json','teachers.json'):(directory/name).write_bytes(gzip.decompress((F/(name+'.gz')).read_bytes()))
    source=gzip.decompress((F/'run_controls.py.gz').read_bytes()).decode()
    source=source.replace('from prototype import consensus,fit,features,regions,canonical_shape,parse,render,rot,transform','')
    source=source.replace("checks=[]","checks=[]\nraw=[]\npalette_fits=[]")
    source=source.replace(' checks.append(row)'," checks.append(row)\n raw.append({'name':name,'input':g,'expected':expected,'hold':hold,'models':ms,'output':out,'record':rec})")
    source=source.replace(' mm,rr=fit(mapped)'," mm,rr=fit(mapped)\n palette_fits.append({'teachers':mapped,'models':mm,'records':rr})")
    names=('consensus','fit','features','regions','canonical_shape','parse','render','rot','transform')
    namespace={name:getattr(adapter.core,name)for name in names};namespace.update(__file__=str(directory/'run_controls.py'),__name__='_original_controls')
    with (directory/'stdout.json').open('w')as stream,contextlib.redirect_stdout(stream):exec(compile(source,str(F/'run_controls.py.gz'),'exec'),namespace)
    previous=read('controls.json.gz')
    def semantics(row):return {k:row[k]for k in ('name','pass','expected','output','evaluated','retained')if k in row}
    check('all original 68 controls preserve semantic grids HOLD and fit counts',equal([semantics(r)for r in namespace['result']['checks']],[semantics(r)for r in previous['checks']])and namespace['result']['passed']==68)
    journal=Journal(out/'all-control-events.jsonl.gz');actual=[]
    try:
        for case in namespace['raw']:
            models=tuple((tuple(m['model']),tuple(m['colors']))for m in case['models'])
            output,detail=adapter.predict(case['input'],models,journal)
            assert output==case['output'],case['name']
            orig=case['record']
            if 'returns'in orig:assert equal([{'output':r['output'],'record':r['record']}for r in detail['returns']],orig['returns']),case['name']
            actual.append({**case,'wrapper_output':output,'wrapper_record':detail})
    finally:journal.close()
    save(out,'all-controls-full-inputs-outputs.json.gz',actual);save(out,'both-palette-fits-full576.json.gz',namespace['palette_fits'])
    check('all 66 rendered controls preserve every retained-model output and HOLD',len(actual)==66)

def schema(adapter,teachers,out):
    bad=[None,{},[],teachers[:1],[teachers[0],teachers[0]],[dict(teachers[0],extra=1),teachers[1]],[{'input':teachers[0]['input']},teachers[1]],[None,teachers[1]]]
    grids=[None,[],[[]],[[True]],[[1.0]],[['1']],[[-1]],[[10]],[[0],[0,1]],((0,),),[(0,)],[[0]]*31,[[0]*31]]
    for field in ('input','output'):
        for grid in grids:
            pairs=copy.deepcopy(teachers[:2]);pairs[0][field]=grid;bad.append(pairs)
    results=[];original=adapter.core.fit
    def forbidden(*a,**k):raise AssertionError('invalid schema entered grammar')
    adapter.core.fit=forbidden
    try:
        for value in bad:
            audit={};events=[];before=copy.deepcopy(value);fitted=adapter.見本格子分類教材(value,audit,events.append)
            assert fitted.モデル群==()and 'failure'in audit and value==before and len(events)==1
            results.append({'input':value,'record':audit})
        changed=copy.deepcopy(teachers[:2]);changed[0]['output']=[[0]];audit={}
        fitted=adapter.見本格子分類教材(changed,audit)
        assert fitted.モデル群==()and audit['symbolically_impossible_models']==576 and audit['evaluated_teacher_returns']==0
        results.append({'name':'whole-grammar shape invariant','input':changed,'record':audit})
    finally:adapter.core.fit=original
    assert adapter.validate_teachers(teachers[:2])[0]and adapter.validate_teachers(tuple(teachers))[0]
    for grid in grids:
        if not adapter.valid_grid(grid):assert adapter.predict(grid,())[0]is None
    save(out,'strict-schema-and-shape-proof.json.gz',results);check('strict schema, minimum two distinct teachers, exact whole-grammar shape proof',True)

def resources(adapter,teachers,fitted,out):
    rows=[];original=adapter.core.proposal
    for exception in (MemoryError,RecursionError,TimeoutError):
        for mode in ('fit','prediction'):
            events=[];count=[0]
            def interrupted(*args,**kwargs):
                if count[0]==1:raise exception('injected after one completed allocation')
                count[0]+=1;return original(*args,**kwargs)
            adapter.core.proposal=interrupted
            try:
                if mode=='fit':adapter.fit(teachers,events.append)
                else:fitted.候補(teachers[0]['input'],{},events.append)
                raise AssertionError('resource exception was swallowed')
            except exception:
                e=events[-1];assert e['kind']=='evaluation_exception'and e['semantic_HOLD']is False
                active=e['partial_current_model'];prefix=active['allocation_prefix']
                saved=(len(prefix)+sum(len(x['record'].get('choices',[]))for x in active.get('parameter_returns',[]))
                       +sum(len(x.get('record',{}).get('allocations',[]))for x in e['completed_model_prefix']))
                assert saved==1
                rows.append({'exception':exception.__name__,'mode':mode,'events':events})
            finally:adapter.core.proposal=original
    save(out,'resource-exception-prefix-controls.json.gz',rows);check('resource errors propagate with exact completed allocation and model prefixes',len(rows)==6)

def native_cycles(adapter,native,helpers,fitted,teachers,out):
    identity=fitted.モデル群;before=dataclasses.asdict(fitted);results=[]
    class Recording(native.HDS学習実行系):
        def __init__(self,minimum):super().__init__(最小支持数=minimum);self.calls=[]
        def 実行(self,value):
            result=super().実行(value);exhaust=native.最小排気系().排出する(result)
            self.calls.append({'input':value,'result':result,'exhaust':exhaust});return result
        def 照会(self,*a,**k):raise AssertionError('query prohibited')
    original=adapter.fit
    def no_refit(*a,**k):raise AssertionError('native must reuse identical fitted model tuple')
    adapter.fit=no_refit
    try:
        for minimum in (5,6,3):
            machine=Recording(minimum);assert machine.台帳.全取得()=={};calls=[]
            def candidate(grid,policy):
                assert fitted.モデル群 is identity
                output,detail=fitted.候補(grid,policy);calls.append({'input':grid,'output':output,'record':detail});return output,detail
            boundary='ARC見本格子分類';record=helpers['候補機構を学習'](machine,{'train':teachers},(),boundary,candidate)
            assert record['採用可']and record['同値採用']==(minimum<=5)
            assert record['現在観測数']==5 and record['事前観測数']==0 and record['隔離数']==0
            observations=machine.台帳.取得('観測台帳');assert len(observations)==len(calls)==5
            assert len({encoded(o.原入力)for o in observations})==5
            references=tuple(o.経験識別子 for o in observations);last=machine.calls[-1]['result']
            equality=[p for p in last.有効原理群 if helpers['同値原理あり']([p],boundary)]
            assert all(p.根拠参照群==references and not p.反証参照群 for p in equality)
            for pair,observation,call in zip(teachers,observations,calls):assert observation.原入力=={'候補':pair['output'],'出力':pair['output']}and call['output']==pair['output']
            save(out,f'native-support-{minimum}.json.gz',{'support':minimum,'models':fitted.展開モデル(),'record':record,'candidate_calls':calls,'native_calls':machine.calls,'ledger':machine.台帳.JSON相当(),'raw_exhaust':machine.calls[-1]['exhaust'],'references':references,'equality':equality,'query_calls':0})
            results.append({'support':minimum,'equality':record['同値採用'],'current':5,'prior':0,'quarantine':0,'raw_exhaust':machine.calls[-1]['exhaust'].状態})
            assert fitted.モデル群 is identity and dataclasses.asdict(fitted)==before
    finally:adapter.fit=original
    check('same fitted 30 models, five distinct native observations, support5 true support6 false support3 true',len(results)==3)
    return results

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output-base');args=ap.parse_args()
    out=Path(tempfile.mkdtemp(prefix='arc2-candidate018-',dir=args.output_base));summary={'artifact_directory':str(out)}
    try:
        adapter,native,helpers=load(out);teachers=read('teachers.json.gz')['train'];original=read('teacher-returns.json.gz')
        audit={};journal=Journal(out/'full-teacher-fit-events.jsonl.gz');records=[]
        def observer(event):
            journal(event)
            if event['kind']=='model_completed':records.append(event['record'])
        start=time.process_time()
        try:fitted=adapter.見本格子分類教材(teachers,audit,observer)
        finally:journal.close()
        def fit_semantics(record):return {**{k:record[k]for k in ('model','colors','fit','parameter_failures','parameter_observations')},'teachers':[{k:r[k]for k in ('exact','output')}for r in record['teachers']]}
        assert equal([fit_semantics(r)for r in records],[fit_semantics(r)for r in original['records']])and equal(fitted.展開モデル(),original['retained'])
        check('all576 parameter fits, all2880 teacher grids HOLD and all30 retained match original',len(records)==576 and len(fitted.モデル群)==30)
        unobserved,raw_records=adapter.core.fit(teachers)
        check('observation on/off full output and record parity',equal(raw_records,records)and equal(unobserved,original['retained']))
        returns=[fitted.候補(pair['input'],{})for pair in teachers]
        assert all(x[0]==p['output']for x,p in zip(returns,teachers))
        save(out,'full-teacher-fit-and-returns.json.gz',{'fit_record':audit,'models':fitted.展開モデル(),'records':records,'returns':returns,'cpu_seconds':time.process_time()-start})
        def immutable(v):return isinstance(v,tuple)and all(immutable(x)for x in v)or v is None or type(v)in (str,int,float,bool)
        assert all(immutable(v)for v in dataclasses.astuple(fitted))
        before=fitted.記録();before['保持候補'].clear();assert fitted.適合数==30
        try:fitted.教師数=0
        except dataclasses.FrozenInstanceError:pass
        else:raise AssertionError('mutable state')
        check('immutable tuple/scalar-only fitted state and detached target-free record',True)
        original_controls(adapter,teachers,fitted,out);schema(adapter,teachers,out);resources(adapter,teachers,fitted,out)
        from 見本格子証明検査 import verify
        summary['proof_controls']=verify(adapter,fitted,F,out)
        check('bounded proof fallbacks, all30 stress models, 32 original-renderer witnesses and six exception prefixes',summary['proof_controls']['successful'])
        summary['native']=native_cycles(adapter,native,helpers,fitted,teachers,out)
        summary.update(successful=True,tests_run=len(PASSED),passed_cases=PASSED)
    except BaseException as error:
        summary.update(successful=False,tests_run=len(PASSED),passed_cases=PASSED,error=type(error).__name__,message=str(error),traceback=traceback.format_exc())
    save(out,'summary.json',summary);print(json.dumps(summary,ensure_ascii=False,sort_keys=True));return 0 if summary['successful']else 1

if __name__=='__main__':raise SystemExit(main())
