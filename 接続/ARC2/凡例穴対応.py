"""教師由来の役割色候補と、凡例不在時の動作を保守的に選ぶ。"""
from .既存凡例穴対応 import render_legend_hole_count_recolorer


class 凡例穴教材:
    def __init__(self, 教師群, 最小支持数):
        self.候補群 = []
        self.最小支持数 = 最小支持数
        if not 教師群 or any((len(p['input']),len(p['input'][0])) !=
                              (len(p['output']),len(p['output'][0])) for p in 教師群):
            return
        入力色 = {v for p in 教師群 for row in p['input'] for v in row}
        出力色 = {v for p in 教師群 for row in p['output'] for v in row}
        # 旧fitの役割候補。複数の場合も全教師適合候補を保持する。
        for marker in sorted(入力色-出力色):
            for background in sorted(出力色-{marker}):
                消去支持 = set()
                for p in 教師群:
                    y, info = render_legend_hole_count_recolorer(p['input'],marker,background)
                    if y != p['output']:
                        break
                    if info['legend_removed_component_count']:
                        # 数えるのは異なる教師入力。hole countの許可表ではない。
                        消去支持.add(tuple(tuple(row) for row in p['input']))
                else:
                    self.候補群.append({'marker':marker,'background':background,
                                        '消去支持教師数':len(消去支持)})

    def 候補(self, 格子, _policy):
        if not self.候補群:
            return None, {'failure':'全教師に適合する役割色なし'}
        outputs = []
        for p in self.候補群:
            y, info = render_legend_hole_count_recolorer(格子,p['marker'],p['background'])
            if y is None:
                return None, {'failure':'保持した役割候補が入力を解釈できない'}
            if info['legend_removed_component_count'] and p['消去支持教師数'] < self.最小支持数:
                return None, {'failure':'凡例不在時の消去を支持する教師が不足'}
            outputs.append(y)
        if any(y != outputs[0] for y in outputs):
            return None, {'failure':'保持した役割候補の完全格子出力が競合'}
        return outputs[0], {'役割候補数':len(self.候補群)}

    def 記録(self):
        return {'役割候補群':self.候補群,'消去分岐最小支持数':self.最小支持数,
                '消去条件':'この入力の凡例に穴数の対応が存在しない'}
