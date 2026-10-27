from 接続.ARC2.物体抽出候補 import (
    ObjectExtractionCandidate,
    _select_outlier,
)


def test_複数教師から最大物体を切り出してtestへ適用する():
    teachers = [
        {
            "input": [
                [0, 0, 0, 0, 0],
                [0, 1, 0, 0, 0],
                [0, 0, 0, 0, 0],
                [0, 0, 2, 2, 0],
                [0, 0, 2, 2, 0],
            ],
            "output": [[2, 2], [2, 2]],
        },
        {
            "input": [
                [0, 0, 0, 0, 0, 0],
                [0, 1, 0, 0, 0, 0],
                [0, 1, 0, 0, 0, 0],
                [0, 0, 2, 2, 2, 0],
                [0, 0, 2, 2, 2, 0],
                [0, 0, 0, 0, 0, 0],
            ],
            "output": [[2, 2, 2], [2, 2, 2]],
        },
    ]
    query = [
        [0, 0, 0, 0, 0, 0],
        [0, 1, 0, 0, 0, 0],
        [0, 1, 0, 0, 0, 0],
        [0, 0, 2, 2, 0, 0],
        [0, 0, 2, 2, 0, 0],
        [0, 0, 2, 2, 0, 0],
    ]
    candidate, record = ObjectExtractionCandidate(teachers).candidate(query)

    assert candidate == [[2, 2], [2, 2], [2, 2]]
    assert record["top_votes"] >= 2


def test_教師が一例だけなら候補を出さない():
    teachers = [{
        "input": [[0, 1], [0, 0]],
        "output": [[1]],
    }]

    candidate, record = ObjectExtractionCandidate(teachers).candidate(
        [[0, 2], [0, 0]]
    )

    assert candidate is None
    assert record["fitted_models"] == 0


def test_同値群から一つだけ外れる特徴値を選ぶ():
    objects = [
        {"area": 1, "name": "common-a"},
        {"area": 1, "name": "common-b"},
        {"area": 2, "name": "outlier"},
    ]

    assert _select_outlier(objects, "area:unique") == objects[2]
    assert _select_outlier(
        [{"area": 1}, {"area": 2}, {"area": 3}], "area:unique"
    ) is None


def test_外れ値選択器も複数教師に一致する切出し候補を返す():
    teachers = [
        {
            "input": [
                [0, 0, 0, 0, 0, 0, 0],
                [0, 1, 0, 1, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 2, 0],
                [0, 0, 0, 0, 0, 2, 0],
            ],
            "output": [[2], [2]],
        },
        {
            "input": [
                [0, 0, 0, 0, 0, 0, 0, 0],
                [0, 1, 0, 1, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 2, 0],
                [0, 0, 0, 0, 0, 0, 2, 0],
            ],
            "output": [[2], [2]],
        },
    ]
    query = [
        [0, 0, 0, 0, 0, 0, 0],
        [0, 1, 0, 1, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 2, 0],
        [0, 0, 0, 0, 0, 2, 0],
    ]

    model = ObjectExtractionCandidate(teachers)
    candidate, record = model.outlier_candidate(query)

    assert candidate == [[2], [2]]
    assert record["top_votes"] >= 2
    assert model._outlier_models is not None
    assert any(selector == "area:unique" for _, selector, _, _ in model._outlier_models)


def test_教師間で一意な色パレットの物体を選ぶ():
    teachers = [
        {
            "input": [
                [0, 0, 0, 0, 0, 0, 0],
                [0, 1, 0, 1, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 2, 0],
                [0, 0, 0, 0, 0, 3, 0],
            ],
            "output": [[2], [3]],
        },
        {
            "input": [
                [0, 0, 0, 0, 0, 0, 0, 0],
                [0, 1, 0, 1, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 2, 0],
                [0, 0, 0, 0, 0, 0, 3, 0],
            ],
            "output": [[2], [3]],
        },
    ]
    query = [
        [0, 0, 0, 0, 0, 0, 0],
        [0, 1, 0, 1, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 2, 0],
        [0, 0, 0, 0, 0, 3, 0],
    ]
    model = ObjectExtractionCandidate(teachers)

    candidate, record = model.palette_candidate(query)

    assert candidate == [[2], [3]]
    assert record["top_votes"] >= 2
    assert model._palette_models is not None
    assert any(selector == "palette:unique" for _, selector, _, _ in model._palette_models)
    assert any(
        selector == "shape_palette:unique"
        for _, selector, _, _ in model._palette_models
    )
