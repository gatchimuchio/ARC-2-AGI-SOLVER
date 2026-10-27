"""全ての現在教師から出力paletteを確定し、既存グラフ候補へ渡す。"""
from collections import Counter
from .既存成分最短経路 import (
    terminal_square_path_policy, terminal_square_path_output_colors,
    render_terminal_square_component_path_recolorer,
)


def 背景が一意(格子):
    if not 格子 or not 格子[0]:
        return False
    数 = Counter(v for row in 格子 for v in row)
    return sum(v == max(数.values()) for v in 数.values()) == 1


class 成分経路教材:
    def __init__(self, 教師群):
        self.出力色対 = None
        if not 教師群 or len({tuple(map(tuple, p['input'])) for p in 教師群}) != len(教師群):
            return
        色対群 = []
        for 番号, 対 in enumerate(教師群):
            入力, 正解 = 対['input'], 対['output']
            if not 背景が一意(入力) or (len(入力),len(入力[0])) != (len(正解),len(正解[0])):
                return
            方針, _ = terminal_square_path_policy(入力)
            if 方針 is None:
                return
            色対, _ = terminal_square_path_output_colors(入力, 正解, 方針, 番号)
            if 色対 is None or render_terminal_square_component_path_recolorer(入力, *色対)[0] != 正解:
                return
            色対群.append(色対)
        if len(set(色対群)) == 1:
            self.出力色対 = 色対群[0]

    def 候補(self, 格子, _policy):
        if self.出力色対 is None or not 背景が一意(格子):
            return None, {'failure': '教師共有palette又は一意背景なし'}
        return render_terminal_square_component_path_recolorer(格子, *self.出力色対)

    def 記録(self):
        return {'出力色対': self.出力色対}
