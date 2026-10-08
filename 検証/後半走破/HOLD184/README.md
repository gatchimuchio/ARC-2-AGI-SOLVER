# 候補184: 対辺標点配置の所有・重なり再観測

判定: HOLD、runtime変更なし。現行102課題/144格子、増分0。

開始時に目的再固定指示書を全文読み、AGENTS・権限順序・現在状態・戦略と照合した。結果報告後の続行前にも原文全文を再読した。全3教師の入出力と両query入力をobservations.pngで実見した。教師限定・input-only以外の正解、solutions、scorer、denied047は読んでいない。

## 確認結果

既存の対辺標点配置候補は、核の役割が0の場合だけ部分key viewを使う。全3教師で8programをfitすると、color_union/components8 × source_first/small_firstの4programが残る。全教師を完全再現する。query0は全4program一致、query1はsource_firstの2programが成功し、small_firstの2programが同数競合で失敗する。旧HOLDをそのまま再現した。

source_firstは元セルを保存する制御ではない。obj.bbox=(top,left,bottom,right)の辞書順最小を優先する制御で、色や列挙順ではなくsource内の位置順である。query1の(6,12)は入力背景0で、元の色セルの保護ではなく、新規転写セル同士の競合である。

query1:
- magenta: sourceの5×5対角線5セル、中心(2,2)、標点(8,14)。sourceセル(0,0)が競合点(6,12)に到達する。
- yellow: sourceの3×3内5セル、中心(7,2)、標点(5,13)。sourceセル(8,1)が同じ競合点に到達する。
- 両色ともC8単一物体、対辺keyは有効、転写は境界内。frame解釈2通りはどちらも同じ物体・転写・競合を与える。
- 両方とも競合点は端部。どちらを除いても残りのC8連結性は壊れない。標点一致・対応数も双方同等で所有を区別しない。
- C4ではmagentaが5個の単点、yellowは5セル単一成分になる。しかしその部品を個別中心で標点へ転写すると対角線の形が失われる。既存C4認識をそのまま合成すれば解決する状況ではない。

教師内の異色転写競合はteacher0の1点だけで、5対9セル、双方3×3である。他2教師は異色競合なし。query0は3対8セル、双方3×3の競合3点。したがって、セル数は前景量を表しているが、物体の範囲の大きさと同一ではない。query1で初めてその差が現れる。ただし範囲の大小が所有順位になる教師証拠も、同数時の所有証拠もない。

## 採否

bbox面積やC4成分量を別順位として発明せず、source_firstを同数tie-breakとして追加せず、成功programだけの選別も行わなかった。独立の画像再観測でも、一方の所有を直接支持する未使用関係は見つからなかった。

支持可能な最小候補を得ていないため、凍結する新runtimeや新予測はない。全教師fit・両queryの全保持programの成功/失敗と実入力の所有情報をobservation.jsonに保存した。現行source、HDS v0.4.2、global gate、family、過去HOLDは変更していない。公式評価/native統合/採用/commit/push/uploadは実行していない。コード変更がないため新規全体regressionは未実行であり、性能改善は主張しない。
