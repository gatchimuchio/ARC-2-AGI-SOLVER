import ast
import base64
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import zipfile
import pytest

from 道具.ARC2二面候補実験準備 import 作成
from 接続.ARC2.二面真理値候補 import provisional_action_gate


def _valid_gate():
    return provisional_action_gate(
        [[0]], [[0]], [[1]], train_exact=True,
        loo={"loo_total": 2, "loo_correct": 2, "loo_conflicts": 0, "loo_unavailable": 0},
        hds_basis={"status": "断定保留", "reason_count": 1, "reason_labels": ["MISSING_OBSERVATION"],
                   "quarantined": 0, "answer_present": False, "equality_admitted": False},
        now_monotonic=1, cutoff_monotonic=10)


def test_stage_is_reproducible_and_pins_the_candidate(tmp_path):
    stage = tmp_path / "stage"
    manifest = 作成(stage)
    assert manifest["diagnostic_sha256"]["Kaggle提出.py"] == "fac1e7522d58a5db8a2138d96019caa001deb6c9d90b3d298b00b049318cfa57"
    assert hashlib.sha256((stage / "two_panel.py").read_bytes()).hexdigest() == manifest["candidate_sha256"]
    with pytest.raises(FileExistsError):
        作成(stage)


def test_memory_intervention_is_explicit_and_preserves_candidate(tmp_path):
    stage = tmp_path / "intervention"
    manifest = 作成(stage, 記憶介入=True)
    source = (stage / "Kaggle提出.py").read_text(encoding="utf-8")
    assert manifest["generic_prior_intervention_available"] is True
    assert 'if os.environ.get("ARC2_EMPTY_GENERIC_PRIOR") == "1":' in source
    assert '汎用記憶 = {"examples": [], "features": []}' in source
    assert '"generic_prior_support_observations": 結果.get(' in source
    assert 'two_panel_candidate_details(課題["train"], 課題["test"][位置]["input"])' in source


def test_candidate_provenance_survives_without_diagnostics_and_invalid_loo_is_rejected(tmp_path):
    stage = tmp_path / "stage"
    作成(stage)
    spec = importlib.util.spec_from_file_location("arc2_provenance_test_control", stage / "deadline_control.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        entry = {"test_index": 0, "source": "two_panel_occupancy_truth_table",
                 "decision": "provisional_external_candidate", "loo_total": 3,
                 "loo_correct": 2, "loo_conflicts": 0, "loo_unavailable": 1,
                 "gate": _valid_gate()}
        result = {"results": [{"second_answer": [[1]]}], "candidate_provenance": [entry],
                  "local_training_validation": []}
        control = SimpleNamespace(invoke=lambda *args, **kwargs: SimpleNamespace(
            cleanup_complete=True, error=None, stdout=json.dumps(result), returncode=0))
        observed_results = []
        def select_result(task_id, task, worker_result):
            observed_results.append(worker_result)
            return ([{"attempt_1": [[0]], "attempt_2": [[1]]}], [])
        api = {"課題時間上限秒": 300, "結果を候補へ": select_result}
        args = (api, "task-with_underscore", {"train": [{}, {}, {}], "test": [{"input": [[0]]}]}, "unused", "unused")
        kwargs = {"aggregate_diagnostics": False, "control": control,
                  "budget": SimpleNamespace(solve_cutoff=1000)}
        assert module.run_one(*args, **kwargs)[2]["candidate_provenance"] == [entry]
        local = {"test_index": 0, "train_exact": True, "loo_applicable": True,
                 "loo_total": 3, "loo_correct": 1, "loo_conflicts": 1, "loo_unavailable": 1,
                 "reason": "training_reproduced_loo_recorded", "generalization_risk": "loo_conflict",
                 "candidate_sha256": hashlib.sha256(b"[[1]]").hexdigest(), "selected": True, "gate": _valid_gate()}
        result["local_training_validation"] = [local]
        assert module.run_one(*args, **kwargs)[2]["local_training_validation"] == [local]
        api["結果を候補へ"] = lambda *args: ([{"attempt_1": [[0]], "attempt_2": [[0]]}], [])
        assert module.run_one(*args, **kwargs)[2]["local_training_validation"] == []
        api["結果を候補へ"] = select_result
        result["local_training_validation"] = [{**local, "loo_unavailable": 3}]
        assert module.run_one(*args, **kwargs)[2]["local_training_validation"] == []
        assert observed_results[-1] == {"error": "invalid_candidate_provenance"}
        result["local_training_validation"] = [{**local, "gate": {"accepted": True}}]
        assert module.run_one(*args, **kwargs)[2]["local_training_validation"] == []
        assert observed_results[-1] == {"error": "invalid_candidate_provenance"}
        result["local_training_validation"] = [{**local, "candidate_sha256": "0" * 64}]
        assert module.run_one(*args, **kwargs)[2]["local_training_validation"] == []
        assert observed_results[-1] == {"error": "invalid_candidate_provenance"}
        del result["local_training_validation"]
        assert module.run_one(*args, **kwargs)[2]["candidate_provenance"] == []
        assert observed_results[-1] == {"error": "invalid_candidate_provenance"}
        result["local_training_validation"] = []
        complete_gate = entry["gate"]
        for corrupt_gate in ({"authority": "arc2_domain_adapter", "hds_truth_approved": False, "confidence": None, "accepted": True},
                             {**complete_gate, "remaining_seconds": 10**309},
                             {**complete_gate, "hds_basis": {**complete_gate["hds_basis"], "status": "HDS_BOGUS_VALUE"}},
                             {**complete_gate, "objective": "unrelated"}):
            entry["gate"] = corrupt_gate
            proof = module.run_one(*args, **kwargs)[2]
            assert proof["candidate_provenance"] == []
            assert proof["candidate_provenance_drops"] == [{"test_index": None, "reason": "invalid_provenance"}]
            assert observed_results[-1] == {"error": "invalid_candidate_provenance"}
        entry["gate"] = complete_gate
        entry["gate"] = {**complete_gate, "remaining_seconds": float("nan")}
        proof = module.run_one(*args, **kwargs)[2]
        assert proof["candidate_provenance"] == []
        assert observed_results[-1] == {"error": "worker_invalid_json"}
        entry["gate"] = complete_gate
        del result["candidate_provenance"]
        proof = module.run_one(*args, **kwargs)[2]
        assert proof["candidate_provenance"] == []
        assert proof["candidate_provenance_drops"] == [{"test_index": None, "reason": "invalid_provenance"}]
        assert observed_results[-1] == {"error": "invalid_candidate_provenance"}
        result["candidate_provenance"] = []
        assert module.run_one(*args, **kwargs)[2]["candidate_provenance"] == []
        assert observed_results[-1] is result or observed_results[-1] == result
        result["candidate_provenance"] = [entry, entry]
        proof = module.run_one(*args, **kwargs)[2]
        assert proof["candidate_provenance"] == []
        assert proof["candidate_provenance_drops"] == [{"test_index": None, "reason": "invalid_provenance"}]
        result["candidate_provenance"] = [entry]
        entry.update({"loo_total": 2, "loo_correct": 1})
        proof = module.run_one(*args, **kwargs)[2]
        assert proof["candidate_provenance"] == []
        assert proof["candidate_provenance_drops"] == [{"test_index": None, "reason": "invalid_provenance"}]
        entry.update({"loo_total": 3, "loo_correct": 2})
        result["results"] = []
        proof = module.run_one(*args, **kwargs)[2]
        assert proof["candidate_provenance"] == []
        assert proof["candidate_provenance_drops"] == [{"test_index": 0, "reason": "invalid_worker_result"}]
        result["results"] = [{"second_answer": [[1]]}]
        api["結果を候補へ"] = lambda *args: ([{"attempt_1": [[0]], "attempt_2": [[0]]}], [])
        proof = module.run_one(*args, **kwargs)[2]
        assert proof["candidate_provenance"] == []
        assert proof["candidate_provenance_drops"] == [{"test_index": 0, "reason": "candidate_not_applied"}]
        api["結果を候補へ"] = lambda *args: ([{"attempt_1": [[0]], "attempt_2": [[1]]}], [])
        entry.update({"decision": "rejected_loo_conflict", "loo_correct": 1, "loo_conflicts": 1, "gate": None})
        assert module.run_one(*args, **kwargs)[2]["candidate_provenance"] == [entry]
        entry["loo_conflicts"] = 0
        proof = module.run_one(*args, **kwargs)[2]
        assert proof["candidate_provenance"] == []
        assert proof["candidate_provenance_drops"] == [{"test_index": None, "reason": "invalid_provenance"}]
    finally:
        sys.modules.pop(spec.name, None)


def test_nonzero_worker_exit_does_not_promote_valid_looking_json(tmp_path):
    stage = tmp_path / "stage"
    作成(stage)
    spec = importlib.util.spec_from_file_location("arc2_failed_worker_test_control", stage / "deadline_control.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        result = {"results": [{"second_answer": [[1]]}], "candidate_provenance": []}
        control = SimpleNamespace(invoke=lambda *args, **kwargs: SimpleNamespace(
            cleanup_complete=True, error=None, stdout=json.dumps(result), returncode=1))
        api = {"課題時間上限秒": 300, "結果を候補へ": lambda task_id, task, value: (value, [])}
        prediction, holds, diagnostic = module.run_one(
            api, "task", {"train": [], "test": [{"input": [[0]]}]}, "unused", "unused",
            aggregate_diagnostics=False, control=control, budget=SimpleNamespace(solve_cutoff=1000))
        assert prediction == {"error": "worker_exit"}
        assert holds == [] and diagnostic["candidate_provenance"] == []
    finally:
        sys.modules.pop(spec.name, None)


def test_worker_error_with_valid_looking_results_is_treated_as_failure(tmp_path):
    stage = tmp_path / "stage"
    作成(stage)
    spec = importlib.util.spec_from_file_location("arc2_reported_error_test_control", stage / "deadline_control.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        result = {"error": "failure", "results": [{"second_answer": [[1]]}], "candidate_provenance": []}
        control = SimpleNamespace(invoke=lambda *args, **kwargs: SimpleNamespace(
            cleanup_complete=True, error=None, stdout=json.dumps(result), returncode=0))
        api = {"課題時間上限秒": 300, "結果を候補へ": lambda task_id, task, value: (value, [])}
        prediction, _, diagnostic = module.run_one(
            api, "task", {"train": [], "test": [{"input": [[0]]}]}, "unused", "unused",
            aggregate_diagnostics=False, control=control, budget=SimpleNamespace(solve_cutoff=1000))
        assert prediction == {"error": "worker_reported_error"}
        assert diagnostic["candidate_provenance"] == []
    finally:
        sys.modules.pop(spec.name, None)


def test_invalid_unicode_is_isolated_before_diagnostic_snapshot(tmp_path, monkeypatch):
    stage = tmp_path / "stage"
    作成(stage)
    spec = importlib.util.spec_from_file_location("arc2_unicode_worker_test_control", stage / "deadline_control.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        monkeypatch.setenv("ARC2_DIAGNOSTIC_DIR", str(tmp_path))
        monkeypatch.setenv("ARC2_DEADLINE_RUN_TOKEN", "test-token")
        control = SimpleNamespace(invoke=lambda *args, **kwargs: SimpleNamespace(
            cleanup_complete=True, error=None,
            stdout='{"results":[{"status":"\\ud800","answer":null}],"candidate_provenance":[]}', returncode=0))
        api = {"課題時間上限秒": 300, "結果を候補へ": lambda task_id, task, value: (value, [])}
        prediction, _, _ = module.run_one(
            api, "task", {"train": [], "test": [{"input": [[0]]}]}, "unused", "unused",
            aggregate_diagnostics=True, control=control, budget=SimpleNamespace(solve_cutoff=1000))
        assert prediction == {"error": "worker_invalid_json"}
        diagnostic = json.loads((tmp_path / "task.json").read_text(encoding="utf-8"))
        assert diagnostic["result"] == prediction
    finally:
        sys.modules.pop(spec.name, None)


def test_owned_output_failure_reports_safe_codes_and_preserves_primary(tmp_path, monkeypatch, capsys):
    stage = tmp_path / "stage"
    作成(stage)
    spec = importlib.util.spec_from_file_location("arc2_owned_failure_test_control", stage / "deadline_control.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        output = tmp_path / "submission.json"
        artifact = module.OwnedArtifact(output)
        original = artifact.write({"value": "original"})
        original_unlink = Path.unlink

        def replace_failure(*args, **kwargs):
            raise PermissionError(13, "sensitive exception message")

        def cleanup_failure(path, *args, **kwargs):
            if path.name.endswith(".tmp"):
                raise OSError(5, "sensitive cleanup message")
            return original_unlink(path, *args, **kwargs)

        with monkeypatch.context() as context:
            context.setattr(module.os, "replace", replace_failure)
            context.setattr(Path, "unlink", cleanup_failure)
            with pytest.raises(PermissionError):
                artifact.write({"value": "changed"})
        assert output.read_bytes() == original
        stderr = capsys.readouterr().err
        events = [json.loads(line.removeprefix("ARC2_ARTIFACT_ERROR ")) for line in stderr.splitlines()]
        assert [event["operation"] for event in events] == ["replace", "cleanup"]
        assert events[0]["exception_type"] == "PermissionError" and events[0]["errno"] == 13
        assert all(event["artifact"] == "submission.json" for event in events)
        assert "sensitive" not in stderr and str(tmp_path) not in stderr
    finally:
        sys.modules.pop(spec.name, None)


def test_outer_failure_forwards_only_valid_artifact_codes(tmp_path, monkeypatch, capsys):
    stage = tmp_path / "stage"
    作成(stage)
    old_control = sys.modules.get("deadline_control")
    control_spec = importlib.util.spec_from_file_location("deadline_control", stage / "deadline_control.py")
    control_module = importlib.util.module_from_spec(control_spec)
    sys.modules["deadline_control"] = control_module
    spec = importlib.util.spec_from_file_location("arc2_outer_failure_test", stage / "outer_watchdog.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        control_spec.loader.exec_module(control_module)
        spec.loader.exec_module(module)
        event = {"artifact": "submission.json", "operation": "replace", "exception_type": "PermissionError",
                 "errno": 13, "winerror": 32}

        class FailedControl:
            error = None
            def __init__(self, *args, **kwargs):
                self.active = set()

            def invoke(self, *args, **kwargs):
                return SimpleNamespace(cleanup_complete=True, error=self.error, returncode=1,
                    stderr="secret data\nARC2_ARTIFACT_ERROR " + json.dumps(event) + "\n")

        monkeypatch.setattr(module, "ProcessControl", FailedControl)
        monkeypatch.setattr(module, "adapter", lambda: SimpleNamespace(
            _discover_challenges=lambda: None, 入力検査=lambda x: x, 提出名="submission.json", 監査名="submission_audit.json"))
        challenges = tmp_path / "challenges.json"
        challenges.write_text('{}', encoding="utf-8")
        args = SimpleNamespace(run_budget_seconds=60, finalization_reserve_seconds=5,
            cleanup_grace_seconds=1, exit_reserve_seconds=2, challenges=challenges,
            output_dir=tmp_path / "output", runner=stage / "solve.py", max_worker_output_bytes=1024,
            aggregate_diagnostics=False)
        with pytest.raises(RuntimeError, match="inner failure"):
            module.run(args)
        stderr = capsys.readouterr().err
        assert "secret data" not in stderr
        assert json.loads(stderr.removeprefix("ARC2_ARTIFACT_ERROR ")) == event
        FailedControl.error = "global_deadline"
        args.output_dir = tmp_path / "output-deadline"
        with pytest.raises(RuntimeError, match="artifact failure before deadline"):
            module.run(args)
        assert json.loads(capsys.readouterr().err.removeprefix("ARC2_ARTIFACT_ERROR ")) == event
    finally:
        sys.modules.pop(spec.name, None)
        if old_control is None:
            sys.modules.pop("deadline_control", None)
        else:
            sys.modules["deadline_control"] = old_control


def test_outer_entrypoint_emits_sanitized_failure_without_traceback(tmp_path):
    stage = tmp_path / "stage"
    作成(stage)
    result = subprocess.run([sys.executable, str(stage / "outer_watchdog.py"), "--run-budget-seconds", "nan"],
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode != 0
    event = json.loads(result.stderr.removeprefix("ARC2_ARTIFACT_ERROR "))
    assert event["operation"] == "outer_controller" and event["exception_type"] == "ValueError"
    assert "Traceback" not in result.stderr and str(tmp_path) not in result.stderr


@pytest.mark.parametrize("bad_case", ["large_gate_number", "large_json_integer", "deep_json", "invalid_unicode", "missing_provenance"])
def test_bad_provenance_does_not_stop_other_scheduled_tasks(tmp_path, monkeypatch, bad_case):
    stage = tmp_path / "stage"
    作成(stage)
    spec = importlib.util.spec_from_file_location("arc2_scheduler_provenance_test", stage / "deadline_control.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        entry = {"test_index": 0, "source": "two_panel_occupancy_truth_table",
                 "decision": "provisional_external_candidate", "loo_total": 2,
                 "loo_correct": 2, "loo_conflicts": 0, "loo_unavailable": 0,
                 "gate": _valid_gate()}
        corrupt_entry = {**entry, "gate": {**entry["gate"], "remaining_seconds": 10**309}}
        class FakeControl:
            def __init__(self, grace, maximum, **kwargs):
                self.max_output_bytes = maximum
                self.active = set()
                self.peak_active = 0
                self.termination_failures = 0
            def invoke(self, command, **kwargs):
                if "--preflight" in command:
                    return SimpleNamespace(cleanup_complete=True, error=None, stdout="{}", returncode=0)
                task = json.loads(kwargs["input_text"])
                bad = task["test"][0]["input"] == [[0]]
                if bad and bad_case in ("large_json_integer", "deep_json"):
                    stdout = '{"x":' + ('9' * 4301 if bad_case == "large_json_integer" else '[' * 100000 + '0' + ']' * 100000) + '}'
                    return SimpleNamespace(cleanup_complete=True, error=None, stdout=stdout, returncode=0)
                if bad and bad_case == "invalid_unicode":
                    return SimpleNamespace(cleanup_complete=True, error=None,
                        stdout='{"results":[{"status":"\\ud800","answer":null}],"candidate_provenance":[]}', returncode=0)
                decisions = [corrupt_entry] if bad else [entry]
                result = {"results": [{"second_answer": [[1]]}], "candidate_provenance": decisions,
                          "local_training_validation": []}
                if bad and bad_case == "missing_provenance":
                    del result["candidate_provenance"]
                return SimpleNamespace(cleanup_complete=True, error=None, stdout=json.dumps(result), returncode=0)
            def stop_all(self, reason):
                return None
        monkeypatch.setattr(module, "ProcessControl", FakeControl)
        for name in ("ARC2_RUN_STARTED_MONOTONIC", "ARC2_RUN_DEADLINE_MONOTONIC", "ARC2_DEADLINE_RUN_TOKEN"):
            monkeypatch.delenv(name, raising=False)
        tasks = {key: {"train": [{}, {}], "test": [{"input": [[value]]}]}
                 for key, value in (("first", 0), ("second", 1))}
        challenges = tmp_path / "challenges.json"
        challenges.write_text(json.dumps(tasks), encoding="utf-8")
        args = SimpleNamespace(challenges=challenges, output_dir=tmp_path / "output", run_budget_seconds=60,
                               finalization_reserve_seconds=5, cleanup_grace_seconds=1,
                               max_worker_output_bytes=1024 * 1024, aggregate_diagnostics=False)
        api = {"__file__": str(stage / "Kaggle提出.py"), "課題時間上限秒": 30, "並列数": 2,
               "入力検査": lambda value: value, "提出名": "submission.json", "監査名": "submission_audit.json",
               "提出検査": lambda tasks, submission: None, "_保留理由数": lambda holds: {},
               "結果を候補へ": lambda task_id, task, result: ([{"attempt_1": [[0]], "attempt_2": [[1]]}], [])}
        api["_run_one"] = lambda *values, **options: module.run_one(api, *values, **options)
        assert module.run_submission(args, api) == 0
        audit = json.loads((args.output_dir / "submission_audit.json").read_text(encoding="utf-8"))
        assert audit["deadline_control"]["run_state"] == "COMPLETE"
        assert audit["deadline_control"]["completed_task_count"] == 2
        assert len(audit["candidate_provenance"]) == 1
        assert audit["candidate_provenance"][0]["task_id"] == "second"
        expected_drops = [] if bad_case in ("large_json_integer", "deep_json", "invalid_unicode") else [
            {"task_id": "first", "test_index": None, "reason": "invalid_provenance"}]
        assert audit["candidate_provenance_drops"] == expected_drops
    finally:
        sys.modules.pop(spec.name, None)


def test_hardened_stage_preserves_train_and_checks_cached_payload(tmp_path, monkeypatch):
    stage = tmp_path / "safe"
    manifest = 作成(stage, 安全化=True)
    assert manifest["security"]["teacher_test_removed"] is True
    adapter = (stage / "Kaggle提出.py").read_text(encoding="utf-8")
    assert 'if 観測診断:\n                診断選択前 = deepcopy(' in adapter
    assert 'if 観測診断:\n                公開行群[-1]["diagnostic_candidates"] = {' in adapter
    source = (stage / "solve.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    values = {node.targets[0].id: ast.literal_eval(node.value)
              for node in tree.body if isinstance(node, ast.Assign) and len(node.targets) == 1
              and isinstance(node.targets[0], ast.Name)
              and node.targets[0].id in ("PAYLOAD_B64", "PAYLOAD_SHA256")}
    raw = base64.b64decode(values["PAYLOAD_B64"], validate=True)
    assert hashlib.sha256(raw).hexdigest() == manifest["security"]["payload_sha256"]
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        teachers = [name for name in archive.namelist()
                    if name.startswith("入力/公式ソース/ARC-AGI-2/data/training/") and name.endswith(".json")]
        assert len(teachers) == 1
        teacher = json.loads(archive.read(teachers[0]))
        assert set(teacher) == {"train"} and len(teacher["train"]) == 2
        teacher_path = teachers[0]
        new_contents = {name: archive.read(name) for name in archive.namelist()}
    old_source = (Path(__file__).resolve().parents[1] / "運用/証拠/ARC26-UNIFIED/ARC2-v61-global-deadline-isolated/solve.py").read_text(encoding="utf-8")
    old_tree = ast.parse(old_source)
    old_payload = next(ast.literal_eval(node.value) for node in old_tree.body
                       if isinstance(node, ast.Assign) and len(node.targets) == 1
                       and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "PAYLOAD_B64")
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(old_payload, validate=True))) as archive:
        assert teacher["train"] == json.loads(archive.read(teacher_path))["train"]
        assert set(archive.namelist()) == set(new_contents)
        for name in archive.namelist():
            if name not in (teacher_path, "__arc2_bundle_manifest__.json", "接続/ARC2/HDS接続.py"):
                assert archive.read(name) == new_contents[name]
        assert archive.read("接続/ARC2/HDS接続.py") != new_contents["接続/ARC2/HDS接続.py"]
    context = {"__name__": "arc2_test_launcher", "__file__": str(stage / "solve.py")}
    exec(compile(source, str(stage / "solve.py"), "exec"), context)
    root = tmp_path / "payload"
    monkeypatch.setenv("ARC2_PAYLOAD_ROOT", str(root))
    context["payload_root"]()
    assert context["payload_root"]() == root.resolve()
    target = root / "接続" / "ARC2" / "HDS接続.py"
    original = target.read_bytes()
    target.write_bytes(original + b"\n")
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        context["payload_root"]()
    assert target.read_bytes() == original + b"\n"
