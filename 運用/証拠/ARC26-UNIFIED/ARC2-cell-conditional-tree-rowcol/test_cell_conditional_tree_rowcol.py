import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest


HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "ARC2-cell-conditional-tree/cell_conditional_tree.py"
NEW = HERE / "cell_conditional_tree.py"
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


old = load(OLD, "old_tree33_rowcol_tests")
new = load(NEW, "new_tree35_rowcol_tests")


def teachers():
    examples = []
    for active, single, first_color in ((1, 5, 1), (2, 4, 3), (3, 1, 5)):
        grid = [[0] * 7 for _ in range(7)]
        grid[active][0] = grid[active][-1] = first_color
        grid[single][0] = first_color + 1
        examples.append({"input": grid, "output": target(grid)})
    return examples


def target(grid):
    return [[6] * len(row) if sum(value != 0 for value in row) == 2 else row[:] for row in grid]


def query():
    grid = [[0] * 9 for _ in range(7)]
    grid[3][0], grid[3][-1] = 7, 8
    grid[4][0], grid[4][-1] = 8, 9
    grid[1][0] = 5
    return grid


def test_only_feature_grammar_schema_and_extraction_differ_from_frozen_core():
    assert hashlib.sha256(OLD.read_bytes()).hexdigest() == "f1116b7c386baad86a958af5f936b598960e83a64a9644b548efbda3978a49c4"
    def core(path):
        result = []
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                continue
            if isinstance(node, ast.FunctionDef) and node.name in {"_domain", "_input_cells"}:
                continue
            if isinstance(node, ast.Assign) and any(isinstance(item, ast.Name) and item.id in {"SCHEMA", "FEATURES"} for item in node.targets):
                continue
            if isinstance(node, ast.ImportFrom) and node.module == "接続.ARC2.受動凡例転写核":
                assert {alias.name for alias in node.names} == {"colour_prefix", "rectangle_count"}
                continue
            result.append(ast.dump(node, include_attributes=False))
        return result
    assert core(OLD) == core(NEW)
    assert new.PROGRAMS == old.PROGRAMS and new.Bounds() == new.Bounds(**old.Bounds().__dict__)
    assert new.FEATURES[:33] == old.FEATURES
    assert new.FEATURES[33:] == ("row_foreground_count", "column_foreground_count")


def test_counts_use_whole_input_and_preserve_original_features_and_roles():
    grid = [[0, 0, 2], [0, 0, 0], [3, 0, 0]]
    first, extended = old._input_cells(grid), new._input_cells(grid)
    assert all(new_features[:33] == old_features and new_roles == old_roles
               for (old_features, old_roles), (new_features, new_roles) in zip(first, extended, strict=True))
    assert extended[3][0][-2:] == ("0", "1")
    assert extended[0][0][-2:] == ("1", "1")
    assert all(features[-2:] == ("unknown", "unknown") for features, _roles in new._input_cells([[0, 1], [1, 0]]))
    assert new._domain("row_foreground_count") == {"unknown", *(str(value) for value in range(31))}


def test_global_counts_generalize_where_same_old_features_need_different_outputs():
    examples = teachers()
    old_groups = {}
    for pair in examples:
        for (features, roles), value in zip(old._input_cells(pair["input"]), (v for row in pair["output"] for v in row), strict=True):
            viable = {program for program in old.PROGRAMS if old._program_value(program, roles) == value}
            if features in old_groups:
                old_groups[features].intersection_update(viable)
            else:
                old_groups[features] = viable
    assert any(not actions for actions in old_groups.values())  # Old grammar impossible at any depth.
    model = new.CellConditionalTree(examples)
    assert model.status == "fitted"
    assert model.training_replayed == 3
    assert model.候補(query(), {})[0] == target(query())
    assert all(model.候補(pair["input"], {})[0] == pair["output"] for pair in examples)


def test_state_roundtrip_carries_35_feature_domains_without_raw_teacher_grids():
    model = new.CellConditionalTree(teachers())
    state = json.loads(json.dumps(model.model_state()))
    restored = new.CellConditionalTree.from_state(state)
    assert state["schema"] == "arc2-cell-conditional-tree-rowcol-v1"
    assert state["feature_indices"] == list(range(35))
    assert restored.model_state() == state
    assert restored.候補(query(), {"expected": [[9]]})[0] == target(query())
    assert '"input"' not in json.dumps(state) and '"output"' not in json.dumps(state)
    altered = deepcopy(state)
    for tree in altered["forest"]["choices"]:
        if tree["kind"] == "split":
            tree["branches"]["31"] = next(iter(tree["branches"].values()))
    with pytest.raises(ValueError):
        new.CellConditionalTree.from_state(altered)


def test_existing_hds_admits_queries_and_preserves_counterexample_rejection():
    examples = teachers()
    model = new.CellConditionalTree(examples)
    machine = new.new_hds_machine()
    admission = model.admit_to_hds(machine, examples)
    assert admission["採用可"] is True and admission["同値採用"] is True
    output = model.query_via_hds(machine, query())
    assert output["hds_queried"] is True and output["answer"] == target(query())
    wrong = {"input": query(), "output": [[9] * 9 for _ in range(7)]}
    rejection = model.admit_to_hds(new.new_hds_machine(), [*examples, wrong])
    assert rejection["採用可"] is False and rejection["状態"] == "教師反例により不採用"
