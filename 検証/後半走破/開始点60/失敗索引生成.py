"""Index original replay events without rewriting or inferring unseen causes."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('replay',type=Path);a=p.parse_args()
raw=(a.replay/'raw.jsonl.gz').read_bytes()
raw_hash=hashlib.sha256(gzip.decompress(raw)).hexdigest()
events=[];holds=[];types=Counter();reasons=Counter()
for line_index,line in enumerate(gzip.decompress(raw).splitlines()):
    record=json.loads(line);task=record['task_id']
    for call in record.get('calls',[]):
        if not call.get('candidate_is_none') and 'exception' not in call:
            continue
        detail=call.get('detail',{})
        kind='runtime_exception' if 'exception' in call else 'candidate_generation_failure'
        reason=detail.get('failure','returned_no_candidate_without_failure_key')
        event={'event_id':f"baseline-replay-{task}-call-{call['sequence']:04}",
               'attempt_id':'baseline-observational-replay','task_id_audit_only':task,
               'stage':call['phase'],'family_or_callable':call['callable'],'type':kind,
               'observed_reason':reason,'input_sha256':call['input_sha256_before'],
               'root_cause_status':'Only the returned failure is observed; semantic cause may remain unconfirmed',
               'evidence':{'artifact':'raw.jsonl.gz','decompressed_sha256':raw_hash,
                           'jsonl_line_zero_based':line_index,'pointer':f"/calls/{call['sequence']}"}}
        events.append(event);types[kind]+=1;reasons[str(reason)]+=1
    for index,result in enumerate(record.get('result',{}).get('results',[])):
        if result.get('answer') is not None:
            continue
        holds.append({'event_id':f'baseline-replay-{task}-query-{index}',
                      'attempt_id':'baseline-observational-replay','task_id_audit_only':task,
                      'query_index_audit_only':index,'type':'query_HOLD',
                      'status':result.get('status'),'reasons':result.get('reasons'),
                      'evidence':{'artifact':'raw.jsonl.gz','decompressed_sha256':raw_hash,
                                  'jsonl_line_zero_based':line_index,'pointer':f'/result/results/{index}'}})
out=''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in events+holds).encode()
compressed=gzip.compress(out,mtime=0);(a.replay/'failure-events.jsonl.gz').write_bytes(compressed)
summary={'candidate_failure_events':len(events),'query_HOLD_events':len(holds),
         'failure_types':dict(types),'reason_counts':dict(reasons),'raw_sha256':hashlib.sha256(out).hexdigest(),
         'gzip_sha256':hashlib.sha256(compressed).hexdigest(),
         'scope':'An index of observed returned failures; candidate counts are not HDS support. Full details remain in frozen raw replay.'}
(a.replay/'failure-index-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in summary.items() if k!='reason_counts'},ensure_ascii=False))
