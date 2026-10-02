"""既存テンプレート穴充填候補を既存HDSの学習・照会へ渡す。"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

from hds学習系統 import HDS学習実行系, 最小排気系
from hds学習系統.型 import 学習入力, 観測事実
from .既存穴充填 import _template_hole_pack_render
from .既存入れ子合成 import _nested_panel_relation_render
from .既存領域転写 import _dual_region_hole_palette_render
from .物体端投射 import 端投射教材
from .凡例穴対応 import 凡例穴教材
from .色群充填 import 色群充填教材
from .物体群整列 import 物体群教材
from .格子自己マスク import 格子自己マスク教材
from .既存辺対応抽出 import 辺対応候補
from .成分経路教材 import 成分経路教材
from .対角線橋教材 import 対角線橋教材
from .対角領域教材 import 対角領域教材
from .軸反射教材 import 軸反射教材
from .周期組修復教材 import 周期組修復教材
from .部分見本教材 import 部分見本教材
from .穴形拡大教材 import 穴形拡大教材
from .標識移動教材 import 標識移動教材
from .放射組立教材 import 放射組立教材
from .穴輪郭教材 import 穴輪郭教材
from .形状色教材 import 形状色教材
from .凡例経路教材 import 凡例経路教材
from .行周期教材 import 行周期教材
from .重畳組立教材 import 重畳組立教材
from .空白移動教材 import 空白移動教材
from .順位着色教材 import 順位着色教材
from .距離層教材 import 距離層教材
from .対称剪定教材 import 対称剪定教材
from .反復行教材 import 反復行教材
from .種境界教材 import 種境界教材
from .流路教材 import 流路教材
from .成分直列教材 import 成分直列教材
from .十字教材 import 十字教材
from .枠計数教材 import 枠計数教材
from .標識計数教材 import 標識計数教材


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


def 同値原理あり(原理群, 境界):
    return any(
        原理.対象系境界 == 境界
        and 原理.関係型 == "同値関係"
        and 原理.条件経路群 == (("候補",),)
        and 原理.結果経路 == ("出力",)
        for 原理 in 原理群
    )


def 出力格子(機械, 観測, *, 同値必須=False):
    実行結果 = 機械.照会(観測)
    排気 = 最小排気系().排出する(実行結果)
    値群 = [p.予測値 for p in 実行結果.予測群 if p.結果経路 == ("出力",)]
    同値あり = 同値原理あり(実行結果.有効原理群, 観測.対象系境界)
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


def 候補機構を学習(機械, 課題, 事前教材, 境界, 候補器):
    記録 = {"境界": 境界, "事前観測数": 0, "現在観測数": 0,
            "採用可": False, "同値採用": False}
    全再現 = True
    for 群名, 教材群 in (("事前観測数", 事前教材), ("現在観測数", 課題["train"])):
        for 対 in 教材群:
            # 常に入力だけで候補を生成。expected引数は渡さない。
            候補, 詳細 = 候補器(対["input"], {})
            if 候補 is None:
                return {**記録, "状態": "充足する候補なし", "詳細": 詳細}
            全再現 = 全再現 and 候補 == 対["output"]
            # 反例も公開学習経路へ渡す。隔離・保留を解除しない。
            学習結果 = 機械.実行(観測へ({"候補": 候補, "出力": 対["output"]}, 境界))
            記録[群名] += 1
            記録["同値採用"] = 同値原理あり(学習結果.有効原理群, 境界)
    return {**記録, "採用可": 全再現,
            "状態": "全教師再現" if 全再現 else "教師反例により不採用",
            "隔離数": len(学習結果.係争中原理群) if 課題["train"] or 事前教材 else 0}


def 課題を解く(課題, 事前教材):
    if set(課題) != {"train", "test"}:
        raise ValueError("runtime課題はtrain/testだけを受け取る")
    if any(set(対) != {"input"} for 対 in 課題["test"]):
        raise ValueError("runtimeのtest対へ正解や識別子を渡してはならない")
    二例 = (len(課題["train"]) == 2
            and 課題["train"][0]["input"] != 課題["train"][1]["input"])
    必要支持数 = 2 if 二例 else 3
    # 課題全体に作用する明示設定。HDS中核の既定値3は変更しない。
    機械 = HDS学習実行系(最小支持数=必要支持数)
    for 対 in 課題["train"]:
        機械.実行(格子観測(対))
    基底 = [出力格子(機械, 格子観測(対)) for 対 in 課題["test"]]
    if all(結果["answer"] is not None for 結果 in 基底):
        return {"results": 基底, "mechanism": "格子値基底", "minimum_support": 必要支持数}

    端教材 = 端投射教材(課題["train"])
    端教材.学習する(機械, 観測へ)
    凡例教材 = 凡例穴教材(課題["train"], 必要支持数)
    色群教材 = 色群充填教材(課題["train"])
    整列教材 = 物体群教材(課題["train"])
    整列教材.学習する(機械, 観測へ)
    格子教材 = 格子自己マスク教材(課題["train"])
    経路教材 = 成分経路教材(課題["train"])
    橋教材 = 対角線橋教材(課題["train"])
    対角教材 = 対角領域教材(課題["train"])
    反射教材 = 軸反射教材(課題["train"])
    周期教材 = 周期組修復教材(課題["train"])
    見本教材 = 部分見本教材(課題["train"])
    拡大教材 = 穴形拡大教材(課題["train"])
    移動教材 = 標識移動教材(課題["train"])
    放射教材 = 放射組立教材(課題["train"])
    輪郭教材 = 穴輪郭教材(課題["train"])
    形状教材 = 形状色教材(課題["train"])
    凡例経路 = 凡例経路教材(課題["train"])
    行周期 = 行周期教材(課題["train"])
    重畳教材 = 重畳組立教材(課題["train"])
    空白教材 = 空白移動教材(課題["train"])
    順位教材 = 順位着色教材(課題["train"])
    距離教材 = 距離層教材(課題["train"])
    剪定教材 = 対称剪定教材(課題["train"])
    反復教材 = 反復行教材(課題["train"])
    種境界 = 種境界教材(課題["train"])
    流路 = 流路教材(課題["train"])
    直列 = 成分直列教材(課題["train"])
    十字 = 十字教材(課題["train"])
    枠計数 = 枠計数教材(課題["train"])
    標識計数 = 標識計数教材(課題["train"])
    機構群 = (
        ("ARCテンプレート穴充填", _template_hole_pack_render, 事前教材),
        ("ARC入れ子パネル合成", _nested_panel_relation_render, ()),
        ("ARC閉領域パレット転写", _dual_region_hole_palette_render, ()),
        ("ARC物体端投射", 端教材.候補, ()),
        ("ARC凡例穴数対応", 凡例教材.候補, ()),
        ("ARC色群テンプレート充填", 色群教材.候補, ()),
        ("ARC物体群整列", 整列教材.候補, ()),
        ("ARC格子自己マスク", 格子教材.候補, ()),
        ("ARC辺対応抽出", 辺対応候補, ()),
        ("ARC成分最短経路", 経路教材.候補, ()),
        ("ARC対角線橋", 橋教材.候補, ()),
        ("ARC対角領域", 対角教材.候補, ()),
        ("ARC軸反射", 反射教材.候補, ()),
        ("ARC周期組修復", 周期教材.候補, ()),
        ("ARC部分見本転写", 見本教材.候補, ()),
        ("ARC穴形拡大", 拡大教材.候補, ()),
        ("ARC標識移動", 移動教材.候補, ()),
        ("ARC放射組立", 放射教材.候補, ()),
        ("ARC穴輪郭", 輪郭教材.候補, ()),
        ("ARC形状色転写", 形状教材.候補, ()),
        ("ARC凡例経路接続", 凡例経路.候補, ()),
        ("ARC行周期合成", 行周期.候補, ()),
        ("ARC重畳組立", 重畳教材.候補, ()),
        ("ARC空白矩形移動", 空白教材.候補, ()),
        ("ARCheader順位着色", 順位教材.候補, ()),
        ("ARC距離層周期充填", 距離教材.候補, ()),
        ("ARC最大保持対称剪定", 剪定教材.候補, ()),
        ("ARC反復行singleton抽出", 反復教材.候補, ()),
        ("ARCseed境界着色", 種境界.候補, ()),
        ("ARC下向き流路", 流路.候補, ()),
        ("ARC成分path直列化", 直列.候補, ()),
        ("ARC十字形態着色", 十字.候補, ()),
        ("ARC枠内成分計数", 枠計数.候補, ()),
        ("ARC標識panel計数", 標識計数.候補, ()),
    )
    記録群 = [候補機構を学習(機械, 課題, 教材, 境界, 候補器)
              for 境界, 候補器, 教材 in 機構群]
    結果群 = []
    隔離数 = 0
    for 対 in 課題["test"]:
        # 全機構の学習後に照会するため、後発の隔離も既存排気gateへ反映される。
        基底結果 = 出力格子(機械, 格子観測(対))
        隔離数 = max(隔離数, 基底結果["quarantined"])
        予測群 = [] if 基底結果["answer"] is None else [基底結果]
        未解決理由 = []
        for (境界, 候補器, _), 記録 in zip(機構群, 記録群):
            if not 記録["採用可"] or not 記録["同値採用"]:
                continue
            候補, _ = 候補器(対["input"], {})
            if 候補 is None:
                未解決理由.append(f"採用済み機構{境界}のtest候補が未確定")
                continue
            予測 = 出力格子(機械, 観測へ({"候補": 候補}, 境界), 同値必須=True)
            if 予測["answer"] is not None:
                予測群.append({**予測, "family": 境界})
            else:
                未解決理由.append(f"採用済み機構{境界}のHDS排気が保留")
        if 未解決理由:
            結果群.append({"answer": None, "status": "断定保留", "reasons": 未解決理由})
        elif not 予測群:
            結果群.append(基底結果)
        elif all(p["answer"] == 予測群[0]["answer"] for p in 予測群):
            結果群.append({**予測群[0], "agreeing_predictions": len(予測群)})
        else:
            結果群.append({"answer": None, "status": "断定保留",
                           "reasons": ["採用済み機構の完全格子予測が競合したため保留"]})
    return {"results": 結果群, "mechanism": "HDS機構候補の照会",
            "minimum_support": 必要支持数, "families": 記録群,
            "quarantined": 隔離数, "object_learning": 端教材.記録(), "legend_learning": 凡例教材.記録(), "grouped_packing": 色群教材.記録(), "group_order": 整列教材.記録(), "lattice_self_mask": 格子教材.記録(), "component_path": 経路教材.記録(), "diagonal_bridge": 橋教材.記録(), "diagonal_region": 対角教材.記録(), "axis_reflection": 反射教材.記録(), "tuple_repair": 周期教材.記録(), "panel_exemplar": 見本教材.記録(), "hole_scale": 拡大教材.記録(), "guided_compaction": 移動教材.記録(), "radial_assembly": 放射教材.記録(), "hole_outline": 輪郭教材.記録(), "template_shape_color": 形状教材.記録(), "legend_gap": 凡例経路.記録(), "separator_run": 行周期.記録(), "overlap_mosaic": 重畳教材.記録(), "farthest_blank": 空白教材.記録(), "header_rank": 順位教材.記録(), "separator_layer": 距離教材.記録(), "vertical_pruning": 剪定教材.記録(), "periodic_panel": 反復教材.記録(), "seeded_boundary": 種境界.記録(), "corridor": 流路.記録(), "panel_path": 直列.記録(), "plus_motif": 十字.記録(), "frame_count": 枠計数.記録(), "marker_count": 標識計数.記録()}


if __name__ == "__main__":
    print(json.dumps(課題を解く(json.load(sys.stdin), 事前教材を読む()), ensure_ascii=False))
