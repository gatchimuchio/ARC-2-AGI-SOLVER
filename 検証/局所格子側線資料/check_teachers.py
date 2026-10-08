"""Small train-only replay; no official data or full/native evaluator."""
import hashlib
import json
import resource
import sys
from pathlib import Path
import os
import tempfile

resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
OUT = Path(os.environ.get('ARC134_EVIDENCE_DIR', tempfile.mkdtemp(prefix='arc134-check-')))
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(BASE.parents[1]))
from 接続.ARC2 import 局所格子側線候補 as candidate

teachers = json.loads((BASE/'teachers-only.json').read_text())['train']
models, fitting = candidate.fit(teachers)
results = []
for i, teacher in enumerate(teachers):
    output, record = candidate.predict(teacher['input'], models)
    results.append(dict(teacher=i, output=output, expected=teacher['output'],
                        exact=output == teacher['output'], record=record))
report = dict(accepted_head='8eca96d5ff325bfaef359cf824d8cae50344a499',
              source_sha256=hashlib.sha256((BASE.parents[1]/'接続/ARC2/局所格子側線候補.py').read_bytes()).hexdigest(),
              scope='train-only; no HDS/native/public/query execution',
              fitting=fitting, consensus_results=results)
(OUT/'teacher-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(dict(declared=len(fitting['declared_models']), retained=models,
                     exact=[x['exact'] for x in results],
                     source_sha256=report['source_sha256'],
                     result_file=str(OUT/'teacher-result.json'))))
assert models and all(x['exact'] for x in results)

print(json.dumps(dict(successful=True, tests_run=len(results))))
