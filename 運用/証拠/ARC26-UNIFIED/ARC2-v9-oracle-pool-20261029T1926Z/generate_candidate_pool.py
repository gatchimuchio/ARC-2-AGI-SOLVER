from __future__ import annotations
import argparse, hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

ap=argparse.ArgumentParser()
ap.add_argument('--repo-root',required=True)
ap.add_argument('--input',required=True)
ap.add_argument('--output',required=True)
ap.add_argument('--cohort-sha256',required=True)
ns=ap.parse_args()
repo=Path(ns.repo_root).resolve(); sys.path.insert(0,str(repo))
from 接続.ARC2 import arc_proof_search
from 接続.ARC2.汎用プログラム帰納候補 import 汎用プログラム帰納候補群

def grid_hash(g):
    obj=[[int(x) for x in row] for row in g.tolist()]
    return sha(json.dumps(obj,separators=(',',':')).encode())

data=json.loads(Path(ns.input).read_text(encoding='utf-8'))
result={}
for alias, runtime_task in data.items():
    if any(set(test) != {'input'} for test in runtime_task['test']):
        raise SystemExit(f'test output leakage in input: {alias}')
    train=[{'input':p['input'],'output':p['output']} for p in runtime_task['train']]
    model_task={'train':train,'test':[]}
    generated=[c for c in arc_proof_search.synthesize(model_task) if c.exact]
    adapter=汎用プログラム帰納候補群(train)
    accepted=adapter._候補群
    per_test=[]
    for ti,test in enumerate(runtime_task['test']):
        grid=arc_proof_search.as_grid(test['input'])
        def predictions(candidates):
            unique={}
            for rank,cand in enumerate(candidates,1):
                pred=arc_proof_search.safe(cand.function,grid)
                if pred is None: continue
                digest=grid_hash(pred)
                info={'program':cand.name,'family':cand.name.split('|colors=',1)[0],
                      'rank':rank,'cost':cand.cost}
                unique.setdefault(digest,[]).append(info)
            return [{'prediction_sha256':digest,'programs':programs}
                    for digest,programs in unique.items()]
        full=predictions(generated); capped=predictions(accepted)
        submitted=[]; seen=set()
        for rank,cand in enumerate(accepted,1):
            pred=arc_proof_search.safe(cand.function,grid)
            if pred is None: continue
            digest=grid_hash(pred)
            if digest in seen: continue
            seen.add(digest)
            submitted.append({'prediction_sha256':digest,'program':cand.name,'rank':rank})
            if len(submitted)==2: break
        per_test.append({'test_index':ti,'generated_exact_programs':len(generated),
                         'adapter_accepted_exact_programs':len(accepted),
                         'full_pool_unique_predictions':len(full),
                         'adapter_pool_unique_predictions':len(capped),
                         'first_two_distinct_predictions':submitted,
                         'full_pool_predictions':full,
                         'adapter_pool_predictions':capped})
    result[alias]=per_test
rev=subprocess.run(['git','rev-parse','HEAD'],cwd=repo,text=True,capture_output=True,check=True).stdout.strip()
source_files=['接続/ARC2/arc_proof_search.py','接続/ARC2/汎用プログラム帰納候補.py']
doc={'schema':'arc2-generic-pool-freeze-v1','track':'ARC2',
     'generated_at_utc':datetime.now(timezone.utc).isoformat(),
     'purpose':'Offline oracle-coverage diagnostic on an already-opened development cohort; no validation claim.',
     'cohort_relationship':'previously-scored development cohort; exposure_unknown; exploratory only',
     'cohort_input_sha256':ns.cohort_sha256,'cohort_tasks':len(data),
     'test_grids':sum(len(x['test']) for x in data.values()),
     'runtime_input_has_test_outputs':False,'solution_file_read':False,
     'runtime_aliases_are_offline_alignment_only':True,'repo_root':str(repo),
     'git_head':rev,'source_sha256':{f:sha((repo/f).read_bytes()) for f in source_files},
     'candidate_family':'train-exact symbolic program induction',
     'pool_semantics':'full = every exact synthesized program returned by synthesize; adapter = exact candidates accepted up to the runtime cap of 32; output hashes only',
     'predictions':result}
Path(ns.output).write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'git_head':rev,'tasks':doc['cohort_tasks'],'test_grids':doc['test_grids'],
                  'sha256':sha(Path(ns.output).read_bytes()),
                  'source_sha256':doc['source_sha256']},ensure_ascii=False))
