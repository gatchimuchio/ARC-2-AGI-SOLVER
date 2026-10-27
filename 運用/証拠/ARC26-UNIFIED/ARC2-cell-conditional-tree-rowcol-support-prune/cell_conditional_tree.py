"""Isolated bounded categorical cell-tree induction; no production integration.

Features use current input context, color roles and row/column foreground counts. Leaves are typed
input-color roles or constant colors. Every equally simple retained tree must
agree; unseen categories, undefined roles and incomplete search produce HOLD.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
import sys

from 接続.ARC2.局所近傍変換候補 import _context, _shape
from 接続.ARC2.既存物体特徴 import dominant_background_for_grid
from 接続.ARC2.受動凡例転写核 import colour_prefix, rectangle_count


SCHEMA = "arc2-cell-conditional-tree-rowcol-v1"
HDS_BOUNDARY = "ARC入力セル条件木_実験v1"
NEIGHBORS = (0, 1, 2, 3, 5, 6, 7, 8)
ROLES = ("center", *(f"neighbor_{index}" for index in NEIGHBORS), "background", "unique_rarest")
PROGRAMS = (*ROLES, *(f"constant:{color}" for color in range(10)))
FEATURES = (
    *(f"context_{index}" for index in range(9)),
    *(f"equals_center_{index}" for index in NEIGHBORS),
    *(f"background_role_{index}" for index in range(9)),
    "border_top", "border_bottom", "border_left", "border_right",
    "cardinal_same_count", "cardinal_foreground_count", "palette_count",
    "row_foreground_count", "column_foreground_count",
)


def _domain(feature: str) -> set[str]:
    if feature.startswith("context_"):
        return {str(value) for value in range(-1, 10)}
    if feature.startswith("equals_center_"):
        return {"outside", "same", "different"}
    if feature.startswith("background_role_"):
        return {"outside", "unknown", "background", "foreground"}
    if feature.startswith("border_"):
        return {"0", "1"}
    if feature == "cardinal_same_count":
        return {str(value) for value in range(5)}
    if feature == "cardinal_foreground_count":
        return {"unknown", *(str(value) for value in range(5))}
    if feature in {"row_foreground_count", "column_foreground_count"}:
        return {"unknown", *(str(value) for value in range(31))}
    return {str(value) for value in range(1, 11)}


@dataclass(frozen=True)
class Bounds:
    max_depth: int = 3
    max_nodes: int = 15
    max_teachers: int = 8
    max_training_cells: int = 4096
    minimum_teacher_support: int = 2
    minimum_cell_support: int = 2
    max_fit_states: int = 256
    max_alternatives: int = 32
    max_work_units: int = 2_000_000

    def __post_init__(self):
        if any(type(value) is not int or value < 1 for value in asdict(self).values()):
            raise ValueError("bounds must be positive integers")
        if self.minimum_teacher_support < 2 or self.minimum_cell_support < 2:
            raise ValueError("two distinct teacher inputs and two cells are required")


class _Hold(Exception):
    pass


def _input_cells(grid):
    """Feature/role extractor: no output, identifiers or absolute coordinates."""
    shape = _shape(grid)
    if shape is None or max(shape) > 30:
        raise ValueError("invalid ARC grid")
    counts = Counter(color for row in grid for color in row)
    maximum, minimum = max(counts.values()), min(counts.values())
    # The existing dominant role is used only when its physical role is unique.
    background = dominant_background_for_grid(grid) if sum(value == maximum for value in counts.values()) == 1 else None
    rare = next(color for color, value in counts.items() if value == minimum) if sum(value == minimum for value in counts.values()) == 1 else None
    if background is None:
        row_foreground = ["unknown"] * shape[0]
        column_foreground = ["unknown"] * shape[1]
    else:
        prefix = colour_prefix(grid, background)
        row_foreground = [str(shape[1] - rectangle_count(prefix, (row, 0, row, shape[1] - 1))) for row in range(shape[0])]
        column_foreground = [str(shape[0] - rectangle_count(prefix, (0, column, shape[0] - 1, column))) for column in range(shape[1])]
    result = []
    for row in range(shape[0]):
        for column in range(shape[1]):
            context = _context(grid, row, column)
            center = context[4]
            values = [*(str(value) for value in context)]
            values.extend("outside" if context[index] < 0 else "same" if context[index] == center else "different" for index in NEIGHBORS)
            values.extend("outside" if value < 0 else "unknown" if background is None else "background" if value == background else "foreground" for value in context)
            values.extend(str(int(context[index] < 0)) for index in (1, 7, 3, 5))
            values.append(str(sum(context[index] == center for index in (1, 3, 5, 7))))
            values.append("unknown" if background is None else str(sum(context[index] >= 0 and context[index] != background for index in (1, 3, 5, 7))))
            values.append(str(len(counts)))
            values.extend((row_foreground[row], column_foreground[column]))
            roles = (center, *(context[index] if context[index] >= 0 else None for index in NEIGHBORS), background, rare)
            result.append((tuple(values), roles))
    return result


def _program_value(program, roles):
    return int(program.split(":")[1]) if program.startswith("constant:") else roles[ROLES.index(program)]


def _program_cost(program):
    # Fixed experimental MDL prior: prefer input roles over absolute colors.
    if program.startswith("constant:"):
        return 1, 0
    return 0, 0 if program == "center" else 2 if program == "unique_rarest" else 1


def _tree_cost(tree):
    if tree["kind"] == "leaf":
        return (1, *_program_cost(tree["programs"][0]))
    children = list(tree["branches"].values())
    return (1 + sum(child["cost"][0] for child in children),
            sum(child["cost"][1] for child in children),
            sum(child["cost"][2] for child in children))


def _evaluate(forest, features, roles):
    outputs = set()
    for tree in forest["choices"]:
        if tree["kind"] == "leaf":
            values = {_program_value(program, roles) for program in tree["programs"]}
        else:
            category = features[tree["feature_index"]]
            if category not in tree["branches"]:
                raise _Hold("unseen_feature_category")
            values = {_evaluate(tree["branches"][category], features, roles)}
        if None in values:
            raise _Hold("undefined_color_role")
        outputs.update(values)
        if len(outputs) != 1:
            raise _Hold("ambiguous_minimal_trees")
    return next(iter(outputs))


def _connection():
    hds_root = Path(__file__).resolve().parents[4] / "HDS/学習系統/v0.4.2"
    if str(hds_root) not in sys.path:
        sys.path.insert(0, str(hds_root))
    from 接続.ARC2 import HDS接続
    return HDS接続


def new_hds_machine():
    return _connection().HDS学習実行系()


class CellConditionalTree:
    def __init__(self, teachers, *, bounds=Bounds(), feature_indices=tuple(range(len(FEATURES)))):
        self.bounds = bounds
        self.feature_indices = tuple(sorted(set(feature_indices)))
        if not self.feature_indices or any(type(index) is not int or not 0 <= index < len(FEATURES) for index in self.feature_indices):
            raise ValueError("invalid feature grammar")
        self.status = "unfitted"
        self.training_examples = len(teachers)
        self.distinct_training_examples = self.training_cells = self.fit_states = self.work_units = self.training_replayed = 0
        self.forest = None
        try:
            self._fit(teachers)
        except _Hold as error:
            self.status = str(error)
            self.forest = None

    def _fit(self, teachers):
        if len(teachers) > self.bounds.max_teachers:
            raise _Hold("teacher_budget_exceeded")
        unique = {}
        for pair in teachers:
            if not isinstance(pair, dict) or _shape(pair.get("input")) is None or _shape(pair.get("output")) is None:
                raise _Hold("invalid_teacher")
            if _shape(pair["input"]) != _shape(pair["output"]):
                raise _Hold("teacher_shape_changed")
            if max(_shape(pair["input"])) > 30:
                raise _Hold("invalid_teacher")
            input_key = tuple(tuple(row) for row in pair["input"])
            if input_key in unique and unique[input_key]["output"] != pair["output"]:
                raise _Hold("conflicting_duplicate_input")
            unique[input_key] = pair
        ordered = [unique[item] for item in sorted(unique)]
        self.distinct_training_examples = len(ordered)
        if len(ordered) < self.bounds.minimum_teacher_support:
            raise _Hold("insufficient_distinct_teachers")
        self.training_cells = sum(len(pair["input"]) * len(pair["input"][0]) for pair in ordered)
        if self.training_cells > self.bounds.max_training_cells:
            raise _Hold("training_cell_budget_exceeded")
        records = []
        for teacher_index, pair in enumerate(ordered):
            targets = [value for row in pair["output"] for value in row]
            records.extend((features, roles, target, teacher_index) for (features, roles), target in zip(_input_cells(pair["input"]), targets, strict=True))

        def spend(amount):
            self.work_units += amount
            if self.work_units > self.bounds.max_work_units:
                raise _Hold("work_budget_exceeded")

        infeasible_subsets = set()

        @lru_cache(maxsize=None)
        def leaf(indices):
            spend(len(indices))
            subset = [records[index] for index in indices]
            teacher_support = len({record[3] for record in subset})
            if teacher_support < self.bounds.minimum_teacher_support or len(subset) < self.bounds.minimum_cell_support:
                infeasible_subsets.add(indices)
                return None
            leaf_programs = []
            for program in PROGRAMS:
                for _features, roles, target, _teacher in subset:
                    spend(1)
                    if _program_value(program, roles) != target:
                        break
                else:
                    leaf_programs.append(program)
            if leaf_programs:
                best = min(map(_program_cost, leaf_programs))
                programs = [program for program in leaf_programs if _program_cost(program) == best]
                tree = {"kind": "leaf", "programs": programs, "teacher_support": teacher_support, "cell_support": len(subset)}
                return {"cost": list(_tree_cost(tree)), "choices": [tree]}
            return None

        @lru_cache(maxsize=None)
        def fit(indices, depth):
            if indices in infeasible_subsets:
                return None
            self.fit_states += 1
            if self.fit_states > self.bounds.max_fit_states:
                raise _Hold("fit_state_budget_exceeded")
            result = leaf(indices)
            if result is not None:
                return result
            if indices in infeasible_subsets:
                return None
            if depth == self.bounds.max_depth:
                return None
            best, alternatives = None, []
            partitions = []

            def retain(tree):
                nonlocal best, alternatives
                cost = _tree_cost(tree)
                if cost[0] > self.bounds.max_nodes or (best is not None and cost > best):
                    return
                if best is None or cost < best:
                    best, alternatives = cost, []
                if tree not in alternatives:
                    alternatives.append(tree)
                    if len(alternatives) > self.bounds.max_alternatives:
                        raise _Hold("alternative_budget_exceeded")

            # Enumerate all one-level splits before any deeper subtree. A tree
            # with an internal child needs at least five nodes, so a complete
            # three/four-node result is already globally minimal in node cost.
            for feature_index in self.feature_indices:
                groups = {}
                spend(len(indices))
                for index in indices:
                    groups.setdefault(records[index][0][feature_index], []).append(index)
                if len(groups) < 2 or len(groups) + 1 > self.bounds.max_nodes:
                    continue
                groups = {category: tuple(groups[category]) for category in sorted(groups)}
                partitions.append((feature_index, groups))
                branches = {}
                for category, child_indices in groups.items():
                    child = leaf(child_indices)
                    if child is None:
                        break
                    branches[category] = child
                else:
                    retain({"kind": "split", "feature_index": feature_index, "branches": branches})
            if best is not None and best[0] < 5:
                return {"cost": list(best), "choices": alternatives}
            for feature_index, groups in partitions:
                if best is not None and len(groups) + 1 > best[0]:
                    continue
                branches = {}
                for category, child_indices in groups.items():
                    child = fit(child_indices, depth + 1)
                    if child is None:
                        break
                    branches[category] = child
                else:
                    retain({"kind": "split", "feature_index": feature_index, "branches": branches})
            return {"cost": list(best), "choices": alternatives} if alternatives else None

        self.forest = fit(tuple(range(len(records))), 0)
        if self.forest is None:
            raise _Hold("no_exact_bounded_tree")
        self.status = "fitted"
        for pair in ordered:
            prediction, _diagnostic = self.候補(pair["input"], {})
            if prediction != pair["output"]:
                raise _Hold("full_train_validation_failed")
        self.training_replayed = len(ordered)

    def 候補(self, grid, _context_or_expected=None):
        if _shape(grid) is None or max(_shape(grid)) > 30:
            return None, {"reason": "invalid_grid"}
        if self.status != "fitted":
            return None, {"reason": self.status}
        try:
            colors = [_evaluate(self.forest, features, roles) for features, roles in _input_cells(grid)]
        except _Hold as error:
            return None, {"reason": str(error)}
        width = len(grid[0])
        return [colors[index:index + width] for index in range(0, len(colors), width)], {"reason": "all_minimal_trees_agree", "root_alternatives": len(self.forest["choices"])}

    def model_state(self):
        from copy import deepcopy
        return {"schema": SCHEMA, "status": self.status, "bounds": asdict(self.bounds), "feature_indices": list(self.feature_indices),
                "training_examples": self.training_examples, "distinct_training_examples": self.distinct_training_examples,
                "training_cells": self.training_cells, "fit_states": self.fit_states, "work_units": self.work_units, "training_replayed": self.training_replayed,
                "forest": deepcopy(self.forest)}

    @classmethod
    def from_state(cls, state):
        allowed = {"schema", "status", "bounds", "feature_indices", "training_examples", "distinct_training_examples", "training_cells", "fit_states", "work_units", "training_replayed", "forest"}
        if not isinstance(state, dict) or set(state) != allowed or state["schema"] != SCHEMA:
            raise ValueError("invalid state schema")
        engine = cls([], bounds=Bounds(**state["bounds"]), feature_indices=state["feature_indices"])
        if list(engine.feature_indices) != state["feature_indices"]:
            raise ValueError("noncanonical feature grammar")
        for field in ("training_examples", "distinct_training_examples", "training_cells", "fit_states", "work_units", "training_replayed"):
            if type(state[field]) is not int or state[field] < 0:
                raise ValueError("invalid evidence count")
            setattr(engine, field, state[field])
        if engine.distinct_training_examples > engine.training_examples:
            raise ValueError("invalid distinct support count")
        statuses = {"fitted", "teacher_budget_exceeded", "invalid_teacher", "teacher_shape_changed", "conflicting_duplicate_input", "insufficient_distinct_teachers", "training_cell_budget_exceeded", "fit_state_budget_exceeded", "work_budget_exceeded", "alternative_budget_exceeded", "no_exact_bounded_tree", "full_train_validation_failed"}
        if state["status"] not in statuses:
            raise ValueError("invalid fit status")
        engine.status = state["status"]
        if engine.status != "fitted":
            if state["forest"] is not None or state["training_replayed"]:
                raise ValueError("HOLD cannot contain an executable forest")
            return engine
        if not engine.bounds.minimum_teacher_support <= engine.distinct_training_examples <= engine.training_examples <= engine.bounds.max_teachers or engine.training_replayed != engine.distinct_training_examples or engine.training_cells > engine.bounds.max_training_cells or engine.fit_states > engine.bounds.max_fit_states or engine.work_units > engine.bounds.max_work_units:
            raise ValueError("invalid fitted-state support")

        def validate(forest, depth):
            if not isinstance(forest, dict) or set(forest) != {"cost", "choices"} or not isinstance(forest["choices"], list) or not 1 <= len(forest["choices"]) <= engine.bounds.max_alternatives:
                raise ValueError("invalid forest")
            if not isinstance(forest["cost"], list) or len(forest["cost"]) != 3 or any(type(value) is not int or value < 0 for value in forest["cost"]):
                raise ValueError("invalid cost")
            for tree in forest["choices"]:
                if not isinstance(tree, dict):
                    raise ValueError("invalid tree")
                if tree.get("kind") == "leaf":
                    if set(tree) != {"kind", "programs", "teacher_support", "cell_support"} or not isinstance(tree["programs"], list) or not tree["programs"] or len(tree["programs"]) != len(set(tree["programs"])) or any(program not in PROGRAMS for program in tree["programs"]):
                        raise ValueError("invalid typed leaf")
                    if any(_program_cost(program) != _program_cost(tree["programs"][0]) for program in tree["programs"]):
                        raise ValueError("mixed leaf complexities")
                    if type(tree["teacher_support"]) is not int or not engine.bounds.minimum_teacher_support <= tree["teacher_support"] <= engine.distinct_training_examples or type(tree["cell_support"]) is not int or not engine.bounds.minimum_cell_support <= tree["cell_support"] <= engine.training_cells:
                        raise ValueError("invalid leaf support")
                elif tree.get("kind") == "split":
                    if set(tree) != {"kind", "feature_index", "branches"} or type(tree["feature_index"]) is not int or tree["feature_index"] not in engine.feature_indices or depth >= engine.bounds.max_depth or not isinstance(tree["branches"], dict) or len(tree["branches"]) < 2 or not set(tree["branches"]) <= _domain(FEATURES[tree["feature_index"]]):
                        raise ValueError("invalid categorical split")
                    for child in tree["branches"].values():
                        validate(child, depth + 1)
                else:
                    raise ValueError("invalid tree kind")
                if _tree_cost(tree) != tuple(forest["cost"]) or forest["cost"][0] > engine.bounds.max_nodes:
                    raise ValueError("tree complexity mismatch")
        validate(state["forest"], 0)
        from copy import deepcopy
        engine.forest = deepcopy(state["forest"])
        return engine

    def admit_to_hds(self, machine, teachers):
        return _connection().候補機構を学習(machine, {"train": teachers, "test": []}, [], HDS_BOUNDARY, self.候補)

    def query_via_hds(self, machine, grid):
        candidate, diagnostic = self.候補(grid, {})
        if candidate is None:
            return {"answer": None, "status": "candidate_hold", "reasons": [diagnostic["reason"]], "hds_queried": False}
        connection = _connection()
        result = connection.出力格子(machine, connection.観測へ({"候補": candidate}, HDS_BOUNDARY), 同値必須=True)
        return {**result, "hds_queried": True, "candidate_diagnostic": diagnostic}
