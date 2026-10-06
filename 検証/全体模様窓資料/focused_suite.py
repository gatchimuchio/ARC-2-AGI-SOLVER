"""Relocated focused cases; original behavioral functions/assertions retained."""
import sys
sys.dont_write_bytecode=True
import argparse,ast,copy,dataclasses,gzip,hashlib,importlib,json,pathlib,resource,signal,time
from unittest.mock import patch
import evidence_support as h
import necessity_controls as c
F=pathlib.Path(__file__).resolve().parent
CHECKS=[]
def load(root):
    repo=pathlib.Path(root).resolve();sys.path.insert(0,str(repo));sys.path.insert(0,str(h.S))
    return importlib.import_module('接続.ARC2.全体模様窓必要条件教材'),repo
def read_pinned(path,pin):
    h.pincheck('reference-byte-pin',h.sha(path)==pin)
    with gzip.open(path,'rt')as stream:return json.load(stream)
def check(name,value=True):
 if not value:raise AssertionError(name)
 CHECKS.append(name)

def save(out,name,value):h.write(out/name,value)

def encoder(value):return h.encoded(value).decode()

def native(a,repo,fitted,teachers,out):
 pins=h.readpins();bridge=repo/'接続/ARC2/HDS接続.py'
 nodes=[n for n in ast.parse(bridge.read_bytes()).body if isinstance(n,ast.FunctionDef)and n.name in pins['native_bridge_ast']]
 h.pincheck('exact-native-three-function-ASTs',{n.name:ast.dump(n,include_attributes=False)for n in nodes}==pins['native_bridge_ast'])
 sys.path.insert(0,str(repo/'HDS/学習系統/v0.4.2'));n=importlib.import_module('hds学習系統');nt=importlib.import_module('hds学習系統.型')
 helpers={'deepcopy':copy.deepcopy,'学習入力':nt.学習入力,'観測事実':nt.観測事実};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(bridge),'exec'),helpers)
 class Recording(n.HDS学習実行系):
  def __init__(self,minimum):super().__init__(最小支持数=minimum);self.calls=[]
  def 実行(self,value):
   result=super().実行(value);exhaust=n.最小排気系().排出する(result);self.calls.append({'input':value,'result':result,'raw_exhaust':exhaust});return result
  def 照会(self,*args,**kwargs):raise AssertionError('native query prohibited')
 identity=fitted.モデル群;state=dataclasses.asdict(fitted);rows=[]
 with patch.object(a,'fit',side_effect=AssertionError('native refit prohibited')):
  for minimum in(2,3):
   machine=Recording(minimum);calls=[];check('empty-native-ledger',machine.台帳.全取得()=={})
   def candidate(grid,policy):
    check('same-frozen-model-identity',fitted.モデル群 is identity);output,detail=fitted.候補(grid,policy);calls.append({'input':grid,'output':output,'detail':detail});return output,detail
   boundary='ARC全体模様窓';record=helpers['候補機構を学習'](machine,{'train':teachers},(),boundary,candidate)
   obs=machine.台帳.取得('観測台帳');refs=tuple(o.経験識別子 for o in obs);equalities=[p for p in machine.calls[-1]['result'].有効原理群 if helpers['同値原理あり']([p],boundary)]
   check('native-current-support:'+str(minimum),record['採用可']and record['同値採用']==(minimum==2)and record['現在観測数']==2 and record['事前観測数']==record['隔離数']==0)
   check('native-reference-values',len(obs)==len(calls)==2 and len({encoder(o.原入力)for o in obs})==2 and bool(equalities)==(minimum==2)and all(p.根拠参照群==refs and not p.反証参照群 for p in equalities))
   check('native-observation-full-values',all(ob.原入力=={'候補':pair['output'],'出力':pair['output']}and call['input']==pair['input']and call['output']==pair['output']for pair,ob,call in zip(teachers,obs,calls)))
   check('native-fitted-state-unchanged',identity is fitted.モデル群 and dataclasses.asdict(fitted)==state)
   save(out,'native-support-'+str(minimum)+'.json.gz',{'minimum':minimum,'record':record,'candidate_calls':calls,'native_calls':machine.calls,'ledger':machine.台帳.JSON相当(),'references':refs,'equalities':equalities,'retained_models':identity,'query_calls':0})
   rows.append({'minimum_support':minimum,'current_observations':len(obs),'equality_admitted':record['同値採用'],'query_calls':0})
 return rows

def raw_reporter_fault(a,teachers,out):
 proof=a.necessity;primary=MemoryError('certificate current pending is unknown');original=proof.certify_teacher;calls=0;caught=None
 def changed(*args,**kwargs):
  nonlocal calls
  calls+=1
  if calls==2:raise primary
  return original(*args,**kwargs)
 def broken(*args,**kwargs):raise RecursionError('whole reporter unavailable')
 with patch.object(proof,'certify_teacher',changed),patch.object(proof,'attach_exception',broken):
  try:proof.fit(teachers)
  except BaseException as error:caught=error
 check('whole-reporter-original-primary',caught is primary);raw=h.capture_raw_exception(caught)
 frames=[frame['locals']for frame in raw['frames']if frame['function']=='fit'and'certificate_rows'in frame['locals']]
 check('whole-reporter-complete-prefix',any(len(row['pre_parsed'])==len(teachers)and len(row['witness_records'])==len(teachers)and len(row['certificate_rows'])==1 and row['pending_certificate']is None and row['teacher_index']==1 and not row['actual_rows']and not row['symbolic_slots']for row in frames))
 save(out,'whole-reporter-raw-prefix.json.gz',raw)

def execute(args,repo,out):
 CHECKS.clear();lock=h.verify_lock(h.S);a,repo=load(repo);proof=a.necessity
 teachers=json.loads(gzip.decompress((F/'old-synthetic-fixtures.json.gz').read_bytes()))['teachers'];results={}
 if args.mode=='literal':results={'certificates':c.check_certificates(proof),'strict':c.check_strict_inputs(proof)}
 elif args.mode=='fit_native':
  original=copy.deepcopy(teachers);audit={};obj=a.全体模様窓必要条件教材(teachers,audit)
  check('original-inputs-unchanged',teachers==original)
  identity=obj.モデル群;expanded=obj.記録()['保持候補'];decoded=tuple((row['model_index'],)+tuple(row['spec'][key]for key in proof.FIELDS)for row in expanded)
  check('native-model-schema-lossless',decoded==identity and all(tuple(row['spec'])==proof.FIELDS for row in expanded))
  predictions=[]
  for pair in teachers:
   output,record=obj.候補(pair['input'],{});check('full-teacher-reproduction',output==pair['output']);predictions.append({'output':output,'record':record})
  save(out,'fit-record.json.gz',{'teachers':teachers,'models':identity,'audit':audit,'predictions':predictions,'native_metadata':obj.記録(),'runtime_lock_sha256':h.sha(h.DEPLOYMENT_PIN_PATH)})
  results={'retained_count':len(identity),'actual_rows':audit['complete_program_teacher_evaluations'],'symbolic_slots':audit.get('symbolically_unexecuted_program_teacher_evaluations',0),'native':native(a,repo,obj,teachers,out)}
 elif args.mode=='reconcile':
  new=read_pinned(args.new_record.resolve(),args.new_record_sha256);paths=c.fixtures()['saved_complete_synthetic_fit_records'];pin='15ba2a93673cee277615f825783f6fe4d53db89c4d69a5f7a9c38b5217b61da1'
  for path in paths:h.pincheck('saved-complete-matrix-provenance:'+path,h.readpins()['reference_sources'][path]==pin)
  old=read_pinned(F/'baseline-matrix.json.gz',pin);models=tuple(tuple(m)for m in new['models'])
  results={'independent_full_domain':c.check_fit_record(models,new['audit'],old),'all_four_old_complete_files_byte_identical':True,'source_pins':{'new':args.new_record_sha256,'old':pin},'new_fits_executed':0}
 elif args.mode=='inconclusive':
  value=c.check_inconclusive_fallback(proof,(args.case,));save(out,'exact-inconclusive-fallback.json.gz',value);results={'case':args.case,'completed_original_models':1,'new_full_fits':0}
 elif args.mode=='fault':
  kind={'MemoryError':MemoryError,'RuntimeError':RuntimeError,'RecursionError':RecursionError,'TimeoutError':TimeoutError}[args.exception]
  value=c.check_fault_prefix(proof,args.case,kind);save(out,'fault-prefix.json.gz',value);results={'case':args.case,'exception':args.exception,'prefix':value['summary']}
 else:raw_reporter_fault(a,teachers,out);results={'whole_reporter_failure':True}

 h.pincheck('sealed-runtime-unchanged',h.verify_lock(h.S)==lock)
 return {'passed':True,'mode':args.mode,'case':args.case,'optimized':sys.flags.optimize,'checks':CHECKS,'results':results,
         'administrative_check_count':len(h.ADMIN_CHECKS),'official_query_calls':0,'scorer_calls':0}
