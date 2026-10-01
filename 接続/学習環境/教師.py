"""教師側にだけ公開正解を保持し、予測確定を先に記録する。"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from .契約 import 格子化, 予測要求, 結果通知

class 公開教材:
    def __init__(self, content):
        if set(content) != {'train', 'test'} or not content['train'] or not content['test']:
            raise ValueError('公開ARC教材はtrain/testを持つ')
        self._組 = {}
        for split in ('train', 'test'):
            rows = []
            for example in content[split]:
                if set(example) != {'input', 'output'}:
                    raise ValueError('公開教材の各例はinput/outputのみ。非公開testは対象外')
                rows.append((格子化(example['input']), 格子化(example['output'])))
            self._組[split] = tuple(rows)

    def 件数(self, split):
        return len(self._組[split])

    def 問い(self, split, index):
        return 予測要求(self._組[split][index][0])

    def 採点(self, split, index, prediction):
        return 結果通知(prediction.出力 == self._組[split][index][1], prediction.状態)

    def 教示可能(self, index):
        """公開trainの予測後観測専用。testを引数に受け付けない。"""
        return deepcopy(self._組['train'][index][1])

class 教師:
    def __init__(self, 教材):
        self.教材 = 教材
        self.履歴 = []
        self._提示済み = {}
        self._教示済み = set()

    def 評価(self, 学習機械, split, index):
        request = self.教材.問い(split, index)
        # 正解に触れる前に予測と学習状態署名を固定する。
        before = 学習機械.状態署名()
        prediction = 学習機械.予測する(request)
        after = 学習機械.状態署名()
        if before != after:
            raise RuntimeError('評価照会が学習状態を書き換えた')
        record = {'分割': split, '位置': index, '予測': asdict(prediction),
                  '学習状態署名': before, '順序': '予測確定→教師採点'}
        record['予測確定署名'] = hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        outcome = self.教材.採点(split, index, prediction)
        record['結果'] = asdict(outcome)
        self.履歴.append(record)
        self._提示済み[(id(学習機械), split, index)] = (学習機械, before)
        return prediction, outcome

    def 教示(self, 学習機械, index):
        receipt = self._提示済み.get((id(学習機械), 'train', index))
        if receipt is None or receipt[0] is not 学習機械 or receipt[1] != 学習機械.状態署名():
            raise RuntimeError('予測前には教師出力を教示できない')
        if (id(学習機械), index) in self._教示済み:
            raise RuntimeError('同じ例を独立経験として再投入しない')
        change = 学習機械.観測する(self.教材.問い('train', index), self.教材.教示可能(index))
        self._教示済み.add((id(学習機械), index))
        self.履歴.append({'分割': 'train', '位置': index, '段階': '予測後の公開観測', '更新': change})
        return change
