import sys
sys.dont_write_bytecode=True
import argparse,ast,copy,dataclasses,gzip,hashlib,importlib,importlib.util,json,pathlib,tempfile,traceback,types
P=pathlib.Path(__file__).resolve().parents[1];S=P.parent;F=P/'検証/全足跡整列資料';PASSED=[]
def serial(value):
 if dataclasses.is_dataclass(value):return serial(dataclasses.asdict(value))
 if isinstance(value,dict):return {str(k):serial(v)for k,v in value.items()}
 if isinstance(value,(list,tuple)):return [serial(v)for v in value]
 if isinstance(value,(set,frozenset)):return [serial(v)for v in sorted(value,key=repr)]
 if value is None or type(value)in(str,int,float,bool):return value
 raise TypeError(type(value).__name__)
def same(a,b):return json.dumps(serial(a),sort_keys=True)==json.dumps(serial(b),sort_keys=True)
def need(condition,message):
 if not condition:raise AssertionError(message)
def check(name,condition=True):need(condition,name);PASSED.append(name)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_bytes(gzip.compress(json.dumps(serial(value),ensure_ascii=False,separators=(',',':')).encode(),mtime=0)if path.suffix=='.gz'else json.dumps(serial(value),ensure_ascii=False,indent=2).encode())

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output-base');ap.add_argument('--repository-root');args=ap.parse_args();output_base=pathlib.Path(args.output_base).resolve()if args.output_base else S/'candidate030-v2-results';output_base.mkdir(parents=True,exist_ok=True)
 out=pathlib.Path(tempfile.mkdtemp(prefix='arc2-candidate030-v2-',dir=output_base));summary={'artifact_directory':str(out),'full120_runs':0}
 try:
  spec=importlib.util.spec_from_file_location('v1_regression',F/'v1_regression.py');reg=importlib.util.module_from_spec(spec);spec.loader.exec_module(reg)
  reg.P=P;reg.F=F;loaded,native,helpers,oracle,guard=reg.load(out,args.repository_root);old=loaded.base;identity=json.loads(gzip.decompress((F/'依存固定.json.gz').read_bytes()))
  pkg=types.ModuleType('_candidate030_v2');pkg.__path__=[str(P/'接続/ARC2')];sys.modules[pkg.__name__]=pkg;adapter=importlib.import_module(pkg.__name__+'.全足跡整列教材')
  check('exact original fitter bytes',sha(P/'接続/ARC2/全足跡整列基底教材.py')==identity['v1_wrapper_sha256'])
  need(sha(P/'接続/ARC2/全足跡整列候補.py')==identity['runtime_core_sha256']and sha(P/'接続/ARC2/全足跡旧部品.py')==identity['legacy_sha256'],'unchanged runtime')
  need(sha(P/'接続/ARC2/全足跡整列教材.py')==identity['v2_wrapper_sha256'],'frozen v2 wrapper')
  teachers=reg.read('teachers.json.gz')['train'];audit={};events=[];fitted=adapter.全足跡整列教材(teachers,audit,events.append);prior={};previous=old.全足跡整列教材(teachers,prior)
  check('same original fitted state',dataclasses.asdict(fitted)==dataclasses.asdict(previous))
  original_record={k:v for k,v in audit.items()if k!='axis_necessity'};check('fallback all original fit records identical',same(original_record,prior)and audit['axis_necessity']['disposition']=='exact_v1_fitter_fallback')
  need(fitted.モデル群==adapter.PROGRAMS,'fixed activation');save(out/'fallback-full-teacher-fit.json.gz',audit)
  summary['prototype']=reg.replay(adapter,teachers,oracle,guard,out)
  summary['native']=reg.native_cycles(adapter,native,helpers,fitted,teachers,out)
  PASSED.extend(reg.PASSED)
  state=dataclasses.asdict(fitted)
  try:fitted.教師数=0
  except dataclasses.FrozenInstanceError:pass
  else:raise AssertionError('mutable fit')
  detached=fitted.記録();detached['保持候補'].clear();need(dataclasses.asdict(fitted)==state,'detached immutable state')
  check('immutable inherited model and detached state')
  # All old fixture inputs: certificate presence is independently checked from pixels.
  proof_rows=[]
  for case in oracle.fixture_cases():
   grid=case['input']
   if not adapter.valid_grid(grid):continue
   certificate=adapter.axis_certificate(grid);colors=sorted(set(v for line in grid for v in line));counts={color:sum(v==color for line in grid for v in line)for color in colors};maximum=max(counts.values());bgs=[c for c in colors if counts[c]==maximum]
   need(certificate['background_candidates']==bgs,'original full-grid background')
   for c in range(10):need(certificate['colors'][c]['row_counts']==[line.count(c)for line in grid],'complete per-color row counts')
   witnesses=[]
   if len(bgs)==1:
    for color in colors:
     positions=[(r,c)for r,line in enumerate(grid)for c,v in enumerate(line)if v==color];rows={r for r,c in positions}
     if color!=bgs[0]and len(positions)>=3 and len(rows)==1 and 0<next(iter(rows))<len(grid)-1:witnesses.append((next(iter(rows)),color))
    need(certificate['axis_absence_proved']==(not witnesses),'independent absence')
    output,detail=old.render(grid,old.PROGRAMS[0])
    if not witnesses:need(output is None and not detail['retained_roles'],'source necessity agrees with original full renderer')
   else:need(not certificate['axis_absence_proved']and certificate['symbolic_raw_pair_count']is None,'tie not absence')
   proof_rows.append({'case':case['name'],'certificate':certificate});check('certificate arithmetic '+case['name'])
  save(out/'independent-certificate-controls.json.gz',proof_rows)
  # Schema failure cannot reach hashing or the new proof, including bad trailing pairs.
  malformed=[None,{},[],teachers[:1],[teachers[0],teachers[0]],[None,teachers[1]],teachers+[{'input':[[True]],'output':[[0]]}],[{'input':[[0]],'output':[[0]],'extra':0},teachers[1]]]
  certificate_fn=adapter.axis_certificate;key=adapter.base.gridkey
  def forbidden(*a,**k):raise AssertionError('invalid schema reached proof/hash/renderer')
  adapter.axis_certificate=forbidden
  try:
   for pairs in malformed:
    schema_invalid=type(pairs)in(list,tuple)and any(type(p)is not dict or set(p)!={'input','output'}or not adapter.valid_grid(p['input'])or not adapter.valid_grid(p['output'])for p in pairs)
    if schema_invalid:adapter.base.gridkey=forbidden
    try:models,record=adapter.fit(pairs)
    finally:adapter.base.gridkey=key
    need(models==()and 'axis_necessity'not in record,'strict schema old failure')
   check('strict validation precedes new proof and malformed hashing')
  finally:adapter.axis_certificate=certificate_fn
  # Any proved-empty teacher suffices, but all teacher certificates are completed.
  empty={'input':[[0]],'output':[[0]]};mixed=[teachers[0],empty,teachers[1]];basefit=adapter.base.fit;calls=[]
  adapter.base.fit=forbidden
  try:
   models,record=adapter.fit(mixed);need(models==()and record['evaluated_teacher_returns']==0 and record['evaluated_programs']==0,'no executed returns fabricated')
   need(record['axis_necessity']['rejecting_teacher_indices']==[1]and len(record['axis_necessity']['certificates'])==3,'any proof and all teachers')
   need(len(record['unexecuted_calls'])==3 and all(not r['renderer_executed']and not r['raw_pairs_enumerated']and not r['output_returned']for r in record['unexecuted_calls']),'explicit skipped calls')
   save(out/'mixed-any-teacher-proof.json.gz',record);check('any teacher absence rejects fit with all calls explicitly unexecuted')
  finally:adapter.base.fit=basefit
  # No proof, including a nonunique background: exact old fitter must run.
  tie={'input':[[0,1],[1,0]],'output':[[0,1],[1,0]]};calls=[]
  def counted(*args,**kwargs):calls.append(1);return basefit(*args,**kwargs)
  adapter.base.fit=counted
  try:
   models,record=adapter.fit([teachers[0],tie]);need(calls==[1]and record['axis_necessity']['rejecting_teacher_indices']==[]and record['axis_necessity']['certificates'][1]['proof_status']=='inapplicable_nonunique_background','nonunique background fallback')
   old_models,old_record=basefit([teachers[0],tie]);need(models==old_models and same({k:v for k,v in record.items()if k!='axis_necessity'},old_record),'exact old fallback')
   save(out/'background-tie-fallback.json.gz',record);check('background tie cannot fabricate absence; exact fitter fallback')
  finally:adapter.base.fit=basefit
  tasks=json.loads(gzip.decompress((F/'resource-proof-teachers.json.gz').read_bytes()));resource_proofs=[];adapter.base.fit=forbidden
  try:
   for task_id in ('0934a4d8','4c7dc4dd','981571dc'):
    pairs=tasks[task_id]['train'];models,record=adapter.fit(pairs)
    need(models==()and len(record['axis_necessity']['rejecting_teacher_indices'])==len(pairs),'all old resource inputs proof');need(len(record['unexecuted_calls'])==len(pairs),'all symbolic calls')
    resource_proofs.append({'task_id':task_id,'record':record});check('old resource task proof only '+task_id)
  finally:adapter.base.fit=basefit
  save(out/'three-old-resource-task-proof-controls.json.gz',resource_proofs)
  resource_controls=[]
  for error_type in (MemoryError,RecursionError,TimeoutError,ValueError):
   for observed in (False,True):
    for mode in ('certificate','fallback'):
     error=error_type('injected v2 '+mode+' failure');events=[]
     if mode=='certificate':
      failed_grid=teachers[1]['input']
      def interrupted(iterable,*args):
       if iterable is failed_grid:
        def generator():
         yield 0,iterable[0]
         raise error
        return generator()
       return enumerate(iterable,*args)
      adapter.enumerate=interrupted
     else:
      apply=adapter.core.apply_role;count=[0]
      def interrupted(*a,**k):
       count[0]+=1
       if count[0]==2:raise error
       return apply(*a,**k)
      adapter.core.apply_role=interrupted
     try:adapter.fit(teachers,events.append if observed else None)
     except error_type as caught:
      need(caught is error,'same original exception');outer=caught.evaluation_diagnostic;need(not outer['semantic_HOLD']and outer['resource_failure']==issubclass(error_type,adapter.RESOURCE_ERRORS),'error classification')
      inner=outer['inner_diagnostic']
      if mode=='certificate':need(len(outer['completed_teacher_certificates'])==1 and sum(map(sum,inner['partial_row_counts']))==len(teachers[1]['input'][0]),'complete prior certificate and partial counts')
      else:need(len(outer['completed_teacher_certificates'])==3 and len(inner['completed_teacher_returns'])==1 and inner['inner_diagnostic']['completed_resource_prefix'],'fallback nested original prefix')
      resource_controls.append({'mode':mode,'observed':observed,'exception':error_type.__name__,'diagnostic':outer,'events':events});check('v2 resource prefix '+mode+' '+str(observed)+' '+error_type.__name__)
     else:raise AssertionError('v2 exception swallowed')
     finally:
      if mode=='certificate':del adapter.enumerate
      else:adapter.core.apply_role=apply
  save(out/'proof-and-fallback-resource-prefixes.json.gz',resource_controls)
  summary.update(successful=True,tests_run=len(PASSED),passed_cases=PASSED,new_proof_only=True,original_fitter_fallback_exact=True)
 except BaseException as error:summary.update(successful=False,tests_run=len(PASSED),passed_cases=PASSED,error=type(error).__name__,message=str(error),traceback=traceback.format_exc())
 save(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False));return 0 if summary['successful']else 1
if __name__=='__main__':raise SystemExit(main())
