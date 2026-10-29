"""同倍率タイルを教師から学び、位置ごとのD4写像で入力格子を拡張する。"""

from .格子D4教材 import _変換群


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


class 周期タイルD4教材:
    def __init__(self, 教師群):
        self.全教師再現 = False
        self.タイル行数 = 0
        self.タイル列数 = 0
        self.配置 = ()
        if not isinstance(教師群, (list, tuple)) or len(教師群) < 2:
            return
        if any(
            not isinstance(対, dict)
            or not _有効格子(対.get("input"))
            or not _有効格子(対.get("output"))
            for 対 in 教師群
        ):
            return
        入力群 = [tuple(map(tuple, 対["input"])) for 対 in 教師群]
        if len(set(入力群)) < 2:
            return

        倍率群 = []
        for 対 in 教師群:
            高さ, 幅 = len(対["input"]), len(対["input"][0])
            出力高さ, 出力幅 = len(対["output"]), len(対["output"][0])
            if 出力高さ % 高さ or 出力幅 % 幅:
                return
            行倍率, 列倍率 = 出力高さ // 高さ, 出力幅 // 幅
            if 行倍率 * 列倍率 < 2:
                return
            倍率群.append((行倍率, 列倍率))
        if len(set(倍率群)) != 1:
            return
        self.タイル行数, self.タイル列数 = 倍率群[0]

        配置 = []
        for タイル行 in range(self.タイル行数):
            配置行 = []
            for タイル列 in range(self.タイル列数):
                共通変換 = None
                for 対 in 教師群:
                    高さ, 幅 = len(対["input"]), len(対["input"][0])
                    対象 = [
                        行[タイル列 * 幅:(タイル列 + 1) * 幅]
                        for 行 in 対["output"][タイル行 * 高さ:(タイル行 + 1) * 高さ]
                    ]
                    一致 = {
                        名
                        for 名, 変換済み in _変換群(対["input"]).items()
                        if 変換済み == 対象
                    }
                    共通変換 = 一致 if 共通変換 is None else 共通変換 & 一致
                    if not 共通変換:
                        return
                配置行.append(tuple(sorted(共通変換)))
            配置.append(tuple(配置行))
        self.配置 = tuple(配置)
        self.全教師再現 = True

    def 候補(self, 格子, _方針):
        if not self.全教師再現:
            return None, {"failure": "no periodic D4 tiling reproduces all training pairs"}
        if not _有効格子(格子):
            return None, {"failure": "invalid_grid"}
        高さ, 幅 = len(格子), len(格子[0])
        if 高さ * self.タイル行数 > 30 or 幅 * self.タイル列数 > 30:
            return None, {"failure": "tiled_output_exceeds_grid_limit"}
        変換群 = _変換群(格子)
        出力 = [[None] * (幅 * self.タイル列数) for _ in range(高さ * self.タイル行数)]
        for タイル行, 配置行 in enumerate(self.配置):
            for タイル列, 変換候補 in enumerate(配置行):
                一意格子 = {
                    tuple(tuple(行) for 行 in 変換群[名])
                    for 名 in 変換候補
                    if len(変換群[名]) == 高さ
                    and len(変換群[名][0]) == 幅
                }
                if len(一意格子) != 1:
                    return None, {"failure": "ambiguous_or_shape_incompatible_tile_transform"}
                タイル = [list(行) for 行 in next(iter(一意格子))]
                for 行番号, 行 in enumerate(タイル):
                    出力[タイル行 * 高さ + 行番号][
                        タイル列 * 幅:(タイル列 + 1) * 幅
                    ] = 行
        if not _有効格子(出力):
            return None, {"failure": "invalid_tiled_grid"}
        return 出力, {
            "tile_rows": self.タイル行数,
            "tile_columns": self.タイル列数,
            "operations_per_tile": [list(行) for 行 in self.配置],
        }

    def 記録(self):
        return {
            "all_training_pairs_reproduced": self.全教師再現,
            "tile_rows": self.タイル行数,
            "tile_columns": self.タイル列数,
            "operations_per_tile": [list(行) for 行 in self.配置],
        }


class 条件付き周期タイルD4教材:
    """入力の背景マスクに従い、非背景セルだけD4変換タイルへ展開する。"""

    def __init__(self, 教師群):
        self.全教師再現 = False
        self.背景色 = None
        self.タイル行数 = 0
        self.タイル列数 = 0
        self.教師数 = 0
        self.配置 = ()
        if not isinstance(教師群, (list, tuple)) or len(教師群) < 2:
            return
        if any(
            not isinstance(対, dict)
            or not _有効格子(対.get("input"))
            or not _有効格子(対.get("output"))
            for 対 in 教師群
        ):
            return

        形状群 = {(len(対["input"]), len(対["input"][0])) for 対 in 教師群}
        入力群 = {tuple(map(tuple, 対["input"])) for 対 in 教師群}
        if len(形状群) != 1 or len(入力群) < 2:
            return
        self.タイル行数, self.タイル列数 = next(iter(形状群))
        高さ, 幅 = self.タイル行数, self.タイル列数
        if any(
            len(対["output"]) != 高さ * 高さ
            or len(対["output"][0]) != 幅 * 幅
            for 対 in 教師群
        ):
            return

        前計算教師群 = []
        背景候補群 = set()
        for 対 in 教師群:
            入力 = 対["input"]
            出力 = 対["output"]
            変換群 = _変換群(入力)
            タイル群 = []
            for タイル行 in range(高さ):
                タイル行群 = []
                for タイル列 in range(幅):
                    タイル = [
                        行[タイル列 * 幅:(タイル列 + 1) * 幅]
                        for 行 in 出力[
                            タイル行 * 高さ:(タイル行 + 1) * 高さ
                        ]
                    ]
                    marker = 入力[タイル行][タイル列]
                    if all(色 == marker for 行 in タイル for 色 in 行):
                        背景候補群.add(marker)
                    タイル行群.append(タイル)
                タイル群.append(タイル行群)
            前計算教師群.append((入力, タイル群, 変換群))

        適合背景群 = []
        for 背景色 in sorted(背景候補群):
            配置 = [[None] * 幅 for _ in range(高さ)]
            空白タイル数 = 0
            非空白タイル数 = 0
            適合 = True
            for 入力, タイル群, 変換群 in 前計算教師群:
                for タイル行 in range(高さ):
                    for タイル列 in range(幅):
                        タイル = タイル群[タイル行][タイル列]
                        if 入力[タイル行][タイル列] == 背景色:
                            if any(
                                色 != 背景色 for 行 in タイル for 色 in 行
                            ):
                                適合 = False
                                break
                            空白タイル数 += 1
                            continue

                        一致変換 = {
                            名
                            for 名, 変換済み in 変換群.items()
                            if 変換済み == タイル
                        }
                        if not 一致変換:
                            適合 = False
                            break
                        非空白タイル数 += 1
                        既存 = 配置[タイル行][タイル列]
                        配置[タイル行][タイル列] = (
                            一致変換 if 既存 is None else 既存 & 一致変換
                        )
                        if not 配置[タイル行][タイル列]:
                            適合 = False
                            break
                    if not 適合:
                        break
                if not 適合:
                    break
            if 適合 and 空白タイル数 and 非空白タイル数:
                適合背景群.append((背景色, 配置))

        if len(適合背景群) != 1:
            return
        self.背景色, 配置 = 適合背景群[0]
        self.教師数 = len(教師群)
        self.配置 = tuple(tuple(行) for 行 in 配置)
        self.全教師再現 = True

    def 候補(self, 格子, _方針):
        if not self.全教師再現:
            return None, {"failure": "no masked periodic D4 tiling reproduces all training pairs"}
        if not _有効格子(格子):
            return None, {"failure": "invalid_grid"}
        高さ, 幅 = len(格子), len(格子[0])
        if (高さ, 幅) != (self.タイル行数, self.タイル列数):
            return None, {"failure": "test_grid_shape_mismatch"}
        if 高さ * 高さ > 30 or 幅 * 幅 > 30:
            return None, {"failure": "tiled_output_exceeds_grid_limit"}

        変換群 = _変換群(格子)
        出力 = [[None] * (幅 * 幅) for _ in range(高さ * 高さ)]
        for タイル行, 配置行 in enumerate(self.配置):
            for タイル列, 変換候補 in enumerate(配置行):
                if 格子[タイル行][タイル列] == self.背景色:
                    タイル = [[self.背景色] * 幅 for _ in range(高さ)]
                else:
                    if not 変換候補:
                        return None, {
                            "failure": "unobserved_nonbackground_tile_transform"
                        }
                    一意格子 = {
                        tuple(tuple(行) for 行 in 変換群[名])
                        for 名 in 変換候補
                        if len(変換群[名]) == 高さ
                        and len(変換群[名][0]) == 幅
                    }
                    if len(一意格子) != 1:
                        return None, {
                            "failure": "ambiguous_or_shape_incompatible_tile_transform"
                        }
                    タイル = [list(行) for 行 in next(iter(一意格子))]
                for 行番号, 行 in enumerate(タイル):
                    出力[タイル行 * 高さ + 行番号][
                        タイル列 * 幅:(タイル列 + 1) * 幅
                    ] = 行

        if not _有効格子(出力):
            return None, {"failure": "invalid_tiled_grid"}
        return 出力, {
            "background_color": self.背景色,
            "training_pair_count": self.教師数,
            "tile_rows": 高さ,
            "tile_columns": 幅,
            "operations_per_nonbackground_tile": [
                [sorted(変換候補 or ()) for 変換候補 in 行]
                for 行 in self.配置
            ],
        }

    def 記録(self):
        return {
            "all_training_pairs_reproduced": self.全教師再現,
            "background_color": self.背景色,
            "training_pair_count": self.教師数,
            "tile_rows": self.タイル行数,
            "tile_columns": self.タイル列数,
            "operations_per_nonbackground_tile": [
                [sorted(変換候補 or ()) for 変換候補 in 行]
                for 行 in self.配置
            ],
        }
