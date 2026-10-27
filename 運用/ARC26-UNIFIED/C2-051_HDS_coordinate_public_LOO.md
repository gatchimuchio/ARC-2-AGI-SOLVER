# C2-051 — HDS coordinate-conditioned public LOO

## 仮説

一部の同形格子変換では出力色が入力セル色と位置で決まり、近傍色数や行・列色数を使わずにHDSが少数の座標条件から規則を学べる可能性がある。C2-049/050では色ベクトル特徴が重く、pilot中に完全候補格子を確認できなかったため、今回は中心色とzero-based行・列indexの3特徴に限定する。

問題ID・ファイル名・hashによる答え分岐、answer map、held-out出力、hidden/evaluation正解のruntime使用は禁止。

## 比較条件

- C2-045と同じ公開training母集団、source除外、入力重複除外、LOO順序とbaselineを使う。
- HDS connector、support=3、最大条件数=2、候補選択を固定する。
- HDSが全セルで一意な予測を返した完全格子だけを候補扱いし、fallback/HOLDは正答に数えない。
- held-out出力はsolver return後にparent evaluatorが採点する。

## 実行ゲート

1. 先頭4適格課題のpilotを行い、baseline一致、fold数、完全候補格子、second exact/wrong、union exact、fallback、実時間を確認する。
2. 5分のpilot資源上限で未完なら中断記録を残し、性能結論を出さない。
3. pilot完了後も完全候補格子0またはunion exact増加0なら全件LOOへ拡大しない。
4. 改善信号がある場合だけ全適格母集団LOOを実施し、previous/current/deltaと退行を示す。
5. 全LOOと回帰で改善確認されるまで本番solver・提出へ採用しない。

## 生成物

- 実験: `運用/証拠/ARC26-UNIFIED/P5_HDS_coordinate_LOO.py`
- pilot/full JSONは新規作成し、既存証拠を上書きしない。
