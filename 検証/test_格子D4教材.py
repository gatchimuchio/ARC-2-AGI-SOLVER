from 接続.ARC2.HDS接続 import 課題を解く
from 接続.ARC2.格子D4教材 import 格子D4教材


def test_全教師で一致した回転をHDS同値ゲート経由で適用する():
    教師群 = [
        {"input": [[0, 1, 2], [3, 4, 5]], "output": [[3, 0], [4, 1], [5, 2]]},
        {"input": [[1, 2], [3, 4], [5, 6]], "output": [[5, 3, 1], [6, 4, 2]]},
        {"input": [[2, 3, 4], [5, 6, 7]], "output": [[5, 2], [6, 3], [7, 4]]},
    ]
    入力 = [[9, 8, 7], [6, 5, 4]]

    結果 = 課題を解く(
        {"train": 教師群, "test": [{"input": 入力}]}, 事前教材=[]
    )

    assert 結果["results"][0]["answer"] == [[6, 9], [5, 8], [4, 7]]
    assert 結果["d4_transform"]["fitting_operations"] == ["rotate_90"]
    assert any(
        family["境界"] == "ARC格子D4変換"
        and family["採用可"]
        and family["同値採用"]
        for family in 結果["families"]
    )


def test_支持不足ではD4を採用しない():
    二例 = [
        {"input": [[0, 1], [2, 3]], "output": [[2, 0], [3, 1]]},
        {"input": [[4, 5], [6, 7]], "output": [[6, 4], [7, 5]]},
    ]
    支持不足 = 格子D4教材(二例)
    assert 支持不足.候補([[8, 9], [1, 2]], {})[0] is None

def test_全教師で確定したD4と一対一色写像をHDS同値ゲート経由で適用する():
    教師群 = [
        {
            "input": [[0, 3, 3, 3], [3, 3, 0, 1], [2, 1, 1, 3]],
            "output": [[6, 7, 4], [5, 7, 7], [5, 4, 7], [7, 5, 7]],
        },
        {
            "input": [[2, 3, 3, 0], [1, 0, 3, 1], [2, 0, 1, 1]],
            "output": [[6, 5, 6], [4, 4, 7], [5, 7, 7], [5, 5, 4]],
        },
        {
            "input": [[2, 3, 1, 2], [3, 0, 1, 2], [1, 2, 3, 0]],
            "output": [[5, 7, 6], [6, 4, 7], [7, 5, 5], [4, 6, 6]],
        },
    ]

    結果 = 課題を解く(
        {
            "train": 教師群,
            "test": [{"input": [[0, 3, 3, 0], [0, 0, 2, 3], [2, 0, 2, 1]]}],
        },
        事前教材=[],
    )

    assert 結果["results"][0]["answer"] == [
        [6, 4, 4],
        [4, 4, 7],
        [6, 6, 7],
        [5, 7, 4],
    ]
    assert 結果["d4_transform"]["fitting_operations"] == []
    assert 結果["d4_transform"]["fitting_palette_operations"] == [
        {
            "operation": "rotate_90",
            "mapping": {0: 4, 1: 5, 2: 6, 3: 7},
        }
    ]
    assert any(
        family["境界"] == "ARC格子D4変換"
        and family["採用可"]
        and family["同値採用"]
        for family in 結果["families"]
    )


def test_写像が未観測色を含む照会と非単射写像は保留する():
    未観測色 = 格子D4教材(
        [
            {
                "input": [[0, 3, 3, 3], [3, 3, 0, 1], [2, 1, 1, 3]],
                "output": [[6, 7, 4], [5, 7, 7], [5, 4, 7], [7, 5, 7]],
            },
            {
                "input": [[2, 3, 3, 0], [1, 0, 3, 1], [2, 0, 1, 1]],
                "output": [[6, 5, 6], [4, 4, 7], [5, 7, 7], [5, 5, 4]],
            },
            {
                "input": [[2, 3, 1, 2], [3, 0, 1, 2], [1, 2, 3, 0]],
                "output": [[5, 7, 6], [6, 4, 7], [7, 5, 5], [4, 6, 6]],
            },
        ]
    )
    assert 未観測色.候補([[0, 3, 8, 0], [0, 0, 2, 3], [2, 0, 2, 1]], {})[0] is None

    非単射 = 格子D4教材(
        [
            {"input": [[0, 1], [2, 3]], "output": [[5, 5], [6, 7]]},
            {"input": [[1, 0], [3, 2]], "output": [[5, 5], [7, 6]]},
            {"input": [[2, 3], [0, 1]], "output": [[5, 6], [5, 7]]},
        ]
    )
    assert 非単射.候補([[0, 3], [1, 2]], {})[0] is None


def test_学習時に曖昧な向きが残る場合はtest格子で一致しなければ保留する():
    教材 = 格子D4教材(
        [
            {"input": [[0]], "output": [[0]]},
            {"input": [[1]], "output": [[1]]},
            {"input": [[2]], "output": [[2]]},
        ]
    )

    候補, 詳細 = 教材.候補([[1, 2], [3, 4]], {})

    assert 候補 is None
    assert 詳細["failure"] == "consistent D4 transforms disagree on the input"
