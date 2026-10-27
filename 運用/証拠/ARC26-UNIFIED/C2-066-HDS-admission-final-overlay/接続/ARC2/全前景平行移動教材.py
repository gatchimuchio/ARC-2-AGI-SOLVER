"""教師群が支持する単一オフセットの前景平行移動候補。"""

from collections import Counter

Grid = list[list[int]]


def _有効格子(格子: object) -> bool:
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


def _背景色(格子: Grid) -> int:
    頻度 = Counter(色 for 行 in 格子 for 色 in 行)
    return min(頻度, key=lambda 色: (-頻度[色], 色))


def _移動(格子: Grid, 行差: int, 列差: int) -> Grid | None:
    高さ, 幅 = len(格子), len(格子[0])
    背景 = _背景色(格子)
    出力 = [[背景] * 幅 for _ in range(高さ)]
    for 行, 行群 in enumerate(格子):
        for 列, 色 in enumerate(行群):
            if 色 == 背景:
                continue
            移動行, 移動列 = 行 + 行差, 列 + 列差
            if not (0 <= 移動行 < 高さ and 0 <= 移動列 < 幅):
                return None
            出力[移動行][移動列] = 色
    return 出力


def _入力鍵(格子: Grid) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(行) for 行 in 格子)


def _教師移動量(入力: Grid, 出力: Grid) -> tuple[int, int] | None | bool:
    if len(入力) != len(出力) or any(
        len(入力行) != len(出力行)
        for 入力行, 出力行 in zip(入力, 出力)
    ):
        return False
    背景 = _背景色(入力)
    入力前景 = [
        (行, 列)
        for 行, 行群 in enumerate(入力)
        for 列, 色 in enumerate(行群)
        if 色 != 背景
    ]
    if not 入力前景:
        return None
    出力前景 = [
        (行, 列)
        for 行, 行群 in enumerate(出力)
        for 列, 色 in enumerate(行群)
        if 色 != 背景
    ]
    if len(入力前景) != len(出力前景):
        return False
    行差 = min(行 for 行, _ in 出力前景) - min(行 for 行, _ in 入力前景)
    列差 = min(列 for _, 列 in 出力前景) - min(列 for _, 列 in 入力前景)
    return (行差, 列差) if _移動(入力, 行差, 列差) == 出力 else False


class 全前景平行移動教材:
    """全教師で同じ移動量を再現し、照会出力が一意な場合だけ返す。"""

    def __init__(self, 教師群):
        self.必要支持数 = 3
        self.移動量群: tuple[tuple[int, int], ...] = ()
        if not isinstance(教師群, (list, tuple)) or len(教師群) < self.必要支持数:
            return
        if any(
            not isinstance(対, dict)
            or not _有効格子(対.get("input"))
            or not _有効格子(対.get("output"))
            for 対 in 教師群
        ):
            return
        入力群 = [_入力鍵(対["input"]) for 対 in 教師群]
        if len(set(入力群)) != len(入力群):
            return

        共通移動量 = None
        for 対 in 教師群:
            入力, 正解 = 対["input"], 対["output"]
            移動量 = _教師移動量(入力, 正解)
            if 移動量 is False or 移動量 is None:
                return
            共通移動量 = (
                {移動量}
                if 共通移動量 is None
                else 共通移動量 & {移動量}
            )
            if not 共通移動量:
                return
        self.移動量群 = tuple(sorted(共通移動量 or ()))

    def 候補(self, 格子, _方針):
        if not self.移動量群:
            return None, {"failure": "no_common_translation_reproduces_all_training_pairs"}
        if not _有効格子(格子):
            return None, {"failure": "invalid_grid"}
        出力群 = {
            _入力鍵(出力)
            for 行差, 列差 in self.移動量群
            if (出力 := _移動(格子, 行差, 列差)) is not None
        }
        if len(出力群) != 1:
            return None, {
                "failure": "consistent_translation_offsets_disagree_or_leave_canvas",
                "retained_offset_count": len(self.移動量群),
            }
        出力 = next(iter(出力群))
        return [list(行) for 行 in 出力], {
            "offsets": [list(移動量) for 移動量 in self.移動量群],
        }

    def 記録(self):
        return {
            "minimum_support": self.必要支持数,
            "fitting_offsets": [list(移動量) for 移動量 in self.移動量群],
        }
