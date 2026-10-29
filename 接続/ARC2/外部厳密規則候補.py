"""公開trainに完全整合するNVARC規則だけをHDSの既存候補枠へ渡す。"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .第三者.NVARC import merge_agreement as _source

_SOURCE_PATH = Path(_source.__file__).resolve()
_SOURCE_SHA256 = hashlib.sha256(_SOURCE_PATH.read_bytes()).hexdigest()
# The upstream near-exact panel rule accepts training mismatches. It is excluded
# from this experiment; only outputs returned by train-exact rules are eligible.
_source.near_exact_transform_prediction = lambda *args, **kwargs: None


def _格子か(value: object) -> bool:
    return (
        isinstance(value, list) and 1 <= len(value) <= 30
        and all(isinstance(row, list) and 1 <= len(row) <= 30
                and len(row) == len(value[0])
                and all(type(cell) is int and 0 <= cell <= 9 for cell in row)
                for row in value)
    )


class 汎用プログラム帰納候補群:
    """課題の公開trainに全一致する外部規則群を順位別に提示する。"""

    def __init__(self, 教師群: list[dict[str, Any]]):
        self._課題 = {
            "train": [
                {"input": [row[:] for row in pair["input"]],
                 "output": [row[:] for row in pair["output"]]}
                for pair in 教師群
            ]
        }
        self._cache: dict[tuple[tuple[int, ...], ...], list[tuple[list[list[int]], list[str]]]] = {}

    def _順位候補(self, 格子: Any, 順位: int):
        if not _格子か(格子):
            return None, {"generator": "symbolic_program_induction",
                          "program_source_sha256": _SOURCE_SHA256,
                          "rank": 順位 + 1, "train_fit": False,
                          "reason": "invalid_input_grid"}
        key = tuple(tuple(row) for row in 格子)
        ranked = self._cache.get(key)
        if ranked is None:
            predictions = _source.exact_predictions(
                self._課題, [row[:] for row in 格子]
            )
            groups: dict[tuple[tuple[int, ...], ...], dict[str, Any]] = {}
            for order, (name, prediction) in enumerate(predictions.items()):
                if name.startswith("near2:") or not _格子か(prediction):
                    continue
                signature = tuple(tuple(row) for row in prediction)
                group = groups.get(signature)
                if group is None:
                    groups[signature] = {"grid": prediction, "names": [name], "first": order}
                else:
                    group["names"].append(name)
            ordered = sorted(
                groups.items(),
                key=lambda item: (-len(item[1]["names"]), item[1]["first"], item[0]),
            )
            ranked = [(group["grid"], group["names"]) for _, group in ordered]
            self._cache[key] = ranked
        if 順位 >= len(ranked):
            return None, {"generator": "symbolic_program_induction",
                          "program_source_sha256": _SOURCE_SHA256,
                          "rank": 順位 + 1, "train_fit": False,
                          "reason": "no_exact_external_rule"}
        grid, names = ranked[順位]
        detail = {
            "generator": "symbolic_program_induction",
            "program_source_sha256": _SOURCE_SHA256,
            "rank": 順位 + 1, "train_fit": True,
            "program": "nvarc_exact_rule_consensus",
            "program_family": "nvarc_exact_rules",
            "program_cost": len(names), "training_score": None,
            "uncertainty": "not_measured",
            "action_origin": "public_train_exact_external_rule",
        }
        return [row[:] for row in grid], detail

    def 第一候補(self, 格子: Any, 既定値: dict[str, Any]):
        del 既定値
        return self._順位候補(格子, 0)

    def 第二候補(self, 格子: Any, 既定値: dict[str, Any]):
        del 既定値
        return self._順位候補(格子, 1)
