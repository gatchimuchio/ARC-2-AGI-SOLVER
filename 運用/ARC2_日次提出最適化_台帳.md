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
| M5 日次反復 | 実行中 | 2026-10-23の公式枠はref `57560705` で消費済み。palette拡張はLOO・ローカル全件runner・clean Kaggle Notebook v4の出力一致までPASS。公式採点は未実施。 |
| M6 最終凍結 | 未開始 | 大会受付終了の公式確認後に実施する。 |

### 提出候補の固定

- Kaggle Notebook: `tecchannn/arc2-codex-main-baseline-v1`, version 2
- 実行記録: `出力/Kaggle/arc2-codex-main-baseline-v1/v2/実行記録.json`
- Notebook SHA-256: `47fcc2a650fc59d33c2f2182c0670e3d639bac5d92e3f4fca836c0093493a8ef`
- Metadata SHA-256: `d7de070ae4379246d8e26eece0ffe656ad44ba30fdc853bdc0af0957bc8a3a04`
- `submission.json`: 1,731,133 bytes、240課題、259 test、SHA-256 `a0eeaaa6203d4fdd049f8aa705a8ac7832cb98240759703eb0288ad3d62b4927`
- 258 fallback件を含む。fallbackを正答・解決として数えない。

### M5 private Notebook検証

- v3はlocal commit `cf2de3f59b5352c3c5eef7f66572274bc4b9ec78` のclean bundleから作成。Notebook SHA `43b541530a04947618991814cab1c4ac64a03c1ef6f3a2866837757fa1aebde0`、metadata SHA `d7de070ae4379246d8e26eece0ffe656ad44ba30fdc853bdc0af0957bc8a3a04`。
- Kaggle runはCOMPLETE、392.139秒。240課題/259 test、2候補/test。Kaggle出力はローカル出力と一致し、submission SHAは `fb34dfe3e1d6d982478be564a4aa4a51550335b8fd3ac8c8b4341beb104f1843`。これはNotebook実行であり大会提出ではない。検証記録は[KaggleNotebook-v3検証.json](証拠/ARC2_Kaggle日次提出_20261023/KaggleNotebook-v3検証.json)。
- palette版v4はlocal commit `e26e9bb82acf8806b9a649fdf7b1cc3cfadf92fe` のclean bundleから作成。Notebook SHA `84a6da8173870e56ca2caf223628db17351da45780f10318d07bfe383a3ff824`、payload SHA `fb8049c72f2413bf98b2471dde5e8895ca0932f51dcacbedf477975d152316ac`。Kaggle runはCOMPLETE、234.124秒。240課題/259 test、fallback 256、2候補/test。Kaggle出力はローカル出力とバイト単位で一致し、submission SHA `78e59642d9a84457c1ad9a16b1b98c12de717a34d562438ae830a8903cd5b026`。検証記録は[KaggleNotebook-v4検証.json](証拠/ARC2_Kaggle日次提出_20261023/KaggleNotebook-v4検証.json)。
- 公式履歴の最新大会提出はref `57560705`、COMPLETE、public score `0.00`のまま。Notebook v4は非公開検証実行であり、大会への新規提出・採点はない。2026-10-23の枠は使用済み。

### 日次履歴

| Kaggle基準日 | サイクル | 変更・検査 | 公式提出 | score/状態 | 次の作業 |
| --- | --- | --- | --- | --- | --- |
| 2026-10-22 | D0 初回試行 | v1はevaluation challenges 120課題/172 testを選んだため、公式sampleに必要な240課題/259 testと不一致 | ref `57517199`、COMPLETE後にformat error、scoreなし | 失敗。証跡は `運用/証拠/ARC2_Kaggle初回提出_v1/` | M2是正後、v2を別versionで再実行済み |
| 2026-10-23 | D0 初回形式修正提出 | v2の実行・形式・出力SHAを再確認済み | ref `57560705`、2026-10-23 12:25:05 UTCに受理。Notebook v2 | `COMPLETE`、public score `0.00`、失敗詳細なし（履歴確認12:42 UTC） | M4をPASS固定。今日の枠は消費済み。fallback/HOLDを原因別に分析し、次回候補を同条件で評価 |

## M5 着手時の原因分析

- 公式v2出力監査: 258/259 testがfallback。内訳は `solver_hold` 257件（HDS状態 `断定保留`）と `AssemblyIncomplete` 1件。public score `0.00` はKaggleの表示値で、これから正答件数を推定しない。
- HDS入力専用の代表hold再実行では `現行暫定原理の適用に必要な観測が不足している`。現時点で公開testに対するHDS確定回答は未成立。
- `AssemblyIncomplete`は疎標点重畳候補の250,000探索上限超過が、他の独立候補機構までタスク単位で中断していた。候補モジュール内で隔離する修正候補を作成し、対象単体テスト1件PASS。公式test入力で再実行後もそのtestは `断定保留` のため、提出品質の改善はまだ実証されていない。変更は未採用・未push。
- 公開trainingのLOO母数を再監査した。最低支持数3に対し、holdout後も3教師が残る適格例は1,191件。従来の2,916はtrain例3件のtaskも含めており、支持数条件を満たさない例まで分母に含めていた。訂正計算は公開trainingだけを使い、task ID条件やHDS事前記憶を予測に使わない。旧JSONは履歴として保持し、訂正証拠は[D4色写像拡張-訂正.json](証拠/ARC2_Kaggle日次提出_20261023/D4色写像拡張-訂正.json)へ記録する。色変更なしD4は12予測中12完全一致、誤り0。部分的一対一色写像を追加した候補は同じ1,191件上で13予測中13完全一致、誤り0。既存12回答は全て同一、新規回答は1件。
- palette候補は、3教師以上で同じD4操作と一貫した単射色写像が適合し、照会に出る全色が既知写像に含まれ、残るD4出力が全て一致するときだけ回答する。未観測色、写像衝突、候補不一致はHOLD。HDS同値ゲート統合・保持を含むテスト79件と29 subtests、Ruff、`git diff --check`がPASS。
- 公開evaluation challengeは120課題/172 testで候補なし。公式test challenge入力では旧候補1件からpalette拡張後2件へ増えた。全件runnerは240課題/259 test、687.297秒、v3比で変化test1件、fallback 257→256（全て`solver_hold`）、非fallback 2→3件。sampleのtask順序・test数・2候補が一致。提出JSON SHA-256 `78e59642d9a84457c1ad9a16b1b98c12de717a34d562438ae830a8903cd5b026`、監査SHA-256 `f12a8544b49098d7ebf1e2d5bcbcaa0e4382f8958e455de8220aa8a52e6e6951`。変更したtestの正誤は未知。正解ファイルは読んでいない。
- palette版はclean Kaggle v4 Notebook検証までCOMPLETEで、ローカル提出JSONと完全一致した。ローカルmainの`e26e9bb`までにコード・回帰・証跡をコミット済み。GitHubへはpushしていない。公式test正誤・palette版の公式scoreは未確認。2026-10-23の大会提出枠はref `57560705` で使用済み。次回は最新正本・公式ルール・履歴と日次枠を再確認してから公式提出する。
- 第2候補の改善仮説として、attempt_1を維持し、教師適合したD4モデルがtestで不一致の場合にだけ別D4予測をattempt_2へ出す案を測定した。公開training LOOの最低支持数3の適格fold 1,191件中、現行D4モデルが適用できた13件は全て一意・完全一致で、異なる第2候補は0件。公式test challenge入力でもD4候補がある2件は両方一意で、不一致は0件（正解は未観測）。D4限定の案はLOO改善根拠がないため実装しない。全HDS機構の代替候補選択を評価した結果ではない。証跡は[D4第二候補-不採用.json](証拠/ARC2_Kaggle日次提出_20261023/D4第二候補-不採用.json)。

## 日次記録の必須項目

各日、Kaggle基準日とJST、前回/最高score、改善仮説、変更点、同条件ローカル比較、回帰、Notebook/ソース/JSON SHA、当日枠、提出ref・受理/失敗状態、score/Pending、次の作業と提出可能時刻を追記する。曖昧な提出応答では再送せず履歴を照合する。順位やscoreを推定・捏造しない。

自動再開機構はCodex heartbeatで本台帳を読み込むよう設定する。セッションが切れた場合は、ここにある最終状態と `Kaggle操作.py 履歴` を照合してから再開し、同日二重提出を防ぐ。
