# HDS・テンプレート穴充填

現行HDSを一つ使用し、旧ARC資産の入力専用充填候補を学習・検証・排気へ接続する。固定training教材2観測と現在の教師観測を公開学習経路へ渡し、全教師対の再現、採用済み同値原理、既存排気gateが揃う場合だけ出力する。候補が複数、不足、反例、隔離、支持不足の場合は推測で埋めない。

固定公式source submoduleが必要。単一課題JSONはtrain教師対とtest入力だけを含める。

```sh
PYTHONPATH="HDS/学習系統/v0.4.2" python -m 接続.ARC2.HDS接続 < 課題.json
python 検証/ARC2評価.py --mode baseline --output /tmp/arc2-baseline.json
python 検証/ARC2評価.py --mode current --output /tmp/arc2-current.json
python 検証/テンプレート充填回帰.py
```

評価は旧ARC採点関数を再利用する全120課題・167test例、各課題10CPU秒・512MiB・60秒wall、3並列。baselineは既存HDSの格子値観測だけ。test正解と課題IDは親採点側に限定する。

公開source評価は0→1/120課題、0→2/167例。既存資産の適用例を含む公開評価であり、hidden・競技満点・Kaggle提出を示すものではない。固定source evaluationのSHA256は既存ZIPマニフェストと不一致であり、source版として評価する。正確な条件は `検証/テンプレート充填比較.json` に記録する。
