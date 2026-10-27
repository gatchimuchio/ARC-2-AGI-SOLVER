"""Standalone stdlib-only local Linux smoke; no pytest/HDS/public dataset.

Run the reviewed file with WSL /usr/bin/python3. Results describe this local
Linux environment only and do not prove the Kaggle image/runtime guarantee.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import deadline_control as dc
import outer_watchdog as outer


def adapter():
    spec = importlib.util.spec_from_file_location("linux_smoke_adapter", HERE / "Kaggle提出.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def nonrunning(pid):
    path = Path(f"/proc/{pid}/stat")
    return not path.exists() or path.read_text().rsplit(")", 1)[1].split()[0] == "Z"


def main():
    if sys.platform != "linux" or sys.version_info < (3, 11):
        raise RuntimeError("this smoke requires local Linux Python >=3.11")
    checks = []
    with tempfile.TemporaryDirectory(prefix="arc2_deadline_linux_smoke_") as directory:
        tmp = Path(directory)
        grandchild = "import time;time.sleep(5)"
        child = "import subprocess,sys,time,json;p=subprocess.Popen([sys.executable,'-B','-c'," + repr(grandchild) + "],stdout=sys.stdout,stderr=sys.stderr);print(json.dumps({'pid':p.pid}),flush=True);time.sleep(5)"
        control = dc.ProcessControl(cleanup_grace=0.4, hard_deadline=time.monotonic() + 4)
        started = time.monotonic()
        result = control.invoke([sys.executable, "-B", "-c", child], timeout=0.7)
        assert result.error == "task_wall_timeout" and result.cleanup_complete
        assert result.direct_child_reaped and result.tree_termination_acknowledged
        assert nonrunning(json.loads(result.stdout)["pid"]) and not control.active
        checks.append({"name": "actual_posix_group_descendant_cleanup", "passed": True,
                       "seconds": round(time.monotonic() - started, 4)})

        worker = tmp / "synthetic_worker.py"
        worker.write_text("import json,sys,time\nif '--preflight' in sys.argv:raise SystemExit(0)\njson.load(sys.stdin)\ntime.sleep(5)\n", encoding="utf-8")
        data = {f"synthetic-{index}": {"train": [{"input": [[1]], "output": [[2]]}],
                                       "test": [{"input": [[index % 9]]}, {"input": [[1, 2]]}]}
                for index in range(8)}
        challenge = tmp / "synthetic_challenges.json"
        challenge.write_text(json.dumps(data), encoding="utf-8")
        saved = dict(os.environ)
        try:
            os.environ["ARC2_WORKER_LAUNCHER"] = str(worker)
            os.environ["ARC2_PAYLOAD_ROOT"] = str(tmp)
            for key in ("ARC2_RUN_STARTED_MONOTONIC", "ARC2_RUN_DEADLINE_MONOTONIC", "ARC2_DEADLINE_RUN_TOKEN", "ARC2_OUTER_WATCHDOG_ACTIVE"):
                os.environ.pop(key, None)
            output = tmp / "global_cutoff"
            started = time.monotonic()
            with contextlib.redirect_stdout(io.StringIO()):
                assert adapter().run_cli(["--challenges", str(challenge), "--output-dir", str(output),
                                          "--run-budget-seconds", "1.8", "--finalization-reserve-seconds", "0.6",
                                          "--cleanup-grace-seconds", "0.3"]) == 0
            submission = json.loads((output / "submission.json").read_text())
            audit = json.loads((output / "submission_audit.json").read_text())
            assert list(submission) == list(data)
            assert audit["deadline_control"]["run_state"] == "GLOBAL_DEADLINE_EXHAUSTED"
            assert audit["deadline_control"]["max_inflight"] <= 3 and audit["deadline_control"]["max_active_subprocesses"] <= 3
            assert audit["fallback_count"] == 16 and not audit["deadline_control"]["scientific_correctness_evaluated"]
            assert all(row["attempt_1"] == row["attempt_2"] == pair["input"] for key in data for row, pair in zip(submission[key], data[key]["test"], strict=True))
            checks.append({"name": "actual_global_cutoff_ordered_all_id_fallback", "passed": True,
                           "seconds": round(time.monotonic() - started, 4), "fallback_rows": 16})

            runner = tmp / "seed_and_stall.py"
            runner.write_text('''import argparse,hashlib,json,os,sys,time,importlib.util
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,'''+repr(str(HERE))+''')
from deadline_control import OwnedSnapshot,artifact_bytes
spec=importlib.util.spec_from_file_location('seed_format',Path('''+repr(str(HERE))+''')/'Kaggle提出.py')
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
p=argparse.ArgumentParser();p.add_argument('--challenges',type=Path);p.add_argument('--output-dir',type=Path);a,_=p.parse_known_args()
raw=a.challenges.read_bytes();tasks=m.入力検査(json.loads(raw));submission={};holds=[]
for key,task in tasks.items():
 rows,missing=m.結果を候補へ(key,task,{'error':'global_deadline_unprocessed'});submission[key]=rows;holds.extend(missing)
a.output_dir.mkdir(parents=True,exist_ok=True);token=os.environ['ARC2_DEADLINE_RUN_TOKEN']
audit={'format':'arc2-kaggle-submission-audit-v1','challenge_sha256':hashlib.sha256(raw).hexdigest(),'submission_sha256':hashlib.sha256(artifact_bytes(submission)).hexdigest(),'fallbacks':holds,'fallback_count':len(holds),'deadline_control':{'run_token':token,'preflight_passed':True,'scientific_correctness_evaluated':False,'solved_count':None,'run_state':'RUNNING','all_tasks_processed':False}}
owned=OwnedSnapshot(a.output_dir,token);owned.publish(submission,audit)
if os.environ.get('ARC2_SMOKE_PUBLICATION_PAUSE'):
 key=next(iter(submission));submission[key][0]={'attempt_1':[[9]],'attempt_2':[[9]]}
 audit['fallbacks']=[r for r in holds if not(r['task_id']==key and r['test_index']==0)];audit['fallback_count']=len(audit['fallbacks']);audit['submission_sha256']=hashlib.sha256(artifact_bytes(submission)).hexdigest()
 def pause(value):
  (a.output_dir/'publication_paused.marker').write_text('derived submission updated; audit pending')
  time.sleep(8)
 owned.audit.write=pause;owned.publish(submission,audit)
else:
 executor=ThreadPoolExecutor(1);executor.submit(time.sleep,8);executor.shutdown(wait=False)
''', encoding="utf-8")
            for mode in ("atexit_join", "publication_recovery"):
                if mode == "publication_recovery":
                    os.environ["ARC2_SMOKE_PUBLICATION_PAUSE"] = "1"
                else:
                    os.environ.pop("ARC2_SMOKE_PUBLICATION_PAUSE", None)
                output = tmp / mode
                started = time.monotonic()
                with contextlib.redirect_stdout(io.StringIO()):
                    assert outer.main(["--runner", str(runner), "--challenges", str(challenge), "--output-dir", str(output),
                                       "--run-budget-seconds", "2", "--finalization-reserve-seconds", "0.5",
                                       "--exit-reserve-seconds", "0.6", "--cleanup-grace-seconds", "0.3"]) == 0
                audit = json.loads((output / "submission_audit.json").read_text())
                assert audit["deadline_control"]["outer_watchdog"]["deadline_terminated_runner"]
                assert audit["submission_sha256"] == hashlib.sha256((output / "submission.json").read_bytes()).hexdigest()
                assert not audit["deadline_control"]["scientific_correctness_evaluated"]
                if mode == "publication_recovery":
                    assert (output / "publication_paused.marker").exists()
                    assert json.loads((output / "submission.json").read_text())[next(iter(data))][0]["attempt_1"] == [[9]]
                checks.append({"name": "actual_linux_outer_" + mode, "passed": True,
                               "seconds": round(time.monotonic() - started, 4)})
        finally:
            os.environ.clear()
            os.environ.update(saved)
    print(json.dumps({"scope": "local_linux_synthetic_only", "python": sys.version, "platform": platform.platform(),
                      "checks": checks, "hds_or_public_tasks_executed": False, "kaggle_runtime_proof": False,
                      "source_pins": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                      for name in ("deadline_control.py", "Kaggle提出.py", "solve.py", "outer_watchdog.py", Path(__file__).name)}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
