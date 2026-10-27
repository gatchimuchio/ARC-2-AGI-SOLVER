# ARC26 共通作業正本 v5.0

## 現行正本 v5.0（Owner指定 2026-10-26）

- 指示ID: `ARC26-SOLVE-SCORE-20261025`
- 受領原本: [v5 ZIP](ARC26-UNIFIED/v5_0/受領原本.zip) — SHA-256 `8a148feef55cac4c3f7a481d324bf344ee151d50d5b52dbc07eb129510b08c82`
- [共通仕様書](ARC26-UNIFIED/v5_0/01_共通仕様書.md) — SHA-256 `cedfcf88c334bc1bd88395b9d5904f3e98df68ea8fef79376178da2d3ecd2f45`
- [共通工程表](ARC26-UNIFIED/v5_0/02_共通工程表.md) — SHA-256 `d6fc39216c5b24d81a7d692a8e60f605b8df31b126562a5302ae533612daa7f4`
- [共通Codex指示書](ARC26-UNIFIED/v5_0/03_共通Codex指示書.md) — SHA-256 `f28a14b45b97f2c6520bb237a1544863334248bc8762853084a00fcebbd46f4d`
- v5.0が現行正本。v4.0と以前は履歴・参照用。
- Ownerの優先依頼: ARC2の実測scoreを先に出す。現行公式履歴は2026-10-25T15:02:40.500Z照会で57611018 COMPLETE/public 0.00、UTC当日枠1/9/0。提出可能な次UTC日までにARC2の失敗原因を修正・同条件評価し、改善した版を用意する。
- ARC2/ARC3を混同せず、`AGENTS.md`と`制御/現在状態.json`を保護し、既存dirty差分と失敗証拠を保持する。

## v4履歴（以下は2026-10-25時点の記録）

Ownerが2026-10-25に指定した「ARC26 再現性優先 v4 3点セット」を、ARC2・ARC3共通の当時の現行作業正本として適用した。v5.0採用後は履歴・参照用。

## 正本

- 指示ID: ARC26-REPRODUCIBILITY-FIRST-20261025
- 受領原本: [受領原本.zip](ARC26-UNIFIED/v4_0/受領原本.zip)
- ZIP SHA-256: aeba755872429df889c39a09b7c13a923779aa732194aa5fa90514c39d2f31e0
- [01 共通仕様書](ARC26-UNIFIED/v4_0/01_共通仕様書.md) — SHA-256 c5938497688a94eb3e01c80c9d61583f38a23c200174987773568b1bc5d0362a
- [02 共通工程表](ARC26-UNIFIED/v4_0/02_共通工程表.md) — SHA-256 cf9037370617ed899dee039e67720713ac62f58e76dc2ec3055cb36360807d3b
- [03 共通Codex指示書](ARC26-UNIFIED/v4_0/03_共通Codex指示書.md) — SHA-256 fe553ee2f77022a2ba331bcd525792ab20e5fdda5126141bf656d4dc4be52480

v3.0および以前の指示は削除・上書きせず、履歴・補足として保持する。v3とv4が異なる場合は新しいOwner指示のv4を適用する。

## 権限・作業境界

Ownerの現在の原文指示、各repoのAGENTS.md、制御/現在状態.jsonの保護条件を優先する。保護ファイルや認証・規約設定は明示許可なく変更しない。ARC2とARC3のソース、記憶、入力、評価、Kaggle提出を混同しない。

工程はP0〜P3の再現条件回収・基線確立から開始し、その後P4〜P8で能力と提出同値を検証する。形式PASS、過去スコア、局所再現を現行能力PASSに置き換えない。G0〜G4と公開評価での正方向能力が揃うまで、新しいKaggle提出枠は消費しない。既存のローカル差分・失敗証拠は消さない。

## 現行の公式履歴（2026-10-25 UTC read-only観測）

- ARC2: 2026-10-25T14:14:58.146Z に公式履歴をread-only照会。最新提出57611018 COMPLETE / public 0.00。今日1件、累計9件、残り0件。
- 詳細は 運用/ARC26-UNIFIED/score-ledger.jsonl と 運用/証拠/ARC26-UNIFIED/official-history-*.json を参照。

## 起動時の再開順

1. 両repoのAGENTS.md、制御/現在状態.json、v4正本、最新baseline、台帳、checkpoint、ローカル差分を確認する。
2. Kaggle公式履歴を専用project環境からread-only照会する。
3. 旧成功版の身元・再現条件と現行版の固定条件を回収する。固定入力・seed・初期記憶・予算で最低2回実行し、最初の差分を記録する。
4. ARC2では正しい予測格子、ARC3では合法操作と状態進捗を別々に実証する。実証前に提出しない。

## v4 P0-P3 最新追記（2026-10-25）

- P0 baseline: 運用/ARC26-UNIFIED/p0-baseline-v4-corrected-20261025T141349Z.json。source/input/memory/dependency SHAと詳細dirty snapshotを保存し、AGENTS.md・制御/現在状態.jsonがHEADと一致することを確認。
- 最新公式履歴 read-only照会: 2026-10-25T14:14:58.146Z、提出57611018 COMPLETE/public 0.00。10/25枠は使用済み。
- R-B: public training sparse cohortの4課題・12 LOO foldsを独立2回実行。training manifestと結果一致。previous/currentともexact 0、fallback 12、delta 0。限定標本の再現結果であり能力PASSではない。prior-memoryはこのrunnerでは未ロード。
- 旧C2-062 full worker PID16192は404/575 tasks・1212/1725 foldsで停止。後続確認でprocessと出力の両方がなく、exit cause UNKNOWN、TERMINAL_INCOMPLETEとして記録。部分値は採用しない。
- 詳細: 運用/ARC26-UNIFIED/V4-P0-P3-checkpoint-ARC2-20261025T142006Z.md、reproduction-ledger.jsonl、capability-ledger.jsonl、ARC2-V4-RB-C2-062-repro-report-20261025T142006Z.json。
- 当時の次作業（2026-10-25T14:20:57Z）は過去0.83版の身元回収と258 fallback分類。大規模LOOは現在コードの短い固定標本と時間計測から再設計する。G0-G4と公開評価の正方向能力が揃うまでは公式枠を使わない。
## v4 P1監査更新（2026-10-25 14:35 UTC）

- 公式履歴を専用ARC2環境からread-only再照会：submission 57611018 COMPLETE/public 0.00。UTC 10/25の提出枠は1/1使用済み、残り0。観測：[official history](証拠/ARC26-UNIFIED/official-history-20261025T143414Z.json)。
- 旧最高値55046979 COMPLETE/public 0.83は公式履歴で確認。Notebook v4の説明・復元version4 outputとの提出SHA一致・時刻は強く整合するが、提出IDとkernel version/outputの直接対応はKaggle APIから証明できない。復元packageにはpublic-training task ID literalが1種類・2箇所あり、AGENTS.mdの禁止条件により再利用対象から除外。
- 旧v2提出57560705の258 fallbackは259件中257件のHDS HOLD、1件の未捕捉AssemblyIncomplete、残る1件は正誤未計測と分類。原因不明だったexception pathは後続integrationでcatchされているが、HDS coverage改善の証拠ではない。
- 最新v9提出57611018の259件中254件はgeneric solver_hold / 断定保留。v9 auditがHDS詳細理由を落としており、内訳・正答率は不明。公開training C2-068 LOOはexact 16→17、fallback 1175→1174、wrong 0→0、退行0だが公式public scoreは0.00のまま。
- 詳細：[P1 identity/fallback audit](証拠/ARC26-UNIFIED/ARC2-V4-P1-identity-fallback-audit-20261025T143500Z.json)（SHA-256 15753acf49275ac4f988ba1b1a690577ac41fa7ea40cda9bd8de4142fccc70f4）、reproduction/work ledger、[最新checkpoint](ARC26-UNIFIED/V4-P0-P3-checkpoint-ARC2-20261025T143500Z.md)。
- 次：現行v9のfallback理由はUNKNOWNのまま保持。認可済みfuture runでID/hash/gridを保存せずaggregate-only HDS理由を記録する。大規模LOOは現在sourceでの時間計測とbounded設計を先に満たす。提出・能力改善の主張は行わない。
