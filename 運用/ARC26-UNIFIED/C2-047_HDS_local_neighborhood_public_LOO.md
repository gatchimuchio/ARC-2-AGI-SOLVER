# C2-047: HDSセル近傍表現の公開training LOO

## 根拠と仮説

- ARC2の直近提出57576155は公式 `COMPLETE / public_score 0.00`。
- 最新P5 full stageでは259 test inputsのうち254が「現行暫定原理の適用に必要な観測不足」で保留。
- HDS max condition 3、single-condition、candidate pooling、raw consensus/plurality、prior追加は既存全LOOで正答増加なし。再実行しない。
- 現行ARC connectorの基底観測は入力格子全体を単一値としてHDSへ渡す。未評価の仮説として、セルごとの中心色と周囲8セルの色数・境界数をHDS条件観測にし、trainingで反復する局所決定規則から出力色を学べる可能性を試す。
- 近傍特徴は位置・課題ID・hashに依存せず、全training課題へ同じ規則で適用する。条件値の衝突・未知特徴・HDS保留が一つでもあれば候補格子を出さない。

## 比較条件

- previous: C2-045 `previous_no_prior`。公開trainingのみ、同一prior重複ガード、267課題・1,191 LOO fold、現行connector、HDS最大2条件、priorなし。
- candidate: 同じfoldで現行connectorのfirst/second候補を再計測し、別の汎用HDSエンジンが局所近傍ルールから完全格子を構成できるか評価する。候補時のみセル近傍featureを使い、training supportは独立teacher gridごとに重複排除する。
- 各foldでsolverへ渡すのはtraining teacher examplesとheldout inputのみ。heldout outputは両solver返却後に親評価器だけが採点する。
- fallbackは正解に含めず、課題ID・格子・回答・fold別結果を証拠へ保存しない。hidden/evaluation解答は参照しない。

## 実行順と採否

1. 5課題pilotでHDS API、候補完全性、保留時の拒否、実行時間を確認する。pilotの性能は採否判定に使わない。
2. pilotが完了し全件実行が実用的なら、同一267課題・1,191 foldで本評価する。
3. previous/current/delta、first/second exact/wrong、fallback、HDS未予測・競合・追加観測・隔離数、実行時間を比較する。
4. baselineの再実測がC2-045 previousと一致しない場合は比較を無効として調査する。候補が正答を増やさない、誤答を含む、または資源負荷が許容できない場合は不採用。改善が実証されるまでproduction、提出候補、Kaggle notebookを変更しない。

## 制約

公開trainingのみの局所評価。official submission、Competition Rerun、hidden/evaluation参照、answer map、task ID/hash分岐、固定出力、問題専用scriptは行わない。`AGENTS.md`と`制御/現在状態.json`は変更しない。
