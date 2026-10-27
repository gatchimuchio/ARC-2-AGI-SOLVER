"""Sensitivity probe using the existing public-training LOO runner at support threshold four.

The production HDS source and the original support-three runner are unchanged.
Task eligibility stays at the original threshold; only the partial-condition
prediction support minimum is raised for this matched comparison.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE_RUNNER = (
    ROOT
    / "運用/証拠/ARC26-UNIFIED/"
    / "P5_HDS_partial_condition_consensus_visible_guard_LOO.py"
)
PARTIAL_SUPPORT_MINIMUM = 4

spec = importlib.util.spec_from_file_location(
    "arc2_visible_guard_loo_base", BASE_RUNNER
)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load the preserved support-three runner")
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)

original_partial_consensus = runner.部分条件合意


def partial_consensus_with_support_four(principle, mapping):
    eligibility_threshold = runner.SUPPORT_MINIMUM
    runner.SUPPORT_MINIMUM = PARTIAL_SUPPORT_MINIMUM
    try:
        return original_partial_consensus(principle, mapping)
    finally:
        runner.SUPPORT_MINIMUM = eligibility_threshold


runner.部分条件合意 = partial_consensus_with_support_four

if __name__ == "__main__":
    runner.main()
