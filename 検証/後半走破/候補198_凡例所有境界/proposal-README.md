# 候補198: 所有領域の斜行境界条件

未採用pure候補。基底111/156は無変更。native、full regression、公式評価、commit、upload、remote writeは未実施。正答増分は未確認。

## 観測・既存資産・最初のgap

指示書原文、AGENTS、権限順序、現在状態、戦略を開始時に確認し、純粋結果を親へ報告した後も指示書全文を再読した。許可された3教師入出力と2query入力を画像で実見した。hidden/solutions/query正答は読んでいない。

171r2完全sourceと174診断sourceをarc2-current99/evidence/not-adoptedから回収した。今回は未回収sourceなし。171のwrong1履歴は維持し、逆答え選択には使用しない。174は対象所有と向きと終点壁を検査していたが、斜行の直交中間位置にある境界を検査していなかった。

現行凡例方向移動の役割固定parserはquery0の壁色と凡例tail色のaliasで閉じない。171r2の局所凡例＋成分所有viewはその不足を解消するが、その後の作用は次の配置セルだけを見る。query0の灰色領域ではsource(3,11)からの斜行が(4,12)→(5,13)で(4,13)の自分の壁を隅越しに通過する。この局所境界条件が今回の追加観測gap。座標は0始まり。

既存のmixed patch、色成分、矩形、enclosed non-wall region、valid_rectangle_positions、shifted_sparse_point_mask、clone/mergeを再使用する。既存の連結箱参照path_graphにはC8_no_corner_shortcutという別目的の隅検査があるが、wire上の経路短絡を防ぐ条件なので、そのまま移植すると本件とは意味が異なる。反射は教師に観測されず、既存の最初の障害前停止を保持する。新機構は所有領域包含を斜行の両直交中間footprintにも適用する条件だけ。

## 明示的priorと不確定性

「斜行1単位では、両直交中間footprintも同じ囲み所有領域内にある必要がある」を追加priorとして固定。これは壁境界の位相条件であり、他標点の瞬間的占有は壁ではない。元のblock/transparentは実際の到達配置に適用したまま全4モデルを保持する。途中の標点接触によるモデル絞り込みはしない。

教師では自由斜行と境界隅禁止の双方がfitする。教師から論理的一意とは主張しない。旧171自由斜行と本候補を双方保持して合議すればquery0は不一致HOLDになる。今回の候補は、上記を明示した追加priorの検証候補であり、旧wrongだけを根拠に正しいとするものではない。

初案は中間位置にも全valid配置条件を要求したため、他標点のblock/transparent差でquery1が不一致HOLDになった。first-swept-hold/にsource、freeze、全返却を保存した。初案と最終案は異なるpriorであり、初案が不成立だった証拠を取り除いていない。

## Pure結果

OPENBLAS_NUM_THREADS=1、CPU10秒、512MiB、wall60秒の各プロセスで実行。
- 全480モデル・1440教師呼出しを完了、3教師完全一致、4モデル保持。
- query0/1とも全保持モデル・全所有候補が成功一致。query0では旧171から標点1個だけ(8,16)→(4,12)へ変化。query1は旧171と完全一致。
- 160件のD4/色置換共変性、混合失敗のHOLDと例外伝播2件、計162検査PASS。
- strict list/min2/全入力unique/pairdict/両grid valid/同shapeの教師guardを追加。
- fit/predictはruntimeデータを読むI/O、ID、hash、filename、固定格子を含まない。probe/checkは許可データを渡す検証専用ハーネス。

freeze.jsonに核SHAと全保持モデル、pure-evidence.jsonに全入力返却、checks.jsonに検査結果を保存。初案とは異なるSHAを最終prediction前に凍結した。
