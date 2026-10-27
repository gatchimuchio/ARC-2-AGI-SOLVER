# ARC2 日次提出最適化台帳

- 適用正本: [2026-10-24 v2 現行正本](ARC2_初回Kaggle提出_現行正本.md)
- Owner指示ID: `ARC2-SCORE-GATE-20261024`
- 現在工程: P5 原因分析・汎用改善・同条件比較
- 最終提出期限（2026-10-24時点の公式表示）: 2026-11-02 23:59 UTC。各日にKaggle公式タイムラインを再確認する。

## 最新状態 — v2 / 2026-10-24 JST

| 工程・ゲート | 判定 | 根拠 |
| --- | --- | --- |
| P0 正本・現状確認 | PASS | 添付ZIP SHA `9d16d2b408948c6d914755cf56a206fe78dccd2b6131e882874d4c60d391345a` とv2三文書のSHAを照合。branch `main`、HEAD `dae0a5dbe124a0c4a01bd69a26dda0036d0379e0`、origin/mainの現行remoteも `6a6bd43cbf4ec80f7b2ffd50e5c0a3a97655d8b6`。作業開始時tracked差分なし、既存untrackedは保持。mainはorigin/mainより40 commit先行。 |
| P1 現行提出の再照会 | PASS | 2026-10-24 01:58:26 UTCの公式履歴で、最新ref `57576155` が `COMPLETE / 0.00`、失敗詳細なしと再確認。 |
| G-SCORE / P4 基準点固定 | PASS | ref `57560705` はv2、ref `57576155` はNotebook `tecchannn/arc2-codex-main-baseline-v1` v5、source commit `2759d393a8d79824d36754785ce16f66d0493ebd`、Notebook SHA `d04668b0410a028195c1eb3c0c99620c9336d8ff10a41156181faaf73dc7910c`、test入力SHA `232264c58f825ee77327dcfc9f4e5cb2f83b8d997eb69032be1bf2205bbe1a83`、提出JSON SHA `78e59642d9a84457c1ad9a16b1b98c12de717a34d562438ae830a8903cd5b026`。前回score・最新scoreとも0.00。最新記録は[提出-57576155](証拠/ARC2_公式スコア起点_20261024/公式提出-57576155.json)と追記型[運用checkpoint](ARC2_公式スコア運用チェックポイント.jsonl)。 |
| P5 原因分析・最適化 | 診断PASS / candidate未提出 | 全前景平行移動候補は公開training LOO 1,191 foldで4件を追加回答し4件完全一致・誤答0、基準D4の13件を保持。全HDSのLOOは3回答・1保留。全challenge 240/259でv5比fallback 256→254、回答3→5、変更行2。Kaggle Notebook v6は01:58:22 UTC `COMPLETE`、version 6の取得出力はローカルとbyte一致、SHA `c34dcdd39e1afacba8c2fe992ffd93378c92bbbde3885a58f43f3fd02253bcb2`、実行350.365秒。評価正解未読で公式改善とは扱わず、候補は未提出。[LOO証拠](証拠/ARC2_公式スコア起点_20261024/P5_global_translation_LOO.json)、[challenge比較](証拠/ARC2_公式スコア起点_20261024/P5_global_translation_full_challenge_check.json)、[Kaggle v6照合](証拠/ARC2_公式スコア起点_20261024/P5_global_translation_kaggle_v6_check.json)。 |
| P2/P3 採点監視・修理 | 数値score確定 / 継続監視 | ref `57576155` は01:58:26 UTCの公式履歴でも `COMPLETE / 0.00`。次回は02:34:26.521420 UTC。提出再送なし。観測履歴は追記型checkpoint、初回詳細は[公式スコア観測](証拠/ARC2_公式スコア起点_20261024/公式スコア観測-57576155.json)。 |
| G3 継続運転・再開 | PARTIAL | Task Scheduler `ARC2-Kaggle-Score-Monitor`は10:33:01 JSTに実起動しLastTaskResult=0。期限後の読み取り専用`--tick`でref `57576155`を再照会、数値scoreをcheckpointへ追記し次回時刻を02:34 UTCに更新。Codex heartbeatの実triggerによるスレッド再開は未観測のためG3 PASSにはしない。 |
| P6 日次提出 | 2026-10-24 UTC 提出・採点完了 | Notebook v5、ref `57576155` を00:12:39 UTCに受理。公式履歴で `COMPLETE / 0.00` を確認。前回scoreも0.00、公式score差分0.00。提出可否確認もUTC当日枠使用済みで拒否（当日履歴はref `57576155`のみ）。次の提出可能日はUTC日付変更後に当日規則・履歴・残枠を再確認する。 |
| P7 最終凍結 | 未開始 | 公式受付終了後に履歴と最良候補を固定する。 |

Kaggle 2.2.4の認証・履歴照会はプロジェクト `.venv` では成立。global `python` は別環境で認証に失敗したため、以後の直接操作は `.venv\\Scripts\\python.exe` を明示する。認証値自体は記録・表示しない。
提出wrapperは履歴を読み取り、当日UTC枠使用済み・直近の採点待ち・直近の空scoreで送信を拒否する。可否判定の単体試験5件PASS。2026-10-23 UTCの実可否照会はref `57560705`が当日提出済みのため送信不可を返し、当日は提出していない。

公式ルールは[Kaggle rules](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/rules)、受付日程は[大会ページ](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2)で作業日に再確認する。

2026-10-24 UTCの提出候補は、Notebook v5の完了・出力一致と、D4色写像拡張の公開training LOO 13/13正答を根拠に選定した。公式test入力259例でfallbackはv2の258からv5の256へ減ったが、v5の提出ref `57576155` は `COMPLETE / 0.00`。追加出力の個別正誤は未観測で、改善を主張しない。公式提出記録は[公式提出-57576155](証拠/ARC2_公式スコア起点_20261024/公式提出-57576155.json)。

## 過去の状態 — 2026-10-23（v1.1時点の履歴）

以下は旧正本での観測・作業記録であり、現在の正本・工程位置は上のv2状態を参照する。

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
- 既知の公開training support-2 LOO 2 foldの `IndexError` を再現。原因は `vertical_template_right` のsource開始列が右テンプレート位置を指し、左素材パネル幅とslice幅が不一致になること。開始列を左端へ修正し、公式提出版source commit `3d444f34` で合成回帰の例外を再現、修正版の右テンプレート回帰と関連3 suite 15件PASS。training SHA `779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5` の同一2 foldを再実行すると2件ともrunner完了したがsolver回答は0件で、正答改善は未確認。この修正は局所的な例外修復候補にとどめ、性能向上・公式提出候補とは扱わない。詳細は[右テンプレート素材パネル座標診断](証拠/ARC2_公式スコア起点_20261024/P5_右テンプレート素材パネル座標診断.json)。
- `AssemblyIncomplete`は疎標点重畳候補の250,000探索上限超過が、他の独立候補機構までタスク単位で中断していた。候補モジュール内で隔離する修正候補を作成し、対象単体テスト1件PASS。公式test入力で再実行後もそのtestは `断定保留` のため、提出品質の改善はまだ実証されていない。変更は未採用・未push。
- 公開trainingのLOO母数を再監査した。最低支持数3に対し、holdout後も3教師が残る適格例は1,191件。従来の2,916はtrain例3件のtaskも含めており、支持数条件を満たさない例まで分母に含めていた。訂正計算は公開trainingだけを使い、task ID条件やHDS事前記憶を予測に使わない。旧JSONは履歴として保持し、訂正証拠は[D4色写像拡張-訂正.json](証拠/ARC2_Kaggle日次提出_20261023/D4色写像拡張-訂正.json)へ記録する。色変更なしD4は12予測中12完全一致、誤り0。部分的一対一色写像を追加した候補は同じ1,191件上で13予測中13完全一致、誤り0。既存12回答は全て同一、新規回答は1件。
- palette候補は、3教師以上で同じD4操作と一貫した単射色写像が適合し、照会に出る全色が既知写像に含まれ、残るD4出力が全て一致するときだけ回答する。未観測色、写像衝突、候補不一致はHOLD。HDS同値ゲート統合・保持を含むテスト79件と29 subtests、Ruff、`git diff --check`がPASS。
- 公開evaluation challengeは120課題/172 testで候補なし。公式test challenge入力では旧候補1件からpalette拡張後2件へ増えた。全件runnerは240課題/259 test、687.297秒、v3比で変化test1件、fallback 257→256（全て`solver_hold`）、非fallback 2→3件。sampleのtask順序・test数・2候補が一致。提出JSON SHA-256 `78e59642d9a84457c1ad9a16b1b98c12de717a34d562438ae830a8903cd5b026`、監査SHA-256 `f12a8544b49098d7ebf1e2d5bcbcaa0e4382f8958e455de8220aa8a52e6e6951`。変更したtestの正誤は未知。正解ファイルは読んでいない。
- palette版はclean Kaggle v4 Notebook検証までCOMPLETEで、ローカル提出JSONと完全一致した。ローカルmainの`e26e9bb`までにコード・回帰・証跡をコミット済み。GitHubへはpushしていない。公式test正誤・palette版の公式scoreは未確認。2026-10-23の大会提出枠はref `57560705` で使用済み。次回は最新正本・公式ルール・履歴と日次枠を再確認してから公式提出する。
- 第2候補の改善仮説として、attempt_1を維持し、教師適合したD4モデルがtestで不一致の場合にだけ別D4予測をattempt_2へ出す案を測定した。公開training LOOの最低支持数3の適格fold 1,191件中、現行D4モデルが適用できた13件は全て一意・完全一致で、異なる第2候補は0件。公式test challenge入力でもD4候補がある2件は両方一意で、不一致は0件（正解は未観測）。D4限定の案はLOO改善根拠がないため実装しない。全HDS機構の代替候補選択を評価した結果ではない。証跡は[D4第二候補-不採用.json](証拠/ARC2_Kaggle日次提出_20261023/D4第二候補-不採用.json)。
- 全HDS第2候補の隔離LOO runnerで公開trainingの限定sample 23 fold/5 taskを調べ、solver answer・候補・pair正答はいずれも0だった（全1,191 eligible foldに一般化しない）。task `009d5c81` 5 foldのparse cache比較では平均fit時間21.80902秒から12.66006秒へ41.95%短縮した一方、候補は増えなかった。同一公式test challengeの240課題/259 test全件A/Bはbaseline 730.328秒、cache候補756.703秒（3.61%遅延）で、提出JSON SHAとfallback記録は完全一致。cacheは採用せず、製品wrapperはHEADへ復元した。trace有効試行はWindows worker access violationのため除外し、runnerを修正してtraceなし10 foldが10/10 clean completeすることを確認。詳細hash・文字コード混入runの除外理由は[全HDS第二候補-parse-cache比較.json](証拠/ARC2_Kaggle日次提出_20261023/全HDS第二候補-parse-cache比較.json)。以前の未完了試行は履歴として[全HDS第二候補-試行中断.json](証拠/ARC2_Kaggle日次提出_20261023/全HDS第二候補-試行中断.json)へ残す。
- 旧Kernel由来の適格な汎用候補を追加監査した。v31が公開するv29対角領域塗り、v30障害物コリドール、v31プラス字形再着色の各部品にtask ID・長いhash条件はない。支持3以上のLOO 1,191 foldでは3部品ともfit成功0だった。後続監査で現行HDSが許容する「異なる入力の教師2例」1,725 foldも加えると、十字再着色だけが3件fitし全件正答、他2部品は0件だった。現行HDSの既存ARC十字形態着色は、その同じ3 foldを全件正答し、公式test challenge入力でも当familyの候補は0件。旧部品は重複実装で増分なしとして統合しない。証跡は[安全旧コンポーネントLOO-不採用.json](証拠/ARC2_Kaggle日次提出_20261023/安全旧コンポーネントLOO-不採用.json)と[支持数2補足](証拠/ARC2_Kaggle日次提出_20261023/安全旧コンポーネントLOO-支持数2補足.json)。旧Kernelの他候補は課題ID依存を含むため監査対象から除外した。支持数2を含む2,916 foldはこの適用範囲に限り、palette候補の支持数3基準1,191 foldは変更しない。

## 2026-10-24 UTC スコア帰還・P5詳細診断

- ref `57576155` はNotebook `tecchannn/arc2-codex-main-baseline-v1` v5、source `2759d393a8d79824d36754785ce16f66d0493ebd`、submission SHA `78e59642d9a84457c1ad9a16b1b98c12de717a34d562438ae830a8903cd5b026`に結び付いた `COMPLETE / 0.00`。00:34:15 UTC観測。前回ref `57560705`も0.00のため、公式score差分は0.00。証跡は[公式スコア観測](証拠/ARC2_公式スコア起点_20261024/公式スコア観測-57576155.json)。
- v2 source `3d444f34db32d62bd2edad320648e08e8dae19d6`を同一test SHAで再実行。105機構×239正常task記録=25,095機構記録中、25,093は候補なし、1は全教師再現（疎点graph転写）、1は教師反例（色群template充填）。testは257 HOLD、1回答、1 `AssemblyIncomplete`。fallback 258で公式v2監査と一致。
- v5 source `2759d393a8d79824d36754785ce16f66d0493ebd`も再実行。106機構×240 task=25,440記録中、25,436は候補なし、3は全教師再現（格子D4変換2、疎点graph転写1）、1は教師反例（色群template充填）。testは256 HOLD、3回答、task例外0で、公式v5監査fallback 256と一致。3回答は各1機構の単独予測で、競合なし。正解は未読のため正誤不明。
- HOLDの主因はtest候補不成立。v2は257件、v5は256件が「適用に必要な観測不足」。各版とも2件には隔離原理の追加理由があった。v5の隔離数は257行が0、2行が1。課題ごとの300秒上限超過は0。v2の最大worker wall 200.97秒で`AssemblyIncomplete`が1 test、v5は最大196.38秒・例外0。
- 制約診断例：連結箱参照240件は108件が全教師fit programなし、61件はrendererが入力外色を出せない必要条件、71件は入力と出力の形状差で棄却された。色・形状guardだけを外してもrenderer能力がないため解決せず、新しい汎用rendererと公開training LOO根拠が必要。band-profile stack 223件、marker-channel 223件も保存則の必要条件で不可能と分類された。これらを緩めるだけの修正は行わない。
- 2版は同一test入力でfallbackが258→256、回答が1→3になったが、公式public scoreは0.00→0.00。正誤未観測のローカル件数差を性能向上と扱わず、現時点で新規規則は採用していない。診断JSONはtest ID・格子を保存せず、評価解答も読んでいない。

- D4色写像の一対一制約を緩める仮説を、提出v5 sourceの公開training LOO 1,191 foldでprobeした。現行は13回答・13正答、many-to-one候補は14回答・13正答で、新規1回答が誤り。現行test 259入力ではmany-to-one fitが0件で候補増分なし。汎用化候補として棄却し、製品コードは変更しない。[訂正版診断](証拠/ARC2_公式スコア起点_20261024/P5_D4many_to_one_palette_LOO-corrected.json)。初回診断はlist/tuple比較不一致が判明したため採用せず、訂正版から置換した。初回ファイルは履歴保全のため残す。
- 連結箱参照の既存9汎用programを公開training LOO 1,191 foldで再評価。全foldで教師fit不成立、回答0。汎用候補として棄却し、製品コードは変更しない。提出v5と当該機構・依存ファイルのSHAを固定し、公開training以外を読まない再実行scriptと集計を[連結箱参照LOO証拠](証拠/ARC2_公式スコア起点_20261024/P5_連結箱参照_LOO.json)へ保存。
- テンプレート穴埋めの曖昧候補を教師例で分割方向 (`split_mode`) ごとに絞る汎用仮説を、固定training prior 2例を含む同じ1,191 LOO foldで比較。現行の一意候補baselineは0回答、候補版も0回答で増分なし。検証scriptとhash付き集計を[split-mode LOO証拠](証拠/ARC2_公式スコア起点_20261024/P5_template_split_mode_LOO.json)へ保存し、不採用。製品コード変更なし。
- 背景色bboxを切ってからD4を行う案は、同じ公開training LOOで現行13回答/13正答に対しfallback増分0。bbox単独は1回答が現行と衝突して誤り、優先fallbackなら現行13件を保つが増えないため不採用。[D4 bbox LOO証拠](証拠/ARC2_公式スコア起点_20261024/P5_D4_bbox_crop_LOO.json)。

## 日次記録の必須項目

各日、Kaggle基準日とJST、前回/最高score、改善仮説、変更点、同条件ローカル比較、回帰、Notebook/ソース/JSON SHA、当日枠、提出ref・受理/失敗状態、score/Pending、次の作業と提出可能時刻を追記する。曖昧な提出応答では再送せず履歴を照合する。順位やscoreを推定・捏造しない。

自動再開機構はCodex heartbeatで本台帳を読み込むよう設定する。セッションが切れた場合は、ここにある最終状態と `Kaggle操作.py 履歴` を照合してから再開し、同日二重提出を防ぐ。

## 2026-10-23 D4の支持数2 ablation

格子D4教材の最小支持数を3から2へ一箇所だけ変えた隔離probeを実施した。HDS契約と同じく残る2教師入力が異なるLOO fold 1,725件で19予測が発火し、18正答・1誤答。支持3以上の1,191 foldでは既存ゲートと出力が全件一致し、13予測全て正解だった。

該当19 foldだけ現行HDSへ仮統合すると、D4 familyは19件全て同値採用され、誤答1件も断定出力した。公式evaluation/test challengeでは支持2条件のfitは0、候補増分も0で、test側既存D4候補2件は出力差なし。現行閾値を保ち、提出コードへ統合しない。証跡は[D4支持数2-不採用.json](証拠/ARC2_Kaggle日次提出_20261023/D4支持数2-不採用.json)。

| 2026-10-23 | M5 標識軸転写の共通色枝刈り | 厳密必要条件で360→教師共通paletteの候補だけ評価。LOO 2,916 row完全一致、時間924.088→119.406秒。公式challenge入力・全adapter出力も同一。 | 公式提出なし。ref `57560705` がUTC当日枠を使用済み | local JSON SHA `78e596…3cd5b026`のまま、fallback256。Notebook v5 COMPLETE、実行359.332秒（v4より125.208秒長く、Kaggle時間短縮は未確認）。証跡は[枝刈り検証](証拠/ARC2_Kaggle日次提出_20261023/標識軸転写共通色枝刈り-検証.json) | local commit `2759d39`、Notebook v5 COMPLETE。出力SHA `78e596…3cd5b026`はlocalとbyte一致。詳細は[KaggleNotebook-v5検証](証拠/ARC2_Kaggle日次提出_20261023/KaggleNotebook-v5検証.json)。公式提出可能枠は2026-10-24 00:00 UTC以降。実提出前に当日rule・履歴・参加状況を再確認 |
| 2026-10-23 | M5 全HDS第2候補の全域LOO評価 | 公開trainingの1,191 unique fold。初回20秒制限で1,178 complete/13 timeout、13件を60秒で再試行し全件complete。診断上の主出力一致21のうち8はidentity fallbackの偶然一致。実solver回答は13件すべてD4で完全一致、第2候補増分0。 | 公式提出なし。ref `57560705` が当日枠を使用済み | 第2候補増分なし、13 retry全てsolver回答/候補なし。製品変更なし。hidden/evaluation解答未読。 | 第2候補仮説は不採用。次のUTC日付に公式rule・履歴・提出枠を再確認。証跡は[全域LOO](証拠/ARC2_Kaggle日次提出_20261023/全HDS第二候補-全1191fold-LOO.json) |
| 2026-10-23 | M5 全HDS最低支持2以上のLOO（進行中） | 公開training 2,916 foldを20秒/foldで評価。support==2は1,725、support>=3は1,191。21:46 UTCのJSONL snapshotは1,711 fold（1,689 complete、22 timeout）。timeout22件は7課題に集中（task別5/4/4/3/3/2/1 fold）。primary exact22件のうち7件はidentity fallback一致。solver実回答15件は全てprimary exact（支持数3のD4が9件、支持数2の疎点graph転写が3件、十字形態着色が3件）。distinct second candidateは0 fold、selected second exact 0、incremental pair exact 0。旧support3 raw runとtraining SHA/ID除外条件は一致し、共有686 foldの共通診断値に不一致0（実行順・所要時間を除外）。比較は部分範囲のため全run後に再集計する。 | 公式提出なし。最新ref `57560705` が10/23枠を使用済み | product solver不変。hidden/evaluation解答未読。runner commit `370b267`。 | session 33524をpollし同一run継続。全件完了後、支持数別評価・timeout再試行・公式test入力影響を監査 |
| 2026-10-23 | M5 Kaggle v5 live recheck | 公式ルール・timelineを再確認：1日最大1提出、最終選択最大2件、Entry deadline 10/26 23:59 UTC、Final deadline 11/02 23:59 UTC。履歴最新ref `57560705` は2026-10-23 12:25:06.577 UTC、COMPLETE/public 0.00。kernel `tecchannn/arc2-codex-main-baseline-v1` v5もCOMPLETE、失敗詳細なし。 | 公式提出なし。10/23枠使用済み。24h間隔を守る次回最早時刻は10/24 12:25:06.577 UTC（当日にrule/history/quotaを再確認）。 | Notebook実行は大会提出ではない。前回取得outputはsubmission SHA `78e596…3cd5b026`、240/259。 | 次の提出時に候補出力・sample形式・kernel完了・参加・当日枠・24h間隔を再検査し、同日1回だけ公式提出 |

## 2026-10-24 全前景平行移動候補のローカル受入

公式スコア起点 `57576155` は 2026-10-24 00:34:15.171685 UTC 時点で `COMPLETE / 0.00`。直前の `57560705` も `COMPLETE / 0.00`。10/24 UTC の日次提出枠は `57576155` で使用済み（受付 00:12:39.158567 UTC）のため、本候補では再提出していない。公式記録は[提出-57576155](証拠/ARC2_公式スコア起点_20261024/公式提出-57576155.json)と[スコア観測-57576155](証拠/ARC2_公式スコア起点_20261024/公式スコア観測-57576155.json)。同一IDの次回再照会予定は 01:34:15.171685 UTC。

新しい汎用教材は全前景を色を保ったまま一定量だけ平行移動する教師規則を実装し、支持数3、教師の一意性、形状・色の有効性、盤面外移動を検査する。v5 D4を固定基準にした公開training LOO 1,191 fold で、基準は13回答・13完全一致・0誤答。候補は4件を追加回答し4件完全一致・0誤答、基準回答との競合0。全HDSへの統合診断では候補4 foldのうち3件が回答・候補一致、1件はHDS排気ゲートにより保留した。公式test challenge 240課題/259入力では1課題に2候補出力があり、全HDSは2件とも候補と一致、保留・競合0。評価解答は読まず、課題ID・格子も証拠へ保存していない。正解性は未確認なので公式性能改善とは扱わず、台帳判定はローカル候補のレビュー対象にとどめる。[LOO証拠](証拠/ARC2_公式スコア起点_20261024/P5_global_translation_LOO.json)、[HDS統合証拠](証拠/ARC2_公式スコア起点_20261024/P5_global_translation_HDS_integration.json)。

Kaggle bundle はdirty source `dae0a5dbe124a0c4a01bd69a26dda0036d0379e0` と HDS submodule `f3283f727488ad98fe575ea6a5ac981e4a188e49` から生成。274 source files、payload/bundle SHA-256 `08d0c1f42d2d6ad0169bba70dd6e6a1b34697a7359c808d8d8b9b6739545bd0b`。manifest内の新教材SHAは製品ソースと一致し、評価解答・evaluation名に該当するファイルは0件。`solve.py --preflight` は `ok / prior_examples=2`。公式challengeの該当課題をbundle内 `--worker` でも実行し、2出力とも統合HDS候補と一致した。Pytestは92 passed・29 subtests passed、対象Ruffと `git diff --check` はPASS。大会提出・新スコア取得は未実施。

追記：同一ref `57576155` を監視scriptで2026-10-24 01:34:26.521420 UTCに再照会し、`COMPLETE / 0.00`、数値score維持を確認。新規提出なし。次回照会予定は02:34:26.521420 UTC。[追跡証拠](証拠/ARC2_公式スコア起点_20261024/公式スコア観測-57576155.json)

追跡記録の所在補足：上記JSONは初回の00:34 UTC観測を不変保存したもの。01:34 UTC再照会は追記型[運用チェックポイント](ARC2_公式スコア運用チェックポイント.jsonl)の最新レコードに記録した。

## 2026-10-24 Kaggle v6実行・出力照合

Kaggle private kernel `tecchannn/arc2-codex-main-baseline-v1` のversion 6を01:49:22 UTCに送信し、01:58:22 UTCに `COMPLETE` を確認。Kaggleの整数version指定でv6出力を取得し、公式public challenge 240課題・259入力に対するローカルbundle出力と `submission.json` がbyte単位で一致した。Notebook SHA `d36d197a4690673ea411c169126f8a357ea8c2bfa261d926b721b7e9fbefc325`、metadata SHA `d7de070ae4379246d8e26eece0ffe656ad44ba30fdc853bdc0af0957bc8a3a04`、出力SHA `c34dcdd39e1afacba8c2fe992ffd93378c92bbbde3885a58f43f3fd02253bcb2`、実行350.365秒、fallback254。結果はv5の保存出力と同じ入力で比較し、2行だけ変化、fallback256→254。評価解答は未読なので正誤・公式score改善は未確認。

01:58:26 UTCの公式提出履歴は最新ref `57576155 / COMPLETE / 0.00`のまま。日次枠使用済みで、v6はNotebook実行であり大会提出ではない。次の同一ID照会予定02:34:26.521420 UTC。詳細は[Kaggle v6照合証拠](証拠/ARC2_公式スコア起点_20261024/P5_global_translation_kaggle_v6_check.json)、追記履歴は[運用checkpoint](ARC2_公式スコア運用チェックポイント.jsonl)。

## 2026-10-24 特定色群の平行移動仮説

教師例で背景以外の同じ色群だけを一定量移動し他色を固定する仮説を、支持数3の公開training LOO 1,191 foldで隔離評価した。色群候補は0回答・増分0。比較基準のD4は13/13正答、既採用前景全体移動は4/4正答のまま。仮説を不採用とし、製品コードは変更しない。評価解答・課題ID・格子は読取・保存していない。[特定色群LOO証拠](証拠/ARC2_公式スコア起点_20261024/P5_color_group_translation_LOO.json)。
- foreground-copy仮説を公開training LOO 1,191 foldでprobeした。全前景の複製は候補0、誤答0、増分0。単一4連結成分の複製も候補0。いずれも実装・公式challengeへの適用なし。[全前景複製](証拠/ARC2_公式スコア起点_20261024/P5_foreground_copy_translation_LOO.json)、[成分複製](証拠/ARC2_公式スコア起点_20261024/P5_component_copy_translation_LOO.json)。
- 同じ4連結成分に対する固定ベクトル移動仮説は、支持3以上の公開training LOO 1,191 foldで4回答・4完全一致・誤答0だったが、全て既存の全前景平行移動と一致し、増分0・競合0。重複規則として棄却し製品コードは変更しない。[成分移動](証拠/ARC2_公式スコア起点_20261024/P5_component_move_translation_LOO.json)。challenge正解未読、公式スコアへの影響未確認。

## 2026-10-26 v16 周期タイルD4候補のローカル評価

- ARC26 v5を正本としてARC2最適化を継続。教師例だけで倍率・タイル位置別D4変換を確定し、全教師を再現できる場合だけ候補出力する汎用教材をHDS候補収集へ追加。問題ID・hash分岐なし。
- 公式ARC-AGI-2 trainingのpaired LOO: 適格2916 fold中、候補適合63 fold。baseline 3/2916 exactからcandidate 63/2916へ、+60 exact、regression 0、worker error 0。19課題で適合。
- ARC2 challenge 240課題/259例のローカル比較: v10保存出力5課題/6例から、周期候補の実adapter出力を組み込んだmatched compositionは8課題/9例。+3課題/+3例、新規正解3課題、regression 0。全240 IDが公開training元ファイルと重なるため、正解ラベルは全予測保存後のオフライン照合だけに使用。runtimeには渡していない。これはローカルproxyであり公式スコアではない。
- 適合3課題/3例はversioned Kaggle adapter bundleで実行し、fallback 0。v16 bundle SHA256: f2d7d7d84429be67cc80a7bce6e6df6123e9ff5bf38138204e1db928dfea825。全240の統合runtimeは10分上限で中断し、完走出力なし。したがってchallenge比較はv10出力と適合3課題の実adapter出力を合成したmatched compositionとして記録。
- 周期タイルの色写像拡張、単純変換、特徴近傍の追加候補は、baseline超過なし。追加候補に寄与しない汎用事前記憶は実装から除去。
- 検証: 対象pytest 15 passed (7.93s)、関連4 Pythonファイル py_compile PASS。公式提出・Kaggle quota使用なし。candidateの公式スコアはUNKNOWN_NOT_SUBMITTED。
- 集約証拠: [ARC2-periodic-tile-acceptance-20261026.json](証拠/ARC26-UNIFIED/ARC2-periodic-tile-acceptance-20261026.json) (SHA256 2ee14aa4a0d773e8b3ca6bcd62f1aa6ade2cc0bac94b8aa91c1cb4db316a7603)。この候補はローカル最適化の継続対象として保持する。

## 2026-10-26 補足: 補助候補probeの再現集計

- simple transformとfeature-neighborのchallenge 240課題probeを、集約値だけ保存するrunnerで再実行。各候補の予測を全件生成・保持した後に公開training出力を開き、offline照合。課題別ID・予測格子・正解格子は証拠ファイルへ保存していない。
- simple transform: 3例を予測し3例exact。attempt_2としてbaseline attempt_1を保った場合、5/240課題・6/259例のbaselineから変化なし、新規正解0、後退0。
- feature-neighbor: 5例を予測し2例exact。同じattempt_2比較で5/240課題・6/259例から変化なし、新規正解0、後退0。
- このraw候補probeはHDS内の候補採用gateと同値ではないため、統合runtimeの性能根拠に加えず、両機構は今回の採用候補に含めない。
- 再現runner: [ARC2-aux-candidate-probe-20261026.py](証拠/ARC26-UNIFIED/ARC2-aux-candidate-probe-20261026.py) (SHA256 3ab0ca929eca34f6b778a6a1866d6931f2df1f5c1f56d652d55918352e05e030)。集約結果: [ARC2-aux-candidate-probe-20261026.json](証拠/ARC26-UNIFIED/ARC2-aux-candidate-probe-20261026.json) (SHA256 0239ab1547f9f266599a0bf4319e8596f26c5de3ae94c9acb173396d24c0758b)。

## 2026-10-26 証拠hash訂正

- acceptance JSONの説明を「追加runtimeコスト」から、集計で確認できる「スコア改善なし」に限定して修正。集計値は不変。最新SHA256は 092fa7f6c15fca38e7314cc6729cb7c6baa0cb98ae03978fdafe5a282b4005c8。直前の台帳記載hashは修正前の版。


## 2026-10-26 v18 複合幾何候補をattempt_2専用で評価

- v17のHDS内統合は全240件で8→9課題、9→10例だったが、attempt_1を1例変更し、distinct attempt pairは0のままだった。HDS本体はv16時点へ戻し、複合幾何候補をKaggle adapter内で第2候補だけに使う形へ変更。既存attempt_1と既存の別候補を優先し、全教師に適合するcrop+D4+scale/tile/downscaleプログラムが既存attemptと異なる場合だけ候補へ加える。
- 公開ARC-AGI-2 training paired LOO: 適格2,916 fold中8 foldで候補fit。baseline 2 exactからcurrent 8へ、+6、新規正解6、退行0。attempt_1変更0、attempt_2変更8、distinct pairは2→8。held-out出力は全予測後に照合し、task別予測・正解は保存していない。worker error 0。
- challenge matched impact評価: v16全240課題/259例の実runtime出力は8課題/9例。v18 versioned bundle workerを候補がattempt_2を変えうる全課題に実行（1課題、worker error 0）し、他の課題は変更なしとしてv16出力を合成。9課題/10例、+1課題/+1例、新規正解1、退行0。attempt_1変更0、attempt_2変更1、distinct pairは0→1。これは全240件のv18 runtimeではなく、全影響課題をversioned workerで実行したmatched composition。公式スコアではない。
- 検討して不採用: HDS内統合v17はprimary変更を避けるため不採用。入力そのままのhedgeはduplicate pair 11件をdistinctにしたが正答増分0。crop-only拡張はLOO 36 fitで+6 netながら1 regression、challengeで新規増点0だったため撤回。現行複合幾何moduleはv17検証済みSHAへ復帰。
- 検証: 対象pytest 20 passed (8.83秒)、py_compile PASS、git diff --check PASS。保護ファイル AGENTS.md / 制御/現在状態.json は変更なし。Notebook/kernel編集、公式Kaggle提出、quota使用なし。公式スコアは UNKNOWN_NOT_SUBMITTED。
- v18 build: payload SHA256 cbc182270d1edfd6637ec3ecb8f36205a9f52e0e6ede53f149f54eade68562d1、build-manifest SHA256 c089e410c9cc3182b674285b68900c2bd38eabf4c5593163e706b2a4ff2ef41b、280 source files。HDS connector SHA256 69ba1aa8f428a108624ae871672496f8b0bf2746b93f96f65d1a0f78d3c0d1fe。
- [second-only paired LOO](証拠/ARC26-UNIFIED/ARC2-composite-geometry-attempt2-only-paired-LOO-20261026.json) SHA256 2bd8b6df36ddcce15a6181d1ff13cacb99d578671480b422ff267bf3db0076e5。 [v18 matched impact scorecard](証拠/ARC26-UNIFIED/ARC2-v18-composite-attempt2-impact-scorecard-20261026.json) SHA256 634ed4363d0eb24ada69aae0777fa3d69ad5a8d171ce741a892b2fd5fccb548c。
- 次はsecond-only候補を別の汎用規則で増やし、paired LOOと影響範囲のversioned worker比較を通してから採用する。


### 2026-10-26 background crop-policy ablation

- 0色/外周最多色を背景crop規則へ追加したprobeは、challengeで候補1例・exact1だったがv17 attempt_1と同一で、attempt_2差分・正答増分とも0。
- second-only paired LOOは適格2,916 fold中10 fit、baseline 4 exactからcurrent 10へ+6、新規6、退行0、attempt_1変更0、attempt_2変更8、distinct pair 4→10。元のdominant-only版は8 fit、baseline2→current8で同じ+6だった。新規2 fitはscore deltaを増やさず、probe所要は279.891秒。候補空間の拡大を採用せず、複合幾何moduleをv18固定bundleと同じSHA256 b7ee7d9c9ccc3767f47dccdef25b378c961a8e150f145fc1c11860e5e4ac39へ戻した。
- [crop-policy paired LOO](証拠/ARC26-UNIFIED/ARC2-composite-geometry-crop-policy-attempt2-only-paired-LOO-20261026.json) SHA256 f72cfaf261eb4f3f354954ac9d28258bfbc048b1c9ef31cba5bfcc83bc39a2ea。 [challenge crop-policy probe](証拠/ARC26-UNIFIED/ARC2-composite-geometry-crop-policy-attempt2-probe-20261026.json) SHA256 38303a6a7308c7e182e9dd9eac5875a5c1c39ef38609bdfb5017a9bd41d91a2b。
- 元のv18 second-only codeへ戻した後の最終対象確認: pytest 20 passed (7.68秒)、py_compile PASS、git diff --check PASS。

## 2026-10-26 追加attempt_2仮説の比較

- 教師全例で一致する全体D4変換が複数ある場合の代替候補は、challenge 240課題/259例のうちD4適合2例・複数出力0例。distinct pair 0→0、正答8課題/9例のままのため不採用。[probe](証拠/ARC26-UNIFIED/ARC2-d4-alternative-attempt2-probe-20261026.json) SHA256 `823a07602360fd98c540c5a667a531da921120bed68f45d14ed455e98fef392b`。
- 背景crop後に位置別D4タイルを学ぶ仮説は、production候補モジュールのpaired LOOで2,916適格fold中14 fit、baseline 11→14（+3）、退行0。attempt_1変更0、attempt_2変更3。[production LOO](証拠/ARC26-UNIFIED/ARC2-cropped-periodic-d4-production-paired-LOO-20261026.json) SHA256 `d36e2a973de8286d2b28c67af7f74c0219d179bc9d86984bf3a26ab029d84cc3`。
- ただしv18候補と合わせたchallenge比較はv16 8/9からv18 9/10、追加候補込みも9/10で増点0。challengeで適合した候補も既存複合幾何候補の選択と重なった。v18相当のpaired LOOでも14→14、増分0・退行0。既存候補に対する増分がないため本番コードへは採用せず、実験runnerと集計証拠だけ保持。[challenge probe](証拠/ARC26-UNIFIED/ARC2-cropped-periodic-d4-challenge-probe-20261026-production-module.json) SHA256 `0e93d86db244d4f6f99df9c5044e2f24a7aa1f8efcc2fd91d81daf5d7695ba0c`; [v18 incremental LOO](証拠/ARC26-UNIFIED/ARC2-cropped-periodic-d4-v18-incremental-paired-LOO-20261026.json) SHA256 `e23baccc450d80942358d123a312cf9f155815ae8b2f4fe45270ff1db2df325b`。
- 最終候補コードはv18に復帰（Kaggle adapter SHA256 `c5b9c76f68b950b16e0843b57ba9ce2771e958b4e06905427697dd190a55f555`、HDS SHA256 `69ba1aa8f428a108624ae871672496f8b0bf2746b93f96f65d1a0f78d3c0d1fe`）。Notebook/kernel編集、公式提出、quota利用なし。公式scoreはUNKNOWN_NOT_SUBMITTED。
### 2026-10-26 C2-066を第2候補として評価

- C2-066複合前景D4・色写像・平行移動をv18のprimary保持・attempt_2専用で比較。公開training paired LOOは2,916適格fold中8 fit・8 exactだが、v18 baseline/currentとも8 exactで増分0、退行0、attempt pair変更0。欠損secondをprimary複製として扱う提出形式で正規化済み。[paired LOO](証拠/ARC26-UNIFIED/ARC2-c2-066-attempt2-v18-paired-LOO-20261026.json) SHA256 `f0575e82c0ec2ca893046036bb068f6537ca6fc9b1d9b5916ea284fe3c972570`。
- challenge 240課題/259例ではC2-066 fit 2例、primaryと異なる候補0。v18再構成9/10から変化なし。第2候補としても既存出力の重複のため不採用。[challenge probe](証拠/ARC26-UNIFIED/ARC2-c2-066-attempt2-challenge-probe-20261026.json) SHA256 `89eb821cafcdb3f78015b5eada169e919e4608a5bc2c346393f6fa86831b9682`。
- production code変更なし。公式提出・quota利用なし。次はprimaryのfallback群を公開training LOOで分解し、重複しない予測機構を探す。

## 2026-10-26 v19 局所近傍候補をattempt_2へ追加

- 公開training paired LOO 3,232 eligible foldsのうち、同形状教師から3x3近傍→中心色の一意規則を得た551 foldを現行v18 workerと照合。baseline 13 exactから候補併用27 exactへ+14、新規正答14、退行0。教師・出力格子の形がqueryと異なる例は除外し、未知・競合contextは入力色のまま保つ。
- 初回LOO実行はsystem Pythonを使い、HDS workerがModuleNotFoundErrorで失敗したため無効扱い。`.venv/Scripts/python.exe`で再実行し、worker errors 0を確認した値だけを採用。
- adapterでは既存HDS第2候補とsimple transformを維持し、attempt_2がprimaryと重複する場合だけ新候補を追加。attempt_1は変更しない。
- v19 Kaggle形式bundleを生成しpreflight `ok`（template examples 2）。bundleの全240課題/259例runtimeを完走、784.297秒、fallback 249。v18 matched compositionは9課題/10例、v19 full runtimeは10課題/11例。差分は+1 solved task / +1 exact example、task regression 0、attempt_1の変更0、attempt_2の変更50。公式challenge正解は公開trainingからruntime完了後に照合し、task ID・格子・task別結果はscorecardへ保存していない。
- ローカル評価であり公式Kaggle scoreではない。公式提出・quota使用なし。次は `.venv` Kaggle CLIで既存公式記録をread-only照合する。v19は未提出。
- 実装: [局所近傍変換候補.py](../接続/ARC2/局所近傍変換候補.py)、[Kaggle提出.py](../接続/ARC2/Kaggle提出.py)。LOO: [v18 paired LOO](証拠/ARC26-UNIFIED/ARC2-shape-filtered-local-context-v18-LOO-venv-20261026.json)。全runtime scorecard: [v19 scorecard](証拠/ARC26-UNIFIED/ARC2-v19-local-context-full-runtime-scorecard-20261026.json)。bundle: `v19-local-context-second-20261026`, payload SHA256 `dfe30eb9308aef722d2756bf4d26868b5bbf21039bcfbcb6e`; submission SHA256 `171dbfcafa394f36dfdd79914f3b1c730e293003595a7563c620eb831a127c4f`.


### 2026-10-26 v19 payload hash correction

- 直前項目に記載したpayload SHA256に転記誤りがあった。build manifestとbundleの正しいSHA256は `dfe30eb9308aef722d2756bf4d26801b21f42a70e56868b5bbf21039bcfbcb6e`。submission SHA256 `171dbfcafa394f36dfdd79914f3b1c730e293003595a7563c620eb831a127c4f`は正しい。


### 2026-10-26 近傍候補ablationとKaggle CLI再設定

- v19 full-runtime出力に対し、3x3 ring8・orthogonal4・diagonal4・radius2 crossの近傍規則をchallengeで評価。fit数は63/67/65/68だが、各variantともv19から新規exact task/grid 0、退行0。追加候補は不採用し、productionはv19のまま。
- `.venv`にKaggle CLI 2.2.5を設定。`ensurepip`でpipを追加し、欠損metadataの既存残骸を避けてwheel導入。既存ローカル認証でARC2/ARC3のhistory・submission-limits読取成功。認証値は表示・保存せず、提出/Uploadなし。
- ARC2 history最新 ref 57646990 (`ARC26 v5 v11 score measurement`) は `PENDING`、public/private scoreなし。limit API値は `numToday=1,numTotal=10`。直前の数値はref 57611018 `COMPLETE / 0.00`。
- ARC3 history最新 ref 57612586 は `COMPLETE / public 0.03`、C1-018 ref 57577905 は `COMPLETE / public 23.86`（private scoreなし）。limit API値は `numTotal=7,numAllowedNow=1`。submission historyにはv23またはC2-059 v28と明示された行なし。v28 kernel run/outputの状態は未確認のまま保持。
- CLI観測: [history and limits](証拠/ARC26-UNIFIED/kaggle-cli-history-limits-20261026T023102Z.json) SHA256 `72a69871f8fa70bc8fcafc77b3ab05814b5fa289e774d948deb80ad1bcfa9806`。近傍ablation: [probe](証拠/ARC26-UNIFIED/ARC2-neighbor-context-variants-v19-probe-20261026.json) SHA256 `c4d11c9851142d60ec55b55bc674a73007559496f2813c2c814f96f1ebff41d1`。有効LOO: [v19 candidate paired LOO](証拠/ARC26-UNIFIED/ARC2-shape-filtered-local-context-v18-LOO-venv-20261026.json) SHA256 `0712a78f0bde43bf872a3d5b5c008f42e9e16b14e8e78c7addfc3748394d2b88`。full-runtime scorecard SHA256 `9f30a1d3d6501d5ca34f95cbe8a9eb13c419ad5a21bfea1172d5bc876b399ecc`。


### 2026-10-26 v19後続候補の比較

- サイズ横断の同一タスク見本プール規則をprobe。LOO候補正答は現行同サイズ14/3232に対し、全サイズsupport>=1で30/3232、support>=2で23/3232。ただしv19の公開challenge出力259例に対する追加正答はいずれも0、退行0。LOO単体差をchallenge改善と扱わず、統合しない。
- 同じ3x3規則を複数回適用するprobeでは、step2/step3のLOO正答0、stableは13件（直接適用14件）。v19 challenge上も新規正答0、退行0。統合しない。
- 現行候補はv19のまま。直近成立した比較はv18 9 tasks/10 grids → v19 10 tasks/11 grids、+1 task/+1 grid、退行0。これは公開ラベルによるローカル評価で、公式Kaggle scoreは未提出のためUNKNOWN。
- probe evidence: pooled-shape [report](証拠/ARC26-UNIFIED/ARC2-local-context-pooled-shape-v19-probe-20261026.json) SHA256 `f53073fdecb1e775b26436e58b1c04c3c750d301d24edb7ece8a6b490d9ad5ea`; iterative [report](証拠/ARC26-UNIFIED/ARC2-local-context-iterative-v19-probe-20261026.json) SHA256 `df6458434b77c480adb3796cab2128cf918bd4b9b271931687f845d2e4e3b6fd`。


### 2026-10-26 v19 候補族差分と近傍pool比較 (02:53 UTC)

- pooled-local-contextをv19のattempt_2選択候補と置換するchallenge 240課題/259例評価ではsupport1が新規exact 0・回帰0 (既存11例/10課題を維持)、support2は1例/1課題回帰した。support1/2は採用せず、productionはv19を維持。証拠: [pool-swap probe](../証拠/ARC26-UNIFIED/ARC2-local-context-pool-swap-v19-probe-20261026.json) SHA256 `c99b6374f21928d38fa67ee7ef9ace04e006ba3870afac2a2821521527737baa`.
- HDS候補族の出力を全240課題で生成し終えた後にのみ公開test出力と照合した。9候補族のいずれもv19のattempt_1/2と異なる出力を1例も作らず、新規exact 0・回帰0。HDS候補族だけでは現行2枠の正解範囲を広げない。候補生成347.406秒。証拠: [candidate-family audit](../証拠/ARC26-UNIFIED/ARC2-candidate-family-challenge-audit-v19-20261026.json) SHA256 `882060a7a4d9a655ee94624f3e68e3d6961c12be0fec22d53142ac2b0b41e3b7`.
- 結果は公開challengeによるローカル評価で、公式Kaggle scoreは `UNKNOWN_NOT_SUBMITTED`。候補出力と正解の組は保存していない。次の探索は候補族を単に増やすのでなく、失敗課題を形状差/同形状の大誤差に分け、trainだけから未知出力を導く一般化変換の追加に向ける。


### 2026-10-26 v19 候補多数決・HDS支持2監査

- 単純変換モデルの最多票を各閾値 (支持2、50/75/90%、全会一致) でattempt_2に加えるprobe。13個の全教師適合モデルから一意topが出たのは3例だが、すべてv19候補と重複。新規exact 0、回帰0、10課題/11例を維持。証拠: [vote probe](../証拠/ARC26-UNIFIED/ARC2-simple-transform-vote-v19-probe-20261026.json) SHA256 `1ff0cb506a286dd71ad1c48c6152df294611fee13795c424eccb662070f83680`.
- HDSの最小支持数を全課題で2に固定して240課題/259例を再生成。353.204秒、直接回答候補10例、v19の2候補と異なる回答0。候補多数決でも新規exact 0、回帰0。閾値緩和のみでは増点しない。証拠: [support2 probe](../証拠/ARC26-UNIFIED/ARC2-hds-support2-v19-probe-20261026.json) SHA256 `333fb974631d14b966ad0af05ad6e8c34ec056450c668efafdbcfbce786d6237`.
- 現行v19監査のHDS保留は観測不足249例、隔離中原理2例。候補族追加・閾値緩和・単純変換多数決は現行候補を超えない。v19コードを維持し、出力形状をまたぐ構造変換など、未知test格子へ一般化する新しい機構を探索する。公式Kaggle scoreは `UNKNOWN_NOT_SUBMITTED`。


### 2026-10-26 v20 教師適合型 object extraction 候補

- 汎用機構 `物体抽出候補.py` を追加。教師例から最大/最小面積・外接箱・位置などで一意に選ぶ前景成分を学び、切出し、D4変換と一貫した色写像をtest入力へ適用する。2モデル以上の一意topだけを出力し、runtimeに課題ID・hash・正解を渡さない。既存の第2候補が第1候補と重複する時だけ補充する。
- ARC2 training paired LOO candidate-only: 適格2,916 foldでidentity基準10 exactからsupport2 top候補43 exactへ+33、後退0。さらに現行v19 adapterとのmatched候補fit 48 foldではbaseline 17 exactから33へ+16、後退0、worker error 0。後者は候補fit foldのみを両版で同条件実行した増分。証拠: [candidate LOO](証拠/ARC26-UNIFIED/ARC2-object-extraction-paired-LOO-20261026.json) SHA256 `61927db2b2ca15d9ad48894975165a9e27f47689b863f96856f1f98d79c45680`; [matched v19 LOO](証拠/ARC26-UNIFIED/ARC2-object-extraction-v19-matched-paired-LOO-20261026.json) SHA256 `388557322048954d54fd0a437516f6cefdbd024cab1f7e764d4ef7bde27f2b0d`.
- 公開challenge 240課題/259例 matched evaluation: v19 10課題/11例から12課題/13例へ+2/+2、後退0。変更対象2課題は統合adapterで実行しworker error 0。v20 Kaggle形式bundleからも同じ2課題を実行し12/13を再現、残り238課題はv19出力を保持するmatched composition。正解は全予測生成後にのみ照合し、課題別予測・正解は保存しない。証拠: [duplicate-slot challenge probe](証拠/ARC26-UNIFIED/ARC2-object-extraction-v19-deployable-probe-20261026.json) SHA256 `6d6b93f83210379272271db903957f3ff33e2ab3789866b6a8b9c13ccc421ff2`; [integrated adapter](証拠/ARC26-UNIFIED/ARC2-object-extraction-v19-matched-challenge-20261026.json) SHA256 `e34bd5f39d46bf8bdf721876137b4882cc3222455185d8550b18c857078a7da1`; [v20 bundle](証拠/ARC26-UNIFIED/ARC2-object-extraction-v20-bundle-matched-challenge-20261026.json) SHA256 `6f5b193aebf3ca27be6bc3db9ec56953ddbe370224fe2055f86c1aa7efd7b35d`.
- Bundle: 282 source files; payload SHA256 `407dc55dcacd408451997afc098e45aadc9b69dde828a9c18e4c7d173d6df43b`; Notebook SHA256 `2187bd3a99509885926fe0d7a94f6ff4d1ef5210faaef5d350894bedd0877b4d`; `--preflight` status `ok`, template examples 2. Payload includes the object module with SHA256 `03e38ebbbf01e2444278fc419a22f13d9b23b34ce9d3abc5b8fdb04ee9c6781f`.
- Regression tests: 24 passed (object extraction, simple transform, composite geometry, Kaggle adapter). `git diff --check` PASS; `AGENTS.md` and `制御/現在状態.json` unchanged. Kaggle submission/quota was not used; official score remains `UNKNOWN_NOT_SUBMITTED`.

### 2026-10-26 台帳リンク訂正

- 直前に追記したv19監査行の相対リンクに余分な `../` があった。正しいprefixは `証拠/ARC26-UNIFIED/`。pool-swap: [corrected link](証拠/ARC26-UNIFIED/ARC2-local-context-pool-swap-v19-probe-20261026.json); simple-vote: [corrected link](証拠/ARC26-UNIFIED/ARC2-simple-transform-vote-v19-probe-20261026.json); support2: [corrected link](証拠/ARC26-UNIFIED/ARC2-hds-support2-v19-probe-20261026.json)。evidence bytesと記録済みhashは不変。

### 2026-10-26 v21.1 外れ値物体選択をattempt_2へ追加

- 物体抽出候補に面積・形状・周長・穴・対称性・縦横比・充填率・外周接触などの汎用属性を追加。属性値が同値群から一つだけ外れる場合を教師例間で適合させ、2モデル以上の一意topだけを候補化する。従来v20候補が第2枠を埋めない場合だけ遅延評価して選ぶ。課題ID/hash/正解の分岐なし、attempt_1は維持。
- ARC2 training 2,916適格foldのうち候補提案41 foldをv20/v21.1の実行bundleでpaired評価。v20は26/41 exact、v21.1は35/41、+9、新規正解9、退行0、第2枠変更12。両bundleのfallbackは各26件。held-out出力はcandidate/runtimeへ渡さず、fold別予測・正解は保存しない。[exact-bundle paired LOO](証拠/ARC26-UNIFIED/ARC2-object-outlier-v21.1-bundle-matched-LOO-20261026.json)。
- 公開challenge 240課題/259例のmatched compositionはv20 12課題/13例からv21.1 13課題/14例へ+1課題/+1例、退行0。v20対象2課題、v21.1対象3課題を各versioned bundleで実行。第2枠変更1、runtimeはtest入力のみ受領し、正解は両bundle終了後に照合。[bundle challenge比較](証拠/ARC26-UNIFIED/ARC2-object-outlier-v21.1-bundle-matched-challenge-20261026.json)。
- 初回統合bundleでunique selectorを学習時に誤選択する不整合を検出し、対象テストを追加して修正。最終v21.1 bundleではLOOとchallengeの両方で候補効果を再現。最終候補probe: [aggregate](証拠/ARC26-UNIFIED/ARC2-object-outlier-v21-probe-20261026.json)。初回統合比較[報告](証拠/ARC26-UNIFIED/ARC2-object-outlier-v21-bundle-matched-challenge-20261026.json)は修正前として参照専用。
- v21.1 bundle: 282 source files、payload SHA256 98e02b86a5409362502abf1c97329a53cfeb4c414b5f43344e207192931c64c7、Notebook SHA256 1f0b583fcb38ee864407cbdb1a25d461cbfbfc3ed7afde9d08cda1b49cf3eae6。preflight ok、template examples 2。対象pytest 26 passed。AGENTS.md / 制御/現在状態.json は変更なし。公式提出・Kaggle quota使用なし、公式score UNKNOWN_NOT_SUBMITTED。
### 2026-10-26 v21.1後の増分selector仮説を不採用

- 他物体とのbbox距離・隣接数・接触数を使うrelation候補は27 foldで提案し単体LOOは15 exact。現行v21.1 adapterとのpaired比較は16/27から16/27、適用2、増分0、退行0。公開challengeでも候補1例は既存第2枠と重複し、追加選択0。製品へ統合しない。[probe](証拠/ARC26-UNIFIED/ARC2-object-relational-v22-probe-20261026.json) SHA256 036e017c55cd42a0a9a2afbf9350c33c0eb3ab21b76d821eda6c901b8de070dc; [paired LOO](証拠/ARC26-UNIFIED/ARC2-object-relational-v22-paired-LOO-20261026.json) SHA256 bdf20ad0ca09176ae59524a89e9f7cf987698b400eb63585aaf09df8c266fdf5。
- object centroid-to-center、border clearance/count候補は26 fold、単体LOO17 exactだったが、現行v21.1公開challengeでは候補出力0・増分0。現行candidate pair超過は確認できず、paired LOO/production統合は行わない。[spatial probe](証拠/ARC26-UNIFIED/ARC2-object-spatial-v23-probe-20261026.json) SHA256 0d9feef6dbb2f4fcc741bc700c99fc378e4de0e2dfd24b1d9679cab7e423234.

- 証拠hash補足: final challenge JSON SHA256 ab59e8827fc191e64badc1de8bcaa547f0f6b88e0ff21b704269141582b17026、paired LOO JSON SHA256 1cebcf17a94d08a4f1f97ab36a033e8f3a090ae25988a925c9dac9e278d5b45a、build manifest SHA256 bbc0e7e5266a44aaada42f6362736a49c7e13343e5bb24b7c66f289e9719f99b。

### 2026-10-26 v21.1 full runtime and v24 palette selector (04:29 UTC)

- Exact v21.1 full runtime on all 240 public challenge tasks / 259 examples completed in 806.11 s. Matched v19 baseline was 10/240 tasks, 11/259 examples; v21.1 reached 13/240, 14/259 (+3 tasks, +3 examples), with 0 regressions. Attempt 1 was unchanged; 3 second-slot outputs changed. This is a local public-label evaluation, not an official Kaggle score. [runtime report](証拠/ARC26-UNIFIED/ARC2-v21.1-full-runtime-evaluation-20261026.json) SHA256 fa4ab7c28e64507f40a92a035a85fe361e6f0d6e6bd4f6e57d6b7da598455ba0.
- Added palette, dominant-color/count, and global palette-frequency selectors as a lazy attempt-2 fallback, only when the current second slot is empty or duplicates attempt 1. On the 40 training LOO folds proposed from 2,916 eligible folds, exact v21.1 bundle scored 30/40 and v24 scored 32/40; +2 newly correct, 0 newly wrong, 2 second-slot changes, no regression. Both exact bundles had 25 fallbacks. [paired exact-bundle LOO](証拠/ARC26-UNIFIED/ARC2-object-palette-v24-bundle-matched-LOO-20261026.json) SHA256 39f48870850beadc6ee9b2edbc14b155105123a459ba1052528d620eb7d60589.
- Across the 240 public challenge tasks, palette scan found 3 candidate examples. The exact v21.1 and v24 bundles produced identical outputs on all 3; each was 3/3 exact. v24 therefore preserves the v21.1 local result of 13/240 tasks and 14/259 examples on the public challenge. The runtime received input-only tests; labels were read after both runs. [matched candidate-task challenge](証拠/ARC26-UNIFIED/ARC2-object-palette-v24-bundle-challenge-20261026.json) SHA256 b5f09f75eb7e7d54b709d854710ec151142758843e6c033bcc58574f512bbdca.
- v24 exact bundle has 282 files, payload SHA256 60e816a1b12404893ccf4455e532896fb2da9bb81da3cd18c9ba9f00fefb7945, Notebook SHA256 0eedd88967ba70f1fdf7e3f859668eb652a27ff3965e8f056e8381c98dd657bc, manifest SHA256 6a52003b25dad93b4113c259b2d6e0f9d284161b5b78ecae544997fe11410aa1. Preflight ok with 2 template examples; targeted extraction tests 5 passed.
- A v25 probe of 13 composite shape/color/size features on those same 40 LOO folds found no proposal for the 15 duplicate second slots: v24 32/40, v25 probe 32/40, delta 0, regressions 0. Not integrated. [composite probe](証拠/ARC26-UNIFIED/ARC2-object-composite-palette-v25-probe-20261026.json) SHA256 49e8543938228388b1053f8860194ca3aafc4f71c319673e872e5f2f49908b1b.
- AGENTS.md and 制御/現在状態.json hashes match their protected baselines. No Kaggle submission or quota use; official Kaggle score remains UNKNOWN_NOT_SUBMITTED.


### 2026-10-26 v25 composite palette expansion (04:44 UTC)

- A full scan of the 2,916 eligible ARC2 training LOO folds found 43 composite-feature proposals. On those folds, exact v24 bundle scored 33/43 and exact v25 bundle scored 34/43: +1 newly correct, 0 newly wrong, one attempt_2 change, no regression. Held-out outputs were not given to proposal generation or either runtime; labels were read after both exact bundle outputs. [proposal scan](証拠/ARC26-UNIFIED/ARC2-object-composite-palette-v25-proposal-scan-20261026.json) SHA256 837d121b7155dbdc1166fa850f7ebed13262cd644dbab9ead902e42e8e904e64; [exact-bundle paired LOO](証拠/ARC26-UNIFIED/ARC2-object-composite-palette-v25-exact-bundle-paired-LOO-20261026.json) SHA256 610af5238457eb663a2ae15c79793e8ecc636f53d09b73d6e211dc8b4a6957e.
- Full public challenge input scan found 3 potentially affected examples across 3 tasks. Exact v24 and v25 bundles produced identical outputs on all 3; both were 3/3 exact. The projected full public result stays at the previously measured v21.1 local score of 13/240 tasks and 14/259 examples; no full 240-task v25 runtime was run. [matched candidate-task challenge](証拠/ARC26-UNIFIED/ARC2-object-composite-palette-v25-bundle-challenge-20261026.json) SHA256 6e377da6ce17ea02799d5110269269abbffb70d5443d1590aa41ecef873f272c.
- v25 bundle has 282 source files; payload SHA256 becbda2905f19d9d6445c75667d5d1f0eeddca593c0e3757e9c66fe8ae065e9d, Notebook SHA256 8585a8aacdd53904abd8f86b864c9491df4391f35aa780b2129c91429465319d, manifest SHA256 bc09d3caa1894df9a35ac35fffdd81cd9d4736037fae743571e2a84b54ecd0ec. Preflight ok with 2 template examples; targeted extraction tests 5 passed.
- Kaggle CLI 2.2.5 in .venv reports the existing account login. A read-only ARC2 history query showed submission 57646990 still PENDING with no public/private score. No submission or quota use was performed; official score remains UNKNOWN_NOT_SUBMITTED.


### 2026-10-26 v26 composite extremes and v27 background components (04:55 UTC)

- v26 added min/max modes for 10 composite object properties on the same 43 v25-proposal LOO folds. Exact v25 bundle baseline was 34/43; the extra selectors proposed no distinct answer on 15 duplicate attempt_2 slots, so result stayed 34/43, delta 0, regressions 0. Rejected. [v26 probe](証拠/ARC26-UNIFIED/ARC2-object-composite-extreme-v26-probe-20261026.json) SHA256 2eac457acfb29e89cb2e7e91d80bcc5f42561aa5860529ee953fb3981444a93b.
- v27 tested connected components of the majority/background color alongside normal objects, with no task-specific branching. On 42 proposals from 2,916 eligible folds, exact v25 baseline and background-augmented candidate both scored 34/42. No second-slot change, new correct answer, or regression. Rejected; production stays v25. [background-component probe](証拠/ARC26-UNIFIED/ARC2-background-component-v27-probe-20261026.json) SHA256 bbec0fb14ed5ea465833e15351c31c82cdbfb81f506afbea01555e82ad084d10.
- Neither experiment passed held-out outputs to proposal generation or runtime; fold predictions/targets were not saved. No official Kaggle submission or quota use.

### 2026-10-26 v28 object-candidate vote-ratio selection (05:33 UTC)

- When attempt_2 is still unfilled, rank distinct object-extraction, outlier, and palette candidates by top_votes / applicable_models; break ties by higher votes, then the existing family order. attempt_1 remains unchanged; no task-identity or hidden-answer branching.
- Exact v25/v28 bundle paired LOO on 43 composite-selector proposals: 34/43 -> 37/43, +3 newly exact, 0 newly wrong, 3 attempt_2 changes; each bundle had 28 fallbacks. Candidate generation/runtime used teachers and held input only; labels were read after both outputs; per-fold IDs, predictions, and targets were not saved. A base-palette selector probe also measured 32/40 -> 35/40 (+3, 0 regressions); folds may overlap the 43-fold set, so this is corroborating evidence rather than an independent validation set. [exact-bundle paired LOO](証拠/ARC26-UNIFIED/ARC2-candidate-priority-v28-exact-bundle-paired-LOO-20261026.json) SHA256 ec63298a32ad92b456e13fc4ccd2454c95b915c0fef178c8e62f234f12b18820; [base-selector scorecard](証拠/ARC26-UNIFIED/ARC2-candidate-priority-v28-independent-20261026.json) SHA256 8a04f4f624ec26661851936b381da7cf4e244fb64cc4d3e0c81de41f570f1b0d.
- Full public challenge runtime covered all 240 tasks / 259 examples: v28 scored 13/240 tasks and 14/259 examples versus v19's 10/240 and 11/259, +3 tasks/examples, 0 regressions, attempt_1 unchanged, 3 attempt_2 changes. Runtime was 770.125 seconds with 249 fallbacks. A candidate scan found 0 public examples where these three families offered multiple distinct grids; v28 therefore projects the same public result as v25 (13/240, 14/259), delta 0. This remains local public-split evidence, not an official Kaggle score. [full runtime report](証拠/ARC26-UNIFIED/ARC2-v28-full-runtime-evaluation-20261026.json) SHA256 169ace5f406914e1679a195d64e8162ef9f9a35cbccbacd9386a7cbc2b56ea6b; [candidate challenge scan](証拠/ARC26-UNIFIED/ARC2-candidate-priority-v28-bundle-challenge-20261026.json) SHA256 5c44292f493b345f134e6cba9556e1d09157e63b414842e1333eb7d7ed51bfa6.
- v28 build contains 282 source files; payload SHA256 cfe1a2de49f918e349585825f06afcce1d147c52a011046fd52a371fac45a563, Notebook SHA256 0926f55ce4afb5cfed386c7e6b5d3233cffa08a32f62faf3d21acba9930bc3ff, manifest SHA256 8bafa314ddb1e25831769d38f3e1d779fc3b6c060a002cd91caccf5e37529f17. Preflight passed with 2 template examples; targeted object-candidate tests passed (5/5). Adapter SHA256 31b5321fc6fa804747d98e26bba9c2f771fb4d07f1ab1acfac2c3b834b738045.
- AGENTS.md and 制御/現在状態.json hashes remain at their protected baselines. v28 was not submitted; no Kaggle quota was used. Official v28 score remains unknown.
- Read-only `.venv` Kaggle CLI history observation at 2026-10-26 05:35:15 UTC: existing submission 57646990 (`2026-10-26T00:14:46`, `ARC26 v5 v11 score measurement`) remains `SubmissionStatus.PENDING`; public and private scores are blank. This check used no quota; v28 remains unsubmitted.

### 2026-10-26 v29 feature-neighbor radius experiment (05:59 UTC)

- Compared the exact v28 and v29 bundles with the feature-neighbor applicability factor changed from 1.5x to 2.0x. Across 2,916 eligible LOO folds, feature-neighbor proposals rose from 132 to 139. On the 139-fold union, both bundles scored 59 exact; newly correct 0, newly wrong 0. Four rows changed (attempt_1: 4; attempt_2: 2), with no exact-score effect. Fallback count fell 32 to 28, which is not counted as a quality gain.
- Public challenge scan covered 240 tasks / 259 examples: candidate availability was 5 at both factors, newly eligible examples 0. Projected public result stayed 13 tasks / 14 examples, delta 0. No official submission or quota use; official score remains UNKNOWN_NOT_SUBMITTED.
- Rejected v29. Restored the production module exactly to the v28-bundled SHA256 `5cd2e0d39709576702dfa42474c1232ca0e14371e486ad4dfc7b35f8f0ac8726`; retained the candidate bundle and aggregate-only evidence. [paired exact report](証拠/ARC26-UNIFIED/ARC2-feature-neighbor-radius-v29-exact-paired-20261026.json) SHA256 `20ecb5c624ecb3b7f28234f8992448caad96320f2a3b81fbd76d62ca1335f449`; v29 manifest SHA256 `b251276cc44365b51ec89448f3fdb0c23411f5d19911039a3fd56cc54005d700`.

### 2026-10-26 v30 feature-neighbor rank-depth screen (06:03 UTC)

- Tested whether deeper simple-transform ranks could resolve inputs where the current simplest-rank selector abstains. On 2,916 eligible LOO folds, both selectors proposed on 132 and differed on 0. On the 240-task / 259-example public challenge, both proposed on 5 examples and differed on 0. The screen produced no changed candidate, so no exact bundle was built and production stayed unchanged.
- No official submission or quota use; official score remains UNKNOWN_NOT_SUBMITTED. [rank-depth probe](証拠/ARC26-UNIFIED/ARC2-feature-neighbor-rank-depth-v30-probe-20261026.json) SHA256 `2c8f20c51d555df38ea034d12c5267ab05a5c4a36176e7f7aa105ece257dfbc4`.

### 2026-10-26 v31 feature-neighbor all-model vote screen (06:06 UTC)

- Tested a unique plurality across every fitted simple transform for the nearest training input, with a two-vote minimum and agreement from every tied nearest neighbor. Across 2,916 eligible LOO folds, current and candidate selectors both proposed on 132 and differed on 0; across 259 public examples, both proposed on 5 and differed on 0. No exact bundle was warranted and production stayed unchanged.
- No official submission or quota use; official score remains UNKNOWN_NOT_SUBMITTED. [all-model vote probe](証拠/ARC26-UNIFIED/ARC2-feature-neighbor-transform-vote-v31-probe-20261026.json) SHA256 `ea648461721f3758a574da20ff89ae08ba265ab86eb4dc817faddce4979a9897`.

### 2026-10-26 v32-v34 global training analog screen (06:14 UTC)

- The runtime template declares 2 prior training pairs; the official training folder contains 1,000 tasks / 3,232 pairs. Screened a global input-feature nearest-transform candidate using only that training folder, excluding the entire scored task in LOO. A 2-neighbor unanimous candidate passed the exact local teacher gate on 0/2,916 LOO folds and 0/240 public tasks. Allowing one nearest example passed the local teacher gate on 0 LOO folds and 2 public tasks / 2 examples; one candidate matched a public target.
- Ran the exact v28 bundle on both changed public tasks after candidate generation. The one correct candidate was already covered by a v28 attempt; neither changed the exact score. Projected public result remains 13 tasks / 14 examples, delta 0. The global-prior candidate was rejected; production and bundle inputs remain unchanged. No official submission or quota use.
- [exact-baseline global-prior report](証拠/ARC26-UNIFIED/ARC2-global-training-feature-neighbor-v34-exact-baseline-probe-20261026.json) SHA256 `0e19be0087dce2c1dd9cdfac7a561f46efe9ddb7e039589dde0311b66ce297c3`.


### 2026-10-26 v35 v28 residual-shape audit (06:30 UTC)

- Repeated the exact v28 bundle on all 240 public challenge tasks / 259 examples with input-only test data. Its temporary submission SHA256 `54f6a303c4143f15279e2084d5ad798455e565b4d51cd6a2b226e4d4735af46a` exactly matches the prior full-runtime output. Score reproduced at 13/240 tasks and 14/259 examples; runtime 785.272 s.
- Of 245 non-exact examples, 169 had at least one candidate with the target dimensions and 76 had neither. Across the two wrong attempt slots per example, 152 had a dimension mismatch while 338 matched target dimensions; the matched wrong grids averaged 76.2066% pixel accuracy. Target shape relation to input was same for 175 examples, area shrink for 66, and area expansion for 18. This aggregate-only diagnostic points the next screen toward cell-rule alternatives, while leaving the local public score unchanged.
- Runtime received no test targets; targets were read only after completion. No task IDs, grids, predictions, or targets were saved. No Kaggle submission or quota use. Official score remains UNKNOWN_NOT_SUBMITTED. [aggregate residual audit](証拠/ARC26-UNIFIED/ARC2-v28-residual-shape-audit-20261026.json) SHA256 `F655F224E1B9E24244ECB41A86AC56C0FD50126299B6E4BD56A07168B5F3917C`.


### 2026-10-26 v36 orthogonal cell-context candidate (06:55 UTC)

- Tested a five-cell center/up/right/down/left context that requires the same unambiguous cell mapping to be supported by at least two distinct shape-compatible teacher pairs. On 218 proposal folds out of 2,916 eligible LOO folds, the exact v28 bundle was correct on 11; the candidate itself matched the held output on 2, but added 0 correct answers because neither filled a useful distinct second slot. The candidate was usable only on 15 folds where v28 attempt_2 duplicated attempt_1; all 15 were wrong candidates.
- On the 26 public examples with proposals (26 tasks; 27 total examples in those tasks), baseline exact examples/tasks were 3/2, candidate exact outputs 0, added exact examples/tasks 0, regressions 0. Rejected; no production code or bundle changed. Targets were read after both prediction sets; no per-task data saved. No submission/quota use.
- [proposal scan](証拠/ARC26-UNIFIED/ARC2-orthogonal-cell-context-v36-probe-20261026.json) SHA256 `E73424364FEFA1A15ED7946440EEEF0406E65DB5115F83242A16EBE050181455`; [exact v28 paired scorecard](証拠/ARC26-UNIFIED/ARC2-orthogonal-cell-context-v36-exact-paired-20261026.json) SHA256 `71707FE716491990E1B0BC64C7B4F5873690879B4F45C50ABAA076B311B23C56`.


### 2026-10-26 v37 neighborhood-multiset cell-context candidate (06:56 UTC)

- Tested a rotation/reflection-invariant context comprising the center color and unordered multiset of its four orthogonal neighbors, requiring an unambiguous output supported by at least two distinct shape-compatible teachers. On 186 proposal folds, exact v28 was correct on 11; the candidate produced 5 exact outputs, but 0 incremental exact answers because it did not fill a useful distinct second slot. It was usable on 21 folds with duplicate v28 attempts; none was correct.
- On 21 public proposal examples in 21 tasks, v28 scored 1 exact example/task; candidate exact outputs 0, gains 0, regressions 0. Rejected; no production code or bundle changed. All targets were read after exact predictions; no per-task data saved. No submission or quota use.
- [proposal scan](証拠/ARC26-UNIFIED/ARC2-neighborhood-multiset-context-v37-probe-20261026.json) SHA256 `398A100B94EA2051DCA38DDF023F456D0A24DB3569FD4C10456DEEB21B0FF505`; [exact v28 paired scorecard](証拠/ARC26-UNIFIED/ARC2-neighborhood-multiset-context-v37-exact-paired-20261026.json) SHA256 `0918A6A0AF0E47C9F6C9C289F5C51C1D3E70340DE45AC0B64F281683004B8AB2`.


### 2026-10-26 v38 spatial-composite object selectors (06:59 UTC)

- Combined centroid distance, border clearance/count, palette, object shape, area, perimeter, solidity, and border-touch descriptors in 12 generic unique selectors. Only 3 of 2,916 eligible LOO folds and 1 of 259 public examples proposed a new candidate.
- On those LOO proposals, exact v28 already solved 2/3 and the new selector outputs also matched 2/3; neither occupied a useful duplicate second slot, so incremental exact count was 0. The single public proposal was already exact under v28; new selector was exact but unusable because attempt_2 was already distinct. Public gain 0, regression 0. Rejected with no production change or quota use.
- [proposal scan](証拠/ARC26-UNIFIED/ARC2-object-spatial-composite-v38-probe-20261026.json) SHA256 `0C2CF002F66971BAD6AB1101493D24C7FA8C50D68F4F8762D0321DC03BD2D9F1`; [exact paired scorecard](証拠/ARC26-UNIFIED/ARC2-object-spatial-composite-v38-exact-paired-20261026.json) SHA256 `68D220EF6DEB1A00D28CF263C79FB218CB8F01ED27BA0C7C65046024AACC9D4D`.


### 2026-10-26 v39 eight-neighbor multiset cell-context candidate (07:14 UTC)

- Expanded the rotation/reflection-invariant context to the center color plus an unordered multiset of all eight surrounding cells, with at least two distinct teacher-pair support. Across 161 proposal folds, exact v28 solved 7; the candidate was exact on 0 and added 0. Thirteen proposals could use an otherwise duplicate v28 slot, all incorrect.
- On 18 public proposal examples in 18 tasks, v28 scored 1 exact; candidate outputs matched 1 target, but its only usable duplicate slot was not exact. Added 0 examples/tasks, regressions 0. Rejected; no production change or quota use. Targets were read after both prediction sets; task data was not saved.
- [proposal scan](証拠/ARC26-UNIFIED/ARC2-8-neighborhood-multiset-context-v39-probe-20261026.json) SHA256 `8192C845FB51F967C32AFEF161E9DFCF55D8D14F82281C128DAE07F5ABE17ADA`; [exact v28 paired scorecard](証拠/ARC26-UNIFIED/ARC2-8-neighborhood-multiset-context-v39-exact-paired-20261026.json) SHA256 `453F70B5822F83D64A40926C0FABADA9FF67D32B19297EE96D8F17E3B80531AA`.


### 2026-10-26 v39 eight-neighbor multiset cell-context candidate (07:14 UTC)

- Expanded the rotation/reflection-invariant context to the center color plus an unordered multiset of all eight surrounding cells, with at least two distinct teacher-pair support. Across 161 proposal folds, exact v28 solved 7; the candidate was exact on 0 and added 0. Thirteen proposals could use an otherwise duplicate v28 slot, all incorrect.
- On 18 public proposal examples in 18 tasks, v28 scored 1 exact; candidate outputs matched 1 target, but its only usable duplicate slot was not exact. Added 0 examples/tasks, regressions 0. Rejected; no production change or quota use. Targets were read after both prediction sets; task data was not saved.
- [proposal scan](証拠/ARC26-UNIFIED/ARC2-8-neighborhood-multiset-context-v39-probe-20261026.json) SHA256 `8192C845FB51F967C32AFEF161E9DFCF55D8D14F82281C128DAE07F5ABE17ADA`; [exact v28 paired scorecard](証拠/ARC26-UNIFIED/ARC2-8-neighborhood-multiset-context-v39-exact-paired-20261026.json) SHA256 `453F70B5822F83D64A40926C0FABADA9FF67D32B19297EE96D8F17E3B80531AA`.


### 2026-10-26 v40 global-neighbor teacher gate (07:20 UTC)

- Relaxed v33's full teacher-consensus gate to require at least two non-held/public training examples that the training-only global feature-neighbor model predicted exactly. Candidate generation still excludes the entire scored task on LOO and uses only the official training split.
- The relaxed gate passed 0/2,916 LOO folds and proposed 0 LOO candidates. It proposed 2 examples in 2 public tasks; exact v28 paired baseline was correct on 1/2 and already had a distinct second answer on both, so candidate exactness (1/2) yielded 0 gain. Rejected; no production change or quota use. Targets were read after prediction; per-task data not saved.
- [gate scan](証拠/ARC26-UNIFIED/ARC2-global-training-feature-neighbor-v40-two-teacher-support-probe-20261026.json) SHA256 `8A34040D6D04ABA2F88D7647C6407AE4EECB92E69E867BDE15E192EF55FC8A6A`; [exact paired scorecard](証拠/ARC26-UNIFIED/ARC2-global-training-feature-neighbor-v40-exact-paired-20261026.json) SHA256 `739671C9334C37E5164572FF31F1C25AC8478FAE14078ADC352C8E4028638F44`.


### 2026-10-26 v41 global-neighbor radius 99th percentile (07:23 UTC)

- Raised the training-only nearest-input radius from p95 (0.01817) to p99 (0.05924), retaining the two-exact-teacher support gate. LOO proposals stayed at 0/2,916; public candidates stayed at 2 examples / 2 tasks with 1 exact candidate.
- Exact v28 paired run reproduced the same temporary submission SHA as v40. Baseline exact was 1/2 examples and 1/2 tasks; neither candidate could use an empty duplicate slot, so gain 0 and regressions 0. Rejected; no production change or quota use.
- [radius scan](証拠/ARC26-UNIFIED/ARC2-global-training-feature-neighbor-v41-radius-99-two-teacher-support-probe-20261026.json) SHA256 `FDF44EC3641F29B90D4E1B9107DFB09F18E786FE9F3E817A7E2E6011F1AB1DCD`; [exact paired scorecard](証拠/ARC26-UNIFIED/ARC2-global-training-feature-neighbor-v41-radius-99-exact-paired-20261026.json) SHA256 `52AFBF15D2008ED24B4B53678ADA644E4F5EA4328C1377D1E3BC37A9EA6F3E1A`.


### 2026-10-26 v42 global-neighbor one-teacher gate (07:27 UTC)

- With the p99 global-training radius, lowered exact teacher support from 2 to 1. The gate passed 0/2,916 LOO folds, and no LOO candidates existed. It proposed 3 examples in 3 public tasks; exact v28 was correct on 2/3 examples, while the candidate was exact on 1/3. Only one proposal could use a duplicate second slot and that candidate was wrong. Gain 0, regression 0. Rejected; no production change or quota use.
- [gate scan](証拠/ARC26-UNIFIED/ARC2-global-training-feature-neighbor-v42-radius-99-one-teacher-support-probe-20261026.json) SHA256 `CF5CE8B10748C076D0F7CB06FA2316F092A73527F24A6DAB94C6827A067E9FDA`; [exact paired scorecard](証拠/ARC26-UNIFIED/ARC2-global-training-feature-neighbor-v42-radius-99-one-teacher-support-exact-paired-20261026.json) SHA256 `D5E916C364F1688F14D0C65DEA12CA79C9CCF6E289ECC1C23CA1B5ADEB38BA62`.


### 2026-10-26 v43 border-majority object extraction (07:41 UTC)

- Changed object segmentation background from the full-grid modal color to the modal color among unique border cells; kept the tie-break at the lowest color and required at least two of the existing object/outlier/palette model families to agree on one distinct valid grid.
- Across 38 LOO proposals, the exact v28 baseline and candidate each scored 32 exact; one candidate was usable in an otherwise duplicate slot but did not add a correct answer. On 4 public examples in 4 tasks, both baseline and candidate scored 4/4; candidate slot was already distinct for all 4. Gain 0, regression 0. Rejected; no production change or quota use.
- [proposal scan](証拠/ARC26-UNIFIED/ARC2-border-background-object-v43-probe-20261026.json) SHA256 `0C2A85ADE98C8DECDE8C67DB3E8C413C9D29551F4B665C333C35CB699D99A120`; [exact paired scorecard](証拠/ARC26-UNIFIED/ARC2-border-background-object-v43-exact-paired-20261026.json) SHA256 `73854E3A097A3CBAC53AB4D5803BE3FFDA2AD1D8646C5B3E2A9047F751A2EE1A`.


### 2026-10-26 v44 border-background single-family candidate (07:54 UTC)

- Kept the v43 border-majority background policy and allowed a candidate when one object/outlier/palette family had the unique top grid (ties still abstain). Proposal count rose 38 to 60 LOO folds; public proposals stayed at 4 examples.
- Exact v28 was correct on 44/60 LOO proposals; the candidate also matched 44/60. Three candidates were usable in duplicate slots but none was correct. All four public proposals were already exact under v28 with distinct second answers. Increment 0, regressions 0; rejected.
- [proposal scan](証拠/ARC26-UNIFIED/ARC2-border-background-object-v44-border-background-single-family-probe-20261026.json) SHA256 `34C02CA2BC04C25C5FFCCB3CB6F8FE483A73100C6634BD5A28D5F3384CA451C3`; [exact paired scorecard](証拠/ARC26-UNIFIED/ARC2-border-background-object-v44-exact-paired-20261026.json) SHA256 `8A46ABD9394396D2F67D0596D6264F31520DEFE7BFE6F5BADF13160E7CFF4697`.


### 2026-10-26 v45 color-0 background object extraction (08:12 UTC)

- Tested generic object extraction with color 0 as the background and required agreement from at least two of the object, outlier, and palette families. Across 58 LOO proposals, exact v28 solved 47; the candidate was exact on 49, with 4 usable duplicate slots, adding 1 correct answer and causing 0 regressions.
- On 6 public examples in 6 tasks, exact v28 was correct on all 6; all candidate outputs were also exact, but none could fill a duplicate slot. Public score delta 0. Rejected for production; local public baseline remains 13/240 tasks and 14/259 examples. No official submission or quota use.
- [proposal scan](証拠/ARC26-UNIFIED/ARC2-zero-background-object-v45-probe-20261026.json) SHA256 `cdc2558e2e7b596c01356c8dbb73bec6043e1e1eb3d57d8b1a9a4e804220ccf3`; [exact paired scorecard](証拠/ARC26-UNIFIED/ARC2-zero-background-object-v45-exact-paired-20261026.json) SHA256 `8c3486ac5bd23c3ffe04c3261f23fb24643028673408394930c19487e5e34523`.


### 2026-10-26 v46 color-0 background single-family object candidate (08:34 UTC)

- Relaxed v45 to accept a distinct unique top output from only one object/outlier/palette family. This raised LOO proposals from 58 to 82. Across the 82 proposals, exact v28 solved 60; candidate outputs were exact on 62, 6 could fill duplicate slots, with 1 newly correct answer and 0 regressions.
- On 6 public examples in 6 tasks, exact v28 and candidates were all correct; no duplicate second slot was available. Public gain 0. The extra proposals did not improve on v45's LOO gain, so the broader single-family gate was rejected. No production change or quota use.
- [proposal scan](証拠/ARC26-UNIFIED/ARC2-zero-background-object-v46-probe-20261026.json) SHA256 `4390b47aca487b1b20a89fc2dea3316b49f30506057afb9d487e69c9423d5a00`; [exact paired scorecard](証拠/ARC26-UNIFIED/ARC2-zero-background-object-v46-exact-paired-20261026.json) SHA256 `e3293711510c6e02cbea61d4a5ec5352c5589553763dc1a7b0c6aa6c0eceb069`.


### 2026-10-26 v47 global cellwise color remap (08:51 UTC)

- Tested a shape-preserving global color map that must fit every teacher pair without conflicts, have at least two teachers, cover every query color, and produce a changed grid. The probe proposed 13 of 2,916 LOO folds and 1 public example.
- On 13 LOO proposals, exact v28 solved 10 and the candidate matched 10; the only usable duplicate slot was not a new correct answer. Public v28 solved the single candidate example and the candidate also matched it, with no usable duplicate slot. Gain 0, regressions 0. Rejected; no production change or quota use.
- [proposal scan](証拠/ARC26-UNIFIED/ARC2-global-color-remap-v47-probe-20261026.json) SHA256 `e3e45dc4a8753abf1385bef78e8a068b96126f25f8ab761b26aa47effdcdb90f`; [exact paired scorecard](証拠/ARC26-UNIFIED/ARC2-global-color-remap-v47-exact-paired-20261026.json) SHA256 `72ed83720d5b942b6737a9be9e0c81d071e43eebbf623d7cbe3e4f38d4db004b`.


### 2026-10-26 v48 global color remap with one-teacher folds (09:06 UTC)

- Extended the global color-remap screen to 3,232 LOO folds, including tasks whose held example leaves only one teacher. Candidate count stayed 13, and the public proposal set stayed at 1 example; the new one-teacher folds added no candidates.
- Exact v28 pairing on 13 LOO proposals remained 10 baseline exact / 10 candidate exact, 1 usable duplicate slot, 0 newly correct, 0 regressions. The single public proposal was already solved by v28, with no usable duplicate slot. Rejected; no production change or quota use.
- [proposal scan](証拠/ARC26-UNIFIED/ARC2-global-color-remap-v48-probe-20261026.json) SHA256 `61b90e32870f1ca745898c5085d38fd5a469bd80e84234edd3f4026480b5e08d`; [exact paired scorecard](証拠/ARC26-UNIFIED/ARC2-global-color-remap-v48-exact-paired-20261026.json) SHA256 `747515925c4490d9416b283b7ca7fd00fd5b6c8ad18ed4fbc9406e607db532a8`.


### 2026-10-26 v49 global color remap with unseen colors preserved (09:19 UTC)

- Relaxed the query-color coverage rule: colors absent from the fitted teacher map now remain unchanged. LOO proposals rose from 13 to 17; public proposals remained 1 example in 1 task.
- Exact v28 solved 10/17 LOO proposals; candidate outputs were exact on 10, and 2 could replace a duplicate slot, but neither added a correct answer. Public v28 solved the one candidate example; candidate was also exact, with no duplicate slot. Gain 0, regressions 0. Rejected; no production change or quota use.
- [proposal scan](証拠/ARC26-UNIFIED/ARC2-global-color-remap-v49-probe-20261026.json) SHA256 `93d136115c5b5a0fd8898cf38f13bc8fa1dd71d82873edd7b9d52ce5461c19d4`; [exact paired scorecard](証拠/ARC26-UNIFIED/ARC2-global-color-remap-v49-exact-paired-20261026.json) SHA256 `9fd26870e4c1e44c51c89aa37c068e774f16619385f0cafbbc8cebc2a851a712`.


### 2026-10-26 v14-v5-current full public runtime (08:56 UTC)

- Re-ran the frozen v14-v5-current bundle on all 240 public challenge tasks / 259 examples. It produced 8 exact tasks / 9 exact examples, with 249 fallbacks, in 758.594 seconds. Compared with the v19 local baseline (10 / 11), delta was -2 tasks / -2 examples, with two regressions and no newly correct examples; attempt 1 was unchanged and attempt 2 changed on 51 examples.
- The local output SHA256 `08d0dc111f97c9f3a909955296fc58d46ea0c4514fe66e75169526723359f017` matches the recorded output for official submission 57646990 / kernel version 11. This confirms byte-identical local output; the official Kaggle score remains unobserved here and must not be inferred from the local labels.
- The v14 bundle includes training-only generic prior memory SHA256 `66e98b7eebab697b4b6877d73af3ec6cb2529104f0386183412ac340760d422a`. Runtime received no test targets; target labels were read only after full predictions existed. The no-memory v28 bundle previously scored 13 / 14 against the same public set, but it also contains later solver changes, so this difference does not isolate the memory effect.
- Evidence: [full runtime report](証拠/ARC26-UNIFIED/ARC2-v14-v5-memory-full-runtime-evaluation-20261026.json), SHA256 `249960df1290e929e6c969f930d775b700b684378f6c06aba0d130a0bddf12a2`; bundle manifest SHA256 `3394ba9168be81c659284b57d21a5f4bf255aa5816978abd99ec2ef90b58743f`. No production code or Kaggle submission was changed.


### 2026-10-26 v50 v28 plus generic training-prior memory (09:15 UTC)

- Built a local-only v50 overlay from v28, restoring the v14 training-only generic prior memory path and its feature-distance API while retaining v28 candidate families. The bundle contains the v14 memory file SHA256 `66e98b7eebab697b4b6877d73af3ec6cb2529104f0386183412ac340760d422a`; preflight passed. No production source, Kaggle kernel, or submission was changed.
- Full runtime completed all 240 public tasks / 259 examples in 768.922 seconds. v50 scored 13 / 14, identical to v28, and produced the same output SHA256 `54f6a303c4143f15279e2084d5ad798455e565b4d51cd6a2b226e4d4735af46a`. Against v19 (10 / 11), net delta was +3 / +3 with 0 regressions. Adding the training prior did not alter the prediction file, so no score gain was established. v28 remains the current best local result.
- Runtime received no test targets; labels were read only after full prediction generation. Official Kaggle score remains `UNKNOWN_NOT_SUBMITTED` for this candidate.
- Evidence: [v50 full-runtime report](証拠/ARC26-UNIFIED/ARC2-v50-v28-training-prior-full-runtime-evaluation-20261026.json), SHA256 `c73062c772b9b8a5721e8467a8f6e285a58c6f67a81afba24ca006f57b5f7ee1`; [v50 build manifest](../出力/Kaggle/arc2-codex-main-baseline-v1/v50-v28-with-training-memory-20261026/build-manifest.json), SHA256 `47e721b91e6f17fa4a1bb0cbb23459ba06b23f8acfcb5aed6309668519d76ba2`; build script SHA256 `eae4a2fe56941337a02e00cf5d067c0f6e64b673d54990c105de070868aab17d`.


### 2026-10-26 v51 largest-connected-component object background (09:59 UTC)

- Starting from v50 (v28 plus generic training-prior memory), changed only the generic object extractor's background selection to the color with the largest 4-connected component; ties use total count, then the lowest color. Bundle preflight passed. The memory payload remains training-only (SHA256 `66e98b7eebab697b4b6877d73af3ec6cb2529104f0386183412ac340760d422a`).
- Full runtime completed all 240 public tasks / 259 examples in 752.468 seconds. v51 scored 14 / 15 versus v28 and v50 at 13 / 14, a net +1 task / +1 example. Against v19 (10 / 11), it gained 4 tasks / 4 examples with 0 regressions; attempt 1 was unchanged and attempt 2 changed on 4 examples.
- Exact paired candidate-region evaluation found 5 public candidate examples in 5 tasks: v28 was exact on 4, v51 on 5, adding 1 task / 1 example with 0 regressions. LOO exact pairing covered 41 proposal folds: 33 baseline exact, 36 candidate exact outputs, 4 usable duplicate slots, +3 newly correct and 0 regressions. These provide candidate-region regression evidence; full-run regression counts are measured against v19.
- The runtime received no test targets; public labels were read only after prediction completion. v51 is a local best candidate; official Kaggle score remains `UNKNOWN_NOT_SUBMITTED`. No kernel, production source, or Kaggle submission was changed.
- Evidence: [v51 full-runtime report](証拠/ARC26-UNIFIED/ARC2-v51-largest-component-full-runtime-evaluation-20261026.json), SHA256 `38f55726e8bf4d09e39c91c2f530a2be55470b47b3152530b951e21b987af2c6`; [v51 build manifest](../出力/Kaggle/arc2-codex-main-baseline-v1/v51-largest-component-background-20261026/build-manifest.json), SHA256 `ebdd96836be417c0257030a115c6a6043a46c9471611af63000f677a75104c85`; full-runtime runner SHA256 `b04281247bec1dc38d1c862ead1b8cd1da5839431d2b69b98c6d3c7bc2659cdf`; build script SHA256 `5f2a0797e53d297348c6a66a1ed4d48a922941db12a40a5f46c08694bf72b8ea`; [probe](証拠/ARC26-UNIFIED/ARC2-largest-component-object-v51-probe-20261026.json) SHA256 `3c226cb8152da9232e9cf331433f032b885051746f5c1cc52ced3d22d48bfb7e`; [exact paired scorecard](証拠/ARC26-UNIFIED/ARC2-largest-component-object-v51-exact-paired-20261026.json) SHA256 `037e4db063a6be8594da1b91c74d4bcdc473451df2b2ca41a91d2dba6177e9f9`.


### 2026-10-26 v52 8-connected largest-component background (10:08 UTC)

- Compared a generic 8-connected largest-component background rule with the exact v28 runtime. The screen proposed 40 of 2,916 LOO folds and 4 public examples in 4 tasks.
- On LOO proposals, v28 was exact on 33/40 and candidate outputs on 31/40; 4 candidates could fill duplicate slots, producing 0 new exact answers and 0 regressions. On the 4 public candidate examples, v28 and candidates were both exact on all 4; no second slot was available for any proposal. Public gain 0, regressions 0. Rejected without a full build or runtime.
- Held-out outputs and public targets were read only after the exact v28 runtime generated predictions. No production code, kernel, or Kaggle submission was changed; official score remains `UNKNOWN_NOT_SUBMITTED`.
- Evidence: [probe](証拠/ARC26-UNIFIED/ARC2-largest-component-object-v52-8connected-probe-20261026.json) SHA256 `2e24ba28b48713aaa127e9dcc89145fcdb69b4bd892d782a82ce27adf89d80b0`; [exact paired scorecard](証拠/ARC26-UNIFIED/ARC2-largest-component-object-v52-8connected-exact-paired-20261026.json) SHA256 `e88c54bb18e69dbe9f011ba49b37bbda270f4566c086d1eadf368ba7236e17b4`; probe script SHA256 `4f3407c593d6bd4cf45e0c04857fe30386e3941b1ed66b4cc0fb5bfc014b9fad`; paired runner SHA256 `883d1d0d8069551d5a1c211aa4fb8b48f3ae65a3fbc8490dafa511b2e3acbec8`.


### 2026-10-26 v53 largest border-connected component background (10:26 UTC)

- Tested the color whose largest 4-connected component touches the grid border, with ties by total count and then lowest color. The screen proposed 38 of 2,916 LOO folds and 4 public examples in 4 tasks.
- Exact v28 pairing scored 33/38 LOO proposals and candidates scored 33/38; one candidate could fill a duplicate slot but added no exact answer. On public candidate examples v28 and candidates both scored 4/4, with no available duplicate slot. Public gain 0, regressions 0. Rejected without a full build or runtime.
- Held-out outputs and public targets were read only after the exact v28 runtime generated predictions. No production code, kernel, or Kaggle submission was changed; official score remains `UNKNOWN_NOT_SUBMITTED`.
- Evidence: [probe](証拠/ARC26-UNIFIED/ARC2-largest-border-component-object-v53-probe-20261026.json) SHA256 `5b4b016ac54ba844fad153d93ae6564111e9d72243fb7bfe512a4b6e6b9b4cd6`; [exact paired scorecard](証拠/ARC26-UNIFIED/ARC2-largest-border-component-object-v53-exact-paired-20261026.json) SHA256 `9ba47ccfba430204673b84910ad16715aee6e86faa49313b8304ec02f78b8dba`; probe script SHA256 `c0b82a759a4069a479e2611021856bd5c5c2984e4fe009c733943dd4bdf7b01f`; paired runner SHA256 `e142c8b004bbcd37ec4acb8cbf30776469bdb4f1c23dad394d1de82716759b71`.


### 2026-10-26 v54 training-guided removed-color background (10:39 UTC)

- Tested a background choice from training pairs: each teacher votes for the unique color with the largest positive input-minus-output count loss; a unique plurality of at least two teachers selects that color when present in the query, otherwise the modal color is used. The screen proposed 40 of 2,916 LOO folds and 4 public examples in 4 tasks.
- Exact v28 pairing found 32/40 baseline exact LOO outputs and 34/40 candidate exact outputs; 3 candidates could fill duplicate slots, yielding +1 newly correct and 0 regressions. On public candidate examples, v28 and candidates were both exact on 4/4 and none could use a duplicate slot. Public gain 0, regressions 0. Rejected without a full build or runtime.
- Held-out outputs and public targets were read only after the exact v28 runtime generated predictions. No production code, kernel, or Kaggle submission was changed; official score remains `UNKNOWN_NOT_SUBMITTED`.
- Evidence: [probe](証拠/ARC26-UNIFIED/ARC2-training-guided-background-object-v54-probe-20261026.json) SHA256 `47c460a3c3c9b2ac0536a75394246aad4ff65820115efdb144acc738eff72b50`; [exact paired scorecard](証拠/ARC26-UNIFIED/ARC2-training-guided-background-object-v54-exact-paired-20261026.json) SHA256 `7f5a4026ff9ab79af399d58c8d976644d894c2883cedda69306f7ebb946d1e52`; probe script SHA256 `cfc84e971037489056c2e619c39da1f3bb8a65c846e85307c8293f8df77f5f77`; paired runner SHA256 `539076d7ac51e54997347c77e4d2d8047c27e9d8b322d7663b5193c3474486dc`.


### 2026-10-26 v55 corner-connected largest-component background (10:51 UTC)

- Tested the color whose largest 4-connected component contains any grid corner, with ties by total count then lowest color. The screen proposed 36 of 2,916 LOO folds and 4 public examples in 4 tasks.
- Exact v28 pairing scored 31/36 LOO proposals and candidates scored 31/36; 1 candidate could fill a duplicate slot, yielding 0 new exact answers and 0 regressions. On public candidate examples, v28 and candidates were both exact on 4/4; no proposal could use a duplicate slot. Public gain 0, regressions 0. Rejected without a full build or runtime.
- Held-out outputs and public targets were read only after the exact v28 runtime generated predictions. No production code, kernel, or Kaggle submission was changed; official score remains `UNKNOWN_NOT_SUBMITTED`.
- Evidence: [probe](証拠/ARC26-UNIFIED/ARC2-largest-corner-component-object-v55-probe-20261026.json) SHA256 `7e8c0aee7dbf9cfad6299e523390cfa4d65f1d202991e5fc3d024c2ae2f24ea7`; [exact paired scorecard](証拠/ARC26-UNIFIED/ARC2-largest-corner-component-object-v55-exact-paired-20261026.json) SHA256 `b4343f5695f5c91e03c1f115c448ed368edc5c94d907ba14ca27748b1ab3dba9`; probe script SHA256 `addbedbf16d6b8ff45a77a8e7c2374fbfaeb9392bebacc853a3d08520c2117a0`; paired runner SHA256 `3b0ae2711e3218008d642a14aa3c292999cc8ec7782f594d372fe088cca3692d`.


### 2026-10-26 v56 largest-component background for composite geometry (10:56 UTC)

- Applied the v51 largest 4-connected component background rule to both composite-geometry teacher fitting and query crop preparation. Public-only screening proposed 1 example in 1 task; no LOO screen was run due the candidate family's higher fitting cost.
- Exact v28 pairing found the candidate exact on the single proposal, but v28 was already exact and its second slot was distinct. Public gain 0, regressions 0. Rejected without a build or full runtime.
- Candidate and exact-v28 runtime received no challenge targets; labels were read only after both prediction sets existed. No production code, kernel, or Kaggle submission was changed; official score remains `UNKNOWN_NOT_SUBMITTED`.
- Evidence: [public probe](証拠/ARC26-UNIFIED/ARC2-composite-geometry-largest-background-v56-probe-20261026.json) SHA256 `cdbabacd5e08340197f79ff54ca956deb714ddd97ece06103ba296cf5b4457fe`; [exact paired scorecard](証拠/ARC26-UNIFIED/ARC2-composite-geometry-largest-background-v56-exact-paired-20261026.json) SHA256 `3c87e46d185235c503db01fa028351d5673a8f6c418f68487abfcefc312d29a6`; probe script SHA256 `cd35a656bc2aa7b7046bf3e9b1bf33dfe6b811be55b0fb7e5d39ad9e27f62fb7`; paired runner SHA256 `1ad711320c8664a7b13ea8d954c93142041a764b49ef939bfa8d884399e670f2`.

### 2026-10-26 v57 training-guided object-background fallback (11:34 UTC)

- Built a local-only candidate on v51, retaining generic training-only prior memory and the largest-component object rule, then adding a unique plurality of training-teacher removed-color votes as a fallback. Preflight passed. Full runtime completed all 240 tasks / 259 examples in 822.407 s; test targets were read only after prediction generation.
- v57 scored 14/240 tasks and 15/259 examples, +4/+4 vs v19 (10/11), with 0 regressions. Against current best v51 it was 0/0: output SHA256 is identical (`8c4a3d09d80e9cef5cf9f3873afa523d2700a52882a5b65ad041d39380327194`). Thus the paired v28-region gain was already present in v51; the fallback changed no final prediction. Reject v57 and retain v51 as best local candidate.
- Runtime received no test targets; no per-task predictions or targets were saved. No production source, kernel, or Kaggle submission changed; official score remains `UNKNOWN_NOT_SUBMITTED` and quota was not used.
- [v57 full-runtime report](証拠/ARC26-UNIFIED/ARC2-object-background-fallback-v57-full-runtime-evaluation-20261026.json) SHA256 `48f45900c40bd950c458ebcdbde5d7ad4a10d950945703e27309e377a2382ea3`; payload SHA256 `b01432af3a51a2f147db20c07e8fd77874dc50b414c59b07cf082d0421f16edb`; notebook SHA256 `f5ee4dea36d7c6a5cbd83bc0d627de6baf935514188c7585ada9ed121c7f4d1d`.
### 2026-10-26 v58 parallel object-background hypotheses (12:10 UTC)

- Screened modal, largest 4-connected component, and training removed-color plurality background hypotheses in parallel. Each object-family output was ranked by its own teacher-vote confidence, followed by the existing object/outlier/palette family priority. The screen proposed on 73/2,916 LOO folds and 5 public examples across 5 tasks.
- Paired against the exact current v51 bundle on those candidates: LOO had 52 baseline exact outputs and 54 candidate exact outputs; the candidate fit a duplicate slot on 3 folds, adding 2 correct with 0 regressions. On the 5 public candidate examples, v51 was already exact on 5/5; none had a duplicate second-answer slot, so the combined score stayed 5/5 (+0, 0 regressions). Reject v58 without building a new bundle; retain v51 as best local candidate.
- Candidate generation used training pairs and inputs only; the exact v51 runtime received no held-out outputs or public targets. Targets were read after both prediction sets. No per-task data was saved; no production source, kernel, submission, or quota changed. Official score remains `UNKNOWN_NOT_SUBMITTED`.
- Evidence: [probe](証拠/ARC26-UNIFIED/ARC2-object-parallel-background-v58-probe-20261026.json) SHA256 `a8b9b7f8d733a883e2c941aad027d6fb8de9236792fad79c9f7a46c1a851391b`; [exact v51 paired scorecard](証拠/ARC26-UNIFIED/ARC2-object-parallel-background-v58-exact-paired-20261026.json) SHA256 `1f67de531a391490a104b1ab1b3bde34bd5ddb1f155e8eb964d3677f64c414ce`.

### 2026-10-26 v59 border-connected component mass background (12:20 UTC)

- Tested a background rule that sums the area of all 4-connected components touching any grid border, with ties by total color count and then lowest color. The screen proposed on 39/2,916 LOO folds and 4 public examples across 4 tasks.
- Paired against the exact current v51 bundle: LOO had 33 baseline exact outputs and 33 candidate exact outputs; only 1 candidate could fill a duplicate slot, adding 0 correct and 0 regressions. On the 4 public candidate examples, v51 was already exact on 4/4 and no candidate had a duplicate second-answer slot. Public gain 0, regressions 0. Reject v59 without a new bundle; retain v51.
- Candidate generation used training pairs and inputs only. The exact v51 runtime received no held-out outputs or public targets; targets were read after both prediction sets. No task-level prediction/target data was saved. Production source, kernel, submission, and quota were unchanged; official score remains `UNKNOWN_NOT_SUBMITTED`.
- Evidence: [probe](証拠/ARC26-UNIFIED/ARC2-border-connected-mass-background-v59-probe-20261026.json) SHA256 `7d4523d95bfc3213caedded4f149c0f759b364541b9786b7fee53ebc63886a22`; [exact v51 paired scorecard](証拠/ARC26-UNIFIED/ARC2-border-connected-mass-background-v59-exact-paired-20261026.json) SHA256 `7168df0b78953961638bccb9c29449b824a75d3a142e53a197372557c97fa80e`.

### 2026-10-26 v60 relaxed object-model vote threshold (12:31 UTC)

- Tested accepting a unique object-model plurality with one or more votes instead of requiring at least two, while preserving the existing family-confidence priority. It proposed on 72/2,916 LOO folds; all 72 were paired against exact v51. LOO baseline/candidate exact outputs were 51/51; 3 candidates could fill a duplicate slot, with 0 new correct and 0 regressions.
- On all 5 public candidate examples across 5 tasks, v51 was already exact on 5/5 and none had a duplicate second-answer slot. Public gain 0, regressions 0. Reject v60 without a new bundle; retain v51.
- Candidate generation used training pairs and inputs only. The exact v51 runtime received no held-out outputs or public targets; targets were read after both prediction sets. No task-level predictions or targets were saved. Production source, kernel, submission, and quota were unchanged; official score remains `UNKNOWN_NOT_SUBMITTED`.
- Evidence: [exact v51 paired scorecard](証拠/ARC26-UNIFIED/ARC2-object-single-vote-relaxed-v60-exact-paired-20261026.json) SHA256 `e203ab793953f4a2067d9fe332de228c25f446f122dd77eab4b2b995b11f4d20`.

### 2026-10-26 Kaggle read-only history refresh (12:41 UTC)

- .venv Kaggle CLI 2.2.5 reported an existing authenticated session; the login screen did not open and no new token was created. Credential contents were not read.
- ARC3 submission 57577905 (C1-018) is COMPLETE, public score 23.86, with no private score provided. This is +23.61 vs B1 0.25 and +23.86 vs B0 0.00. Latest ARC3 submission 57612586 is COMPLETE / public 0.03. The submission history contains no description explicitly matching v23. ARC3 limits: `numTotal=7`, `numAllowedNow=1`.
- ARC2 submission-history read returned HTTP 403 with Kaggle's rules-access message; no rules were accepted or changed. ARC2 limits were readable: `numAllowedNow=100`.
- No kernel was run or edited, no submission/upload was made, and no quota was used. Evidence: [read-only history and limits refresh](証拠/ARC26-UNIFIED/kaggle-cli-history-limits-20261026T124112Z.json) SHA256 7e792c2234b7e88c1ec4e15afd095c75ceff8786336fae3be644c0b6055e3c4a.

### 2026-10-26 v61 teacher-pair object consensus (13:08 UTC)

- Candidate models were fit independently on every two-teacher subset; only a unique output supported by multiple subsets was proposed. On 83/2,916 LOO proposals paired against exact v51, baseline exact outputs were 51/83 and candidate exact outputs 54/83; 14 candidates could fill a duplicate slot, adding 4 correct with 0 regressions.
- Public candidate-region pairing covered 7 examples in 6 tasks. The v51 baseline was exact on 5/7 and bundled v61 on 6/7: +1 example, 0 regressions, 0 task-level gain. Attempt 1 was unchanged in 7/7; attempt 2 changed only in the 2 usable duplicate slots; expected second answers matched bundled runtime in 7/7.
- Combining the verified candidate-region delta with the v51 full-run baseline gives 14/240 tasks and 16/259 examples (+0 tasks, +1 example). This is a paired local estimate, not a full v61 challenge run or an official Kaggle score. Retain v61 as the local candidate pending further optimization.
- Local-only bundle `v61-object-teacher-pair-consensus-20261026`: payload SHA256 `06f7e19da4f1b6fc0059a4aef03833fd9074bc725204a3f9c5c1b33523e0fbee`; build manifest SHA256 `21150b4b766b823a2cc9fd3089b083229db2deaea23e4b0d0a5d06acec4f0356`.
- Evidence: [LOO and exact v51 paired scorecard](証拠/ARC26-UNIFIED/ARC2-object-teacher-pair-consensus-v61-exact-paired-20261026.json) SHA256 `8d97761ca196bf4307ac235090e402a65ed135773d624de1051993c9abb0e36b`; [bundled runtime validation](証拠/ARC26-UNIFIED/ARC2-object-teacher-pair-consensus-v61-runtime-validation-20261026.json) SHA256 `123cb3b1987eea075d9a6a6172575a011792e5494afd542c6960ad53cb7ee2dc`.
- No production source, tracked kernel, Kaggle submission, or competition quota changed.

### 2026-10-26 v62/v63 subset-consensus ablations (13:30 UTC)

- v62 required a strict majority among candidate-producing teacher pairs. On 82/2,916 LOO proposals, it yielded 13 usable duplicate slots, +4 correct, 0 regressions; public pairing remained +1 example, 0 regressions, and 0 task gain. Reject the stricter threshold: it did not improve public results and reduced usable LOO candidates from v61's 14 to 13. Evidence: [v62 paired scorecard](証拠/ARC26-UNIFIED/ARC2-object-teacher-pair-majority-v62-exact-paired-20261026.json) SHA256 `9a8ad9a4f1c7abf9114e85cfa4b93ce02e134c21c15460cf41007ae811bb85ab`.
- v63 fit near-complete teacher subsets, omitting one teacher at a time. On 76/2,916 LOO proposals it yielded +4 correct and 0 regressions, but public pairing covered 5 examples already solved by v51; public gain 0 and regressions 0. Reject v63 and retain v61. Evidence: [v63 paired scorecard](証拠/ARC26-UNIFIED/ARC2-object-teacher-leave-one-out-v63-exact-paired-20261026.json) SHA256 `9f7f5250342f027436fb7d5f68b317957ac51171dfff8cb89f9942efad48dd11`.
- No v62/v63 runtime bundle, production source, kernel, submission, or competition quota changed.
### 2026-10-26 v64-v74 候補監査・局所改善継続 (14:56 UTC)

- 現行ローカル比較の基準はv51の14/240完答タスク・15/259正解例。v61の複数教師合意は支持2で+1例・退行0を再現したが、完答タスク増は0。これはローカルpaired推定であり、公式Kaggle採点値ではない。
- v11提出済み固定出力の事後profileでは、入力コピーfallback 249/249例が不正解。正解出力の関係は形状変更80、同形状の色集合変更84、同形状・同色集合の配置変更85と分散し、v11の単純な単一変換候補だけでは説明できない。これはv11出力監査であり、v51の失敗profileではない。
- v64 pooled-familyとv66 task-coherent familyは、いずれもv61と同等の+1例・0完答増・0退行。v65 single-teacher screenは提案0。採用せず。
- v67/68の物体再配色はchallenge提案0。v69 D4局所文脈は41タスク41例に提案したが、pairedで既存正解2例を再現しただけで新規正解・完答増0。v70近傍色数はLOO 396提案中4正解、challenge39タスクで空き枠使用6・候補正解2だが新規正解・完答増0。v70は台帳v39の8近傍multiset系を再確認したものでもあり、新規方式として扱わない。
- v71物体平行移動はchallenge提案0。v72色単位移動は1タスク2例を提案しLOO 4件中3件一致したが、challengeの2例はv51が既に正解し、空き枠もなく増分0。v74固定slotへの物体整列も提案0。
- v73でv61候補を空きslotだけでなく第2回答へ差し替える方針も評価。支持2以上は5タスク6例中+1例・0完答増・退行0で、v61の結果を再現。支持3以上または支持率50%以上では増分0。ローカル推定は14/240タスク・16/259例のまま。提出器への採用・公式提出は行わない。
- 公式ref 57646990は、保存済み最終照会 `2026-10-26T13:32:00.977941Z` で `COMPLETE`、public/private score欄は空欄。数値公式スコアは未確認であり、0点とは扱わない。
- 全screenは入力と教師例だけで候補を作り、targetをruntimeへ渡していない。target照合は予測固定後に行い、task ID・grid・targetの個別データは報告へ保存していない。
- v64〜v74の結果は新しい一般候補群として不採用。次の探索はtask-level gainを狙う別機構へ移し、背景・global color remap・local-neighborhood histogramの既試験族は再実行しない。
- この追記でproduction source、kernel、Notebook、GitHub、Kaggle submission/quotaは変更していない。保護対象SHAは `AGENTS.md=315998bc0549de61f70fda28a9c9923bea8a61ba6d9b79019283165e5438109b`、`制御/現在状態.json=773fdfdd37aad115c6bbbcb879304142136654db649eb1954cde0d69eb14aa6d`。

Evidence SHA256:
- v11 error profile `ARC2-v11-error-profile-20261026.json`: `82f3cec5d50cb16bfcc924fb69b9ae4e8e7eca313327a0623fa1b48ac127af58`.
- v64 pooled family `ARC2-object-teacher-pair-consensus-v64-pooled-family-exact-paired-20261026.json`: `6e297bd100b7bedcd7deaf3b41056348d758246a9bdcc8c287d823d434cfd62f`; v65 screen `ARC2-object-single-teacher-v65-screen-20261026.json`: `b84bdc588459022c8565a4e96709e2cdb128a8ca1026cc149515288374f43b98`; v66 `ARC2-object-teacher-task-coherent-family-v66-exact-paired-20261026.json`: `382417f2b7eb4490c69ec364317e265410d6ce201fc5d78c73bd268c3fc4d`.
- v67 screen: `b68317732b577ddbc6f9c9092b977471ac16bea29ce4b2cb0a3cb49e614de69a`; v68 screen: `0c2b351b3b3a693cdfabd0f450bfedfeea549117c716a8cbde5c337404554db7`.
- v69 paired: `0d2432dbbbd1099ba76ccb16314b55c832779e8e8bf6b22879ba2d061b9d7bc9`; v70 paired: `e1bb79a2cbad5e12f4d2450d30a5a77cc075da98a21880f5d39ad0d4c8b849a5`.
- v71 screen: `4b6677ff8a15ee60b29cec1d46cec5b5c3ebbc7a660ea461ec3d1a4146e96e38`; v72 paired: `2b791450497ccc0adc2ed9cb698f7719e952095ed4607c1f9a94670cbcfb5093`; v73 paired: `85fc2e70e4f85d48a6d13908da4e54951878b165b652730931c77711eab709a`; v74 screen: `aa30cd5cdf351cddf79b35f30a644ce5b54d3e5559199da2eb137463acfb4a20`.

### 2026-10-26 v11 official hidden-runtime failure diagnosis (15:18 UTC)

- Kaggle API detail for submission ref `57646990` is terminal `COMPLETE`, with public/private score fields blank and exact `error_description`: `Your submission notebook exceeded the allowed runtime. Review the competition's Code Requirements page for the time limits. Note that the hidden dataset can be larger/smaller/different than the public dataset.` The official numeric score remains unobserved, not 0.
- Retrieved exact kernel version 11 output read-only. Its `submission.json` SHA256 is `08d0dc111f97c9f3a909955296fc58d46ea0c4514fe66e75169526723359f017`, byte-identical to the file recorded for ref `57646990`. It contains 240 public tasks / 259 test examples; its local generation time was 338.955 seconds with 249 fallback examples. That local run does not establish hidden-run runtime.
- Offline reference scoring for the fixed v11 output is 8/240 exact tasks and 9/259 exact examples; current local best remains v51 at 14/240 tasks and 15/259 examples. These are local comparisons only. The submitted v11 is both locally weaker and officially unscored due to runtime.
- The official page states a <=12 hour CPU/GPU notebook limit and allows public external data/pretrained models. The API does not expose the hidden run's elapsed time or internal cutoff. No notebook edit/push, official submission, or quota use occurred.
- Continue optimization from v51 under the v5 HDS plus training-memory contract; do not repeat v11. Report: [v11 runtime-timeout diagnosis](証拠/ARC26-UNIFIED/ARC2-v11-official-runtime-timeout-diagnosis-20261026T1518Z.json).

### 2026-10-26 v6 current evaluation, boundary audit, and pending ablation

- Reproduced current local public evaluation at 120/120 tasks and 167/167 grids on two identical runs; prediction SHA matched. Windows CPU/RAM limits unavailable. This is not an official score.
- v12 remote notebook is COMPLETE but official submission 57646990 remains scoreless (allowed-runtime timeout); v12 local public score is 14/259. A separately measured v51 bundle has 15/259 locally and is under exact artifact/remote verification before selecting it.
- Runtime audit found all 120 evaluation IDs present in prior-memory index 4, but the tested 282-file runtime bundle excludes those indexes and all evaluation/solution files; the solver sees training data plus input-only tests. Module provenance remains an open audit item.
- No-static-prior gate ablation is running in `出力/Kaggle/arc2-codex-main-baseline-v1/v6-no-static-prior-ablation-20261026T1710Z`.
- Current evidence: `運用/証拠/ARC26-UNIFIED/ARC2-v6-current-repro-and-boundary-20261026.json`.

### 2026-10-26 v6 fixed-prior gate ablation

- On the same 240 public challenge tasks / 259 grids, disabling the two fixed examples as per-mechanism fit requirements produced the byte-identical submission (`54f6a303...5af46a`). Parent-side scoring stayed 13/240 tasks and 14/259 grids; attempt_1=9, attempt_2=13. Runtime rose from 320.762s to 807.547s (2.518x), fallback remained 249, and wall timeouts increased from 2 to 3.
- Decision: reject this change; no production source change. Full aggregate evidence: `証拠/ARC26-UNIFIED/ARC2-v6-static-prior-gate-ablation-20261026.json`.
- Continue by reproducing the independently recorded v51 bundle with 15/259 local exact grids, then verify a remote Kaggle kernel run before choosing the official submission candidate.

### 2026-10-26 v51 Kaggle Notebook v13 実行検証

- Kaggle上の `tecchannn/arc2-v51-local-largest-component-object-candidate` v13 は `COMPLETE` で、Kaggle現行版番号も13。metadataの要求slugと応答refの不一致は、Notebook一覧・Kaggle APIの現行版番号・remote code cell/runner/payload hash照合で解決した。remote code cell SHAはlocal bundleと一致し、payload SHAは `bea77a...b4bb23`。
- Kaggle `submission.json` SHA `8c4a3d09d80e9cef5cf9f3873afa523d2700a52882a5b65ad041d39380327194` は、同一bundleのローカル再現出力とbyte-identical。remote runtime 335.142秒、240課題/259格子、fallback249。ローカル公開正解の事後照合は14/240課題・15/259格子。v12の13/240・14/259比で+1格子、退行0。この数値はローカル公開データ指標で、公式scoreではない。
- `接続/Kaggle操作.py 状態` と `出力` 経路でもv13 COMPLETEと出力取得を再確認。2026-10-26 UTC枠は提出57646990で使用済み。24時間ゲートは2026-10-27T00:14:45.885Zまで閉じているため公式提出は未実施。
- Evidence: `運用/証拠/ARC26-UNIFIED/ARC2-v51-kaggle-version13-verification-20261026.json`; local score reference `運用/証拠/ARC26-UNIFIED/ARC2-v51-largest-component-full-runtime-evaluation-20261026.json`.
- 次回はゲート時刻以降に公式rules/timeline、UTC日、履歴/score、日次枠、24時間条件、v13 status/output/format/SHAを再確認し、全条件PASSなら1度だけ提出。同一提出IDを数値public_scoreまで追跡する。v6に従い公開データの原因分析は並行継続。

### 2026-10-26 v61 full runtime とremote検証開始

- v61 exact bundleを公開competition challenge 240課題/259格子で再実行。890.281秒、fallback249。公開training solutionsで予測ファイル生成後に採点し、14/240課題・16/259格子。v51は14/240・15/259で、v61は+1格子、退行0、完答課題増0。出力SHA `827bccfc1cf51e2fc87d687ba51e1375899650a530ec00e7a20eb1f71eb2dd18`。これはローカル公開データ評価であり公式scoreではない。
- challenge SHA `232264c58f825ee77327dcfc9f4e5cb2f83b8d997eb69032be1bf2205bbe1a83`、solutions SHA `9f07a38bd25af5e83aa5bf85c5cb1a1fefdb30f6a755256fa65429e697ca97f9`。個別task ID/targetは評価記録へ保存していない。
- metadataを専用slugへ合わせたprivate/internet=false stagingでKaggle Notebook `tecchannn/arc2-v61-local-teacher-pair-consensus-candidate` v1を起動。現状RUNNING。重複pushせず、完了後にremote output hashと形式を照合する。
- Evidence: `運用/証拠/ARC26-UNIFIED/ARC2-v61-full-runtime-public-score-20261026.json`; execution record `出力/Kaggle/arc2-v61-local-teacher-pair-consensus-candidate/v1/実行記録.json`.
- 公式提出57646990はCOMPLETE/public score空。2026-10-26 UTC枠使用済み、次回ゲート2026-10-27T00:14:45.885Z。次はv61のKaggle実行完了・出力一致まで確認し、提出直前に規則/履歴/日次枠/24hを再確認する。v61 remote未確認ならv51 v13がfallback候補。

### 2026-10-26 v61 Kaggle Notebook v1 実行検証

- Kaggle Notebook `tecchannn/arc2-v61-local-teacher-pair-consensus-candidate` v1 is COMPLETE/current version 1. Metadata is private, internet disabled, and linked to ARC2. The remote code cell, embedded runner/payload hashes, and private competition source match the frozen v61 build.
- Remote `submission.json` SHA `827bccfc1cf51e2fc87d687ba51e1375899650a530ec00e7a20eb1f71eb2dd18` is byte-identical to the local 890.281-second full runtime. Remote runtime was 398.848 seconds; 240 tasks/259 grids; fallback249. Format validation passed.
- Post-run public score is 14/240 exact tasks and 16/259 exact grids. Paired to verified v51 output: +1 grid, 0 regressions, no increase in fully solved tasks. This is a local public metric, not official Kaggle score.
- Evidence `運用/証拠/ARC26-UNIFIED/ARC2-v61-kaggle-version1-verification-20261026.json`. Official submission 57646990 remains scoreless; no new competition submission was made. Gate stays 2026-10-27T00:14:45.885Z.
- At the gate, recheck rules/timeline, UTC date, official history/score, daily limit, 24h interval, and v1 status/output/format/SHA. Submit v1 once only if all pass, then track that submission ref to numerical score.
