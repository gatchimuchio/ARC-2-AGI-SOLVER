# ARC2 C2-045 実行記録: 承認済み事前記憶を含む漏洩除外LOO比較

- 実行時刻: 2026-10-24 12:57:55 UTC
- 指示: `運用/ARC26-UNIFIED/C2-045_事前記憶を含む漏洩除外LOO比較.md`
- 適用正本: ARC26 共通3点セット v3.0
- データ: 公開 ARC-AGI-2 training split のみ
- 条件: 同じ現行HDS connectorと同じLOO foldで、previousは事前記憶なし、currentは承認済みtraining priorを2例使用
- 事前記憶参照 SHA-256: `8f5f24571f0457c44af68b57b9aebbcf4dabbb9164f24942108e1b98f635f112`
- training manifest SHA-256: `10a0146ab6374f18f44a770b37154ccb6d579fddb9a321eb3bf936666bc85aa8`
- HDS connector SHA-256: `d1b31e1c39aac62e99b86a1bbf267725e5306a13f54fced6690e67e133345f55`

## 漏洩ガードと対象範囲

ソース課題IDとprior入力格子との重複を各公開training課題で検査し、条件間で同一の eligible task/fold 集合を使用した。除外数はソース課題0、入力重複課題0、対象267課題・1,191 fold。各foldでheldout出力をsolver入力から外し、solver返却後に親評価器だけで採点した。hidden/evaluation解答は読まず、課題ID・格子を証拠へ保存していない。fallbackは初回正答に含めていない。

## 結果

| 指標（1,191 fold） | previous: priorなし | current: prior 2例 | current - previous |
|---|---:|---:|---:|
| 初回の有効解答 | 16 | 16 | 0 |
| 初回完全一致 | 16 | 16 | 0 |
| 初回誤答 | 0 | 0 | 0 |
| distinct second候補 | 1 | 1 | 0 |
| second完全一致 | 1 | 1 | 0 |
| second誤答 | 0 | 0 | 0 |
| union完全一致 | 17 | 17 | 0 |
| fallback | 1,175 | 1,175 | 0 |

条件別solver実行時間はprevious 1,671.145秒、current 1,681.920秒、差 +10.776秒（+0.645%）。

## 判定

承認済みprior 2例による正答・候補数の改善は観測されず、実行時間はわずかに増えた。したがって観測専用・改善未実証とし、production solverや提出物を変更せず、Kaggle提出も行っていない。

## 機械証拠

- 集計JSON: `運用/証拠/ARC26-UNIFIED/P5_prior_memory_leakage_guard_LOO.json`
- 集計JSON SHA-256: `35eb1723ddd2537f4243aa1cb4d8d2a2257fa095d0bb0feb6c94f0a3cc61e9b0`
- 実行script SHA-256: `46dc81b724893b2a0dc3dd9d9894fb4ee04aae4a6b9a4c4a4301c9ba2727315f`
- 集計検査: 対象数、fold数、条件別指標一致、全deltaゼロ、漏洩ガード、fallback除外、hidden/evaluation未読、production未変更を確認
