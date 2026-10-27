# ARC2 P3 観測追加実験の独立監査

監査記録: 2026-10-26T22:12:27Z。ファイル読取と保存済み結果の集計だけを行い、solver・評価jobは実行していない。solver、台帳、checkpointは変更していない。

## 判定

現在の提出workerを使った `A → A+[F]` のbatch refit比較は成立している。追加したFへの教師適合は確認できるが、このcohortで未見Uへの性能改善は未実証である。

| 観測 | 追加前 | 追加後 | 差分 |
|---|---:|---:|---:|
| 未見U pass@1 | 2/20 | 2/20 | 0 |
| 未見U pass@2 | 2/20 | 2/20 | 0、回復0・退行0 |
| F pass@1 / pass@2 | 1/20 | 20/20 | 19件が教師適合へ変化 |
| U primary fallback | 18/20 | 18/20 | 0 |
| Uの異なる2候補 | 3/20 | 3/20 | 0 |
| 第二候補によるU追加正解 | 0 | 0 | 0 |

- 20課題すべてbefore/after COMPLETE。requested=processed=paired complete=20、不完了pair=0。cohortは20の異なる課題、seedは20261026。
- Uの実attempt pair SHAは20/20で同一。Fの実attempt pair SHAは19/20で変化した。
- HDS semantic rule SHAは20/20で変化した。一方、境界・関係型・条件/結果経路・状態・採用状態からなる構造signatureは20/20で不変。
- 全43原理のmapping digestと支持証拠数が変化したが、原理構造の追加・削除はない。採用family集合も20/20で不変。
- 原理構造は、20件のraw入力→出力対応、19件の逆対応、既存2familyの同値関係4件。U正解のtask index 5/8はそれぞれ `ARC特徴近傍変換選択` / `ARC周期タイルD4反復` で、追加前から同じfamilyが採用されていた。

## データフローと採点

- 実験script `ARC2-P3-observation-update.py:275` で予測前にcohortを保存。task IDは親のprovenance・prior漏洩除外にだけ使う。
- `:305` は `b = a + [feedback]`。`:308` のbeforeにはAとinput-onlyの `[F,U]`、`:310` のafterにはA+[F]と同じtest入力順を送る。U正解はworkerへ渡さない。
- `:112` で同じ検査済みpriorを注入し、`:146` の `Kaggle提出._worker` と `:156` の `結果を候補へ` を再利用する。候補pool内のoracle正解数ではなく、実際のattempt_1/attempt_2を採点する。
- `:199` の採点はattempt単位で入力コピーfallbackを除外する。primaryがfallbackでも、異なる実生成attempt_2の正答は残る。
- `:224` で予測gridを保存前に除去。semantic mappingはdigestだけを保存し、診断は数値/count辞書へ限定される。保存JSONLのschema確認・再帰走査で生の数値grid行列は0件。
- このseedの20課題について、U/F入力とA・有効priorの入力衝突は0件。Aには各課題3件以上の一意な教師対がある。
- 記録された開始/終了source照合は一致し、監査時のscript SHAも記録値と一致した。

## なぜFには適合し、Uは変わらなかったか

`接続/ARC2/HDS接続.py:166,275` は公開教師のraw入力・出力をHDSへ観測として渡す。`HDS/学習系統/v0.4.2/hds学習系統/適応.py:136–145` は既知条件値を対応表から予測し、未知条件値には追加観測を要求する。

Fを追加するとFの入力は教師対応表の既知値になる。今回の記録では支持・対応表は拡張されたが、汎用原理の構造や採用familyは増えず、Uのattempt pairも全件不変だった。これはFへの教師適合と整合し、Uへの一般化改善の証拠にはならない。

## 範囲・制約

- 公開training 1000課題のうち、教師対5件以上のeligible 78課題からseed固定で選んだ20課題だけを評価した。全公開課題・hidden・公式scoreの推定値にはしない。
- 追加前後で同じ現行local solverと提出選択policyを使用したbatch refitであり、永続的なincremental学習やfresh processでの学習済み記憶保持は実証していない。
- F追加後の20/20はtraining fitであり未見得点ではない。fallbackを正答に含めていない。
- 1phase90秒のwall timeoutのみ。WindowsのCPU/RAM隔離はない。
- 現行checkoutの実験であり、凍結済みKaggle v61 runnerの同等性を自動的には示さない。

## SHA-256

| ファイル | SHA-256 |
|---|---|
| `運用/証拠/ARC26-UNIFIED/ARC2-P3-observation-update.py` | `14fe5c0d0ef2dce2cae69343309b6a6f45e50262499b497e15c1e2e55ec64621` |
| `出力/検証/ARC2-P3-observation-update-20task-20261026T2204Z.jsonl` | `6f9e92d47a0899844c54fd50105a26cf22a0ce2168de1348cc9f6567284b7537` |
| `出力/検証/ARC2-P3-observation-update-20task-20261026T2204Z.summary.json` | `e179b5cc9d6d6d2a4625d5c753fd4c5be5d26b24c9387eeab63774050dd9096f` |
| `出力/検証/ARC2-P3-observation-update-20task-20261026T2204Z.cohort.json` | `26471467dbcfefc2697c49ff1632828bba886a2359071564293449e1dec77e6d` |

run内のsource tree記録: ARC2 connector 268 files `bad27978299932c1521c81d4e4a05b0c4597a2bc10359bf8a9f594153dd0ecfd`、HDS 12 files `5b0b377bfad4b5100459fa32198f79214dcd436ee10a426257c2b25eb20b1c14`。

## 再実行比較

`ARC2-P3-observation-update-20task-repeat-20261026T2210Z` は22:12:27Zの読取時点で13課題の行出力、summary未生成だった。終端前の部分結果を再現成立とは扱わない。終端確認後にcohort、実U/F予測hash、semantic stateを比較する。

### 再実行の終端確認と比較

再実行は2026-10-26T22:14:07.907291Zに終端COMPLETE。20/20 paired COMPLETE、不完了0、source開始/終了照合一致。U pass@1/pass@2は再び2→2、回復0・退行0、F追加後training fitは20/20だった。

- cohort manifestは内容・byteとも完全一致。同じ20課題・同じU/F選択である。
- before/after × F/U × 20課題の実attempt pair SHAは **80/80一致**。採点辞書も80/80一致。
- HDS初期state配列、最終semantic state配列、family記録、数値/count診断はそれぞれ **40/40一致**。
- 比較した決定的な出力・stateに差分は0件。記録時刻・所要時間は一致条件に含めないため、JSONL全体のbyte hashは異なる。
- 再実行JSONLでも生の数値grid行列は0件。scriptの現在SHAも記録された `14fe5c…` と一致する。

このcohort・同一版では「Fへの教師適合は増えるが、Uの出力も未見得点も変化しない」という負のP3結果が再現した。学習効果の成立とは扱わない。

| 再実行ファイル | SHA-256 |
|---|---|
| `出力/検証/ARC2-P3-observation-update-20task-repeat-20261026T2210Z.jsonl` | `0b18d6108dc639d313b4e44809584f2c1229870320099f9f3246622a1373c9b3` |
| `出力/検証/ARC2-P3-observation-update-20task-repeat-20261026T2210Z.summary.json` | `3e7389d9ce1ce6056189dd52b4491c690db3dee8e8a40473bb93f7bdbcb0357f` |
| `出力/検証/ARC2-P3-observation-update-20task-repeat-20261026T2210Z.cohort.json` | `26471467dbcfefc2697c49ff1632828bba886a2359071564293449e1dec77e6d` |
