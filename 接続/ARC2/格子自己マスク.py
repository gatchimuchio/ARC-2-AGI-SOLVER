"""教師で32候補を選ぶ、seed付きのcell-mask→macro配置接続。"""
from collections import Counter
from .既存格子操作 import detect_separator_lattice, lattice_tile_mask, transform_grid_by_name

変換群 = ('identity', 'rot90', 'rot180', 'rot270', 'flip_h', 'flip_v', 'transpose', 'anti_transpose')
候補モデル群 = tuple((役割, mask, d4) for 役割 in ('common_background', 'rare_background')
                   for mask in ('exclusive', 'shared') for d4 in 変換群)


def 格子鍵(格子):
    return tuple(map(tuple, 格子))


def 格子を読む(格子):
    分割 = detect_separator_lattice(格子)
    if 分割 is None:
        return None
    行群, 列群 = 分割['row_segments'], 分割['col_segments']
    片群 = [[格子鍵([row[c0:c1+1] for row in 格子[r0:r1+1]])
             for c0, c1 in 列群] for r0, r1 in 行群]
    個数 = Counter(片 for 行 in 片群 for 片 in 行)
    if (len(個数) != 2 or len(set(個数.values())) != 2
            or len({(len(片), len(片[0])) for 片 in 個数}) != 1):
        return None
    return 分割, 片群, 個数


def 配置候補(格子, モデル):
    読取 = 格子を読む(格子)
    if 読取 is None:
        return None, {'failure': '異なる頻度の等寸法二種類の格子片が必要'}
    分割, 片群, 個数 = 読取
    役割, mask種, 変換 = モデル
    順 = sorted(個数, key=個数.get)
    背景片, 原型 = (順[1], 順[0]) if 役割 == 'common_background' else (順[0], 順[1])
    色群 = {v for row in 原型 for v in row}
    背景色群 = {v for row in 背景片 for v in row}
    選択色群 = 色群-背景色群 if mask種 == 'exclusive' else 色群&背景色群
    高さ, 幅 = len(原型), len(原型[0])
    maskセル = set().union(*(lattice_tile_mask(原型, (0, 0, 高さ-1, 幅-1), 色) for 色 in 選択色群))
    mask = transform_grid_by_name([[int((r,c) in maskセル) for c in range(幅)] for r in range(高さ)], 変換)
    有効セル = {(r,c) for r, row in enumerate(mask) for c, v in enumerate(row) if v}
    if not 有効セル:
        return None, {'failure': '空のmask'}
    seed = {(r,c) for r, row in enumerate(片群) for c, 片 in enumerate(row) if 片 == 原型}
    配置群 = []
    for 行 in range(len(片群)-len(mask)+1):
        for 列 in range(len(片群[0])-len(mask[0])+1):
            配置 = frozenset((行+r, 列+c) for r,c in 有効セル)
            if seed <= 配置:
                配置群.append(配置)
    # 全ての入力整合anchorを残す。教師出力で都合のよいanchorを選ばない。
    配置集合 = set(配置群)
    if len(配置集合) != 1:
        return None, {'failure': 'anchorなし又は複数', 'anchors': len(配置集合)}
    配置 = next(iter(配置集合))
    出力 = [row[:] for row in 格子]
    for i, (r0,r1) in enumerate(分割['row_segments']):
        for j, (c0,c1) in enumerate(分割['col_segments']):
            片 = 原型 if (i,j) in 配置 else 背景片
            for y, row in enumerate(片):
                出力[r0+y][c0:c1+1] = row
    return 出力, {'seed_cells': len(seed), 'completed_cells': len(配置), 'anchors': 1}


class 格子自己マスク教材:
    def __init__(self, 教師群):
        self.モデル群 = []
        if not 教師群 or len({格子鍵(p['input']) for p in 教師群}) != len(教師群):
            return
        for モデル in 候補モデル群:
            if all(配置候補(p['input'], モデル)[0] == p['output'] for p in 教師群):
                self.モデル群.append(モデル)

    def 候補(self, 格子, _policy):
        if not self.モデル群:
            return None, {'failure': '全教師再現モデルなし'}
        出力群 = []
        for モデル in self.モデル群:
            出力, 詳細 = 配置候補(格子, モデル)
            if 出力 is None:
                return None, {'failure': '教師整合モデルが未確定', 'detail': 詳細}
            出力群.append(出力)
        if any(出力 != 出力群[0] for 出力 in 出力群):
            return None, {'failure': '教師整合モデル間の予測競合'}
        return 出力群[0], {'models': len(self.モデル群)}

    def 記録(self):
        return {'モデル群': self.モデル群, '候補文法数': len(候補モデル群)}
