# HDS・既存機構接続

一つの現行HDSへ、既存のテンプレート穴充填・入れ子パネル合成・閉領域パレット転写の入力専用候補を接続する。充填だけに固定training教材2観測を渡し、入れ子合成・領域転写へ別機構の証拠を混ぜない。全教師再現・採用済み同値原理・既存排気gateが揃う場合だけ出力する。学習後に候補を照会し、採用機構の競合や未確定候補はHOLDとする。

ARCの教師が「異なる入力の二例ちょうど」の場合、呼出側が最小支持数2を設定する。それ以外は3。これは課題全体の証拠要件を3→2へ緩める変更であり、二例での推論確実性が強くなったとの主張ではない。HDS中核の既定値3・検証・反例隔離・排気処理は変更しない。

固定公式source submoduleが必要。単一課題JSONはtrain教師対とtest入力だけを含める。

```sh
PYTHONPATH="HDS/学習系統/v0.4.2" python -m 接続.ARC2.HDS接続 < 課題.json
python 検証/ARC2評価.py --mode baseline --output /tmp/arc2-baseline.json
python 検証/ARC2評価.py --mode current --output /tmp/arc2-current.json
python 検証/テンプレート充填回帰.py
python 検証/入れ子合成回帰.py
python 検証/領域転写回帰.py
```

全120課題・167test例、各課題10CPU秒・512MiB・60秒wall、3並列で旧ARC採点関数を再利用する。baselineモードは初期のHDS格子値診断であり、前commitそのものではない。test正解と課題IDは親採点側に限定する。

前commit `ac0cc8c` の2/120課題・3/167例から、領域転写接続で3/120課題・5/167例へ改善。正確な比較は `検証/領域転写比較.json`。先行成果は `検証/入れ子合成比較.json` と `検証/テンプレート充填比較.json` に記録する。

公開評価での改善であり、既存helperの過去開発データから独立な評価・hidden汎化・満点・Kaggle提出を示さない。固定source evaluationのSHA256は既存ZIPマニフェストと不一致であり、source版として評価する。
