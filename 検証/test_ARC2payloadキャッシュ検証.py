import pytest
import io
import json
import tarfile

from 道具.ARC2Kaggle提出bundle import _make_payload, _render_launcher


def _launcher(tmp_path, monkeypatch):
    source = tmp_path / "source.py"
    source.write_text("value = 1\n", encoding="utf-8")
    payload, _ = _make_payload([("example/module.py", source)])
    context = {"__name__": "arc2_test_launcher"}
    exec(compile(_render_launcher(payload, "test"), "launcher.py", "exec"), context)
    destination = tmp_path / "cache"
    monkeypatch.setenv("ARC2_PAYLOAD_ROOT", str(destination))
    return context["payload_root"], destination


def test_reuses_only_intact_cache_and_rejects_same_size_tampering(tmp_path, monkeypatch):
    load, destination = _launcher(tmp_path, monkeypatch)
    assert load() == destination.resolve()
    assert load() == destination.resolve()
    file = destination / "example" / "module.py"
    file.write_text("value = 2\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        load()
    assert file.read_text(encoding="utf-8") == "value = 2\n"


def test_missing_cached_member_or_unowned_destination_is_not_overwritten(tmp_path, monkeypatch):
    load, destination = _launcher(tmp_path, monkeypatch)
    load()
    file = destination / "example" / "module.py"
    file.unlink()
    with pytest.raises(RuntimeError, match="member missing"):
        load()
    assert not file.exists()
    other = tmp_path / "unowned"
    other.mkdir()
    (other / "keep").write_text("original", encoding="utf-8")
    monkeypatch.setenv("ARC2_PAYLOAD_ROOT", str(other))
    with pytest.raises(RuntimeError, match="non-empty and unverified"):
        load()
    assert (other / "keep").read_text(encoding="utf-8") == "original"


def test_unexpected_bytecode_is_rejected_without_removing_it(tmp_path, monkeypatch):
    load, destination = _launcher(tmp_path, monkeypatch)
    load()
    bytecode = destination / "example" / "__pycache__" / "module.cpython-312.pyc"
    bytecode.parent.mkdir()
    bytecode.write_bytes(b"untrusted")
    with pytest.raises(RuntimeError, match="unexpected executable"):
        load()
    assert bytecode.read_bytes() == b"untrusted"


def test_training_material_is_bundled_without_test_answers(tmp_path):
    source = tmp_path / "training.json"
    material = {"train": [{"input": [[1]], "output": [[2]]}],
                "test": [{"input": [[3]], "output": [[4]]}]}
    source.write_text(json.dumps(material), encoding="utf-8")
    name = "入力/公式ソース/ARC-AGI-2/data/training/material.json"
    payload, _ = _make_payload([(name, source)])
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:xz") as archive:
        member = archive.getmember(name)
        stream = archive.extractfile(member)
        assert stream is not None
        bundled = json.loads(stream.read())
    assert bundled == {"train": material["train"]}
    assert json.loads(source.read_text(encoding="utf-8")) == material
