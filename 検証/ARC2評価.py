"""固定公式120課題を旧ARC採点器で評価。正解は親評価過程だけに置く。"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

ルート = Path(__file__).resolve().parents[1]


def runtime(モード):
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (10, 11))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    sys.path[:0] = [str(ルート), str(ルート / 'HDS/学習系統/v0.4.2')]
    from 接続.ARC2.HDS接続 import 課題を解く, 事前教材を読む, 格子観測, 出力格子
    from hds学習系統 import HDS学習実行系
    課題 = json.load(sys.stdin)
    if set(課題) != {'train', 'test'} or any(set(対) != {'input'} for 対 in 課題['test']):
        raise ValueError('runtimeへ課題識別子・test正解を渡してはならない')
    try:
        if モード == 'current':
            結果 = 課題を解く(課題, 事前教材を読む())
        else:
            機械 = HDS学習実行系()
            for 対 in 課題['train']:
                機械.実行(格子観測(対))
            結果 = {'results': [出力格子(機械, 格子観測(対)) for 対 in 課題['test']]}
        print(json.dumps(結果, ensure_ascii=False))
    except MemoryError:
        print(json.dumps({'error': 'memory_limit'}))


def 主処理():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('baseline', 'current'), default='current')
    parser.add_argument('--runtime', choices=('baseline', 'current'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.runtime:
        runtime(args.runtime)
        return
    import 既存ARC2採点 as 採点
    challenges, solutions = {}, {}
    source = ルート / '入力/公式ソース/ARC-AGI-2/data/evaluation'
    for file in sorted(source.glob('*.json')):
        原本 = json.loads(file.read_text())
        challenges[file.stem] = {'train': 原本['train'],
                                 'test': [{'input': p['input']} for p in 原本['test']]}
        solutions[file.stem] = [p['output'] for p in 原本['test']]
    if len(challenges) != 120:
        raise RuntimeError('固定公式evaluation 120課題が必要。公式source submoduleを初期化すること')

    def 実行(課題):
        try:
            p = subprocess.run([sys.executable, __file__, '--runtime', args.mode],
                               input=json.dumps(課題), text=True, capture_output=True, timeout=60)
            if p.returncode:
                return {'error': 'cpu_limit' if p.returncode == -24 else
                        'unknown_kill' if p.returncode == -9 else 'runtime_exit',
                        'returncode': p.returncode, 'stderr': p.stderr[-400:]}
            return json.loads(p.stdout)
        except subprocess.TimeoutExpired:
            return {'error': 'wall_limit'}

    開始 = time.monotonic()
    課題一覧, 記録 = sorted(challenges.items()), []
    with ThreadPoolExecutor(max_workers=3) as pool:
        待機 = iter(zip(課題一覧, pool.map(実行, [t for _, t in 課題一覧])))

        def solve_task(課題):
            (識別子, 元課題), 結果 = next(待機)
            assert 課題 is 元課題
            予測 = 結果.get('results', [{'answer': None} for _ in 課題['test']])
            assert len(予測) == len(課題['test'])
            結果.update(task_id=識別子, test_count=len(課題['test']),
                        unanswered=sum(p.get('answer') is None for p in 予測),
                        correct_examples=sum(p.get('answer') == y
                                             for p, y in zip(予測, solutions[識別子])))
            記録.append(結果)
            return SimpleNamespace(predictions=[SimpleNamespace(attempts=[] if p.get('answer') is None
                else [SimpleNamespace(output=p['answer'], source='HDS', component='HDSv0.4.2')])
                for p in 予測])

        # 元採点関数のsolver境界だけを現在のHDS subprocessへ接続する。
        採点.solve_task = solve_task
        元採点 = 採点.evaluate_solver_core(challenges, solutions)
    要約 = {
        'mode': args.mode, 'tasks': len(challenges),
        'test_examples': sum(p['test_count'] for p in 記録),
        'correct_tasks': 元採点['solved_count'], 'accuracy': 元採点['score'],
        'correct_examples': sum(p['correct_examples'] for p in 記録),
        'unanswered': sum(p['unanswered'] for p in 記録),
        'wrong_attempted_tasks': len(元採点['wrong_attempted_task_ids']),
        'resource_failures': dict(Counter(p['error'] for p in 記録 if 'error' in p)),
        'seconds': time.monotonic() - 開始,
        'challenge_sha256': hashlib.sha256(json.dumps(challenges).encode()).hexdigest(),
        'solutions_sha256': hashlib.sha256(json.dumps(solutions).encode()).hexdigest(),
        'cpu_seconds_per_task': 10, 'address_space_mib': 512,
        'wall_seconds_per_task': 60, 'workers': 3,
    }
    if args.output:
        args.output.write_text(json.dumps({'summary': 要約, 'original_audit': 元採点,
                                          'execution': 記録}, ensure_ascii=False, indent=2))
    print(json.dumps(要約, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    主処理()
