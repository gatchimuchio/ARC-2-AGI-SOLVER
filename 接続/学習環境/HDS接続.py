"""既存HDS学習系統への構造だけのAdapter。変換解法を持たない。"""
from __future__ import annotations
from copy import copy, deepcopy
from dataclasses import asdict, fields, is_dataclass, replace
from enum import Enum
import hashlib
import json
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(_ROOT / 'HDS/学習系統/v0.4.2'))
from hds学習系統 import HDS学習系統, 外部入力
from hds学習系統.型 import 原理候補, 経験記録, 判定状態
from hds学習系統.検証 import 共通検証器
from hds学習系統.適応 import 原理証拠を評価する
from .契約 import 格子化, 予測要求, 予測

目的 = '公開教材で得た経験から暫定関係を学習し、未提示例への適用を検証する'
境界 = 'ARC公開教材・単一学習エピソード'

def 正規化(value):
    if is_dataclass(value):
        value = {f.name: getattr(value, f.name) for f in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): 正規化(v) for k, v in value.items() if k not in {'時点', '対象期間'}}
    if isinstance(value, (tuple, list)):
        return [正規化(v) for v in value]
    return value

def 署名(value):
    return hashlib.sha256(json.dumps(正規化(value), ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def 実装署名():
    import hds学習系統
    roots = (Path(__file__).parent, Path(hds学習系統.__file__).parent)
    parts = [(str(i) + '/' + p.name, hashlib.sha256(p.read_bytes()).hexdigest())
             for i, root in enumerate(roots) for p in sorted(root.glob('*.py'))]
    return 署名(parts)


def 観測射影(grid):
    # 座標と値の列挙だけ。回転・鏡映・色置換などの候補は外から作らない。
    return {'行数': len(grid), '列数': len(grid[0]),
            'セル': {f'{r},{c}': value for r, row in enumerate(grid) for c, value in enumerate(row)}}

class HDS学習機械:
    def __init__(self, 最大セル数=36, 最小学習経験=3, 学習有効=True):
        if type(最大セル数) is not int or not 1 <= 最大セル数 <= 900:
            raise ValueError('最大セル数は1..900')
        if type(最小学習経験) is not int or 最小学習経験 < 3:
            raise ValueError('独立経験の最小支持数は3以上')
        self.最大セル数 = 最大セル数
        self.学習有効 = 学習有効
        self.系 = HDS学習系統(最小支持数=最小学習経験, 最大条件数=1)
        self._観測署名 = set()
        self._失敗 = []
        self._課題番号 = 0
        self._転用候補 = {}

    @property
    def 現在境界(self):
        return 境界 + ':' + str(self._課題番号)

    def _入力(self, content):
        return self.系.吸気系.取り込む(外部入力(content, self.現在境界, 主体='HDS', 目的=目的))

    def 状態(self):
        engine = self.系.エンジン
        return 正規化({'状態版': engine.状態.現在版, '状態': engine.状態.現在状態,
                       '原理履歴': engine._原理履歴, '経験': engine.台帳._台帳,
                       '識別子': engine.識別子.状態を書き出す(),
                       '観測署名': sorted(self._観測署名), '失敗': self._失敗,
                       '課題番号': self._課題番号, '転用候補': self._転用候補})

    def 状態署名(self):
        # 状態()は既に完全な値複製・正規化済み。二度目の全台帳走査をしない。
        return hashlib.sha256(json.dumps(self.状態(), ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def 概況(self):
        engine = self.系.エンジン
        return {'経験数': len(self._観測署名), '状態版': engine.状態.現在版,
                '有効原理数': sum(p.対象系境界 == self.現在境界 for p in engine._有効原理群()),
                '隔離原理数': sum(p.対象系境界 == self.現在境界 for p in engine._係争中原理群()),
                '全課題保持経験数': len(engine._経験群()), '転用候補数': len(self._転用候補),
                '転用隔離数': sum(c['状態'] == '隔離' for c in self._転用候補.values()),
                '状態署名': self.状態署名()}

    def _通常予測(self, request: 予測要求):
        if type(request) is not 予測要求:
            raise TypeError('予測要求だけを受理する')
        grid = request.入力
        if len(grid) * len(grid[0]) > self.最大セル数:
            return 予測('HOLD', None, ('入力が明示計算予算を超過',))
        # 既存照会の唯一の書込み対象（識別子）だけ複製。台帳・原理は読み取り専用。
        engine = copy(self.系.エンジン)
        engine.識別子 = deepcopy(self.系.エンジン.識別子)
        result = engine.照会(self._入力({'入力': 観測射影(grid)}))
        return self._予測を格子化(result.予測群, result.競合群)

    def _予測を格子化(self, predictions, supplied_conflicts):
        values, refs, conflicts = {}, [], []
        for p in predictions:
            if p.結果経路 and p.結果経路[0] == '出力':
                facts = []
                self.系.吸気系._平坦化(p.予測値, p.結果経路, facts)
                projected = {f.経路: f.値 for f in facts if f.推論対象}
                if p.結果経路 == ('出力', 'セル') and isinstance(p.予測値, dict):
                    # 完成したセル集合からARC格子を直列化する。未予測セルは補わない。
                    try:
                        positions = {tuple(map(int, k.split(','))) for k in p.予測値}
                        if positions and all(len(k) == 2 and min(k) >= 0 for k in positions):
                            h, w = 1 + max(k[0] for k in positions), 1 + max(k[1] for k in positions)
                            if positions == {(r, c) for r in range(h) for c in range(w)}:
                                projected[('出力', '行数')], projected[('出力', '列数')] = h, w
                    except (TypeError, ValueError):
                        pass
                for path, value in projected.items():
                    if path in values and values[path] != value:
                        conflicts.append(path)
                    values[path] = value
                refs.append(p.原理参照)
        conflicts.extend(c for c in supplied_conflicts if c.結果経路[0] == '出力')
        if conflicts:
            return 予測('HOLD', None, ('出力関係の競合',), tuple(sorted(set(refs))), len(values))
        height, width = values.get(('出力', '行数')), values.get(('出力', '列数'))
        if type(height) is not int or type(width) is not int or not (1 <= height <= 30 and 1 <= width <= 30):
            return 予測('HOLD', None, ('出力形状が未閉包',), tuple(sorted(set(refs))), len(values))
        if height * width > self.最大セル数:
            return 予測('HOLD', None, ('予測形状が明示計算予算を超過',), tuple(sorted(set(refs))), len(values))
        output = []
        for r in range(height):
            row = []
            for c in range(width):
                value = values.get(('出力', 'セル', f'{r},{c}'))
                if type(value) is not int or not 0 <= value <= 9:
                    return 予測('HOLD', None, ('出力セルが未閉包',), tuple(sorted(set(refs))), len(values))
                row.append(value)
            output.append(tuple(row))
        return 予測('COMMIT', tuple(output), ('現在入力で出力項目が閉包した暫定予測。因果法則の断定ではない',), tuple(sorted(set(refs))), len(values))

    def 観測する(self, request, 観測出力, 更新許可=True):
        grid = 格子化(観測出力)
        if type(request) is not 予測要求:
            raise TypeError('予測要求だけを受理する')
        content = {'入力': 観測射影(request.入力), '出力': 観測射影(grid)}
        key = 署名((self.現在境界, content))
        before = self.概況()
        if not 更新許可 or not self.学習有効:
            return {'採否': 'REJECT', '理由': '記憶更新不許可', '前': before, '後': before}
        if max(len(request.入力) * len(request.入力[0]), len(grid) * len(grid[0])) > self.最大セル数:
            return {'採否': 'HOLD', '理由': '観測が明示計算予算を超過', '前': before, '後': before}
        if key in self._観測署名:
            return {'採否': 'HOLD', '理由': '同一観測の再投入', '前': before, '後': before}
        prior = self.予測する(request)
        # 採用は既存HDSの懐疑→推論→検証→採用を通る。例外時は複製を破棄する。
        candidate = deepcopy(self.系.エンジン)
        result = candidate.実行(self._入力(content))
        self.系.エンジン = candidate
        self._観測署名.add(key)
        self._転用を監査する()
        if prior.出力 != grid:
            self._失敗.append({'分類': '予測未成立' if prior.出力 is None else '暫定予測反証',
                               '発火条件': prior.理由, '影響原理': prior.使用原理,
                               '経験参照': result.学習過程.経験参照,
                               '原因': '未確定。HDSの反証・隔離履歴を参照'})
        return {'採否': 'ADMIT', '前': before, '後': self.概況(),
                '学習過程': 正規化(result.学習過程)}

    def _転用原理(self, capsule):
        # 原記録は変更しない。HDSが許可する現在scopeへの候補射影だけを作る。
        return tuple(replace(self.系.エンジン._原理を探す(ID), 対象系境界=self.現在境界)
                     for ID in capsule['原理参照'])

    @staticmethod
    def _候補化(p):
        return 原理候補(p.原理識別子, p.対象系境界, p.関係型, p.条件経路群,
                      p.結果経路, p.対応表, p.対応値表, p.根拠参照群, (), (),
                      p.適用範囲, {'作用': '過去採用関係の現在観測による再検証', '因果断定': False})

    def _適用範囲内経験(self, capsule):
        return tuple(e for e in self.系.エンジン._経験群(self.現在境界)
                     if capsule.get('構造一般', False) or [e.原入力['入力']['行数'], e.原入力['入力']['列数']] in capsule['入力形状'])

    def _転用を監査する(self):
        for capsule in self._転用候補.values():
            current = self._適用範囲内経験(capsule)
            if capsule['状態'] == '隔離':
                continue
            refs = set()
            for principle in self._転用原理(capsule):
                _, counters = 原理証拠を評価する(principle, current)
                refs.update(counters)
            if refs:
                capsule['状態'] = '隔離'
                capsule['反証参照'] = sorted(set(capsule['反証参照']) | refs)
                self._失敗.append({'分類': '転用適用範囲反証', '候補': capsule['署名'],
                                   '反証参照': sorted(refs), '次処置': '自動復帰禁止'})
            elif len(current) >= 2:
                checks = [共通検証器(最小支持数=2).検証する(self._候補化(p), current)
                          for p in self._転用原理(capsule)]
                if all(x.判定 == 判定状態.適合 for x in checks):
                    capsule['再検証境界'] = self.現在境界
                    capsule['現在支持参照'] = sorted({r for x in checks for r in x.支持参照群})


    def _転用予測群(self, request):
        current = self.系.エンジン._経験群(self.現在境界)
        if len(current) < 2:
            return ()
        shape = [len(request.入力), len(request.入力[0])]
        result = []
        validator = 共通検証器(最小支持数=2)
        for capsule in self._転用候補.values():
            if capsule['状態'] == '隔離' or (not capsule.get('構造一般', False) and shape not in capsule['入力形状']):
                continue
            current = self._適用範囲内経験(capsule)
            principles = self._転用原理(capsule)
            if not all(validator.検証する(self._候補化(p), current).判定 == 判定状態.適合 for p in principles):
                continue
            intake = self._入力({'入力': 観測射影(request.入力)})
            experience = 経験記録('非学習転用照会', self.現在境界, intake.原入力, intake.観測群,
                                  intake.主体, intake.対象, intake.目的, '')
            predictions, conflicts, _ = self.系.エンジン.適応器.予測する(principles, experience)
            formatted = self._予測を格子化(predictions, conflicts)
            if formatted.出力 is None:
                continue
            grid = formatted.出力
            # 現課題の既存原理とも整合しなければ過去モデルを優先しない。
            observed = self._入力({'入力': 観測射影(request.入力), '出力': 観測射影(grid)})
            check = replace(experience, 原入力=observed.原入力, 観測群=observed.観測群)
            if any(原理証拠を評価する(p, (check,))[1] for p in self.系.エンジン._有効原理群()
                   if p.対象系境界 == self.現在境界):
                continue
            result.append(予測('COMMIT', grid, ('過去3支持以上と現在2独立支持による範囲付き暫定転用',),
                               formatted.使用原理, formatted.推定済み項目数))
        return tuple(result)

    def 予測する(self, request: 予測要求):
        primary = self._通常予測(request)
        if '出力関係の競合' in primary.理由 or '入力が明示計算予算を超過' in primary.理由:
            return primary
        reused = self._転用予測群(request)
        candidates = (*reused, *((primary,) if primary.出力 is not None else ()))
        outputs = {p.出力 for p in candidates}
        if len(outputs) > 1:
            return 予測('HOLD', None, ('現在原理と転用候補の競合',))
        return reused[0] if reused else primary

    def 新しい課題(self):
        """権限scopeの切替。課題IDは受け取らず、原理・経験・反例を同一機械に保持。"""
        engine = self.系.エンジン
        principles = tuple(p for p in engine._有効原理群()
                           if p.対象系境界 == self.現在境界 and p.結果経路[0] == '出力'
                           and p.関係型 in {'同値関係', '定値関係'}
                           and all(path[0] == '入力' for path in p.条件経路群))
        # 定値格子丸ごとを答えとして転用しない。入力依存の学習済み関係が必要。
        if any(p.関係型 == '同値関係' and p.結果経路[:2] == ('出力', 'セル') for p in principles):
            self._転用候補を保持(principles, False)
        from hds学習系統.構造関係 import 構造関係型
        for p in engine._有効原理群():
            if (p.対象系境界 == self.現在境界 and p.結果経路[0] == '出力'
                    and p.関係型 in 構造関係型 and p.条件経路群[0][0] == '入力'):
                if p.関係型 == '構造要素対応関係' and len({署名(v) for _, v in p.対応値表}) < 2:
                    continue  # 定値だけの出力を答えとして課題間へ持ち込まない。
                self._転用候補を保持((p,), True)
        self._課題番号 += 1
        self._観測署名 = set()
        # 失敗履歴・HDS経験・原理は削除しない。新scopeは学習前のため転用も保留。
        return self.状態()

    def _転用候補を保持(self, principles, structural):
        structure = [(p.関係型, p.条件経路群, p.結果経路,
                      p.対応値表 if p.関係型 in {'定値関係', '構造要素対応関係'} else (),
                      p.適用範囲.get('根容器型'), p.適用範囲.get('葉値型群')) for p in principles]
        key = 署名(structure)
        shapes = sorted({(e.原入力['入力']['行数'], e.原入力['入力']['列数'])
                         for e in self.系.エンジン._経験群(self.現在境界)})
        if key not in self._転用候補 and len(self._転用候補) < 64:
            self._転用候補[key] = {'署名': key, '原理参照': [p.原理識別子 for p in principles],
                                 '入力形状': [list(x) for x in shapes], '構造一般': structural,
                                 '状態': '再検証待ち', '反証参照': []}

    def 保存する(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.系.保存する(directory / 'HDS.json')
        (directory / '境界.json').write_text(json.dumps({'形式版': 1, '実装署名': 実装署名(), '最大セル数': self.最大セル数,
            '学習有効': self.学習有効, '観測署名': sorted(self._観測署名), '失敗': self._失敗,
            '状態署名': self.状態署名(), '課題番号': self._課題番号, '転用候補': self._転用候補}, ensure_ascii=False, indent=2), encoding='utf-8')

    @classmethod
    def 読み込む(cls, directory):
        directory = Path(directory)
        meta = json.loads((directory / '境界.json').read_text(encoding='utf-8'))
        if meta['形式版'] != 1:
            raise ValueError('未対応の境界版')
        if meta['実装署名'] != 実装署名():
            raise ValueError('保存時と機械実装が異なる。無言移行しない')
        obj = cls(meta['最大セル数'], 学習有効=meta['学習有効'])
        obj.系 = HDS学習系統.読み込む(directory / 'HDS.json')
        obj._観測署名 = set(meta['観測署名'])
        obj._失敗 = meta['失敗']
        obj._課題番号 = meta['課題番号']
        obj._転用候補 = meta['転用候補']
        if obj.状態署名() != meta['状態署名']:
            raise ValueError('保存状態署名が不一致')
        return obj
