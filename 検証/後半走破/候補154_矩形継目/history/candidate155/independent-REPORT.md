# Frozen155 independent ownership audit

判定: 宣言された固定事前仮説とteacher/synthetic範囲ではPASS。採用阻害事項は発見せず。task-score改善・一般化・production統合の承認を意味しない。

## 範囲・完全性

目的はfrozen155の再帰的double-wall分割と全解合意を独立検証すること。AGENTS、現行状態、環境監査、153/154のソースと独立監査を確認した。accepted142の再利用先を使用し、153/154/155のSHA256を実行前後に照合した。155は指定値121d31d0921c9383b769b3b6515aa669259f4aca397c82da70760ba3a6889357のまま。

読み込み対象はソース、既存監査、153のteachers-onlyのみ。元query、155 input-parser-diagnostic、targets、scorer、denied047は読んでいない。提出ソース・production・他者の証跡を編集していない。成果物は本ディレクトリのaudit.py/evidence.json/REPORT.mdのみ。

## 短い証明

新規固定事前仮説は「隣接する二つの全frame色bandが正の接触区間を持ち、その両側に非frame payloadが存在する軸平行cutを、可能な限り再帰適用する」。入力依存であり、出力・assembly成功・ランキングからcutを選ばない。ここでfull bandは現在bodyに属する当該行/列の全pixelを指す。穴を埋めたりbbox全幅を仮定したりしない。最終leafは別途filled rectangleであることを要求する。これは既存能力だけの再配線ではなく明示された新しい固定priorであり、fitは全teacher exactを確認するだけで、学習済み数値parameterはない。

各cutは非空low/highへbodyを厳密に二分し、座標と色を保存する。両子は親より小さいため停止する。子の全飽和分割の直積を全合法cutに対して和集合にするため、最初のcutに関する帰納法で全ての再帰guillotine飽和分割が列挙される。cutがなければ一つのleafだけを返す。memo/dedupは同一body/同一leaf集合を同一視するだけで別解を捨てない。component間も全直積であり、非矩形leaf等を除くのは明示された幾何学的適格条件で、assembly結果による所有権選別ではない。

所有権確認は重複pixel、marker混入、foreground未回収を検査する。各roleの全placementを153の変更なし列挙器から取り出し、154の変更なしseam判定に渡す。base出力が不一致でNoneでもplacementは失われない。同じpaintの物理配置も残り、role内全feasible出力とrole間全出力が一致する場合だけCANDIDATE。どれか一つのretained roleの失敗もHOLD。geometry/seamの完全性については変更されていない153/154の既存独立証明・oracle検査を再利用した。

observeも今回predictのBudgetIncomplete保護範囲にあり、partition、ownership直積、geometry、seamのどの段階でも不足はRESOURCE_INCOMPLETE/no output。fitも伝播する。budgetはwork-unit制御でありwall-clockや全Python操作の厳密な計測ではない。production callerはまだ存在せず、統合時の伝播確認は別途必要。

## 実行結果

実行: PYTHONDONTWRITEBYTECODE=1 python candidate155-independent-audit-20261007/audit.py

全18,438 assertions PASS。

- 独立oracleは再帰直積を使わず、分割集合を状態とし、一度に一leafだけ分割する到達グラフの終端を求めた。
- 2×3の全nonempty absent/wall/payload pattern 728件、および7×7内9候補位置の全payload subset 512件。合計1,240件、6,577終端分割を完全一致確認。複数解を持つ475件を含み、全leaf飽和・色/座標/個数保存を確認。
- 2 teachers exact、全16 D4、各teacherの全正の不足budgetでRESOURCE_INCOMPLETE、正確な必要budgetで成功。
- 実入力形式の独立syntheticで二つの所有権roleを双方保持し、両方を評価してHOLD。全foreground色/座標保存。
- 六つのseam適格配置で出力相違ならHOLD、同一出力なら六配置を残して成功。
- 集約だけを明示的mockで分離し、後続role失敗、不一致、合意、budget不足を検証。
- 実観測十piece例のdefault budget不足が部分答えを返さず、二つの異なるteacherでfitまでRESOURCE_INCOMPLETEを伝播。
- 153/154/155ソースhashは前後不変。

本監査によるaccepted baselineの変更なし。commit/push/統合なし。
