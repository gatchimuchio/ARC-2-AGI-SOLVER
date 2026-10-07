#!/usr/bin/env python3
import sys
sys.dont_write_bytecode=True
import argparse,ast,copy,dataclasses,enum,gzip,importlib,importlib.util,json,pathlib,types,os,errno,tempfile,resource,signal
from unittest.mock import patch
P=pathlib.Path(__file__).resolve().parents[1]
F=P/'検証/合同物体出口資料'
def readpins():return json.loads(gzip.decompress((F/'dependency-pins.json.gz').read_bytes()))
spec=importlib.util.spec_from_file_location('_congruent_ports_evidence_support',F/'evidence_support.py')
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
def load(root):
 repo=pathlib.Path(root).resolve();sys.path.insert(0,str(repo));pkg=types.ModuleType('_fresh036');pkg.__path__=[str(P/'接続/ARC2')];sys.modules[pkg.__name__]=pkg
 a=importlib.import_module(pkg.__name__+'.合同物体出口教材')
 actual={str(pathlib.Path(m.__file__).relative_to(repo))for n,m in sys.modules.items()if n.startswith('接続.ARC2.')and getattr(m,'__file__',None)}
 expected={'接続/ARC2/'+name+'.py'for name in readpins()['import_closure']}
 pincheck('full-transitive-import-closure',actual==expected);return a,repo

def basics(a,teachers,out):
 events=[];audit={};fitted=a.合同物体出口教材(teachers,audit,events.append)
 check('both-C4-C8-literal-models',fitted.モデル群==((4,),(8,)))
 check('all-six-declared-teacher-calls',audit['evaluated_teacher_calls']==6 and audit['symbolic_unexecuted_teacher_calls']==0 and len(audit['model_returns'])==2)
 check('all-teachers-necessity-certified',len(audit['teacher_necessity_certificates'])==3 and all(x['complete']for x in audit['teacher_necessity_certificates']))
 returns=[]
 for pair in teachers:
  result,detail=fitted.候補(pair['input'],{});check('independent-literal-reproduction',result==pair['output']);returns.append({'input':pair['input'],'expected':pair['output'],'output':result,'detail':detail})
 save(out,'positive-fit-and-reproduction.json.gz',{'teachers':teachers,'fit':audit,'events':events,'returns':returns,'state':fitted})
 return fitted,audit

def strict(a,teachers,fitted,out):
 class ListSubclass(list):pass
 class DictSubclass(dict):pass
 class Number(enum.IntEnum):FOUR=4
 g=teachers[0]['input'];models=fitted.モデル群;rows=[]
 invalid=[(),[],[[]],[[True]],[[Number.FOUR]],[[0.0]],[[10]],[[-1]],[[0]*31],[[0]]*31,[[0],[0,1]],ListSubclass([[0]]),[ListSubclass([0])]]
 for v in invalid:
  result,detail=a.predict(v,models);check('strict-grid-'+str(len(rows)),result is None and detail['failure']=='invalid_grid');rows.append({'input':v,'type':type(v).__name__,'result':result,'detail':detail})
 states=[list(models),(models[0],models[0]),((8,),(4,)),((True,),),((Number.FOUR,),),([4],),((4,0),),(4,),None]
 for v in states:
  result,detail=a.predict(g,v);check('strict-state-'+str(len(rows)),result is None and detail['failure']=='invalid_retained_state');rows.append({'state':v,'type':type(v).__name__,'result':result,'detail':detail})
 result,detail=a.predict(g,());check('empty-models',result is None and detail['failure']=='no_retained_models')
 bad=[None,{},ListSubclass(teachers),[teachers[0]],teachers+[dict(teachers[0],extra=1)],[DictSubclass(teachers[0]),teachers[1]],[teachers[0],teachers[0]],[{'input':[[True]],'output':[[1]]},teachers[1]]]
 for v in bad:
  result,detail=a.fit(v);check('strict-teacher-'+str(len(rows)),result==() and detail['failure']in('invalid_teacher_container','invalid_teacher_pair','duplicate_or_conflicting_teacher_input','too_few_distinct_teacher_inputs'));rows.append({'teachers':v,'models':result,'detail':detail})
 for v in (True,4,[4],(True,),(Number.FOUR,)):
  result,detail=a.render(g,v);check('strict-model-'+str(len(rows)),result is None and detail['failure']=='invalid_model');rows.append({'model':v,'result':result,'detail':detail})
 caught=None
 try:fitted.モデル群=()
 except BaseException as e:caught=e
 check('frozen-slotted-state',isinstance(caught,(dataclasses.FrozenInstanceError,AttributeError))and not hasattr(fitted,'__dict__'))
 result,_=a.predict(g,models);result[0][0]=9;again,_=a.predict(g,models);check('returned-output-detached',again==teachers[0]['output'])
 original=a.core.render;calls=[]
 def divergent(grid,program,**kw):
  calls.append(program);out,rec=original(grid,program,**kw)
  if program==8:out=copy.deepcopy(out);out[0][0]=9
  return out,rec
 with patch.object(a.core,'render',divergent):result,detail=a.predict(g,models)
 check('all-retained-disagreement-consensus',result is None and detail['failure']=='retained_models_disagree'and calls==[4,8]);rows.append({'injection':'C8 different cell','calls':calls,'result':result,'detail':detail})
 calls=[]
 def failed(grid,program,**kw):
  calls.append(program)
  return (None,{'complete':True,'status':'HOLD','failure':'synthetic_hold'})if program==4 else original(grid,program,**kw)
 with patch.object(a.core,'render',failed):result,detail=a.predict(g,models)
 check('all-retained-run-after-hold',result is None and detail['failure']=='retained_model_failed'and calls==[4,8]);rows.append({'injection':'C4 complete HOLD','calls':calls,'result':result,'detail':detail})
 save(out,'strict-schema-state-consensus.json.gz',rows)

def proofs(a,teachers,out):
 rows=[];cases=[]
 shape=copy.deepcopy(teachers);shape[0]['output']=[[0]];cases.append(('shape',shape))
 foreground=copy.deepcopy(teachers);foreground[0]['output'][4][3]=9;cases.append(('original-foreground-changed',foreground))
 nonzero=copy.deepcopy(teachers)
 for pair in nonzero:
  for key in('input','output'):pair[key]=[[{1:9,9:1,3:0,0:3}.get(v,v) for v in row]for row in pair[key]]
 nonzero[0]['output'][4][3]=8;cases.append(('unique-nonzero-background-foreground-zero',nonzero))
 for name,pairs in cases:
  events=[]
  with patch.object(a.core,'render',side_effect=AssertionError('proof must not execute renderer')):models,record=a.fit(pairs,events.append)
  check('proof-'+name,models==()and record['proof_complete']and record['logical_domain_complete']and record['evaluated_teacher_calls']==0 and record['symbolic_unexecuted_teacher_calls']==6 and len(record['teacher_necessity_certificates'])==3)
  check('whole-symbolic-domain-'+name,record['symbolic_model_teacher_pairs']==[[m,i]for m in range(2)for i in range(3)])
  rows.append({'name':name,'teachers':pairs,'models':models,'record':record,'events':events})
 # Complete validation precedes even an earlier valid impossibility witness.
 invalid=copy.deepcopy(shape);invalid[-1]['output']=[[True]]
 with patch.object(a,'teacher_necessity_certificate',side_effect=AssertionError('must validate all first')):models,record=a.fit(invalid)
 check('malformed-later-teacher-prevents-proof',record['failure']=='invalid_teacher_pair');rows.append({'name':'all-teachers-first','record':record})
 # Background is inferred only from the original input, even when target mode changes.
 pair={'input':[[0,0,0],[0,1,0],[0,0,0]],'output':[[7,7,7],[7,1,7],[7,7,7]]}
 cert=a.teacher_necessity_certificate(0,pair);check('no-target-derived-background',cert['input_background']==0 and cert['foreground_changes']==[] and cert['violations']==['no_possible_border_singleton_cue'] and cert['orthogonally_isolated_border_foreground']==[]);rows.append({'name':'target-mode-change','pair':pair,'certificate':cert})
 pair={'input':[[0,1],[1,0]],'output':[[7,1],[1,7]]};cert=a.teacher_necessity_certificate(0,pair)
 check('tied-original-background-inapplicable',cert['input_background']is None and cert['foreground_check_applicable']is False and cert['violations']==[]);rows.append({'name':'tie','pair':pair,'certificate':cert})
 pairs=[{'input':[[0,0,0],[0,1,1],[0,0,0]],'output':[[0,0,0],[0,1,1],[0,0,0]]},{'input':[[0,0,0,0],[0,2,2,0],[0,0,0,0]],'output':[[0,0,0,0],[0,2,2,0],[0,0,0,0]]}]
 events=[];models,record=a.fit(pairs,events.append)
 check('no-border-cues-refutes-C4-and-C8',models==()and record['evaluated_teacher_calls']==0 and record['symbolic_unexecuted_teacher_calls']==4 and record['model_returns']==[] and record['proof_complete']and record['logical_domain_complete']and record['symbolic_model_teacher_pairs']==[[m,i]for m in range(2)for i in range(2)] and len(record['teacher_necessity_certificates'])==2 and all(c['complete']and c['border_cue_check_applicable']and c['orthogonally_isolated_border_foreground']==[] and c['violations']==['no_possible_border_singleton_cue']for c in record['teacher_necessity_certificates']))
 rows.append({'name':'no-border-cues-complete-two-program-proof','teachers':pairs,'models':models,'record':record,'events':events})
 original=a.teacher_necessity_certificate;count=0;primary=MemoryError('synthetic second certificate');events=[];caught=None
 def interrupt(index,pair):
  nonlocal count
  count+=1
  if count==2:raise primary
  return original(index,pair)
 try:
  with patch.object(a,'teacher_necessity_certificate',interrupt):a.fit(shape,events.append)
 except BaseException as e:caught=e
 raw=h.capture_raw_exception(caught)
 check('partial-certificates-never-proof',caught is primary and caught.evaluation_diagnostic['semantic_HOLD']is False and not any(e['kind']=='teacher_fit_proven_empty'for e in events)and sum(e['kind']=='teacher_necessity_completed'for e in events)==1)
 rows.append({'name':'later-certificate-resource-after-refutation','exception':caught,'diagnostic':caught.evaluation_diagnostic,'raw':raw,'events':events})
 save(out,'fresh-proof-controls.json.gz',rows)

def exceptions(a,teachers,fitted,audit,out):
 rows=[];g=teachers[0]['input'];models=fitted.モデル群
 def record(name,caught,events=None):rows.append({'name':name,'exception':caught,'diagnostic':getattr(caught,'evaluation_diagnostic',None),'raw':h.capture_raw_exception(caught),'events':events})
 for typ in(MemoryError,RecursionError,TimeoutError,RuntimeError):
  primary=typ('synthetic actual extraction helper failure');events=[];caught=None
  try:
   with patch.object(a.core,'mixed_region_dicts_for_grid',side_effect=primary):a.fit(teachers,events.append)
  except BaseException as e:caught=e
  raw=h.capture_raw_exception(caught)
  check('helper-primary-'+typ.__name__,caught is primary and caught.evaluation_diagnostic['semantic_HOLD']is False and caught.evaluation_diagnostic['resource_failure']==issubclass(typ,(MemoryError,RecursionError,TimeoutError)))
  check('helper-live-core-prefix-'+typ.__name__,any(f['function']=='render'and'rec'in f['locals']and f['locals']['rec']['extraction']['complete']is False for f in raw['frames']))
  record('helper-'+typ.__name__,caught,events)
 # Actual operational cap exposes complete lists plus the active stage, never logical HOLD.
 caught=None
 try:a.render(g,(4,),operation_budget=2)
 except BaseException as e:caught=e
 check('real-operation-cap',isinstance(caught,a.core.BudgetExhausted)and caught.evaluation_diagnostic['resource_failure']and caught.evaluation_diagnostic['prototype_record']['complete']is False)
 record('real-operation-cap',caught)
 # Inject mid-D4 helper after several complete comparisons; preserve partial frontier.
 original=a.core.d4_motif_transform_coord;count=0;primary=MemoryError('mid-D4 failure');caught=None
 def fail_transform(*args,**kw):
  nonlocal count
  count+=1
  if count==13:raise primary
  return original(*args,**kw)
 try:
  with patch.object(a.core,'d4_motif_transform_coord',fail_transform):a.render(g,(4,))
 except BaseException as e:caught=e
 rec=caught.evaluation_diagnostic['prototype_record'];check('partial-D4-prefix-retained',caught is primary and len(rec['body_pairs'][0]['comparisons'])>=4 and any(x['complete']for x in rec['body_pairs'][0]['comparisons'])and not rec['complete']);record('mid-D4-prefix',caught)
 # Fourth declared render fails: first model complete, next model active.
 original=a.core.render;count=0;primary=MemoryError('fifth declared render');caught=None;events=[]
 def later(*args,**kw):
  nonlocal count
  count+=1
  if count==5:raise primary
  return original(*args,**kw)
 try:
  with patch.object(a.core,'render',later):a.fit(teachers,events.append)
 except BaseException as e:caught=e
 d=caught.evaluation_diagnostic;check('complete-fit-prefix-and-active',caught is primary and len(d['completed_model_returns'])==1 and len(d['completed_teacher_returns'])==1 and d['active_call']['model_index']==1 and d['active_call']['teacher_index']==1);record('fit-prefix',caught,events)
 # Failure after real return but before wrapper row leaves lossless pending output/detail.
 for point,invoke in [('render_row',lambda:a.render(g,(4,))),('teacher_row',lambda:a.fit(teachers))]:
  primary=MemoryError('row construction '+point);caught=None
  try:
   with patch.object(a,point,side_effect=primary):invoke()
  except BaseException as e:caught=e
  d=caught.evaluation_diagnostic;check('pending-raw-'+point,caught is primary and d['raw_return_pending']and d['pending_output']==teachers[0]['output']and d['pending_detail']['complete']);record(point,caught)
 primary=OSError(errno.ENOSPC,'observer synthetic disk full');caught=None
 def observer(event):
  if event['kind']=='retained_model_return':raise primary
 try:a.predict(g,models,observer)
 except BaseException as e:caught=e
 check('prediction-prefix-observer-failure',caught is primary and len(caught.evaluation_diagnostic['completed_model_returns'])==1);record('observer-prediction',caught)
 primary=MemoryError('primary helper');secondary=RuntimeError('whole reporter');caught=None
 try:
  with patch.object(a.core,'mixed_region_dicts_for_grid',side_effect=primary),patch.object(a,'report_exception',side_effect=secondary):a.fit(teachers)
 except BaseException as e:caught=e
 raw=h.capture_raw_exception(caught)
 def contains(node,kind):return bool(node)and(node['primary_exception']['type']==kind or contains(node.get('context'),kind))
 check('whole-reporter-retains-original',caught is primary and caught.evaluation_reporting_failure is secondary and contains(raw,'MemoryError')and raw['reporting_failure']['type']=='RuntimeError');record('whole-reporter-failure',caught)
 primary=MemoryError('primary helper diagnostic');secondary=RuntimeError('diagnostic construction');caught=None
 try:
  with patch.object(a.core,'mixed_region_dicts_for_grid',side_effect=primary),patch.object(a,'diagnostic_record',side_effect=secondary):a.fit(teachers)
 except BaseException as e:caught=e
 check('diagnostic-failure-retains-primary',caught is primary and caught.evaluation_diagnostic['diagnostic_construction_failure']=='RuntimeError');record('diagnostic-failure',caught)
 # Metadata-only state entry fault: explicitly replay the already verified immutable fit.
 primary=MemoryError('audit deepcopy failure');caught=None;fit_replays=[]
 def replay(*args,**kw):fit_replays.append(True);return models,copy.deepcopy(audit)
 try:
  with patch.object(a,'fit',replay),patch.object(a,'deepcopy',side_effect=primary):a.合同物体出口教材(teachers,{})
 except BaseException as e:caught=e
 check('saved-fit-state-entry-fault',caught is primary and caught.evaluation_diagnostic['completed_models']==models and caught.evaluation_diagnostic['completed_fit']==audit and len(fit_replays)==1);record('saved-fit-metadata-fault-no-refitting',caught)
 # Fresh protected reporter tests cover every reporting call boundary.
 for observed in(False,True):
  for caller in('teacher_necessities','render','fit','predict','state_entry'):
   primary=MemoryError('primary '+caller);secondary=RuntimeError('reporter '+caller);caught=None;events=[]
   observer=events.append if observed else None
   if caller=='teacher_necessities':
    original_certificate=a.teacher_necessity_certificate
    def fault_certificate(index,pair):
     if index==1:raise primary
     return original_certificate(index,pair)
    patches=[patch.object(a,'teacher_necessity_certificate',fault_certificate)]
    invoke=lambda:a.teacher_necessities(teachers,observer,a.Budget())
   elif caller=='render':
    patches=[patch.object(a,'render_row',side_effect=primary)];invoke=lambda:a.render(g,(4,),observer)
   elif caller=='fit':
    patches=[patch.object(a,'teacher_row',side_effect=primary)];invoke=lambda:a.fit(teachers,observer)
   elif caller=='predict':
    original_render=a.render;predict_count=[0]
    def fail_second(*args,**kwargs):
     predict_count[0]+=1
     if predict_count[0]==2:raise primary
     return original_render(*args,**kwargs)
    patches=[patch.object(a,'render',fail_second)];invoke=lambda:a.predict(g,models,observer)
   else:
    patches=[patch.object(a,'fit',return_value=(models,copy.deepcopy(audit))),patch.object(a,'deepcopy',side_effect=primary)];invoke=lambda:a.合同物体出口教材(teachers,{},observer)
   from contextlib import ExitStack
   try:
    with ExitStack() as stack:
     for p in patches:stack.enter_context(p)
     stack.enter_context(patch.object(a,'report_exception',side_effect=secondary));invoke()
   except BaseException as e:caught=e
   raw=h.capture_raw_exception(caught);check('protected-whole-reporter:'+caller+':'+str(observed),caught is primary and caught.evaluation_reporting_failure is secondary)
   loc=[f['locals']for f in raw['frames']]
   if caller=='teacher_necessities':check('reporter-certificate-prefix:'+str(observed),any(len(v.get('records',[]))==1 for v in loc))
   if caller in('render','fit'):check('reporter-pending-return:'+caller+':'+str(observed),any(v.get('raw_pending')is True and v.get('output')==teachers[0]['output']and v.get('detail',{}).get('complete')is True for v in loc))
   if caller=='predict':check('reporter-prediction-prefix:'+str(observed),any(len(v.get('rows',[]))==1 for v in loc))
   if caller=='state_entry':check('reporter-saved-state-prefix:'+str(observed),any(v.get('models')==h.serial(models)and v.get('record')==h.serial(audit)for v in loc))
   record('protected-'+caller+'-'+str(observed),caught,events)
 # Fail while evaluating reporting keyword metadata, before report_exception can run.
 class AllocationFaultBudget(a.Budget):
  metadata_failure=False
  def __getattribute__(self,name):
   if name=='exception_prefix' and object.__getattribute__(self,'metadata_failure'):raise secondary
   return super().__getattribute__(name)
 for observed in(False,True):
  control=AllocationFaultBudget();primary=RuntimeError('primary before metadata allocation');secondary=MemoryError('metadata argument construction');caught=None;events=[]
  def row_failure(*unused):control.metadata_failure=True;raise primary
  try:
   with patch.object(a,'render_row',row_failure):a.render(g,(4,),events.append if observed else None,control)
  except BaseException as e:caught=e
  raw=h.capture_raw_exception(caught);check('reporting-argument-allocation:'+str(observed),caught is primary and caught.evaluation_reporting_failure is secondary and any(f['locals'].get('raw_pending')is True and f['locals'].get('output')==teachers[0]['output']for f in raw['frames']))
  record('reporting-argument-allocation-'+str(observed),caught,events)
 save(out,'actual-exception-prefix-controls.json.gz',rows)

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
   boundary='ARC合同物体出口';record=helpers['候補機構を学習'](machine,{'train':teachers},(),boundary,candidate)
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

def harness_controls(a,teachers,out):
 rows=[]
 # Reuse the immutable saved positive state to exercise storage metadata; no renderer call.
 saved=out/'positive-fit-and-reproduction.json.gz';raw=saved.read_bytes();state=json.loads(gzip.decompress(raw));digest=h.sha(saved)
 check('saved-state-complete-return-domain',len(state['fit']['model_returns'])==2 and all(len(r['returns'])==3 for r in state['fit']['model_returns'])and len(state['returns'])==3)
 event={'kind':'model_teacher_return','model_index':0,'teacher_index':0,**state['fit']['model_returns'][0]['returns'][0]}
 j=h.Journal(out/'storage-fault.events.jsonl.gz');j.set_context('fit');j({'kind':'model_teacher_start','model_index':0,'teacher_index':0});primary=OSError(errno.ENOSPC,'synthetic saved-return journal write');caught=None
 try:
  with patch.object(h.gzip,'compress',side_effect=primary):j(event)
 except BaseException as e:caught=e
 result={'completed':True,'semantic_HOLD':True,'all_exact':True,'disposition':'logical_HOLD'};h.close_journal(j,result)
 check('saved-return-pending-after-storage-fault',caught is primary and not result['completed']and not result['semantic_HOLD']and result['pending_event_suffix'][0]['output']==teachers[0]['output']and result['pending_event_suffix'][0]['record']==state['fit']['model_returns'][0]['returns'][0]['record'])
 save(out,'storage-fault-lossless-pending.json.gz',{'saved_source_sha256':digest,'fitting_executed':False,'result':result});rows.append({'name':'saved-return-journal-storage','saved_source_sha256':digest,'fitting_executed':False})
 # A valid complete record deliberately receives an unfulfilled final parent CPU budget.
 value={'completed':True,'semantic_HOLD':True,'all_exact':True,'resource_failure':False,'disposition':'logical_HOLD'}
 h.enforce_whole_child_budget(value,10.001,1.0);check('whole-child-CPU-overrides-completion',not value['completed']and not value['semantic_HOLD']and value['resource_failure']);rows.append({'name':'saved-completion-CPU-accounting','row':value,'actual_CPU_consumption_claimed':False})
 value={'completed':True,'semantic_HOLD':False,'all_exact':True,'resource_failure':False,'disposition':'FIT'}
 h.enforce_whole_child_budget(value,1.0,60.001);check('whole-child-wall-overrides-completion',not value['completed']and value['resource_failure']);rows.append({'name':'saved-completion-wall-accounting','row':value,'actual_wall_consumption_claimed':False})
 # Event prefix damage is detected without interpreting the truncated suffix.
 path=out/'truncated.events.jsonl.gz';data=(out/'storage-fault.events.jsonl.gz').read_bytes();path.write_bytes(data+gzip.compress(b'{"kind":"incomplete"}\n',mtime=0)[:12]);prefix=h.read_journal(path,3)
 check('truncated-event-complete-prefix',prefix['complete_event_prefix_count']==1 and prefix['incomplete_compressed_suffix_bytes']==12 and prefix['incomplete_model_teacher_pairs']['count']==1);rows.append({'name':'truncated-event-prefix','receipt':prefix})
 bad=out/'malformed.record.json.gz';bad.write_bytes(gzip.compress(b'[]',mtime=0));receipt=h.read_completion(bad,False,0);check('malformed-completion-no-HOLD',not receipt['completed']and not receipt['semantic_HOLD']);rows.append({'name':'malformed-record','receipt':receipt})
 # Replay an already saved return through the exact control boundary wrapper.
 # Failure after _original returned cannot discard raw_pending or invoke candidate fitting.
 for error_type in(MemoryError,OSError):
  primary=error_type('saved boundary-return metadata failure');caught=None;events=[];replays=[]
  saved_return=(tuple(tuple(m)for m in state['state']['モデル群']),copy.deepcopy(state['fit']))
  def replay_only(*unused,**kw):replays.append(True);return saved_return
  def prohibited(*unused,**kw):raise AssertionError('candidate execution forbidden in saved metadata replay')
  dummy=types.SimpleNamespace(core=types.SimpleNamespace(render=prohibited),fit=replay_only,render=prohibited,predict=prohibited,teacher_necessity_certificate=prohibited,teacher_necessities=prohibited)
  def fail_boundary(event):
   events.append(event)
   if event['kind']=='control_boundary_return':raise primary
  install_control_return_journal(dummy,fail_boundary)
  try:dummy.fit(teachers)
  except BaseException as error:caught=error
  raw_failure=h.capture_raw_exception(caught)
  check('saved-boundary-raw-pending:'+error_type.__name__,caught is primary and len(replays)==1 and any(f['locals'].get('_name')=='fit'and f['locals'].get('raw_pending')==h.serial(saved_return)for f in raw_failure['frames']))
  rows.append({'name':'saved-boundary-'+error_type.__name__,'source_sha256':digest,'candidate_fits':0,'saved_return_replays':1,'error':caught,'raw':raw_failure,'events':events})
 save(out,'harness-saved-state-fault-controls.json.gz',rows)

def geometry(a,root,out):
 packet=json.loads(gzip.decompress((F/'geometry-extra.json.gz').read_bytes()));rows=[]
 def select(value,path):
  parts=path if type(path)is list else path.split('.')
  values=[value]
  for part in parts:
   new=[]
   for v in values:
    if part=='*':new.extend(v.values()if isinstance(v,dict)else v)
    elif isinstance(v,(list,tuple)):new.append(v[int(part)])
    else:new.append(v[part])
   values=new
  return values
 for case in packet['render_cases']:
  for program,expected in case['expectations'].items():
   output,record=a.render(case['input'],(int(program),));check('geometry-output:'+case['id']+':'+program,output==expected['output']and record['complete']==expected.get('complete',True)and record['status']==expected.get('status','OK'if output is not None else'HOLD'))
   codes=[r['failure']for r in record['failures']]
   check('geometry-failures:'+case['id']+':'+program,all(f in codes for f in expected.get('required_failures',[])))
   for p in expected.get('trace_predicates',[]):
    vals=select(record,p['path']);check('geometry-trace:'+case['id']+':'+program+':'+str(p),bool(vals)and all(('equals'not in p or v==p['equals'])and('length'not in p or len(v)==p['length'])and('contains'not in p or p['contains']in v)for v in vals))
   rows.append({'id':case['id'],'program':program,'input':case['input'],'expected':expected,'output':output,'record':record})
 for case in packet.get('teacher_necessity_cases',[]):
  models,record=a.fit(case['teachers']);check('literal-teacher-fit:'+case['id'],h.serial(models)==case['expected_models']and all(h.serial(record[k])==v for k,v in case['expected_fit'].items()))
  if 'expected_certificate_violations'in case:check('literal-certificate:'+case['id'],[r['violations']for r in record['teacher_necessity_certificates']]==case['expected_certificate_violations'])
  rows.append({'id':case['id'],'teachers':case['teachers'],'models':models,'record':record,'expected':case})
 save(out,'literal-extra-geometry.json.gz',rows)

def install_control_return_journal(a,journal):
    # Durable every-return transport for controls, including a late failed assertion/kill.
    h.install_call_observers(a,journal)
    for name in('fit','render','predict','teacher_necessity_certificate','teacher_necessities'):
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
 base=args.output_base.resolve()if args.output_base else pathlib.Path(tempfile.gettempdir());base.mkdir(parents=True,exist_ok=True);out=pathlib.Path(tempfile.mkdtemp(prefix='arc2-candidate036-',dir=base))
 h.RUNTIME_ROOTS=(P/'接続/ARC2',repo/'接続/ARC2',repo/'HDS/学習系統/v0.4.2/hds学習系統');h.CONTROL_SCRIPT=pathlib.Path(__file__).resolve()
 summary={'artifact_directory':str(out),'repository_root':str(repo),'deployment_root':str(P),'explicit_repository_root':args.repository_root is not None,'deployed_default_root':deployed,'deployment_check_only':args.deployment_check_only,'full120_runs':0,'public_query_runs':0}
 runtime_calls={};journal=None
 def profile(frame,event,arg):
  if event!='call' or frame.f_code.co_name not in ('fit','render','predict','候補機構を学習','実行','照会'):return
  path=pathlib.Path(frame.f_code.co_filename)
  if any(r in path.parents for r in h.RUNTIME_ROOTS):
   name=frame.f_code.co_name;runtime_calls[name]=runtime_calls.get(name,0)+1
 try:
  pins=verify(repo)
  if args.deployment_check_only:sys.setprofile(profile)
  a,repo=load(repo);teachers=json.loads(gzip.decompress((F/'fixtures.json.gz').read_bytes()))['teachers']
  if args.deployment_check_only:
   sys.setprofile(None)
   if runtime_calls:raise AssertionError('loader-only path executed candidate/native behavior')
   if a.PROGRAMS!=((4,),(8,)):raise AssertionError('fixed C4/C8 domain changed')
   summary.update(runtime_calls=runtime_calls,fit_render_predict_native_calls=0,behavioral_suite_executed=False)
  else:
   journal=h.Journal(out/'all-control-returns.events.jsonl.gz');journal.set_context('focused_controls');install_control_return_journal(a,journal)
   fitted,audit=basics(a,teachers,out);geometry(a,repo,out);strict(a,teachers,fitted,out);proofs(a,teachers,out)
   exceptions(a,teachers,fitted,audit,out);summary['native']=native(a,repo,fitted,teachers,out);harness_controls(a,teachers,out)
   journal.close();journal=None
   if CHECKS!=pins['expected_behavioral_checks']:raise AssertionError('behavioral assertion list/order changed')
   summary.update(behavioral_suite_executed=True,retained_models=fitted.モデル群)
  if verify(repo)!=pins:raise AssertionError('source pins changed')
  summary.update(successful=True,tests_run=len(CHECKS),passed_cases=CHECKS,administrative_check_count=len(PIN_CHECKS),administrative_checks=PIN_CHECKS)
 except BaseException as error:
  sys.setprofile(None)
  summary.update(successful=False,tests_run=len(CHECKS),passed_cases=CHECKS,exception=h.safe_exception(error),raw_exception=h.capture_raw_exception(error))
  if journal is not None:
   try:journal.close()
   except BaseException as secondary:summary['secondary_journal_close_failure']=h.safe_exception(secondary)
 save(out,'summary.json',summary);print(h.encoded(summary).decode());return 0 if summary['successful']else 1
if __name__=='__main__':raise SystemExit(main())
