# 境界key lane pure候補195

基底: arc2-current109/source（109/154、残11）。正本・HDS・Gate無変更。native/full/公式評価・採用・commit/upload/remote writeなし。

## 結果
全教師3/3を完全再現。input-only queryは1出力。pure-evidence.jsonに全role・穴所有・出力を凍結。44件のD4、色置換、scene色非依存、nearest-edge同率不一致HOLD、重複key失敗HOLD、教師guard、MemoryError伝播検査PASS。OPENBLAS_NUM_THREADS=1、CPU10秒、AS512MiB、wall60秒。

## 入力由来の追加prior
2-laneの矩形表について、keyはcanvas外側に近いlaneとする。横表は上/下、縦表は左/右、2x2は全4sideのcanvas距離を比較。最小距離同率は全保持し、不一致/一候補の失敗でもHOLD。scene中のキー一致数や塗れる物体数で向きを選ばない。

教師の表は順にtop距離0、left距離0、top距離0。最後の2x2はleft距離1なのでtop側の関係が一意。queryの表はbottom距離0、top距離11のためbottomをkeyとする。scene色を変更してもlaneは変わらない。

これは教師整合の明示priorであり、教師からの論理的一意性を主張しない。固定top/left読みも教師と整合するがqueryで異なる。旧wrongを否定条件に使って逆答えを選んでいない。query出力は青1の穴を7、緑3の穴を6、赤2の両diamond中心を8にする。灰5は対応keyがないため保存。

## 既存能力と不足
既存mixed_region_dicts_for_gridの完全mixed C8矩形成分、color_componentsの単色C8物体、_orthogonal_componentsのC4補領域、merge_proposalsを合成。既存凡例穴対応はmarker色/穴数から色を求める異なるrelation、空洞種伝播は囲まれたseedとwireのrelationであり、二lane表の入力境界向きは扱わない。最小追加は表のkey/value方向の境界束縛。穴は物体bbox内で境界に触れないC4領域のみ、他物体が入る穴は失敗。画像境界を壁として追加穴を作らない。

## 旧履歴と限界
旧137/161完全sourceはローカル短時間探索で未回収。親も既知所在なしと確認し探索終了。161のdecision/runtime-exclusionと176診断を読んだ。旧161はtable-to-scene relevance拡張、teacherfit後wrong1で棄却。旧出力と本出力の同一性は未確認であり、旧source復元・旧案に対する改善とは主張しない。旧棄却を維持。新候補の公式正答数は未検証。

初回pureは既存mixed成分cellsがlistであるためset intersection TypeError。例外伝播して停止、部分結果なし。明示set変換で修正しinitial-failure.txtに保存。

開始前およびpure結果後・44検査結果後の続行前に指定指示書全文を再読済み。
