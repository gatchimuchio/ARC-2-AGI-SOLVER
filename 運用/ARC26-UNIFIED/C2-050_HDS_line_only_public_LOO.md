# C2-050 — HDS row/column-count public LOO

## 仮説

出力色は、セル自身の色と、そのセルが属する行・列の色数で決まる汎用規則を持つ場合がある。C2-047の局所近傍特徴へ行・列特徴を足したC2-049は、4課題pilotの2課題目を処理中に15分上限へ達し、5fold時点で完全候補格子0だった。C2-049は未完了のため性能判定に使わない。

C2-050では候補器の探索量を抑えるため、入力特徴を中心色・行色数・列色数の3種類に限定する。問題ID・ファイル名・hash分岐、answer map、held-out出力・hidden/evaluation正解の利用は禁止。

## 比較条件

- C2-045と同じ公開training母集団、source除外、入力重複除外、LOO順序、baselineを使う。
- HDS connector、support=3、最大条件数=2、候補選択は固定する。
- 候補は全セルに一意なHDS出力がある完全格子だけ。fallback/HOLDは正答に数えない。
- candidate solverには教師例とheld-out入力だけを渡し、held-out出力はreturn後にparent evaluatorが採点する。

## 実行ゲート

1. 先頭4適格課題のpilotを行い、baselineがC2-045と一致すること、fold数、完全候補数、exact/wrong/fallback、実時間を確認する。
2. 完全候補格子0かつunion exact増加0なら全件実行へ拡大しない。
3. 改善信号がある場合だけ全適格母集団LOOを行い、previous/current/deltaと退行を示す。
4. 全LOOと回帰で改善が確認されるまで本番solver・提出には採用しない。

## 生成物

- 実験: `運用/証拠/ARC26-UNIFIED/P5_HDS_line_only_LOO.py`
- pilot/full JSONは新規作成し、既存証拠を上書きしない。
