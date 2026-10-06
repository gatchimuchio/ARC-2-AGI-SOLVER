"""Unchanged reviewed child-case assertions under relocated paths."""
import gzip,io,json,os,pathlib,resource,signal,subprocess,sys,time
import evidence_support as h
F=pathlib.Path(__file__).resolve().parent
def injected(case,root,out,optimized):
 packet=json.loads(gzip.decompress((F/'old-synthetic-fixtures.json.gz').read_bytes()));pairs=packet['teachers']
 if case=='proof':pairs=[pairs[0],{'input':[[0,0]],'output':[[0,1]]}]
 if case=='early':pairs=[{'input':[[0]],'output':[[0]]},{'input':[[0,1]],'output':[[1,0]]}]
 if case=='malformed':pairs=[{'input':[[0]],'output':[[0]],'extra':1}]
 sys.stdin=io.StringIO(json.dumps({'train':pairs}));original=h.importlib.import_module
 def load(name,*args,**kwargs):
  m=original(name,*args,**kwargs)
  if name=='接続.ARC2.全体模様窓必要条件教材' and case in('memory','cpu','kill'):
   add=m.strict._base.Returns.add;n=0
   def replacement(*args,**kwargs):
    nonlocal n
    n+=1
    if n==3:
     if case=='memory':bytearray(1024*1024*1024)
     elif case=='cpu':
      resource.setrlimit(resource.RLIMIT_CPU,(1,1))
      while True:pass
     else:os.kill(os.getpid(),signal.SIGKILL)
    return add(*args,**kwargs)
   def broken_report(*args,**kwargs):raise RecursionError('secondary reporting failure')
   m.strict._base.Returns.add=replacement
   for module in(m,m.necessity,m.strict,m.strict._base):module.attach_exception=broken_report
  return m
 h.importlib.import_module=load
 return h.child(0,out,root,h.sha(h.DEPLOYMENT_PIN_PATH))
def execute(a,root,out,entry,repo):
 lock=h.sha(h.DEPLOYMENT_PIN_PATH);h.verify_lock(root,lock)
 cmd=[sys.executable]+(['-O']if a.optimized else[])+['-B',str(entry),'--repository-root',str(repo),'--internal-child',a.case,'--case-output',str(out)]
 started=time.monotonic();timed_out=False
 with(out/'stdout').open('wb')as stdout,(out/'stderr').open('wb')as stderr:
  p=subprocess.Popen(cmd,stdout=stdout,stderr=stderr,cwd=repo)
  try:
   while True:
    pid,status,usage=os.wait4(p.pid,os.WNOHANG)
    if pid:break
    if time.monotonic()-started>=60 and not timed_out:timed_out=True;p.kill()
    time.sleep(.02)
  finally:
   if not locals().get('pid'):
    p.kill();pid,status,usage=os.wait4(p.pid,0)
   p.returncode=os.waitstatus_to_exitcode(status)
   h.write(out/'child-process.json',{'exit_code':p.returncode,'wait_status':status,'cpu_seconds':usage.ru_utime+usage.ru_stime,'whole_wall_seconds':time.monotonic()-started,'max_rss_KiB':usage.ru_maxrss,'timed_out':timed_out})
 elapsed=time.monotonic()-started;teacher_count=1 if a.case=='malformed'else 2
 row=h.read_completion(out/'000.record.json.gz',timed_out,p.returncode,elapsed);row.update(h.read_journal(out/'000.events.jsonl.gz',teacher_count));h.reconcile_receipt(row,teacher_count,lock)
 row.update(exit_code=p.returncode,parent_wall_seconds=elapsed,actual_child_process_cpu_seconds=usage.ru_utime+usage.ru_stime,wait4_ru_maxrss_KiB=usage.ru_maxrss)
 h.enforce_whole_child_budget(row,usage.ru_utime+usage.ru_stime,elapsed)
 h.write(out/'000.receipt.json.gz',row)
 if a.case in('positive','proof','early'):
  if not row['completed']or p.returncode or row['receipt_consistency_failures']:raise AssertionError('synthetic child failed '+str(row.get('receipt_consistency_failures')))
  if a.case=='positive':
   if not row['all_exact']or row['evaluated_teacher_calls']+row['symbolic_unexecuted_teacher_calls']!=46080 or row['accounted_model_teacher_pairs']['count']!=46080 or not row['models']:raise AssertionError('positive domain incomplete')
  else:
   if row['models']or row['evaluated_teacher_calls']or row['symbolic_unexecuted_teacher_calls']!=46080 or row['actual_started_fit_action_calls']:raise AssertionError('parse impossibility proof accounting')
   if a.case=='early'and(row['actual_completed_prediction_parse_calls']!=2 or row['actual_completed_prediction_strict_parse_calls']!=0):raise AssertionError('early whole parse omitted or nested strict falsely counted')
 elif a.case=='malformed':
  if row['completed']or row['semantic_HOLD']or row.get('exception')!='ValueError':raise AssertionError('malformed schema became HOLD')
 else:
  if row['completed']or row['semantic_HOLD']or not row['resource_failure']:raise AssertionError('resource failure became completion/HOLD')
  if row['completed_model_teacher_pairs']['count']!=2 or row['core_completed_model_teacher_pairs']['count']!=3 or row['core_return_without_teacher_record_pairs']['count']!=1 or row['completed_program_indices']!=list(range(len(row['completed_program_indices']))):raise AssertionError('resource completed/pending prefix lost')
  if a.case=='memory':
   with gzip.open(out/'000.exception-raw.json.gz','rt')as stream:raw=json.load(stream)
   fit=[x['locals']for x in raw['frames']if x['function']=='fit'and 'actual_rows'in x['locals']]
   if row.get('exception')!='MemoryError'or not any(len(x['actual_rows'])==2 and len(x['certificates'])==23040 and x['pending']['row_committed']is False and x['result']is not None for x in fit):raise AssertionError('real memory exception/pending lost after reporter failure')

 return {'passed':True,'case':a.case,'optimized':a.optimized,'record':row,
         'administrative_check_count':len(h.ADMIN_CHECKS),'official_input':False}
