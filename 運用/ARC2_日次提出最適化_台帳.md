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
| M5 日次反復 | 実行中 | Kaggle履歴上、最新ref `57560705` は0.00、過去最高ref `55046979` は0.83（2026-07-28）。旧Kernel v4出力はローカル完全再現したがtraining task ID分岐があり、現行AGENTSにより再利用不可。適格なpalette版Notebook v4出力（SHA `78e596…3cd5b026`）を次回候補として復元・再検査済み。2026-10-23 UTCの公式枠はref `57560705` で消費済み。 |
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
| 2026-10-23 | D0 初回形式修正提出 | v2の実行・形式・出力SHAを再確認済み | ref `57560705`、2026-10-23 12:25:05 UTCに受理。Notebook v2 | `COMPLETE`、public score `0.00`、失敗詳細なし（最新履歴15:41 UTC） | M4をPASS固定。歴史上の最高0.83（ref `55046979`）を確認。旧Kernel v4はtraining ID分岐のため不採用。palette v4を次回候補に固定 |
| 2026-10-23 | M5 過去最高・候補再監査 | 旧Kernel v4の出力SHAは取得物・隔離ローカル再実行で一致。公開training ID分岐を検出し、現行AGENTSに従い旧パッケージを再利用対象外とした。現行palette v4出力をKaggleから復元し、公式sample構造とSHAを再検査 | 公式提出なし。日次枠はref `57560705` が使用済み | 旧0.83は履歴値として保持するが、source/scoreの厳密な版対応は未証明。次回UTC日付に履歴・ruleを確認しpalette v4を提出候補にする |
| 2026-10-23 | M5 安全な旧汎用部品のLOO監査 | v29/v30/v31のtask-ID分岐なしコンポーネントを、公開trainingのみの適格1,191-foldで厳密なfit/predictゲートに通した。3部品ともfit成功0、予測0、例外0。統合根拠なしとして不採用 | 公式提出なし。ref `57560705` が当日枠を使用済み | palette v4を維持。提出前に毎回公式rule・履歴・UTC枠を再照合する |
| 2026-10-23 | M5 2例支持の補足・既存HDS重複確認 | HDSが許容する異なる2教師の1,725-foldも追加評価。旧v31十字部品が3件fitし全件正答したが、現行HDSのARC十字形態着色も同じ3-foldで全件正答。公式test challenge入力では同family候補0件 | 公式提出なし。ref `57560705` が当日枠を使用済み | 旧部品は既存実装と重複し増分なし。palette v4を維持。提出可能日はrule・履歴・枠を再照合 |

## M5 着手時の原因分析

- 公式v2出力監査: 258/259 testがfallback。内訳は `solver_hold` 257件（HDS状態 `断定保留`）と `AssemblyIncomplete` 1件。public score `0.00` はKaggleの表示値で、これから正答件数を推定しない。
- HDS入力専用の代表hold再実行では `現行暫定原理の適用に必要な観測が不足している`。現時点で公開testに対するHDS確定回答は未成立。
- `AssemblyIncomplete`は疎標点重畳候補の250,000探索上限超過が、他の独立候補機構までタスク単位で中断していた。候補モジュール内で隔離する修正候補を作成し、対象単体テスト1件PASS。公式test入力で再実行後もそのtestは `断定保留` のため、提出品質の改善はまだ実証されていない。変更は未採用・未push。
- 公開trainingのLOO母数を再監査した。最低支持数3に対し、holdout後も3教師が残る適格例は1,191件。従来の2,916はtrain例3件のtaskも含めており、支持数条件を満たさない例まで分母に含めていた。訂正計算は公開trainingだけを使い、task ID条件やHDS事前記憶を予測に使わない。旧JSONは履歴として保持し、訂正証拠は[D4色写像拡張-訂正.json](証拠/ARC2_Kaggle日次提出_20261023/D4色写像拡張-訂正.json)へ記録する。色変更なしD4は12予測中12完全一致、誤り0。部分的一対一色写像を追加した候補は同じ1,191件上で13予測中13完全一致、誤り0。既存12回答は全て同一、新規回答は1件。
- palette候補は、3教師以上で同じD4操作と一貫した単射色写像が適合し、照会に出る全色が既知写像に含まれ、残るD4出力が全て一致するときだけ回答する。未観測色、写像衝突、候補不一致はHOLD。HDS同値ゲート統合・保持を含むテスト79件と29 subtests、Ruff、`git diff --check`がPASS。
- 公開evaluation challengeは120課題/172 testで候補なし。公式test challenge入力では旧候補1件からpalette拡張後2件へ増えた。全件runnerは240課題/259 test、687.297秒、v3比で変化test1件、fallback 257→256（全て`solver_hold`）、非fallback 2→3件。sampleのtask順序・test数・2候補が一致。提出JSON SHA-256 `78e59642d9a84457c1ad9a16b1b98c12de717a34d562438ae830a8903cd5b026`、監査SHA-256 `f12a8544b49098d7ebf1e2d5bcbcaa0e4382f8958e455de8220aa8a52e6e6951`。変更したtestの正誤は未知。正解ファイルは読んでいない。
- palette版はclean Kaggle v4 Notebook検証までCOMPLETEで、ローカル提出JSONと完全一致した。ローカルmainの`e26e9bb`までにコード・回帰・証跡をコミット済み。GitHubへはpushしていない。公式test正誤・palette版の公式scoreは未確認。2026-10-23の大会提出枠はref `57560705` で使用済み。次回は最新正本・公式ルール・履歴と日次枠を再確認してから公式提出する。
- 第2候補の改善仮説として、attempt_1を維持し、教師適合したD4モデルがtestで不一致の場合にだけ別D4予測をattempt_2へ出す案を測定した。公開training LOOの最低支持数3の適格fold 1,191件中、現行D4モデルが適用できた13件は全て一意・完全一致で、異なる第2候補は0件。公式test challenge入力でもD4候補がある2件は両方一意で、不一致は0件（正解は未観測）。D4限定の案はLOO改善根拠がないため実装しない。全HDS機構の代替候補選択を評価した結果ではない。証跡は[D4第二候補-不採用.json](証拠/ARC2_Kaggle日次提出_20261023/D4第二候補-不採用.json)。
- 全HDS第2候補の隔離LOO runnerで公開trainingの限定sample 23 fold/5 taskを調べ、solver answer・候補・pair正答はいずれも0だった（全1,191 eligible foldに一般化しない）。task `009d5c81` 5 foldのparse cache比較では平均fit時間21.80902秒から12.66006秒へ41.95%短縮した一方、候補は増えなかった。同一公式test challengeの240課題/259 test全件A/Bはbaseline 730.328秒、cache候補756.703秒（3.61%遅延）で、提出JSON SHAとfallback記録は完全一致。cacheは採用せず、製品wrapperはHEADへ復元した。trace有効試行はWindows worker access violationのため除外し、runnerを修正してtraceなし10 foldが10/10 clean completeすることを確認。詳細hash・文字コード混入runの除外理由は[全HDS第二候補-parse-cache比較.json](証拠/ARC2_Kaggle日次提出_20261023/全HDS第二候補-parse-cache比較.json)。以前の未完了試行は履歴として[全HDS第二候補-試行中断.json](証拠/ARC2_Kaggle日次提出_20261023/全HDS第二候補-試行中断.json)へ残す。
- 旧Kernel由来の適格な汎用候補を追加監査した。v31が公開するv29対角領域塗り、v30障害物コリドール、v31プラス字形再着色の各部品にtask ID・長いhash条件はない。支持3以上のLOO 1,191 foldでは3部品ともfit成功0だった。後続監査で現行HDSが許容する「異なる入力の教師2例」1,725 foldも加えると、十字再着色だけが3件fitし全件正答、他2部品は0件だった。現行HDSの既存ARC十字形態着色は、その同じ3 foldを全件正答し、公式test challenge入力でも当familyの候補は0件。旧部品は重複実装で増分なしとして統合しない。証跡は[安全旧コンポーネントLOO-不採用.json](証拠/ARC2_Kaggle日次提出_20261023/安全旧コンポーネントLOO-不採用.json)と[支持数2補足](証拠/ARC2_Kaggle日次提出_20261023/安全旧コンポーネントLOO-支持数2補足.json)。旧Kernelの他候補は課題ID依存を含むため監査対象から除外した。支持数2を含む2,916 foldはこの適用範囲に限り、palette候補の支持数3基準1,191 foldは変更しない。

## 日次記録の必須項目

各日、Kaggle基準日とJST、前回/最高score、改善仮説、変更点、同条件ローカル比較、回帰、Notebook/ソース/JSON SHA、当日枠、提出ref・受理/失敗状態、score/Pending、次の作業と提出可能時刻を追記する。曖昧な提出応答では再送せず履歴を照合する。順位やscoreを推定・捏造しない。

自動再開機構はCodex heartbeatで本台帳を読み込むよう設定する。セッションが切れた場合は、ここにある最終状態と `Kaggle操作.py 履歴` を照合してから再開し、同日二重提出を防ぐ。

## 2026-10-23 D4の支持数2 ablation

格子D4教材の最小支持数を3から2へ一箇所だけ変えた隔離probeを実施した。HDS契約と同じく残る2教師入力が異なるLOO fold 1,725件で19予測が発火し、18正答・1誤答。支持3以上の1,191 foldでは既存ゲートと出力が全件一致し、13予測全て正解だった。

該当19 foldだけ現行HDSへ仮統合すると、D4 familyは19件全て同値採用され、誤答1件も断定出力した。公式evaluation/test challengeでは支持2条件のfitは0、候補増分も0で、test側既存D4候補2件は出力差なし。現行閾値を保ち、提出コードへ統合しない。証跡は[D4支持数2-不採用.json](証拠/ARC2_Kaggle日次提出_20261023/D4支持数2-不採用.json)。

| 2026-10-23 | M5 標識軸転写の共通色枝刈り | 厳密必要条件で360→教師共通paletteの候補だけ評価。LOO 2,916 row完全一致、時間924.088→119.406秒。公式challenge入力・全adapter出力も同一。 | 公式提出なし。ref `57560705` がUTC当日枠を使用済み | local JSON SHA `78e596…3cd5b026`のまま、fallback256。Notebook v5 COMPLETE、実行359.332秒（v4より125.208秒長く、Kaggle時間短縮は未確認）。証跡は[枝刈り検証](証拠/ARC2_Kaggle日次提出_20261023/標識軸転写共通色枝刈り-検証.json) | local commit `2759d39`、Notebook v5 COMPLETE。出力SHA `78e596…3cd5b026`はlocalとbyte一致。詳細は[KaggleNotebook-v5検証](証拠/ARC2_Kaggle日次提出_20261023/KaggleNotebook-v5検証.json)。公式提出可能枠は2026-10-24 00:00 UTC以降。実提出前に当日rule・履歴・参加状況を再確認 |
| 2026-10-23 | M5 全HDS第2候補の全域LOO評価 | 公開trainingの1,191 unique fold。初回20秒制限で1,178 complete/13 timeout、13件を60秒で再試行し全件complete。診断上の主出力一致21のうち8はidentity fallbackの偶然一致。実solver回答は13件すべてD4で完全一致、第2候補増分0。 | 公式提出なし。ref `57560705` が当日枠を使用済み | 第2候補増分なし、13 retry全てsolver回答/候補なし。製品変更なし。hidden/evaluation解答未読。 | 第2候補仮説は不採用。次のUTC日付に公式rule・履歴・提出枠を再確認。証跡は[全域LOO](証拠/ARC2_Kaggle日次提出_20261023/全HDS第二候補-全1191fold-LOO.json) |
| 2026-10-23 | M5 全HDS最低支持2以上のLOO（進行中） | 公開training 2,916 foldを20秒/foldで評価。support==2は1,725、support>=3は1,191。21:23 UTCのJSONL snapshotは1,403 fold（1,382 complete、21 timeout）。timeout21件は6課題に集中（task別5/4/4/3/3/2 fold）。primary exact22件のうち7件はidentity fallback一致。solver実回答15件は全てprimary exact（支持数3のD4が9件、支持数2の疎点graph転写が3件、十字形態着色が3件）。distinct second candidateは0 fold、selected second exact 0、incremental pair exact 0。旧support3 raw runとtraining SHA/ID除外条件は一致し、共有563 foldの共通診断値に不一致0（実行順・所要時間を除外）。比較は部分範囲のため全run後に再集計する。 | 公式提出なし。最新ref `57560705` が10/23枠を使用済み | product solver不変。hidden/evaluation解答未読。runner commit `370b267`。 | session 33524をpollし同一run継続。全件完了後、支持数別評価・timeout再試行・公式test入力影響を監査 |
| 2026-10-23 | M5 Kaggle v5 live recheck | 公式ルール・timelineを再確認：1日最大1提出、最終選択最大2件、Entry deadline 10/26 23:59 UTC、Final deadline 11/02 23:59 UTC。履歴最新ref `57560705` は2026-10-23 12:25:06.577 UTC、COMPLETE/public 0.00。kernel `tecchannn/arc2-codex-main-baseline-v1` v5もCOMPLETE、失敗詳細なし。 | 公式提出なし。10/23枠使用済み。24h間隔を守る次回最早時刻は10/24 12:25:06.577 UTC（当日にrule/history/quotaを再確認）。 | Notebook実行は大会提出ではない。前回取得outputはsubmission SHA `78e596…3cd5b026`、240/259。 | 次の提出時に候補出力・sample形式・kernel完了・参加・当日枠・24h間隔を再検査し、同日1回だけ公式提出 |
