# C2-048: HDS exact 3x3 neighborhood patch public-training LOO

## 根拠と仮説

- 直近のARC2公式提出57576155はCOMPLETE / public_score 0.00。P5で公開training限定の一般的なHDS機構を検討する。
- C2-047の近傍色数表現は4課題・19 foldのpilotで完成候補0。経路診断では出力色に関係する隔離原理も観測され、色数への圧縮が曖昧な関係を残す仮説がある。
- 新仮説: 各セルの位置に依存しない正確な3x3 patch（格子外はsentinel -1）を一つの観測値として出力色に結び、teacher gridごとに重複を除いてHDSへ与える。複数teacherで再現するpatch-to-colorだけを使う。
- task ID/hash、絶対座標、answer map、hidden/evaluation正解を使わない。出力色経路に未確定/係争/競合/追加観測が残る、未知のセルがある、または格子の一部しか構成できない場合は候補格子全体を拒否する。

## 比較条件

- Baseline: C2-045 previous_no_prior。現行connector、同じ公開training manifestと事前教材重複除外。
- Candidate: 独立した汎用HDS engine。min_support=3、max_conditions=2。heldout outputは親評価器のみがsolver返却後に採点。
- fallbackは正解に数えない。課題ID、格子、回答、fold別結果はartifactへ書かない。

## 実行順・採否

1. 対象populationの先頭4 eligible課題（19 fold）でAPI/保留・係争処理/候補成立/負荷を確認。pilotは全体性能の主張に使わない。
2. 5課題目を含む先行pilotは10分超の処理で中断したため、追加task数を増やさない。4課題pilotの実測で全件実行が現実的か判断。
3. 267課題・1,191 foldのfull LOOは、pilotでunion exact増加、second wrong増加なし、regressionなし、runtimeが許容可能な場合のみ実施。
4. baseline再測定がC2-045 full metricsと一致しない場合は比較を無効として調査。改善未実証ならproduction・submission candidate・Kaggle notebookを変更しない。

## 保護

公開trainingのみ。submission、Competition Rerun、Notebook pushを行わない。AGENTS.mdと制御/現在状態.jsonは変更しない。
