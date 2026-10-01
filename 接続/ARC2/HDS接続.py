"""既存テンプレート穴充填候補を既存HDSの学習・照会へ渡す。"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

from hds学習系統 import HDS学習実行系, 最小排気系
from hds学習系統.型 import 学習入力, 観測事実
from .既存穴充填 import _template_hole_pack_render


def 事前教材を読む():
    """固定したtraining教材の参照。現在課題の識別子は受け取らない。"""
    ルート = Path(__file__).resolve().parents[2]
    参照 = json.loads(Path(__file__).with_name("テンプレート充填教材.json").read_text())
    if 参照["分割"] != "training":
        raise ValueError("事前教材はtraining分割に限定する")
    教材, 既出 = [], set()
    for 出典 in 参照["教材"]:
        原本 = json.loads((ルート / "入力/公式ソース/ARC-AGI-2/data/training"
                         / f"{出典['課題ID']}.json").read_text())
        for 位置 in 出典["訓練例位置"]:
            鍵 = (出典["課題ID"], 位置)
            if 鍵 in 既出:
                raise ValueError("同一の教師観測を重複して支持へ加算しない")
            既出.add(鍵)
            教材.append(原本["train"][位置])
    return 教材


def 有効格子(格子):
    return (
        isinstance(格子, list) and 1 <= len(格子) <= 30
        and all(
            isinstance(行, list) and 1 <= len(行) <= 30
            and len(行) == len(格子[0])
            and all(type(色) is int and 0 <= 色 <= 9 for 色 in 行)
            for 行 in 格子
        )
    )


def 観測へ(内容, 境界):
    内容 = deepcopy(内容)
    return 学習入力(
        原入力=内容, 対象系境界=境界,
        観測群=tuple(観測事実((名,), 値, "列") for 名, 値 in 内容.items()),
    )


def 格子観測(対):
    内容 = {"入力": 対["input"]}
    if "output" in 対:
        内容["出力"] = 対["output"]
    return 観測へ(内容, "ARC格子変換")


def 出力格子(機械, 観測, *, 同値必須=False):
    実行結果 = 機械.照会(観測)
    排気 = 最小排気系().排出する(実行結果)
    値群 = [p.予測値 for p in 実行結果.予測群 if p.結果経路 == ("出力",)]
    同値あり = any(
        原理.対象系境界 == 観測.対象系境界
        and 原理.関係型 == "同値関係"
        and 原理.条件経路群 == (("候補",),)
        and 原理.結果経路 == ("出力",)
        for 原理 in 実行結果.有効原理群
    )
    確定 = (
        排気.状態 == "出力" and bool(値群)
        and all(v == 値群[0] for v in 値群)
        and 有効格子(値群[0]) and (not 同値必須 or 同値あり)
    )
    return {
        "answer": 値群[0] if 確定 else None,
        "status": 排気.状態, "reasons": 排気.内容["断定保留理由群"],
        "equality_admitted": 同値あり,
        "quarantined": len(実行結果.係争中原理群),
    }


def 課題を解く(課題, 事前教材):
    if set(課題) != {"train", "test"}:
        raise ValueError("runtime課題はtrain/testだけを受け取る")
    if any(set(対) != {"input"} for 対 in 課題["test"]):
        raise ValueError("runtimeのtest対へ正解や識別子を渡してはならない")
    機械 = HDS学習実行系()  # 既存の最小支持数3・最大条件数2を保持。
    for 対 in 課題["train"]:
        機械.実行(格子観測(対))
    結果群 = [出力格子(機械, 格子観測(対)) for 対 in 課題["test"]]
    if all(結果["answer"] is not None for 結果 in 結果群):
        return {"results": 結果群, "mechanism": "格子値基底"}

    境界 = "ARCテンプレート穴充填"
    事前数, 現在数, 全再現 = 0, 0, True
    for 群名, 教材群 in (("事前", 事前教材), ("現在", 課題["train"])):
        for 対 in 教材群:
            # expected引数は渡さない。候補は常に入力だけで生成する。
            候補, _ = _template_hole_pack_render(対["input"], {})
            if 候補 is None:
                return {"results": 結果群, "mechanism": "充填候補なし"}
            再現 = 候補 == 対["output"]
            全再現 = 全再現 and 再現
            # 反例も公開学習経路へ渡す。隔離や保留を自動解除しない。
            学習結果 = 機械.実行(観測へ({"候補": 候補, "出力": 対["output"]}, 境界))
            if 群名 == "事前":
                事前数 += 1
            else:
                現在数 += 1
    if not 全再現:
        return {
            "results": 結果群, "mechanism": "教師反例により不採用",
            "prior_observations": 事前数, "current_observations": 現在数,
            "quarantined": len(学習結果.係争中原理群),
        }

    for 位置, 対 in enumerate(課題["test"]):
        if 結果群[位置]["answer"] is not None:
            continue
        候補, 詳細 = _template_hole_pack_render(対["input"], {})
        if 候補 is None:
            結果群[位置] = {"answer": None, "status": "断定保留", "details": 詳細}
            continue
        # helperの候補を直接排出せず、採用済み同値原理の予測だけを排出する。
        結果群[位置] = 出力格子(
            機械, 観測へ({"候補": 候補}, 境界), 同値必須=True,
        )
    return {
        "results": 結果群, "mechanism": "HDS・既存テンプレート穴充填",
        "prior_observations": 事前数, "current_observations": 現在数,
    }


if __name__ == "__main__":
    print(json.dumps(課題を解く(json.load(sys.stdin), 事前教材を読む()), ensure_ascii=False))
