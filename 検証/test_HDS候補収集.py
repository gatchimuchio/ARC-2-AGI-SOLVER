from 接続.ARC2.HDS接続 import 課題を解く


def test_候補収集は通常出力の状態を変えず診断情報だけを追加する():
    teachers = [
        {"input": [[1, 0], [0, 0]], "output": [[1, 0], [0, 0]]},
        {"input": [[0, 2], [0, 0]], "output": [[0, 2], [0, 0]]},
        {"input": [[0, 0], [3, 0]], "output": [[0, 0], [3, 0]]},
    ]
    task = {"train": teachers, "test": [{"input": teachers[0]["input"]}]}

    ordinary = 課題を解く(task, [])
    diagnostic = 課題を解く(task, [], 候補収集=True)

    ordinary_row = ordinary["results"][0]
    diagnostic_row = diagnostic["results"][0]
    assert "candidate_predictions" not in ordinary_row
    assert diagnostic_row.get("answer") == ordinary_row.get("answer")
    assert diagnostic_row.get("status") == ordinary_row.get("status")
    assert diagnostic_row.get("reasons") == ordinary_row.get("reasons")
    first_candidate = diagnostic_row["candidate_predictions"][0]
    assert isinstance(first_candidate["family"], str) and first_candidate["family"]
    assert first_candidate["answer"] == teachers[0]["input"]
