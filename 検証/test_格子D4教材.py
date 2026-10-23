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


def test_支持不足や色変換をD4として採用しない():
    二例 = [
        {"input": [[0, 1], [2, 3]], "output": [[2, 0], [3, 1]]},
        {"input": [[4, 5], [6, 7]], "output": [[6, 4], [7, 5]]},
    ]
    支持不足 = 格子D4教材(二例)
    assert 支持不足.候補([[8, 9], [1, 2]], {})[0] is None

    色変更 = 格子D4教材(
        [
            {"input": [[0, 1], [2, 3]], "output": [[1, 2], [3, 4]]},
            {"input": [[4, 5], [6, 7]], "output": [[5, 6], [7, 8]]},
            {"input": [[8, 9], [1, 2]], "output": [[9, 0], [2, 3]]},
        ]
    )
    assert 色変更.候補([[3, 4], [5, 6]], {})[0] is None


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
