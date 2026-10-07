#!/usr/bin/env python3
"""候補010のcwd非依存・引数不要回帰。教材・自作対照のみ、実HDS照会禁止。"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import ast, copy, dataclasses, enum, gzip, hashlib, importlib, json, tempfile, traceback, types
from pathlib import Path
SCRIPT=Path(__file__).resolve(); P=SCRIPT.parents[1]; F=SCRIPT.parent/'標識軸転写資料'
PASSED=[]; MANIFEST=[]


def serial(v):
    if dataclasses.is_dataclass(v): return serial(dataclasses.asdict(v))
    if isinstance(v,enum.Enum): return serial(v.value)
    if isinstance(v,dict): return {str(k):serial(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)): return [serial(x) for x in v]
    if isinstance(v,(set,frozenset)): return [serial(x) for x in sorted(v)]
    if v is None or isinstance(v,(bool,int,float,str)): return v
    raise TypeError(type(v).__name__)


def encoded(v): return json.dumps(serial(v),ensure_ascii=False,sort_keys=True,separators=(',',':'))
def equal(a,b): return encoded(a)==encoded(b)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def check(name,condition):
    if not condition: raise AssertionError(name)
    PASSED.append(name)
def save(directory,name,value):
    path=directory/name; data=encoded(value).encode()
    path.write_bytes(gzip.compress(data,compresslevel=1,mtime=0) if name.endswith('.gz') else data)
    return path

def read_fixture(name): return json.loads(gzip.decompress((F/name).read_bytes()))
def rows(name):
    with gzip.open(F/name,'rt') as f:
        for line in f: yield json.loads(line)


class Journal:
    def __init__(self,path):
        self.path=path; self.file=path.open('x'); self.counts={}; self.sequence=0
    def __call__(self,event):
        # Each completed return is flushed independently, including before a later exception.
        self.file.write(json.dumps(dict(sequence=self.sequence,**event),ensure_ascii=False,separators=(',',':'))+'\n')
        self.file.flush(); self.sequence+=1; self.counts[event['kind']]=self.counts.get(event['kind'],0)+1
    def close(self): self.file.close()


def find_repo():
    snapshot=P.parent/'source-evidence/repository'
    if (snapshot/'HDS/学習系統/v0.4.2/hds学習系統').is_dir(): return snapshot
    if (P/'HDS/学習系統/v0.4.2/hds学習系統').is_dir(): return P
    raise RuntimeError('Frozen staging dependencies or deployed repository required')


def load_modules(repo):
    sys.path.insert(0,str(repo/'HDS/学習系統/v0.4.2'))
    pkg=types.ModuleType('_candidate010_regression'); pkg.__path__=[str(P/'接続/ARC2'),str(repo/'接続/ARC2')]; sys.modules[pkg.__name__]=pkg
    adapter=importlib.import_module(pkg.__name__+'.標識軸転写教材'); native=importlib.import_module('hds学習系統'); nt=importlib.import_module('hds学習系統.型')
    frozen=read_fixture('candidate-original-ast.json.gz')
    actual={n.name:ast.dump(n,include_attributes=False) for n in ast.parse((P/'接続/ARC2/標識軸転写候補.py').read_text()).body if isinstance(n,ast.FunctionDef)}
    check('all original core function ASTs unchanged',actual==frozen)
    helper_provenance=read_fixture('source-manifest.json.gz')['shared_pure_dependencies']
    for item in helper_provenance:
        filename=Path(item['repository_path']).name
        data=(repo/'接続/ARC2'/filename).read_bytes()
        if filename=='標識組立教材.py' and hashlib.sha256(data).hexdigest()=='98542bfb2ea5309573e5ab80d1a16fe789d293cfe45dd77ce50132718c7267a6':
            # Exact recovered 055 adapter: reverse only its class dispatch, retaining the original manifest.
            dispatch='''        result = guarded_render(格子, self.役割)
        if result[0] is not None or result[1].get('failure') != 'dominant_translation_axis_tie':
            return result
        # Extend this structural rejection only; fitting and all other results stay exact.
        from .標識組立完全所有 import guarded_render as complete_body_render
        return complete_body_render(格子, self.役割)
'''.encode()
            assert data.count(dispatch)==1
            data=data.replace(dispatch,'        return guarded_render(格子, self.役割)\n'.encode())
        check('frozen old helper source '+filename,hashlib.sha256(data).hexdigest()==item['sha256'])
    for module_name,func in [('既存辺対応抽出','SIDE_TRANSFORM_MAPS'),('既存格子操作','transform_grid_by_name'),('既存領域転写','mixed_region_dicts_for_grid'),('標識組立教材','valid_grid')]:
        module=importlib.import_module(pkg.__name__+'.'+module_name)
        check('direct old helper identity '+func,getattr(adapter.core,func) is getattr(module,func))
    # The preserved synthetic suite contains one package-qualified old-module import.
    alias=types.ModuleType('接続');alias.__path__=[str(repo/'接続')];sys.modules['接続']=alias
    sys.modules['接続.ARC2']=pkg
    for module_name in ('既存領域転写',):
        module=importlib.import_module(pkg.__name__+'.'+module_name);sys.modules['接続.ARC2.'+module_name]=module
    bridge=repo/'接続/ARC2/HDS接続.py'; frozen=read_fixture('native-helpers-ast.json.gz'); data=bridge.read_bytes()
    # Snapshot requires exact accepted whole bridge; deployed use requires matching public ASTs.
    if repo!=P: check('accepted d2bbed bridge full SHA',hashlib.sha256(data).hexdigest()==frozen['bridge_sha256'])
    nodes={n.name:n for n in ast.parse(data).body if isinstance(n,ast.FunctionDef) and n.name in frozen['ast']}
    check('three native public helper ASTs unchanged',{k:ast.dump(v,include_attributes=False) for k,v in nodes.items()}==frozen['ast'])
    scope={'deepcopy':copy.deepcopy,'学習入力':nt.学習入力,'観測事実':nt.観測事実}
    exec(compile(ast.fix_missing_locations(ast.Module(body=list(nodes.values()),type_ignores=[])),str(bridge),'exec'),scope)
    for name,module in sorted(sys.modules.items()):
        filename=getattr(module,'__file__',None)
        if filename and (name.startswith(pkg.__name__+'.') or name.startswith('hds学習系統')):
            MANIFEST.append({'module':name,'path':str(Path(filename).resolve()),'sha256':sha(filename)})
    MANIFEST.append({'module':'three AST public helpers only','path':str(bridge),'sha256':sha(bridge)})
    return adapter,native,scope


def native_cycles(adapter,native,helpers,fitted,teachers,directory,observer=None,supports=(2,3)):
    identity=fitted.モデル群; before=dataclasses.asdict(fitted); cycles=[]
    class Recording(native.HDS学習実行系):
        def __init__(self,minimum): super().__init__(最小支持数=minimum); self.calls=[]
        def 実行(self,value):
            result=super().実行(value); exhaust=native.最小排気系().排出する(result)
            self.calls.append({'input':value,'result':result,'exhaust':exhaust}); return result
        def 照会(self,*args,**kwargs): raise AssertionError('HDS query is prohibited')
    original=adapter.fit
    def no_refit(*args,**kwargs): raise AssertionError('Native must reuse identical fitted models')
    adapter.fit=no_refit
    try:
        for minimum in supports:
            machine=Recording(minimum); assert machine.台帳.全取得()=={}
            candidate_calls=[]
            def candidate(grid,policy):
                assert fitted.モデル群 is identity
                out,detail=fitted.候補(grid,policy,観測=observer)
                candidate_calls.append({'input':copy.deepcopy(grid),'candidate':out,'detail':detail}); return out,detail
            boundary='ARC標識軸転写'
            result=helpers['候補機構を学習'](machine,{'train':teachers},(),boundary,candidate)
            observations=machine.台帳.取得('観測台帳'); last=machine.calls[-1]['result']; exhaust=machine.calls[-1]['exhaust']
            equality=[p for p in last.有効原理群 if helpers['同値原理あり']([p],boundary)]
            assert result['採用可'] and result['同値採用']==(len(teachers)>=minimum)
            assert result['現在観測数']==len(teachers) and result['事前観測数']==0 and result['隔離数']==0
            assert len(candidate_calls)==len(observations)==len(teachers) and not last.係争中原理群
            references=tuple(o.経験識別子 for o in observations)
            assert all(p.根拠参照群==references and not p.反証参照群 for p in equality)
            for pair,obs,called in zip(teachers,observations,candidate_calls):
                assert obs.原入力=={'候補':pair['output'],'出力':pair['output']} and called['candidate']==pair['output']
            evidence={'minimum_support':minimum,'same_fitted_model_group':fitted.展開モデル(),'candidate_calls':candidate_calls,
                      'native_helper_record':result,'native_calls':machine.calls,'ledger':machine.台帳.JSON相当(),
                      'equality_principles':equality,'raw_exhaust':exhaust,'quarantined':last.係争中原理群,
                      'actual_observation_references':references,'query_calls':0}
            save(directory,'native-support-'+str(minimum)+'.json.gz',evidence)
            cycles.append({'minimum_support':minimum,'equality':result['同値採用'],'current_observations':len(observations),
                           'prior_observations':result['事前観測数'],'quarantine':result['隔離数'],
                           'raw_exhaust_status':exhaust.状態,'raw_exhaust_prediction_count':len(exhaust.内容['予測群'])})
            assert fitted.モデル群 is identity and dataclasses.asdict(fitted)==before
    finally: adapter.fit=original
    return cycles


def validation_controls(adapter,teachers,directory):
    cases=[('none',None,'invalid_teacher_container'),('mapping',{},'invalid_teacher_container'),
           ('empty',[],'too_few_distinct_teachers'),('one',teachers[:1],'too_few_distinct_teachers'),
           ('duplicate',[teachers[0],teachers[0]],'duplicate_teacher_inputs')]
    extra=copy.deepcopy(teachers[:2]);extra[0]['extra']=1;cases.append(('extra',extra,'invalid_teacher_pair'))
    missing=copy.deepcopy(teachers[:2]);del missing[0]['output'];cases.append(('missing',missing,'invalid_teacher_pair'))
    cases.append(('wrong_pair',[None,teachers[1]],'invalid_teacher_pair'))
    grids={'bool':[[True]],'float':[[1.0]],'string':[['1']],'negative':[[-1]],'ten':[[10]],'empty':[],'row':[[]],
           'ragged':[[0],[0,1]],'tuple':((0,),),'tuple_row':[(0,)],'height':[[0]]*31,'width':[[0]*31]}
    for field in ('input','output'):
        for name,grid in grids.items():
            bad=copy.deepcopy(teachers[:2]);bad[0][field]=grid;cases.append((field+'_'+name,bad,'invalid_teacher_pair'))
    controls=[]; original=adapter.core.render
    def prohibited(*a,**kw): raise AssertionError('Invalid teachers evaluated')
    adapter.core.render=prohibited
    try:
        for name,value,reason in cases:
            events=[];before=copy.deepcopy(value);models,record=adapter.fit(value,observer=events.append)
            check('schema '+name,models==() and record['failure']==reason and value==before and len(events)==1)
            controls.append({'name':name,'input':value,'record':record,'events':events})
    finally: adapter.core.render=original
    check('minimum two distinct teachers',adapter.validate_teachers(teachers[:2])[0])
    check('tuple teacher container',adapter.validate_teachers(tuple(teachers))[0])
    save(directory,'teacher-validation.json.gz',controls)


def resource_controls(adapter,teachers,fitted,directory):
    original=adapter.core.render; results=[]
    for exception in (MemoryError,RecursionError,TimeoutError):
        for mode,completed in (('fit_after_teacher',1),('fit_after_model',len(teachers)),('predict_after_model',1)):
            journal=Journal(directory/(exception.__name__+'-'+mode+'.jsonl')); count=[0]
            def injected(*args,**kwargs):
                if count[0]==completed: raise exception('simulated '+mode)
                count[0]+=1; return original(*args,**kwargs)
            adapter.core.render=injected
            try:
                if mode.startswith('fit'): adapter.fit(teachers,observer=journal)
                else: fitted.候補(teachers[0]['input'],{},観測=journal)
                raise AssertionError('resource exception swallowed')
            except exception:
                kind='model_teacher_return' if mode.startswith('fit') else 'retained_model_return'
                check(exception.__name__+' '+mode+' prefix propagated',journal.counts.get(kind)==completed and journal.counts.get('evaluation_exception')==1)
                results.append({'exception':exception.__name__,'mode':mode,'completed_prefix':completed,'simulated':True,'semantic_HOLD':False})
            finally: adapter.core.render=original;journal.close()
    return results


def original_synthetic_suite(adapter,directory):
    import contextlib
    outdir=directory/'synthetic';outdir.mkdir()
    (outdir/'fit-exhaustive-evidence.json').write_bytes(gzip.decompress((F/'fit-exhaustive-evidence.json.gz').read_bytes()))
    source=gzip.decompress((F/'validate_prototype.py.gz').read_bytes()).decode()
    start=source.index('C = Path(__file__).resolve().parent');end=source.index('IMMUTABLE =',start)
    amended=source[:start]+source[end:]
    old_functions={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)}
    new_functions={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(amended).body if isinstance(n,ast.FunctionDef)}
    check('all159 synthetic suite function ASTs unchanged',old_functions==new_functions)
    namespace={'__name__':'candidate010_original_control_suite','__file__':str(F/'validate_prototype.py.gz'),
               'C':outdir,'OLD':F/'original','core':adapter.core}
    exec(compile(amended,str(F/'validate_prototype.py.gz'),'exec'),namespace)
    with (outdir/'stdout.json').open('w') as stream,contextlib.redirect_stdout(stream):
        summary=namespace['run']()
    check('all159 original synthetic controls rerun',summary['checks']==summary['passed']==159 and not summary['failures'])
    previous=iter(rows('synthetic-full-returns.jsonl.gz'));count=0
    for line in (outdir/'synthetic-full-returns.jsonl').open():
        actual=json.loads(line);expected=next(previous)
        check('full original synthetic return parity '+actual['name'],equal(actual,expected));count+=1
    check('all159 original full control records retained',count==159 and next(previous,None) is None)
    check('all16 D4 full output and trace parity',equal(json.loads((outdir/'whole-D4-covariance.json').read_text()),read_fixture('whole-D4-covariance.json.gz')))
    return summary


def wrapper_partial_controls(adapter,teachers,fitted,directory):
    outcomes=[]; original=adapter.core.band_view
    for exception in (MemoryError,RecursionError,TimeoutError):
        for mode in ('fit','predict'):
            count=[0];events=[];journal=Journal(directory/(exception.__name__+'-inner-'+mode+'.jsonl'))
            def observer(event):
                journal(event);events.append(event)
            def interrupted(*args,**kwargs):
                count[0]+=1
                if count[0]==3:
                    kwargs['record'].update(active_stage={'axis':'row','scan_complete':False,'scanned_line_indices':[0]},partial_marker='injected-inner-stage')
                    raise exception('simulated interrupted inner band stage')
                return original(*args,**kwargs)
            adapter.core.band_view=interrupted
            try:
                if mode=='fit':adapter.fit(teachers,observer=observer)
                else:fitted.候補(teachers[0]['input'],{},観測=observer)
                raise AssertionError('inner resource failure swallowed')
            except exception:
                partial=events[-1]['partial_inner_stage'];kind='model_teacher_return' if mode=='fit' else 'retained_model_return'
                check(exception.__name__+' '+mode+' complete prefix and inner stage',
                      journal.counts.get(kind)==1 and events[-1]['completed_returns']==1 and
                      events[-1]['semantic_HOLD'] is False and partial['views'][0]['stage']=='band_view' and
                      partial['views'][0]['partition']['partial_marker']=='injected-inner-stage')
                outcomes.append({'exception':exception.__name__,'mode':mode,'completed':1,'partial_inner_stage_saved':True})
            finally:adapter.core.band_view=original;journal.close()
    return outcomes


def consensus_controls(adapter,teachers,fitted,directory):
    original=adapter.core.render;records=[]
    base=teachers[0]['output'];conflict=copy.deepcopy(base);conflict[0][0]=(conflict[0][0]+1)%10
    for name,outputs,reason in [('retained_failure',[base,None],'retained_program_failed'),
                                ('retained_conflict',[base,conflict],'retained_program_outputs_disagree')]:
        calls=[0];events=[]
        def replacement(*args,**kwargs):
            i=calls[0];calls[0]+=1;return copy.deepcopy(outputs[i]),{'injected_control':name,'index':i}
        adapter.core.render=replacement
        try:out,detail=fitted.候補(teachers[0]['input'],{},観測=events.append)
        finally:adapter.core.render=original
        check(name+' whole HOLD and all retained returns',out is None and detail['failure']==reason and calls[0]==2 and len(detail['program_returns'])==2)
        records.append({'name':name,'input':teachers[0]['input'],'candidate':out,'detail':detail,'events':events})
    events=[]
    def mutate(event):
        events.append(copy.deepcopy(event))
        if event['kind']=='retained_model_return':
            event['record']['program']['body_color']=-1
            event['record']['output'][0][0]=-1
            event['record']['detail'].clear()
    out,detail=fitted.候補(teachers[0]['input'],{},観測=mutate)
    check('immediate observer deepcopy isolates full retained returns',out==base and all(r['program']['body_color']==8 and r['detail'] for r in detail['program_returns']))
    records.append({'name':'observer_mutation_isolated','candidate':out,'detail':detail,'events_before_mutation':events})
    save(directory,'wrapper-consensus-controls.json.gz',records)


def main(directory):
    repo=find_repo();adapter,native,helpers=load_modules(repo)
    source_hashes={str(p):sha(p) for p in list((P/'接続/ARC2').glob('*.py'))+list(F.rglob('*'))+[SCRIPT] if p.is_file()}
    source_hashes.update({r['path']:r['sha256'] for r in MANIFEST});save(directory,'source-before.json',source_hashes)
    teachers=json.loads((F/'original/teachers.json').read_text())['train'];before=copy.deepcopy(teachers)
    validation_controls(adapter,teachers,directory)
    journal=Journal(directory/'full-teacher-events.jsonl');expected=iter(rows('fit-720-full-returns.jsonl.gz'));compared=[0]
    def observer(event):
        journal(event)
        if event['kind']=='model_teacher_return':
            old=next(expected);current=dict(program_index=event['model_index'],program=event['program'],**event['result'])
            assert equal(current,old);compared[0]+=1
    audit={}
    try:fitted=adapter.標識軸転写教材(teachers,監査=audit,観測=observer)
    finally:journal.close()
    check('all720 original full teacher returns exactly preserved',compared[0]==720 and next(expected,None) is None)
    check('both original C4 C8 chirality+1 programs retained',len(fitted.モデル群)==2 and equal([m['program'] for m in fitted.展開モデル()],read_fixture('models.json.gz')))
    check('fitted state immutable program tuples and scalar metadata',[f.name for f in dataclasses.fields(fitted)]==['モデル群','教師数','教師fit最小数','適合数','不足理由'] and not hasattr(fitted,'__dict__'))
    check('all models immutable integer tuples',type(fitted.モデル群) is tuple and all(type(m) is tuple and all(type(x) is int for x in m) for m in fitted.モデル群))
    try:fitted.教師数=0;raise AssertionError('mutable adapter')
    except dataclasses.FrozenInstanceError:PASSED.append('frozen adapter assignment rejected')
    check('count summary contains no grids',set(audit)=={'teacher_fit_minimum','teacher_count','program_count','complete_program_teacher_evaluations','outcomes','retained_count','failure'})
    save(directory,'teacher-fit-summary.json',audit);save(directory,'fitted-model-state.json',fitted)
    synthetic=original_synthetic_suite(adapter,directory)
    for index,pair in enumerate(teachers):
        events=[];out,detail=fitted.候補(pair['input'],{},観測=events.append)
        check('teacher consensus '+str(index),out==pair['output'] and equal((out,detail),adapter.core.consensus(pair['input'],read_fixture('models.json.gz'))))
        save(directory,'teacher-consensus-'+str(index)+'.json.gz',{'candidate':out,'detail':detail,'events':events})
    cycles=native_cycles(adapter,native,helpers,fitted,teachers,directory)
    check('actual same-group native support2 equality support3 no equality',[r['equality'] for r in cycles]==[True,False])
    resources=resource_controls(adapter,teachers,fitted,directory)
    partial=wrapper_partial_controls(adapter,teachers,fitted,directory)
    consensus_controls(adapter,teachers,fitted,directory)
    check('teacher grids unchanged and absent from fitted state',teachers==before and len(fitted.モデル群)==2)
    check('all frozen sources and fixtures unchanged',all(sha(p)==v for p,v in source_hashes.items()))
    save(directory,'import-source-manifest.json',MANIFEST)
    return {'successful':True,'tests_run':len(PASSED),'passed_cases':PASSED,'artifact_directory':str(directory),
            'teacher_returns':720,'retained_models':2,'synthetic_controls':synthetic['checks'],'full_D4_covariance':16,
            'native_cycles':cycles,'resource_controls':resources,'partial_inner_controls':partial,'query_calls':0}


if __name__=='__main__':
    staging=P.parent if (P.parent/'source-evidence/repository').is_dir() else None
    base=staging/'run-artifacts' if staging else None
    if base is not None:base.mkdir(exist_ok=True)
    directory=Path(tempfile.mkdtemp(prefix='candidate010-regression-',dir=base))
    try:result=main(directory)
    except BaseException as exc:
        result={'successful':False,'tests_run':len(PASSED),'passed_cases':PASSED,'artifact_directory':str(directory),
                'exception':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc()}
    save(directory,'summary.json',result);print(json.dumps(result,ensure_ascii=False))
    raise SystemExit(0 if result['successful'] else 1)
