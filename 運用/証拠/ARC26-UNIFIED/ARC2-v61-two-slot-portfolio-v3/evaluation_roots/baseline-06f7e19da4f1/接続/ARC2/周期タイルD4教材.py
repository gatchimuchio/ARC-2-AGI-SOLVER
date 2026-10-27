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
