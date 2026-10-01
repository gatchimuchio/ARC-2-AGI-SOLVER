"""固定公開教材の有界実験。CPUのみ、ネットワーク・API・課題別分岐なし。"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time
from .HDS接続 import HDS学習機械, 目的, 正規化, 実装署名
from .教師 import 公開教材, 教師


def 実験する(content, 最大セル数=36, 最大学習経験=8, 学習有効=True, 最小支持数=3, 学習機械=None, 観測表現='座標辞書', 数量関係有効=True, 添字関係有効=True):
    material = 公開教材(content)
    teacher = 教師(material)
    learner = 学習機械 if 学習機械 is not None else HDS学習機械(最大セル数, 最小支持数, 学習有効, 観測表現, 数量関係有効, 添字関係有効)
    frozen_revision = 実装署名()
    initial = learner.概況()
    # 評価は完全非学習。全てのtrainを経験にする前の初期能力を同じtestで測る。
    before = [teacher.評価(learner, 'test', i)[1].正解 for i in range(material.件数('test'))]
    curve = []
    for i in range(min(material.件数('train'), 最大学習経験)):
        pred, outcome = teacher.評価(learner, 'train', i)
        update = teacher.教示(learner, i)
        # 同じtrain例での再試行は未知例の得点には算入しない。
        heldout = [teacher.評価(learner, 'test', j)[1].正解 for j in range(material.件数('test'))]
        retry, retry_outcome = teacher.評価(learner, 'train', i)
        curve.append({'経験位置': i, '提示前正解': outcome.正解, '提示前状態': pred.状態,
                      '更新採否': update['採否'], '再試行正解': retry_outcome.正解, '非学習test正解数': sum(heldout),
                      '学習状態': learner.概況()})
    final_before_eval = learner.状態署名()
    after = [teacher.評価(learner, 'test', i)[1].正解 for i in range(material.件数('test'))]
    assert learner.状態署名() == final_before_eval
    # 記憶除去対照: 同一実装・予算で新しい機械へ置換。test正解は渡さない。
    erased = HDS学習機械(最大セル数, 最小支持数, 観測表現=learner.観測表現, 数量関係有効=learner.系.エンジン.数量関係有効, 添字関係有効=learner.系.エンジン.添字関係有効)
    ablated = [teacher.評価(erased, 'test', i)[1].正解 for i in range(material.件数('test'))]
    if 実装署名() != frozen_revision:
        raise RuntimeError('実験中に機械実装が変更された')
    result = {'実装署名': frozen_revision, '目的': 目的, '範囲': 'ARCリポジトリの専用HDS学習機械',
              '初期': initial, '終了': learner.概況(),
              '学習曲線': curve, '評価例数': len(after),
              'previous': sum(before), 'current': sum(after), 'delta': sum(after) - sum(before),
              '記憶除去': sum(ablated), '学習有効': 学習有効,
              '未提示評価例': 'test出力は全段階で教師のみ保持。testによる更新なし',
              '課題間転用': '同一機械保持。前課題で採用した関係を現在2独立観測で再検証して暫定転用',
              '試行回数': {'学習前評価': len(before), 'train提示前': len(curve),
                           'train再試行': len(curve), '学習曲線test照会': len(curve) * len(before), '学習後評価': len(after), '記憶除去評価': len(ablated)},
              '履歴': teacher.履歴}
    return result, learner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--教材', type=Path, required=True, help='固定版のdata/trainingディレクトリ')
    parser.add_argument('--固定表', type=Path, default=Path(__file__).resolve().parents[2] / '検証/学習環境/教材固定.json')
    parser.add_argument('--出力', type=Path, default=Path('出力/学習環境'))
    parser.add_argument('--問題数', type=int, default=8)
    parser.add_argument('--最大セル数', type=int, default=36)
    parser.add_argument('--最大学習経験', type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.問題数 <= 16 or not 1 <= args.最大学習経験 <= 16:
        parser.error('有界実験は問題数・経験数とも1..16')
    manifest = json.loads(args.固定表.read_text(encoding='utf-8'))
    expected = manifest['教材'][:args.問題数]
    paths = [args.教材 / x['ファイル'] for x in expected]
    if any(not p.is_file() for p in paths):
        parser.error('固定表の教材がない。公開source固定版を展開してください')
    if [p.name for p in paths] != [x['ファイル'] for x in expected] or len(paths) != args.問題数:
        parser.error('教材集合が固定表と不一致')
    for path, row in zip(paths, expected):
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['SHA256']:
            parser.error('公開教材のSHA256が固定表と不一致: ' + path.name)
    args.出力.mkdir(parents=True, exist_ok=True)
    reports = []
    learner = HDS学習機械(args.最大セル数)
    for position, path in enumerate(paths):
        content = json.loads(path.read_text(encoding='utf-8'))
        started = time.monotonic()
        if position:
            learner.新しい課題()
        report, learner = 実験する(content, args.最大セル数, args.最大学習経験, 学習機械=learner)
        reset_report, _ = 実験する(content, args.最大セル数, args.最大学習経験)
        report['課題毎初期化対照'] = {k: reset_report[k] for k in ('previous', 'current', '学習曲線')}
        report['保持対初期化差'] = report['current'] - reset_report['current']
        # 名前は教師側の出典にのみ存在し、HDSの入力・境界・目的には渡さない。
        report['出典ファイル'] = path.name
        report['教材SHA256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        report['経過秒'] = round(time.monotonic() - started, 3)
        dest = args.出力 / path.stem
        dest.mkdir(parents=True, exist_ok=True)
        report['状態追跡'] = '最終checkpointのHDS台帳・経験参照・原理参照と各段階の状態署名で追跡'
        (dest / '教師履歴.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        reports.append({k: v for k, v in report.items() if k not in {'履歴', '学習曲線'}})
    learner.保存する(args.出力 / '最終checkpoint')
    summary = {'形式版': 1, '実装署名': 実装署名(), '教材source': manifest['公式ソース'], '選択規則': manifest['選択'],
               '固定予算': {'問題数': args.問題数, '最大セル数': args.最大セル数, '最大学習経験': args.最大学習経験},
               '問題数': len(reports), '評価例数': sum(r['評価例数'] for r in reports),
               'previous': sum(r['previous'] for r in reports), 'current': sum(r['current'] for r in reports),
               '記憶除去': sum(r['記憶除去'] for r in reports),
               '課題毎初期化': sum(r['課題毎初期化対照']['current'] for r in reports),
               '保持対初期化差': sum(r['保持対初期化差'] for r in reports),
               '問題別': reports,
               '制限': ['公開training部分集合の局所実験。ARC-AGI-2評価セットの得点ではない',
                        '対象はリポジトリ専用HDS。外部ミニドラはこの実験の対象外', '固定位置転用は同一形状。構造一般候補は型範囲と新境界の再検証。因果法則ではない',
                        '初期/後評価を同じtestで比較するが、照会は状態不変・正解非開示',
                        'セル予算超過はHOLD。計算対象から黙って除外しない']}
    summary['delta'] = summary['current'] - summary['previous']
    (args.出力 / '集計.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != '問題別'}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
