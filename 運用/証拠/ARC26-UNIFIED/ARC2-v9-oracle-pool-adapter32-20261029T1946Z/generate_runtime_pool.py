from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

def sha(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
ap=argparse.ArgumentParser()
ap.add_argument('--repo-root',required=True); ap.add_argument('--input',required=True)
ap.add_argument('--output',required=True); ap.add_argument('--rows',required=True)
ap.add_argument('--cohort-sha256',required=True); ap.add_argument('--label',required=True)
ns=ap.parse_args(); repo=Path(ns.repo_root).resolve(); sys.path.insert(0,str(repo))
from 接続.ARC2 import arc_proof_search
from 接続.ARC2.汎用プログラム帰納候補 import 汎用プログラム帰納候補群

def grid_hash(g):
    obj=[[int(x) for x in row] for row in g.tolist()]
    return sha(json.dumps(obj,separators=(',',':')).encode())

data=json.loads(Path(ns.input).read_text(encoding='utf-8'))
rows_path=Path(ns.rows); rows_path.write_text('',encoding='utf-8',newline='\n')
all_results={}; start=time.perf_counter()
for i,(alias,runtime_task) in enumerate(data.items(),1):
    if any(set(test) != {'input'} for test in runtime_task['test']):
        raise SystemExit(f'test output leakage in input: {alias}')
    train=[{'input':p['input'],'output':p['output']} for p in runtime_task['train']]
    candidates=[c for c in arc_proof_search.synthesize({'train':train,'test':[]}) if c.exact][:32]
    by_test=[]
    for ti,test in enumerate(runtime_task['test']):
        grid=arc_proof_search.as_grid(test['input']); unique={}; first_two=[]
        for rank,cand in enumerate(candidates,1):
            pred=arc_proof_search.safe(cand.function,grid)
            if pred is None: continue
            digest=grid_hash(pred)
            info={'program':cand.name,'family':cand.name.split('|colors=',1)[0],'rank':rank,'cost':cand.cost}
            unique.setdefault(digest,[]).append(info)
            if digest not in {x['prediction_sha256'] for x in first_two} and len(first_two)<2:
                first_two.append({'prediction_sha256':digest,'program':cand.name,'rank':rank})
        by_test.append({'test_index':ti,'test_input_sha256':sha(json.dumps(test['input'],separators=(',',':')).encode()),
                        'accepted_exact_program_count':len(candidates),'unique_predictions_in_accepted_pool':len(unique),
                        'first_two_distinct_predictions':first_two,
                        'accepted_pool_predictions':[{'prediction_sha256':h,'programs':p} for h,p in unique.items()]})
    row={'runtime_alias':alias,'tests':by_test}
    all_results[alias]=by_test
    with rows_path.open('a',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
    print(f'{ns.label}: {i}/{len(data)} {alias}',flush=True)
rev=subprocess.run(['git','rev-parse','HEAD'],cwd=repo,text=True,capture_output=True,check=True).stdout.strip()
source_files=['接続/ARC2/arc_proof_search.py','接続/ARC2/汎用プログラム帰納候補.py']
doc={'schema':'arc2-generic-runtime-pool-freeze-v1','track':'ARC2','generated_at_utc':datetime.now(timezone.utc).isoformat(),
     'purpose':'Offline oracle-coverage diagnostic on an already-opened development cohort; no validation claim.',
     'cohort_relationship':'previously-scored development cohort; exposure_unknown; exploratory only',
     'cohort_input_sha256':ns.cohort_sha256,'cohort_tasks':len(data),'test_grids':sum(len(x['test']) for x in data.values()),
     'runtime_input_has_test_outputs':False,'solution_file_read':False,'runtime_aliases_are_offline_alignment_only':True,
     'repo_label':ns.label,'git_head':rev,'source_sha256':{f:sha((repo/f).read_bytes()) for f in source_files},
     'candidate_cap':32,'synthesize_calls_per_task':1,'runtime_pool_semantics':'first 32 exact programs returned by synthesize, matching 汎用プログラム帰納候補群; first two distinct test predictions are current selection output',
     'elapsed_seconds':round(time.perf_counter()-start,3),'row_log_sha256':sha(rows_path.read_bytes()),'predictions':all_results}
output=Path(ns.output); output.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'label':ns.label,'git_head':rev,'tasks':doc['cohort_tasks'],'test_grids':doc['test_grids'],'elapsed_seconds':doc['elapsed_seconds'],'sha256':sha(output.read_bytes()),'rows_sha256':doc['row_log_sha256']},ensure_ascii=False),flush=True)
