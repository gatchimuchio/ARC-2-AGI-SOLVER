from __future__ import annotations

import importlib
import io
import json
from pathlib import Path
import sys
import types
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
        {
            "results": [
                {
                    "answer": None,
                    "status": "断定保留",
                    "reasons": [
                        "  generic   candidate conflict  ",
                        "generic candidate conflict",
                        "deadbeef",
                    ],
                },
                {"answer": None, "reasons": ["no admitted complete grid"]},
            ]
        },
    )
    assert 候補群 == [
        {"attempt_1": [[3]], "attempt_2": [[3]]},
        {"attempt_1": [[4]], "attempt_2": [[4]]},
    ]
    assert [row["reason"] for row in 保留] == ["solver_hold", "solver_hold"]
    assert [row["solver_hold_reasons"] for row in 保留] == [
        ["generic candidate conflict"],
        ["no admitted complete grid"],
    ]
    assert 提出._保留理由数(保留) == {
        "generic candidate conflict": 1,
        "no admitted complete grid": 1,
    }


def test_一意な最多HDS別候補だけを選び同数候補は保留する():
    第一 = [[1]]
    予測群 = [
        {"answer": 第一},
        {"answer": [[2]]},
        {"answer": [[2]]},
        {"answer": [[3]]},
        {"answer": [["invalid"]]},
    ]
    assert 提出._一意な別候補を選ぶ(予測群, 第一) == [[2]]
    assert 提出._一意な別候補を選ぶ(
        [{"answer": [[2]]}, {"answer": [[3]]}], 第一
    ) is None
    assert 提出._一意な別候補を選ぶ([{"answer": 第一}], 第一) is None


def test_別候補が有効な場合だけattempt2へ写す():
    課題 = 提出.入力検査(_課題())["task-a"]
    候補群, 保留 = 提出.結果を候補へ(
        "task-a",
        課題,
        {
            "results": [
                {"answer": None, "second_answer": [[9]]},
                {"answer": [[6]], "second_answer": [[6]]},
            ]
        },
    )
    assert 候補群 == [
        {"attempt_1": [[3]], "attempt_2": [[9]]},
        {"attempt_1": [[6]], "attempt_2": [[6]]},
    ]
    assert [row["reason"] for row in 保留] == ["solver_hold"]


def test_workerはHDS候補収集を要求し選んだ第二候補だけを返す(
    monkeypatch, tmp_path, capsys
):
    呼出し = {}
    fake_hds = types.ModuleType("接続.ARC2.HDS接続")

    def 課題を解く(課題, 教材, *, 候補収集=False):
        呼出し["課題"] = 課題
        呼出し["教材"] = 教材
        呼出し["候補収集"] = 候補収集
        return {
            "results": [
                {
                    "answer": None,
                    "status": "断定保留",
                    "reasons": ["no admitted complete grid"],
                    "candidate_predictions": [
                        {"family": "generic", "answer": [[9]]}
                    ],
                }
            ]
        }

    fake_hds.課題を解く = 課題を解く
    fake_hds.事前教材を読む = lambda: ["公開事前例"]
    monkeypatch.setitem(sys.modules, "接続.ARC2.HDS接続", fake_hds)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setenv("ARC2_PAYLOAD_ROOT", str(tmp_path))

    challenge = {
        "train": [{"input": [[1]], "output": [[2]]}],
        "test": [{"input": [[3]]}],
    }
    assert 提出._worker(challenge) == 0
    output = json.loads(capsys.readouterr().out)
    assert 呼出し["課題"] == challenge
    assert 呼出し["教材"] == ["公開事前例"]
    assert 呼出し["候補収集"] is True
    assert output == {
        "results": [
            {
                "answer": None,
                "status": "断定保留",
                "reasons": ["no admitted complete grid"],
                "second_answer": [[9]],
            }
        ]
    }


def test_workerは完全候補対を両attemptへ渡す(monkeypatch, tmp_path, capsys):
    fake_hds = types.ModuleType("接続.ARC2.HDS接続")
    fake_hds.課題を解く = lambda 課題, 教材, *, 候補収集=False: {
        "results": [{
            "answer": None,
            "status": "断定保留",
            "reasons": ["two complete hypotheses"],
            "candidate_attempts": [[[8]], [[9]]],
        }]
    }
    fake_hds.事前教材を読む = lambda: []
    monkeypatch.setitem(sys.modules, "接続.ARC2.HDS接続", fake_hds)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setenv("ARC2_PAYLOAD_ROOT", str(tmp_path))

    challenge = {
        "train": [{"input": [[1]], "output": [[2]]}],
        "test": [{"input": [[3]]}],
    }
    assert 提出._worker(challenge) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["results"][0] == {
        "answer": [[8]],
        "status": "断定保留",
        "reasons": ["two complete hypotheses"],
        "second_answer": [[9]],
    }


def test_workerは教師適合した一意単純変換を別候補へ追加する(
    monkeypatch, tmp_path, capsys
):
    fake_hds = types.ModuleType("接続.ARC2.HDS接続")
    fake_hds.課題を解く = lambda 課題, 教材, *, 候補収集=False: {
        "results": [{"answer": None, "status": "断定保留"}]
    }
    fake_hds.事前教材を読む = lambda: []
    monkeypatch.setitem(sys.modules, "接続.ARC2.HDS接続", fake_hds)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setenv("ARC2_PAYLOAD_ROOT", str(tmp_path))

    challenge = {
        "train": [
            {"input": [[1]], "output": [[1, 1], [1, 1]]},
            {"input": [[2]], "output": [[2, 2], [2, 2]]},
        ],
        "test": [{"input": [[3]]}],
    }
    assert 提出._worker(challenge) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["results"][0]["second_answer"] == [[3, 3], [3, 3]]


def test_workerは教師適合した複合幾何候補をsecond_onlyで使う(
    monkeypatch, tmp_path, capsys
):
    fake_hds = types.ModuleType("接続.ARC2.HDS接続")
    fake_hds.課題を解く = lambda 課題, 教材, *, 候補収集=False: {
        "results": [{"answer": [[9]], "status": "出力", "reasons": []}]
    }
    fake_hds.事前教材を読む = lambda: []
    monkeypatch.setitem(sys.modules, "接続.ARC2.HDS接続", fake_hds)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setenv("ARC2_PAYLOAD_ROOT", str(tmp_path))

    challenge = {
        "train": [
            {
                "input": [[0, 1, 0], [0, 0, 0], [0, 0, 0]],
                "output": [[1, 1], [1, 1]],
            },
            {
                "input": [[0, 2, 0], [0, 0, 0], [0, 0, 0]],
                "output": [[2, 2], [2, 2]],
            },
        ],
        "test": [{"input": [[0, 3, 0], [0, 0, 0], [0, 0, 0]]}],
    }

    assert 提出._worker(challenge) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["results"][0]["answer"] == [[9]]
    assert output["results"][0]["second_answer"] == [[3, 3], [3, 3]]


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
    assert "接続/ARC2/周期タイルD4教材.py" in names
    assert "接続/ARC2/単純変換候補.py" in names
    assert "接続/ARC2/複合幾何変換候補.py" in names
    assert "missing_edge_bindings.py" in names
    assert "peer_edge.py" in names
    assert any(name.startswith("HDS/学習系統/v0.4.2/") for name in names)
    assert any("/data/training/" in name for name in names)
    assert not any("/data/evaluation/" in name for name in names)
    assert not any("solutions" in name.lower() for name in names)
    assert not any(name.rsplit("/", 1)[-1].startswith("legacy_v4_") for name in names)
    first, _ = bundle._make_payload(files)
    second, _ = bundle._make_payload(files)
    assert first == second
    with zipfile.ZipFile(io.BytesIO(first)) as archive:
        assert "__arc2_bundle_manifest__.json" in archive.namelist()
        assert set(archive.namelist()[1:]) == set(names)


def test_periodic_tile_d4_learns_and_applies_positionwise_transforms():
    from 接続.ARC2.周期タイルD4教材 import 周期タイルD4教材

    learner = 周期タイルD4教材([
        {
            "input": [[7, 9], [4, 3]],
            "output": [
                [7, 9, 7, 9, 7, 9], [4, 3, 4, 3, 4, 3],
                [9, 7, 9, 7, 9, 7], [3, 4, 3, 4, 3, 4],
                [7, 9, 7, 9, 7, 9], [4, 3, 4, 3, 4, 3],
            ],
        },
        {
            "input": [[8, 6], [6, 4]],
            "output": [
                [8, 6, 8, 6, 8, 6], [6, 4, 6, 4, 6, 4],
                [6, 8, 6, 8, 6, 8], [4, 6, 4, 6, 4, 6],
                [8, 6, 8, 6, 8, 6], [6, 4, 6, 4, 6, 4],
            ],
        },
    ])
    answer, _ = learner.候補([[3, 2], [7, 8]], {})
    assert answer == [
        [3, 2, 3, 2, 3, 2], [7, 8, 7, 8, 7, 8],
        [2, 3, 2, 3, 2, 3], [8, 7, 8, 7, 8, 7],
        [3, 2, 3, 2, 3, 2], [7, 8, 7, 8, 7, 8],
    ]


def test_masked_periodic_tile_d4_infers_background_and_positionwise_transforms():
    from 接続.ARC2.周期タイルD4教材 import 条件付き周期タイルD4教材

    def tile_grid(grid, operations):
        transforms = {
            "identity": [row[:] for row in grid],
            "rotate_90": [list(row) for row in zip(*grid[::-1])],
            "reflect_rotate_0": [row[::-1] for row in grid],
        }
        height, width = len(grid), len(grid[0])
        output = [[0] * (width * width) for _ in range(height * height)]
        for tile_row in range(height):
            for tile_column in range(width):
                if grid[tile_row][tile_column] == 0:
                    continue
                tile = transforms[operations[tile_row][tile_column]]
                for row_index, row in enumerate(tile):
                    output[tile_row * height + row_index][
                        tile_column * width:(tile_column + 1) * width
                    ] = row
        return output

    operations = [
        ["identity", "identity"],
        ["rotate_90", "reflect_rotate_0"],
    ]
    teachers = [
        {"input": grid, "output": tile_grid(grid, operations)}
        for grid in (
            [[0, 1], [2, 3]],
            [[4, 0], [5, 6]],
        )
    ]
    learner = 条件付き周期タイルD4教材(teachers)
    answer, _ = learner.候補([[0, 9], [7, 0]], {})
    assert learner.全教師再現
    assert learner.背景色 == 0
    assert answer == tile_grid(
        [[0, 9], [7, 0]],
        operations,
    )


def test_masked_periodic_tile_d4_rejects_conflicting_training_pairs():
    from 接続.ARC2.周期タイルD4教材 import 条件付き周期タイルD4教材

    learner = 条件付き周期タイルD4教材([
        {
            "input": [[0, 1], [2, 3]],
            "output": [[0] * 4 for _ in range(4)],
        },
        {
            "input": [[4, 0], [5, 6]],
            "output": [[0] * 4 for _ in range(4)],
        },
    ])
    assert not learner.全教師再現
    answer, details = learner.候補([[0, 9], [7, 0]], {})
    assert answer is None
    assert "failure" in details


def test_masked_periodic_tile_d4_rejects_unobserved_nonbackground_position():
    from 接続.ARC2.周期タイルD4教材 import 条件付き周期タイルD4教材

    def output_for(grid):
        transforms = [
            [row[:] for row in grid],
            [list(row) for row in zip(*grid[::-1])],
            [row[::-1] for row in grid],
        ]
        output = [[0] * 4 for _ in range(4)]
        for tile_row in range(2):
            for tile_column in range(2):
                if grid[tile_row][tile_column] == 0:
                    continue
                tile = transforms[(tile_row + tile_column) % len(transforms)]
                for row_index, row in enumerate(tile):
                    output[tile_row * 2 + row_index][
                        tile_column * 2:(tile_column + 1) * 2
                    ] = row
        return output

    teachers = [
        {"input": grid, "output": output_for(grid)}
        for grid in (
            [[0, 1], [2, 3]],
            [[0, 4], [5, 6]],
        )
    ]
    learner = 条件付き周期タイルD4教材(teachers)
    answer, details = learner.候補([[9, 4], [5, 6]], {})
    assert learner.全教師再現
    assert answer is None
    assert details["failure"] == "unobserved_nonbackground_tile_transform"


def test_送信Notebookは正しいipynbでrunnerを起動する():
    raw = bundle._render_notebook(b"print('runner-ok')\n", "a" * 64)
    notebook = json.loads(raw.decode("utf-8"))
    assert notebook["nbformat"] == 4
    assert len(notebook["cells"]) == 1
    cell_id = notebook["cells"][0]["id"]
    assert len(cell_id) == 12 and all(character in "0123456789abcdef" for character in cell_id)
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
