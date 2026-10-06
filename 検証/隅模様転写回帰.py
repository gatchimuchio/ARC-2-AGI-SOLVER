#!/usr/bin/env python3
"""Fresh031 controls: literal expectations, strict inputs, all-program state, proof freshness, exceptions and native supports."""
import sys
sys.dont_write_bytecode=True
import argparse,ast,copy,dataclasses,enum,gzip,importlib,json,pathlib,types,tempfile
from unittest.mock import patch
P=pathlib.Path(__file__).resolve().parents[1]
F=P/'検証/隅模様転写資料'
sys.path.insert(0,str(F))
import evidence_support as h
def readpins():return json.loads(gzip.decompress((F/'dependency-pins.json.gz').read_bytes()))
def readfixture(name):return json.loads(gzip.decompress((F/(name+'.gz')).read_bytes()))
ADMIN_CHECKS=[]
def administrative(name,condition):
 if not condition:raise AssertionError(name)
 ADMIN_CHECKS.append(name)
def verify(repo):
 pins=readpins()
 for name,digest in pins['payload_pins'].items():administrative('payload-pin:'+name,h.sha(P/name)==digest)
 for name,digest in pins['base_source_pins'].items():administrative('base-pin:'+name,h.sha(repo/name)==digest)
 bridge=repo/'接続/ARC2/HDS接続.py'
 actual={n.name:ast.dump(n,include_attributes=False)for n in ast.parse(bridge.read_bytes()).body if isinstance(n,ast.FunctionDef)and n.name in pins['native_bridge_ast']}
 administrative('three-native-ASTs',actual==pins['native_bridge_ast'])
 return pins
CHECKS=[]
def check(name,condition=True):
 if not condition:raise AssertionError(name)
 CHECKS.append(name)
def save(out,name,value):h.write(out/name,value)
def load(root):
 repo=pathlib.Path(root).resolve();sys.path.insert(0,str(repo));pkg=types.ModuleType('_fresh031');pkg.__path__=[str(P/'接続/ARC2')];sys.modules[pkg.__name__]=pkg
 a=importlib.import_module(pkg.__name__+'.隅模様転写教材')
 actual={str(pathlib.Path(m.__file__).relative_to(repo))for n,m in sys.modules.items()if n.startswith('接続.ARC2.')and getattr(m,'__file__',None)}
 expected={'接続/ARC2/'+name+'.py'for name in readpins()['import_closure']}
 check('all-ten-transitive-imports-bound',actual==expected);return a,repo

def basics(a,teachers,expected,out):
 events=[];audit={};fitted=a.隅模様転写教材(teachers,audit,events.append)
 check('four-independent-literal-models',fitted.モデル群==tuple(expected))
 check('all-twelve-declared-teacher-calls',audit['evaluated_teacher_returns']==12 and audit['evaluated_programs']==4 and audit['actual_declared_fit_renderer_calls']==12)
 check('fresh-three-probes-fallback',audit['actual_common_prefix_executions']==3 and len(audit['necessity']['certificates'])==3 and audit['unexecuted_calls']==[])
 returns=[]
 for pair in teachers:
  result,detail=fitted.候補(pair['input'],{});check('literal-teacher-reproduction',result==pair['output']);returns.append({'input':pair['input'],'expected':pair['output'],'output':result,'detail':detail})
 save(out,'positive-fit-and-reproduction.json.gz',{'teachers':teachers,'fit':audit,'events':events,'returns':returns,'state':fitted})
 return fitted

def strict(a,teachers,fitted,out):
 class ListSubclass(list):pass
 class DictSubclass(dict):pass
 class StringSubclass(str):pass
 class Number(enum.IntEnum):ONE=1
 rows=[];g=teachers[0]['input'];m=fitted.モデル群
 invalid=[(),[],[[]],[[True]],[[Number.ONE]],[[0.0]],[[10]],[[-1]],[[0]*31],[[0]]*31,[[0],[0,1]],ListSubclass([[0]]),[ListSubclass([0])]]
 for value in invalid:
  result,detail=a.predict(value,m);check('invalid-grid-'+str(len(rows)),result is None and detail['failure']=='invalid_arc_grid');rows.append({'input':value,'result':result,'detail':detail})
 states=[list(m),(m[0],m[0]),('unknown',),(StringSubclass(m[0]),),(True,),(0,),None]
 for value in states:
  result,detail=a.predict(g,value);check('invalid-state-'+str(len(rows)),result is None and detail['failure']=='invalid_retained_state');rows.append({'state_type':type(value).__name__,'state':[{'type':type(v).__name__,'value':str(v)if isinstance(v,str)else v}for v in value]if isinstance(value,(list,tuple))else value,'result':result,'detail':detail})
 result,detail=a.predict(g,());check('empty-retained-hold',result is None and detail['failure']=='no_fitted_models')
 badteachers=[None,{},ListSubclass(teachers),[teachers[0]],teachers+[dict(teachers[0],extra=1)],[DictSubclass(teachers[0]),teachers[1]],[teachers[0],teachers[0]],[{'input':[[True]],'output':[[1]]},teachers[1]]]
 for value in badteachers:
  result,detail=a.fit(value);check('invalid-teachers-'+str(len(rows)),result==() and detail['failure']in ('invalid_teacher_container','invalid_teacher_pair','too_few_distinct_teacher_inputs'));rows.append({'teachers':value,'models':result,'detail':detail})
 caught=None
 try:fitted.モデル群=()
 except BaseException as error:caught=error
 check('frozen-slots-state',isinstance(caught,(dataclasses.FrozenInstanceError,AttributeError)) and not hasattr(fitted,'__dict__'))
 # Original teacher and prediction buffers are detached from immutable model state.
 first,_=a.predict(g,m);first[0][0]=9;again,_=a.predict(g,m);check('detached-return-grid',again==teachers[0]['output'])
 original=a.base.render;calls=[]
 def divergent(grid,program,observer=None):
  output,rec=original(grid,program,observer);calls.append(program)
  if program==m[-1]:output=copy.deepcopy(output);output[0][0]=9
  return output,rec
 with patch.object(a.base,'render',divergent):result,detail=a.predict(g,m)
 check('all-retained-conflict-consensus',result is None and detail['failure']=='retained_program_conflict' and tuple(calls)==m)
 rows.append({'injection':'last model changes one cell','calls':calls,'result':result,'detail':detail})
 calls=[]
 def failed(grid,program,observer=None):
  calls.append(program)
  if program==m[0]:return None,{'failure':'synthetic_hold','status':'HOLD'}
  return original(grid,program,observer)
 with patch.object(a.base,'render',failed):result,detail=a.predict(g,m)
 check('all-retained-run-after-hold',result is None and detail['failure']=='retained_program_failed'and tuple(calls)==m)
 rows.append({'injection':'first model semantic hold','calls':calls,'result':result,'detail':detail})
 save(out,'strict-schema-state-consensus.json.gz',rows)

def proofs(a,teachers,out):
 rows=[]
 # Fresh target-shape, color, no-change, changed-background and unownable-C8 witnesses.
 cases=[]
 shape=copy.deepcopy(teachers);shape[0]['output']=[[0]];cases.append(('shape',shape))
 novel=copy.deepcopy(teachers);novel[0]['output'][0][0]=9;cases.append(('new-color',novel))
 identity=copy.deepcopy(teachers);identity[0]['output']=copy.deepcopy(identity[0]['input']);cases.append(('identity',identity))
 for name,pairs in cases:
  events=[];models,record=a.fit(pairs,events.append)
  check('proof-'+name,models==() and record['necessity']['fit_impossibility_proved'] and len(record['necessity']['certificates'])==len(pairs) and record['actual_renderer_executions_in_fit']==0 and len(record['unexecuted_calls'])==4*len(pairs))
  rows.append({'name':name,'teachers':pairs,'models':models,'record':record,'events':events})
 # A one-foreground-pixel grid passes generic necessary invariants but has no
 # frame role. Its completed first-program structural rejection refutes all4.
 pairs=[{'input':[[0,0,0],[0,1,0],[0,0,0]],'output':[[0,0,0],[0,1,1],[0,0,0]]},{'input':[[0,0,0,0],[0,2,0,0],[0,0,0,0]],'output':[[0,0,0,0],[0,2,2,0],[0,0,0,0]]}]
 events=[];models,record=a.fit(pairs,events.append)
 check('fresh-complete-structural-proof',models==()and record['failure']=='fit_domain_proven_empty_by_common_structural_rejection'and record['actual_common_prefix_executions']==1 and record['necessity']['common_prefix_returns'][0]['complete']is True and len(record['unexecuted_calls'])==8)
 rows.append({'name':'generic-structural','teachers':pairs,'models':models,'record':record,'events':events})
 # Completion of an earlier certificate cannot convert a later interrupted
 # certificate/probe into a completed semantic impossibility proof.
 original=a.necessity_certificate;count=0;primary=MemoryError('synthetic second certificate interruption');events=[];caught=None
 def interrupt(pair):
  nonlocal count
  count+=1
  if count==2:raise primary
  return original(pair)
 try:
  with patch.object(a,'necessity_certificate',interrupt):a.fit(teachers,events.append)
 except BaseException as error:caught=error
 d=caught.evaluation_diagnostic
 check('interrupted-certificate-unknown',caught is primary and d['resource_failure']and d['semantic_HOLD']is False and len(d['completed_teacher_certificates'])==1 and d['active_call']['teacher_index']==1 and not any(e['kind']=='teacher_fit_proven_empty'for e in events))
 rows.append({'name':'interrupted-certificate','exception':caught,'diagnostic':d,'events':events,'raw':h.capture_raw_exception(caught)})
 primary=TimeoutError('synthetic interrupted generic probe');events=[];caught=None
 try:
  with patch.object(a.base,'render',side_effect=primary):a.fit(teachers,events.append)
 except BaseException as error:caught=error
 check('interrupted-probe-unknown',caught is primary and caught.evaluation_diagnostic['active_call']['phase']=='common_prefix_probe'and len(caught.evaluation_diagnostic['completed_teacher_certificates'])==3 and not any(e['kind']=='teacher_fit_proven_empty'for e in events))
 rows.append({'name':'interrupted-probe','exception':caught,'diagnostic':caught.evaluation_diagnostic,'events':events,'raw':h.capture_raw_exception(caught)})
 save(out,'fresh-proof-controls.json.gz',rows)

def exceptions(a,teachers,fitted,out):
 rows=[];g=teachers[0]['input'];m=fitted.モデル群
 for typ in (MemoryError,RecursionError,TimeoutError,RuntimeError):
  primary=typ('synthetic helper interruption');events=[];caught=None
  try:
   with patch.object(a.core,'perimeter_cells',side_effect=primary):a.fit(teachers,events.append)
  except BaseException as error:caught=error
  raw=h.capture_raw_exception(caught)
  check('actual-helper-exception-'+typ.__name__,caught is primary and caught.evaluation_diagnostic['semantic_HOLD']is False and caught.evaluation_diagnostic['resource_failure']==issubclass(typ,(MemoryError,RecursionError,TimeoutError)))
  check('actual-core-traceback-prefix-'+typ.__name__,any(f['function']=='frame_roles'and 'rec'in f['locals']and 'candidates'in f['locals']for f in raw['frames']))
  rows.append({'name':typ.__name__,'exception':caught,'diagnostic':caught.evaluation_diagnostic,'events':events,'raw':raw})
 # Exercise the actual immutable wrapper's promotion of the exact string
 # emitted by the frozen100000-node branch. Traversal count is not fabricated.
 events=[];caught=None;raw_return=(None,{'model':m[0],'frame_roles':[{'rectangles':[{'bbox':(0,0,4,4)}]}],'output':None,'status':'HOLD','failure':'exact_cover_resource_limit'})
 try:
  with patch.object(a.core,'render',return_value=raw_return):a.base.render(g,m[0],events.append)
 except BaseException as error:caught=error
 check('cap-return-promoted-resource',isinstance(caught,a.base.ExactCoverResourceLimit)and caught.evaluation_diagnostic['resource_failure']and caught.evaluation_diagnostic['semantic_HOLD']is False and caught.evaluation_diagnostic['completed_program_return']['record']==raw_return[1])
 rows.append({'name':'synthetic-exact-cap-return','injection':'frozen core raw cap return; does not claim100001 traversal nodes','exception':caught,'diagnostic':caught.evaluation_diagnostic,'events':events})
 # Distinct complete declared prefix and active call when a later real helper fails.
 original=a.core.render;count=0;primary=MemoryError('synthetic fifth declared call');events=[];caught=None
 def interrupt(grid,program):
  nonlocal count
  count+=1
  if count==5:raise primary
  return original(grid,program)
 try:
  with patch.object(a.core,'render',interrupt):a.base.fit(teachers,events.append)
 except BaseException as error:caught=error
 d=caught.evaluation_diagnostic
 check('fit-prefix-completed-and-active',caught is primary and len(d['completed_program_returns'])==1 and len(d['completed_teacher_returns'])==1 and d['active_call']['teacher_index']==1)
 rows.append({'name':'declared-fit-prefix','exception':caught,'diagnostic':d,'events':events,'raw':h.capture_raw_exception(caught)})
 # Observer failure is a real thrown object; reporter failure must not replace it.
 primary=OSError('synthetic observer storage failure');caught=None
 def observer(event):raise primary
 try:a.fit(teachers,observer)
 except BaseException as error:caught=error
 check('observer-primary-preserved',caught is primary and caught.evaluation_diagnostic['semantic_HOLD']is False)
 rows.append({'name':'observer-failure','exception':caught,'diagnostic':caught.evaluation_diagnostic,'raw':h.capture_raw_exception(caught)})
 # The exact recovered reporter itself may fail. Harness context-chain capture
 # must retain both original resource error and reporting error, not claim HOLD.
 primary=MemoryError('synthetic primary before whole reporter failure');secondary=RuntimeError('synthetic whole reporter failure');caught=None
 try:
  with patch.object(a.core,'perimeter_cells',side_effect=primary),patch.object(a.base,'report_exception',side_effect=secondary):a.fit(teachers,None)
 except BaseException as error:caught=error
 raw=h.capture_raw_exception(caught)
 def contains(node,kind):return bool(node)and(node['primary_exception']['type']==kind or contains(node.get('context'),kind))
 check('whole-reporter-context-retains-primary',contains(raw,'MemoryError')and contains(raw,'RuntimeError'))
 rows.append({'name':'whole-reporter-failure','caught':caught,'raw':raw,'semantic_HOLD':False})
 save(out,'actual-exception-prefix-controls.json.gz',rows)

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
   boundary='ARC隅模様転写';record=helpers['候補機構を学習'](machine,{'train':teachers},(),boundary,candidate)
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

def geometry(a,root,out):
 packet=readfixture('geometry-extra.json');rows=[]
 for case in packet['cases']:
  for program,expected in case['expectations'].items():
   output,record=a.render(case['input'],program)
   check('geometry:'+case['id']+':'+program,output==expected['output']and all(record.get(k)==v for k,v in expected.items()if k!='output'))
   if case['id']=='active_owner_paints_inactive_corner_without_reactivation'and output is not None:
    check('inactive5-painted-without-reactivation',5 in record['inactive_corners'] and {p[3]for p in record['proposals']}=={0,4} and any(p[:2]==[2,20]for p in record['proposals']))
   rows.append({'id':case['id'],'program':program,'input':case['input'],'expected':expected,'output':output,'record':record})
 save(out,'literal-extra-geometry.json.gz',rows)


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repository-root',type=pathlib.Path);ap.add_argument('--output-base',type=pathlib.Path);ap.add_argument('--loader-only',action='store_true');args=ap.parse_args()
 root=args.repository_root.resolve()if args.repository_root else(P if (P/'HDS/学習系統/v0.4.2').is_dir()else P.parent/'source-evidence/repository')
 base=args.output_base.resolve()if args.output_base else pathlib.Path(tempfile.gettempdir())
 base.mkdir(parents=True,exist_ok=True);out=pathlib.Path(tempfile.mkdtemp(prefix='candidate031-regression-',dir=base))
 pins=verify(root);a,repo=load(root);fixture=readfixture('fixtures.json');teachers=fixture['teachers']
 if args.loader_only:
  summary={'passed':True,'loader_only':True,'candidate_calls':0,'native_calls':0,'behavioral_checks_executed':0,'administrative_check_count':len(ADMIN_CHECKS),'checks':ADMIN_CHECKS,'import_closure_verified':True,'runtime_hashes':{str(p.relative_to(P)):h.sha(p)for p in(P/'接続/ARC2').glob('*.py')},'repository_root':str(root),'payload_root':str(P),'artifact_directory':str(out)}
  save(out,'summary.json',summary);print(h.encoded(summary).decode());return
 fitted=basics(a,teachers,fixture['expected_models'],out)
 geometry(a,root,out);strict(a,teachers,fitted,out);proofs(a,teachers,out);exceptions(a,teachers,fitted,out);native_rows=native(a,repo,fitted,teachers,out)
 check('all-pins-still-match',verify(root)==pins)
 administrative_labels={'all-ten-transitive-imports-bound','native-three-function-ASTs','all-pins-still-match'}
 behavior=[name for name in CHECKS if name not in administrative_labels]
 summary={'schema':'fresh031-production-regression-v1','passed':True,'checks':behavior,'behavioral_check_count':len(behavior),'administrative_checks':ADMIN_CHECKS+[name for name in CHECKS if name in administrative_labels],'administrative_check_count':len(ADMIN_CHECKS)+sum(name in administrative_labels for name in CHECKS),'optimized':sys.flags.optimize,'teacher_count':len(teachers),'retained_models':fitted.モデル群,'native':native_rows,'query_calls':0,'historical_raw_restored':False,'artifact_directory':str(out)}
 save(out,'summary.json',summary);print(h.encoded({k:v for k,v in summary.items()if k not in ('checks','administrative_checks')}).decode())
if __name__=='__main__':main()
