from 接続.ARC2.全前景平行移動教材 import 全前景平行移動教材


def _teachers():
    pairs = [
        ([[0, 1, 0, 0]], [[0, 0, 1, 0]]),
        ([[1, 0, 0, 0]], [[0, 1, 0, 0]]),
        ([[1, 0, 1, 0]], [[0, 1, 0, 1]]),
    ]
    return [{"input": source, "output": target} for source, target in pairs]


def test_three_distinct_teachers_fit_same_offset_and_predict():
    teachers = _teachers()
    model = 全前景平行移動教材(teachers)
    output, record = model.候補([[0, 0, 1, 0]], {})
    assert output == [[0, 0, 0, 1]]
    assert record["offsets"] == [[0, 1]]


def test_two_teachers_are_below_minimum_support():
    model = 全前景平行移動教材(_teachers()[:2])
    output, record = model.候補([[0, 0, 1, 0]], {})
    assert output is None
    assert record["failure"] == "no_common_translation_reproduces_all_training_pairs"


def test_incompatible_teacher_offset_holds():
    teachers = _teachers() + [{"input": [[1, 0, 0, 1]], "output": [[1, 0, 0, 1]]}]
    model = 全前景平行移動教材(teachers)
    output, _ = model.候補([[0, 0, 1, 0]], {})
    assert output is None


def test_duplicate_teacher_input_does_not_increase_support():
    teachers = _teachers()
    teachers.append(teachers[0])
    model = 全前景平行移動教材(teachers)
    output, _ = model.候補([[0, 0, 1, 0]], {})
    assert output is None


def test_blank_teacher_does_not_count_as_translation_support():
    teachers = _teachers() + [{"input": [[0, 0, 0]], "output": [[0, 0, 0]]}]
    model = 全前景平行移動教材(teachers)
    output, record = model.候補([[0, 0, 1, 0]], {})
    assert output is None
    assert record["failure"] == "no_common_translation_reproduces_all_training_pairs"


def test_foreground_that_would_leave_canvas_holds():
    model = 全前景平行移動教材(_teachers())
    output, record = model.候補([[0, 0, 0, 1]], {})
    assert output is None
    assert record["failure"] == "consistent_translation_offsets_disagree_or_leave_canvas"
