"""Experimental one-predicate induction over existing typed ARC transforms.

Only current train pairs fit the predicate/programs. Runtime state contains no
teacher grids, target grids, task identifiers or answer lookup table. Prediction
requires agreement of every equally simple retained hypothesis; HDS admission
is a separate, unchanged validation step through the existing connector.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import product
import math
from pathlib import Path
import sys
from typing import Any

from 接続.ARC2.特徴近傍変換選択 import _feature
from 接続.ARC2.単純変換候補 import Model, apply_model, fitted_models, key, valid_grid


Grid = list[list[int]]
SCHEMA = "arc2-feature-predicate-transform-v1"
HDS_BOUNDARY = "ARC入力特徴述語単純変換_実験v1"
FEATURE_COUNT = 25
EPSILON = 1e-12
ORIENTATIONS = {
    "identity", "rotate90", "rotate180", "rotate270", "reflect_horizontal",
    "reflect_vertical", "transpose", "anti_transpose",
}
MODES = {"plain", "crop", "scale", "downscale", "tile"}


@dataclass(frozen=True)
class Bounds:
    minimum_branch_support: int = 2
    max_teachers: int = 8
    max_predicates: int = 128
    max_partitions: int = 32
    max_branch_programs: int = 16
    max_hypotheses: int = 256

    def __post_init__(self):
        if any(type(value) is not int or value < 1 for value in asdict(self).values()):
            raise ValueError("all search bounds must be positive integers")
        if self.minimum_branch_support < 2:
            raise ValueError("at least two distinct inputs per branch are required")


@dataclass(frozen=True)
class Predicate:
    feature_index: int
    lower_max: float
    upper_min: float

    def branch(self, features: tuple[float, ...]) -> int | None:
        value = features[self.feature_index]
        if value <= self.lower_max + EPSILON:
            return 0
        if value >= self.upper_min - EPSILON:
            return 1
        # Any threshold inside this unobserved interval fits training equally.
        return None

    def state(self) -> dict:
        return {
            "feature_index": self.feature_index,
            "lower_max": self.lower_max,
            "upper_min": self.upper_min,
            "threshold": self.lower_max + (self.upper_min - self.lower_max) / 2,
        }


@dataclass(frozen=True)
class Hypothesis:
    predicate: Predicate
    when_le: Model
    when_ge: Model
    support: tuple[int, int]


class _SearchHold(Exception):
    pass


def _program_key(model: Model) -> tuple:
    return model[1], tuple(model[2]), tuple(sorted(model[3].items()))


def _program_cost(model: Model) -> tuple[int, int, int, int]:
    mode, rows, columns, _background = model[2]
    recolors = sum(source != target for source, target in model[3].items())
    operations = int(mode != "plain") + int(model[1] != "identity") + 2 * recolors
    mode_cost = {"plain": 0, "crop": 1, "scale": 2, "downscale": 2, "tile": 3}[mode]
    return operations, mode_cost, rows * columns - 1, recolors


def _hypothesis_cost(left: Model, right: Model) -> tuple[int, ...]:
    cost = tuple(a + b for a, b in zip(_program_cost(left), _program_cost(right), strict=True))
    return (cost[0] + 1, *cost[1:])  # one additional predicate operation


def _program_state(model: Model) -> dict:
    mode, rows, columns, background = model[2]
    return {
        "orientation": model[1],
        "geometry": {"mode": mode, "rows": rows, "columns": columns, "background": background},
        "palette": {str(source): target for source, target in sorted(model[3].items())},
    }


def _program_from_state(state: dict) -> Model:
    if not isinstance(state, dict) or set(state) != {"orientation", "geometry", "palette"} or state["orientation"] not in ORIENTATIONS:
        raise ValueError("invalid typed transform state")
    geometry = state["geometry"]
    if not isinstance(geometry, dict) or set(geometry) != {"mode", "rows", "columns", "background"} or geometry["mode"] not in MODES:
        raise ValueError("invalid geometry state")
    rows, columns, background = geometry["rows"], geometry["columns"], geometry["background"]
    if any(type(value) is not int or not 1 <= value <= 4 for value in (rows, columns)):
        raise ValueError("invalid geometry factors")
    if geometry["mode"] in {"plain", "crop"} and (rows, columns) != (1, 1):
        raise ValueError("plain/crop factors must be one")
    if geometry["mode"] in {"scale", "downscale", "tile"} and (rows, columns) == (1, 1):
        raise ValueError("nontrivial geometry factors required")
    if geometry["mode"] == "crop":
        if type(background) is not int or not 0 <= background <= 9:
            raise ValueError("crop requires a color parameter")
    elif background is not None:
        raise ValueError("unexpected background parameter")
    palette = state["palette"]
    if not isinstance(palette, dict) or not palette or len(palette) > 10:
        raise ValueError("invalid palette state")
    mapping = {}
    for source, target in palette.items():
        if source not in {str(color) for color in range(10)} or type(target) is not int or not 0 <= target <= 9:
            raise ValueError("invalid palette parameter")
        mapping[int(source)] = target
    return ((), state["orientation"], (geometry["mode"], rows, columns, background), mapping)


def _hds_connection():
    hds_root = Path(__file__).resolve().parents[4] / "HDS/学習系統/v0.4.2"
    if str(hds_root) not in sys.path:
        sys.path.insert(0, str(hds_root))
    from 接続.ARC2 import HDS接続
    return HDS接続


def new_hds_machine():
    """Return the existing HDS machine with its unchanged default support gate."""
    return _hds_connection().HDS学習実行系()


class FeaturePredicateTransform:
    def __init__(self, teachers: list[dict[str, Grid]], *, bounds: Bounds = Bounds(), feature_indices=tuple(range(FEATURE_COUNT))):
        self.bounds = bounds
        self.feature_indices = tuple(sorted(set(feature_indices)))
        if not self.feature_indices or any(type(index) is not int or not 0 <= index < FEATURE_COUNT for index in self.feature_indices):
            raise ValueError("invalid feature grammar")
        self._status = "unfitted"
        self._teacher_count = len(teachers)
        self._distinct_count = 0
        self._complexity = None
        self._hypotheses: tuple[Hypothesis, ...] = ()
        self._training_replayed = 0
        self._stats = {"predicates": 0, "partitions": 0, "model_fit_calls": 0, "global_models": 0}
        try:
            self._fit(teachers)
        except _SearchHold as error:
            self._status = str(error)
            self._hypotheses = ()
            self._complexity = None

    def _fit(self, teachers):
        if len(teachers) > self.bounds.max_teachers:
            raise _SearchHold("teacher_budget_exceeded")
        if any(not isinstance(pair, dict) or not valid_grid(pair.get("input")) or not valid_grid(pair.get("output")) for pair in teachers):
            raise _SearchHold("invalid_teacher")
        unique = {}
        for pair in teachers:
            input_key = key(pair["input"])
            if input_key in unique and unique[input_key]["output"] != pair["output"]:
                raise _SearchHold("conflicting_duplicate_input")
            unique[input_key] = pair
        ordered = [unique[input_key] for input_key in sorted(unique)]
        self._distinct_count = len(ordered)
        if len(ordered) < 2 * self.bounds.minimum_branch_support:
            raise _SearchHold("insufficient_distinct_support")
        if len(ordered) > self.bounds.max_teachers:
            raise _SearchHold("teacher_budget_exceeded")
        global_models = fitted_models(ordered)
        self._stats["model_fit_calls"] += 1
        self._stats["global_models"] = len(global_models)
        if global_models:
            raise _SearchHold("global_transform_already_supported")

        features = [_feature(pair["input"]) for pair in ordered]
        predicates = []
        partitions = set()
        for index in self.feature_indices:
            values = sorted({feature[index] for feature in features})
            for lower, upper in zip(values, values[1:]):
                left = tuple(i for i, feature in enumerate(features) if feature[index] <= lower)
                right = tuple(i for i, feature in enumerate(features) if feature[index] >= upper)
                if min(len(left), len(right)) < self.bounds.minimum_branch_support:
                    continue
                predicates.append((Predicate(index, lower, upper), left, right))
                partitions.add(tuple(sorted((left, right))))
        self._stats["predicates"] = len(predicates)
        self._stats["partitions"] = len(partitions)
        if len(predicates) > self.bounds.max_predicates:
            raise _SearchHold("predicate_budget_exceeded")
        if len(partitions) > self.bounds.max_partitions:
            raise _SearchHold("partition_budget_exceeded")

        cache = {}
        def branch_models(indices):
            if indices not in cache:
                models = fitted_models([ordered[index] for index in indices])
                self._stats["model_fit_calls"] += 1
                if not models:
                    cache[indices] = ()
                else:
                    simplest = min(_program_cost(model) for model in models)
                    retained = {_program_key(model): model for model in models if _program_cost(model) == simplest}
                    if len(retained) > self.bounds.max_branch_programs:
                        raise _SearchHold("branch_program_budget_exceeded")
                    cache[indices] = tuple(retained[name] for name in sorted(retained))
            return cache[indices]

        best, retained = None, []
        for predicate, left, right in predicates:
            left_models, right_models = branch_models(left), branch_models(right)
            if not left_models or not right_models:
                continue
            cost = _hypothesis_cost(left_models[0], right_models[0])
            if best is not None and cost > best:
                continue
            if best is None or cost < best:
                best, retained = cost, []
            for left_model, right_model in product(left_models, right_models):
                if _program_key(left_model) == _program_key(right_model):
                    continue
                retained.append(Hypothesis(predicate, left_model, right_model, (len(left), len(right))))
                if len(retained) > self.bounds.max_hypotheses:
                    raise _SearchHold("hypothesis_budget_exceeded")
        if not retained:
            raise _SearchHold("no_conditional_model")
        for hypothesis in retained:
            for feature, pair in zip(features, ordered, strict=True):
                branch = hypothesis.predicate.branch(feature)
                model = hypothesis.when_le if branch == 0 else hypothesis.when_ge
                if branch is None or apply_model(model, pair["input"]) != pair["output"]:
                    raise _SearchHold("full_train_validation_failed")
        self._complexity = best
        self._hypotheses = tuple(retained)
        self._training_replayed = len(ordered)
        self._status = "fitted"

    def 候補(self, grid: Grid, _expected: dict[str, Any] | None = None):
        if not valid_grid(grid):
            return None, {"reason": "invalid_grid"}
        if self._status != "fitted":
            return None, {"reason": self._status}
        features = _feature(grid)
        colors = {color for row in grid for color in row}
        outputs = set()
        for hypothesis in self._hypotheses:
            branch = hypothesis.predicate.branch(features)
            if branch is None:
                return None, {"reason": "unobserved_predicate_gap"}
            model = hypothesis.when_le if branch == 0 else hypothesis.when_ge
            mapping = model[3]
            if any(source != target for source, target in mapping.items()) and not colors <= mapping.keys():
                return None, {"reason": "unobserved_recolor_input"}
            output = apply_model(model, grid)
            if not valid_grid(output):
                return None, {"reason": "typed_program_not_applicable"}
            outputs.add(key(output))
            if len(outputs) != 1:
                return None, {"reason": "ambiguous_minimal_hypotheses"}
        return [list(row) for row in next(iter(outputs))], {"reason": "all_minimal_hypotheses_agree", "hypotheses": len(self._hypotheses)}

    def model_state(self) -> dict:
        return {
            "schema": SCHEMA, "status": self._status,
            "training_examples": self._teacher_count, "distinct_training_examples": self._distinct_count,
            "bounds": asdict(self.bounds), "feature_indices": list(self.feature_indices),
            "complexity": list(self._complexity) if self._complexity is not None else None,
            "training_replayed": self._training_replayed, "stats": dict(self._stats),
            "hypotheses": [{"predicate": hypothesis.predicate.state(), "when_le": _program_state(hypothesis.when_le),
                            "when_ge": _program_state(hypothesis.when_ge), "support": list(hypothesis.support)}
                           for hypothesis in self._hypotheses],
        }

    @classmethod
    def from_state(cls, state: dict):
        allowed = {"schema", "status", "training_examples", "distinct_training_examples", "bounds", "feature_indices", "complexity", "training_replayed", "stats", "hypotheses"}
        if not isinstance(state, dict) or set(state) != allowed or state["schema"] != SCHEMA:
            raise ValueError("invalid model state schema")
        engine = cls([], bounds=Bounds(**state["bounds"]), feature_indices=state["feature_indices"])
        if list(engine.feature_indices) != state["feature_indices"]:
            raise ValueError("feature grammar must be canonical")
        counts = (state["training_examples"], state["distinct_training_examples"], state["training_replayed"])
        if any(type(value) is not int or value < 0 for value in counts) or counts[0] < counts[1]:
            raise ValueError("invalid observation counts")
        if set(state["stats"]) != {"predicates", "partitions", "model_fit_calls", "global_models"} or any(type(value) is not int or value < 0 for value in state["stats"].values()):
            raise ValueError("invalid search statistics")
        statuses = {"fitted", "invalid_teacher", "conflicting_duplicate_input", "insufficient_distinct_support", "teacher_budget_exceeded", "global_transform_already_supported", "predicate_budget_exceeded", "partition_budget_exceeded", "branch_program_budget_exceeded", "hypothesis_budget_exceeded", "no_conditional_model", "full_train_validation_failed"}
        if state["status"] not in statuses or not isinstance(state["hypotheses"], list):
            raise ValueError("invalid fit status")
        engine._teacher_count = state["training_examples"]
        engine._distinct_count = state["distinct_training_examples"]
        engine._training_replayed = state["training_replayed"]
        engine._stats = dict(state["stats"])
        engine._status = state["status"]
        engine._complexity = tuple(state["complexity"]) if state["complexity"] is not None else None
        if engine._status != "fitted":
            if state["hypotheses"] or state["complexity"] is not None or state["training_replayed"]:
                raise ValueError("HOLD state cannot contain executable hypotheses")
            return engine
        if engine._distinct_count > engine.bounds.max_teachers or engine._training_replayed != engine._distinct_count or not isinstance(state["complexity"], list) or len(state["complexity"]) != 4 or any(type(value) is not int or value < 0 for value in state["complexity"]):
            raise ValueError("invalid fitted-state evidence counts")
        if not state["hypotheses"] or len(state["hypotheses"]) > engine.bounds.max_hypotheses:
            raise ValueError("invalid hypothesis count")
        retained = []
        for item in state["hypotheses"]:
            if set(item) != {"predicate", "when_le", "when_ge", "support"}:
                raise ValueError("unexpected hypothesis fields")
            predicate = item["predicate"]
            if set(predicate) != {"feature_index", "lower_max", "upper_min", "threshold"}:
                raise ValueError("invalid predicate state")
            index, lower, upper = predicate["feature_index"], predicate["lower_max"], predicate["upper_min"]
            if type(index) is not int or index not in engine.feature_indices or not all(type(value) in (int, float) and math.isfinite(value) for value in (lower, upper)) or not lower < upper:
                raise ValueError("invalid predicate bounds")
            if type(predicate["threshold"]) not in (int, float) or not math.isfinite(predicate["threshold"]) or abs(predicate["threshold"] - (lower + (upper - lower) / 2)) > EPSILON:
                raise ValueError("invalid threshold")
            support = tuple(item["support"])
            if len(support) != 2 or any(type(value) is not int or value < engine.bounds.minimum_branch_support for value in support) or sum(support) != engine._distinct_count:
                raise ValueError("invalid branch support")
            left, right = _program_from_state(item["when_le"]), _program_from_state(item["when_ge"])
            if _program_key(left) == _program_key(right) or _hypothesis_cost(left, right) != engine._complexity:
                raise ValueError("program complexity mismatch")
            retained.append(Hypothesis(Predicate(index, lower, upper), left, right, support))
        engine._hypotheses = tuple(retained)
        return engine

    def 記録(self):
        return {"status": self._status, "training_examples": self._teacher_count,
                "distinct_training_examples": self._distinct_count, "retained_hypotheses": len(self._hypotheses),
                "training_replayed": self._training_replayed, **self._stats}

    def admit_to_hds(self, machine, teachers):
        connection = _hds_connection()
        return connection.候補機構を学習(machine, {"train": teachers, "test": []}, [], HDS_BOUNDARY, self.候補)

    def query_via_hds(self, machine, grid):
        candidate, diagnostic = self.候補(grid, {})
        if candidate is None:
            return {"answer": None, "status": "candidate_hold", "reasons": [diagnostic["reason"]], "hds_queried": False}
        connection = _hds_connection()
        result = connection.出力格子(machine, connection.観測へ({"候補": candidate}, HDS_BOUNDARY), 同値必須=True)
        return {**result, "hds_queried": True, "candidate_diagnostic": diagnostic}
