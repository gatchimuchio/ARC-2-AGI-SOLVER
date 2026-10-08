# 候補191: 完全矩形片の物理所有保存

純粋proposal。基底106/149は未変更、採用・native・全回帰・公式評価・commit・upload・remote writeは未実施。HDSとGate不変。

## 最初の不足
全教師入力/出力とquery入力をobserved.pngで実見した。153のC8成分全矩形parserはq0の接触した非矩形成分でroleなし。155は接触片を二重枠境界で分離する一方、全ての二重枠を飽和分割するため、既に矩形の6×4物理片まで上下に切り、緑と紫の相対位置拘束を失っていた。158のseam伝播と159のpayload C4を再実行し、旧13片・3異出力HOLDをq0-old.jsonにそのまま保存した。

旧3候補を実見すると、紫の開放形と緑/紫の順序交換がある。どちらも既に完全矩形の6×4入力片を分離して動かすことが原因。旧3候補で該当上下片の平行移動差は、それぞれ同一・不一致・不一致だった。候補番号や出力形状をruntime条件には用いない。

## 最小追加prior
「入力から観測された塗り詰め矩形のmixed-C8物理成分、および非矩形分離で得た矩形leafは不可分」とする。矩形なら分割再帰を止める。非矩形なら155の二重枠cut条件をそのまま用い、全cut alternativeを保持する。

このpriorは教師整合の明示的追加priorで、教師からの論理的一意性ではない。二重枠で触れた同幅片が完全矩形に見える場合は一体と解釈する。色・座標・寸法・課題IDのfitted parameterなし。入力view確定時にassemblyの成否や出力を参照しない。

その入力viewと158の完全seam列挙を合成するだけでq0は12片・1完成配置・1出力となる。159のC4条件、閉矩形模様prior、候補ランキングは不要。

## 旧経路保存
physical_rectangle.predictは154を先に呼ぶ。failureがno_structural_roleでない限り、旧返却tupleをそのまま返す。したがって旧parserにroleがある全入力の成功/HOLD/RESOURCE_INCOMPLETEと全候補記録は変更しない。旧roleなしの場合のみ新viewを使用し、旧HOLD診断をlegacy_recordへ保存する。新viewでも全role、全完成候補、不可逆seam棄却を残し、全成功/一致を要求。不一致/欠落はHOLD、予算不完了はRESOURCE_INCOMPLETE。

旧155/158/159のHOLDを削除せず、このproposalの同梱旧moduleとq0-old.json、基底historyを保持する。旧成立域を成功の都合で選ぶのではなく、入力構造のrole有無で境界を固定した。

## 純粋検証
- 全教師2/2 exact。新physical_predict単体も2/2 exact。
- q0: CANDIDATE、12片、完全列挙1配置1出力、work26147。正答未採点。
- q1: 旧154 tuple完全一致、6片、6幾何配置、seam後1出力。正答未採点。
- test_pure.pyの33検査PASS。教師旧tuple、低予算旧tuple、3種の全色循環置換、矩形不可分、非矩形分離、旧HOLD保持、新view6異出力全保持HOLD、資源停止を確認。
- 旧13片3異出力はq0-old.json、q1旧159結果も保存。入力観測と候補画像は解析記録のみ。

初回生成コマンドの括弧構文エラーを修正した。実行対象kernel生成前の失敗であり、回帰/採点結果ではない。

## 凍結/API
freeze.jsonにruntime6moduleとquery evidence SHA256。
physical_rectangle.fit(teachers) -> State|None, record
physical_rectangle.predict(state, grid, budget=100000) -> grid|None, record
Stateはprogram識別子のみ。教師格子・query・診断を学習stateに保持しない。

実行:
PYTHONDONTWRITEBYTECODE=1 python proposal191-rectangle-assembly-20261008/test_pure.py

依存: 基底sourceの標点組立教材 helper、現行153/154（ローカルトップレベルimportへの機械的調整のみ）、回収済155/158。global_rectangle.pyは旧否定結果再現用だけで、新runtime依存ではない。

## r3: 旧域を保存した教師render不変量
旧r1は別directoryに凍結したまま。全回帰で形状色教師2枚と物体端教師1枚がpartition_split中に100000予算を超えた。元rawはcandidate191-production/evidence-20261008/full-regression-current.json、診断はresource-diagnosis.json。r3のfit-necessary-evidence.jsonにも旧fit RESOURCE_INCOMPLETEを再現保存。

変更はphysical_rectangle.pyのfit内だけ。全教師についてlegacy.predictをまず実行し、その返却failureがno_structural_role以外なら成功/HOLD/RESOURCEとtupleをそのまま保持する。旧roleなしの教師だけ、predictより前に以下の必要条件を検査する。
1. 入出力canvas形状は同一。
2. 色count差はちょうど2色。一方は入力3画素のmarker完全消去(-3→0)、他方は背景+3、残りの全色countは不変。

証明: 全rendererは3セルmarkerを背景に置換し、残る全非背景セルを1回ずつ移動し、同寸canvasへ描画する。条件違反は当該教師fit不能の完全証明であり、新viewのCSPを列挙しなくてよい。全教師の結果は従来通り全保持し、別教師のRESOURCEも伝播。predictは全行不変。予算緩和・資源例外のHOLD変換なし。

形状色はcanvas不一致、物体端は全色count不変でmarker非消去のため、新viewを呼ばずHOLDと証明される。目標全教師は必要条件を満たし、fit recordもr1と完全一致。旧域の本物の列挙爆発（marker非消去教師）では元RESOURCEと全fit recordをそのまま保存する。

純粋33検査PASS。追加検査で2種の失敗fixtureについて旧資源失敗再現と新view未呼出の証明HOLD、目標fit record一致、旧域爆発と混合教師のRESOURCE record一致を確認。r2の無条件先行prefilter案は旧域RESOURCEを抑制し得るため採用せず、別directoryに保存。input容量枝刈りも不成立role省略の危険から実装せず。

凍結はfreeze.json。runtime変更はphysical_rectangle.pyのみ、他5moduleはr1と同hash。query証拠はq0-physical.json/q1-physical.json。正本・HDS・Gate未変更。統合・全回帰・公式採否は親へ委譲。
