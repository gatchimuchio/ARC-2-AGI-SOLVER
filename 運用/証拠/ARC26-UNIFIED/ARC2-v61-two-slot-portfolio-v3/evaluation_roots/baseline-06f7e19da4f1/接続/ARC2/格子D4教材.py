"""全教師で確定した格子のD4変換と部分的な一対一色写像を返す。"""


def _有効格子(格子):
    return (
        isinstance(格子, list)
        and 1 <= len(格子) <= 30
        and all(
            isinstance(行, list)
            and 1 <= len(行) <= 30
            and len(行) == len(格子[0])
            and all(type(色) is int and 0 <= 色 <= 9 for 色 in 行)
            for 行 in 格子
        )
    )


def _変換群(格子):
    回転 = [行[:] for 行 in 格子]
    結果 = {}
    for 角度 in (0, 90, 180, 270):
        結果[f"rotate_{角度}"] = 回転
        回転 = [list(行) for 行 in zip(*回転[::-1])]

    反転 = [行[::-1] for 行 in 格子]
    for 角度 in (0, 90, 180, 270):
        結果[f"reflect_rotate_{角度}"] = 反転
        反転 = [list(行) for 行 in zip(*反転[::-1])]
    return 結果


def _色写像を学ぶ(入力, 出力, 前向き, 逆向き):
    if len(入力) != len(出力) or any(
        len(入力行) != len(出力行) for 入力行, 出力行 in zip(入力, 出力)
    ):
        return False
    for 入力行, 出力行 in zip(入力, 出力):
        for 入力色, 出力色 in zip(入力行, 出力行):
            if 入力色 in 前向き and 前向き[入力色] != 出力色:
                return False
            if 出力色 in 逆向き and 逆向き[出力色] != 入力色:
                return False
            前向き[入力色] = 出力色
            逆向き[出力色] = 入力色
    return True


class 格子D4教材:
    def __init__(self, 教師群):
        self.必要支持数 = 3
        self.変換候補 = ()
        self.色写像候補 = ()
        if not isinstance(教師群, (list, tuple)) or len(教師群) < self.必要支持数:
            return
        if any(
            not isinstance(対, dict)
            or not _有効格子(対.get("input"))
            or not _有効格子(対.get("output"))
            for 対 in 教師群
        ):
            return
        入力群 = [tuple(map(tuple, 対["input"])) for 対 in 教師群]
        if len(set(入力群)) != len(入力群):
            return

        候補名 = tuple(_変換群(教師群[0]["input"]))
        完全一致 = []
        色写像一致 = []
        for 名 in 候補名:
            前向き = {}
            逆向き = {}
            色写像可能 = True
            完全一致可能 = True
            for 対 in 教師群:
                変換済み = _変換群(対["input"])[名]
                完全一致可能 = 完全一致可能 and 変換済み == 対["output"]
                if not _色写像を学ぶ(
                    変換済み, 対["output"], 前向き, 逆向き
                ):
                    色写像可能 = False
                    break
            if 完全一致可能:
                完全一致.append(名)
            if 色写像可能 and any(入力色 != 出力色 for 入力色, 出力色 in 前向き.items()):
                色写像一致.append((名, tuple(sorted(前向き.items()))))
        self.変換候補 = tuple(完全一致)
        self.色写像候補 = tuple(色写像一致)

    def 候補(self, 格子, _方針):
        if not self.変換候補 and not self.色写像候補:
            return None, {"failure": "no D4 transform reproduces all training pairs"}
        if not _有効格子(格子):
            return None, {"failure": "invalid_grid"}

        変換群 = _変換群(格子)
        予測群 = []
        適用群 = []
        for 名 in self.変換候補:
            予測 = 変換群[名]
            if 予測 not in 予測群:
                予測群.append(予測)
            適用群.append(名)
        for 名, 色対群 in self.色写像候補:
            変換済み = 変換群[名]
            色写像 = dict(色対群)
            色集合 = {色 for 行 in 変換済み for 色 in 行}
            if not 色集合.issubset(色写像):
                continue
            予測 = [[色写像[色] for 色 in 行] for 行 in 変換済み]
            if 予測 not in 予測群:
                予測群.append(予測)
            適用群.append(f"{名}+bijective_palette")
        if not 予測群:
            return None, {"failure": "query contains colors not covered by a fitted palette"}
        if len(予測群) != 1:
            return None, {
                "failure": "consistent D4 transforms disagree on the input",
                "operations": 適用群,
            }
        return 予測群[0], {"operations": 適用群}

    def 記録(self):
        return {
            "minimum_support": self.必要支持数,
            "fitting_operations": list(self.変換候補),
            "fitting_palette_operations": [
                {"operation": 名, "mapping": dict(色対群)}
                for 名, 色対群 in self.色写像候補
                if dict(色対群) != {色: 色 for 色, _ in 色対群}
            ],
        }
