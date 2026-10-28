import ast
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile
import pytest

from 道具.ARC2二面候補実験準備 import 作成


def test_stage_matches_the_measured_adapter_and_candidate(tmp_path):
    stage = tmp_path / "stage"
    manifest = 作成(stage)
    assert manifest["diagnostic_sha256"]["Kaggle提出.py"] == "b02b617a572ec659170509cf9a9fbb5c5b03b992a6859ab67aa43c3611c80628"
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
    assert 'two_panel_candidate(課題["train"], 課題["test"][位置]["input"])' in source


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
