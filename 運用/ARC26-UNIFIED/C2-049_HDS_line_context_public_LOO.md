# C2-049 — HDS line-context public LOO

## 仮説

C2-047の近傍特徴だけでは、異なる出力色を持つ局所パターンが同じ特徴へ衝突し、HDSが予測を保留する場合がある。入力グリッドから得る行・列ごとの10色カウントを追加すれば、行列構造に沿う汎用規則で一部の衝突を解消できる可能性がある。

問題ID・ファイル名・hashに基づく分岐は行わない。出力色・正解格子・held-out出力は学習・候補生成へ渡さない。

## 比較条件

- C2-045と同じ公開training母集団、source除外、入力重複除外、LOO手順を使う。
- C2-047から変えるのは入力特徴だけ。既存のHDS connector、support=3、最大条件数=2、候補選択とbaselineは固定する。
- 候補はHDSが全セルで一意な出力色を返した格子だけ。fallback/HOLDは正答に数えない。
- held-out出力はcandidate solverのreturn後にparent evaluatorが採点する。

## 実行ゲート

1. まず同じ先頭4適格課題のpilotを行い、baseline再計測がC2-045と一致すること、完了fold数、完全候補格子数、exact/wrong/fallback、実時間を確認する。
2. pilotで完全候補格子もunion exact増加もなければ停止し、仮説を不採用とする。
3. pilotに改善信号がある場合だけ、全適格母集団でLOOを行い、previous/current/delta、退行、fallback/wrong、時間を報告する。
4. 全LOOと回帰で改善が確認されるまで本番solver・提出は変更しない。

## 生成物

- 実験: `運用/証拠/ARC26-UNIFIED/P5_HDS_line_context_LOO.py`
- pilot/fullの証拠JSONは実行ごとに新規作成し、既存ファイルを上書きしない。
