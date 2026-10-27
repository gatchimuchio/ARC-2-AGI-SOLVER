from 接続.ARC2 import 標識経路幾何 as geometry


def test_unique_background_gap_joins_separate_collinear_path_segments():
    grid = [[0] * 9 for _ in range(3)]
    support = {(1, 1), (1, 2), (1, 6), (1, 7)}
    for row, col in support:
        grid[row][col] = 3
    masks = {3: set(support)}

    additions = geometry.fill_unique_collinear_gaps(grid, masks, 0)

    assert additions == {3: [(1, 3), (1, 4), (1, 5)]}
    assert geometry.complete_path_union(masks[3])


def test_gap_with_an_intervening_foreground_cell_is_not_joined():
    grid = [[0] * 9 for _ in range(3)]
    support = {(1, 1), (1, 2), (1, 6), (1, 7)}
    grid[1][4] = 8
    for row, col in support:
        grid[row][col] = 3
    masks = {3: set(support)}

    assert geometry.fill_unique_collinear_gaps(grid, masks, 0) == {}
    assert masks[3] == support
    assert geometry.complete_path_union(masks[3])


def test_union_accepts_disjoint_simple_paths_but_rejects_a_branch():
    paths = {(0, 0), (0, 1), (2, 0), (2, 1)}
    branch = {(1, 0), (1, 1), (1, 2), (0, 1), (2, 1)}

    assert geometry.complete_path_union(paths)
    assert not geometry.complete_path_union(branch)
