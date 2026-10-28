import ast
import base64
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import zipfile
import pytest

from 道具.ARC2二面候補実験準備 import 作成


def test_stage_is_reproducible_and_pins_the_candidate(tmp_path):
    stage = tmp_path / "stage"
    manifest = 作成(stage)
    assert manifest["diagnostic_sha256"]["Kaggle提出.py"] == "bedb5e6df30a2a0e16be4b760c38f31b200f8d1a60713e532f4b8ba05121e62e"
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
                 "loo_correct": 2, "loo_conflicts": 0, "loo_unavailable": 1}
        result = {"results": [], "candidate_provenance": [entry]}
        control = SimpleNamespace(invoke=lambda *args, **kwargs: SimpleNamespace(
            cleanup_complete=True, error=None, stdout=json.dumps(result), returncode=0))
        api = {"課題時間上限秒": 300, "結果を候補へ": lambda *args: ([], [])}
        args = (api, "task-with_underscore", {"train": [], "test": [{"input": [[0]]}]}, "unused", "unused")
        kwargs = {"aggregate_diagnostics": False, "control": control,
                  "budget": SimpleNamespace(solve_cutoff=1000)}
        assert module.run_one(*args, **kwargs)[2]["candidate_provenance"] == [entry]
        entry.update({"decision": "rejected_loo_conflict", "loo_correct": 1, "loo_conflicts": 1})
        assert module.run_one(*args, **kwargs)[2]["candidate_provenance"] == [entry]
        entry["loo_conflicts"] = 0
        with pytest.raises(ValueError, match="invalid candidate provenance"):
            module.run_one(*args, **kwargs)
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
            if name not in (teacher_path, "__arc2_bundle_manifest__.json"):
                assert archive.read(name) == new_contents[name]
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
