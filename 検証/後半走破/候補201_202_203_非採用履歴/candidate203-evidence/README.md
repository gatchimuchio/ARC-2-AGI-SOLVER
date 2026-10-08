# 候補203 孤立native統合検証

基底は arc2-current113/source、検証対象は candidate203-production/source。正本は無変更。公式評価完了: 113/158→113/158、増分0、wrong1のため棄却。旧158格子完全保持、資源失敗0。

旧nativeは99family、採用可かつ同値採用0、枠計数教師不fit、query HOLD。提案203の明示prior（所有payloadの軸投影支持を集合化して密詰め）を、空priorの新しい通常HDS境界へ最小接続した。旧185のC4 prior wrong棄却を保持し、raw教師fit全3modeのquery不一致HOLDも保存。これは教師による論理的一意性の主張ではない。

変更は凍結核追加、strict adapter追加、HDS接続4行。strict教師list/min2/all unique/pairdict/両grid valid/同shapeをfit前に要求。状態はmodel名だけ。診断setは全要素を保存してJSON化し未知型は例外。core、既存family、全体gate、HiGHS threads=1は不変。

native旧99family/全既存記録は同一。新family教師3/3、事前観測数0。query1出力は凍結pureと完全一致。pure再実行63、targeted45、新規全回帰109本7839 PASS。window29は依存ファイル/関連bridge AST同一を確認した保存証拠を合成し110本7868。全3022 source pin保存、基底全bytes一致。独立pure44はREADMEのquery説明を見た制限があるためqueryblindとは呼ばず、答え未読のteacher/synthetic監査として扱う。独立adapter31 PASS。

native/pure/targetedはOPENBLAS_NUM_THREADS=1、CPU10秒、512MiB、wall60秒。全回帰は従来のnormal Python3.12.14/3workers/各script wall120秒。公式は親の条件付き許可後、OPENBLAS1/CPU10/512MiB/wall60/HiGHS1で候補120/167を1回だけ実行。採用・packaging・commit・upload・remote操作は未実施。hidden答えの手動閲覧なし。

## 最終判定

公式候補1回完了。3dc255db q0の新規出力が誤出力1で、正答課題/格子の増分0。203 axis_slices priorは棄却・非採用。pure/native一致や回帰PASSを性能成果へ読み替えない。報告直後に目的再固定指示書全文を再読した。正本113/158は全bytes不変。sourceと反証は孤立実験記録として維持し、runtimeへ採用しない。admission.jsonとdelta.jsonに採否・比較を保存。
