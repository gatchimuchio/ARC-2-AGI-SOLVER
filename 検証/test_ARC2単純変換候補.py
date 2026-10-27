from 接続.ARC2.単純変換候補 import predict_pool, unique_candidate


def test_教師例に完全適合する一意なタイル候補を返す():
    教師 = [
        {"input": [[1]], "output": [[1, 1], [1, 1]]},
        {"input": [[2]], "output": [[2, 2], [2, 2]]},
    ]
    assert unique_candidate(教師, [[3]]) == [[3, 3], [3, 3]]


def test_教師例一つでは候補を返さない():
    教師 = [{"input": [[1]], "output": [[1, 1], [1, 1]]}]
    assert unique_candidate(教師, [[3]]) is None


def test_複数出力が残る場合は曖昧として保留する():
    教師 = [
        {"input": [[1, 1], [1, 1]], "output": [[1, 1], [1, 1]]},
        {"input": [[1, 1], [1, 1]], "output": [[1, 1], [1, 1]]},
    ]
    _, 予測票, _, _ = predict_pool(教師, [[1, 2], [3, 4]])
    assert len(予測票) > 1
    assert unique_candidate(教師, [[1, 2], [3, 4]]) is None
