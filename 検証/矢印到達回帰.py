#!/usr/bin/env python3
"""NEW candidate039 synthetic, strict-state, exception-prefix and native controls."""
import sys
sys.dont_write_bytecode=True
import argparse,ast,copy,dataclasses,enum,gzip,hashlib,importlib,json,pathlib,traceback,types,resource,signal,tempfile,os
from collections import deque
P=pathlib.Path(__file__).resolve().parents[1]
F=P/'検証/矢印到達資料'
def readpins():return json.loads(gzip.decompress((F/'dependency-pins.json.gz').read_bytes()))
CHECKS=[]
def check(name,condition=True):
 if not condition:raise AssertionError(name)
 CHECKS.append(name)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def serial(v):
 if isinstance(v,BaseException):return {'exception':type(v).__name__,'message':safe_message(v)}
 if dataclasses.is_dataclass(v):return serial(dataclasses.asdict(v))
 if isinstance(v,enum.Enum):return serial(v.value)
 if isinstance(v,dict):return {str(k):serial(x) for k,x in v.items()}
 if isinstance(v,(tuple,list,deque)):return [serial(x) for x in v]
 if isinstance(v,(set,frozenset)):return [serial(x) for x in sorted(v,key=repr)]
 if v is None or type(v) in (str,int,float,bool):return v
 raise TypeError(type(v).__name__)
def safe_message(e):
 try:return str(e)
 except BaseException:return '<exception message unavailable>'
def encoded(v):return json.dumps(serial(v),ensure_ascii=False,separators=(',',':'))
def save(out,name,v):
 raw=(encoded(v)+'\n').encode();p=out/name;p.write_bytes(gzip.compress(raw,compresslevel=1,mtime=0) if p.suffix=='.gz' else raw)
def verify(repo):
 pins=readpins()
 for path,h in pins['payload_pins'].items():check('payload-pin:'+path,sha(P/path)==h)
 for path,h in pins['base_source_pins'].items():check('base-pin:'+path,sha(repo/path)==h)
 bridge=repo/'接続/ARC2/HDS接続.py'
 nodes={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(bridge.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name in pins['native_bridge_ast']}
 check('three-native-bridge-AST-pins',nodes==pins['native_bridge_ast'])
 # The old whole bridge hash is snapshot provenance only; integration changes elsewhere are allowed.
 return pins
class Journal:
 def __init__(self,path):self.file=gzip.open(path,'wt',compresslevel=1);self.counts={}
 def __call__(self,event):
  self.file.write(encoded(event)+'\n');self.file.flush();self.counts[event['kind']]=self.counts.get(event['kind'],0)+1
 def close(self):self.file.close()
def load(root):
 repo=pathlib.Path(root).resolve();sys.path.insert(0,str(repo))
 pkg=types.ModuleType('_fresh039');pkg.__path__=[str(P/'接続/ARC2')];sys.modules[pkg.__name__]=pkg
 a=importlib.import_module(pkg.__name__+'.矢印到達教材')
 check('seven exact imported helper files',set(str(pathlib.Path(m.__file__).relative_to(repo)) for n,m in sys.modules.items() if n.startswith('接続.ARC2.') and getattr(m,'__file__',None))=={'接続/ARC2/'+n+'.py' for n in readpins()['import_closure']})
 return a,repo

def geometry(a,out):
 literal=[((-1,0),[(4,3),(5,2),(5,4)],(3,3)),((-1,1),[(4,3),(5,3),(4,2)],(3,4)),((0,1),[(4,3),(3,2),(5,2)],(4,4)),((1,1),[(4,3),(3,3),(4,2)],(5,4)),((1,0),[(4,3),(3,2),(3,4)],(5,3)),((1,-1),[(4,3),(3,3),(4,4)],(5,2)),((0,-1),[(4,3),(3,4),(5,4)],(4,2)),((-1,-1),[(4,3),(4,4),(5,3)],(3,2))]
 rows=[]
 for direction,cells,endpoint in literal:
  grid=[[0]*8 for _ in range(8)]
  for r,c in cells:grid[r][c]=2
  expected=copy.deepcopy(grid);expected[endpoint[0]][endpoint[1]]=9
  output,record=a.render(grid,(1,'cell',9,8));check('literal-eight-direction:'+str(direction),output==expected and record['roles']['actors'][0]['direction']==direction)
  rows.append({'input':grid,'model':(1,'cell',9,8),'expected_direction':direction,'expected':expected,'output':output,'record':record})
 bad=[([], 'invalid_grid'),([[0,1]],'background_tie'),([[0]*5 for _ in range(5)],'input_ownership_incomplete')]
 g=[[0]*5 for _ in range(5)];g[2][2]=2;bad.append((g,'non_arrow_component'))
 g=[[0]*5 for _ in range(5)];g[2][1:4]=[2,2,2];bad.append((g,'arrow_role_not_unique'))
 for g,reason in bad:
  scene,rec=a.parse(g);check('parse-reject:'+reason,scene is None and rec.get('reason')==reason);rows.append({'input':g,'model':None,'expected':{'scene':None,'reason':reason},'parse_only':True,'scene':scene,'record':rec})
 g=copy.deepcopy(rows[0]['input']);output,rec=a.render(g,(29,'cell',9,8));check('endpoint-out-of-bounds',output is None and rec['execution']['reason']=='endpoint_out_of_bounds');rows.append({'input':g,'model':(29,'cell',9,8),'expected':{'output':None,'reason':'endpoint_out_of_bounds'},'output':output,'record':rec})
 save(out,'literal-geometry.json.gz',rows)

def strict(a,teachers,out):
 class ListSubclass(list):pass
 class StrEnum(str,enum.Enum):CELL='cell'
 class IntEnum(enum.IntEnum):ONE=1
 grids=[(),[[True]],[[IntEnum.ONE]],[[0.0]],ListSubclass([[0]]),[ListSubclass([0])],[[0],[0,1]],[[]],[[10]],[[0]*31],[[0]]*31]
 for i,g in enumerate(grids):check('strict-grid:'+str(i),not a.valid_grid(g))
 models=[(True,'cell',1,2),(1,StrEnum.CELL,1,2),(1,'cell',True,2),(1,'cell',1,IntEnum.ONE),[1,'cell',1,2],(1,'bad',1,2),(0,'cell',1,2),(30,'cell',1,2),(1,'cell',-1,2),(1,'cell',1,10)]
 for i,m in enumerate(models):check('strict-model:'+str(i),not a.valid_model(m))
 domain=tuple((d,s,c,m) for d in range(1,30) for s in ('cell','component') for c in range(10) for m in range(10))
 check('literal5800-domain',a.PROGRAMS==domain and len(set(domain))==5800 and a.core.MODEL_COUNT==5800 and a.core.FIT_BUDGET==200000)
 for i,state in enumerate([[],list(domain[:1]),(domain[0],domain[0]),(domain[1],domain[0]),([1,'cell',1,2],),((1,'cell',True,2),)]):
  output,record=a.predict(teachers[0]['input'],state);check('strict-retained-state:'+str(i),output is None and record['failure']=='invalid_retained_state')
 check('ordered-subset-state',a.valid_models((domain[0],domain[10])) and a.valid_models(()))
 invalid=[([], 'too_few_distinct_teacher_inputs'),([teachers[0]],'too_few_distinct_teacher_inputs'),([teachers[0],teachers[0]],'duplicate_or_conflicting_teacher_input'),([dict(teachers[0],extra=1),teachers[1]],'invalid_teacher_pair'),([{},teachers[1]],'invalid_teacher_pair'),(ListSubclass(teachers),'invalid_teacher_container')]
 rows=[]
 for pairs,reason in invalid:
  models,record=a.fit(pairs);check('strict-teachers:'+reason,not models and record['failure']==reason);rows.append(record)
 proofteachers=[{'input':[[0,0],[0,0]],'output':[[0,0],[0,0]]},{'input':[[0,0,0],[0,2,0],[0,0,0]],'output':[[0]]},teachers[0]]
 events=[];models,record=a.fit(proofteachers,events.append)
 check('complete-three-parse-proof',not models and record['rejected_teacher_indices']==[0,1] and record['proof_parse_calls']==3 and record['evaluated_teacher_calls']==0 and record['symbolic_unexecuted_teacher_calls']==17400 and not any(e['kind']=='model_teacher_start' for e in events))
 save(out,'parse-proof.json.gz',{'teachers':proofteachers,'record':record,'events':events})
 # 35 distinct valid arrows exceed original actual execution cap; all35 parse first, zero renders.
 cap=[]
 for h in range(7,14):
  for w in range(7,12):
   g=[[0]*w for _ in range(h)];g[2][3]=g[3][2]=g[3][4]=2;cap.append({'input':g,'output':copy.deepcopy(g)})
 events=[];caught=None
 try:a.fit(cap,events.append)
 except a.EnumerationBudgetExceeded as e:caught=e
 check('original200000-cap35',caught is not None and len([e for e in events if e['kind']=='parse_completed'])==35 and not any(e['kind']=='model_teacher_start' for e in events) and caught.evaluation_diagnostic['required_calls']==203000 and caught.evaluation_diagnostic['committed_model_count']==0)
 save(out,'cap-control.json.gz',{'teacher_count':35,'required_actions':203000,'actual_model_teacher_actions':0,'events':events,'diagnostic':caught.evaluation_diagnostic})
 save(out,'strict-invalid-teachers.json.gz',rows)

def fit_and_state(a,teachers,expected,out):
 audit={};journal=Journal(out/'fit.events.jsonl.gz');before=copy.deepcopy(teachers)
 try:fitted=a.矢印到達教材(teachers,audit,journal)
 finally:journal.close()
 check('independent-literal-retained-model',fitted.モデル群==tuple(tuple(m) for m in expected))
 check('complete5800-all-teachers',len(audit['model_returns'])==5800 and audit['evaluated_teacher_calls']==5800*len(teachers) and audit['symbolic_unexecuted_teacher_calls']==0 and journal.counts['model_teacher_return']==5800*len(teachers))
 check('teacher-inputs-unmodified',teachers==before)
 original_first_output=copy.deepcopy(teachers[0]['output']);teachers[0]['output'][0][0]=6
 check('fitted-state-detached-from-teacher-targets',fitted.候補(teachers[0]['input'],{})[0]==original_first_output)
 teachers[0]['output']=original_first_output

 identity=fitted.モデル群;state=dataclasses.asdict(fitted);predictions=[]
 for i,pair in enumerate(teachers):
  output,rec=fitted.候補(pair['input'],{});check('teacher-reproduction:'+str(i),output==pair['output'] and len(rec['returns'])==len(identity));predictions.append({'teacher_index':i,'output':copy.deepcopy(output),'detail':copy.deepcopy(rec)});output[0][0]=7
 check('detached-prediction-output',fitted.候補(teachers[0]['input'],{})[0]==teachers[0]['output'])
 for field,value in [('モデル群',()),('教師数',0),('不足理由','x')]:
  error=None
  try:setattr(fitted,field,value)
  except (dataclasses.FrozenInstanceError,AttributeError,TypeError) as e:error=e
  check('frozen-state:'+field,error is not None)
 check('state-identity-preserved',fitted.モデル群 is identity and dataclasses.asdict(fitted)==state)
 output,rec=a.predict(teachers[0]['input'],((1,'cell',8,8),(1,'cell',9,8)));check('all-model-output-disagreement',output is None and rec['failure']=='retained_models_disagree' and len(rec['returns'])==2)
 output,rec=a.predict(teachers[0]['input'],((1,'cell',9,8),(29,'cell',9,8)));check('any-model-failure',output is None and rec['failure']=='retained_model_failed' and len(rec['returns'])==2)
 save(out,'complete-fit.json.gz',{'models':identity,'audit':audit,'events':journal.counts,'predictions':predictions,'state':state})
 return fitted

def exceptions(a,teachers,fitted,out):
 rows=[]
 def run(name,target,attribute,call,trigger,expected_kind,predicate,error_class=MemoryError,observer_none=False):
  original=getattr(target,attribute);primary=error_class(name);events=[];count=0
  def replacement(*args,**kwargs):
   nonlocal count
   count+=1
   if trigger(count,args,kwargs):raise primary
   return original(*args,**kwargs)
  setattr(target,attribute,replacement);caught=None
  try:call(None if observer_none else events.append)
  except BaseException as e:caught=e
  finally:setattr(target,attribute,original)
  diag=getattr(caught,'evaluation_diagnostic',None)
  chain=[];node=diag
  while isinstance(node,dict):chain.append(node);node=node.get('inner_diagnostic')
  check('primary-rethrow:'+name,caught is primary)
  check('diagnostic-prefix:'+name,any(d.get('kind')==expected_kind and predicate(d) for d in chain))
  check('exception-never-semantic-HOLD:'+name,all(d.get('semantic_HOLD') is False for d in chain))
  rows.append({'name':name,'observer_none':observer_none,'exception':caught,'diagnostic':diag,'events':events})
 run('geometry-mid-second-arrival',a.core,'shifted_sparse_point_mask',lambda obs:a.render(teachers[1]['input'],(1,'component',9,8),obs),lambda n,*x:n==2,'render_exception',lambda d:any(f['function']=='render_scene' and len(f['locals'].get('endpoints',[]))==1 for f in d.get('geometry_prefix',[])),observer_none=True)
 run('ordinary-runtime-not-semantic',a.core,'parse_input',lambda obs:a.fit(teachers,obs),lambda *x:True,'fit_exception',lambda d:d['resource_failure'] is False,error_class=RuntimeError,observer_none=True)
 run('recursion-propagates',a.core,'parse_input',lambda obs:a.fit(teachers,obs),lambda *x:True,'fit_exception',lambda d:d['resource_failure'] is True,error_class=RecursionError,observer_none=True)
 run('parse-helper-failure',a.core,'parse_input',lambda obs:a.fit(teachers,obs),lambda *x:True,'parse_exception',lambda d:d['raw_return_pending'] is False)
 run('render-row-after-raw',a,'render_row',lambda obs:a.fit(teachers,obs),lambda *x:True,'render_exception',lambda d:d['raw_return_pending'] and d['pending_detail'] is not None)
 run('teacher-row-after-raw',a,'teacher_row',lambda obs:a.fit(teachers,obs),lambda n,*x:n==3,'fit_exception',lambda d:d['raw_return_pending'] and d['current_teacher_row_count']==2 and d['pending_detail'] is not None)
 run('prediction-model-row-after-raw',a,'model_row',lambda obs:a.predict(teachers[0]['input'],fitted.モデル群,obs),lambda *x:True,'render_model_exception',lambda d:d['raw_return_pending'] and d['pending_execution'] is not None)
 # Observer failures target exact trace boundaries. Keep primary and every committed/pending prefix.
 for kind,pred in [('parse_return',lambda d:any(n.get('raw_return_pending') and n.get('pending_detail') is not None for n in d)),('parse_completed',lambda d:d[0]['completed_parse_records']),('model_teacher_return',lambda d:d[0]['current_teacher_row_count']==1),('model_completed',lambda d:d[0]['committed_model_count']==1),('retained_model_return',lambda d:len(d[0]['completed_model_returns'])==1)]:
  primary=TimeoutError('observer:'+kind);events=[];caught=None
  def observe(e):
   events.append(e)
   if e['kind']==kind:raise primary
  try:
   if kind=='retained_model_return':a.predict(teachers[0]['input'],fitted.モデル群,observe)
   else:a.fit(teachers,observe)
  except BaseException as e:caught=e
  diag=getattr(caught,'evaluation_diagnostic',None);chain=[];node=diag
  while isinstance(node,dict):chain.append(node);node=node.get('inner_diagnostic')
  check('observer-primary-prefix:'+kind,caught is primary and bool(pred(chain)) and all(d['semantic_HOLD'] is False for d in chain))
  rows.append({'name':'observer:'+kind,'diagnostic':diag,'events':events})
 original=a.diagnostic_record
 def fail_diag(*args):raise RecursionError('secondary-diagnostic')
 a.diagnostic_record=fail_diag
 try:run('secondary-diagnostic-preserves-primary',a.core,'parse_input',lambda obs:a.fit(teachers,obs),lambda *x:True,'fit_exception',lambda d:d.get('diagnostic_construction_failure')=='RecursionError')
 finally:a.diagnostic_record=original

 run('observer-none-outer-wrapping',a,'model_row',lambda obs:a.render(teachers[0]['input'],(1,'component',9,8),obs),lambda *x:True,'render_model_exception',lambda d:d['raw_return_pending'] and d['pending_output'] is not None and d['pending_execution'] is not None and d['completed_roles'] is not None,observer_none=True)
 run('observer-none-one-completed-parse',a.core,'parse_input',lambda obs:a.fit(teachers,obs),lambda n,*x:n==2,'fit_exception',lambda d:len(d['completed_parse_records'])==1 and len(d['completed_scenes'])==1 and d['active_call']['teacher_index']==1,observer_none=True)
 run('observer-none-one-completed-teacher',a.core,'render_scene',lambda obs:a.fit(teachers,obs),lambda n,*x:n==2,'fit_exception',lambda d:d['current_teacher_row_count']==1 and len(d['completed_teacher_returns'])==1 and d['active_call']['teacher_index']==1,observer_none=True)
 class UnprintableMemoryError(MemoryError):
  def __str__(self):raise ValueError('formatting failed')
 run('observer-none-unprintable-primary',a.core,'parse_input',lambda obs:a.fit(teachers,obs),lambda *x:True,'fit_exception',lambda d:d.get('message')=='<exception message unavailable>',error_class=UnprintableMemoryError,observer_none=True)
 original_report=a.report_exception;original_parse=a.core.parse_input;primary=MemoryError('original-primary');caught=None
 def failing_report(*args,**kwargs):raise RecursionError('report construction failed')
 def failing_parse(*args,**kwargs):raise primary
 a.report_exception=failing_report;a.core.parse_input=failing_parse
 try:a.fit(teachers,None)
 except BaseException as error:caught=error
 finally:a.report_exception=original_report;a.core.parse_input=original_parse
 check('observer-none-report-exception-primary',caught is primary)
 rows.append({'name':'observer-none-report-exception-primary','observer_none':True,'exception':caught,'diagnostic_expected_absent':True,'original_primary_preserved':caught is primary})
 save(out,'exception-prefixes.json.gz',rows)

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
  for count in dict.fromkeys((len(teachers),len(teachers)+1,3)):
   machine=Recording(count);calls=[];check('native-empty-ledger:'+str(count),machine.台帳.全取得()=={})
   def candidate(grid,policy):
    check('same-fitted-identity',fitted.モデル群 is identity);output,detail=fitted.候補(grid,policy);calls.append({'input':grid,'output':output,'detail':detail});return output,detail
   boundary='ARC矢印到達';record=helpers['候補機構を学習'](machine,{'train':teachers},(),boundary,candidate)
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

def main():
 resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024));resource.setrlimit(resource.RLIMIT_CPU,(10,10));signal.signal(signal.SIGALRM,lambda *args:(_ for _ in ()).throw(TimeoutError('60 second regression whole wall')));signal.alarm(60)
 ap=argparse.ArgumentParser();ap.add_argument('--repository-root',type=pathlib.Path);ap.add_argument('--output-base',type=pathlib.Path);args=ap.parse_args()
 deployed=(P/'HDS/学習系統/v0.4.2/hds学習系統').is_dir()
 repo=args.repository_root.resolve() if args.repository_root else P if deployed else P.parent/'source-evidence/repository'
 base=args.output_base.resolve() if args.output_base else pathlib.Path(tempfile.gettempdir());base.mkdir(parents=True,exist_ok=True)
 out=pathlib.Path(tempfile.mkdtemp(prefix='arc2-candidate039-',dir=base));summary={'artifact_directory':str(out),'deployment_root':str(P),'repository_root':str(repo),'explicit_repository_root':args.repository_root is not None,'deployed_default_root':deployed,'full120_runs':0,'public_query_runs':0}
 try:
  pins=verify(repo);a,repo=load(repo);packet=json.loads(gzip.decompress((F/'fixtures.json.gz').read_bytes()));teachers=packet['teachers']
  geometry(a,out);strict(a,teachers,out);fitted=fit_and_state(a,teachers,packet['expected_models'],out);exceptions(a,teachers,fitted,out);summary['native']=native(a,repo,fitted,teachers,out)
  check('all-source-pins-unchanged',verify(repo)==pins)
  save(out,'source-verification.json',{'pins':pins,'bridge_actual_sha256':sha(repo/'接続/ARC2/HDS接続.py'),'whole_bridge_sha_enforced':False,'three_bridge_ASTs_enforced':True,'whole_bridge_executed':False,'snapshot_bridge_sha256':pins['bridge_snapshot_sha256']})
  summary.update(successful=True,tests_run=len(CHECKS),passed_cases=CHECKS)
 except BaseException as error:
  summary.update(successful=False,tests_run=len(CHECKS),passed_cases=CHECKS,exception=type(error).__name__,message=safe_message(error),traceback=traceback.format_exc(),evaluation_diagnostic=getattr(error,'evaluation_diagnostic',None))
 save(out,'summary.json',summary);print(encoded(summary));return 0 if summary['successful'] else 1
if __name__=='__main__':raise SystemExit(main())
