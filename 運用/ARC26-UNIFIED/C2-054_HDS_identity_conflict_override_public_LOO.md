# C2-054: 教師合意identityによるHDS競合上書き候補

## 仮説

各出力座標について、公開trainingの全教師例（最低3件）で入力色と出力色が一致している場合、その座標のidentityを予測候補として使う。C2-053ではHDSのoutput-color係争・競合を理由に一部セルが候補から除外されたため、本試行では教師合意identityがその係争・競合を上書きできるかを調べる。上書き数を独立に記録する。

## 条件と制約

- 公開trainingのteacher pairsだけで学習し、held-out inputだけをsolverへ渡す。
- held-out outputはsolverのreturn後に親評価器が採点する。
- per-cell HDS、`min_support=3`、`max_conditions=2`、近傍色数特徴はC2-053と同条件。
- 合意identityは同じ座標の全teacherで入力色=出力色の場合にだけ許可する。
- 候補は完全な予測gridとして評価し、fallbackを正答に数えない。
- 問題ID・hashによる分岐、answer map、hidden/evaluation正解のruntime使用は禁止。
- まず適格4 taskのpilotを最大5分実行する。pilotで完全grid・exact改善が出なければfull LOOへ拡張しない。
- production solver、Notebook、submission、公式提出は変更しない。

## 成立判定

baseline/current/deltaと、完全grid数、exact/wrong、identity override件数を比較する。改善が未実証なら候補を採用しない。baselineはC2-053と同じ評価対象とするが、過去pilotのbaseline値は部分pilotであり、全対象との同一条件値として扱わない。
