import json
import pytest

from 道具.ARC2記憶介入課題作成 import 作成


def test_rejects_existing_destination_before_reading_any_input(tmp_path):
    dest = tmp_path / "protected"
    dest.mkdir()
    (dest / "keep").write_text("original", encoding="utf-8")
    with pytest.raises(FileExistsError):
        作成(tmp_path / "missing", tmp_path / "missing", tmp_path / "missing", dest)
    assert (dest / "keep").read_text(encoding="utf-8") == "original"


def test_rejects_modified_training_source_before_writing(tmp_path):
    source = tmp_path / "source.json"
    cohort = tmp_path / "cohort.json"
    manifest = tmp_path / "manifest.json"
    source.write_text("{}", encoding="utf-8")
    cohort.write_text(json.dumps({"source_sha256": "not-the-source-hash"}), encoding="utf-8")
    manifest.write_text("{}", encoding="utf-8")
    dest = tmp_path / "new"
    with pytest.raises(ValueError, match="training入力のhash"):
        作成(source, cohort, manifest, dest)
    assert not dest.exists()
