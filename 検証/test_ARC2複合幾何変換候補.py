from 接続.ARC2.複合幾何変換候補 import CompositeGeometryCandidate


def test_二つの異なる教師から背景cropと拡大を再現してtestへ適用する():
    teachers = [
        {
            "input": [[0, 1, 0], [0, 0, 0], [0, 0, 0]],
            "output": [[1, 1], [1, 1]],
        },
        {
            "input": [[0, 2, 0], [0, 0, 0], [0, 0, 0]],
            "output": [[2, 2], [2, 2]],
        },
    ]
    model = CompositeGeometryCandidate(teachers)

    answer, record = model.候補(
        [[0, 3, 0], [0, 0, 0], [0, 0, 0]], {}
    )

    assert answer == [[3, 3], [3, 3]]
    assert record["consensus"] is True
    assert record["fitted_programs"] > 0


def test_教師入力が一種類だけなら候補を出さない():
    repeated_teacher = {
        "input": [[0, 1, 0], [0, 0, 0], [0, 0, 0]],
        "output": [[1, 1], [1, 1]],
    }
    model = CompositeGeometryCandidate([repeated_teacher, repeated_teacher])

    answer, record = model.候補(
        [[0, 3, 0], [0, 0, 0], [0, 0, 0]], {}
    )

    assert answer is None
    assert record["reason"] == "no_fitted_program"


def test_教師例一つでは候補を出さない():
    model = CompositeGeometryCandidate([
        {
            "input": [[0, 1, 0], [0, 0, 0], [0, 0, 0]],
            "output": [[1, 1], [1, 1]],
        }
    ])

    answer, record = model.候補(
        [[0, 3, 0], [0, 0, 0], [0, 0, 0]], {}
    )

    assert answer is None
    assert record["reason"] == "no_fitted_program"


def test_同じtest入力の二回目は同じ記録をcacheから返す():
    teachers = [
        {"input": [[1]], "output": [[1, 1], [1, 1]]},
        {"input": [[2]], "output": [[2, 2], [2, 2]]},
    ]
    model = CompositeGeometryCandidate(teachers)
    query = [[3]]

    first = model.候補(query, {})
    second = model.候補(query, {})

    assert second == first
