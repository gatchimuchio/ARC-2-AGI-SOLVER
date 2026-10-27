import ast
from copy import deepcopy
from dataclasses import asdict
import hashlib
import importlib.util
from itertools import combinations, product
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "ARC2-cell-conditional-tree-rowcol/cell_conditional_tree.py"
NEW = HERE / "cell_conditional_tree.py"
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


old = load(OLD, "rowcol35_before_support_prune")
new = load(NEW, "rowcol35_after_support_prune")
AMPLE = {"max_fit_states": 4096, "max_work_units": 32_000_000, "max_alternatives": 128}


def pair(grid, target):
    return {"input": deepcopy(grid), "output": deepcopy(target)}


def test_only_fit_body_changed_from_frozen_rowcol_and_all_grammar_bounds_hds_fixed():
    assert hashlib.sha256(OLD.read_bytes()).hexdigest() == "0664c6ef1878f434c963125a767a65a35a4737aff9132a5091c05a5c316a5ac2"
    before, after = ast.parse(OLD.read_text(encoding="utf-8")), ast.parse(NEW.read_text(encoding="utf-8"))
    for tree in (before, after):
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "CellConditionalTree")
        fit = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "_fit")
        fit.body = [ast.Pass()]
    assert ast.dump(before, include_attributes=False) == ast.dump(after, include_attributes=False)
    assert old.FEATURES == new.FEATURES and len(new.FEATURES) == 35
    assert old.PROGRAMS == new.PROGRAMS and len(new.PROGRAMS) == 21
    assert asdict(old.Bounds()) == asdict(new.Bounds())
    assert old.SCHEMA == new.SCHEMA and old.HDS_BOUNDARY == new.HDS_BOUNDARY


def test_exhaustive_tiny_teacher_output_spaces_keep_every_minimal_forest_and_answer():
    grids = [[list(values)] for values in product((0, 1), repeat=2)]
    checked, fitted = 0, 0
    for inputs in combinations(grids, 2):
        for targets in product(grids, repeat=2):
            teachers = [pair(grid, target) for grid, target in zip(inputs, targets, strict=True)]
            previous = old.CellConditionalTree(teachers, bounds=old.Bounds(**AMPLE))
            current = new.CellConditionalTree(teachers, bounds=new.Bounds(**AMPLE))
            assert "budget_exceeded" not in previous.status
            assert "budget_exceeded" not in current.status
            assert previous.status == current.status
            assert previous.forest == current.forest
            for grid in grids:
                assert previous.候補(grid, {}) == current.候補(grid, {})
            checked += 1
            fitted += previous.status == "fitted"
    assert checked == 96 and fitted > 0


def test_equal_cost_role_and_tree_ambiguity_is_not_pruned():
    examples = []
    for grid in ([[1, 2, 3], [2, 3, 4], [3, 4, 5]], [[6, 7, 8], [7, 8, 9], [8, 9, 0]]):
        target = deepcopy(grid)
        for row in (1, 2):
            for column in (1, 2):
                target[row][column] = grid[row - 1][column]
        examples.append(pair(grid, target))
    grammar = tuple(new.FEATURES.index(name) for name in ("border_top", "border_left"))
    previous = old.CellConditionalTree(examples, bounds=old.Bounds(**AMPLE), feature_indices=grammar)
    current = new.CellConditionalTree(examples, bounds=new.Bounds(**AMPLE), feature_indices=grammar)
    assert previous.status == current.status == "fitted"
    assert previous.forest == current.forest
    assert len(current.forest["choices"]) >= 2
    assert "neighbor_1" in json.dumps(current.forest) and "neighbor_3" in json.dumps(current.forest)
    query = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    assert current.候補(query, {}) == previous.候補(query, {}) == (None, {"reason": "ambiguous_minimal_trees"})


def test_infeasible_teacher_support_uses_less_actual_work_with_same_ample_result():
    examples = [pair([[1] * 4 for _ in range(4)], [[6] * 4 for _ in range(4)]),
                pair([[2] * 4 for _ in range(4)], [[7] * 4 for _ in range(4)])]
    previous = old.CellConditionalTree(examples, bounds=old.Bounds(**AMPLE))
    current = new.CellConditionalTree(examples, bounds=new.Bounds(**AMPLE))
    assert previous.status == current.status == "no_exact_bounded_tree"
    assert previous.forest is current.forest is None
    assert current.fit_states < previous.fit_states
    assert current.work_units < previous.work_units
    # The same smaller test cap gives a complete impossibility result only
    # after sound pruning; production defaults remain 256 states unchanged.
    limited_previous = old.CellConditionalTree(examples, bounds=old.Bounds(max_fit_states=128))
    limited_current = new.CellConditionalTree(examples, bounds=new.Bounds(max_fit_states=128))
    assert limited_previous.status == "fit_state_budget_exceeded"
    assert limited_current.status == "no_exact_bounded_tree"


def test_cell_support_prune_is_sound_independently_of_teacher_floor():
    examples = [pair([[0, 1]], [[0, 6]]), pair([[1, 0]], [[6, 0]])]
    settings = {**AMPLE, "minimum_cell_support": 3}
    previous = old.CellConditionalTree(examples, bounds=old.Bounds(**settings))
    current = new.CellConditionalTree(examples, bounds=new.Bounds(**settings))
    assert previous.status == current.status == "no_exact_bounded_tree"
    assert current.fit_states < previous.fit_states
    assert current.work_units <= previous.work_units


def test_duplicate_inputs_do_not_gain_support_and_invalids_still_hold():
    example = pair([[0, 1]], [[0, 6]])
    for engine in (old, new):
        assert engine.CellConditionalTree([example, deepcopy(example)]).status == "insufficient_distinct_teachers"
        bad = deepcopy(example)
        bad["output"] = [[9, 9]]
        assert engine.CellConditionalTree([example, bad]).status == "conflicting_duplicate_input"


def test_default_budget_and_serialization_still_replay_count_condition():
    examples = []
    for active, single, color in ((1, 5, 1), (2, 4, 3), (3, 1, 5)):
        grid = [[0] * 7 for _ in range(7)]
        grid[active][0] = grid[active][-1] = color
        grid[single][0] = color + 1
        target = [[6] * 7 if sum(value != 0 for value in row) == 2 else row[:] for row in grid]
        examples.append(pair(grid, target))
    previous, current = old.CellConditionalTree(examples), new.CellConditionalTree(examples)
    assert previous.status == current.status == "fitted"
    assert previous.forest == current.forest
    assert current.training_replayed == 3
    restored = new.CellConditionalTree.from_state(json.loads(json.dumps(current.model_state())))
    assert restored.model_state() == current.model_state()
    assert all(restored.候補(pair["input"], {})[0] == pair["output"] for pair in examples)
