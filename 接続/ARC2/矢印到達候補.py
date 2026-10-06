"""Pure finite arrow-pulse candidate; no task identifiers or target lookup."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from itertools import product

from 接続.ARC2.既存物体特徴 import color_components, dominant_background_for_grid
from 接続.ARC2.既存疎点転写 import shifted_sparse_point_mask

DIRECTIONS = ((-1, 0), (-1, 1), (0, 1), (1, 1),
              (1, 0), (1, -1), (0, -1), (-1, -1))
SCOPES = ("cell", "component")
MODEL_COUNT = 29 * 2 * 10 * 10
FIT_BUDGET = 200_000


@dataclass(frozen=True, order=True)
class Model:
    distance: int
    scope: str
    single_color: int
    multiple_color: int


@dataclass(frozen=True)
class Actor:
    color: int
    cells: tuple[tuple[int, int], ...]
    tip: tuple[int, int]
    direction: tuple[int, int]


@dataclass(frozen=True)
class Scene:
    grid: tuple[tuple[int, ...], ...]
    background: int
    actors: tuple[Actor, ...]


@dataclass(frozen=True)
class Fitted:
    models: tuple[Model, ...]


def valid_grid(grid):
    return (isinstance(grid, list) and 1 <= len(grid) <= 30
            and isinstance(grid[0], list) and 1 <= len(grid[0]) <= 30
            and all(isinstance(row, list) and len(row) == len(grid[0])
                    and all(type(v) is int and 0 <= v <= 9 for v in row)
                    for row in grid))


def all_models():
    return tuple(Model(*v) for v in product(range(1, 30), SCOPES, range(10), range(10)))


def parse_input(grid):
    if not valid_grid(grid):
        return None, {"status": "HOLD", "reason": "invalid_grid"}
    counts = Counter(v for row in grid for v in row)
    modes = tuple(sorted(v for v, n in counts.items() if n == max(counts.values())))
    if len(modes) != 1:
        return None, {"status": "HOLD", "reason": "background_tie", "roles": modes}
    snapshot = tuple(tuple(row) for row in grid)
    background = dominant_background_for_grid(snapshot)
    if background != modes[0]:
        return None, {"status": "HOLD", "reason": "helper_background_disagreement"}
    actors = []
    covered = set()
    foreground = {(r, c) for r, row in enumerate(snapshot)
                  for c, v in enumerate(row) if v != background}
    for color in sorted(counts):
        if color == background:
            continue
        for component in color_components(snapshot, color, include_diagonal=True):
            cells = frozenset(component["cells"])
            if len(cells) != 3:
                return None, {"status": "HOLD", "reason": "non_arrow_component",
                              "color": color, "cells": sorted(cells)}
            roles = []
            for tip in sorted(cells):
                for i, direction in enumerate(DIRECTIONS):
                    arm_a, arm_b = DIRECTIONS[(i - 1) % 8], DIRECTIONS[(i + 1) % 8]
                    mask = {tip, (tip[0] - arm_a[0], tip[1] - arm_a[1]),
                            (tip[0] - arm_b[0], tip[1] - arm_b[1])}
                    if mask == cells:
                        roles.append((tip, direction))
            if len(roles) != 1:
                return None, {"status": "HOLD", "reason": "arrow_role_not_unique",
                              "color": color, "cells": sorted(cells), "roles": roles}
            if covered & cells:
                return None, {"status": "HOLD", "reason": "input_ownership_overlap"}
            covered.update(cells)
            actors.append(Actor(color, tuple(sorted(cells)), *roles[0]))
    if not actors or covered != foreground:
        return None, {"status": "HOLD", "reason": "input_ownership_incomplete"}
    actors = tuple(sorted(actors, key=lambda a: (a.cells, a.color)))
    scene = Scene(snapshot, background, actors)
    return scene, {"status": "OK", "background": background,
                   "actors": [asdict(a) for a in actors],
                   "owned_foreground_count": len(covered),
                   "input_shape": (len(snapshot), len(snapshot[0]))}


def valid_model(model):
    return (isinstance(model, Model) and type(model.distance) is int
            and 1 <= model.distance <= 29 and model.scope in SCOPES
            and type(model.single_color) is int and 0 <= model.single_color <= 9
            and type(model.multiple_color) is int and 0 <= model.multiple_color <= 9)


def render_scene(scene, model):
    if not valid_model(model):
        return None, {"status": "HOLD", "reason": "invalid_model"}
    height, width = len(scene.grid), len(scene.grid[0])
    ownership = {p: i for i, actor in enumerate(scene.actors) for p in actor.cells}
    arrivals, receiver_cells, endpoints = defaultdict(list), {}, []
    for i, actor in enumerate(scene.actors):
        dr, dc = actor.direction
        shifted = shifted_sparse_point_mask({actor.tip}, model.distance * dr,
                                             model.distance * dc, height, width)
        if shifted is None:
            return None, {"status": "HOLD", "reason": "endpoint_out_of_bounds",
                          "actor_index": i, "tip": actor.tip, "direction": actor.direction,
                          "distance": model.distance}
        point = next(iter(shifted))
        if model.scope == "component" and point in ownership:
            receiver = ("component", ownership[point])
            footprint = scene.actors[ownership[point]].cells
        else:
            receiver, footprint = ("cell", *point), (point,)
        arrivals[receiver].append(i)
        receiver_cells[receiver] = footprint
        endpoints.append({"actor_index": i, "endpoint": point, "receiver": receiver})
    output = [list(row) for row in scene.grid]
    painted, receivers = set(), []
    for receiver, actors in sorted(arrivals.items()):
        footprint = receiver_cells[receiver]
        if painted.intersection(footprint):
            return None, {"status": "HOLD", "reason": "receiver_ownership_overlap"}
        painted.update(footprint)
        color = model.single_color if len(actors) == 1 else model.multiple_color
        for r, c in footprint:
            output[r][c] = color
        receivers.append({"receiver": receiver, "source_actors": tuple(actors),
                          "arrival_count": len(actors), "cells": footprint, "color": color})
    if sum(len(v) for v in arrivals.values()) != len(scene.actors):
        return None, {"status": "HOLD", "reason": "pulse_ownership_incomplete"}
    if any(output[r][c] != v for r, row in enumerate(scene.grid)
           for c, v in enumerate(row) if (r, c) not in painted):
        return None, {"status": "HOLD", "reason": "unowned_output_change"}
    return output, {"status": "OK", "endpoints": endpoints, "receivers": receivers,
                    "pulse_count": len(scene.actors), "owned_output_count": len(painted),
                    "preserved_count": height * width - len(painted)}


def render_model(grid, model):
    scene, roles = parse_input(grid)
    if scene is None:
        return None, roles
    output, execution = render_scene(scene, model)
    return output, {"status": execution["status"], "roles": roles, "execution": execution}


def fit_teachers(teachers, budget=FIT_BUDGET):
    if (not isinstance(teachers, list) or len(teachers) < 2
            or any(not isinstance(p, dict) or not valid_grid(p.get("input"))
                   or not valid_grid(p.get("output")) for p in teachers)):
        return None, {"status": "HOLD", "reason": "invalid_or_insufficient_teachers", "complete": True}
    if len({tuple(map(tuple, p["input"])) for p in teachers}) != len(teachers):
        return None, {"status": "HOLD", "reason": "duplicate_teacher_inputs", "complete": True}
    required = MODEL_COUNT * len(teachers)
    if type(budget) is not int or budget < required:
        return None, {"status": "RESOURCE_INCOMPLETE", "reason": "enumeration_budget",
                      "complete": False, "required_calls": required, "budget": budget,
                      "completed_calls": 0, "declared_model_count": MODEL_COUNT, "alternatives": []}
    parsed = [parse_input(p["input"]) for p in teachers]
    alternatives, retained = [], []
    for model in all_models():
        returns = []
        for pair, (scene, roles) in zip(teachers, parsed):
            output, execution = (render_scene(scene, model) if scene is not None else (None, roles))
            returns.append({"output": output, "record": execution,
                            "exact": output is not None and output == pair["output"]})
        exact = all(r["exact"] for r in returns)
        alternatives.append({"model": asdict(model), "teacher_returns": returns, "all_exact": exact})
        if exact:
            retained.append(model)
    record = {"status": "OK" if retained else "HOLD", "complete": True,
              "reason": None if retained else "no_shared_model", "budget": budget,
              "declared_model_count": MODEL_COUNT, "completed_calls": required,
              "teacher_parse_records": [r for _, r in parsed], "alternatives": alternatives,
              "retained_models": [asdict(m) for m in retained]}
    return (Fitted(tuple(retained)) if retained else None), record


def predict(grid, fitted):
    if not isinstance(fitted, Fitted) or not fitted.models:
        return None, {"status": "HOLD", "reason": "no_fitted_models"}
    if len(fitted.models) > MODEL_COUNT:
        return None, {"status": "RESOURCE_INCOMPLETE", "reason": "model_budget"}
    returns = []
    for model in fitted.models:
        output, record = render_model(grid, model)
        returns.append({"model": asdict(model), "output": output, "record": record})
    if any(r["output"] is None for r in returns):
        return None, {"status": "HOLD", "reason": "retained_model_failed", "returns": returns}
    if any(r["record"]["roles"] != returns[0]["record"]["roles"] for r in returns):
        return None, {"status": "HOLD", "reason": "role_disagreement", "returns": returns}
    if any(r["output"] != returns[0]["output"] for r in returns):
        return None, {"status": "HOLD", "reason": "output_disagreement", "returns": returns}
    return returns[0]["output"], {"status": "OK", "model_count": len(returns), "returns": returns}
