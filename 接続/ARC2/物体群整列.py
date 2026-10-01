"""既存物体特徴から群の列/行と順序を教師で選び、同一HDSへ接続する。"""
from collections import Counter
from hds学習系統 import 最小排気系
from .既存物体特徴 import (
    dominant_background_for_grid, edge_pack_components, edge_pack_component_feature,
)


def 格子鍵(格子):
    return tuple(map(tuple, 格子))


def 物体を読む(格子):
    背景 = dominant_background_for_grid(格子)
    物体群 = edge_pack_components(格子, 背景)
    形群 = {(o['bbox'][2]-o['bbox'][0]+1, o['bbox'][3]-o['bbox'][1]+1) for o in 物体群}
    if len(形群) != 1:
        return None
    高さ, 幅 = next(iter(形群))
    for o in 物体群:
        行, 列, _, _ = o['bbox']
        o['格子片'] = [[背景]*幅 for _ in range(高さ)]
        for r, c in o['cells']:
            o['格子片'][r-行][c-列] = o['color']
        o['特徴'] = edge_pack_component_feature(o)
    # 同一外観の教師対応を任意に選ばない。testでも同じ適用域を保つ。
    if len({格子鍵(o['格子片']) for o in 物体群}) != len(物体群):
        return None
    return 背景, 高さ, 幅, 物体群


def 教師を照合(対):
    読取 = 物体を読む(対['input'])
    if 読取 is None:
        return None
    背景, 高さ, 幅, 物体群 = 読取
    正解 = 対['output']
    if len(正解) % 高さ or len(正解[0]) % 幅:
        return None
    枠群 = []
    for 行 in range(0, len(正解), 高さ):
        for 列 in range(0, len(正解[0]), 幅):
            片 = [r[列:列+幅] for r in 正解[行:行+高さ]]
            if any(v != 背景 for r in 片 for v in r):
                枠群.append((行//高さ, 列//幅, 格子鍵(片)))
    if Counter(格子鍵(o['格子片']) for o in 物体群) != Counter(k for _, _, k in 枠群):
        return None
    対応 = {k: (r, c) for r, c, k in 枠群}
    return 読取, [対応[格子鍵(o['格子片'])] for o in 物体群]


def 配置する(読取, 区分群, 群軸, 順序軸, 逆順, 必要区分):
    背景, 高さ, 幅, 物体群 = 読取
    if len(区分群) != len(物体群) or any(type(v) is not int for v in 区分群):
        return None
    群 = {}
    for o, 区分 in zip(物体群, 区分群):
        群.setdefault(区分, []).append(o)
    if set(群) != set(必要区分) or set(群) != set(range(len(群))) or len(群) < 2:
        return None
    最大数 = max(map(len, 群.values()))
    出力高, 出力幅 = ((最大数*高さ, len(群)*幅) if 群軸 == 1
                    else (len(群)*高さ, 最大数*幅))
    if not (1 <= 出力高 <= 30 and 1 <= 出力幅 <= 30):
        return None
    出力 = [[背景]*出力幅 for _ in range(出力高)]
    占有 = set()
    for 区分, 物体列 in 群.items():
        順序値 = [o['bbox'][順序軸] for o in 物体列]
        if len(set(順序値)) != len(順序値):
            return None
        for 位置, o in enumerate(sorted(物体列, key=lambda o: o['bbox'][順序軸], reverse=逆順)):
            行, 列 = ((位置*高さ, 区分*幅) if 群軸 == 1 else (区分*高さ, 位置*幅))
            for r, 片行 in enumerate(o['格子片']):
                for c, 値 in enumerate(片行):
                    座標 = (行+r, 列+c)
                    if 座標 in 占有:
                        return None
                    占有.add(座標)
                    出力[行+r][列+c] = 値
    if Counter(v for r in 出力 for v in r if v != 背景) != Counter(
            v for o in 物体群 for r in o['格子片'] for v in r if v != 背景):
        return None
    return 出力


class 物体群教材:
    def __init__(self, 教師群):
        self.モデル群 = []
        self.教師対応群 = []
        self.境界観測数 = {}
        if not 教師群 or len({格子鍵(p['input']) for p in 教師群}) != len(教師群):
            return
        対応群 = [教師を照合(p) for p in 教師群]
        if any(x is None for x in 対応群):
            return
        # 宣言済み72通りだけ: 2群軸 × 既存9特徴 × 2順序軸 × 2方向。
        for 群軸 in (0, 1):
            for 特徴番号 in range(9):
                写像 = {}
                整合 = True
                for (読取, 枠群) in 対応群:
                    for o, 枠 in zip(読取[3], 枠群):
                        値, 区分 = o['特徴'][特徴番号], 枠[群軸]
                        if 値 in 写像 and 写像[値] != 区分:
                            整合 = False
                        写像[値] = 区分
                必要区分 = set(写像.values())
                if not 整合 or len(必要区分) < 2:
                    continue
                for 順序軸 in (0, 1):
                    for 逆順 in (False, True):
                        if all(配置する(読取, [写像[o['特徴'][特徴番号]] for o in 読取[3]],
                                         群軸, 順序軸, 逆順, 必要区分) == p['output']
                               for p, (読取, _) in zip(教師群, 対応群)):
                            self.モデル群.append((群軸, 特徴番号, 順序軸, 逆順, 写像))
        if self.モデル群:
            self.教師対応群 = 対応群

    def 学習する(self, 機械, 観測へ):
        self.機械, self.観測へ = 機械, 観測へ
        for 群軸 in sorted({m[0] for m in self.モデル群}):
            境界 = f'ARC物体群スロット区分{群軸}'
            特徴群 = sorted({m[1] for m in self.モデル群 if m[0] == 群軸})
            self.境界観測数[境界] = 0
            for 読取, 枠群 in self.教師対応群:
                # bbox/colorの既存順。特徴や順序候補ごとに観測を複製しない。
                for o, 枠 in zip(読取[3], 枠群):
                    内容 = {f'特徴{i}': o['特徴'][i] for i in 特徴群}
                    機械.実行(観測へ({**内容, '区分': 枠[群軸]}, 境界))
                    self.境界観測数[境界] += 1

    def 候補(self, 格子, _policy):
        読取 = 物体を読む(格子)
        if not self.モデル群 or 読取 is None:
            return None, {'failure': '教師整合モデルまたは適用できる物体群なし'}
        出力群, 照会済み = [], {}
        for 群軸, 特徴番号, 順序軸, 逆順, 写像 in self.モデル群:
            区分群 = []
            for o in 読取[3]:
                値 = o['特徴'][特徴番号]
                if 値 not in 写像:
                    return None, {'failure': '未観測の物体特徴'}
                鍵 = (群軸, 特徴番号, 値)
                if 鍵 not in 照会済み:
                    r = self.機械.照会(self.観測へ({f'特徴{特徴番号}': 値}, f'ARC物体群スロット区分{群軸}'))
                    候補 = [p.予測値 for p in r.予測群 if p.結果経路 == ('区分',)]
                    if 最小排気系().排出する(r).状態 != '出力' or not 候補 or any(v != 候補[0] for v in 候補):
                        return None, {'failure': 'HDS区分照会が未確定'}
                    照会済み[鍵] = 候補[0]
                区分群.append(照会済み[鍵])
            出力 = 配置する(読取, 区分群, 群軸, 順序軸, 逆順, set(写像.values()))
            if 出力 is None:
                return None, {'failure': '未解決の配置モデル'}
            出力群.append(出力)
        if any(g != 出力群[0] for g in 出力群):
            return None, {'failure': '教師整合モデル間の出力競合'}
        return 出力群[0], {'models': len(self.モデル群)}

    def 記録(self):
        return {'モデル群': [{'群軸': a, '特徴番号': f, '順序軸': o, '逆順': r}
                            for a, f, o, r, _ in self.モデル群],
                '物理物体観測数': sum(len(p[0][3]) for p in self.教師対応群),
                '境界観測数': self.境界観測数}
