#!/usr/bin/env python3
"""Observation-only source-contract audit. Never changes native source or learned state directly."""
from pathlib import Path
import argparse, ast, dataclasses, gc, hashlib, json, os, resource, sys, time, traceback
from enum import Enum

ap=argparse.ArgumentParser()
ap.add_argument('--root',type=Path,required=True)
ap.add_argument('--protocol',type=Path,required=True)
ap.add_argument('--out',type=Path,required=True)
a=ap.parse_args(); a.out.mkdir(exist_ok=False)
assert __debug__

def default(o):
    if dataclasses.is_dataclass(o):return {f.name:getattr(o,f.name) for f in dataclasses.fields(o)}
    if isinstance(o,Enum):return o.value
    raise TypeError(type(o).__name__)
encoder=json.JSONEncoder(ensure_ascii=False,sort_keys=True,separators=(',',':'),default=default)
def digest(o):
    h=hashlib.sha256()
    for chunk in encoder.iterencode(o):h.update(chunk.encode())
    return h.hexdigest()
def fh(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while chunk:=f.read(1048576):h.update(chunk)
    return h.hexdigest()
def dump(name,o):
    with (a.out/name).open('w',encoding='utf-8') as f:json.dump(o,f,ensure_ascii=False,indent=2,default=default);f.write('\n')

def raw(stage,o):
    json.dump({'stage':stage,'result':o},rawfile,ensure_ascii=False,separators=(',',':'),default=default)
    rawfile.write('\n');rawfile.flush()

protocol=json.loads(a.protocol.read_text())
experience_path=a.root/'学習台帳/ARC2規則経験_v1.jsonl'
rows=[json.loads(s) for s in experience_path.read_text().splitlines()]
assert len(rows)==67 and fh(experience_path)=='5905139cc6723b97c67035c00e3f2ea9633ff58ef0e96b81a6676f8c636ae7c1'
core=sorted((a.root/'HDS/学習系統/v0.4.2/hds学習系統').glob('*.py'));assert len(core)==12
prior_freeze=json.loads((a.protocol.parent.parent/'native-v2/freeze.json').read_text())
assert all(fh(p)==prior_freeze['core12'][str(p.relative_to(a.root))]['sha256'] for p in core)
protected={str(p.relative_to(a.root)):fh(p) for p in a.root.rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts}
ledger_names=set()
for p in core:
    for node in ast.walk(ast.parse(p.read_text())):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='追記' and node.args and isinstance(node.args[0],ast.Constant):ledger_names.add(node.args[0].value)
ledger_names=sorted(ledger_names)
sys.path[:0]=[str(a.root),str(a.root/'HDS/学習系統/v0.4.2')]
from hds学習系統 import HDS学習系統, 外部入力
from 接続.ARC2.HDS接続 import 格子観測
import hds学習系統
m=HDS学習系統();e=m.エンジン
identities={'process':os.getpid(),'machine':id(m),'engine':id(e),'ledger':id(e.台帳),'state':id(e.状態),'identifiers':id(e.識別子)}
start=time.monotonic();checks=[];batches=[];seed_refs=[];rule_refs=[];learning_calls=[];baseline_prefixes={};baseline_state_history=();rawfile=(a.out/'raw-native-results.jsonl').open('w',encoding='utf-8')
freeze={'protocol_sha256':fh(a.protocol),'observer_sha256':fh(Path(__file__)),'experiences_sha256':fh(experience_path),'core12':{str(p.relative_to(a.root)):fh(p) for p in core},'protected_original_files':protected,'import':hds学習系統.__file__,'identity':identities,'defaults':{'minimum_support':e.最小支持数,'max_conditions':e.最大条件数},'ledger_names':ledger_names,'official_input_parsed_or_used_as_runtime':False,'protected_files_hashed_for_integrity_only':True,'native_persistence_attempted':False,'protocol':protocol}
dump('freeze.json',freeze)

def check(name,ok,details=None):
    item={'name':name,'passed':bool(ok)}
    if details is not None:item['details']=details
    checks.append(item)
    return bool(ok)
def assert_identity():
    assert m.エンジン is e
    assert identities=={'process':os.getpid(),'machine':id(m),'engine':id(e),'ledger':id(e.台帳),'state':id(e.状態),'identifiers':id(e.識別子)}
def state_digest():return {'version':e.状態.現在版,'current':digest(e.状態.現在状態),'history':digest(e.状態.履歴()),'counts':{n:e.台帳.件数(n) for n in ledger_names},'observation_contents':digest(e.台帳.取得('観測台帳'))}
def ledger_digests():
    result={}
    for n in ledger_names:
        records=e.台帳.取得(n)
        result[n]={'count':len(records),'sha256':digest(records)}
        if n in baseline_prefixes:
            initial=baseline_prefixes[n]
            check('append_only/'+n, len(records)>=initial['count'] and digest(records[:initial['count']])==initial['sha256'])
        del records;gc.collect()
    return result

def latest_learning():return e.台帳.取得('学習過程台帳')[-1]
def learn(boundary,content,stage,grid=False,args=None):
    assert_identity();before=e.状態.現在版
    if grid:out=m.排気系.排出する(e.実行(格子観測(content)))
    else:out=m.処理する(外部入力(**(args if args is not None else {'内容':content,'対象系境界':boundary})))
    raw(stage,out)
    process=latest_learning();raw(stage+'/learning_process',process)
    learning_calls.append({'stage':stage,'experience':process.経験参照,'boundary':process.対象系境界,'status':process.学習成立状態.value,'before':before,'after':e.状態.現在版})
    check(stage+'/成立確認_requires_state_change',process.学習成立状態.value!='成立確認' or (process.学習後状態版!=process.学習前状態版 and bool(process.状態変化理由群)))
    check(stage+'/one_memory_append',e.台帳.件数('観測台帳')==len(learning_calls))
    return out,process

def prediction_map(out):
    vals={}
    for p in out.内容['予測群']:
        vals.setdefault('/'.join(p['結果経路']),[]).append(p['予測値'])
    return vals

def norm(out):
    c=out.内容
    return {'status':out.状態,'learning_status':c['学習成立状態'],'predictions':prediction_map(out),
            'conflicts':c['競合群'],'additional_observation':c['追加観測要求群'],
            'ambiguity_count':len(c['識別不能群']),'quarantine_count':len(c['係争中原理群']),
            'hold_reasons':c['断定保留理由群']}

def run_batch(stage,full_digest=False):
    assert_identity();before=state_digest();ids=e.識別子.状態を書き出す();full_before=ledger_digests() if full_digest else None
    result={}
    for p in protocol['track_A']['probes']:
        if p.get('interface','').startswith('engine.'):
            out=m.排気系.排出する(e.照会(格子観測(p['input'])))
        else:out=m.照会する(外部入力(内容=p['input'],対象系境界=p['boundary']))
        raw(stage+'/'+p['name'],out);result[p['name']]=norm(out)
        check(stage+'/'+p['name']+'/non_learning_label',out.内容['学習成立状態']=='適用外')
        if p['expected_prediction']:
            expected={k:[v] for k,v in p['expected_prediction'].items()}
        else:expected={}
        check(stage+'/'+p['name']+'/expected_prediction',result[p['name']]['predictions']==expected,{'expected':expected,'actual':result[p['name']]['predictions']})
        if stage=='baseline':check(stage+'/'+p['name']+'/expected_external_status',out.状態==p['expected_status'])
        if p.get('expect_additional_observation'):check(stage+'/'+p['name']+'/observation_request_preserved',bool(out.内容['追加観測要求群']))
    after=state_digest();ids_after=e.識別子.状態を書き出す()
    check(stage+'/learned_state_readonly',before==after,{'before':before,'after':after})
    expected_ids={**ids,'照会':ids.get('照会',0)+len(result),'学習判定':ids.get('学習判定',0)+len(result)}
    check(stage+'/only_query_counters_advance',expected_ids==ids_after)
    if full_digest:
        full_after=ledger_digests();check(stage+'/all_public_ledgers_exact_readonly',full_before==full_after)
        dump(stage+'-ledger-digests.json',{'before':full_before,'after':full_after})
    item={'stage':stage,'identity':identities,'state':before,'probes':result}
    batches.append(item);dump('probe-batches.json',batches)
    return result

def current_principles(boundary=None):
    state=set(e.状態.現在状態.values());found=[]
    records=e.台帳.取得('原理台帳')
    for r in records:
        if r.原理識別子 in state and (boundary is None or r.対象系境界==boundary):found.append(r)
    del records;gc.collect();return found

def pick(boundary,relation,conditions,result):
    matches=[p for p in current_principles(boundary) if p.関係型==relation and p.条件経路群==conditions and p.結果経路==result]
    assert len(matches)==1,(boundary,relation,conditions,result,len(matches))
    return matches[0]

def audit_experiences(stage):
    records=e.台帳.取得('観測台帳')
    out=[]
    for i,ref in enumerate(seed_refs):
        r=records[i];out.append({'kind':'seed','ref':r.経験識別子,'exact_record':digest(r)==ref['sha256']})
    for i,row in enumerate(rows):
        r=records[len(seed_refs)+i];args=row['既存interface入力']
        out.append({'kind':'rule','index':i,'rule':row['規則ID'],'ref':r.経験識別子,'exact_payload':r.原入力==args['内容'],'exact_target':r.対象==args['対象'],'exact_provenance':json.loads(r.対象)==row['原文・出典・完全記録'],'exact_boundary':r.対象系境界==args['対象系境界']})
    check(stage+'/all_seed_and_rule_memory_exact',all(all(v for k,v in row.items() if k.startswith('exact_')) for row in out))
    dump(stage+'-memory-retention.json',out);del records;gc.collect()

def audit_cycle(stage):
    observations=e.台帳.取得('観測台帳');obs_ids={r.経験識別子 for r in observations};obs_boundary={r.経験識別子:r.対象系境界 for r in observations};obs_maps={r.経験識別子:{o.経路:o.値 for o in r.観測群 if o.推論対象} for r in observations}
    check(stage+'/structural_metadata_excluded',all(not o.推論対象 for r in observations for o in r.観測群 if o.値型=='構造' or (o.経路 and o.経路[-1]=='@HDS:要素数')))
    del observations;gc.collect()
    doubts=e.台帳.取得('懐疑台帳');doubt_ids={r.懐疑識別子 for r in doubts};check(stage+'/doubt_memory_refs',all(r.経験参照 in obs_ids and all(x in obs_ids for x in r.参照経験群) for r in doubts));del doubts;gc.collect()
    inf=e.台帳.取得('推論記録台帳');candidate_ids={r['候補参照'] for r in inf}
    check(stage+'/inference_requires_doubt_and_memory',all(r['懐疑参照群'] and all(x in doubt_ids for x in r['懐疑参照群']) and all(x in obs_ids for x in r['経験参照群']) and len(r['条件経路群'])<=2 for r in inf));del inf;gc.collect()
    evidence=e.台帳.取得('証拠台帳');fit={r['候補参照'] for r in evidence if '候補参照'in r and r.get('判定')=='適合'}
    check(stage+'/validation_support_minimum',all(len(r.get('支持参照群',()))>=3 and not r.get('反証参照群') for r in evidence if r.get('判定')=='適合'))
    del evidence;gc.collect()
    decisions=e.台帳.取得('判断台帳');admitted={r['候補参照'] for r in decisions if r.get('採否')=='試行採用'};check(stage+'/admission_only_validated_candidates',admitted<=fit<=candidate_ids);del decisions;gc.collect()
    principles=e.台帳.取得('原理台帳');principle_ids={r.原理識別子 for r in principles}
    check(stage+'/principle_condition_diversity',all(len({digest(tuple(obs_maps[ref][path] for path in r.条件経路群)) for ref in r.根拠参照群 if all(path in obs_maps[ref] for path in r.条件経路群)})>=2 for r in principles))
    check(stage+'/principle_evidence_boundary',all(all(x in obs_ids and obs_boundary[x]==r.対象系境界 for x in r.根拠参照群+r.反証参照群) for r in principles));del principles;gc.collect()
    updates=e.台帳.取得('更新台帳');update_ids={r['更新識別子'] for r in updates};check(stage+'/adaptation_principle_refs',all(r.get('原理参照') in principle_ids for r in updates));del updates;gc.collect()
    feedback=e.台帳.取得('全体帰還台帳');closed={r['学習参照'] for r in feedback if r.get('種別')=='実行完了'};del feedback;gc.collect()
    processes=e.台帳.取得('学習過程台帳')
    check(stage+'/full_cycle_refs',all(p.経験参照 in obs_ids and p.学習識別子 in closed and all(x in doubt_ids for x in p.懐疑参照群) and all(x in candidate_ids for x in p.推論候補参照群) and all(x in principle_ids for x in p.採用原理参照群+p.再開放原理参照群+p.係争化原理参照群) and all(x in update_ids for x in p.更新記録参照群) and all(obs_boundary[x]==p.対象系境界 for x in p.保持記憶参照群) for p in processes))
    dump(stage+'-cycle-summary.json',{'observations':len(obs_ids),'doubt_records':len(doubt_ids),'candidates':len(candidate_ids),'validated_fit':len(fit),'admission_decisions':len(admitted),'principles':len(principle_ids),'updates':len(update_ids),'completed_cycles':len(closed)})

def lifecycle_query(boundary,content,label):
    before=state_digest();ids=e.識別子.状態を書き出す();out=m.照会する(外部入力(内容=content,対象系境界=boundary));raw(label,out)
    check(label+'/query_readonly',before==state_digest())
    expected_ids={**ids,'照会':ids.get('照会',0)+1,'学習判定':ids.get('学習判定',0)+1}
    check(label+'/only_query_counters_advance',expected_ids==e.識別子.状態を書き出す())
    assert_identity();return out

try:
    # Keep all ordinary-output baseline probes free of quarantined/ambiguous controls.
    for group in protocol['track_A']['seed_order']:
        for i,content in enumerate(group['rows']):
            out,proc=learn(group['boundary'],content,'seed/'+group['boundary']+'/'+str(i),grid=group['interface'].startswith('engine.'))
            record=e.台帳.取得('観測台帳')[-1];seed_refs.append({'ref':record.経験識別子,'sha256':digest(record)})
    baseline_state=e.状態.現在状態
    baseline_state_history=e.状態.履歴()
    baseline_principles={p.原理識別子:digest(p) for p in current_principles()}
    dump('baseline-current-principles.json',current_principles())
    baseline=run_batch('baseline',True)
    baseline_prefixes=json.loads((a.out/'baseline-ledger-digests.json').read_text())['before']
    baseline_ok=all(x['passed'] for x in checks)
    dump('baseline-result.json',{'passed':baseline_ok,'checks':checks,'seed_refs':seed_refs})
    if not baseline_ok:raise RuntimeError('Pre-registered clean baseline failed; no67 intervention performed')
    for i,row in enumerate(rows):
        t=time.monotonic();args=row['既存interface入力'];out,proc=learn(args['対象系境界'],args['内容'],f'rule/{i+1:02d}',args=args)
        rule_refs.append({'index':i,'rule':row['規則ID'],'experience':proc.経験参照})
        result=run_batch(f'after-{i+1:02d}',full_digest=(i==66))
        check(f'after-{i+1:02d}/baseline_lineages_current',all(e.状態.現在状態.get(k)==v for k,v in baseline_state.items()))
        print(json.dumps({'completed':i+1,'seconds':round(time.monotonic()-t,3),'equality_status':result['equality_unseen']['status'],'equality_value':result['equality_unseen']['predictions'],'memory':e.台帳.件数('観測台帳'),'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},ensure_ascii=False),flush=True)
    audit_experiences('track-A');audit_cycle('track-A')
    current_ids={p.原理識別子:digest(p) for p in current_principles()}
    check('track-A/prior_state_history_append_only',e.状態.履歴()[:len(baseline_state_history)]==baseline_state_history)
    check('track-A/prior_principles_exact',all(current_ids.get(k)==v for k,v in baseline_principles.items()))
    last=batches[-1]['probes']
    changes=[{'checkpoint':b['stage'],'probe':name,'before':baseline[name],'after':value} for b in batches[1:] for name,value in b['probes'].items() if value!=baseline[name]]
    response_failures=[x for x in changes if baseline[x['probe']]['status']=='出力' and baseline[x['probe']]['predictions'] and x['after']['status']!='出力']
    # Link exact foreign causes through public current principles, not filtered predictions.
    current=current_principles();dump('track-A-current-principles.json',current)
    cause_index={p.原理識別子:{'boundary':p.対象系境界,'relation':p.関係型,'conditions':p.条件経路群,'result':p.結果経路,'state':p.状態.value,'adoption':p.採用状態.value} for p in current}
    dump('track-A-principle-boundary-index.json',cause_index)
    trackA={'completed67':True,'seed_count':len(seed_refs),'same_instance':True,'checkpoints':len(batches),'probes_per_checkpoint':10,'prediction_checks_passed':all(x['passed'] for x in checks if x['name'].endswith('/expected_prediction')),'all_mechanical_checks_passed':all(x['passed'] for x in checks),'successful_output_retention_passed':not response_failures,'first_successful_output_failure':response_failures[0] if response_failures else None,'final_probes':last,'all_probe_changes':changes,'checks':checks.copy(),'rule_refs':rule_refs,'state':state_digest(),'elapsed_seconds':time.monotonic()-start}
    dump('track-A-result.json',trackA)
    print(json.dumps({'track_A_frozen':True,'prediction_retained':trackA['prediction_checks_passed'],'usable_output_retained':trackA['successful_output_retention_passed'],'first_failure':None if not response_failures else response_failures[0]['checkpoint']},ensure_ascii=False),flush=True)
    del current,current_ids;gc.collect()
    # Explicitly separate later mutating contract diagnostics from frozen retention evidence.
    b='監査_係争'
    for i in (1,2,3):learn(b,{'x':i,'y':i},f'lifecycle/dispute/seed{i}')
    old=pick(b,'同値関係',(('x',),),('y',));raw('lifecycle/dispute/original',old)
    _,p4=learn(b,{'x':1,'y':9},'lifecycle/dispute/first_counterexample')
    isolated=pick(b,'同値関係',(('x',),),('y',));raw('lifecycle/dispute/isolated',isolated)
    check('lifecycle/dispute/first_isolates',isolated.採用状態.value=='隔離' and isolated.版==old.版+1 and p4.経験参照 in isolated.反証参照群)
    _,p5=learn(b,{'x':1,'y':8},'lifecycle/dispute/late_counterexample')
    later=pick(b,'同値関係',(('x',),),('y',));raw('lifecycle/dispute/after_late',later)
    check('lifecycle/dispute/late_does_not_revise_quarantined_lineage',digest(isolated)==digest(later))
    rejected=False
    try:m.係争を解決する(later.原理識別子,'復帰','Synthetic fixture: omitted latest evidence must be rejected','source-contract harness')
    except ValueError as ex:rejected=True;raw('lifecycle/dispute/blind_restoration_error',{'type':'ValueError','message':str(ex)})
    check('lifecycle/dispute/blind_restoration_rejected',rejected)
    restored=m.係争を解決する(later.原理識別子,'復帰','Synthetic contract fixture only: explicitly review these two manufactured contradictions; no ARC rule evidence excluded','source-contract harness',(p4.経験参照,p5.経験参照))
    raw('lifecycle/dispute/explicit_restoration',restored)
    check('lifecycle/dispute/restoration_scoped_and_exact',restored.採用状態.value=='有効' and set(restored.除外反証参照群)=={p4.経験参照,p5.経験参照} and restored.系譜識別子==old.系譜識別子)
    r=lifecycle_query(b,{'x':9},'lifecycle/dispute/restored_query');check('lifecycle/dispute/restored_prediction',prediction_map(r).get('y')==[9])
    b='監査_特殊化'
    for i in (1,2,3):learn(b,{'x':i,'mode':0,'y':10*i},f'lifecycle/specialization/seed{i}')
    parent=pick(b,'決定的対応関係',(('x',),),('y',));raw('lifecycle/specialization/original_parent',parent)
    _,sp=learn(b,{'x':1,'mode':1,'y':11},'lifecycle/specialization/counterexample')
    children=[p for p in current_principles(b) if p.結果経路==('y',) and set(p.条件経路群)=={('mode',),('x',)}]
    raw('lifecycle/specialization/children',children)
    history=e.台帳.取得('原理台帳');local=[p for p in history if p.対象系境界==b];del history;gc.collect();raw('lifecycle/specialization/local_history',local)
    check('lifecycle/specialization/child_parent_and_reopening',len(children)==1 and children[0].親原理参照 is not None and bool(sp.再開放原理参照群) and any(p.系譜識別子==parent.系譜識別子 and p.状態.value=='再開放済み' and p.採用状態.value=='新版移行済み' for p in local))
    r=lifecycle_query(b,{'x':1,'mode':1},'lifecycle/specialization/query');check('lifecycle/specialization/child_predicts11',prediction_map(r).get('y')==[11])
    b='監査_識別不能'
    for i in (1,2,3):learn(b,{'x':i,'z':i,'y':10+i},f'lifecycle/ambiguity/seed{i}')
    r=lifecycle_query(b,{'x':1,'z':2},'lifecycle/ambiguity/conflicting_query')
    local_ids={p.原理識別子 for p in current_principles(b)}
    local_ambiguity=[z for z in r.内容['識別不能群'] if set(z['原理参照群'])&local_ids]
    check('lifecycle/ambiguity/local_candidates_unidentified',bool(local_ambiguity))
    check('lifecycle/ambiguity/conflicting_y_not_confirmed','y' not in prediction_map(r) and any(z['結果経路']==('y',) and set(z['候補値群'])=={11,12} for z in r.内容['競合群']))
    b='監査_不成立'
    for i,(x,y) in enumerate(((0,0),(0,1),(1,0),(1,1))):out,pr=learn(b,{'x':x,'y':y},f'lifecycle/non_establishment/{i}')
    check('lifecycle/non_establishment/distinct_status',pr.学習成立状態.value=='不成立確認',pr.学習成立状態.value)
    b='監査_能力境界'
    for i in (1,2,3):learn(b,{'a':i,'b':i+10,'c':i+20,'d':i+30},f'lifecycle/residual/{i}')
    residuals=[r for r in e.台帳.取得('残差台帳') if r.get('対象系境界')==b and r.get('種別')=='実装能力境界'];raw('lifecycle/residual/local_records',residuals)
    check('lifecycle/residual/max2_record_once',len(residuals)==1 and residuals[0]['最大条件数']==2)
    audit_experiences('after-lifecycle')
    check('after-lifecycle/all_protected_source_bytes_unchanged',all((a.root/rel).is_file() and fh(a.root/rel)==h for rel,h in protected.items()))
    check('after-lifecycle/protocol_unchanged',fh(a.protocol)==freeze['protocol_sha256'])
    dump('final-report.json',{'behavioral_retention_outcome':'passed_bounded_probes' if trackA['successful_output_retention_passed'] else 'FAILED_previous_usable_outputs_became_HOLD','track_A':{k:v for k,v in trackA.items() if k not in ('all_probe_changes','checks')},'lifecycle_checks':[x for x in checks if x['name'].startswith('lifecycle/')],'all_checks':checks,'identity':identities,'final_state':state_digest(),'elapsed_seconds':time.monotonic()-start,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'native_save_or_reload_attempted':False,'official_rescore_attempted':False,'whole_arc_retention_claim':False,'failed_checks':[x for x in checks if not x['passed']]})
    print(json.dumps({'finished':True,'output_retention_failed':not trackA['successful_output_retention_passed'],'failed_checks':[x['name'] for x in checks if not x['passed']],'seconds':time.monotonic()-start},ensure_ascii=False),flush=True)
except BaseException:
    dump('failure.json',{'traceback':traceback.format_exc(),'completed_rule_inputs':len(rule_refs),'completed_learning_calls':len(learning_calls),'checks':checks,'state':state_digest(),'elapsed_seconds':time.monotonic()-start})
    raise
finally:rawfile.close()
