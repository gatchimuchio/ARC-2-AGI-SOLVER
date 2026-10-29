"""公開trainから完全整合するプログラム候補を作り、HDSへ渡す。"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from . import arc_proof_search


_SOURCE_PATH = Path(arc_proof_search.__file__).resolve()
_SOURCE_SHA256 = hashlib.sha256(_SOURCE_PATH.read_bytes()).hexdigest()


class 汎用プログラム帰納候補群:
    """一課題のtrainだけから候補を一度生成し、順位別にHDSへ提示する。"""

    def __init__(self, 教師群: list[dict[str, Any]]):
        教師のみ = [
            {"input": 対["input"], "output": 対["output"]}
            for 対 in 教師群
        ]
        課題 = {"train": 教師のみ, "test": []}
        self._候補群 = [
            候補 for 候補 in arc_proof_search.synthesize(課題)
            if 候補.exact
        ]

    def 第一候補(self, 格子: Any, 既定値: dict[str, Any]):
        return self._順位候補(格子, 既定値, 0)

    def 第二候補(self, 格子: Any, 既定値: dict[str, Any]):
        return self._順位候補(格子, 既定値, 1)

    def _順位候補(self, 格子: Any, 既定値: dict[str, Any], 順位: int):
        del 既定値  # HDSの共通候補器インターフェース。候補生成には使用しない。
        共通 = {
            "generator": "symbolic_program_induction",
            "program_source_sha256": _SOURCE_SHA256,
            "rank": 順位 + 1,
        }
        if 順位 >= len(self._候補群):
            return None, {**共通, "train_fit": False, "reason": "no_ranked_exact_program"}

        候補 = self._候補群[順位]
        予測 = arc_proof_search.safe(
            候補.function,
            arc_proof_search.as_grid(格子),
        )
        根拠 = {
            **共通,
            "train_fit": True,
            "program": 候補.name,
            "program_family": 候補.name.split("|colors=", 1)[0],
            "program_cost": 候補.cost,
            "training_score": 候補.training_score,
            "uncertainty": "not_measured",
            "action_origin": "public_train_exact_program",
        }
        if 予測 is None:
            return None, {**根拠, "reason": "unsafe_prediction"}
        return 予測.astype(int).tolist(), 根拠
