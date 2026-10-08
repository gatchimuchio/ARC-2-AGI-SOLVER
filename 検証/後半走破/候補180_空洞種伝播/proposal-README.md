# 候補180: 空洞局所所有と囲まれた種

目的は未解決課題を閉じて120/120へ進むこと。全必要原文を開始時に読了。制御99/140は古く、親の実測100/141を現行基底として扱う。採用source/HDS/core/gateへの変更、公式評価は未実施。

## 観測・最初の不足
全4教師pairと両query入力を実際に描画・目視した。既存C8同色成分、C4補領域、到達グラフ、競合mergeを優先した。旧124の完全sourceはfocused探索で見つからず、新規再構成として扱う。

- 全体同色成分の所有では、接している別々の環が一つの導体になってしまう。各空洞のC4境界セル集合を物理的所有とする。複数所有を辞書上書きで捨てない。
- 単に隣接するsingletonというseed解釈ではquery0黒点を区別できない。教師の実seedは、wireとcanvas境界に閉じられた1セルC4領域の中にある。query0の(14,1),(18,2)は開いた接点でありこの条件を満たさない。色番号や出力成功で選ばない。
- query0の青wireは(6,24)→(7,26)で他色wireに遮蔽される。両fragmentの共通C8接触点(6,25),(7,25)は同じgreen wireに属する。全witnessが同一pairを与えるため同色wire関係を補う。別色wire同士は結合しない。3本以上の同色fragmentなら曖昧HOLD。

## 成果と留保
4/4教師完全一致。両queryについて純粋出力を凍結。96件のD4/全色置換covariance比較PASS。これをARC2正答増加とは呼ばない。公式評価は親に委ねる。

no-crossing ablationも4/4教師に一致するがquery0の斜め環14セルが未充填となる。教師には遮蔽交差例がないことを明示し、ablations.jsonへ相違全セルを保持した。修復はquery入力の物理接触関係による。別仮説を成功出力で選別したという主張はしない。

## 引渡し
- 空洞種伝播核.py: 純粋fit/predict/render。外部I/O、ID、固定出力、固定役割色なし
- pure-evidence.json: 全教師fitと両query純粋出力・関係証拠
- ablations.json: 修復なしの全教師成立とquery差分、seed解釈の棄却理由
- check_pure.py / check-results.json: 必要範囲の共変性検証
- observed.png / predictions.png: input-only観測と予測の視覚確認

基底はarc2-current100/source。モデルはkind/versionのみで教師格子を保持しない。fitは全教師完全一致かつ変化ありを要求。seed衝突・書込衝突・曖昧交差はHOLD、例外をcatchして隠さない。
