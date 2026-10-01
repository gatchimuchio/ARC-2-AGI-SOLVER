#!/usr/bin/env python3
"""固定教材をprocess単位で監督する。資源失敗も分母へ残す。"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from 接続.学習環境.HDS接続 import HDS学習機械, 実装署名
from 接続.学習環境.実験 import 実験する


def 保存(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def 制限を設定(memory_mib):
    limit = memory_mib * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def 監督(command, timeout, memory_mib):
    started = time.monotonic()
    try:
        r = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, timeout=timeout,
                           preexec_fn=lambda: 制限を設定(memory_mib))
        kind = '完了' if r.returncode == 0 else ('メモリ上限' if 'MemoryError' in r.stderr else '実行失敗')
        return {'分類': kind, 'returncode': r.returncode, '秒': round(time.monotonic()-started, 3),
                'stderr': r.stderr[-4000:]}
    except subprocess.TimeoutExpired:
        return {'分類': '時間上限', 'returncode': None, '秒': round(time.monotonic()-started, 3), 'stderr': ''}


def 次状態を選ぶ(outcome, destination, previous):
    if outcome['分類'] != '完了':
        return previous
    if any(not (destination / relative).is_file() for relative in ('report.json', 'checkpoint/境界.json', 'checkpoint/HDS.json')):
        raise ValueError('完了状態に必要なreport/checkpointが欠落')
    report = json.loads((destination / 'report.json').read_text())
    boundary = json.loads((destination / 'checkpoint/境界.json').read_text())
    if report['終了']['状態署名'] != boundary['状態署名']:
        raise ValueError('reportとcheckpointの終了状態が不一致')
    return destination / 'checkpoint'


def worker(args):
    machine = HDS学習機械.読み込む(args.checkpoint)
    machine.新しい課題()
    task_bytes = args.task.read_bytes()
    if hashlib.sha256(task_bytes).hexdigest() != args.task_sha256:
        raise ValueError('worker教材hash不一致')
    report, _ = 実験する(json.loads(task_bytes), 最大セル数=machine.最大セル数,
                          学習機械=machine, 観測表現=machine.観測表現)
    # 状態全体が保存できた場合だけ、親が次のcheckpointとして採用する。
    machine.保存する(args.output / 'checkpoint')
    report['資源'] = {'最大RSS_KiB': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    保存(args.output / 'report.json', report)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='op', required=True)
    w = sub.add_parser('worker')
    w.add_argument('--task', type=Path, required=True)
    w.add_argument('--task-sha256', required=True)
    w.add_argument('--checkpoint', type=Path, required=True)
    w.add_argument('--output', type=Path, required=True)
    r = sub.add_parser('run')
    for name in ('教材', '固定表', '計画', '旧状態', '出力'):
        r.add_argument('--' + name, type=Path, required=True)
    args = p.parse_args()
    if args.op == 'worker':
        worker(args)
        return
    plan = json.loads(args.計画.read_text())
    manifest = json.loads(args.固定表.read_text())
    plan_hash = hashlib.sha256(args.計画.read_bytes()).hexdigest()
    manifest_hash = hashlib.sha256(args.固定表.read_bytes()).hexdigest()
    if plan_hash != manifest['事前計画SHA256'] or 実装署名() != plan['機械実装署名']:
        p.error('事前計画または凍結機械が不一致')
    if not 1 <= len(manifest['教材']) <= 8:
        p.error('事前の8課題上限')
    if args.出力.exists():
        p.error('既存結果を上書きしない。別の出力先を指定')
    tasks = []
    for item in manifest['教材']:
        name = item['ファイル']
        if Path(name).name != name:
            p.error('教材path不正')
        path = args.教材 / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['SHA256']:
            p.error('教材hash不一致')
        content = json.loads(path.read_text())
        if not 3 <= len(content['train']) <= 8 or any(len(g)*len(g[0]) > 64 for row in content['train']+content['test'] for g in row.values()):
            p.error('事前教材予算不一致')
        tasks.append((name, path, len(content['test']), item['SHA256']))
    for name, expected in plan['開始checkpoint']['ファイルSHA256'].items():
        if name not in ('境界.json', 'HDS.json') or hashlib.sha256((args.旧状態 / name).read_bytes()).hexdigest() != expected:
            p.error('開始checkpointの元ファイルhash不一致')
    retained = HDS学習機械.読み込む(args.旧状態)
    if retained.状態署名() != plan['開始checkpoint']['状態署名']:
        p.error('開始checkpointの論理状態不一致')
    if retained.観測表現 != plan['Frame'] or retained.最大セル数 != 36:
        p.error('旧checkpointのFrame・予算不一致')
    before = retained.概況()
    if before['全課題保持経験数'] != 55:
        p.error('今回の事前計画は55経験開始')
    retained.最大セル数 = 64
    after = retained.概況()
    states = {}
    for mode in plan['比較']:
        machine = retained if mode == '55経験継続' else HDS学習機械(64, 観測表現=plan['Frame'])
        checkpoint = args.出力 / '開始' / mode
        machine.保存する(checkpoint)
        states[mode] = checkpoint
    initial = dict(states)
    evaluator = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    results = []
    for i, (name, path, test_count, task_hash) in enumerate(tasks):
        runs = {}
        for mode in plan['比較']:
            dest = args.出力 / Path(name).stem / mode
            checkpoint = initial[mode] if mode == '課題毎初期化' else states[mode]
            command = [sys.executable, str(Path(__file__).resolve()), 'worker', '--task', str(path.resolve()),
                       '--task-sha256', task_hash, '--checkpoint', str(checkpoint.resolve()), '--output', str(dest.resolve())]
            outcome = 監督(command, plan['各課題各対照の壁時計上限秒'], plan['各process仮想メモリ上限MiB'])
            next_state = 次状態を選ぶ(outcome, dest, checkpoint)
            if outcome['分類'] == '完了':
                report = json.loads((dest / 'report.json').read_text())
                if report['実装署名'] != plan['機械実装署名']:
                    raise RuntimeError('worker実装不一致')
                states[mode] = next_state
                compact = {key: report[key] for key in ('previous', 'current', '評価例数', '記憶除去', '初期', '終了', '学習曲線', '資源')}
            else:
                compact = {'previous': None, 'current': 0, '評価例数': test_count,
                           '状態': 'HOLD', '経験更新': '未完了課題を採用せず直前checkpointを保持'}
            compact['監督'] = outcome
            runs[mode] = compact
            保存(dest / '監督.json', compact)
        results.append({'教材': name, '比較': runs})
        print(json.dumps({'完了':i+1, '課題数':len(tasks), '比較':{k:(v['current'],v['監督']['分類']) for k,v in runs.items()}},ensure_ascii=False),flush=True)
        if hashlib.sha256(args.計画.read_bytes()).hexdigest() != plan_hash or hashlib.sha256(args.固定表.read_bytes()).hexdigest() != manifest_hash:
            raise RuntimeError('計画・固定表が途中変更された')
        if 実装署名() != plan['機械実装署名'] or hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != evaluator:
            raise RuntimeError('凍結実装が途中変更された')
        summary = {'責任':'事前固定の未使用公開training・資源監督比較', '計画':plan, '計画SHA256':plan_hash,
                   '固定表SHA256':manifest_hash, '評価器SHA256':evaluator,
                   '予算変更前':before,'予算変更後':after,'新規世界観測_予算変更':0,
                   '課題数':len(tasks),'完了課題数':len(results),'評価例数':sum(x[2] for x in tasks),
                   '正解数':{m:sum(x['比較'][m]['current'] for x in results) for m in plan['比較']},
                   '課題別':results,'最終checkpoint':{m:str(v) for m,v in states.items()}}
        保存(args.出力 / '集計.json', summary)

if __name__ == '__main__':
    main()
