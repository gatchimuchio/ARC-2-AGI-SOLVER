#!/usr/bin/env python3
"""Portable public teacher-only profile-stack regression, with isolated native support cycles."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,ast,copy,dataclasses,enum,gzip,hashlib,importlib,json,tempfile,time,traceback,types
from pathlib import Path
P=Path(__file__).resolve().parents[1];F=Path(__file__).resolve().parent/'帯profile積層資料';PASSED=[]
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
    now=ast.parse((P/'接続/ARC2/帯profile積層候補.py').read_bytes())
    check('six unchanged pure semantic function ASTs',{n.name:ast.dump(n,include_attributes=False) for n in now.body if isinstance(n,ast.FunctionDef)}==manifest['semantic_ast'])
    pkg=types.ModuleType('_candidate024_regression');pkg.__path__=[str(P/'接続/ARC2'),str(repo/'接続/ARC2')];sys.modules[pkg.__name__]=pkg
    adapter=importlib.import_module(pkg.__name__+'.帯profile積層教材')
    aliases={'_orthogonal_components':'components','transform_grid_by_name':'transform','valid_grid':'valid_grid','oriented_cells':'normalize_cells'}
    for name,expected in manifest['helper_ast'].items():
        module=importlib.import_module(pkg.__name__+'.'+expected['module'])
        need(getattr(adapter.core,aliases[name]) is getattr(module,name),'direct import '+name)
        source=ast.parse((repo/'接続/ARC2'/(expected['module']+'.py')).read_bytes())
        node=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name==name)
        need(ast.dump(node,include_attributes=False)==expected['ast'],'helper AST '+name)
    check('four existing helper identities directly imported with fixed ASTs')
    sys.path.insert(0,str(repo/'HDS/学習系統/v0.4.2'));native=importlib.import_module('hds学習系統');nt=importlib.import_module('hds学習系統.型')
    scope={'deepcopy':copy.deepcopy,'学習入力':nt.学習入力,'観測事実':nt.観測事実}
    exec(compile(ast.Module(body=list(nodes.values()),type_ignores=[]),str(bridge),'exec'),scope)
    save(out,'source-verification.json',{'repository_root':str(repo),'deployed_mode':deployed,'actual_repository_argument':repository_root is not None,'snapshot_full_bridge_checked':snapshot,'manifest':manifest,'bridge_actual_sha256':sha(bridge),'runtime_sha256':sha(P/'接続/ARC2/帯profile積層候補.py'),'adapter_sha256':sha(P/'接続/ARC2/帯profile積層教材.py')})
    return adapter,native,scope

def controls(adapter,teachers,fitted,out):
    cases=read('controls142.json.gz');need(len(cases)==142,'142 active fixtures');rows=[];journal=Journal(out/'all142-control-events.jsonl.gz')
    try:
        for case in cases:
            grid=copy.deepcopy(case['input'])
            if case['name']=='strict-tuple-grid':grid=tuple(tuple(row) for row in grid)
            elif case['name']=='strict-tuple-row':grid=[tuple(row) for row in grid]
            output,detail=adapter.core.infer(grid);wrapped,record=fitted.候補(grid,{},journal)
            need(equal(output,case['expected']) and equal(detail,case['diagnostic']),'frozen control replay '+case['name'])
            need(wrapped==output,'wrapper output '+case['name'])
            if adapter.valid_grid(grid):need(equal(record['returns'][0]['record'],detail),'full wrapper record')
            rows.append({'name':case['name'],'input':grid,'expected':case['expected'],'actual_output':wrapped,'pure_record':detail,'wrapper_record':record})
    finally:journal.close()
    save(out,'all142-controls-full-returns.json.gz',rows)
    check('142 public controls exact outputs and full raw replay',len(rows)==142)
    ambiguous=next(x for x in rows if x['name']=='extra-L-piece-ambiguous-five-complete-grids')
    check('historical extra-L expectation corrected only; all five complete grids retained',ambiguous['actual_output'] is None and ambiguous['pure_record']['unique_grid_count']==5)
    roles=adapter.core.enumerate_roles(teachers[0]['input'])[0];role=roles[0];original_enum=adapter.core.enumerate_roles;original_solve=adapter.core.solve_role;calls=[]
    def fake_enum(grid):return [dict(role,role_id=0),dict(role,role_id=1)],[{'injected_control':True}]
    def fail_first(r):
        calls.append(r['role_id']);result=original_solve(r)
        if r['role_id']==0:result['arrangements']=[]
        return result
    adapter.core.enumerate_roles=fake_enum;adapter.core.solve_role=fail_first
    try:output,record=adapter.core.infer(teachers[0]['input'])
    finally:adapter.core.enumerate_roles=original_enum;adapter.core.solve_role=original_solve
    need(output is None and record['failure']=='role_has_no_complete_inventory_arrangement' and calls==[0,1],'all roles after failure')
    save(out,'injected-all-role-retention.json.gz',{'test_kind':'instrumented two-role control','calls':calls,'output':output,'record':record})
    check('whole role failure does not skip later roles or select a success')

def schema(adapter,teachers,fitted,out):
    bad=[None,{},[],teachers[:1],[teachers[0],teachers[0]],[dict(teachers[0],extra=1),teachers[1]],[{'input':teachers[0]['input']},teachers[1]],[None,teachers[1]]]
    grids=[None,[],[[]],[[True]],[[1.0]],[['1']],[[-1]],[[10]],[[0],[0,1]],((0,),),[(0,)],[[0]]*31,[[0]*31]]
    for field in ('input','output'):
        for grid in grids:
            pairs=copy.deepcopy(teachers);pairs[0][field]=grid;bad.append(pairs)
    original_render=adapter.render;original_key=adapter.core.gridkey;rows=[]
    def forbidden(*a,**k):raise AssertionError('invalid schema entered search or hashing')
    adapter.render=forbidden
    try:
        for value in bad:
            events=[];audit={};before=copy.deepcopy(value)
            # Too few valid inputs may form keys; malformed grids must not.
            malformed=type(value) in (list,tuple) and any(type(p) is not dict or set(p)!={'input','output'} or not adapter.valid_grid(p['input']) or not adapter.valid_grid(p['output']) for p in value)
            if malformed:adapter.core.gridkey=forbidden
            try:obj=adapter.帯profile積層教材(value,audit,events.append)
            finally:adapter.core.gridkey=original_key
            need(obj.モデル群==() and bool(audit.get('failure')) and value==before and len(events)==1,'strict validation')
            rows.append({'input':value,'audit':audit,'event_count':len(events)})
    finally:adapter.render=original_render
    need(adapter.validate_teachers(tuple(teachers))[0],'tuple teacher container')
    # Two distinct boards are the minimum; repeated observations do not create parameters.
    duplicated=adapter.帯profile積層教材(teachers+[teachers[0]])
    need(duplicated.異入力数==2 and duplicated.教師数==3 and duplicated.モデル群==fitted.モデル群,'distinct input count')
    altered=copy.deepcopy(teachers);wrong=altered[0]['output'];a=(0,0);b=next((r,c) for r,row in enumerate(wrong) for c,v in enumerate(row) if v!=wrong[0][0]);wrong[a[0]][a[1]],wrong[b[0]][b[1]]=wrong[b[0]][b[1]],wrong[a[0]][a[1]];audit={};events=[]
    obj=adapter.帯profile積層教材(altered,audit,events.append)
    need(obj.モデル群==() and audit['evaluated_teacher_returns']==2 and len(audit['teacher_returns'])==2,'no teacher mismatch shortcut')
    rows.append({'name':'first conservation-valid mismatch still enumerates both teachers','audit':audit,'events':events})
    for grid in grids:need(fitted.候補(grid,{})[0] is None,'invalid prediction')
    state=dataclasses.asdict(fitted);identity=fitted.モデル群
    def immutable(value):return (type(value) is tuple and all(immutable(v) for v in value)) or value is None or type(value) in (str,int)
    need(all(immutable(v) for v in dataclasses.astuple(fitted)) and not hasattr(fitted,'__dict__'),'immutable nested state')
    detached=fitted.記録();detached['保持候補'].clear();need(dataclasses.asdict(fitted)==state,'detached 記録')
    try:fitted.教師数=0
    except dataclasses.FrozenInstanceError:pass
    else:raise AssertionError('mutable fit')
    source=copy.deepcopy(teachers);obj=adapter.帯profile積層教材(source);before=dataclasses.asdict(obj);source[0]['input'][0][0]=9;source[0]['output'].clear()
    need(dataclasses.asdict(obj)==before,'source detached')
    def hostile(event):event.clear()
    hostile_fit=adapter.帯profile積層教材(teachers,観測=hostile)
    need(hostile_fit.モデル群==identity and all(hostile_fit.候補(t['input'],{},hostile)[0]==t['output'] for t in teachers),'observer detached')
    for order in (teachers,teachers[::-1]):need(adapter.帯profile積層教材(order).モデル群==identity,'order invariance')
    save(out,'strict-schema-immutability.json.gz',rows)
    check('strict ARC and teacher schema validated before hashing; at least two distinct inputs')
    check('immutable fixed activation no learned parameters; detached sources records and observers')
    check('all conservation-valid teacher returns retained after first mismatch; teacher order invariant')

def resources(adapter,teachers,fitted,out):
    rows=[];original=adapter.render
    for error_type in (MemoryError,RecursionError,TimeoutError):
        calls=[0];events=[]
        def interrupt(grid,observer=None):
            if calls[0]==1:raise error_type('injected after one complete teacher')
            calls[0]+=1;return original(grid,observer)
        adapter.render=interrupt
        try:adapter.帯profile積層教材(teachers,観測=events.append)
        except error_type:
            last=events[-1];need(last['kind']=='evaluation_exception' and last['resource_failure'] and not last['semantic_HOLD'] and len(last['completed_teacher_returns'])==1 and last['active_call']['teacher_index']==1,'teacher resource prefix')
            rows.append({'mode':'fit','exception':error_type.__name__,'events':events})
        else:raise AssertionError('swallowed fit resource')
        finally:adapter.render=original
        events=[];raised=[False]
        def stop_chain(event):
            events.append(event)
            if event['kind']=='search_prefix' and event['field']=='chain_prefixes' and not raised[0]:
                raised[0]=True;raise error_type('injected after completed chain-prefix event')
        try:fitted.候補(teachers[0]['input'],{},stop_chain)
        except error_type:
            failure=next(e for e in events if e['kind']=='search_exception')
            need(failure['resource_failure'] and not failure['semantic_HOLD'] and bool(failure['completed_resource_prefix']),'internal resource capture')
            need(any(x.get('record',{}).get('chain_prefixes') for x in failure['completed_resource_prefix']),'chain prefix captured')
            rows.append({'mode':'internal_chain_prediction','exception':error_type.__name__,'events':events})
        else:raise AssertionError('swallowed prediction resource')
    save(out,'resource-prefix-rethrow.json.gz',rows)
    check('MemoryError RecursionError TimeoutError retain completed teacher and internal search prefixes and rethrow',len(rows)==6)

def conservation_controls(adapter,teachers,fitted,out):
    baseline=[{'input':[[0,1],[0,0]],'output':[[0,1],[0,0]]},
              {'input':[[0,2],[0,0]],'output':[[0,2],[0,0]]}]
    shaped=copy.deepcopy(baseline);shaped[0]['output']=[[0,1,0,0]]
    counted=copy.deepcopy(baseline);counted[1]['output']=[[0,2],[0,2]]
    both=copy.deepcopy(baseline);both[0]['output']=[[1]];both[1]['output']=[[2]]
    later=copy.deepcopy(teachers);later[1]['output']=[[0]]
    original=adapter.render;rows=[]
    def forbidden(*a,**k):raise AssertionError('whole-domain proof must execute no teacher renderer')
    adapter.render=forbidden
    try:
        for label,pairs,expected_indices in [('shape_only_same_histogram',shaped,[0]),('count_only_same_shape',counted,[1]),('all_mismatches',both,[0,1]),('later_failure_prevents_all_renders',later,[1])]:
            audit={};events=[];obj=adapter.帯profile積層教材(pairs,audit,events.append)
            proof=audit['conservation_proof'];skipped=audit['unexecuted_teacher_renders']
            need(obj.モデル群==() and proof['whole_program_impossible'] and proof['violating_teacher_indices']==expected_indices,'conservation proof '+label)
            need(audit['evaluated_programs']==audit['evaluated_teacher_returns']==0 and audit['teacher_returns']==[],'no fabricated execution')
            need(len(proof['all_teacher_witnesses'])==len(skipped)==len(pairs),'all teacher arithmetic and symbolic skips')
            for row in skipped:need(row['execution']=='unexecuted' and not row['renderer_executed'] and 'output' not in row and 'record' not in row,'unexecuted row cannot fabricate None')
            need(sum(e['kind']=='teacher_render_unexecuted' for e in events)==len(pairs) and not any(e['kind'] in ('program_return','teacher_return') for e in events),'symbolic event contract')
            for witness,pair in zip(proof['all_teacher_witnesses'],pairs):
                need([r['color'] for r in witness['all_color_counts']]==list(range(10)),'all ten colors')
                for row in witness['all_color_counts']:
                    color=row['color'];left=sum(v==color for r in pair['input'] for v in r);right=sum(v==color for r in pair['output'] for v in r)
                    need((row['input_count'],row['target_count'],row['target_minus_input'])==(left,right,right-left),'arithmetic witness')
            if label=='shape_only_same_histogram':need(proof['all_teacher_witnesses'][0]['color_counts_equal'],'shape-only proof')
            if label=='count_only_same_shape':need(proof['all_teacher_witnesses'][1]['shape_equal'],'count-only proof')
            rows.append({'name':label,'teachers':pairs,'audit':audit,'events':events})
    finally:adapter.render=original
    original_proof=adapter.conservation_proof;calls=[]
    def forbidden_proof(*a,**k):calls.append(True);raise AssertionError('proof before full strict validation')
    adapter.conservation_proof=forbidden_proof
    try:
        malformed=copy.deepcopy(shaped);malformed[1]['input']=[[True]];audit={}
        obj=adapter.帯profile積層教材(malformed,audit)
        need(obj.モデル群==() and audit['failure']=='invalid_teacher_pair' and calls==[],'all teachers validate before proof')
    finally:adapter.conservation_proof=original_proof
    events=[];audit={};observed=adapter.帯profile積層教材(teachers,audit,events.append);plain=adapter.帯profile積層教材(teachers)
    need(observed.モデル群==plain.モデル群==fitted.モデル群 and not audit['conservation_proof']['whole_program_impossible'],'necessary proof is not sufficiency')
    need(len(audit['teacher_returns'])==len(teachers) and all(r['exact'] for r in audit['teacher_returns']),'surviving teachers executed completely')
    for pair in teachers:
        raw=adapter.render(pair['input']);with_observer=adapter.render(pair['input'],events.append)
        need(equal(raw,with_observer),'observer on off equality')
    rows.append({'name':'valid_conservation_executes_unchanged_kernel','audit':audit,'models':observed.モデル群})
    save(out,'conservation-proof-controls.json.gz',rows)
    check('strict validation before every teacher invariant; full shape and ten-color arithmetic witnesses')
    check('whole-rule impossibility skips all renders explicitly without fabricated outputs; valid conservation keeps kernel search')
    check('observer on off complete teacher return equality')

def copy_boundary_controls(adapter,teachers,fitted,out):
    rows=[];original_copy=adapter.deepcopy
    for error_type in (MemoryError,RecursionError,TimeoutError):
        for mode in ('fit','prediction'):
            events=[];raised=[False];injected=error_type('injected completed-return copy failure')
            def fail_copy(value,memo=None):
                if isinstance(value,dict) and value.get('kind')=='program_return' and not raised[0]:raised[0]=True;raise injected
                return original_copy(value,memo)
            adapter.deepcopy=fail_copy
            try:
                if mode=='fit':adapter.帯profile積層教材(teachers,観測=events.append)
                else:fitted.候補(teachers[0]['input'],{},events.append)
            except error_type as caught:
                need(caught is injected,'original resource identity')
                failure=next(e for e in events if e['kind']=='search_exception');completed=failure['completed_program_return']
                expected=read('teacher-0-all-hypotheses.json.gz');expected.pop('teacher_equal_after_inference')
                need(completed['output']==teachers[0]['output'] and equal(completed['record'],expected),'raw completed return survives detached copy failure')
                need(failure['resource_failure'] and not failure['semantic_HOLD'] and not any(e['kind']=='program_return' for e in events),'failed normal event separately marked')
                need(events[-1]['kind']=='evaluation_exception' and events[-1]['exception']==error_type.__name__,'outer original exception reported')
                rows.append({'mode':mode,'exception':error_type.__name__,'events':events,'raw_return_in_exception':True})
            else:raise AssertionError('copy resource swallowed')
            finally:adapter.deepcopy=original_copy
        events=[];original_error=error_type('sink fails on completed return');report_failures=[]
        def failed_sink(event):
            if event['kind']=='program_return':raise original_error
            if event['kind'] in ('search_exception','evaluation_exception'):
                report_failures.append(event['kind']);raise RuntimeError('unavailable evidence sink')
            events.append(event)
        try:fitted.候補(teachers[0]['input'],{},failed_sink)
        except error_type as caught:
            need(caught is original_error and report_failures==['search_exception','evaluation_exception'],'preserve original when reporter fails')
            rows.append({'mode':'persistent_sink_failure','exception':error_type.__name__,'original_exception_preserved':True,'report_attempts':report_failures,'completed_return_persisted':False,'limitation':'If observer/storage stays unavailable, or hard kill/OOM prevents serialization, raw return persistence cannot be guaranteed.'})
        else:raise AssertionError('sink failure replaced resource')
    original_infer=adapter.core.infer;original_prefix=adapter.SearchTrace.exception_prefix
    initial_error=TimeoutError('original semantic interruption');events=[]
    def stop_infer(grid):raise initial_error
    def stop_prefix(self,error):raise MemoryError('cannot allocate search prefix')
    adapter.core.infer=stop_infer;adapter.SearchTrace.exception_prefix=stop_prefix
    try:adapter.render(teachers[0]['input'],events.append)
    except TimeoutError as caught:
        need(caught is initial_error,'prefix capture failure must preserve original exception')
        failure=events[-1]
        need(failure['kind']=='search_exception' and failure['exception']=='TimeoutError' and failure['resource_prefix_captured'] is False and failure['resource_prefix_failure']=='MemoryError' and failure['completed_resource_prefix'] is None,'missing prefix explicitly reported')
        rows.append({'mode':'prefix_construction_failure','original_exception':'TimeoutError','prefix_failure':'MemoryError','original_exception_preserved':True,'events':events})
    else:raise AssertionError('prefix failure masked original exception')
    finally:adapter.core.infer=original_infer;adapter.SearchTrace.exception_prefix=original_prefix
    save(out,'completed-copy-boundary-controls.json.gz',rows)
    check('three resource types fit and prediction copy failures include the exact completed raw return before rethrow')
    check('failed evidence sink preserves original resource exception; persistence limit explicitly retained')
    check('prefix construction failure is explicitly missing and cannot replace the original resource exception')

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
        for minimum in (2,3):
            machine=Recording(minimum);need(machine.台帳.全取得()=={},'fresh native');calls=[]
            def candidate(grid,policy):
                need(fitted.モデル群 is identity,'same model identity');output,detail=fitted.候補(grid,policy);calls.append({'input':grid,'output':output,'record':detail});return output,detail
            boundary='ARC帯profile積層';record=helpers['候補機構を学習'](machine,{'train':teachers},(),boundary,candidate)
            need(record['採用可'] and record['同値採用']==(minimum==2),'native support gate')
            need(record['現在観測数']==2 and record['事前観測数']==0 and record['隔離数']==0,'native counts')
            observations=machine.台帳.取得('観測台帳');need(len(observations)==len(calls)==2 and len({encoded(o.原入力) for o in observations})==2,'same two distinct teachers')
            references=tuple(o.経験識別子 for o in observations);last=machine.calls[-1]['result'];equality=[p for p in last.有効原理群 if helpers['同値原理あり']([p],boundary)]
            need(bool(equality)==(minimum==2) and all(p.根拠参照群==references and not p.反証参照群 for p in equality),'native evidence refs')
            for pair,observation,call in zip(teachers,observations,calls):need(observation.原入力=={'候補':pair['output'],'出力':pair['output']} and call['output']==pair['output'],'native whole grids')
            save(out,f'native-support-{minimum}.json.gz',{'support':minimum,'models':fitted.モデル群,'record':record,'candidate_calls':calls,'native_calls':machine.calls,'ledger':machine.台帳.JSON相当(),'raw_exhaust':machine.calls[-1]['exhaust'],'references':references,'equality':equality,'query_calls':0})
            results.append({'support':minimum,'equality':record['同値採用'],'current':2,'prior':0,'quarantine':0,'raw_exhaust':machine.calls[-1]['exhaust'].状態})
            need(fitted.モデル群 is identity and dataclasses.asdict(fitted)==before,'unchanged fitted object')
    finally:adapter.fit=original
    check('same fixed fit and same two teachers fresh native support2 equality true support3 false; raw exhaust separate')
    return results

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output-base');ap.add_argument('--repository-root');args=ap.parse_args()
    base=Path(args.output_base) if args.output_base else P.parent/'candidate024-results';base.mkdir(parents=True,exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix='arc2-candidate024-',dir=base));summary={'artifact_directory':str(out)}
    try:
        adapter,native,helpers=load(out,args.repository_root);teachers=read('teachers.json.gz')['train'];audit={};journal=Journal(out/'full-teacher-fit-events.jsonl.gz');before=encoded(teachers)
        try:fitted=adapter.帯profile積層教材(teachers,audit,journal)
        finally:journal.close()
        need(fitted.モデル群==adapter.PROGRAMS and audit['evaluated_teacher_returns']==2 and encoded(teachers)==before,'fit')
        for i,row in enumerate(audit['teacher_returns']):
            expected=read(f'teacher-{i}-all-hypotheses.json.gz');expected.pop('teacher_equal_after_inference')
            need(equal(row['record'],expected) and row['exact'],'original full teacher evidence')
        direct=[fitted.候補(p['input'],{}) for p in teachers];need(all(o==p['output'] for (o,r),p in zip(direct,teachers)),'both teacher returns')
        save(out,'full-teacher-fit-and-returns.json.gz',{'fit_record':audit,'models':fitted.モデル群,'returns':direct,'event_counts':journal.counts})
        check('fixed no-parameter rule activated; both full teacher role-chain-cover records replay exactly')
        controls(adapter,teachers,fitted,out);schema(adapter,teachers,fitted,out);resources(adapter,teachers,fitted,out)
        conservation_controls(adapter,teachers,fitted,out);copy_boundary_controls(adapter,teachers,fitted,out)
        summary['native']=native_cycles(adapter,native,helpers,fitted,teachers,out)
        summary.update(successful=True,tests_run=len(PASSED),passed_cases=PASSED)
    except BaseException as error:
        summary.update(successful=False,tests_run=len(PASSED),passed_cases=PASSED,error=type(error).__name__,message=str(error),traceback=traceback.format_exc())
    save(out,'summary.json',summary);print(json.dumps(summary,ensure_ascii=False,sort_keys=True));return 0 if summary['successful'] else 1
if __name__=='__main__':raise SystemExit(main())
