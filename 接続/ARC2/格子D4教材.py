"""全教師で確定した格子の回転・反射だけを候補として返す。"""


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


class 格子D4教材:
    def __init__(self, 教師群):
        self.必要支持数 = 3
        self.変換候補 = ()
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
        self.変換候補 = tuple(
            名
            for 名 in 候補名
            if all(_変換群(対["input"])[名] == 対["output"] for 対 in 教師群)
        )

    def 候補(self, 格子, _方針):
        if not self.変換候補:
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
        }
