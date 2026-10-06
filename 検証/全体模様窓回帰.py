#!/usr/bin/env python3
"""Whole-mask necessity regression:29 existing independently bounded cases."""
import sys
sys.dont_write_bytecode=True
import argparse,gzip,hashlib,json,os,pathlib,resource,signal,subprocess,tempfile,time,types
P=pathlib.Path(__file__).resolve().parents[1];F=P/'検証/全体模様窓資料';sys.path.insert(0,str(F))
import evidence_support as h
import focused_suite as suite
import child_cases
CASES=[('literal',None,'MemoryError'),('fit_native',None,'MemoryError'),('raw_reporter',None,'MemoryError'),('reconcile',None,'MemoryError')]
CASES +=[('inconclusive',x,'MemoryError')for x in('absent','failed_role','incomplete_role')]
CASES +=[('fault',x,'MemoryError')for x in('parse','certificate','apply','witness','model_certificate','self_refuted','unknown_exact','success_raw_return','failure_raw_return','actual_row','completed_model','secondary_reporter')]
CASES +=[('fault','parse',x)for x in('RuntimeError','RecursionError','TimeoutError')]
CASES +=[('child',x,'MemoryError')for x in('positive','proof','early','malformed','memory','cpu','kill')]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repository-root',type=pathlib.Path);ap.add_argument('--output-base',type=pathlib.Path);ap.add_argument('--deployment-check-only',action='store_true');ap.add_argument('--worker',type=int);ap.add_argument('--internal-child');ap.add_argument('--case-output',type=pathlib.Path);ap.add_argument('--new-record',type=pathlib.Path);ap.add_argument('--new-record-sha256');args=ap.parse_args()
 deployed=(P/'HDS/学習系統/v0.4.2/hds学習系統').is_dir();repo=args.repository_root.resolve()if args.repository_root else P if deployed else P.parent/'source-evidence/repository';h.REPOSITORY_ROOT=repo
 if args.internal_child:
  if args.internal_child not in('positive','proof','early','malformed','memory','cpu','kill')or args.case_output is None:raise ValueError('invalid internal literal child')
  return child_cases.injected(args.internal_child,P,args.case_output.resolve(),bool(sys.flags.optimize))
 resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,)*2);resource.setrlimit(resource.RLIMIT_CPU,(10,10));signal.signal(signal.SIGALRM,lambda *unused:(_ for _ in()).throw(TimeoutError('regression administrative or individual-control60wall')));signal.alarm(60)
 if args.worker is not None:
  if not 0<=args.worker<len(CASES)or args.case_output is None:raise ValueError('invalid bounded case')
  out=args.case_output.resolve();out.mkdir(parents=True,exist_ok=False);mode,case,error=CASES[args.worker]
  a=types.SimpleNamespace(mode=mode,case=case,exception=error,optimized=bool(sys.flags.optimize),new_record=args.new_record,new_record_sha256=args.new_record_sha256)
  try:value=child_cases.execute(a,P,out,pathlib.Path(__file__).resolve(),repo)if mode=='child'else suite.execute(a,repo,out)
  except BaseException as e:
   h.write(out/'case-failure.json.gz',{'passed':False,'exception':h.safe_exception(e),'raw':h.capture_raw_exception(e)});raise
  h.write(out/'case-summary.json.gz',value);print(json.dumps({'successful':True,'tests_run':1,'case_index':args.worker,'administrative_check_count':len(h.ADMIN_CHECKS)},ensure_ascii=False));return 0
 base=args.output_base.resolve()if args.output_base else pathlib.Path(tempfile.gettempdir());base.mkdir(parents=True,exist_ok=True);out=pathlib.Path(tempfile.mkdtemp(prefix='arc2-candidate034-',dir=base));pins=h.verify_lock(P);calls={}
 if args.deployment_check_only:
  names={'fit','parse','parse_whole','apply','action','render','predict','certify_teacher','候補機構を学習','実行','照会'}
  def profile(frame,event,arg):
   if event=='call'and frame.f_code.co_name in names and any(r in pathlib.Path(frame.f_code.co_filename).parents for r in(P/'接続/ARC2',repo/'接続/ARC2',repo/'HDS/学習系統/v0.4.2/hds学習系統')):calls[frame.f_code.co_name]=calls.get(frame.f_code.co_name,0)+1
  sys.setprofile(profile)
  try:a,_=suite.load(repo)
  finally:sys.setprofile(None)
  h.pincheck('fixed-model-domain',len(a.SPECS)==23040);h.pincheck('no-behavioral-loader-calls',not calls);h.pincheck('pins-unchanged',h.verify_lock(P)==pins)
  summary={'successful':True,'tests_run':0,'behavioral_suite_executed':False,'runtime_calls':calls,'fit_render_predict_native_calls':0,'administrative_check_count':len(h.ADMIN_CHECKS),'artifact_directory':str(out)};h.write(out/'summary.json',summary);print(json.dumps(summary));return 0
 signal.alarm(110) # Outer administrative envelope stays below collector120; each case retains60.
 jobs=list(range(len(CASES)));active={};results=[];fit_path=None;fit_pin=None;start=time.monotonic()
 try:
  while jobs or active:
   while len(active)<3:
    ready=next((i for i in jobs if CASES[i][0]!='reconcile'or fit_path is not None),None)
    if ready is None:break
    jobs.remove(ready);target=out/('case-'+str(ready).zfill(2));stdout=(out/(str(ready).zfill(2)+'.stdout')).open('wb');stderr=(out/(str(ready).zfill(2)+'.stderr')).open('wb');cmd=[sys.executable]+(['-O']if sys.flags.optimize else[])+['-B',str(pathlib.Path(__file__).resolve()),'--repository-root',str(repo),'--worker',str(ready),'--case-output',str(target)]
    if CASES[ready][0]=='reconcile':cmd+=['--new-record',str(fit_path),'--new-record-sha256',fit_pin]
    p=subprocess.Popen(cmd,stdout=stdout,stderr=stderr,cwd=repo,start_new_session=True);active[p.pid]=(p,ready,time.monotonic(),target,stdout,stderr,False)
   for pid,state in list(active.items()):
    p,index,started,target,stdout,stderr,timed=state;got,status,usage=os.wait4(pid,os.WNOHANG);wall=time.monotonic()-started
    if not got:
     if wall>=60 and not timed:os.killpg(pid,signal.SIGKILL);active[pid]=(*state[:-1],True)
     continue
    p.returncode=os.waitstatus_to_exitcode(status);stdout.close();stderr.close();cpu=usage.ru_utime+usage.ru_stime
    row={'case_index':index,'case':CASES[index],'successful':False,'exit_code':p.returncode,'wait_status':status,'actual_process_and_waited_child_cpu_seconds':cpu,'whole_wall_seconds':wall,'max_rss_KiB':usage.ru_maxrss,'timed_out':timed}
    h.write(out/(str(index).zfill(2)+'.terminal.json'),row);results.append(row);del active[pid]
    passed=p.returncode==0 and cpu<=10 and wall<=60 and(target/'case-summary.json.gz').exists()
    if passed:
     try:passed=json.loads(gzip.decompress((target/'case-summary.json.gz').read_bytes())).get('passed')is True
     except BaseException as error:row['summary_read_error']=h.safe_exception(error);passed=False
    row['successful']=passed;h.write(out/(str(index).zfill(2)+'.process.json'),row)
    if CASES[index][0]=='fit_native'and passed:fit_path=target/'fit-record.json.gz';fit_pin=h.sha(fit_path)
   if not active and jobs and fit_path is None and all(CASES[i][0]=='reconcile'for i in jobs):break
   if active:time.sleep(.02)
 finally:
  signal.alarm(0)
  for pid,state in list(active.items()):
   p,index,started,target,stdout,stderr,timed=state
   try:os.killpg(pid,signal.SIGKILL)
   except ProcessLookupError:pass
   got,status,usage=os.wait4(pid,0);p.returncode=os.waitstatus_to_exitcode(status);stdout.close();stderr.close()
   row={'case_index':index,'case':CASES[index],'successful':False,'exit_code':p.returncode,'wait_status':status,'actual_process_and_waited_child_cpu_seconds':usage.ru_utime+usage.ru_stime,'whole_wall_seconds':time.monotonic()-started,'max_rss_KiB':usage.ru_maxrss,'interrupted_parent':True}
   h.write(out/(str(index).zfill(2)+'.process.json'),row);results.append(row);del active[pid]
  h.write(out/'terminal-prefix.json',{'completed_worker_records':sorted(results,key=lambda x:x['case_index']),'unstarted_case_indices':jobs})
 h.pincheck('pins-unchanged',h.verify_lock(P)==pins);passed=len(results)==len(CASES)and all(x['successful']for x in results);summary={'successful':passed,'tests_run':sum(x['successful']for x in results),'declared_test_cases':len(CASES),'case_count_semantics':'Each test is one original independently bounded focused/child case; all assertions inside it are retained','behavioral_suite_executed':True,'administrative_check_count':len(h.ADMIN_CHECKS),'cases':sorted(results,key=lambda x:x['case_index']),'artifact_directory':str(out),'wall_seconds':time.monotonic()-start,'official_query_calls':0,'scorer_calls':0,'full120_runs':0};h.write(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False));return 0 if passed else 1
if __name__=='__main__':raise SystemExit(main())
