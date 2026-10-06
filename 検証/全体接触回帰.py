#!/usr/bin/env python3
import sys
sys.dont_write_bytecode=True
import argparse,ast,copy,dataclasses,enum,gzip,importlib,importlib.util,json,pathlib,types,os,errno,tempfile,resource,signal
from unittest.mock import patch
P=pathlib.Path(__file__).resolve().parents[1]
F=P/'検証/全体接触資料'
def readpins():return json.loads(gzip.decompress((F/'dependency-pins.json.gz').read_bytes()))
spec=importlib.util.spec_from_file_location('_body_ports_evidence_support',F/'evidence_support.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
PIN_CHECKS=[]
def pincheck(name,condition):
 if not condition:raise AssertionError(name)
 PIN_CHECKS.append(name)
def verify(repo):
 pins=readpins()
 for name,digest in pins['payload_pins'].items():pincheck('payload:'+name,h.sha(P/name)==digest)
 for name,digest in pins['base_source_pins'].items():pincheck('base:'+name,h.sha(repo/name)==digest)
 native={n.name:ast.dump(n,include_attributes=False)for n in ast.parse((repo/'接続/ARC2/HDS接続.py').read_bytes()).body if isinstance(n,ast.FunctionDef)and n.name in pins['native_bridge_ast']}
 pincheck('native-helper-ASTs',native==pins['native_bridge_ast'])
 return pins
CHECKS=[]
def check(name,condition=True):
 if not condition:raise AssertionError(name)
 CHECKS.append(name)
def save(out,name,value):h.write(out/name,value)
LOAD_INDEX=0
def load(root):
 global LOAD_INDEX
 repo=pathlib.Path(root).resolve();sys.path.insert(0,str(repo));LOAD_INDEX+=1
 package_name='_body_ports_public_'+str(LOAD_INDEX);pkg=types.ModuleType(package_name);pkg.__path__=[str(P/'接続/ARC2')];sys.modules[package_name]=pkg
 a=importlib.import_module(package_name+'.全体接触教材')
 actual={str(pathlib.Path(m.__file__).relative_to(repo))for n,m in sys.modules.items()if n.startswith('接続.ARC2.')and getattr(m,'__file__',None)}
 expected={'接続/ARC2/'+name+'.py'for name in readpins()['import_closure']}
 pincheck('full-transitive-import-closure',actual==expected)
 helper=importlib.import_module('接続.ARC2.凡例旋回教材');clone=importlib.import_module('接続.ARC2.既存凡例穴対応')
 pincheck('exact-helper-global-bindings',a.core.body_components is helper.body_components and a.core.valid_grid is helper.valid_grid and a.valid_grid is a.core.valid_grid and a.core.clone_grid is clone.clone_grid)
 pincheck('original-geometry-codes-pinned',a.GEOMETRY_CODES==(a.core.parse.__code__,a.core.execute.__code__))
 return a,repo

def literal(a,f,out):
 rows=[]
 for i,pair in enumerate(f['teachers']):
  roles,record=a.core.parse(pair['input']);check('one-literal-role-'+str(i),len(roles)==1)
  output,detail=a.render(pair['input'],('absorb','erase'));check('literal-absorb-erase-'+str(i),output==pair['output'])
  check('finite-directed-state-bound-'+str(i),all(r['detail']['state_count']<=r['detail']['state_space_bound']for r in detail['returns']))
  rows.append({'kind':'positive','teacher_index':i,'roles':roles,'parse_record':record,'output':output,'detail':detail})
 corner=f['two_normal'];roles,record=a.core.parse(corner['input'])
 check('genuine-two-normal-roles',len(roles)==2 and [list(r['bodies'][0]['outward'])for r in roles]==corner['outward_order'])
 check('one-declared-colour-role-both-normals',sum(bool(t.get('accepted_role_indices'))for t in record['all_role_trials'])==1)
 for expected in corner['expected']:
  output,detail=a.render(corner['input'],tuple(expected['model']))
  check('preserve-two-normal-disagreement-'+str(expected['model']),output is None and detail['failure']==expected['failure'] and [r['output']for r in detail['returns']]==expected['role_outputs'])
  rows.append({'kind':'corner','model':expected['model'],'expected':expected,'output':output,'detail':detail})
 save(out,'literal-full-returns.json.gz',rows)
 # Historical helper contract deliberately accepts list subclasses, but rejects bool/float/enum pixels.
 class GridList(list):pass
 class Digit(enum.IntEnum):ONE=1
 for g in([],(),[[]],[[True]],[[Digit.ONE]],[[0.0]],[[-1]],[[10]],[[0]*31],[[0]]*31,[[0],[0,1]]):
  output,rec=a.render(g,('absorb','erase'));check('invalid-grid-'+str(sum(name.startswith('invalid-grid-')for name in CHECKS)),output is None and rec['failure']=='invalid_grid')
 check('preserve-list-subclass-helper-semantics',a.valid_grid(GridList([GridList([0])])) is True)
 for model in(['absorb','erase'],('absorb',),('absorb','erase',0),(1,'erase')):
  output,rec=a.render(f['teachers'][0]['input'],model);check('invalid-model-'+str(sum(name.startswith('invalid-model-')for name in CHECKS)),output is None and rec['failure']=='invalid_model')
 for models in([('absorb','erase')],(('absorb','erase'),('absorb','erase')),(['absorb','erase'],),None):
  output,rec=a.predict(f['teachers'][0]['input'],models);check('invalid-retained-state-'+str(sum(name.startswith('invalid-retained-state-')for name in CHECKS)),output is None and rec['failure']=='invalid_retained_state')
 check('preserve-distinct-retained-order-semantics',a.valid_models((('continue','preserve'),('absorb','erase'))))
 for teachers in(None,{},[f['teachers'][0]],[f['teachers'][0]]*2,[dict(f['teachers'][0],extra=1),f['teachers'][1]]):
  models,rec=a.fit(teachers);check('teacher-schema-before-fitting-'+str(sum(name.startswith('teacher-schema-before-fitting-')for name in CHECKS)),models==() and rec['failure']in('invalid_teacher_container','invalid_teacher_pair','too_few_distinct_teacher_inputs'))
 output,rec=a.predict(f['teachers'][0]['input'],());check('empty-retained-models',output is None and rec['failure']=='no_retained_models')
 # Active-body-only literal leaves erase/preserve genuinely indistinguishable.
 pairs=copy.deepcopy(f['teachers'])
 for i,pair in enumerate(pairs):
  for r,c in[(7,10),(7,11),(8,10),(8,11),(6,10),(6,11)]:pair['input'][r][c if i==0 else 13-c]=0
 models,rec=a.fit(pairs);check('keep-both-genuine-law-alternatives',models==(('absorb','erase'),('absorb','preserve')))
 output,detail=a.predict(pairs[0]['input'],models);check('all-retained-consensus-copy',output==pairs[0]['output'] and len(detail['returns'])==2 and output is not detail['returns'][0]['output'] and all(x is not y for x,y in zip(output,detail['returns'][0]['output'])))
 save(out,'genuine-model-ambiguity.json.gz',{'teachers':pairs,'models':models,'fit':rec,'output':output,'detail':detail})
 output,detail=a.predict(f['teachers'][0]['input'],models)
 check('genuine-retained-law-disagreement',output is None and detail['failure']=='retained_models_disagree' and len(detail['returns'])==2)
 save(out,'genuine-retained-law-disagreement.json.gz',{'models':models,'input':f['teachers'][0]['input'],'output':output,'detail':detail})
 original_render=a.render;calls=[]
 def first_role_failed(grid,model,*args,**kwargs):
  calls.append(model)
  if model==models[0]:return None,{'failure':'declared synthetic first retained model failure'}
  return original_render(grid,model,*args,**kwargs)
 with patch.object(a,'render',first_role_failed):output,detail=a.predict(f['teachers'][0]['input'],models)
 check('failure-retains-all-other-model-returns',output is None and detail['failure']=='retained_model_failed'and calls==list(models)and len(detail['returns'])==2)
 save(out,'retained-failure-exhaustive-returns.json.gz',{'injection':'First retained render returns declared synthetic complete failure; second executes real geometry','calls':calls,'output':output,'detail':detail})


def fit_native(a,repo,f,out):
 teachers=copy.deepcopy(f['teachers']);before=copy.deepcopy(teachers);events=[];audit={};obj=a.全体接触教材(teachers,audit,events.append)
 check('one-all-teacher-law',obj.モデル群==(('absorb','erase'),))
 check('every-program-teacher-call',audit['evaluated_teacher_calls']==8 and len(audit['model_returns'])==4 and all(len(r['returns'])==2 for r in audit['model_returns']))
 check('teachers-unmodified',teachers==before)
 state=dataclasses.asdict(obj);caught=None
 try:obj.モデル群=()
 except BaseException as error:caught=error
 check('frozen-slotted-state',isinstance(caught,(dataclasses.FrozenInstanceError,AttributeError))and not hasattr(obj,'__dict__'))
 output,detail=obj.候補(teachers[0]['input'],{});check('teacher-reproduction',output==teachers[0]['output']);output[0][0]=9
 again,_=obj.候補(teachers[0]['input'],{});check('output-detached',again==teachers[0]['output'])
 teachers[0]['output'][0][0]=9;audit['model_returns'].clear();check('teacher-audit-detached-state',dataclasses.asdict(obj)==state)
 # Fit record is already preserved through independently copied event values before audit mutation.
 save(out,'positive-fit-and-state.json.gz',{'teachers':before,'events':events,'state':state,'reproduced_output':again,'native_fit_identity':obj.モデル群})
 native_rows=native(a,repo,obj,before,out)
 return native_rows

def boundaries(a,f,out,case):
 teachers=copy.deepcopy(f['teachers']);g=teachers[0]['input'];primary={'runtime_primary':RuntimeError,'recursion_primary':RecursionError,'timeout_primary':TimeoutError}.get(case,MemoryError)('declared '+case);secondary=RuntimeError('reporter failure');events=[];caught=None;stack=[]
 def observer(event):
  events.append(event)
  if case=='completed_role'and event['kind']=='role_completed':raise primary
  if case=='completed_teacher'and event['kind']=='model_teacher_return':raise primary
  if case=='completed_model'and event['kind']=='model_completed':raise primary
  if case=='prediction_return'and event['kind']=='retained_model_return':raise primary
 original=a.core.body_components;calls=0
 def interrupted(*args,**kwargs):
  nonlocal calls
  calls+=1
  if calls==(2 if case=='parse_prefix' else 1):raise primary
  return original(*args,**kwargs)
 original_execute=a.core.execute;execute_calls=0
 def later(*args,**kwargs):
  nonlocal execute_calls
  execute_calls+=1
  if execute_calls==4:raise primary
  return original_execute(*args,**kwargs)
 if case in('parse_prefix','reporter','diagnostic','unprintable','runtime_primary','recursion_primary','timeout_primary'):
  stack.append(patch.object(a.core,'body_components',interrupted))
 if case=='reporter':stack.append(patch.object(a,'report_exception',side_effect=secondary))
 if case=='diagnostic':stack.append(patch.object(a,'diagnostic_record',side_effect=secondary))
 if case=='role_pending':stack.append(patch.object(a,'role_row',side_effect=primary))
 if case=='teacher_pending':stack.append(patch.object(a,'teacher_row',side_effect=primary))
 if case=='fit_prefix':stack.append(patch.object(a.core,'execute',later))
 if case=='state_entry':stack.append(patch.object(a,'deepcopy',side_effect=primary))
 if case=='unprintable':
  class Unprintable(MemoryError):
   def __str__(self):raise RuntimeError('message unavailable')
  primary=Unprintable()
 try:
  for p in stack:p.start()
  if case=='state_entry':a.全体接触教材(teachers,{},observer)
  elif case=='prediction_return':a.predict(g,(('absorb','erase'),('absorb','preserve')),observer)
  else:a.fit(teachers,observer)
 except BaseException as error:caught=error
 finally:
  for p in reversed(stack):p.stop()
 check('original-exception-identity-'+case,caught is primary)
 raw=h.capture_raw_exception(caught);d=getattr(caught,'evaluation_diagnostic',None)
 check('never-semantic-hold-'+case,raw['semantic_HOLD']is False and(d is None or d['semantic_HOLD']is False))
 if case=='reporter':check('whole-reporter-cannot-replace-primary',caught.evaluation_reporting_failure is secondary)
 if case=='fit_prefix':check('complete-model-and-teacher-prefix',len(d['completed_model_returns'])==1 and len(d['completed_teacher_returns'])==1 and d['active_call']['model_index']==1 and d['active_call']['teacher_index']==1)
 if case=='teacher_pending':check('complete-render-pending-teacher-row',d['raw_return_pending'] and d['pending_output']==teachers[0]['output'] and len(d['pending_detail']['returns'])==1)
 if case=='role_pending':
  inner=d['inner_diagnostic'];check('complete-execute-pending-role-row',inner['raw_return_pending']and inner['pending_output']==teachers[0]['output']and inner['pending_detail']['state_count']>0)
 if case=='completed_role':check('completed-role-survives-observer',len(d['inner_diagnostic']['completed_role_returns'])==1)
 if case=='completed_teacher':check('completed-teacher-survives-observer',len(d['completed_teacher_returns'])==1)
 if case=='completed_model':check('completed-model-survives-observer',len(d['completed_model_returns'])==1)
 if case=='prediction_return':check('completed-prediction-survives-observer',len(d['completed_model_returns'])==1)
 if case=='parse_prefix':check('literal-parse-prefix-captured',any(x['function']=='parse' and x['locals'].get('trials')for x in raw['frames']))
 if case=='state_entry':check('completed-fit-survives-state-entry',d['completed_fit']['evaluated_teacher_calls']==8 and d['completed_models']==(('absorb','erase'),))
 save(out,'boundary-'+case+'.json.gz',{'primary':caught,'diagnostic':d,'raw':raw,'events':events})



def helper_frontier(a,f,out):
 """One fixed trace interruption inside the unchanged accepted component traversal."""
 helper=a.core.body_components
 helper_code=helper.__code__
 tree=ast.parse(pathlib.Path(helper_code.co_filename).read_bytes())
 function=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='body_components')
 boundary=next(n.lineno for n in ast.walk(function)if isinstance(n,ast.While)and isinstance(n.test,ast.Name)and n.test.id=='stack')
 primary=MemoryError('fixed second-component frontier interruption');events=[];caught=None;hits=[]
 original_trace=a.Budget.trace
 def traced(self,frame,event,arg):
  if frame.f_code is helper_code:
   local=frame.f_locals
   if event=='line'and frame.f_lineno==boundary and len(local.get('result',()))==1 and local.get('first')==(6,10) and len(local.get('stack',()))==2:
    hits.append({'line':frame.f_lineno,'function':frame.f_code.co_name})
    raise primary
   return self.trace
  return original_trace(self,frame,event,arg)
 try:
  with patch.object(a.Budget,'trace',traced):a.fit(f['teachers'],events.append)
 except BaseException as error:caught=error
 check('real-helper-frontier-original-exception',caught is primary and len(hits)==1)
 check('real-helper-source-identity',a.core.body_components is helper and helper.__code__ is helper_code)
 raw=h.capture_raw_exception(caught)
 frames=[row for row in raw['frames']if row['function']=='body_components'and row['source']==helper_code.co_filename]
 check('real-helper-traceback-preserved',len(frames)==1)
 frame=frames[0];v=frame['locals'];completed={(r,c)for r in(3,4,5)for c in(6,7)}
 check('completed-component-before-interruption',len(v['result'])==1 and v['result'][0]['color']==3 and {tuple(x)for x in v['result'][0]['cells']}==completed and v['result'][0]['bbox']==[3,6,5,7])
 check('active-component-prefix',v['colour']==3 and v['first']==[6,10] and {tuple(x)for x in v['cells']}=={(6,10),(7,10),(6,11)})
 check('ordered-pending-helper-stack',v['stack']==[[7,10],[6,11]])
 check('typed-unseen-coordinate-set',frame['local_python_types']['unseen']=='builtins.set'and frame['local_item_python_types']['unseen']==['builtins.tuple']and {tuple(x)for x in v['unseen']}=={(7,11),(8,10),(8,11)} and all(type(c)is int for point in v['unseen']for c in point))
 check('typed-active-cell-set',frame['local_python_types']['cells']=='builtins.set'and frame['local_item_python_types']['cells']==['builtins.tuple'])
 check('ordered-stack-and-coordinate-types',frame['local_python_types']['stack']=='builtins.list'and frame['local_item_python_types']['stack']==['builtins.tuple']and frame['local_python_types']['first']==frame['local_python_types']['q']=='builtins.tuple')
 check('last-inspected-neighbor-preserved',v['q']==[6,9])
 check('helper-locals-complete-no-silent-omission',not frame['omitted_runtime_local_names']and not frame['unserializable_locals'])
 check('helper-interruption-never-semantic-hold',raw['semantic_HOLD']is False and raw['resource_failure']is True and caught.evaluation_diagnostic['semantic_HOLD']is False)
 save(out,'real-helper-frontier-prefix.json.gz',{'intervention':'Trace raises MemoryError at second component while-stack boundary after two neighbor discoveries; original helper bytes and code unchanged','boundary_line':boundary,'hits':hits,'events':events,'raw':raw,'diagnostic':caught.evaluation_diagnostic})


def transport(a,f,out):
 # This control performs one real role execution; fault only its return serialization boundary.
 original=a.core.execute;primary=OSError(errno.ENOSPC,'after exact completed execute return');seen=[];caught=None
 def journal(event):
  seen.append(event)
  if event['kind']=='core_execute_return':raise primary
 h.install_call_observers(a,journal)
 try:a.render(f['teachers'][0]['input'],('absorb','erase'))
 except BaseException as error:caught=error
 check('pending-transport-primary',caught is primary)
 raw=h.capture_raw_exception(caught)
 check('completed-return-in-observer-traceback',any(x['function']=='observed'and isinstance(x['locals'].get('raw_pending'),list)and x['locals']['raw_pending'][0]==f['teachers'][0]['output']for x in raw['frames']))
 check('unwrapped-geometry-code-kept',original.__code__ in a.GEOMETRY_CODES)
 save(out,'completed-return-before-journal-failure.json.gz',{'events':seen,'raw':raw,'diagnostic':caught.evaluation_diagnostic})
 # Genuine per-member journal with an incomplete trailing member must preserve its complete prefix.
 j=h.Journal(out/'truncated.events.jsonl.gz');j.set_context('fit');j({'kind':'model_teacher_start','model_index':0,'teacher_index':0});j.close()
 with(out/'truncated.events.jsonl.gz').open('ab')as stream:stream.write(gzip.compress(b'{"kind":"unfinished"}')[:12])
 rec=h.read_journal(out/'truncated.events.jsonl.gz',2);check('partial-gzip-does-not-invent-return',rec['complete_event_prefix_count']==1 and rec['incomplete_compressed_suffix_bytes']>0 and rec['completed_model_teacher_pairs']['count']==0)
 save(out,'truncated-journal-receipt.json',rec)
 # Late terminal exit overrides a success record; supplied record is explicitly synthetic metadata.
 detail={'version':h.VERSION,'teacher_count':0,'completed':True,'disposition':'logical_HOLD','semantic_HOLD':True,'resource_failure':False,'runtime_unchanged':True,'teacher_returns':[],'fit':{},'models':[],'all_exact':False,'proof_rejected':False,'fit_parse_calls':0,'evaluated_teacher_calls':0,'symbolic_unexecuted_teacher_calls':0}
 h.write(out/'synthetic.record.json.gz',detail)
 for code in(7,-9):
  rec=h.read_completion(out/'synthetic.record.json.gz',False,code,0.1);check('late-exit-no-success-'+str(code),not rec['completed']and not rec['semantic_HOLD'])
 row={'completed':True,'disposition':'CONTROL_PASS','semantic_HOLD':False,'all_exact':False,'resource_failure':False};h.enforce_whole_child_budget(row,10.001,1);check('whole-child-cpu-override',not row['completed']and row['resource_failure'])


def native(a,repo,fitted,teachers,out):
 pins=readpins()
 bridge=repo/'接続/ARC2/HDS接続.py';nodes=[n for n in ast.parse(bridge.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name in pins['native_bridge_ast']]
 pincheck('native-three-function-ASTs',{n.name:ast.dump(n,include_attributes=False) for n in nodes}==pins['native_bridge_ast'])
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
  for count in dict.fromkeys((2,len(teachers),len(teachers)+1)):
   machine=Recording(count);calls=[];check('native-empty-ledger:'+str(count),machine.台帳.全取得()=={})
   def candidate(grid,policy):
    check('same-fitted-identity',fitted.モデル群 is identity);output,detail=fitted.候補(grid,policy);calls.append({'input':grid,'output':output,'detail':detail});return output,detail
   boundary='ARC全体接触';record=helpers['候補機構を学習'](machine,{'train':teachers},(),boundary,candidate)
   obs=machine.台帳.取得('観測台帳');refs=tuple(o.経験識別子 for o in obs);equalities=[p for p in machine.calls[-1]['result'].有効原理群 if helpers['同値原理あり']([p],boundary)]
   check('native-support-boundary:'+str(count),record['採用可'] and record['同値採用']==(count<=len(teachers)) and record['現在観測数']==len(teachers) and record['事前観測数']==record['隔離数']==0)
   check('native-distinct-observations:'+str(count),len(obs)==len(calls)==len(teachers) and len({h.encoded(o.原入力) for o in obs})==len(teachers))
   check('native-reference-exactness:'+str(count),bool(equalities)==(count<=len(teachers)) and all(p.根拠参照群==refs and not p.反証参照群 for p in equalities))
   check('native-actual-observation-values:'+str(count),all(ob.原入力=={'候補':pair['output'],'出力':pair['output']} and call['input']==pair['input'] and call['output']==pair['output'] for pair,ob,call in zip(teachers,obs,calls)))
   check('native-state-unmodified:'+str(count),identity is fitted.モデル群 and dataclasses.asdict(fitted)==state)
   save(out,'native-support-'+str(count)+'.json.gz',{'support':count,'record':record,'candidate_calls':calls,'native_calls':machine.calls,'ledger':machine.台帳.JSON相当(),'references':refs,'equalities':equalities,'query_calls':0,'retained_models':identity})
   rows.append({'minimum_support':count,'current_observations':len(obs),'prior_observations':0,'quarantined':record['隔離数'],'equality_admitted':record['同値採用'],'query_calls':0,'raw_exhaust_status':machine.calls[-1]['raw_exhaust'].状態})
 finally:a.fit=original
 return rows


def independent(a,root,out):
 """Compare exact candidate returns to independently sealed semantic declarations."""
 declaration_path=F/'independent-declarations.json.gz'
 declarations=json.loads(gzip.decompress(declaration_path.read_bytes()));rows=[]
 direction_vectors={'north':[-1,0],'east':[0,1],'south':[1,0],'west':[0,-1]}
 for case in declarations['cases']:
  name=case['case'];grid=case['input'];roles,record=a.core.parse(grid);expected_roles=[]
  for declared in case['structure']['accepted_roles']:
   role={'background':case['structure']['background'],**{key+'_color':declared['assignment'][key]for key in('tail','head','body','port')},'head':declared['source']['head_cell'],'source_cells':declared['source']['cells'],'heading':declared['source']['vector'],'bodies':[]}
   for body in declared['bodies']:
    role['bodies'].append({'id':body['body_index'],'cells':body['cells'],'payload':body['payload'],'exit_cells':body['exits'],'bbox':body['bounds'],'normals':[direction_vectors[n]for n in body['valid_normals']],'outward':body['selected_vector']})
   expected_roles.append(role)
  check('independent-complete-roles-'+name,h.serial(roles)==expected_roles)
  check('independent-all-colour-assignments-'+name,len(record['all_role_trials'])==24 and [bool(x.get('accepted_role_indices'))for x in record['all_role_trials']]==[x['accepted']for x in case['structure']['assignment_audit']])
  for program_name in declarations['program_order']:
   model=tuple(program_name.split('/'));expected=case['programs'][program_name];output,detail=a.render(grid,model)
   check('independent-render-consensus-'+name+'-'+program_name,output==expected['consensus']['output'] and detail.get('failure')==expected['consensus']['failure'])
   check('independent-all-role-returns-'+name+'-'+program_name,len(detail['returns'])==len(expected['per_role']))
   for actual,declared in zip(detail['returns'],expected['per_role']):
    runtime=h.serial(actual['detail'])
    check('independent-role-output-'+name+'-'+program_name+'-'+declared['role_id'],actual['output']==declared['output'] and runtime['paint']==declared['painted_cells'] and runtime['activated']==declared['activated_bodies'] and runtime['inactive']==declared['inactive_bodies'])
    expected_states=[{'state':row['state'],'body_hit':row['body_index'],'successors':row['appended_states_in_order']}for row in declared['fifo_trace']if row['disposition']=='visited_and_painted']
    check('independent-ordered-state-transitions-'+name+'-'+program_name+'-'+declared['role_id'],runtime['states']==expected_states)
   rows.append({'case':name,'program':model,'input':grid,'output':output,'detail':detail})
  # Full four-program retained consensus is separate from individual program role consensus.
  expected=next(x['prediction']for x in case['all_16_retained_program_subsets']if x['retained_programs']==declarations['program_order'])
  output,detail=a.predict(grid,tuple(tuple(x.split('/'))for x in declarations['program_order']))
  check('independent-full-model-consensus-'+name,output==expected['output']and detail.get('failure')==expected['failure']and len(detail['returns'])==4)
  rows.append({'case':name,'retained_programs':declarations['program_order'],'output':output,'detail':detail})
 save(out,'independent-literal-full-returns.json.gz',{'declaration_sha256':h.sha(declaration_path),'scope':'All6 role sets,24 program renders, and6 full-model consensus calls; other declared model subsets are saved declarations, not claimed as separately executed','returns':rows})


def install_control_return_journal(a,journal):
 h.install_call_observers(a,journal)
 for name in('fit','render','predict'):
  original=getattr(a,name)
  def traced(*args,_name=name,_original=original,**kwargs):
   journal({'kind':'control_boundary_start','boundary':_name})
   raw_pending=_original(*args,**kwargs)
   journal({'kind':'control_boundary_return','boundary':_name,'raw_return':raw_pending})
   return raw_pending
  setattr(a,name,traced)

def main():
 resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,)*2);resource.setrlimit(resource.RLIMIT_CPU,(10,10))
 signal.signal(signal.SIGALRM,lambda *unused:(_ for _ in ()).throw(TimeoutError('regression whole wall60s')));signal.alarm(60)
 ap=argparse.ArgumentParser();ap.add_argument('--repository-root',type=pathlib.Path);ap.add_argument('--output-base',type=pathlib.Path);ap.add_argument('--deployment-check-only',action='store_true');args=ap.parse_args()
 deployed=(P/'HDS/学習系統/v0.4.2/hds学習系統').is_dir();repo=args.repository_root.resolve()if args.repository_root else P if deployed else P.parent/'source-evidence/repository'
 base=args.output_base.resolve()if args.output_base else pathlib.Path(tempfile.gettempdir());base.mkdir(parents=True,exist_ok=True);out=pathlib.Path(tempfile.mkdtemp(prefix='arc2-candidate035-',dir=base))
 h.RUNTIME_ROOTS=(P/'接続/ARC2',repo/'接続/ARC2',repo/'HDS/学習系統/v0.4.2/hds学習系統');h.CONTROL_SCRIPT=pathlib.Path(__file__).resolve()
 summary={'artifact_directory':str(out),'repository_root':str(repo),'deployment_root':str(P),'explicit_repository_root':args.repository_root is not None,'deployed_default_root':deployed,'deployment_check_only':args.deployment_check_only,'full120_runs':0,'public_query_runs':0}
 runtime_calls={};journal=None
 def profile(frame,event,arg):
  if event!='call'or frame.f_code.co_name not in('fit','parse','execute','render','predict','候補機構を学習','実行','照会'):return
  path=pathlib.Path(frame.f_code.co_filename)
  if any(root in path.parents for root in h.RUNTIME_ROOTS):
   name=frame.f_code.co_name;runtime_calls[name]=runtime_calls.get(name,0)+1
 try:
  pins=verify(repo)
  if args.deployment_check_only:
   sys.setprofile(profile);a,repo=load(repo);sys.setprofile(None)
   if runtime_calls:raise AssertionError('loader-only path executed candidate/native behavior')
   if a.PROGRAMS!=(('absorb','erase'),('absorb','preserve'),('continue','erase'),('continue','preserve')):raise AssertionError('fixed four-program domain changed')
   summary.update(runtime_calls=runtime_calls,fit_parse_execute_render_predict_native_calls=0,behavioral_suite_executed=False)
  else:
   f=json.loads(gzip.decompress((F/'fixtures.json.gz').read_bytes()));journal=h.Journal(out/'all-control-returns.events.jsonl.gz')
   for stage in pins['behavioral_stages']:
    mode,case=stage['mode'],stage.get('case');a,repo=load(repo);journal.set_context('public_controls',stage=mode,boundary_case=case)
    if mode!='transport':install_control_return_journal(a,journal)
    if mode=='independent':independent(a,repo,out)
    elif mode=='literal':literal(a,f,out)
    elif mode=='fit_native':summary['native']=fit_native(a,repo,f,out)
    elif mode=='transport':transport(a,f,out)
    elif case=='helper_frontier':helper_frontier(a,f,out)
    else:boundaries(a,f,out,case)
   journal.close();journal=None
   if CHECKS!=pins['expected_behavioral_checks']:raise AssertionError('behavioral assertion list/order changed')
   summary.update(behavioral_suite_executed=True,behavioral_stages_completed=len(pins['behavioral_stages']))
  if verify(repo)!=pins:raise AssertionError('source pins changed')
  summary.update(successful=True,tests_run=len(CHECKS),passed_cases=CHECKS,administrative_check_count=len(PIN_CHECKS),administrative_checks=PIN_CHECKS)
 except BaseException as error:
  sys.setprofile(None);summary.update(successful=False,tests_run=len(CHECKS),passed_cases=CHECKS,administrative_check_count=len(PIN_CHECKS),administrative_checks=PIN_CHECKS,exception=h.safe_exception(error))
  try:summary['raw_exception']=h.capture_raw_exception(error)
  except BaseException as secondary:summary['raw_capture_failure']=h.safe_exception(secondary)
  if journal is not None:
   try:journal.close()
   except BaseException as secondary:summary['secondary_journal_close_failure']=h.safe_exception(secondary)
 save(out,'summary.json',summary);print(h.encoded(summary).decode());return 0 if summary['successful']else 1
if __name__=='__main__':raise SystemExit(main())
