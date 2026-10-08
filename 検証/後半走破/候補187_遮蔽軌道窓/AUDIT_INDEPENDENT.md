# 候補187・限定独立監査

判定: 指定範囲でPASS。採用・公式性能改善の判定ではない。

開始前に現行103のAGENTS.md、運用/権限順序.md、運用/ARC2_目的再固定_指示書.mdの全文を確認。目的120/120、親から提示された現行値103/146を保持。

対象: source/接続/ARC2/遮蔽軌道窓.py
SHA256: 1522b9a4201eea9dcf123352eea49968173b855783d43d5ac6ffa354211079fc
基底: arc2-current103/source
教師: arc2-current99/teachers-only/0934a4d8.json のtrainのみ。
query入力、pure-freeze.json、REPORT.md、observed.png、探索・既存検査script、公式採点・答えは未読・未実行。
正本・対象候補コードは改変していない。

## 検証

- 教師4/4完全再現、共有反射和[31,31]。
- 小型2x3/3x2の全矩形欠損×二色既知配置658例とseed187の250例、合計908例を独立愚直全列挙と比較。
- 矩形窓・全平行移動donorを愚直に列挙し、圧縮記録から復元した全候補集合と一致。包含最大窓の全donor集合も一致。
- 成立284、HOLD624で独立判定と一致。全例についてrender_encodedへの接続も確認し、成立例で全既知セルおよび原入力witness集合が一致。
- 既存二軸rendererが成功する297 synthetic経路では出力と原証明記録がそのまま一致。
- 非矩形欠損、donorなし、既知軌道矛盾、欠損なし、負fold座標、範囲外軸の失敗を確認。local_bindに注入した例外は握り潰さず伝播。

## 静的確認と限定

全行上端・下端と全平行移動を列挙し、各固定行区間について欠損を含む最大水平区間を記録する。任意の成立窓は同一donorのこの水平拡張に包含され、左右端範囲から元窓を復元できる。したがって非最大水平窓の省略は候補集合の圧縮としてlosslessであり、グローバル包含最大窓を失わない。空の既知contextだけは明示的に除外する。

ただし非最大contextの予測を最大contextで抑制する判断そのものは追加priorである。すべてのcontextの予測が同一と証明したわけではない。採用した「包含最大窓の全donor一致」という明示prior内で完全性を確認した。

既存renderer成功時は即時返却。追加経路は原witness欠落だけに限定し、全既知値を再走査して矛盾を拒否する。原入力witnessと新規束縛を別記し、既知セルは上書きしない。例外を成功に変えるcatchはない。

対象コードにデータセットアクセス、問題ID・filename・hashによる分岐、固定答え、答えmapはない。軸は教師から導出され、サイズ・色・平行移動は入力から列挙される。教師4例が追加priorを特定するという主張はしない。

本監査は教師・syntheticと対象コードの限定監査。全問題regression、query正答、性能増分、production経路の統合は検証対象外。これらの確認前に能力向上・採用を認定しない。

再実行: PYTHONDONTWRITEBYTECODE=1 python proposal187-masked-pattern-20261008/audit_independent.py
結果: audit_independent_results.json
