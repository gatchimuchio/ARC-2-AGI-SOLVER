# ARC2 日次提出最適化台帳

- 適用正本: [2026-10-23 v1.1 現行正本](ARC2_初回Kaggle提出_現行正本.md)
- Owner指示ID: `ARC2-DAILY-OPTIMIZATION-20261023`
- 次に再開する工程: M3 初回公式提出の受理確認 → M4 公式score/提出経路の固定 → M5 日次最適化
- 最終提出期限（正本記載）: 2026-11-02 23:59 UTC。実際の最新Kaggle画面/APIを各日に確認する。

## 現在状態 — 2026-10-23

| 工程 | 判定 | 根拠 |
| --- | --- | --- |
| M0 基準点固定 | PASS | 作業開始時のHEADとorigin/mainはともに `ba4ec6e4131bff174d41ef1bb2909ed652d7bdae`。開始前は `main` がcleanで、添付保管ディレクトリだけが未追跡。今回の指示・仕様・工程は添付原文のSHAと一致。 |
| M1 現行資産の再現 | PASS（既存測定） | 運用報告の同条件実測: 240課題・259 test、909.109秒。258件はHDS HOLD fallbackで正答ではない。 |
| M2 Kaggle結合 | PASS（v2） | Kaggle Notebook `tecchannn/arc2-codex-main-baseline-v1` v2 は現行版、状態COMPLETE。Internet OFF/CPU、実行283.265秒。提出出力240課題・259 test、2候補/test、SHA-256 `a0eeaaa6203d4fdd049f8aa705a8ac7832cb98240759703eb0288ad3d62b4927`。 |
| M3 公式提出 | ACCEPTED / 採点待ち | Notebook v2の提出ref `57560705`。Kaggle履歴で2026-10-23 12:25:06 UTC、`PENDING`、score空、失敗詳細なしを確認。提出前の接続確認成功、当日履歴なし、前回から24時間超。 |
| M4 score・経路固定 | HOLD / 採点待ち | Notebook v2 → `submission.json` → 公式提出ref `57560705` の経路は記録済み。公式scoreは未公開のためG5未成立。 |
| M5 日次反復 | 未開始 | M4成立後に追加承認なしで開始し、最終受付まで継続する。 |
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
| 2026-10-23 | D0 初回形式修正提出 | v2の実行・形式・出力SHAを再確認済み | ref `57560705`、2026-10-23 12:25:05 UTCに受理。Notebook v2 | `PENDING`、score未観測、失敗詳細なし（履歴確認 12:25:06 UTC） | status/scoreを追跡。結果確定後にM4を固定し、scoreと経路が確認できたらM5へ移る |

## 日次記録の必須項目

各日、Kaggle基準日とJST、前回/最高score、改善仮説、変更点、同条件ローカル比較、回帰、Notebook/ソース/JSON SHA、当日枠、提出ref・受理/失敗状態、score/Pending、次の作業と提出可能時刻を追記する。曖昧な提出応答では再送せず履歴を照合する。順位やscoreを推定・捏造しない。

自動再開機構はCodex heartbeatで本台帳を読み込むよう設定する。セッションが切れた場合は、ここにある最終状態と `Kaggle操作.py 履歴` を照合してから再開し、同日二重提出を防ぐ。
