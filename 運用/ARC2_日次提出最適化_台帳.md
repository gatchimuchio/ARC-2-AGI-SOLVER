# ARC2 日次提出最適化台帳

- 適用正本: [2026-10-23 v1.1 現行正本](ARC2_初回Kaggle提出_現行正本.md)
- Owner指示ID: `ARC2-DAILY-OPTIMIZATION-20261023`
- 次に再開する工程: M5 原因分析・汎用改善・同条件比較
- 最終提出期限（正本記載）: 2026-11-02 23:59 UTC。実際の最新Kaggle画面/APIを各日に確認する。

## 現在状態 — 2026-10-23

| 工程 | 判定 | 根拠 |
| --- | --- | --- |
| M0 基準点固定 | PASS | 作業開始時のHEADとorigin/mainはともに `ba4ec6e4131bff174d41ef1bb2909ed652d7bdae`。開始前は `main` がcleanで、添付保管ディレクトリだけが未追跡。今回の指示・仕様・工程は添付原文のSHAと一致。 |
| M1 現行資産の再現 | PASS（既存測定） | 運用報告の同条件実測: 240課題・259 test、909.109秒。258件はHDS HOLD fallbackで正答ではない。 |
| M2 Kaggle結合 | PASS（v2） | Kaggle Notebook `tecchannn/arc2-codex-main-baseline-v1` v2 は現行版、状態COMPLETE。Internet OFF/CPU、実行283.265秒。提出出力240課題・259 test、2候補/test、SHA-256 `a0eeaaa6203d4fdd049f8aa705a8ac7832cb98240759703eb0288ad3d62b4927`。 |
| M3 公式提出 | PASS / 受理・採点完了 | Notebook v2の提出ref `57560705`。Kaggle履歴でstatus `COMPLETE`、public_score `0.00`、失敗詳細なしを確認。 |
| M4 score・経路固定 | PASS | Notebook v2 → `submission.json`（SHA `a0ee…4927`）→ ref `57560705` → 公式public score `0.00`。版、出力、受理、採点状態を証跡に固定。 |
| M5 日次反復 | 実行中 | 2026-10-23の公式枠は消費済み。基準版のfallback原因を分析し、汎用改善候補を同条件で検査する。 |
| M6 最終凍結 | 未開始 | 大会受付終了の公式確認後に実施する。 |

### 提出候補の固定

- Kaggle Notebook: `tecchannn/arc2-codex-main-baseline-v1`, version 2
- 実行記録: `出力/Kaggle/arc2-codex-main-baseline-v1/v2/実行記録.json`
- Notebook SHA-256: `47fcc2a650fc59d33c2f2182c0670e3d639bac5d92e3f4fca836c0093493a8ef`
- Metadata SHA-256: `d7de070ae4379246d8e26eece0ffe656ad44ba30fdc853bdc0af0957bc8a3a04`
- `submission.json`: 1,731,133 bytes、240課題、259 test、SHA-256 `a0eeaaa6203d4fdd049f8aa705a8ac7832cb98240759703eb0288ad3d62b4927`
- 258 fallback件を含む。fallbackを正答・解決として数えない。

### 日次履歴

| Kaggle基準日 | サイクル | 変更・検査 | 公式提出 | score/状態 | 次の作業 |
| --- | --- | --- | --- | --- | --- |
| 2026-10-22 | D0 初回試行 | v1はevaluation challenges 120課題/172 testを選んだため、公式sampleに必要な240課題/259 testと不一致 | ref `57517199`、COMPLETE後にformat error、scoreなし | 失敗。証跡は `運用/証拠/ARC2_Kaggle初回提出_v1/` | M2是正後、v2を別versionで再実行済み |
| 2026-10-23 | D0 初回形式修正提出 | v2の実行・形式・出力SHAを再確認済み | ref `57560705`、2026-10-23 12:25:05 UTCに受理。Notebook v2 | `COMPLETE`、public score `0.00`、失敗詳細なし（履歴確認12:42 UTC） | M4をPASS固定。今日の枠は消費済み。fallback/HOLDを原因別に分析し、次回候補を同条件で評価 |

## M5 着手時の原因分析

- 公式v2出力監査: 258/259 testがfallback。内訳は `solver_hold` 257件（HDS状態 `断定保留`）と `AssemblyIncomplete` 1件。public score `0.00` はKaggleの表示値で、これから正答件数を推定しない。
- HDS入力専用の代表hold再実行では `現行暫定原理の適用に必要な観測が不足している`。現時点で公開testに対するHDS確定回答は未成立。
- `AssemblyIncomplete`は疎標点重畳候補の250,000探索上限超過が、他の独立候補機構までタスク単位で中断していた。候補モジュール内で隔離する修正候補を作成し、対象単体テスト1件PASS。公式test入力で再実行後もそのtestは `断定保留` のため、提出品質の改善はまだ実証されていない。変更は未採用・未push。
- 公開trainingのleave-one-outで汎用D4候補を測定した。3件以上の異なる教師入力に対し、同じ回転/反射が全教師出力を色変更なしで完全再現し、test上で残る変換が一致する条件に限定。事前教材に含む元課題1件を除外した2,916例中、一意予測12件、完全一致12件、誤予測0件。
- 同じ12例を既存HDSで比較するとD4候補無効時は0件回答、候補有効時は12件回答・12件完全一致。HDS同値ゲートを通した。公式 `arc-agi_test_challenges.json` の全件runnerは240課題/259 test、686.578秒、fallback 258→257、変更出力1 test。sample形式一致、submission SHA-256 `fb34dfe3e1d6d982478be564a4aa4a51550335b8fd3ac8c8b4341beb104f1843`。このtestの正誤は不明。評価記録は[比較JSON](証拠/ARC2_Kaggle日次提出_20261023/D4-LOO比較.json)。`evaluation_solutions.json` は読んでいない。
- 実装は公開training leave-one-outで同条件増分を確認した候補としてローカルmainへ保存する。GitHubへはpushせず、Kaggle private Notebookで検証する。公式testの正誤と改善scoreは未確認。2026-10-23の提出枠はref `57560705` で使用済み。次回はclean commitからKaggle Notebookを実行し、日次上限と履歴を再確認してから次の公式提出を行う。

## 日次記録の必須項目

各日、Kaggle基準日とJST、前回/最高score、改善仮説、変更点、同条件ローカル比較、回帰、Notebook/ソース/JSON SHA、当日枠、提出ref・受理/失敗状態、score/Pending、次の作業と提出可能時刻を追記する。曖昧な提出応答では再送せず履歴を照合する。順位やscoreを推定・捏造しない。

自動再開機構はCodex heartbeatで本台帳を読み込むよう設定する。セッションが切れた場合は、ここにある最終状態と `Kaggle操作.py 履歴` を照合してから再開し、同日二重提出を防ぐ。
