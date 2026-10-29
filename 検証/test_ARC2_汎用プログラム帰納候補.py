from 接続.ARC2.HDS接続 import 課題を解く
from 接続.ARC2.汎用プログラム帰納候補 import 汎用プログラム帰納候補群


def test_train_exact_program_is_applied_to_test_input_and_has_provenance():
    教師群 = [
        {"input": [[0, 0, 1], [1, 2, 2]], "output": [[1, 0, 0], [2, 2, 1]]},
        {"input": [[3, 3, 4], [4, 5, 5]], "output": [[4, 3, 3], [5, 5, 4]]},
    ]
    候補群 = 汎用プログラム帰納候補群(教師群)

    予測, 根拠 = 候補群.第一候補([[6, 6, 7], [7, 8, 8]], {})

    assert 予測 == [[7, 6, 6], [8, 8, 7]]
    assert 根拠["train_fit"] is True
    assert 根拠["program"] == "flip_horizontal"
    assert 根拠["rank"] == 1
    assert len(根拠["program_source_sha256"]) == 64


def test_missing_rank_does_not_invent_a_candidate():
    候補群 = 汎用プログラム帰納候補群([
        {"input": [[0, 0, 1], [1, 2, 2]], "output": [[1, 0, 0], [2, 2, 1]]},
        {"input": [[3, 3, 4], [4, 5, 5]], "output": [[4, 3, 3], [5, 5, 4]]},
    ])

    予測, 根拠 = 候補群.第二候補([[6, 6, 7], [7, 8, 8]], {})

    assert 予測 is None
    assert 根拠["train_fit"] is False
    assert 根拠["reason"] == "no_ranked_exact_program"


def test_hds_adopts_exact_candidate_and_keeps_its_provenance():
    課題 = {
        "train": [
            {"input": [[0, 0, 1], [1, 2, 2]], "output": [[1, 0, 0], [2, 2, 1]]},
            {"input": [[3, 3, 4], [4, 5, 5]], "output": [[4, 3, 3], [5, 5, 4]]},
        ],
        "test": [{"input": [[6, 6, 7], [7, 8, 8]]}],
    }

    結果 = 課題を解く(課題, (), 候補収集=True)

    assert 結果["results"][0]["answer"] == [[7, 6, 6], [8, 8, 7]]
    機構 = next(x for x in 結果["families"] if x["境界"] == "ARC汎用プログラム帰納_1")
    assert 機構["採用可"] is True
    assert 機構["同値採用"] is True
    assert 機構["候補根拠"]["program"] == "flip_horizontal"
    予測 = next(
        x for x in 結果["results"][0]["candidate_predictions"]
        if x["family"] == "ARC汎用プログラム帰納_1"
    )
    assert 予測["evidence"]["program_source_sha256"] == 機構["候補根拠"]["program_source_sha256"]
