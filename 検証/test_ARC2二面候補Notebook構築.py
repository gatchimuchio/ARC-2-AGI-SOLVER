import hashlib
import json
import zipfile
import pytest

from 道具.ARC2二面候補Notebook構築 import 構築
from 道具.ARC2二面候補実験準備 import 作成


def test_builds_private_offline_notebook_with_exact_five_members(tmp_path):
    stage, output = tmp_path / "stage", tmp_path / "output"
    作成(stage, 安全化=True)
    manifest = 構築(stage, output)
    metadata = json.loads((output / "kernel-metadata.json").read_text(encoding="utf-8"))
    notebook = json.loads((output / "main.ipynb").read_text(encoding="utf-8"))
    assert metadata["is_private"] is True and metadata["enable_internet"] is False
    assert metadata["competition_sources"] == ["arc-prize-2026-arc-agi-2"]
    assert manifest["aggregate_diagnostics"] is False and manifest["run_budget_seconds"] == 37800
    assert manifest["acceptance"] == "LOCAL_AND_PRIVATE_RUNTIME_VERIFICATION_REQUIRED"
    cell = "".join(notebook["cells"][0]["source"])
    assert '"--run-budget-seconds", "37800"' in cell and "--aggregate-diagnostics" not in cell
    with zipfile.ZipFile(output / "runtime_bundle.zip") as archive:
        assert set(archive.namelist()) == {"Kaggle提出.py", "deadline_control.py", "outer_watchdog.py", "solve.py", "two_panel.py"}
        for name, expected in manifest["runtime_member_sha256"].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == expected
    with pytest.raises(FileExistsError):
        構築(stage, output)


def test_rejects_stage_without_security_attestation_before_output(tmp_path):
    stage, output = tmp_path / "stage", tmp_path / "output"
    stage.mkdir()
    (stage / "diagnostic-manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="安全化済み"):
        構築(stage, output)
    assert not output.exists()
