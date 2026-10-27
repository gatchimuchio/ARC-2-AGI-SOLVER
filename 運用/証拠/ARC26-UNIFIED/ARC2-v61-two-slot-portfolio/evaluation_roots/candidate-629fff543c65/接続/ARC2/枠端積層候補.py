"""cue有向辺を右向きにする固定C4 prior。元24モデルの選別ではない。"""
from dataclasses import asdict, dataclass
from itertools import product
from . import 枠端積層幾何 as base


@dataclass(frozen=True)
class Program:
    fast_color: int
    connectivity: int
    fast_sign: int
    slow_sign: int
    center: str

    def record(self):
        return asdict(self)


def all_programs():
    return [Program(*params) for params in product(range(10), (4, 8), (1, -1), (1, -1), base.CENTERS)]


def cue_rotation(role, cue_color):
    """Unique proper rotation sending the corner-to-edge vector to (row=0, col=1)."""
    row, col = role["corner"]
    if cue_color == role["horizontal_color"]:
        vector = (0, 1 if col == 0 else -1)
    elif cue_color == role["vertical_color"]:
        vector = (1 if row == 0 else -1, 0)
    else:
        return None, None
    rotations = {(0, 1): "identity", (1, 0): "rot270", (0, -1): "rot180", (-1, 0): "rot90"}
    return vector, rotations[vector]


class Evaluator:
    def __init__(self, view):
        self.view = view

    def evaluate(self, program):
        if self.view["failure"]:
            return {"output": None, "failure": self.view["failure"], "roles": []}
        records = []
        for role in self.view["roles"]:
            vector, transform = cue_rotation(role, program.fast_color)
            # The established renderer is a pure component-placement primitive here.
            # Both transform slots receive one input-derived geometric rotation.
            # No learned D4 table or original retained-model membership is consulted.
            adapter = base.Program(program.fast_color, program.connectivity, program.fast_sign,
                                   program.slow_sign, transform or "identity", transform or "identity", program.center)
            result = base.render_role(role, adapter)
            result["directed_cue_vector"] = vector
            result["input_derived_C4_rotation"] = transform
            records.append(result)
        output, failure = base.collapse(records)
        return {"output": output, "failure": failure, "roles": records}


def fit(teachers, record_return=None):
    views = [base.prepare_input(pair["input"]) for pair in teachers]
    evaluators = [Evaluator(view) for view in views]
    retained = []
    for number, program in enumerate(all_programs()):
        results = [evaluator.evaluate(program) for evaluator in evaluators]
        exacts = [result["failure"] is None and result["output"] == pair["output"]
                  for result, pair in zip(results, teachers)]
        if record_return is not None:
            record_return(number, program, results, exacts)
        if teachers and all(exacts):
            retained.append(program)
    return retained, views


def apply_retained(programs, grid):
    view = base.prepare_input(grid)
    evaluator = Evaluator(view)
    returns = [{"program": program.record(), "result": evaluator.evaluate(program)} for program in programs]
    failures = [i for i, row in enumerate(returns) if row["result"]["failure"]]
    success = [row["result"]["output"] for row in returns if row["result"]["failure"] is None]
    unique = {base.grid_key(output) for output in success}
    if not programs:
        status, code = "HOLD", "no_teacher_consistent_program"
    elif failures:
        status, code = "HOLD", "retained_program_failure"
    elif len(unique) != 1:
        status, code = "HOLD", "retained_program_disagreement"
    else:
        status, code = "OUTPUT", None
    return {"status": status, "code": code, "output": success[0] if status == "OUTPUT" else None,
            "failure_program_indices": failures, "distinct_success_outputs": len(unique),
            "input_view": view, "returns": returns}
