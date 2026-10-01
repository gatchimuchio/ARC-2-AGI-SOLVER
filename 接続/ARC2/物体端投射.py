"""教師から特徴→端方向を学び、既存の物体移動をHDS照会で制御する。"""
from collections import Counter
from hds学習系統 import 最小排気系
from .既存物体特徴 import (
    dominant_background_for_grid, edge_pack_components,
    edge_pack_component_feature, edge_pack_side_for_train_component,
)

方向境界 = "ARC物体端投射方向"


def 配置する(格子, 物体群, 方向群):
    背景 = dominant_background_for_grid(格子)
    高さ, 幅 = len(格子), len(格子[0])
    出力 = [[背景]*幅 for _ in range(高さ)]
    占有 = set()
    for 物体, 向き in zip(物体群, 方向群):
        if 向き not in ("top", "bottom"):
            return None
        r0, _, r1, _ = 物体["bbox"]
        先頭 = 0 if 向き == "top" else 高さ-(r1-r0+1)
        for 行, 列 in 物体["cells"]:
            行 = 先頭+行-r0
            if not (0 <= 行 < 高さ and 0 <= 列 < 幅) or (行,列) in 占有:
                return None
            占有.add((行,列))
            出力[行][列] = 物体["color"]
    if Counter(v for row in 出力 for v in row) != Counter(v for row in 格子 for v in row):
        return None
    return 出力


class 端投射教材:
    def __init__(self, 教師群):
        self.観測群 = []
        self.特徴番号群 = []
        self.状態 = "教師の完全な端対応なし"
        for 対 in 教師群:
            入力, 正解 = 対["input"], 対["output"]
            if (len(入力),len(入力[0])) != (len(正解),len(正解[0])):
                return
            物体群 = edge_pack_components(入力, dominant_background_for_grid(入力))
            if not 物体群:
                return
            方向群 = [edge_pack_side_for_train_component(o,正解,len(入力)) for o in 物体群]
            if 配置する(入力,物体群,方向群) != 正解:
                return
            self.観測群.extend((edge_pack_component_feature(o),side) for o,side in zip(物体群,方向群))
        # 固定された既存九特徴だけ。教師の整合性で選び、testは見ない。
        for i in range(9):
            対応 = {}
            for 特徴, 向き in self.観測群:
                if 特徴[i] in 対応 and 対応[特徴[i]] != 向き:
                    break
                対応[特徴[i]] = 向き
            else:
                if len(対応) >= 2:
                    self.特徴番号群.append(i)
        self.状態 = "教師整合特徴あり" if self.特徴番号群 else "整合する既存特徴なし"

    def 特徴観測(self, 特徴):
        return {f"特徴{i}":特徴[i] for i in self.特徴番号群}

    def 学習する(self, 機械, 観測へ):
        self.機械, self.観測へ = 機械, 観測へ
        if not self.特徴番号群:
            return
        for 特徴, 向き in self.観測群:
            機械.実行(観測へ({**self.特徴観測(特徴),"向き":向き},方向境界))

    def 候補(self, 格子, _policy):
        if not self.特徴番号群:
            return None, {"failure":self.状態}
        物体群 = edge_pack_components(格子,dominant_background_for_grid(格子))
        if not 物体群:
            return None, {"failure":"物体なし"}
        方向群 = []
        for 物体 in 物体群:
            特徴 = edge_pack_component_feature(物体)
            r = self.機械.照会(self.観測へ(self.特徴観測(特徴),方向境界))
            p = [p.予測値 for p in r.予測群 if p.結果経路 == ("向き",)]
            if 最小排気系().排出する(r).状態 != "出力" or not p or any(x != p[0] for x in p):
                return None, {"failure":"物体方向がHDSで未確定"}
            方向群.append(p[0])
        出力 = 配置する(格子,物体群,方向群)
        return 出力, {"failure":None if 出力 is not None else "配置競合または保存違反"}

    def 記録(self):
        return {"状態":self.状態,"特徴番号群":self.特徴番号群,
                "物理物体観測数":len(self.観測群) if self.特徴番号群 else 0}
