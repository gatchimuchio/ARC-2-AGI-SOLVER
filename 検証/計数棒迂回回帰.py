#!/usr/bin/env python3
"""Portable public teacher-only counted-bar regression, with isolated native support cycles."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,ast,copy,dataclasses,enum,gzip,hashlib,importlib,json,tempfile,time,traceback,types
from pathlib import Path
P=Path(__file__).resolve().parents[1];F=Path(__file__).resolve().parent/'計数棒迂回資料';PASSED=[]
def serial(v):
    if dataclasses.is_dataclass(v):return serial(dataclasses.asdict(v))
    if isinstance(v,enum.Enum):return serial(v.value)
    if isinstance(v,dict):return {str(k):serial(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [serial(x) for x in v]
    if isinstance(v,(set,frozenset)):return [serial(x) for x in sorted(v,key=repr)]
    if v is None or type(v) in (str,int,float,bool):return v
    raise TypeError(type(v).__name__)
def encoded(v):return json.dumps(serial(v),ensure_ascii=False,sort_keys=True,separators=(',',':'))
def equal(a,b):return encoded(a)==encoded(b)
def need(condition,message):
    if not condition:raise AssertionError(message)
def check(name,condition=True):need(condition,name);PASSED.append(name)
def read(name):return json.loads(gzip.decompress((F/name).read_bytes()))
def save(out,name,value):
    data=encoded(value).encode();(out/name).write_bytes(gzip.compress(data,mtime=0) if name.endswith('.gz') else data)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
class Journal:
    def __init__(self,path):self.file=gzip.open(path,'wt',compresslevel=1);self.counts={}
    def __call__(self,event):
        self.file.write(encoded(event)+'\n');self.file.flush();kind=event['kind'];self.counts[kind]=self.counts.get(kind,0)+1
    def close(self):self.file.close()

def load(out,repository_root=None):
    deployed=(P/'HDS/学習系統/v0.4.2/hds学習系統').is_dir()
    repo=Path(repository_root).resolve() if repository_root else P if deployed else P.parent/'source-evidence/repository'
    snapshot=not deployed and repository_root is None;manifest=read('依存固定.json.gz')
    for item in manifest['pure_dependencies']+manifest['native']['core']:
        need(sha(repo/item['path'])==item['sha256'],'dependency bytes: '+item['path'])
    bridge=repo/'接続/ARC2/HDS接続.py';data=bridge.read_bytes();fixed=manifest['native']
    if snapshot:need(sha(bridge)==fixed['bridge_sha256'],'snapshot full bridge SHA')
    nodes={n.name:n for n in ast.parse(data).body if isinstance(n,ast.FunctionDef) and n.name in fixed['ast']}
    check('three native helper ASTs and accepted dependency bytes',{k:ast.dump(n,include_attributes=False) for k,n in nodes.items()}==fixed['ast'])
    now=ast.parse((P/'接続/ARC2/計数棒迂回候補.py').read_bytes())
    check('byte-frozen prototype and all semantic function ASTs',{n.name:ast.dump(n,include_attributes=False) for n in now.body if isinstance(n,ast.FunctionDef)}==manifest['semantic_ast'])
    sys.path.insert(0,str(repo))
    pkg=types.ModuleType('_candidate027_regression');pkg.__path__=[str(P/'接続/ARC2'),str(repo/'接続/ARC2')];sys.modules[pkg.__name__]=pkg
    adapter=importlib.import_module(pkg.__name__+'.計数棒迂回教材')
    for name,expected in manifest['helper_ast'].items():
        module=importlib.import_module('接続.ARC2.'+expected['module'])
        need(getattr(adapter.core,name) is getattr(module,name),'direct import '+name)
        source=ast.parse((repo/'接続/ARC2'/(expected['module']+'.py')).read_bytes())
        node=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name==name)
        need(ast.dump(node,include_attributes=False)==expected['ast'],'helper AST '+name)
    need(adapter.core.PROGRAMS==(0,1),'exact two-program grammar')
    need(sha(P/'接続/ARC2/計数棒迂回候補.py')==manifest['prototype_sha256'],'prototype exact bytes')
    check('four existing helper function identities directly imported and exact two-program grammar')
    sys.path.insert(0,str(repo/'HDS/学習系統/v0.4.2'));native=importlib.import_module('hds学習系統');nt=importlib.import_module('hds学習系統.型')
    scope={'deepcopy':copy.deepcopy,'学習入力':nt.学習入力,'観測事実':nt.観測事実}
    exec(compile(ast.Module(body=list(nodes.values()),type_ignores=[]),str(bridge),'exec'),scope)
    save(out,'source-verification.json',{'repository_root':str(repo),'deployed_mode':deployed,'actual_repository_argument':repository_root is not None,'snapshot_full_bridge_checked':snapshot,'manifest':manifest,'bridge_actual_sha256':sha(bridge),'runtime_sha256':sha(P/'接続/ARC2/計数棒迂回候補.py'),'adapter_sha256':sha(P/'接続/ARC2/計数棒迂回教材.py')})
    return adapter,native,scope

def native_cycles(adapter,native,helpers,fitted,teachers,out):
    identity=fitted.モデル群;before=dataclasses.asdict(fitted);results=[]
    class Recording(native.HDS学習実行系):
        def __init__(self,minimum):super().__init__(最小支持数=minimum);self.calls=[]
        def 実行(self,value):
            result=super().実行(value);exhaust=native.最小排気系().排出する(result);self.calls.append({'input':value,'result':result,'exhaust':exhaust});return result
        def 照会(self,*a,**k):raise AssertionError('query prohibited')
    original=adapter.fit
    def no_refit(*a,**k):raise AssertionError('same fixed activation must be reused')
    adapter.fit=no_refit
    try:
        for minimum in (4,5):
            machine=Recording(minimum);need(machine.台帳.全取得()=={},'fresh native');calls=[]
            def candidate(grid,policy):
                need(fitted.モデル群 is identity,'same model identity');output,detail=fitted.候補(grid,policy);calls.append({'input':grid,'output':output,'record':detail});return output,detail
            boundary='ARC計数棒迂回';record=helpers['候補機構を学習'](machine,{'train':teachers},(),boundary,candidate)
            need(record['採用可'] and record['同値採用']==(minimum==4),'native support gate')
            need(record['現在観測数']==4 and record['事前観測数']==0 and record['隔離数']==0,'native counts')
            observations=machine.台帳.取得('観測台帳');need(len(observations)==len(calls)==4 and len({encoded(o.原入力) for o in observations})==4,'same four distinct teachers')
            references=tuple(o.経験識別子 for o in observations);last=machine.calls[-1]['result'];equality=[p for p in last.有効原理群 if helpers['同値原理あり']([p],boundary)]
            need(bool(equality)==(minimum==4) and all(p.根拠参照群==references and not p.反証参照群 for p in equality),'native evidence refs')
            for pair,observation,call in zip(teachers,observations,calls):need(observation.原入力=={'候補':pair['output'],'出力':pair['output']} and call['output']==pair['output'],'native whole grids')
            save(out,f'native-support-{minimum}.json.gz',{'support':minimum,'models':fitted.モデル群,'record':record,'candidate_calls':calls,'native_calls':machine.calls,'ledger':machine.台帳.JSON相当(),'raw_exhaust':machine.calls[-1]['exhaust'],'references':references,'equality':equality,'query_calls':0})
            results.append({'support':minimum,'equality':record['同値採用'],'current':4,'prior':0,'quarantine':0,'raw_exhaust':machine.calls[-1]['exhaust'].状態})
            need(fitted.モデル群 is identity and dataclasses.asdict(fitted)==before,'unchanged fitted object')
    finally:adapter.fit=original
    check('same fixed fit and same four teachers fresh native support4 equality true support5 false; raw exhaust separate')
    return results

def replay(adapter,teachers,fitted,out):
    journal=Journal(out/'replay-events.jsonl.gz');rows=[]
    def run(name,g,expected,programs=(1,),expected_record=None):
        output,record=adapter.predict(g,programs,journal)
        need(equal(output,expected),'output '+name)
        if expected_record is not None:
            need(equal(record['returns'],expected_record['returns']),'all raw records '+name)
        rows.append({'name':name,'input':g,'expected':expected,'output':output,'record':record});check(name)
    try:
        for i,r in enumerate(read('synthetic-transform-results.json.gz')):
            run('independent D4 palette fixture '+str(i),r['input'],r['expected'],expected_record={'returns':[{'program':1,'output':r['output'],'record':r['record']}]})
        for r in read('boundary-results.json.gz'):
            run('boundary '+r['name'],r['input'],r['output'],tuple(r['programs']),r['record'])
        for r in read('count-interventions.json.gz'):
            fixture=r.get('fixture',r);run('intervention '+r['name'],fixture['input'],fixture['expected'] if 'expected' in fixture else fixture['output'])
        orders=[]
        for r in read('teacher-order-results.json.gz'):
            audit={};obj=adapter.計数棒迂回教材([teachers[i] for i in r['order']],audit,journal)
            need(obj.モデル群==tuple(r['retained']),'order retained')
            normalized=[{'program':p['program'],'all_exact':p['all_exact'],'teachers':[{'teacher':x['teacher_index'],'output':x['output'],'record':x['record'],'exact':x['exact']} for x in p['teachers']]} for p in audit['program_returns']]
            need(equal(normalized,r['returns']),'order raw returns');orders.append({'order':r['order'],'audit':audit});check('teacher order '+str(r['order']))
        save(out,'all-order-returns.json.gz',orders)
        tampered=copy.deepcopy(teachers);tampered[-1]['output'][0][0]=7;audit={};obj=adapter.計数棒迂回教材(tampered,audit,journal)
        need(obj.モデル群==() and audit['evaluated_teacher_returns']==8,'falsification exhaustive');save(out,'falsification.json.gz',audit);check('all eight returns retained after falsification')
    finally:journal.close()
    save(out,'all-replay-returns.json.gz',rows)

def schema(adapter,teachers,fitted,out):
    malformed=[None,{},[],teachers[:1],[teachers[0],teachers[0]],[dict(teachers[0],extra=1),teachers[1]],[{'input':teachers[0]['input']},teachers[1]],[None,teachers[1]]]
    grids=[None,[],[[]],[[True]],[[1.0]],[['1']],[[-1]],[[10]],[[0],[0,1]],((0,),),[(0,)],[[0]]*31,[[0]*31]]
    for field in ('input','output'):
        for grid in grids:
            pairs=copy.deepcopy(teachers);pairs[0][field]=grid;malformed.append(pairs)
    rows=[];original_render=adapter.render;original_key=adapter.gridkey
    def forbidden(*a,**k):raise AssertionError('invalid schema reached hashing or renderer')
    adapter.render=forbidden
    try:
        for value in malformed:
            invalid=type(value) in (list,tuple) and any(type(p) is not dict or set(p)!={'input','output'} or not adapter.valid_grid(p['input']) or not adapter.valid_grid(p['output']) for p in value)
            if invalid:adapter.gridkey=forbidden
            audit={};events=[];before=copy.deepcopy(value)
            try:obj=adapter.計数棒迂回教材(value,audit,events.append)
            finally:adapter.gridkey=original_key
            need(obj.モデル群==() and audit.get('failure') and value==before and len(events)==1,'strict schema')
            rows.append({'value':value,'audit':audit,'events':events})
    finally:adapter.render=original_render
    check('strict grids and teacher pairs before hashing; minimum two distinct inputs')
    state=dataclasses.asdict(fitted);identity=fitted.モデル群
    need(type(identity) is tuple and all(type(x) is int for x in identity) and not hasattr(fitted,'__dict__'),'immutable models')
    try:fitted.教師数=0
    except dataclasses.FrozenInstanceError:pass
    else:raise AssertionError('mutable fit')
    detached=fitted.記録();detached['保持候補'].clear();need(dataclasses.asdict(fitted)==state,'detached record')
    source=copy.deepcopy(teachers);obj=adapter.計数棒迂回教材(source);before=dataclasses.asdict(obj);source[0]['input'][0][0]=9;source[0]['output'].clear();need(dataclasses.asdict(obj)==before,'source detached')
    duplicate=adapter.計数棒迂回教材(teachers+[teachers[0]]);need(duplicate.異入力数==4 and duplicate.教師数==5 and duplicate.モデル群==identity,'distinct inputs')
    def hostile(e):e.clear()
    obj=adapter.計数棒迂回教材(tuple(teachers),観測=hostile);need(obj.モデル群==identity,'hostile observer detached')
    for g in grids:need(fitted.候補(g,{})[0] is None,'strict prediction')
    check('frozen tuple models; source record observer isolation and repeated inputs')
    # Instrumentation proves no retained program is discarded and no failure causes early completion.
    calls=[]
    def both(grid,program,observer=None,budget=None):
        calls.append(program);return original_render(grid,1,observer,budget)
    adapter.render=both
    try:
        audit={};obj=adapter.計数棒迂回教材(teachers,audit);need(obj.モデル群==(0,1) and len(calls)==8,'all matching models retained')
        calls.clear();output,record=obj.候補(teachers[0]['input'],{});need(output==teachers[0]['output'] and calls==[0,1] and len(record['returns'])==2,'all matching predictions')
        rows.append({'case':'instrumented_all_retained','audit':audit,'prediction':record})
        def first_fails(grid,program,observer=None,budget=None):
            calls.append(program)
            return (None,{'failure':'instrumented'}) if program==0 else original_render(grid,1,observer,budget)
        adapter.render=first_fails;calls.clear();output,record=adapter.predict(teachers[0]['input'],(0,1));need(output is None and calls==[0,1] and len(record['returns'])==2,'no failure short circuit');rows.append({'case':'instrumented_first_failure','record':record})
    finally:adapter.render=original_render
    check('all matching programs retained; full success consensus and complete failure returns')
    save(out,'strict-schema-and-retention.json.gz',rows)

def resources(adapter,teachers,fitted,out):
    rows=[];original=adapter.render
    for error_type in (MemoryError,RecursionError,TimeoutError,ValueError):
        for mode in ('fit','prediction'):
            calls=[0];events=[]
            def interrupt(grid,program,observer=None,budget=None):
                if calls[0]==1:raise error_type('injected after completed return')
                calls[0]+=1;return original(grid,program,observer,budget)
            adapter.render=interrupt
            try:
                if mode=='fit':adapter.計数棒迂回教材(teachers,観測=events.append)
                else:adapter.predict(teachers[0]['input'],(0,1),events.append)
            except error_type:
                e=events[-1];need(e['kind']=='evaluation_exception' and not e['semantic_HOLD'] and e['resource_failure']==issubclass(error_type,adapter.RESOURCE_ERRORS),'exception classification')
                field='completed_teacher_returns' if mode=='fit' else 'completed_program_returns';need(len(e[field])==1 and e['active_call'] is not None,'lossless completed prefix')
                rows.append({'mode':mode,'exception':error_type.__name__,'events':events});check('exception prefix '+mode+' '+error_type.__name__)
            else:raise AssertionError('exception swallowed')
            finally:adapter.render=original
    original_clone=adapter.core.clone_grid
    for error_type in (MemoryError,RecursionError,TimeoutError,ValueError):
        events=[]
        def interrupt_clone(grid):raise error_type('injected after geometric traversal')
        adapter.core.clone_grid=interrupt_clone
        try:fitted.候補(teachers[0]['input'],{},events.append)
        except error_type:
            e=next(e for e in events if e['kind']=='search_exception');prefix=e['completed_resource_prefix'];need(e['resource_prefix_captured'] and any(x.get('record',{}).get('states') and x.get('cells') for x in prefix),'internal state/path prefix')
            rows.append({'mode':'internal','exception':error_type.__name__,'events':events});check('internal geometry prefix '+error_type.__name__)
        else:raise AssertionError('exception swallowed')
        finally:adapter.core.clone_grid=original_clone
    fixtures=read('independent-fixtures.json.gz')
    for i,r in enumerate(read('resource-boundaries.json.gz')):
        events=[];grid=fixtures[r['fixture']]['input']
        try:output,record=adapter.predict(grid,(1,),events.append,budget=r['budget'])
        except adapter.ResourceIncomplete:
            need(r['budget']<r['required_work'],'unexpected budget exception')
            e=next(e for e in events if e['kind']=='search_exception');need(equal(e['completed_program_return']['record'],r['record']) and e['resource_failure'] and not e['semantic_HOLD'],'budget partial return lossless')
        else:need(r['budget']==r['required_work'] and output==r['output'],'exact work budget')
        rows.append({'mode':'budget','fixture':r['fixture'],'budget':r['budget'],'events':events});check('budget boundary '+str(i))
    events=[];raised=[False]
    def sink(event):
        events.append(event)
        if event['kind']=='program_return' and not raised[0]:raised[0]=True;raise MemoryError('injected observer copy boundary')
    try:fitted.候補(teachers[0]['input'],{},sink)
    except MemoryError:
        e=next(x for x in events if x['kind']=='search_exception');need(e['completed_program_return']['output']==teachers[0]['output'],'completed output before sink');rows.append({'mode':'observer','events':events});check('completed raw return survives observer exception')
    else:raise AssertionError('observer exception swallowed')
    save(out,'resource-and-exception-prefixes.json.gz',rows)


def resources_without_observer(adapter,teachers,fitted,out):
    rows=[];original_clone=adapter.core.clone_grid
    for error_type in (MemoryError,TimeoutError):
        for mode in ('fit','prediction'):
            error=error_type('injected after geometry without observer')
            def interrupt_clone(grid):raise error
            adapter.core.clone_grid=interrupt_clone
            try:
                if mode=='fit':adapter.計数棒迂回教材(teachers)
                else:fitted.候補(teachers[0]['input'],{})
            except error_type as caught:
                need(caught is error,'original exception identity rethrown')
                outer=caught.evaluation_diagnostic;inner=outer['inner_diagnostic']
                need(outer['kind']=='evaluation_exception' and outer['stage']==mode,'outer evaluation diagnostic')
                need(inner['kind']=='search_exception' and inner['resource_failure'] and not inner['semantic_HOLD'],'inner resource diagnostic')
                need(inner['resource_prefix_captured'] and any(x.get('record',{}).get('states') and x.get('cells') for x in inner['completed_resource_prefix']),'observer-free geometry prefix accessible')
                rows.append({'mode':mode,'exception':error_type.__name__,'original_exception_identity':True,'diagnostic':outer})
                check('observer-free nested geometry prefix '+mode+' '+error_type.__name__)
            else:raise AssertionError('observer-free exception swallowed')
            finally:adapter.core.clone_grid=original_clone
    save(out,'observer-free-resource-prefixes.json.gz',rows)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output-base');ap.add_argument('--repository-root');args=ap.parse_args()
    base=Path(args.output_base).resolve() if args.output_base else P.parent/'candidate027-results';base.mkdir(parents=True,exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix='arc2-candidate027-',dir=base));summary={'artifact_directory':str(out)}
    try:
        adapter,native,helpers=load(out,args.repository_root);teachers=read('teachers.json.gz')['train'];audit={};journal=Journal(out/'teacher-fit-events.jsonl.gz');before=encoded(teachers)
        try:fitted=adapter.計数棒迂回教材(teachers,audit,journal)
        finally:journal.close()
        need(fitted.モデル群==(1,) and audit['evaluated_teacher_returns']==8 and encoded(teachers)==before,'fit')
        original=read('teacher-results.json.gz')
        normalized=[{'program':p['program'],'all_exact':p['all_exact'],'teachers':[{'teacher':x['teacher_index'],'output':x['output'],'record':x['record'],'exact':x['exact']} for x in p['teachers']]} for p in audit['program_returns']]
        expected=original['returns'] if type(original) is dict and 'returns' in original else original
        need(equal(normalized,expected),'all original teacher returns')
        direct=[fitted.候補(p['input'],{}) for p in teachers];need(all(o==p['output'] for (o,r),p in zip(direct,teachers)),'four teacher reproductions')
        save(out,'full-teacher-fit-and-returns.json.gz',{'fit_record':audit,'models':fitted.モデル群,'returns':direct,'event_counts':journal.counts});check('two programs all eight full teacher returns exactly replayed; retained count+1')
        replay(adapter,teachers,fitted,out);schema(adapter,teachers,fitted,out);resources(adapter,teachers,fitted,out)
        resources_without_observer(adapter,teachers,fitted,out)
        summary['native']=native_cycles(adapter,native,helpers,fitted,teachers,out)
        summary.update(successful=True,tests_run=len(PASSED),passed_cases=PASSED)
    except BaseException as error:summary.update(successful=False,tests_run=len(PASSED),passed_cases=PASSED,error=type(error).__name__,message=str(error),traceback=traceback.format_exc())
    save(out,'summary.json',summary);print(json.dumps(summary,ensure_ascii=False,sort_keys=True));return 0 if summary['successful'] else 1
if __name__=='__main__':raise SystemExit(main())
