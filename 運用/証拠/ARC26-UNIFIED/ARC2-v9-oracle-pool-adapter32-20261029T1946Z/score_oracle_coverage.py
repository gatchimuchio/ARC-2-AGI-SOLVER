from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

def sha(b: bytes) -> str: return hashlib.sha256(b).hexdigest()
def grid_sha(grid): return sha(json.dumps(grid,separators=(',',':')).encode())
ap=argparse.ArgumentParser()
ap.add_argument('--baseline-pool',required=True); ap.add_argument('--candidate-pool',required=True)
ap.add_argument('--input',required=True); ap.add_argument('--prereg',required=True)
ap.add_argument('--challenges',required=True); ap.add_argument('--solutions',required=True)
ap.add_argument('--output',required=True)
ns=ap.parse_args()
bp=Path(ns.baseline_pool); cp=Path(ns.candidate_pool); ip=Path(ns.input); pp=Path(ns.prereg)
chp=Path(ns.challenges); sop=Path(ns.solutions)
for path,expected in [(chp,'779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5'),(sop,'9f07a38bd25af5e83aa5bf85c5cb1a1fefdb30f6a755256fa65429e697ca97f9')]:
    if sha(path.read_bytes()) != expected: raise SystemExit(f'training data hash mismatch: {path.name}')
baseline=json.loads(bp.read_text(encoding='utf-8')); candidate=json.loads(cp.read_text(encoding='utf-8'))
runtime=json.loads(ip.read_text(encoding='utf-8')); prereg=json.loads(pp.read_text(encoding='utf-8'))
solutions=json.loads(sop.read_text(encoding='utf-8')); challenges=json.loads(chp.read_text(encoding='utf-8'))
alias_to_id={item['runtime_alias']:item['source_task_id'] for item in prereg['task_selection_manifest']}
if set(runtime)!=set(baseline['predictions']) or set(runtime)!=set(candidate['predictions']): raise SystemExit('cohort aliases differ')
totals={'test_grids':0,'baseline_pool_oracle_hits':0,'candidate_pool_oracle_hits':0,
        'baseline_first_two_hits':0,'candidate_first_two_hits':0,
        'baseline_selection_misses':0,'candidate_selection_misses':0,
        'baseline_not_in_runtime_pool':0,'candidate_not_in_runtime_pool':0,
        'pool_oracle_gain':0,'pool_oracle_loss':0,'first_two_gain':0,'first_two_loss':0}
per_grid=[]
for alias,task in runtime.items():
    source_id=alias_to_id[alias]
    if source_id not in solutions or source_id not in challenges: raise SystemExit(f'missing source challenge: {source_id}')
    gold=solutions[source_id]
    if len(gold)!=len(task['test']): raise SystemExit(f'test count mismatch: {alias}')
    for ti,solution in enumerate(gold):
        g=grid_sha(solution)
        btest=baseline['predictions'][alias][ti]; ctest=candidate['predictions'][alias][ti]
        bpool={x['prediction_sha256'] for x in btest['accepted_pool_predictions']}
        cpool={x['prediction_sha256'] for x in ctest['accepted_pool_predictions']}
        bfirst={x['prediction_sha256'] for x in btest['first_two_distinct_predictions']}
        cfirst={x['prediction_sha256'] for x in ctest['first_two_distinct_predictions']}
        bhit=g in bpool; chit=g in cpool; btop=g in bfirst; ctop=g in cfirst
        totals['test_grids']+=1
        totals['baseline_pool_oracle_hits']+=int(bhit); totals['candidate_pool_oracle_hits']+=int(chit)
        totals['baseline_first_two_hits']+=int(btop); totals['candidate_first_two_hits']+=int(ctop)
        totals['baseline_selection_misses']+=int(bhit and not btop); totals['candidate_selection_misses']+=int(chit and not ctop)
        totals['baseline_not_in_runtime_pool']+=int(not bhit); totals['candidate_not_in_runtime_pool']+=int(not chit)
        totals['pool_oracle_gain']+=int(chit and not bhit); totals['pool_oracle_loss']+=int(bhit and not chit)
        totals['first_two_gain']+=int(ctop and not btop); totals['first_two_loss']+=int(btop and not ctop)
        per_grid.append({'runtime_alias':alias,'test_index':ti,'baseline_pool_oracle_hit':bhit,
                         'candidate_pool_oracle_hit':chit,'baseline_first_two_hit':btop,'candidate_first_two_hit':ctop,
                         'baseline_selection_miss':bool(bhit and not btop),'candidate_selection_miss':bool(chit and not ctop)})
out={'schema':'arc2-runtime-pool-oracle-coverage-v1','track':'ARC2','scored_at_utc':datetime.now(timezone.utc).isoformat(),
     'diagnostic_scope':'Offline public-training labels after prediction freeze; previously opened/exposure_unknown development cohort; exploratory only; not a fresh validation or official score.',
     'labels_read_after_this_pool_freeze':True,'evaluation_labels_read':False,'runtime_received_labels':False,
     'cohort_input_sha256':sha(ip.read_bytes()),'cohort_tasks':len(runtime),'test_grids':totals['test_grids'],
     'baseline_pool_sha256':sha(bp.read_bytes()),'candidate_pool_sha256':sha(cp.read_bytes()),
     'prereg_sha256':sha(pp.read_bytes()),'training_challenges_sha256':sha(chp.read_bytes()),'training_solutions_sha256':sha(sop.read_bytes()),
     'candidate_cap':32,'metrics':totals,'per_grid':per_grid}
Path(ns.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\\n',encoding='utf-8',newline='\\n')
print(json.dumps({'tasks':out['cohort_tasks'],'grids':out['test_grids'],'metrics':totals,'output_sha256':sha(Path(ns.output).read_bytes())},ensure_ascii=False))
