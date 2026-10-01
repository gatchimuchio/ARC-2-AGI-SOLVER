#!/usr/bin/env python3
"""固定学習機械の保存状態継続・新規連続・課題毎初期化を同じ未使用教材で比較する。"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from 接続.学習環境.HDS接続 import HDS学習機械, 実装署名
from 接続.学習環境.実験 import 実験する


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--教材', type=Path, required=True)
    parser.add_argument('--固定表', type=Path, required=True)
    parser.add_argument('--旧状態', type=Path, required=True)
    parser.add_argument('--出力', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.固定表.read_text(encoding='utf-8'))
    if not 1 <= len(manifest['教材']) <= 16:
        parser.error('一つの有界比較は1〜16課題')
    tasks = []
    for item in manifest['教材']:
        name = item['ファイル']
        if Path(name).name != name or Path(name).suffix != '.json':
            parser.error('教材名はディレクトリなしのJSONファイル名')
        data = (args.教材 / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != item['SHA256']:
            parser.error('教材hash不一致: ' + name)
        tasks.append((name, json.loads(data)))
    frozen = 実装署名()
    evaluator = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    retained = HDS学習機械.読み込む(args.旧状態)
    if retained.最大セル数 != 36 or retained.系.エンジン.最小支持数 != 3 or not retained.学習有効:
        parser.error('この事前固定比較の旧状態は36セル・支持3・学習有効が必要')
    initial = retained.概況()
    cold = HDS学習機械(36)
    args.出力.mkdir(parents=True, exist_ok=True)
    results = []
    started = time.monotonic()
    for i, (name, content) in enumerate(tasks):
        retained.新しい課題()
        if i:
            cold.新しい課題()
        runs = {}
        for mode, machine in (('保存状態継続', retained), ('新規連続', cold), ('課題毎初期化', None)):
            report, _ = 実験する(content, 最大セル数=36, 最大学習経験=8, 学習機械=machine)
            dest = args.出力 / Path(name).stem
            dest.mkdir(parents=True, exist_ok=True)
            (dest / (mode + '.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            runs[mode] = {k: report[k] for k in ('previous', 'current', '評価例数', '記憶除去', '初期', '終了', '学習曲線')}
        results.append({'教材': name, '比較': runs})
        print(json.dumps({'完了': i + 1, '課題数': len(tasks), '教材': name,
                          '得点': {k: v['current'] for k, v in runs.items()},
                          '保持累積経験': retained.概況()['全課題保持経験数']}, ensure_ascii=False), flush=True)
    if 実装署名() != frozen or hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != evaluator:
        raise RuntimeError('比較中に実装または評価器が変わった')
    retained.保存する(args.出力 / '継続最終checkpoint')
    cold.保存する(args.出力 / '新規最終checkpoint')
    summary = {'形式版': 1, '実装署名': frozen, '評価器SHA256': evaluator,
               '教材source': manifest['公式ソース'], '事前選択': manifest['選択'],
               '教材固定表SHA256': hashlib.sha256(args.固定表.read_bytes()).hexdigest(),
               '開始時継承状態': initial, '課題数': len(tasks),
               '評価例数': sum(r['比較']['保存状態継続']['評価例数'] for r in results),
               '学習後正解数': {mode: sum(r['比較'][mode]['current'] for r in results)
                                 for mode in ('保存状態継続', '新規連続', '課題毎初期化')},
               '課題別': results, '経過秒': round(time.monotonic() - started, 3),
               '境界': ['推論実装を固定。途中の得点を用いた実装修正・教材選択をしない',
                        'testは教師内採点だけ。全ての学習は公開trainの予測後観測',
                        '公式evaluation・コンペ得点ではない']}
    (args.出力 / '集計.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != '課題別'}, ensure_ascii=False, indent=2), flush=True)

if __name__ == '__main__':
    main()
