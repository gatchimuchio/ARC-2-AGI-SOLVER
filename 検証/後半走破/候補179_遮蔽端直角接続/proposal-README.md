# 候補179: 遮蔽下の二端直角接続

目的は未解決一課題を閉じ、検証済み99/140から120/120へ進むこと。規則数・資料数は成果としない。作業開始時にOWNER_INSTRUCTIONS.md、AGENTS.md、運用/権限順序.md、制御/現在状態.json、戦略/README.mdを原文確認した。

## 観測と最初の不足

全3教師の入力・出力およびinput-only queryを画像・座標で確認した。既存の成分抽出、直線区間、競合を拒む書込合成を使用し、既知の半辺追跡と直進／対辺順序対応を再構成した。125の完全sourceは復旧資料に見つからず、同一sourceの復旧とは主張しない。

直進／対辺順序モデルは全教師に一致する一方、query左下の矩形で完了しない。矩形外の真の端は (16,5) から左向き、(18,2) から上向きの二つだけで、対辺ではない。両端の進行方向を延ばすと矩形内 (16,2) で一意に交わる。したがって不足は新たな自由対応ではなく、遮蔽内の既存直線二本による一意な直角接続である。

## 最小追加

既存の直進または対辺順序対応を保持し、未対応がちょうど二端、方向が垂直、交点が両端の前方、両区間全体が同じ矩形内部にある場合のみ接続する。端数不足・多義・未完了はHOLD。全線セルと全有向半辺の使用、端対応の双方向一致、全glyphの端所属、色一致、書込非競合を要求する。

両配色roleの交換が同じ線集合になるため、4教師適合modelを全て保持。query時に一つでも失敗または出力不一致ならHOLDであり、失敗modelを落とさない。保持する状態はrole色と対応policyのみ。教師・query・出力格子をruntime状態へ保持しない。

## 保存した否定結果

- 直角追加を無効にすると、4保持modelすべてが左下の同一矩形で incomplete_cover_pairing。
- 違う遮蔽色roleは教師で矩形条件または端対応条件に不適合。全12試行は verification.json に保存。
- 以前の125で無制限の15対応を認めても教師0に2種類の出力が残ったという履歴は親から受領。復旧sourceが無いため独立再実行とは主張しない。その失敗を消さず、今回も任意対応列挙・恣意的な一候補選択は採用しない。

## 検証・凍結

- 全3教師 × 4保持model: 12/12格子完全一致
- query: 4/4 modelが同一の完全格子を生成
- 90度回転とpalette巡回置換: 教師再fit・query同変性PASS
- 不正入力、無model、保持失敗model追加: HOLD
- 読んだtest entryはinputのみであることを実行時assert
- HDS v0.4.2・全体authority・consensus・採用source: 変更なし
- 公式score、全回帰、採用、commit: 未実施。親が次段で実施する

実行: `PYTHONPATH=arc2-current99/source:proposal179-occluded-port-20261008 python proposal179-occluded-port-20261008/verify_candidate.py`

凍結runtime: `occluded_ports.py`。SHA256はverification.json参照。`fit(teachers)` は全保持modelと診断、`predict(input, models)` は全保持modelの一致格子と診断を返す。内部 `render(input, model)` は単一modelの純粋描画。prediction.jsonは検証用成果であり、runtimeへの入力ではない。
