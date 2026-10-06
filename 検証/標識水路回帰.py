#!/usr/bin/env python3
"""Fresh044 independent literal controls; no official teachers or queries loaded."""
import sys
sys.dont_write_bytecode=True
import argparse,ast,copy,dataclasses,enum,gzip,hashlib,importlib,json,pathlib,resource,signal,types,dis,inspect,tempfile,importlib.util
P=pathlib.Path(__file__).resolve().parents[1]
F=P/'検証/標識水路資料'
def readpins():return json.loads(gzip.decompress((F/'dependency-pins.json.gz').read_bytes()))
spec=importlib.util.spec_from_file_location('_marker_channel_evidence_support',F/'evidence_support.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
PIN_CHECKS=[]
def is_runtime_source(filename,repo):
 p=pathlib.Path(filename).resolve()
 return p.is_relative_to(repo/'接続/ARC2') or p.is_relative_to(P/'接続/ARC2') or p.is_relative_to(repo/'HDS/学習系統/v0.4.2/hds学習系統')
CHECKS=[]
def check(name,value=True):
 if not value:raise AssertionError(name)
 CHECKS.append(name)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def encoded(v):return h.encoded(h.serial(v)).decode()
def save(out,name,v):h.write(out/name,h.serial(v))
def verify(repo):
 pins=readpins()
 def pin(name,condition):
  if not condition:raise AssertionError(name)
  PIN_CHECKS.append(name)
 for path,digest in pins['payload_pins'].items():pin('payload:'+path,sha(P/path)==digest)
 for path,digest in pins['base_source_pins'].items():pin('base:'+path,sha(repo/path)==digest)
 bridge=repo/'接続/ARC2/HDS接続.py'
 native={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(bridge.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name in pins['native_bridge_ast']}
 pin('three-native-helper-ASTs',native==pins['native_bridge_ast'])
 return pins
def load(root):
 repo=pathlib.Path(root).resolve();sys.path.insert(0,str(repo))
 pkg=types.ModuleType('_fresh044');pkg.__path__=[str(P/'接続/ARC2')];sys.modules[pkg.__name__]=pkg
 a=importlib.import_module(pkg.__name__+'.標識水路教材')
 actual={str(pathlib.Path(m.__file__).relative_to(repo)) for n,m in sys.modules.items() if n.startswith('接続.ARC2.') and getattr(m,'__file__',None)}
 check('complete-nine-file-import-closure',actual=={'接続/ARC2/'+n+'.py' for n in readpins()['import_closure']})
 return a,repo

def closure(a,repo,out):
 seen=set();rows=[];pending=[]
 for module in list(sys.modules.values()):
  if not getattr(module,'__file__',None) or not is_runtime_source(module.__file__,repo):continue
  for value in list(vars(module).values()):
   if inspect.isfunction(value) and is_runtime_source(value.__code__.co_filename,repo):pending.append(value)
   elif inspect.isclass(value):
    for method in vars(value).values():
     if inspect.isfunction(method) and is_runtime_source(method.__code__.co_filename,repo):pending.append(method)
 def names(code):
  got=set(code.co_names)
  for c in code.co_consts:
   if isinstance(c,types.CodeType):got.update(names(c))
  return got
 while pending:
  f=pending.pop()
  if id(f) in seen:continue
  seen.add(id(f));source=pathlib.Path(f.__code__.co_filename).resolve(); globals_={}
  for key in sorted(names(f.__code__)):
   if key not in f.__globals__:continue
   value=f.__globals__[key]
   if inspect.isfunction(value) and is_runtime_source(value.__code__.co_filename,repo):pending.append(value)
   if isinstance(value,types.ModuleType):summary={'module':value.__name__,'file':getattr(value,'__file__',None)}
   elif isinstance(value,type) or callable(value):summary={'callable':getattr(value,'__qualname__',str(type(value))),'module':getattr(value,'__module__',None)}
   else:
    try:summary=h.serial(value)
    except BaseException:summary={'opaque_type':type(value).__name__}
   globals_[key]=summary
  rows.append({'function':f.__qualname__,'source':str(source),'source_sha256':sha(source),'line':f.__code__.co_firstlineno,'globals':globals_})
 check('closure-includes-clone-grid',any(x['function']=='clone_grid' for x in rows))
 check('closure-includes-component-global-closure',any(x['function']=='body_components' for x in rows))
 save(out,'callable-global-closure.json',{'functions':rows,'stdlib_python':sys.version,'imported_runtime_modules':[{ 'name':n,'file':m.__file__,'sha256':sha(pathlib.Path(m.__file__))} for n,m in sorted(sys.modules.items()) if getattr(m,'__file__',None) and is_runtime_source(m.__file__,repo)]})

def geometry(a,packet,out):
 f=packet['law_fixture'];g=f['input'];rows=[]
 for law,expected in f['expected_by_law'].items():
  output,record=a.render(g,(law,));check('literal-law-endpoint:'+law,output==expected and record['status']=='complete' and record['traces'][0]['destination']==tuple(f['expected_endpoints'][law]));rows.append({'law':law,'input':g,'expected':expected,'output':output,'record':record})
 # Literal D4 map covariance preserves complete grids, marker roles and all three laws.
 def rotate(x):return [list(row) for row in zip(*x[::-1])]
 for rotation in range(4):
  for reflect in (False,True):
   def transform(x):
    x=copy.deepcopy(x)
    for _ in range(rotation):x=rotate(x)
    return [row[::-1] for row in x] if reflect else x
   for law,expected in f['expected_by_law'].items():
    grid=transform(g);expected=transform(expected);output,record=a.render(grid,(law,));check('D4:'+str((rotation,reflect,law)),output==expected);rows.append({'transform':[rotation,reflect],'law':law,'input':grid,'expected':expected,'output':output,'record':record})
 noop=[[9,0,0,0,0] for _ in range(5)]
 for model in a.PROGRAMS:
  output,record=a.render(noop,model);check('no-op-complete:'+model[0],output==noop and record['status']=='complete' and not record['traces'] and record['changed_cells']==[]);rows.append({'input':noop,'model':model,'output':output,'record':record})
 ambiguous=[[9,0,0,0,0,0,8] for _ in range(5)];scene,record=a.core.parse(ambiguous);check('raw-role-ambiguity',scene is None and record['raw_role_count']==2 and record['failure']=='raw_role_not_unique');rows.append({'input':ambiguous,'scene':scene,'record':record})
 output,record=a.predict(g,a.PROGRAMS);check('whole-output-consensus-disagreement',output is None and record['failure']=='retained_models_disagree' and len(record['returns'])==3);rows.append({'input':g,'models':a.PROGRAMS,'output':output,'record':record})
 save(out,'literal-geometry.json.gz',rows)

def strict(a,teachers,out):
 class LS(list):pass
 class TS(tuple):pass
 class SS(str):pass
 class IE(enum.IntEnum):ZERO=0
 bad=[(),[[True]],[[IE.ZERO]],[[0.0]],LS([[0]]),[LS([0])],[[0],[0,1]],[[]],[[10]],[[0]*31],[[0]]*31]
 for i,g in enumerate(bad):check('strict-grid:'+str(i),not a.valid_grid(g))
 for i,m in enumerate([['initial_color'],('bogus',),(SS('initial_color'),),TS(('initial_color',)),(),('initial_color','any_color'),(True,)]):check('strict-model:'+str(i),not a.valid_model(m))
 check('literal-three-law-domain',a.PROGRAMS==( ('initial_color',),('refreshed_color',),('any_color',)))
 for i,state in enumerate([[],list(a.PROGRAMS),(a.PROGRAMS[0],a.PROGRAMS[0]),tuple(reversed(a.PROGRAMS)),( ['initial_color'],),TS(a.PROGRAMS)]):
  output,record=a.predict(teachers[0]['input'],state);check('strict-state:'+str(i),output is None and record['failure']=='invalid_retained_state')
 check('ordered-subset',a.valid_models(()) and a.valid_models((a.PROGRAMS[0],a.PROGRAMS[2])))
 invalid=[([], 'too_few_distinct_teacher_inputs'),([teachers[0]],'too_few_distinct_teacher_inputs'),([teachers[0],teachers[0]],'duplicate_or_conflicting_teacher_input'),([dict(teachers[0],extra=1),teachers[1]],'invalid_teacher_pair'),([{},teachers[1]],'invalid_teacher_pair'),(LS(teachers),'invalid_teacher_container')]
 rows=[]
 for pairs,reason in invalid:
  models,record=a.fit(pairs);check('strict-teacher:'+reason,not models and record['failure']==reason);rows.append(record)
 # Complete conservation witnesses, including nonviolating and late violating teachers.
 conservation=[copy.deepcopy(teachers[0]),{'input':[[0,0],[0,0]],'output':[[0,0],[0,1]]},{'input':[[0,0,0,0]],'output':[[0,0],[0,0]]}]
 events=[];models,record=a.fit(conservation,events.append)
 check('necessary-shape-and-full-color-counts',not models and record['conservation_certificate']['violating_teacher_indices']==[1,2] and len(record['conservation_certificate']['witnesses'])==3 and record['evaluated_teacher_calls']==0 and record['symbolic_unexecuted_teacher_calls']==9 and len(record['symbolic_teacher_calls'])==9 and not any(e['kind']=='model_teacher_start' for e in events))
 check('necessary-only-not-sufficiency',record['conservation_certificate']['necessary_only'] is True)
 save(out,'conservation-certificate.json.gz',{'teachers':conservation,'record':record,'events':events});save(out,'strict-invalid-teachers.json.gz',rows)

def fit_state(a,teachers,out):
 events=[];audit={};before=copy.deepcopy(teachers);fitted=a.標識水路教材(teachers,audit,events.append)
 check('literal-refreshed-only-fit',fitted.モデル群==( ('refreshed_color',),))
 check('all-teachers-all-models',audit['evaluated_teacher_calls']==3*len(teachers) and len(audit['model_returns'])==3 and all(len(row['returns'])==len(teachers) for row in audit['model_returns']) and audit['symbolic_unexecuted_teacher_calls']==0)
 check('teachers-unmodified',teachers==before)
 identity=fitted.モデル群;state=dataclasses.asdict(fitted);predictions=[]
 for i,pair in enumerate(teachers):
  output,record=fitted.候補(pair['input'],{});check('teacher-reproduction:'+str(i),output==pair['output']);predictions.append({'output':copy.deepcopy(output),'record':copy.deepcopy(record)});output[0][0]=1
 check('fresh-prediction-copy',fitted.候補(teachers[0]['input'],{})[0]==teachers[0]['output'])
 old=teachers[0]['output'];teachers[0]['output']=[[1]];check('target-detached-state',fitted.候補(teachers[0]['input'],{})[0]==old);teachers[0]['output']=old
 for field,value in [('モデル群',()),('教師数',0),('不足理由','changed')]:
  caught=None
  try:setattr(fitted,field,value)
  except BaseException as e:caught=e
  check('frozen-state:'+field,isinstance(caught,(dataclasses.FrozenInstanceError,AttributeError,TypeError)))
 check('state-unmodified',identity is fitted.モデル群 and dataclasses.asdict(fitted)==state)
 save(out,'complete-fit.json.gz',{'models':identity,'audit':audit,'events':events,'predictions':predictions,'state':state})
 return fitted

def exceptions(a,teachers,fitted,out):
 rows=[]
 def run(name,target,attribute,call,when,predicate,error_class=MemoryError,report_fail=False):
  original=getattr(target,attribute);report=a.report_exception;primary=error_class(name);n=0;caught=None
  def replacement(*args,**kwargs):
   nonlocal n
   n+=1
   if n==when:raise primary
   return original(*args,**kwargs)
  def broken_report(*args,**kwargs):raise RecursionError('whole reporter secondary failure')
  setattr(target,attribute,replacement)
  if report_fail:a.report_exception=broken_report
  try:call()
  except BaseException as e:caught=e
  finally:setattr(target,attribute,original);a.report_exception=report
  check('original-primary:'+name,caught is primary)
  raw=h.capture_raw_exception(caught);save(out,'raw-'+name+'.json.gz',raw)
  check('raw-prefix:'+name,predicate(raw))
  check('not-semantic-HOLD:'+name,raw['semantic_HOLD'] is False and raw['resource_failure']==issubclass(error_class,(MemoryError,RecursionError,TimeoutError)))
  rows.append({'name':name,'primary':h.safe_exception(caught),'report_failed':report_fail,'raw_file':'raw-'+name+'.json.gz','diagnostic':getattr(caught,'evaluation_diagnostic',None)})
 def frame(raw,name):return [x['locals'] for x in raw['frames'] if x['function']==name]
 run('teacher-pending-after-completed',a,'teacher_row',lambda:a.fit(teachers,None),2,lambda r:any(len(x['calls'])==1 and x['raw_pending'] and x['detail'] is not None for x in frame(r,'fit')),report_fail=True)
 run('model-prefix-plus-pending',a,'teacher_row',lambda:a.fit(teachers,None),3,lambda r:any(len(x['records'])==1 and x['raw_pending'] and x['detail'] is not None for x in frame(r,'fit')),report_fail=True)
 run('render-pending-before-metadata',a,'render_row',lambda:a.render(teachers[0]['input'],a.PROGRAMS[1],None),1,lambda r:any(x['raw_pending'] and x['output'] is not None and x['detail']['status']=='complete' for x in frame(r,'render')),report_fail=True)
 run('completed-witness-and-active-count',a,'color_counts',lambda:a.fit(teachers,None),3,lambda r:any(len(x['witnesses'])==1 and x['certificate_active']['teacher_index']==1 for x in frame(r,'fit')),report_fail=True)
 run('ordinary-error-not-HOLD',a.core,'parse',lambda:a.fit(teachers,None),1,lambda r:bool(frame(r,'fit')),error_class=RuntimeError)
 run('recursion-error-prefix',a.core,'parse',lambda:a.fit(teachers,None),1,lambda r:bool(frame(r,'fit')),error_class=RecursionError)
 class UnprintableMemoryError(MemoryError):
  def __str__(self):raise ValueError('formatting also fails')
 run('unprintable-original-error',a.core,'parse',lambda:a.render(teachers[0]['input'],a.PROGRAMS[1]),1,lambda r:r['primary_exception']['message']=='<exception message unavailable>',error_class=UnprintableMemoryError,report_fail=True)
 caught=None
 try:a.render(teachers[0]['input'],a.PROGRAMS[1],state_limit=2)
 except BaseException as e:caught=e
 raw=h.capture_raw_exception(caught);check('explicit-timeout-completed-two-states',isinstance(caught,TimeoutError) and any(x['locals'].get('record',{}).get('states_completed')==2 for x in raw['frames']));save(out,'raw-timeout.json.gz',raw)
 for kind in ('conservation_teacher_witness','symbolic_teacher_call','model_teacher_return','model_completed','retained_model_return'):
  primary=TimeoutError('observer-'+kind);caught=None;events=[]
  def observe(event):
   events.append(event)
   if event['kind']==kind:raise primary
  pairs=teachers if kind!='symbolic_teacher_call' else [teachers[0],{'input':[[0]],'output':[[1]]}]
  original_report=a.report_exception
  def broken_report(*args,**kwargs):raise RecursionError('secondary reporter failure')
  a.report_exception=broken_report
  try:
   if kind=='retained_model_return':a.predict(teachers[0]['input'],a.PROGRAMS,observe)
   else:a.fit(pairs,observe)
  except BaseException as e:caught=e
  finally:a.report_exception=original_report
  raw=h.capture_raw_exception(caught);check('observer-original:'+kind,caught is primary)
  locs=frame(raw,'predict' if kind=='retained_model_return' else 'fit');field={'conservation_teacher_witness':'witnesses','symbolic_teacher_call':'symbolic','model_teacher_return':'calls','model_completed':'records','retained_model_return':'rows'}[kind]
  check('observer-completed-prefix:'+kind,any(len(x[field])==1 for x in locs));save(out,'raw-observer-'+kind+'.json.gz',{'raw':raw,'events':events})
 save(out,'exception-controls.json.gz',rows)

def native(a,repo,fitted,teachers,out):
 pins=readpins()
 bridge=repo/'接続/ARC2/HDS接続.py';nodes=[n for n in ast.parse(bridge.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name in pins['native_bridge_ast']]
 check('native-three-function-ASTs',{n.name:ast.dump(n,include_attributes=False) for n in nodes}==pins['native_bridge_ast'])
 sys.path.insert(0,str(repo/'HDS/学習系統/v0.4.2'));n=importlib.import_module('hds学習系統');nt=importlib.import_module('hds学習系統.型')
 helpers={'deepcopy':copy.deepcopy,'学習入力':nt.学習入力,'観測事実':nt.観測事実};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(bridge),'exec'),helpers)
 class Recording(n.HDS学習実行系):
  def __init__(self,minimum):super().__init__(最小支持数=minimum);self.calls=[]
  def 実行(self,value):
   result=super().実行(value);exhaust=n.最小排気系().排出する(result);self.calls.append({'input':value,'result':result,'raw_exhaust':exhaust});return result
  def 照会(self,*args,**kwargs):raise AssertionError('native query prohibited')
 identity=fitted.モデル群;state=dataclasses.asdict(fitted);rows=[];original=a.fit
 def forbidden(*args,**kwargs):raise AssertionError('native re-fit prohibited')
 a.fit=forbidden
 try:
  for count in (len(teachers),len(teachers)+1):
   machine=Recording(count);calls=[];check('native-empty-ledger:'+str(count),machine.台帳.全取得()=={})
   def candidate(grid,policy):
    check('same-fitted-identity',fitted.モデル群 is identity);output,detail=fitted.候補(grid,policy);calls.append({'input':grid,'output':output,'detail':detail});return output,detail
   boundary='ARC標識水路';record=helpers['候補機構を学習'](machine,{'train':teachers},(),boundary,candidate)
   obs=machine.台帳.取得('観測台帳');refs=tuple(o.経験識別子 for o in obs);equalities=[p for p in machine.calls[-1]['result'].有効原理群 if helpers['同値原理あり']([p],boundary)]
   check('native-support-boundary:'+str(count),record['採用可'] and record['同値採用']==(count<=len(teachers)) and record['現在観測数']==len(teachers) and record['事前観測数']==record['隔離数']==0)
   check('native-distinct-observations:'+str(count),len(obs)==len(calls)==len(teachers) and len({encoded(o.原入力) for o in obs})==len(teachers))
   check('native-reference-exactness:'+str(count),bool(equalities)==(count<=len(teachers)) and all(p.根拠参照群==refs and not p.反証参照群 for p in equalities))
   check('native-actual-observation-values:'+str(count),all(ob.原入力=={'候補':pair['output'],'出力':pair['output']} and call['input']==pair['input'] and call['output']==pair['output'] for pair,ob,call in zip(teachers,obs,calls)))
   check('native-state-unmodified:'+str(count),identity is fitted.モデル群 and dataclasses.asdict(fitted)==state)
   save(out,'native-support-'+str(count)+'.json.gz',{'support':count,'record':record,'candidate_calls':calls,'native_calls':machine.calls,'ledger':machine.台帳.JSON相当(),'references':refs,'equalities':equalities,'query_calls':0,'retained_models':identity})
   rows.append({'minimum_support':count,'current_observations':len(obs),'prior_observations':0,'quarantined':record['隔離数'],'equality_admitted':record['同値採用'],'query_calls':0,'raw_exhaust_status':machine.calls[-1]['raw_exhaust'].状態})
 finally:a.fit=original
 return rows

def harness_failures(out):
 value={(1,2):'tuple','(1, 2)':'string',7:'integer','7':'digit-string'}
 encoded_keys=json.loads(h.encoded({'geometry_prefix':value}))['geometry_prefix']['__arc2_typed_mapping__']
 check('tuple-key-diagnostic-lossless-no-collision',len(encoded_keys)==4 and encoded_keys[0]['key']==['tuple',[['int',1],['int',2]]] and [x['value'] for x in encoded_keys]==['tuple','string','integer','digit-string'])
 save(out,'typed-key-serialization.json',{'input_key_descriptors':encoded_keys,'passed':True})
 primary=MemoryError('primary-evaluation');result={'version':h.VERSION,'completed':False,'semantic_HOLD':False,'resource_failure':True};h.add_failure(result,primary,'injected_primary')
 original=h.write;calls=[]
 def fail_once(path,value):
  calls.append(str(path))
  if len(calls)==1:raise OSError('injected completion reporter failure')
  return original(path,value)
 h.write=fail_once
 try:ok=h.persist_result(out/'failure-test.json.gz',result)
 finally:h.write=original
 fallback=json.loads((out/'failure-test.json.gz.failure.json').read_text());check('completion-report-failure-preserves-primary',not ok and fallback['exception']=='MemoryError' and fallback['secondary_errors'][0]['phase']=='completion_write')
 journal=h.Journal(out/'journal-failure-control.jsonl.gz');original_file=journal.file
 class BadFile:
  def write(self,data):raise OSError('injected event reporting failure')
  def fileno(self):return original_file.fileno()
  def close(self):return original_file.close()
 journal.file=BadFile();caught=None
 try:journal({'kind':'pending_raw_return','output':[[0]],'detail':{'status':'complete'}})
 except OSError as e:caught=e
 evidence={'version':h.VERSION,'completed':False,'semantic_HOLD':False,'resource_failure':False};h.add_failure(evidence,caught,'journal');h.close_journal(journal,evidence)
 check('journal-pending-raw-preserved',evidence['pending_event_suffix'][0]['output']==[[0]] and evidence['pending_event_suffix'][0]['detail']['status']=='complete' and evidence['durable_event_prefix_count']==0)
 save(out,'journal-failure-evidence.json',evidence)

def main():
 resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,)*2);resource.setrlimit(resource.RLIMIT_CPU,(10,10));signal.signal(signal.SIGALRM,lambda *args:(_ for _ in ()).throw(TimeoutError('whole-regression60s')));signal.alarm(60)
 ap=argparse.ArgumentParser();ap.add_argument('--repository-root',type=pathlib.Path);ap.add_argument('--output-base',type=pathlib.Path);ap.add_argument('--deployment-check-only',action='store_true');args=ap.parse_args()
 deployed=(P/'HDS/学習系統/v0.4.2/hds学習系統').is_dir();repo=args.repository_root.resolve() if args.repository_root else P if deployed else P.parent/'source-evidence/repository'
 base=args.output_base.resolve() if args.output_base else pathlib.Path(tempfile.gettempdir());base.mkdir(parents=True,exist_ok=True);out=pathlib.Path(tempfile.mkdtemp(prefix='arc2-candidate044-',dir=base))
 summary={'artifact_directory':str(out),'deployment_root':str(P),'repository_root':str(repo),'explicit_repository_root':args.repository_root is not None,'deployed_default_root':deployed,'deployment_check_only':args.deployment_check_only,'full120_runs':0,'public_query_runs':0}
 runtime_calls={}
 def profile(frame,event,arg):
  if event=='call' and frame.f_code.co_name in ('fit','render','predict','候補機構を学習','実行','照会') and is_runtime_source(frame.f_code.co_filename,repo):
   name=frame.f_code.co_name;runtime_calls[name]=runtime_calls.get(name,0)+1
 try:
  pins=verify(repo)
  if args.deployment_check_only:sys.setprofile(profile)
  a,repo=load(repo);packet=json.loads(gzip.decompress((F/'fixtures.json.gz').read_bytes()));teachers=packet['teachers'];closure(a,repo,out)
  if args.deployment_check_only:
   sys.setprofile(None)
   if runtime_calls:raise AssertionError('deployment-only path executed candidate/native behavior')
   if a.PROGRAMS!=(('initial_color',),('refreshed_color',),('any_color',)):raise AssertionError('frozen three-law domain changed')
   summary.update(runtime_calls=runtime_calls,fit_render_predict_native_calls=0,behavioral_suite_executed=False)
  else:
   geometry(a,packet,out);strict(a,teachers,out);fitted=fit_state(a,teachers,out);exceptions(a,teachers,fitted,out);summary['native']=native(a,repo,fitted,teachers,out);harness_failures(out)
   if CHECKS!=pins['expected_nonadministrative_checks']:raise AssertionError('behavioral assertion list/order changed')
   summary['behavioral_suite_executed']=True
  if verify(repo)!=pins:raise AssertionError('source pins changed during regression')
  save(out,'source-verification.json',{'pins':pins,'bridge_actual_sha256':sha(repo/'接続/ARC2/HDS接続.py'),'whole_bridge_sha_enforced':False,'three_bridge_ASTs_enforced':True,'whole_bridge_executed':False})
  summary.update(successful=True,tests_run=len(CHECKS),passed_cases=CHECKS,pin_checks=len(PIN_CHECKS),pin_check_names=PIN_CHECKS)
 except BaseException as error:
  sys.setprofile(None);summary.update(successful=False,tests_run=len(CHECKS),passed_cases=CHECKS,pin_checks=len(PIN_CHECKS),exception=h.safe_exception(error),raw_exception=h.capture_raw_exception(error))
 save(out,'summary.json',summary);print(encoded(summary));return 0 if summary['successful'] else 1
if __name__=='__main__':raise SystemExit(main())
