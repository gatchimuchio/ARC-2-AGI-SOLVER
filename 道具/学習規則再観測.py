#!/usr/bin/env python3
"""Frozen existing-interface observation only; no source or engine mutation."""
from pathlib import Path
import argparse,dataclasses,hashlib,json,sys,time,traceback,resource,gc

p=argparse.ArgumentParser()
p.add_argument('--root',type=Path,required=True)
p.add_argument('--experiences',type=Path,required=True)
p.add_argument('--protocol',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
a.out.mkdir(exist_ok=False)
def dump(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def filehash(path):return hashlib.sha256(path.read_bytes()).hexdigest()
rows=[json.loads(line) for line in a.experiences.read_text(encoding='utf-8').splitlines()]
assert len(rows)==67 and len({r['規則ID'] for r in rows})==67
protocol=json.loads(a.protocol.read_text(encoding='utf-8'))
assert __debug__, 'run ordinary Python; assertions are required'
core_files=sorted((a.root/'HDS/学習系統/v0.4.2/hds学習系統').glob('*.py'))
assert len(core_files)==12
core_manifest={str(f.relative_to(a.root)):{'sha256':filehash(f),'git_blob_sha1':hashlib.sha1(b'blob '+str(f.stat().st_size).encode()+b'\0'+f.read_bytes()).hexdigest()} for f in core_files}
sys.path.insert(0,str(a.root/'HDS/学習系統/v0.4.2'))
from hds学習系統 import HDS学習系統,外部入力
import hds学習系統
from hds学習系統.吸気系 import 最小吸気系
intake=最小吸気系()
preflight=[intake.取り込む(外部入力(**row['既存interface入力'])) for row in rows]
paths={fact.経路 for item in preflight for fact in item.観測群 if fact.推論対象}
n=len(paths)
freeze={'experience_sha256':filehash(a.experiences),'protocol_sha256':filehash(a.protocol),
        'observer_sha256':filehash(Path(__file__)),'protocol':protocol,'row_count':len(rows),
        'input_order':[r['規則ID'] for r in rows],
        'ordered_native_inputs_sha256':hashlib.sha256(json.dumps([r['既存interface入力'] for r in rows],ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
        'core12':core_manifest,
        'imported_hds_package':hds学習系統.__file__,
        'intake_preflight':{'union_inferable_paths':sorted(paths),'union_path_count':n,'maximum_scalar_count':max(sum(f.推論対象 for f in x.観測群) for x in preflight),'max2_combinations_per_step':n*((n-1)+(n-1)*(n-2)//2)},
        'runner_limits':{'CPU':resource.getrlimit(resource.RLIMIT_CPU),'address_space':resource.getrlimit(resource.RLIMIT_AS),'added_wall_timeout':None},
        'configuration':{'HDS学習系統':'default constructor','最小支持数':3,'最大条件数':2},
        'source_root':str(a.root),'official_data_read_by_this_process':False}
dump(a.out/'freeze.json',freeze)
machine=HDS学習系統()
assert machine.エンジン.最小支持数==3 and machine.エンジン.最大条件数==2
machine.保存する(a.out/'initial-native-state.json')
start=time.monotonic();sidecar={};proof=[];summaries=[]
with (a.out/'raw-native-responses.jsonl').open('w',encoding='utf-8') as raw:
    for i,row in enumerate(rows):
        args=row['既存interface入力']
        assert args['文脈']=={} and isinstance(args['対象'],str)
        assert json.loads(args['対象'])==row['原文・出典・完全記録']
        before=time.monotonic()
        try:
            result=machine.処理する(外部入力(**args))
        except Exception:
            (a.out/'native-error.txt').write_text(traceback.format_exc(),encoding='utf-8')
            dump(a.out/'failure.json',{'stage':'native call','input_index':i,'completed':len(summaries),'elapsed_seconds':time.monotonic()-start})
            machine.保存する(a.out/'partial-native-state.json')
            raise
        out=dataclasses.asdict(result)
        raw.write(json.dumps(out,ensure_ascii=False)+'\n');raw.flush()
        ref=out['追跡情報']['経験参照']
        sidecar[ref]={'規則ID':row['規則ID'],'原文・出典・完全記録':row['原文・出典・完全記録']}
        stored=machine.エンジン.台帳.取得('観測台帳')[-1]
        check={'input_index':i,'規則ID':row['規則ID'],'経験参照':ref,
               '原入力完全一致':stored.原入力==args['内容'],'対象文字列完全一致':stored.対象==args['対象'],
               '原文出典アーカイブ復元一致':json.loads(stored.対象)==row['原文・出典・完全記録'],
               '対象系境界一致':stored.対象系境界==args['対象系境界']}
        assert all(v for k,v in check.items() if k.endswith('一致'))
        proof.append(check)
        summaries.append({'input_index':i,'規則ID':row['規則ID'],'経験参照':ref,'状態':out['状態'],
                          '学習成立状態':out['内容']['学習成立状態'],
                          '台帳件数':out['追跡情報']['台帳件数'],
                          '有効原理数':len(out['内容']['有効原理群']),
                          'native_call_seconds':time.monotonic()-before})
        print(json.dumps({'completed':i+1,'rule':row['規則ID'],'seconds':round(summaries[-1]['native_call_seconds'],3),'principles':summaries[-1]['有効原理数']},ensure_ascii=False),flush=True)
dump(a.out/'provenance-sidecar.json',sidecar)
dump(a.out/'retention-checks-before-save.json',proof)
# Preserve exact native semantics; avoid retaining a duplicate full ledger during native save.
gc.collect()
machine.保存する(a.out/'final-native-state.json')
snapshot=machine.エンジン.台帳.JSON相当()
ledger_counts={k:len(v) for k,v in snapshot.items()}
dump(a.out/'full-ledger-snapshot.json',snapshot)
del snapshot,machine,intake,preflight
gc.collect()
reloaded=HDS学習系統.読み込む(a.out/'final-native-state.json')
again=reloaded.エンジン.台帳.JSON相当()
dump(a.out/'reloaded-ledger-snapshot.json',again)
assert filehash(a.out/'full-ledger-snapshot.json')==filehash(a.out/'reloaded-ledger-snapshot.json')
del again
gc.collect()
reloaded.保存する(a.out/'reloaded-native-state.json')
assert (a.out/'final-native-state.json').read_bytes()==(a.out/'reloaded-native-state.json').read_bytes()
assert len(reloaded.エンジン.台帳.取得('観測台帳'))==67
for row,stored in zip(rows,reloaded.エンジン.台帳.取得('観測台帳')):
    assert stored.原入力==row['既存interface入力']['内容']
    assert stored.対象==row['既存interface入力']['対象']
    assert json.loads(stored.対象)==row['原文・出典・完全記録']
    assert sidecar[stored.経験識別子]['規則ID']==row['規則ID']
report={'completed_inputs':len(summaries),'elapsed_seconds':time.monotonic()-start,
        'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'retention_checks':proof,'call_summaries':summaries,
        'native_ledger_counts':ledger_counts,
        'full_native_snapshot_reload_equal':True,
        'saved_native_bytes_reload_equal':True,'all67_payload_and_provenance_reload_equal':True,
        'core12_sha256_unchanged':all(filehash(a.root/rel)==v['sha256'] for rel,v in core_manifest.items()),
        'files':{f.name:{'bytes':f.stat().st_size,'sha256':filehash(f)} for f in a.out.iterdir() if f.is_file()}}
dump(a.out/'observation-report.json',report)
assert report['core12_sha256_unchanged']
assert filehash(a.experiences)==freeze['experience_sha256']
assert filehash(a.protocol)==freeze['protocol_sha256']
print(json.dumps({'completed_inputs':67,'elapsed_seconds':report['elapsed_seconds'],'reload_equal':True,'native_ledger_counts':report['native_ledger_counts']},ensure_ascii=False),flush=True)
