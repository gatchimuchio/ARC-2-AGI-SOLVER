# C2-052 — HDS per-cell local public LOO

## 仮説

C2-047は全教師セルを1つのHDS relation poolへ入れた。座標の異なるセルの対応が同じpoolで競合し、無関係な出力色原理まで同時に隔離されている可能性がある。各出力座標に独立したHDS learnerを用意し、その座標のteacherセルだけで学習すれば、空間位置ごとの対応を分離できる可能性がある。

特徴はC2-047と同じ入力由来の中心色・半径1近傍色数・境界数。問題ID・ファイル名・hash分岐、answer map、held-out出力、hidden/evaluation正解のruntime使用は禁止。

## 比較条件

- C2-045と同じ公開training母集団、source除外、入力重複除外、LOO順序、baselineを使う。
- 各座標のHDSはsupport=3、最大条件数=2。教師例が3件未満の座標は即HOLD。
- 各セルの候補は出力色経路に一意な予測があり、出力色経路に追加観測要求・係争・競合がない場合だけ採用する。
- 全セルが確定した格子だけを候補扱いし、fallback/HOLDは正答に数えない。
- held-out出力はsolver return後にparent evaluatorが採点する。

## 実行ゲート

1. 先頭4適格課題でpilotを行い、baseline一致、fold数、complete candidate grids、exact/wrong/fallback、teacher support不足数、実時間を確認する。資源上限は5分。
2. pilot未完、完全候補格子0、またはunion exact増加0なら全件LOOへ拡大しない。
3. 改善信号がある場合だけ全適格母集団LOOを実行し、previous/current/deltaと退行を示す。
4. 全LOOと回帰で改善確認されるまで本番solver・提出へ採用しない。

## 生成物

- 実験: `運用/証拠/ARC26-UNIFIED/P5_HDS_per_cell_LOO.py`
- pilot/full JSONは新規作成し、既存証拠を上書きしない。
