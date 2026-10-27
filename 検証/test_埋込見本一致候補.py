from copy import deepcopy

from 接続.ARC2.埋込見本一致候補 import fit_candidate, predict_candidate


_KEYS = [
    [[1, 1, 1], [1, 8, 1], [1, 1, 1]],
    [[2, 8, 2], [2, 2, 2], [8, 2, 8]],
    [[3, 3, 8], [3, 8, 3], [3, 3, 3]],
    [[4, 8, 4], [8, 4, 8], [4, 4, 4]],
]


def _make_case(positions, *, residual=False):
    grid = [[8] * 22 for _ in range(30)]
    grid[5] = [6] * 22
    grid[27] = [6] * 22
    for index, key in enumerate(_KEYS):
        for row in range(3):
            grid[1 + row][2 + 5 * index:5 + 5 * index] = key[row][:]

    for tile_row in range(4):
        for tile_col in range(4):
            y, x = 8 + tile_row * 5, 2 + tile_col * 5
            patch = _KEYS[positions.index((tile_row, tile_col))] if (tile_row, tile_col) in positions else [
                [9, 8, 9], [8, 9, 8], [9, 9, 8]
            ]
            for row in range(3):
                grid[y + row][x:x + 3] = patch[row][:]

    output = deepcopy(grid)
    for tile_row, tile_col in positions:
        y, x = 8 + tile_row * 5, 2 + tile_col * 5
        for row in range(y - 1, y + 4):
            for col in range(x - 1, x + 4):
                if grid[row][col] == 8:
                    output[row][col] = 3

    aligned = (
        len(positions) == 4
        and (len({row for row, _ in positions}) == 1 or len({col for _, col in positions}) == 1)
    )
    if aligned:
        for row in range(5):
            for col in range(22):
                if grid[row][col] == 8:
                    output[row][col] = 3
        footer_color = 3
    else:
        footer_color = 2
    for row in range(28, 30):
        for col in range(22):
            if grid[row][col] == 8:
                output[row][col] = footer_color

    if residual:
        output[1][7] = 5
    return {"input": grid, "output": output}


def test_candidate_accepts_exact_teacher_rule_and_predicts_scattered_layout():
    train = [
        _make_case([(0, 0), (0, 1), (0, 2), (0, 3)]),
        _make_case([(0, 0), (1, 0), (2, 0), (3, 0)]),
        _make_case([(0, 0), (1, 1), (2, 2), (3, 3)]),
        _make_case([(0, 1), (1, 2), (2, 3), (3, 0)]),
    ]

    model, evidence = fit_candidate(train)

    assert model is not None
    assert evidence["exact_teacher_count"] == 4
    prediction, detail = predict_candidate(train[2]["input"], model)
    assert prediction == train[2]["output"]
    assert detail == {"matches": 4, "aligned": False}


def test_candidate_only_tolerates_one_small_header_card_residual():
    train = [
        _make_case([(1, 0), (1, 1), (1, 2), (1, 3)], residual=True),
        _make_case([(0, 0), (0, 1), (0, 2), (0, 3)]),
        _make_case([(0, 0), (1, 0), (2, 0), (3, 0)]),
        _make_case([(0, 0), (1, 1), (2, 2), (3, 3)]),
        _make_case([(0, 1), (1, 2), (2, 3), (3, 0)]),
    ]

    model, evidence = fit_candidate(train)

    assert model is not None
    assert evidence["exact_teacher_count"] == 4
    assert evidence["residual_teacher_indices"] == [0]
    assert evidence["residual_cell_counts"] == [1]


def test_candidate_rejects_residual_outside_header_card():
    train = [
        _make_case([(1, 0), (1, 1), (1, 2), (1, 3)]),
        _make_case([(0, 0), (0, 1), (0, 2), (0, 3)]),
        _make_case([(0, 0), (1, 0), (2, 0), (3, 0)]),
        _make_case([(0, 0), (1, 1), (2, 2), (3, 3)]),
        _make_case([(0, 1), (1, 2), (2, 3), (3, 0)]),
    ]
    train[0]["output"][9][3] = 5

    model, _ = fit_candidate(train)

    assert model is None
