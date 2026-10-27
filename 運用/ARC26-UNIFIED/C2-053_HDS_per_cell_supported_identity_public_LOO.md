# C2-053 — HDS per-cell supported identity public LOO

## 仮説

C2-052は4適格課題・19foldで候補格子を作れなかった。出力不明セルのうち、教師例の全てで同じ座標の入力色と出力色が一致するセルは、少なくとも3件の独立な教師例に支えられたidentity規則として保持できる可能性がある。

これはfallbackを正答扱いすることではない。各セルをHDS予測、または教師データで支持されたidentity予測で埋め、完成した格子だけをheld-out出力に対してexact採点する。問題ID・ファイル名・hash分岐、answer map、held-out出力、hidden/evaluation正解のruntime使用は禁止。

## 比較条件

- C2-052と同じper-cell HDS、公開training母集団、source除外、入力重複除外、LOO順序を使用。
- HDS support=3、最大条件数=2。座標に対応するteacher数が3未満ならHOLD。
- identity fillは、同じ座標にある全teacher例で入力色と出力色が一致し、かつ出力色経路の係争・競合がない場合だけ許可。
- HDS予測とidentity予測の両方で完全格子を構成できた場合だけ候補を返す。未予測セルはfallbackで埋めない。
- held-out出力はsolver return後にparent evaluatorが採点する。

## 実行ゲート

1. 先頭4適格課題・19fold相当のpilotを行い、C2-052 baseline一致、candidate exact/wrong/fallback、identityセル数、実時間を確認する。資源上限は5分。
2. pilotが未完、完全候補格子0、またはunion exact増加0なら全件LOOへ拡大しない。
3. 改善信号があれば全適格母集団LOOでprevious/current/deltaと退行を確認する。
4. 全LOOと回帰で改善が確認されるまで本番solver・提出へ採用しない。

## 生成物

- 実験: `運用/証拠/ARC26-UNIFIED/P5_HDS_per_cell_identity_LOO.py`
- pilot/full JSONは新規作成し、既存証拠を上書きしない。
