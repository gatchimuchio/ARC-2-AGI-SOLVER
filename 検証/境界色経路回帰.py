#!/usr/bin/env python3
"""Portable public teacher-only boundary color regression, with isolated native support cycles."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,ast,copy,dataclasses,enum,gzip,hashlib,importlib,json,tempfile,time,traceback,types
from pathlib import Path
P=Path(__file__).resolve().parents[1];F=Path(__file__).resolve().parent/'境界色経路資料';PASSED=[]
def serial(v):
    if dataclasses.is_dataclass(v):return serial(dataclasses.asdict(v))
    if isinstance(v,enum.Enum):return serial(v.value)
    if isinstance(v,dict):return {str(k):serial(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [serial(x) for x in v]
    if isinstance(v,(set,frozenset)):return [serial(x) for x in sorted(v,key=repr)]
    if v is None or type(v) in (str,int,float,bool):return v
    if isinstance(v,str):return {'string_subclass':type(v).__name__,'value':str(v)}
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
    now=ast.parse((P/'接続/ARC2/境界色経路候補.py').read_bytes())
    check('six original semantic function ASTs',{n.name:ast.dump(n,include_attributes=False) for n in now.body if isinstance(n,ast.FunctionDef)}==manifest['semantic_ast'])
    sys.path.insert(0,str(repo))
    pkg=types.ModuleType('_candidate028_regression');pkg.__path__=[str(P/'接続/ARC2'),str(repo/'接続/ARC2')];sys.modules[pkg.__name__]=pkg
    adapter=importlib.import_module(pkg.__name__+'.境界色経路教材')
    for name,expected in manifest['helper_ast'].items():
        module=importlib.import_module('接続.ARC2.'+expected['module'])
        need(getattr(adapter.core.turn if name in ('valid_grid','body_components') else adapter.core,name) is getattr(module,name),'direct import '+name)
        source=ast.parse((repo/'接続/ARC2'/(expected['module']+'.py')).read_bytes())
        node=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name==name)
        need(ast.dump(node,include_attributes=False)==expected['ast'],'helper AST '+name)
    need(adapter.core.PHASES==('continuous','contact_tick','reset_after_turn'),'exact three-phase grammar')
    need(sha(P/'接続/ARC2/境界色経路候補.py')==manifest['runtime_core_sha256'],'frozen runtime bytes')
    check('three existing helper function identities directly imported and exact three-phase grammar')
    sys.path.insert(0,str(repo/'HDS/学習系統/v0.4.2'));native=importlib.import_module('hds学習系統');nt=importlib.import_module('hds学習系統.型')
    scope={'deepcopy':copy.deepcopy,'学習入力':nt.学習入力,'観測事実':nt.観測事実}
    exec(compile(ast.Module(body=list(nodes.values()),type_ignores=[]),str(bridge),'exec'),scope)
    save(out,'source-verification.json',{'repository_root':str(repo),'deployed_mode':deployed,'actual_repository_argument':repository_root is not None,'snapshot_full_bridge_checked':snapshot,'manifest':manifest,'bridge_actual_sha256':sha(bridge),'runtime_sha256':sha(P/'接続/ARC2/境界色経路候補.py'),'adapter_sha256':sha(P/'接続/ARC2/境界色経路教材.py')})
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
        for minimum in (3,4):
            machine=Recording(minimum);need(machine.台帳.全取得()=={},'fresh native');calls=[]
            def candidate(grid,policy):
                need(fitted.モデル群 is identity,'same model identity');output,detail=fitted.候補(grid,policy);calls.append({'input':grid,'output':output,'record':detail});return output,detail
            boundary='ARC境界色経路';record=helpers['候補機構を学習'](machine,{'train':teachers},(),boundary,candidate)
            need(record['採用可'] and record['同値採用']==(minimum==3),'native support gate')
            need(record['現在観測数']==3 and record['事前観測数']==0 and record['隔離数']==0,'native counts')
            observations=machine.台帳.取得('観測台帳');need(len(observations)==len(calls)==3 and len({encoded(o.原入力) for o in observations})==3,'same three distinct teachers')
            references=tuple(o.経験識別子 for o in observations);last=machine.calls[-1]['result'];equality=[p for p in last.有効原理群 if helpers['同値原理あり']([p],boundary)]
            need(bool(equality)==(minimum==3) and all(p.根拠参照群==references and not p.反証参照群 for p in equality),'native evidence refs')
            for pair,observation,call in zip(teachers,observations,calls):need(observation.原入力=={'候補':pair['output'],'出力':pair['output']} and call['output']==pair['output'],'native whole grids')
            save(out,f'native-support-{minimum}.json.gz',{'support':minimum,'models':fitted.モデル群,'record':record,'candidate_calls':calls,'native_calls':machine.calls,'ledger':machine.台帳.JSON相当(),'raw_exhaust':machine.calls[-1]['exhaust'],'references':references,'equality':equality,'query_calls':0})
            results.append({'support':minimum,'equality':record['同値採用'],'current':3,'prior':0,'quarantine':0,'raw_exhaust':machine.calls[-1]['exhaust'].状態})
            need(fitted.モデル群 is identity and dataclasses.asdict(fitted)==before,'unchanged fitted object')
    finally:adapter.fit=original
    check('same fixed fit and same three teachers fresh native support3 equality true support4 false; raw exhaust separate')
    return results

def replay(adapter,teachers,fitted,out):
    fixtures=read('independent-fixtures.json.gz');saved=read('independent-results.json.gz')['results'];rows=[]
    core=adapter.core;parse,clone,components=core.parse,core.clone_grid,core.turn.body_components
    for f,previous in zip(fixtures,saved):
        need(f['id']==previous['id'],'fixture order');roles,detail=parse(copy.deepcopy(f['input']))
        need(equal(roles,previous['parse_roles']) and equal(detail,previous['parse_detail']),'full raw roles '+f['id'])
        for phase,e in f['expected'].items():
            counts=[0];grid=copy.deepcopy(f['input']);before=encoded(grid);row={'id':f['id'],'category':f['category'],'phase':phase,'input':grid,'expected':e}
            if 'inject_parse_role' in f:core.parse=lambda g:([copy.deepcopy(f['inject_parse_role'])],{'raw_role_count':1,'engine_injected':True,'all_role_trials':[]})
            if f.get('inject_memoryerror')=='parse_components':
                def failing(*a,**k):raise MemoryError('independent validation injected component resource exception')
                core.turn.body_components=failing
            elif 'inject_memoryerror' in f:
                fail_at=1 if f['inject_memoryerror']=='clone_first' else 2
                def failing(*a,**k):
                    counts[0]+=1
                    if counts[0]==fail_at:raise MemoryError('independent validation injected clone resource exception')
                    return clone(*a,**k)
                core.clone_grid=failing
            try:
                # Only the frozen unknown-phase API control calls the core directly;
                # production strict rejection is checked separately below.
                output,record=(core.render if f['category']=='api_invalid_argument' else adapter.render)(grid,phase)
                row.update(output=output,record=record)
                need('exception_type' not in e,'missing frozen exception')
                prior=next(x for x in previous['results'] if x['semantics']==phase)
                need(equal(output,e['returned_grid']) and equal(output,prior['returned_grid']) and equal(record,prior['detail']),'full independent outcome '+f['id']+' '+phase)
            except MemoryError as error:
                need(e.get('exception_type')=='MemoryError','unexpected resource exception')
                row.update(exception=type(error).__name__,diagnostic=getattr(error,'evaluation_diagnostic',None))
                need(row['diagnostic'] and row['diagnostic']['resource_failure'] and not row['diagnostic']['semantic_HOLD'],'resource classified')
            finally:core.parse=parse;core.clone_grid=clone;core.turn.body_components=components
            need(encoded(grid)==before,'input unchanged '+f['id']);rows.append(row);check('independent '+f['id']+' '+phase)
    need(len(rows)==109,'109 independent executions');save(out,'independent-all-109-returns.json.gz',rows)
    rows=[]
    for i,prior in enumerate(read('equivariance-full.json.gz')):
        output,record=fitted.候補(prior['input'],{})
        need(equal(output,prior['expected']) and equal(record['returns'][0]['record'],prior['detail']),'teacher-derived parity')
        rows.append({'teacher':prior['teacher'],'transform':prior['transform'],'input':prior['input'],'expected':prior['expected'],'output':output,'record':record});check('teacher-derived transform '+str(i))
    need(len(rows)==33,'33 teacher transforms');save(out,'teacher-derived-33-returns.json.gz',rows)
    wrong=copy.deepcopy(teachers);wrong[-1]['output'][0][0]=(wrong[-1]['output'][0][0]+1)%10
    audit={};obj=adapter.境界色経路教材(wrong,audit);need(obj.モデル群==() and audit['evaluated_teacher_returns']==9,'all nine falsification returns');save(out,'falsification.json.gz',audit);check('all three phases and nine returns after target falsification')

def schema(adapter,teachers,fitted,out):
    malformed=[None,{},[],teachers[:1],[teachers[0],teachers[0]],[dict(teachers[0],extra=1),teachers[1]],[{'input':teachers[0]['input']},teachers[1]],[None,teachers[1]]]
    grids=[None,[],[[]],[[True]],[[1.0]],[['1']],[[-1]],[[10]],[[0],[0,1]],((0,),),[(0,)],[[0]]*31,[[0]*31]]
    for field in ('input','output'):
        for grid in grids:
            pairs=copy.deepcopy(teachers);pairs[0][field]=grid;malformed.append(pairs)
    rows=[];original,key=adapter.render,adapter.gridkey
    def forbidden(*a,**k):raise AssertionError('invalid schema reached hashing or renderer')
    adapter.render=forbidden
    try:
        for value in malformed:
            invalid=type(value) in (list,tuple) and any(type(p) is not dict or set(p)!={'input','output'} or not adapter.valid_grid(p['input']) or not adapter.valid_grid(p['output']) for p in value)
            if invalid:adapter.gridkey=forbidden
            audit={};events=[];before=copy.deepcopy(value)
            try:obj=adapter.境界色経路教材(value,audit,events.append)
            finally:adapter.gridkey=key
            need(obj.モデル群==() and audit.get('failure') and value==before and len(events)==1,'strict schema')
            rows.append({'input':value,'record':audit,'events':events})
    finally:adapter.render=original
    check('strict ARC pairs and grids validated before hashing; minimum two distinct inputs')
    state=dataclasses.asdict(fitted);identity=fitted.モデル群
    need(type(identity) is tuple and all(type(x) is str for x in identity) and not hasattr(fitted,'__dict__'),'immutable tuple')
    try:fitted.教師数=0
    except dataclasses.FrozenInstanceError:pass
    else:raise AssertionError('mutable fitted state')
    detached=fitted.記録();detached['保持候補'].clear();need(dataclasses.asdict(fitted)==state,'detached record')
    source=copy.deepcopy(teachers);obj=adapter.境界色経路教材(source);before=dataclasses.asdict(obj);source[0]['input'][0][0]=9;source[0]['output'].clear();need(dataclasses.asdict(obj)==before,'source detached')
    duplicate=adapter.境界色経路教材(teachers+[teachers[0]]);need(duplicate.異入力数==3 and duplicate.教師数==4 and duplicate.モデル群==identity,'distinct count')
    obj=adapter.境界色経路教材(tuple(teachers),観測=lambda e:e.clear());need(obj.モデル群==identity,'observer detached')
    for grid in grids:need(fitted.候補(grid,{})[0] is None,'invalid prediction HOLD')
    check('frozen phase tuple; detached source record and observer; duplicate input count')
    invalid_phases=['unknown','Continuous','continuous ',None,True,0,[],{},('continuous',)]
    class S(str):pass
    invalid_phases.append(S('continuous'));core_render=adapter.core.render;adapter.core.render=forbidden
    try:
        for phase in invalid_phases:
            output,record=adapter.render(teachers[0]['input'],phase);need(output is None and record['failure']=='invalid_phase_program','invalid phase whole HOLD');rows.append({'phase':phase,'record':record})
        for models in [None,[],['continuous'],('continuous','unknown'),('unknown','continuous'),('continuous','continuous'),('continuous',True),('continuous',[]),(S('continuous'),)]:
            output,record=adapter.predict(teachers[0]['input'],models);need(output is None and record['failure']=='invalid_retained_state' and record['returns']==[],'invalid retained whole HOLD');rows.append({'models':models,'record':record})
    finally:adapter.core.render=core_render
    check('unknown phase and invalid retained state reject whole before core; no filtering')
    calls=[]
    def all_match(grid,program,observer=None):calls.append(program);return original(grid,'continuous',observer)
    adapter.render=all_match
    try:
        audit={};obj=adapter.境界色経路教材(teachers,audit);need(obj.モデル群==adapter.PROGRAMS and len(calls)==9,'all phases retained');calls.clear()
        output,record=obj.候補(teachers[0]['input'],{});need(output==teachers[0]['output'] and calls==list(adapter.PROGRAMS) and len(record['returns'])==3,'all phases predicted');rows.append({'all_retained_fit':audit,'prediction':record})
        def first_fails(grid,program,observer=None):
            calls.append(program)
            return (None,{'failure':'instrumented'}) if program=='continuous' else original(grid,'continuous',observer)
        adapter.render=first_fails;calls.clear();output,record=adapter.predict(teachers[0]['input'],adapter.PROGRAMS);need(output is None and calls==list(adapter.PROGRAMS) and len(record['returns'])==3,'no failure short circuit');rows.append({'first_failure':record})
        def disagree(grid,program,observer=None):
            calls.append(program);output,record=original(grid,'continuous',observer)
            if program=='contact_tick':output[0][0]=(output[0][0]+1)%10
            return output,record
        adapter.render=disagree;calls.clear();output,record=adapter.predict(teachers[0]['input'],adapter.PROGRAMS);need(output is None and record['failure']=='retained_program_conflict' and len(calls)==3,'all retained conflict HOLD');rows.append({'disagreement':record})
    finally:adapter.render=original
    check('all three models retained when fitting; complete success failure and conflicting consensus')
    save(out,'strict-schema-and-retention.json.gz',rows)

def resources(adapter,teachers,fitted,out):
    rows=[];core=adapter.core;clone,components=core.clone_grid,core.turn.body_components
    for error_type in (MemoryError,RecursionError,TimeoutError,ValueError):
        for mode in ('fit','prediction'):
            for observed in (False,True):
                error=error_type('injected after completed models and geometric trace');count=[0];events=[];fail_at=10 if mode=='fit' else 4
                def interrupt(grid):
                    count[0]+=1
                    if count[0]==fail_at:raise error
                    return clone(grid)
                core.clone_grid=interrupt
                try:
                    if mode=='fit':adapter.境界色経路教材(teachers,観測=events.append if observed else None)
                    else:adapter.predict(teachers[0]['input'],adapter.PROGRAMS,events.append if observed else None)
                except error_type as caught:
                    need(caught is error,'same error identity');outer=caught.evaluation_diagnostic;inner=outer['inner_diagnostic']
                    need(outer['stage']==mode and len(outer['completed_program_returns'])==1 and outer['active_call'],'completed earlier program')
                    if mode=='fit':need(len(outer['completed_teacher_returns'])==1,'completed current teacher prefix')
                    need(inner['resource_prefix_captured'] and any(x.get('traces') and x.get('proposal') and x.get('roles') for x in inner['completed_resource_prefix']),'geometric prefix')
                    need(inner['resource_failure']==issubclass(error_type,adapter.RESOURCE_ERRORS) and not inner['semantic_HOLD'],'logical/resource distinction')
                    rows.append({'mode':mode,'observed':observed,'exception':error_type.__name__,'diagnostic':outer,'events':events});check('nested completed model and geometry prefix '+mode+' '+str(observed)+' '+error_type.__name__)
                else:raise AssertionError('exception swallowed')
                finally:core.clone_grid=clone
    count=[0]
    def interrupt_components(*a,**k):
        count[0]+=1
        if count[0]==2:raise MemoryError('parser prefix')
        return components(*a,**k)
    core.turn.body_components=interrupt_components
    try:fitted.候補(teachers[0]['input'],{})
    except MemoryError as error:
        prefix=error.evaluation_diagnostic['inner_diagnostic']['completed_resource_prefix'];need(any(x.get('trials') for x in prefix),'parser trials prefix');rows.append({'mode':'parser','diagnostic':error.evaluation_diagnostic});check('completed parser trials survive without observer')
    finally:core.turn.body_components=components
    def observer(event):
        if event['kind']=='program_return':raise MemoryError('observer boundary')
    try:fitted.候補(teachers[0]['input'],{},observer)
    except MemoryError as error:
        inner=error.evaluation_diagnostic['inner_diagnostic'];need(inner['completed_program_return']['output']==teachers[0]['output'],'complete return before observer');rows.append({'mode':'observer','diagnostic':error.evaluation_diagnostic});check('complete raw return survives failing observer')
    else:raise AssertionError('observer error swallowed')
    save(out,'resource-and-exception-prefixes.json.gz',rows)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output-base');ap.add_argument('--repository-root');args=ap.parse_args()
    base=Path(args.output_base).resolve() if args.output_base else P.parent/'candidate028-results';base.mkdir(parents=True,exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix='arc2-candidate028-',dir=base));summary={'artifact_directory':str(out)}
    try:
        adapter,native,helpers=load(out,args.repository_root);teachers=read('teachers.json.gz')['train'];audit={};journal=Journal(out/'teacher-fit-events.jsonl.gz');before=encoded(teachers)
        try:fitted=adapter.境界色経路教材(teachers,audit,journal)
        finally:journal.close()
        need(fitted.モデル群==('continuous',) and audit['evaluated_teacher_returns']==9 and encoded(teachers)==before,'fit')
        prior=read('teacher-probe-full.json.gz')
        for p in audit['program_returns']:
            for row in p['teachers']:
                old=next(r for r in prior[row['teacher_index']]['candidates'] if r['semantics']==p['program'])
                need(equal(row['output'],old['returned_grid']) and equal(row['record'],old['detail']) and row['exact']==old['teacher_equal'],'all original teacher records')
        direct=[fitted.候補(p['input'],{}) for p in teachers];need(all(o==p['output'] for (o,r),p in zip(direct,teachers)),'three teacher reproductions')
        save(out,'full-teacher-fit-and-returns.json.gz',{'fit':audit,'models':fitted.モデル群,'returns':direct,'event_counts':journal.counts});check('all nine phase teacher returns reproduced; continuous alone fits')
        replay(adapter,teachers,fitted,out);schema(adapter,teachers,fitted,out);resources(adapter,teachers,fitted,out)
        summary['native']=native_cycles(adapter,native,helpers,fitted,teachers,out)
        summary.update(successful=True,tests_run=len(PASSED),passed_cases=PASSED,independent_executions=109,teacher_derived_transforms=33)
    except BaseException as error:summary.update(successful=False,tests_run=len(PASSED),passed_cases=PASSED,error=type(error).__name__,message=str(error),traceback=traceback.format_exc())
    save(out,'summary.json',summary);print(json.dumps(summary,ensure_ascii=False,sort_keys=True));return 0 if summary['successful'] else 1
if __name__=='__main__':raise SystemExit(main())
