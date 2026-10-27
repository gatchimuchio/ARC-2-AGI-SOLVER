import json
from pathlib import Path

from 接続.ARC2 import Kaggle提出 as submission
from 接続.ARC2 import 標点組立教材 as marked_assembly


def test_n_square_palette_emits_both_complete_input_only_hypotheses():
    root = Path(__file__).resolve().parents[1]
    challenges = json.loads(
        (root / '入力/Kaggle/arc-agi_evaluation_challenges.json').read_text(
            encoding='utf-8'
        )
    )
    task = challenges['f560132c']
    model = marked_assembly.標点組立教材(task['train'])

    answer, record = model.候補(task['test'][0]['input'], {})

    assert answer is None
    assert record['failure'] == 'two_complete_square_palette_hypotheses'
    pair = record['candidate_attempts']
    assert len(pair) == 2 and pair[0] != pair[1]
    assert all(len(grid) == 15 and all(len(row) == 15 for row in grid)
               for grid in pair)
    assert all(0 <= color <= 9 for grid in pair for row in grid for color in row)


def test_complete_candidate_pair_requires_two_distinct_valid_grids():
    pair = ([[1]], [[2]])

    assert submission._完全候補対([[[1]], [[2]]]) == pair
    assert submission._完全候補対([[[1]], [[1]]]) is None
    assert submission._完全候補対([[[1]]]) is None
    assert submission._完全候補対([[[1]], [['invalid']]]) is None
