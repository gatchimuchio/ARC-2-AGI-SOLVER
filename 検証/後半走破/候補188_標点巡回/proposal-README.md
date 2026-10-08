# 候補188: 標点巡回の所有継承・終端合成

状態: 全3教師再現、全3保持modelのinput-only出力一致、targeted52検査PASS。独立監査、HDS統合、native、全回帰、公式採点は未実施。正答増分は未主張。基底は採用104/147の `arc2-current104/source`。基底への変更なし。

## 最初の不足と既存能力

全教師入力/出力とquery入力を observation.png で画像実見。既存の `矢印到達候補.parse_input` と `全panel端連鎖核.views` を実行した結果は existing-capability-evidence.json。前者は固定3セル矢印のみの全foreground所有であり、疎標点・可変maskを所有できない。後者はpanel内の単一連結bodyを要求するので、この分散した標点と矢印を扱えない。

旧144/147の完全sourceは今回workspaceから回収できなかった。negative176の保存記録は、前方優先巡回の教師fit、snapshot-strideとconsume-allの両fit、queryのpanel_role_not_uniqueを示す。この否定履歴を新実装で消したとも、旧sourceを復元したとも主張しない。

現物を再観測すると、教師2の後続panelでは4セルの矢印と未消費標点がC8接触して5セル成分となる。各snapshotを独立に再分割すると所有が変わる。新kernelは初panelの唯一非単点C8成分を矢印として所有し、全maskを剛体移動する。後続panelは状態の完全一致で検証し、再分割しない。

再利用した実部品:
- color_components: 同色C8所有
- full_separator_lines / separator_lattice_segments: 区切り・等形panel認識
- shifted_sparse_point_mask: 全maskの有界平行移動
- merge_proposals: 同色書込みunionと異色競合検出
- valid_grid: 既存の入力検証

最小追加は、形状の対称軸と狭端からの方向role、上の部品を繋ぐ有限標点巡回、snapshot完全照合、終端契約。

## 教師からの観測と明示prior

初panelの矢印は、反射対称軸の前端が1セル・後端が複数セル。各単点に軸方向で到達してtipを一致させ、到達点だけを消費する。各方向では最初に出会う点を取る。逆行はしない。

教師0/1/2はそれぞれ、初期標点数6/4/10、input panel数3/4/2、snapshot stride2/1/5。出力はすべて標点を全消費した矢印のみ。全消費終端と通常のsnapshot-stride外挿は教師上同じ出力になる。教師だけで両者の論理的一意性は証明できない。

ここでは「全消費までの行程を等間隔に示し、終端panelだけを省略する」を明示したpriorとする。単一panelでも終端は全消費であり、任意の未知strideを成功するように選ばない。このpriorは最初のquery予測より前に prequery-freeze.json へ固定した。

初版はactorと未消費markerの実セル重複を禁止していた。全教師fitしたが、queryの6回目到達で後端が未消費markerと重なり、全3保持modelが同じHOLDになった。初版source・教師証拠・凍結・query失敗を initial-exclusive-ownership/ に保存。

修正版の追加priorは「一時遮蔽は描画のみの同色unionであり、論理標点はtip到達まで保持する」。接触で別物体へ再分割せず、実セル重なりで未消費標点を削除しない。この修正後に教師再fitし、kernelを凍結してqueryを実行した。失敗履歴は保持。公式正解/評価は一度も見ていない。

## 全候補と失敗保存

モデルはpanel順序2通り × routing3通りの全6候補。
- 直進優先、なければ左右
- 逆行を除く全方向の最短点
- 逆行を除く各方向の最初の点を全保持

教師fitでascendingの3候補すべてが保持され、descendingの3失敗も証拠に残る。queryでは3保持候補が全て同じ有限12到達行程を完了し、同じ出力になった。方向/role/経路の分岐は全保持し、失敗枝をsnapshot成功により選別しない。いずれか失敗、又は完成出力不一致はHOLD。資源上限はSearchIncompleteとして伝播する。

状態は順序・routingラベルのみ。教師格子や予測格子はモデルに入らない。kernelにI/O、ID/hash/filename分岐、固定出力なし。IDは検証harnessの対象選択にだけ使う。

## 再現と次段

- `python -B proposal188-marker-traversal-20261008/check_candidate.py`: 教師fit → query実行前hash固定 → input-only全保持予測。証拠ファイルを再生成するため監査では既存freezeとのhashを先に照合する。
- `python -B proposal188-marker-traversal-20261008/test_targeted.py`: 52検査。D4/色置換、snapshot接触、遮蔽標点再到達、失敗枝/完成不一致、無効状態、資源伝播、非変異、freeze hashを含む。

親へ渡すruntime候補は接続/ARC2/標点巡回核.pyの1ファイル。fit/predict/render API。HDS中核・全体Gateは未変更。独立監査の後に通常空prior境界へ接続し、native/全回帰/同条件公式採点を親が担当する。
