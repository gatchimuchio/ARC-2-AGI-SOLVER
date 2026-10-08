# 175 revision2: 未観測キーの厳密なHDS原因契約

Revision1は独立監査でBLOCKED。未知キーで予測がないことだけを確認していたため、競合・識別不能・無関係な不足観測・学習未確認を覆い隠す欠陥が再現された。元凍結物は無変更で保存。監査結果を revision1-blocked-evidence.json に保存。

Revision2はHDS中核・元学習順序・全体採否を変更しない。新しいARC側推論事前仮説という責任は同じ。単一元特徴モデルの構文的範囲だけを扱い、複数元モデルから成功集合を選ばない。完全被覆時は元候補の成功・失敗をそのまま返す。

未知キーの照会は次の全条件が必要:
- 純粋照会の学習状態は厳密に「適用外」。その状態を学習確認と解釈しない。
- 元学習を透過的に観測し、「成立確認」で採用された原理参照を別に保持。元の学習呼出し・戻り値は変更しない。学習後の機械参照は元機械へ戻す。
- 予測、競合、係争、識別不能なし。保留理由は既存の観測不足理由1個だけ。
- 追加要求は方向経路1個だけ、不足経路なし、未知条件値は現在の単一特徴キーと一致。
- 参照原理は厳密に1個で、上述の成立確認証跡を持つ。複数参照は保留して選択しない。
- 参照先は現に有効・暫定の決定的対応原理。境界、条件経路、結果経路が元特徴契約に一致。既知の対応値表全体が元教師表と一致し、現在キーの既存直列化表現がない。
- 理由文字列だけで判定しない。上記構造と原理の検査を併用する。

API: `MissingEdgeBindings(teachers)` → `learn(machine, observe)` → `predict(grid, policy=None)`。
変更ソース: `missing_edge_bindings.py`。151 peerソースは同梱の未変更 `peer_edge.py`。production patchは作成・適用していない。

52局所検査PASS。教師、独立人工入力、許可されたsanitized input-only入力を使用。Revision1全22検査に加え、正確な原因署名、監査再現4故障、係争、無関係経路・未知値・余剰要求・複数参照・原理欠落・保留理由・状態・境界・原理表・学習成立証跡を検査。2教師で元候補への完全委譲も確認。CPU10秒、仮想メモリ512MiB、wall20秒の上限内で実行完了。

独立レビュー用には `missing_edge_bindings.py`、`peer_edge.py`、`teachers-only.json` を使用できる。`check.py` は許可されたquery入力も読むので、teacher-only監査では実行せず独自syntheticを使用する。

採否: revision1はBLOCKED、revision2は再監査待ちHOLD。正解照合・scorer・native/full/public integrationなし。採用・commit・pushなし。
