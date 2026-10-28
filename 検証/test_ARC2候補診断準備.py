import hashlib
import importlib.util
import json
import sys
from types import SimpleNamespace

import pytest

from 道具 import ARC2候補診断準備 as prepare


def test_prepared_copy_preserves_frozen_inputs_and_refuses_overwrite(tmp_path):
    stage = tmp_path / "stage"
    before = {name: hashlib.sha256((prepare.SOURCE / name).read_bytes()).hexdigest()
              for name in prepare.EXPECTED}
    manifest = prepare.作成(stage)
    assert manifest["source_sha256"] == before
    assert manifest["diagnostic_sha256"]["Kaggle提出.py"] != before["Kaggle提出.py"]
    assert manifest["diagnostic_sha256"]["solve.py"] == before["solve.py"]
    with pytest.raises(FileExistsError):
        prepare.作成(stage)
    assert {name: hashlib.sha256((prepare.SOURCE / name).read_bytes()).hexdigest()
            for name in prepare.EXPECTED} == before


def test_mismatched_frozen_source_is_rejected_before_output(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    for name in prepare.EXPECTED:
        (source / name).write_bytes(b"incorrect")
    monkeypatch.setattr(prepare, "SOURCE", source)
    dest = tmp_path / "stage"
    with pytest.raises(ValueError, match="hash"):
        prepare.作成(dest)
    assert not dest.exists()


def test_controller_records_worker_output_without_reading_solutions(tmp_path, monkeypatch):
    stage = tmp_path / "stage"
    prepare.作成(stage)
    spec = importlib.util.spec_from_file_location("arc2_diagnostic_test_control", stage / "deadline_control.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        records = tmp_path / "records"
        records.mkdir()
        monkeypatch.setenv("ARC2_DIAGNOSTIC_DIR", str(records))
        worker_result = {"results": [{"answer": [[1]], "diagnostic_candidates": {"preselection": []}}]}
        control = SimpleNamespace(invoke=lambda *a, **kw: SimpleNamespace(
            cleanup_complete=True, error=None, stdout=json.dumps(worker_result), returncode=0))
        api = {"課題時間上限秒": 300, "結果を候補へ": lambda *args: ([], [])}
        module.run_one(api, "testtask", {"train": [], "test": [{"input": [[1]]}]},
                       "unused", "unused", aggregate_diagnostics=True, control=control,
                       budget=SimpleNamespace(solve_cutoff=1000))
        assert json.loads((records / "testtask.json").read_text(encoding="utf-8")) == worker_result
    finally:
        sys.modules.pop(spec.name, None)
