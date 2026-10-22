from __future__ import annotations

import importlib
import io
import json
from pathlib import Path
import zipfile


提出 = importlib.import_module("接続.ARC2.Kaggle提出")
bundle = importlib.import_module("道具.ARC2Kaggle提出bundle")


def _課題():
    return {
        "task-a": {
            "train": [{"input": [[1]], "output": [[2]]}],
            "test": [{"input": [[3]]}, {"input": [[4]]}],
        },
        "task-b": {
            "train": [{"input": [[5]], "output": [[6]]}],
            "test": [{"input": [[7]]}],
        },
    }


def test_入力検査は動的な課題数とtest数を保つ():
    課題群 = 提出.入力検査(_課題())
    assert list(課題群) == ["task-a", "task-b"]
    assert [len(課題群[key]["test"]) for key in 課題群] == [2, 1]


def test_challenge選択はevaluationでなくsubmission用testを読む(tmp_path):
    入力根 = tmp_path / "input"
    大会根 = 入力根 / "arc-prize-2026-arc-agi-2"
    大会根.mkdir(parents=True)
    evaluation = 大会根 / "arc-agi_evaluation_challenges.json"
    submission = 大会根 / "arc-agi_test_challenges.json"
    evaluation.write_text("{}", encoding="utf-8")
    submission.write_text("{}", encoding="utf-8")

    assert 提出._discover_challenges(入力根) == submission


def test_test正解が含まれる入力は拒否する():
    原本 = _課題()
    原本["task-a"]["test"][0]["output"] = [[8]]
    try:
        提出.入力検査(原本)
    except ValueError as error:
        assert "inputだけ" in str(error)
    else:
        raise AssertionError("test outputを含む入力を受け入れた")


def test_HOLDは入力由来の合法gridを二候補へ複写する():
    課題 = 提出.入力検査(_課題())["task-a"]
    候補群, 保留 = 提出.結果を候補へ(
        "task-a",
        課題,
        {"results": [{"answer": None}, {"answer": None}]},
    )
    assert 候補群 == [
        {"attempt_1": [[3]], "attempt_2": [[3]]},
        {"attempt_1": [[4]], "attempt_2": [[4]]},
    ]
    assert [row["reason"] for row in 保留] == ["solver_hold", "solver_hold"]


def test_提出検査は全testとattemptを要求する():
    課題群 = 提出.入力検査(_課題())
    正常 = {
        "task-a": [
            {"attempt_1": [[1]], "attempt_2": [[1]]},
            {"attempt_1": [[2]], "attempt_2": [[2]]},
        ],
        "task-b": [{"attempt_1": [[3]], "attempt_2": [[3]]}],
    }
    提出.提出検査(課題群, 正常)
    正常["task-b"] = []
    try:
        提出.提出検査(課題群, 正常)
    except ValueError as error:
        assert "test数" in str(error)
    else:
        raise AssertionError("欠落したtestを受け入れた")


def test_bundleはsolverと許可済trainingだけを含む():
    files = bundle._runtime_files()
    names = [name for name, _ in files]
    assert "接続/ARC2/Kaggle提出.py" in names
    assert "接続/ARC2/テンプレート充填教材.json" in names
    assert "missing_edge_bindings.py" in names
    assert "peer_edge.py" in names
    assert any(name.startswith("HDS/学習系統/v0.4.2/") for name in names)
    assert any("/data/training/" in name for name in names)
    assert not any("/data/evaluation/" in name for name in names)
    assert not any("solutions" in name.lower() for name in names)
    first, _ = bundle._make_payload(files)
    second, _ = bundle._make_payload(files)
    assert first == second
    with zipfile.ZipFile(io.BytesIO(first)) as archive:
        assert "__arc2_bundle_manifest__.json" in archive.namelist()
        assert set(archive.namelist()[1:]) == set(names)


def test_送信Notebookは正しいipynbでrunnerを起動する():
    raw = bundle._render_notebook(b"print('runner-ok')\n", "a" * 64)
    notebook = json.loads(raw.decode("utf-8"))
    assert notebook["nbformat"] == 4
    assert len(notebook["cells"]) == 1
    source = "".join(notebook["cells"][0]["source"])
    compile(source, "main.ipynb", "exec")
    assert '"--output-dir"' in source
    assert "subprocess.run(arguments, check=True, env=environment)" in source


def test_upload_stageにはNotebookとmetadataだけを含める(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "出力").mkdir(parents=True)
    source = root / "出力" / "build"
    source.mkdir()
    (source / "main.ipynb").write_bytes(b"notebook")
    metadata = {
        "id": "owner/kernel",
        "code_file": "main.ipynb",
        "kernel_type": "notebook",
    }
    (source / "kernel-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (source / "bundle.zip").write_bytes(b"not-for-upload")
    monkeypatch.setattr(bundle, "ROOT", root)
    result = bundle.stage_upload(source, Path("出力/upload"))
    staged = root / "出力" / "upload"
    assert result["files"] == ["main.ipynb", "kernel-metadata.json"]
    assert sorted(path.name for path in staged.iterdir()) == ["kernel-metadata.json", "main.ipynb"]
    assert (staged / "main.ipynb").read_bytes() == b"notebook"
