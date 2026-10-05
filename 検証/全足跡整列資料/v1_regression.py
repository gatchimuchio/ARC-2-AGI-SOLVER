#!/usr/bin/env python3
"""Portable public teacher-only whole-chart full-footprint regression, with isolated native support cycles."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,ast,copy,dataclasses,enum,gzip,hashlib,importlib,json,tempfile,time,traceback,types
from pathlib import Path
P=Path(__file__).resolve().parents[1];F=Path(__file__).resolve().parent/'全足跡整列資料';PASSED=[]
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
            boundary='ARC全足跡整列';record=helpers['候補機構を学習'](machine,{'train':teachers},(),boundary,candidate)
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

def load(out,repository_root=None):
    deployed=(P/'HDS/学習系統/v0.4.2/hds学習系統').is_dir()
    repo=Path(repository_root).resolve() if repository_root else P if deployed else P.parent/'source-evidence/repository'
    snapshot=not deployed and repository_root is None;manifest=read('依存固定.json.gz')
    for item in manifest['pure_dependencies']+manifest['native']['core']:
        need(sha(repo/item['path'])==item['sha256'],'dependency bytes '+item['path'])
    bridge=repo/'接続/ARC2/HDS接続.py';fixed=manifest['native']
    if snapshot:need(sha(bridge)==fixed['bridge_sha256'],'snapshot complete bridge')
    nodes={n.name:n for n in ast.parse(bridge.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name in fixed['ast']}
    check('three native helpers AST fixed; whole bridge hash only snapshot',{k:ast.dump(n,include_attributes=False)for k,n in nodes.items()}==fixed['ast'])
    corepath=P/'接続/ARC2/全足跡整列候補.py'
    semantic={n.name:ast.dump(n,include_attributes=False)for n in ast.parse(corepath.read_bytes()).body if isinstance(n,ast.FunctionDef)}
    need(semantic==manifest['staged_functions'] and sha(corepath)==manifest['runtime_core_sha256'],'staged runtime pin')
    need(all(semantic[k]==manifest['original_functions'][k] for k in manifest['exact_semantic_functions']),'four exact semantic ASTs')
    original_line='    actions = [apply_role(grid, role) for role in roles]'
    staged_line='    actions = []\n    for role in roles:\n        actions.append(apply_role(grid, role))'
    text=corepath.read_text();need(text.count(staged_line)==1,'one append substitution')
    normalized=next(n for n in ast.parse(text.replace(staged_line,original_line)).body if isinstance(n,ast.FunctionDef) and n.name=='render')
    check('four exact functions and normalized render AST preserve original grammar',ast.dump(normalized,include_attributes=False)==manifest['original_functions']['render'])
    sys.path.insert(0,str(repo));pkg=types.ModuleType('_candidate030_regression');pkg.__path__=[str(P/'接続/ARC2'),str(repo/'接続/ARC2')];sys.modules[pkg.__name__]=pkg
    adapter=importlib.import_module(pkg.__name__+'.全足跡整列教材')
    for name,expected in manifest['helper_ast'].items():
        module=importlib.import_module('接続.ARC2.'+expected['module']);need(getattr(adapter.core,name) is getattr(module,name),'direct import '+name)
    need(sha(P/'接続/ARC2/全足跡旧部品.py')==manifest['legacy_sha256'],'byte exact full legacy asset')
    need(sha(F/'token_sort_guard.py')==manifest['guard_sha256'],'byte exact old guard')
    check('direct accepted C4 clone shape helpers and byte identical legacy asset; guard comparison only')
    sys.path.insert(0,str(F));sys.modules['token_sort_primitives']=adapter.core.legacy
    oracle=importlib.import_module('independent_oracles');guard=importlib.import_module('token_sort_guard')
    sys.path.insert(0,str(repo/'HDS/学習系統/v0.4.2'));native=importlib.import_module('hds学習系統');nt=importlib.import_module('hds学習系統.型')
    scope={'deepcopy':copy.deepcopy,'学習入力':nt.学習入力,'観測事実':nt.観測事実}
    exec(compile(ast.Module(body=list(nodes.values()),type_ignores=[]),str(bridge),'exec'),scope)
    save(out,'source-verification.json',{'repository_root':str(repo),'deployed_mode':deployed,'actual_repository_argument':repository_root is not None,'snapshot_full_bridge_checked':snapshot,'dependency_manifest_sha256':sha(F/'依存固定.json.gz'),'bridge_actual_sha256':sha(bridge),'runtime_sha256':sha(corepath),'adapter_sha256':sha(P/'接続/ARC2/全足跡整列教材.py')})
    return adapter,native,scope,oracle,guard

def replay(adapter,teachers,oracle,guard,out):
    cases=oracle.fixture_cases();previous={r['name']:r for r in read('prototype-returns.json.gz')};rows=[];shared=0;raw=0;actions=0
    cases += [{'name':'teacher_'+str(i),'input':p['input'],'expected_output':p['output']}for i,p in enumerate(teachers)]
    for case in cases:
        name=case['name'];grid=copy.deepcopy(case['input']);before=encoded(grid);output,detail=adapter.render(grid,adapter.PROGRAMS[0]);old=previous[name]['new_full_return']
        need(equal(output,old['output']) and equal(detail,old['detail']),'all complete output/detail parity '+name)
        expected,roles=oracle.oracle(grid);need(output==case['expected_output']==expected,'independent expected '+name)
        need(len(roles)==len(detail['retained_roles'])==len(detail['actions']),'all roles '+name)
        legacy_out,legacy_detail=guard.guarded_render(grid);prior=previous[name]['legacy_guard_full_return']
        need(equal(legacy_out,prior['output']) and equal(legacy_detail,prior['detail']),'unchanged guard '+name)
        if legacy_out is not None and output is not None:shared+=1;need(legacy_out==output,'full legacy action parity')
        for role,action in zip(detail['retained_roles'],detail['actions']):
            left,right=role['extent'];cropped=[line[left:right+1]for line in grid];shifted=copy.deepcopy(role);shifted['extent']=[0,right-left];shifted['axis_cells']=[(r,c-left)for r,c in role['axis_cells']]
            for bar in shifted['bars']:bar['left']-=left;bar['right']-=left
            crop=adapter.core.apply_role(cropped,shifted)
            padded=[[role['background']]*left+line+[role['background']]*(len(grid[0])-right-1)for line in crop['output']] if crop['output'] is not None else None
            need(crop['status']==action['status'] and padded==action['output'],'frozen background inverse embedding')
        if name=='legacy_variable_width_37_to_35':need([sum(v!=0 for line in g for v in line)for g in (grid,output)]==[37,35],'variable widths do not conserve background')
        need(encoded(grid)==before,'immutable input');raw+=len(detail['raw_roles']);actions+=len(detail['actions'])
        rows.append({'name':name,'input':grid,'output':output,'record':detail,'legacy_output':legacy_out,'legacy_record':legacy_detail});check('complete prototype parity '+name)
    grid=next(c['input']for c in cases if c['name']=='legacy_even_asymmetric');_,detail=adapter.render(grid,adapter.PROGRAMS[0]);role=copy.deepcopy(detail['retained_roles'][0]);role['bars'].pop();failed=adapter.core.apply_role(grid,role);good=detail['actions'][0];output,reason=adapter.core.aggregate_actions([good,failed]);prior=previous['corrupted_certificate_role_cannot_be_dropped']
    need(equal([good,failed],prior['all_actions']) and output==prior['output'] and reason==prior['failure'],'defensive failure parity');rows.append({'name':prior['name'],'all_actions':[good,failed],'output':output,'failure':reason});check('defensive role failure remains with successful companion')
    need(len(rows)==82 and shared==42 and raw==3131 and actions==62,'original exact case and role counts')
    save(out,'prototype-82-full-returns.json.gz',rows)
    return {'cases':82,'synthetic_executions':78,'synthetic_unique_input_type_combinations':77,'defensive_cases':1,'teachers':3,'raw_pairs':raw,'retained_actions':actions,'old_action_parity':shared}

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
            invalid=type(value) in (list,tuple) and any(type(p) is not dict or set(p)!={'input','output'} or not adapter.valid_grid(p['input']) or not adapter.valid_grid(p['output'])for p in value)
            if invalid:adapter.gridkey=forbidden
            audit={};events=[];before=copy.deepcopy(value)
            try:obj=adapter.全足跡整列教材(value,audit,events.append)
            finally:adapter.gridkey=key
            need(obj.モデル群==() and audit.get('failure') and value==before and len(events)==1,'strict schema')
            rows.append({'input':value,'record':audit,'events':events})
    finally:adapter.render=original
    check('strict grid and pair schemas before hashing; two distinct inputs required')
    state=dataclasses.asdict(fitted);identity=fitted.モデル群;need(identity==adapter.PROGRAMS and not hasattr(fitted,'__dict__'),'fixed immutable state')
    try:fitted.教師数=0
    except dataclasses.FrozenInstanceError:pass
    else:raise AssertionError('mutable fit')
    detached=fitted.記録();detached['保持候補'].clear();need(dataclasses.asdict(fitted)==state,'detached record')
    source=copy.deepcopy(teachers);obj=adapter.全足跡整列教材(source);before=dataclasses.asdict(obj);source[0]['input'][0][0]=9;source[0]['output'].clear();need(dataclasses.asdict(obj)==before,'source detached')
    duplicate=adapter.全足跡整列教材(teachers+[teachers[0]]);need(duplicate.異入力数==3 and duplicate.教師数==4 and duplicate.モデル群==identity,'duplicates do not inflate distinct count')
    obj=adapter.全足跡整列教材(tuple(teachers),観測=lambda e:e.clear());need(obj.モデル群==identity,'detached observer')
    for grid in grids:need(fitted.候補(grid,{})[0] is None,'invalid grid rejection')
    invalid_models=[None,[],list(identity),('unknown',),(identity[0],identity[0]),(identity[0],True)]
    for models in invalid_models:
        output,record=adapter.predict(teachers[0]['input'],models);need(output is None and record['failure']=='invalid_retained_state','invalid model state');rows.append({'models':models,'record':record})
    check('immutable fixed activation; detached inputs observer records; strict state')
    wrong=copy.deepcopy(teachers);wrong[0]['output'][0][0]=(wrong[0]['output'][0][0]+1)%10;audit={};obj=adapter.全足跡整列教材(wrong,audit)
    need(obj.モデル群==() and audit['evaluated_teacher_returns']==3 and len(audit['program_returns'][0]['teachers'])==3,'all teacher returns after early mismatch');rows.append({'falsified_fit':audit});check('all teachers evaluated despite first equality failure')
    save(out,'strict-schema-and-retention.json.gz',rows)

def resources(adapter,teachers,oracle,out):
    rows=[];core=adapter.core;original=core.apply_role;two=next(c for c in oracle.fixture_cases()if c['name']=='two_success_agree');pairs=[teachers[0],{'input':two['input'],'output':two['expected_output']}]
    for error_type in (MemoryError,RecursionError,TimeoutError,ValueError):
        for mode in ('fit','prediction'):
            for observed in (False,True):
                error=error_type('injected after completed role action');count=[0];events=[];fail_at=3 if mode=='fit' else 2
                def failing(grid,role):
                    count[0]+=1
                    if count[0]==fail_at:raise error
                    return original(grid,role)
                core.apply_role=failing
                try:
                    if mode=='fit':adapter.全足跡整列教材(pairs,観測=events.append if observed else None)
                    else:adapter.predict(two['input'],adapter.PROGRAMS,events.append if observed else None)
                except error_type as caught:
                    need(caught is error,'original exception identity');outer=caught.evaluation_diagnostic;inner=outer['inner_diagnostic'];need(outer['stage']==mode and outer['active_call'],'outer active call')
                    if mode=='fit':need(len(outer['completed_teacher_returns'])==1 and outer['completed_teacher_returns'][0]['output']==teachers[0]['output'],'full completed teacher')
                    frame=next(f for f in inner['completed_resource_prefix']if f['function']=='render');need(len(frame['actions'])==1 and frame['actions'][0]['output'] is not None and len(frame['roles'])==2,'full completed action and all roles retained')
                    need(inner['resource_failure']==issubclass(error_type,adapter.RESOURCE_ERRORS) and not inner['semantic_HOLD'] and inner['resource_prefix_captured'],'resource distinct from semantic HOLD')
                    rows.append({'mode':mode,'observer':observed,'exception':error_type.__name__,'diagnostic':outer,'events':events});check('nested role and teacher exception prefix '+mode+' '+str(observed)+' '+error_type.__name__)
                else:raise AssertionError('exception swallowed')
                finally:core.apply_role=original
    def observer(event):
        if event['kind']=='program_return':raise MemoryError('observer failure after full return')
    try:adapter.predict(teachers[0]['input'],adapter.PROGRAMS,observer)
    except MemoryError as error:
        inner=error.evaluation_diagnostic['inner_diagnostic'];need(inner['completed_program_return']['output']==teachers[0]['output'],'completed raw return preserved');rows.append({'observer_failure':error.evaluation_diagnostic});check('completed raw return preserved on observer failure')
    else:raise AssertionError('observer failure swallowed')
    # Exercise an actual mid-enumeration frame, with already completed raw certificates.
    original_shape=core.grid_shape;original_components=core.same_color_components_4
    injection_enabled=[True]
    class ExplodingList(list):
        calls=0
        def __iter__(self):
            self.calls+=1
            if injection_enabled[0] and self.calls==3:
                injection_enabled[0]=False
                raise ValueError('injected parser continuation failure')
            return super().__iter__()
    def components(grid,color):return ExplodingList(original_components(grid,color))
    core.same_color_components_4=components
    try:adapter.predict(teachers[0]['input'],adapter.PROGRAMS)
    except ValueError as error:
        inner=error.evaluation_diagnostic['inner_diagnostic'];need(any(f.get('raw')for f in inner['completed_resource_prefix']),'completed parser certificates');rows.append({'parser_failure':error.evaluation_diagnostic});check('completed raw parser prefix without observer')
    else:raise AssertionError('parser injection not reached')
    finally:core.same_color_components_4=original_components
    save(out,'resource-and-exception-prefixes.json.gz',rows)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output-base');ap.add_argument('--repository-root');args=ap.parse_args()
    base=Path(args.output_base).resolve() if args.output_base else P.parent/'candidate030-results';base.mkdir(parents=True,exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix='arc2-candidate030-',dir=base));summary={'artifact_directory':str(out)}
    try:
        adapter,native,helpers,oracle,guard=load(out,args.repository_root);teachers=read('teachers.json.gz')['train'];audit={};journal=Journal(out/'teacher-fit-events.jsonl.gz');before=encoded(teachers)
        try:fitted=adapter.全足跡整列教材(teachers,audit,journal)
        finally:journal.close()
        need(fitted.モデル群==adapter.PROGRAMS and audit['evaluated_teacher_returns']==3 and encoded(teachers)==before,'three teacher fixed activation')
        direct=[fitted.候補(p['input'],{})for p in teachers];need(all(o==p['output']for (o,r),p in zip(direct,teachers)),'teacher reproductions')
        save(out,'full-teacher-fit-and-returns.json.gz',{'fit':audit,'models':fitted.モデル群,'returns':direct,'event_counts':journal.counts});check('fixed rule fit all three teachers and full direct returns')
        summary['prototype']=replay(adapter,teachers,oracle,guard,out);schema(adapter,teachers,fitted,out);resources(adapter,teachers,oracle,out)
        summary['native']=native_cycles(adapter,native,helpers,fitted,teachers,out)
        summary.update(successful=True,tests_run=len(PASSED),passed_cases=PASSED)
    except BaseException as error:summary.update(successful=False,tests_run=len(PASSED),passed_cases=PASSED,error=type(error).__name__,message=str(error),traceback=traceback.format_exc())
    save(out,'summary.json',summary);print(json.dumps(summary,ensure_ascii=False,sort_keys=True));return 0 if summary['successful'] else 1
if __name__=='__main__':raise SystemExit(main())
