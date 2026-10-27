import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import pytest

from test_deadline_control import HERE, legacy, synthetic
import outer_watchdog as outer


def delegated_runner(tmp):
    path = tmp / "delegated_synthetic_runner.py"
    path.write_text("import sys,importlib.util\nfrom pathlib import Path\n"
                    + "here=Path(" + repr(str(HERE)) + ")\nsys.path.insert(0,str(here))\n"
                    + "spec=importlib.util.spec_from_file_location('child_deadline_adapter',here/'Kaggle提出.py')\n"
                    + "module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)\n"
                    + "raise SystemExit(module.run_cli(sys.argv[1:]))\n", encoding="utf-8")
    return path


def arguments(path, output, runner, *, budget="10", reserve="2", exit_reserve="1", grace="0.5"):
    return ["--runner", str(runner), "--challenges", str(path), "--output-dir", str(output),
            "--run-budget-seconds", budget, "--finalization-reserve-seconds", reserve,
            "--exit-reserve-seconds", exit_reserve, "--cleanup-grace-seconds", grace]


def seed_then_stall_runner(tmp):
    path = tmp / "seed_then_interpreter_join.py"
    path.write_text('''import argparse,hashlib,json,os,sys,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,'''+repr(str(HERE))+''')
from deadline_control import OwnedSnapshot,artifact_bytes
import importlib.util
spec=importlib.util.spec_from_file_location('seed_format',Path('''+repr(str(HERE))+''')/'Kaggle提出.py')
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
p=argparse.ArgumentParser();p.add_argument('--challenges',type=Path);p.add_argument('--output-dir',type=Path);a,_=p.parse_known_args()
raw=a.challenges.read_bytes();tasks=m.入力検査(json.loads(raw));submission={};holds=[]
for key,task in tasks.items():
 rows,missing=m.結果を候補へ(key,task,{'error':'global_deadline_unprocessed'});submission[key]=rows;holds.extend(missing)
a.output_dir.mkdir(parents=True,exist_ok=True)
token=os.environ['ARC2_DEADLINE_RUN_TOKEN'] if not os.environ.get('SYNTH_FOREIGN_TOKEN') else 'foreign'
audit={'format':'arc2-kaggle-submission-audit-v1','challenge_sha256':hashlib.sha256(raw).hexdigest(),'submission_sha256':hashlib.sha256(artifact_bytes(submission)).hexdigest(),'fallbacks':holds,'fallback_count':len(holds),'deadline_control':{'run_token':token,'preflight_passed':True,'scientific_correctness_evaluated':False,'solved_count':None,'run_state':'RUNNING_WITH_UNPROCESSED_FALLBACK','all_tasks_processed':False}}
owned=OwnedSnapshot(a.output_dir,token);owned.publish(submission,audit)
if os.environ.get('SYNTH_INTERRUPT_PUBLICATION'):
 key=next(iter(submission));submission[key][0]={'attempt_1':[[9]],'attempt_2':[[9]]}
 audit['fallbacks']=[r for r in holds if not(r['task_id']==key and r['test_index']==0)];audit['fallback_count']=len(audit['fallbacks']);audit['submission_sha256']=hashlib.sha256(artifact_bytes(submission)).hexdigest()
 def pause_before_audit(value):
  (a.output_dir/'publication_interrupted.marker').write_text('submission published, audit pending')
  time.sleep(8)
 owned.audit.write=pause_before_audit;owned.publish(submission,audit)
elif not os.environ.get('SYNTH_FOREIGN_TOKEN'):
 executor=ThreadPoolExecutor(max_workers=1);executor.submit(time.sleep,8);executor.shutdown(wait=False)
''', encoding="utf-8")
    return path


def test_outer_normal_submission_bytes_match_frozen_reference(synthetic):
    tmp, challenge = synthetic
    path, _ = challenge(3)
    old_output, new_output = tmp / "outer-old", tmp / "outer-new"
    legacy.run_cli(["--challenges", str(path), "--output-dir", str(old_output)])
    assert outer.main(arguments(path, new_output, delegated_runner(tmp))) == 0
    assert (old_output / "submission.json").read_bytes() == (new_output / "submission.json").read_bytes()
    audit = json.loads((new_output / "submission_audit.json").read_text(encoding="utf-8"))
    assert audit["deadline_control"]["whole_notebook_outer_watchdog_wired"] is True
    assert audit["deadline_control"]["outer_watchdog"]["completed"] is True
    assert audit["deadline_control"]["outer_watchdog"]["whole_notebook_host_runtime_proved"] is False


def test_outer_kills_runner_stuck_in_interpreter_thread_join_and_keeps_owned_fallback(synthetic):
    tmp, challenge = synthetic
    path, data = challenge(3)
    output = tmp / "outer-stall"
    started = time.monotonic()
    assert outer.main(arguments(path, output, seed_then_stall_runner(tmp), budget="3", reserve="0.8", exit_reserve="0.8", grace="0.5")) == 0
    assert time.monotonic() - started < 4.5
    submission = json.loads((output / "submission.json").read_text(encoding="utf-8"))
    audit = json.loads((output / "submission_audit.json").read_text(encoding="utf-8"))
    assert list(submission) == list(data)
    assert audit["deadline_control"]["run_state"] == "OUTER_WATCHDOG_DEADLINE_WITH_EXPLICIT_FALLBACK"
    assert audit["deadline_control"]["outer_watchdog"]["deadline_terminated_runner"] is True
    assert audit["deadline_control"]["scientific_correctness_evaluated"] is False
    assert {row["reason"] for row in audit["fallbacks"]} == {"outer_watchdog_deadline"}


def test_outer_preflight_failure_and_preexisting_file_remain_failures(synthetic, monkeypatch):
    tmp, challenge = synthetic
    path, _ = challenge(2)
    monkeypatch.setenv("SYNTH_PREFLIGHT_EXIT", "7")
    output = tmp / "outer-preflight-fail"
    with pytest.raises(RuntimeError, match="inner failure"):
        outer.main(arguments(path, output, delegated_runner(tmp)))
    assert not (output / "submission.json").exists()
    protected = tmp / "outer-protected"
    protected.mkdir()
    (protected / "submission.json").write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        outer.main(arguments(path, protected, delegated_runner(tmp)))
    assert (protected / "submission.json").read_bytes() == b"existing"


def test_outer_rejects_foreign_token_without_rewriting_it(synthetic, monkeypatch):
    tmp, challenge = synthetic
    path, _ = challenge(1)
    monkeypatch.setenv("SYNTH_FOREIGN_TOKEN", "1")
    output = tmp / "outer-foreign"
    with pytest.raises(FileExistsError, match="run|ownership"):
        outer.main(arguments(path, output, seed_then_stall_runner(tmp)))
    audit = json.loads((output / "submission_audit.json").read_text(encoding="utf-8"))
    assert audit["deadline_control"]["run_token"] == "foreign"


def test_outer_recovers_atomic_pair_when_killed_between_publications(synthetic, monkeypatch):
    tmp, challenge = synthetic
    path, data = challenge(2)
    monkeypatch.setenv("SYNTH_INTERRUPT_PUBLICATION", "1")
    output = tmp / "interrupted-publication"
    assert outer.main(arguments(path, output, seed_then_stall_runner(tmp), budget="3", reserve="0.8", exit_reserve="0.8", grace="0.5")) == 0
    assert (output / "publication_interrupted.marker").exists()
    submission = json.loads((output / "submission.json").read_text(encoding="utf-8"))
    audit = json.loads((output / "submission_audit.json").read_text(encoding="utf-8"))
    assert submission[next(iter(data))][0]["attempt_1"] == [[9]]
    assert audit["submission_sha256"] == hashlib.sha256((output / "submission.json").read_bytes()).hexdigest()
    assert audit["deadline_control"]["outer_watchdog"]["deadline_terminated_runner"] is True
    assert audit["deadline_control"]["scientific_correctness_evaluated"] is False


def test_new_notebook_cell_template_is_wired_to_outer_watchdog(synthetic, monkeypatch):
    tmp, challenge = synthetic
    path, _ = challenge(1)
    output = tmp / "cell-template"
    cell = json.loads((HERE / "deadline_notebook_template.ipynb").read_text(encoding="utf-8"))["cells"][0]
    monkeypatch.setenv("ARC2_DEADLINE_VARIANT_ROOT", str(HERE))
    monkeypatch.setenv("ARC2_WATCHDOG_ARGS", json.dumps(arguments(path, output, delegated_runner(tmp))))
    exec(compile("".join(cell["source"]), "isolated_notebook_cell", "exec"), {})
    assert (output / "submission.json").is_file()
