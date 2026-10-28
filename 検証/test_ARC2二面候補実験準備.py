import hashlib
import pytest

from 道具.ARC2二面候補実験準備 import 作成


def test_stage_matches_the_measured_adapter_and_candidate(tmp_path):
    stage = tmp_path / "stage"
    manifest = 作成(stage)
    assert manifest["diagnostic_sha256"]["Kaggle提出.py"] == "b02b617a572ec659170509cf9a9fbb5c5b03b992a6859ab67aa43c3611c80628"
    assert hashlib.sha256((stage / "two_panel.py").read_bytes()).hexdigest() == manifest["candidate_sha256"]
    with pytest.raises(FileExistsError):
        作成(stage)
