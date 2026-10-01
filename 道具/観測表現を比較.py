#!/usr/bin/env python3
"""観測Frameの対照と、旧経験を保存したままの明示的な再観測移行。"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from 接続.学習環境.HDS接続 import HDS学習機械, 実装署名, 署名
from 接続.学習環境.契約 import 格子化, 予測要求
from 接続.学習環境.実験 import 実験する
from hds学習系統 import HDS学習系統


def 格子を復元(observation, frame):
    if set(observation) != {'行数', '列数', 'セル'}:
        raise ValueError('旧観測は明示したARC格子契約だけを受理する')
    h, w = observation['行数'], observation['列数']
    if type(h) is not int or type(w) is not int or not (1 <= h <= 30 and 1 <= w <= 30):
        raise ValueError('旧観測の形状が不正')
    if frame == '座標辞書':
        cells = observation['セル']
        if not isinstance(cells, dict) or set(cells) != {f'{r},{c}' for r in range(h) for c in range(w)}:
            raise ValueError('旧観測に欠落・余剰セルがある')
        grid = 格子化([[cells[f'{r},{c}'] for c in range(w)] for r in range(h)])
    elif frame == '配列階層':
        grid = 格子化(observation['セル'])
    else:
        raise ValueError('未知の観測表現を変換しない')
    if (len(grid), len(grid[0])) != (h, w):
        raise ValueError('宣言形状と格子が不一致')
    return grid


def 旧状態を検証して読む(directory, expected_implementation):
    directory = Path(directory)
    meta = json.loads((directory / '境界.json').read_text(encoding='utf-8'))
    if meta['形式版'] not in (1, 2) or meta['実装署名'] != expected_implementation:
        raise ValueError('許可した旧実装・形式と異なる。無言移行しない')
    frame = meta.get('観測表現', '座標辞書')
    holder = HDS学習機械(meta['最大セル数'], 学習有効=meta['学習有効'], 観測表現=frame)
    holder.系 = HDS学習系統.読み込む(directory / 'HDS.json')
    holder._観測署名 = set(meta['観測署名'])
    holder._失敗 = meta['失敗']
    holder._課題番号 = meta['課題番号']
    holder._転用候補 = meta['転用候補']
    if holder.系.エンジン.数量関係有効 != meta.get('数量関係有効', True):
        raise ValueError('旧状態の数量設定がHDSと境界で不一致')
    if holder.系.エンジン.添字関係有効 != meta.get('添字関係有効', True):
        raise ValueError('旧状態の添字設定がHDSと境界で不一致')
    for key,default in (('関係合成有効',False),('最大合成段数',4),('最大合成候補数',4096)):
        if getattr(holder.系.エンジン,key)!=meta.get(key,default):raise ValueError('旧合成設定がHDSと境界で不一致')
    state = holder.状態()
    for key in ('関係合成有効','最大合成段数','最大合成候補数'):
        if key not in meta:state.pop(key)
    if meta['形式版'] == 1:
        for key in ('観測表現', '最大セル数', '学習有効', '最小支持数', '最大条件数'):
            state.pop(key)
    if '添字関係有効' not in meta:
        state.pop('添字関係有効')
    if '数量関係有効' not in meta:
        state.pop('数量関係有効')
    if 署名(state) != meta['状態署名']:
        raise ValueError('旧状態の論理署名が不一致')
    if holder.系.エンジン.最小支持数 != 3 or holder.系.エンジン.最大条件数 != 1:
        raise ValueError('今回の移行検証は支持3・最大条件1だけを対象とする')
    return holder, meta


def 旧経験を検証して取り出す(directory, expected_implementation):
    directory = Path(directory)
    holder, meta = 旧状態を検証して読む(directory, expected_implementation)
    frame = meta.get('観測表現', '座標辞書')
    records = []
    for e in holder.系.エンジン._経験群():
        if set(e.原入力) != {'入力', '出力'}:
            raise ValueError('経験に未対応の内容がある')
        records.append({'旧境界': e.対象系境界, '旧経験参照': e.経験識別子,
                        '入力': 格子を復元(e.原入力['入力'], frame),
                        '出力': 格子を復元(e.原入力['出力'], frame)})
    return records, {'旧実装署名': expected_implementation, '旧状態署名': meta['状態署名'],
                     '旧観測表現': frame, '旧経験数': len(records), '世界観測署名': 署名(records),
                     '旧HDSファイルSHA256': hashlib.sha256((directory / 'HDS.json').read_bytes()).hexdigest()}


def 再観測する(records, frame, maximum=36):
    machine = HDS学習機械(maximum, 観測表現=frame)
    last_scope, trace = None, []
    for record in records:
        if last_scope is not None and record['旧境界'] != last_scope:
            machine.新しい課題()
        last_scope = record['旧境界']
        request = 予測要求(record['入力'])
        machine.予測する(request)
        change = machine.観測する(request, record['出力'])
        if change['採否'] != 'ADMIT':
            raise ValueError('再観測を黙って脱落・重複計数しない: ' + change.get('理由', '不明'))
        trace.append({'旧経験参照': record['旧経験参照'], '旧境界': record['旧境界'],
                      '新経験参照': change['学習過程']['経験参照'], '新境界': machine.現在境界,
                      '世界観測署名': 署名((record['入力'], record['出力']))})
    return machine, trace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='操作', required=True)
    replay = sub.add_parser('再観測')
    replay.add_argument('--旧状態', type=Path, required=True)
    replay.add_argument('--旧実装署名', required=True)
    replay.add_argument('--観測表現', choices=('座標辞書', '配列階層'), required=True)
    replay.add_argument('--観測上限', type=int, default=128)
    compare = sub.add_parser('比較')
    compare.add_argument('--教材', type=Path, required=True)
    compare.add_argument('--固定表', type=Path, required=True)
    for p in (replay, compare):
        p.add_argument('--出力', type=Path, required=True)
        p.add_argument('--最大セル数', type=int, default=36)
    args = parser.parse_args()
    frozen, evaluator = 実装署名(), hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.出力.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    if args.操作 == '再観測':
        records, report = 旧経験を検証して取り出す(args.旧状態, args.旧実装署名)
        if len(records) > args.観測上限:
            parser.error('明示した再観測上限を超える。途中切捨てはしない')
        machine, trace = 再観測する(records, args.観測表現, args.最大セル数)
        machine.保存する(args.出力 / 'checkpoint')
        report.update({'責任': 'DEVELOPMENTによる観測再符号化と状態再生成', '新規世界観測数': 0,
                       '再処理経験数': len(trace), '観測表現': args.観測表現, '終了': machine.概況(), '対応': trace})
    else:
        manifest_bytes = args.固定表.read_bytes()
        manifest = json.loads(manifest_bytes)
        if not 1 <= len(manifest['教材']) <= 16:
            parser.error('有界比較は1〜16課題')
        modes = ('座標辞書', '配列階層')
        learners = {mode: HDS学習機械(args.最大セル数, 観測表現=mode) for mode in modes}
        tasks, results = [], []
        for item in manifest['教材']:
            name = item['ファイル']
            if Path(name).name != name:
                parser.error('教材名にディレクトリを含めない')
            data = (args.教材 / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != item['SHA256']:
                parser.error('教材hash不一致')
            tasks.append((name, json.loads(data)))
        for i, (name, content) in enumerate(tasks):
            row = {'教材': name, 'Frame別': {}}
            for mode in modes:
                if i:
                    learners[mode].新しい課題()
                result, _ = 実験する(content, args.最大セル数, 学習機械=learners[mode])
                reset, _ = 実験する(content, args.最大セル数, 観測表現=mode)
                dest = args.出力 / Path(name).stem
                dest.mkdir(parents=True, exist_ok=True)
                (dest / (mode + '.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                row['Frame別'][mode] = {'学習前': result['previous'], '学習後': result['current'],
                    '課題毎初期化': reset['current'], '記憶除去': result['記憶除去'], '評価例数': result['評価例数'],
                    '終了': result['終了'], '学習曲線': result['学習曲線']}
            results.append(row)
            print(json.dumps({'完了': i + 1, '課題数': len(tasks), '得点': {m: row['Frame別'][m]['学習後'] for m in modes}}, ensure_ascii=False), flush=True)
        for mode, machine in learners.items():
            machine.保存する(args.出力 / (mode + '_checkpoint'))
        report = {'責任': '同一機械の入力Frameの開発比較', '教材固定表SHA256': hashlib.sha256(manifest_bytes).hexdigest(),
                  '課題数': len(tasks), '評価例数': sum(r['Frame別'][modes[0]]['評価例数'] for r in results),
                  '学習後正解': {m: sum(r['Frame別'][m]['学習後'] for r in results) for m in modes},
                  '課題毎初期化正解': {m: sum(r['Frame別'][m]['課題毎初期化'] for r in results) for m in modes}, '課題別': results}
    if 実装署名() != frozen or hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != evaluator:
        raise RuntimeError('実行中に実装が変わった')
    report.update({'実装署名': frozen, '評価器SHA256': evaluator, '経過秒': round(time.monotonic() - started, 3)})
    (args.出力 / '集計.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('課題別', '対応')}, ensure_ascii=False, indent=2), flush=True)

if __name__ == '__main__':
    main()
