# NEW072 平行成分の基準長

新規再構成の実測:90/125 → 91/126、+1課題/+1格子。e376de54 query0を追加し、元125格子すべて同一、誤出力0・通常資源失敗0。同一の120課題/167例・10CPU秒/512MiB/60wall秒/3workers。

既存の成分、straight segment、shifted mask primitiveを再利用し、入力中の空間的中位成分の長さを共通端面から全線へ適用する。偶数個の両中位や同位置の全参照、全共通端面を保持し、一つでも失敗または完全格子不一致ならHOLD。元の疎点fit/render成功は保持し、完了したtrain_not_expansive不適合だけを新しい教師適合へ接続する。

教師3件、10普通の確認、input-only、同じHDS familyの完全grid一致を検証。全回帰100script/4574reported checksは99current recordと、変更疎点moduleを使わない同一window scopeのprior29-case recordで構成。元072 source/rawの復元ではなく、新しい実装・実行証拠。旧92/127原commit/raw欠落の区別を保持する。

基底401de208。HDS core/authority/公式source/採点器は変更しない。新075は未採用。GitHubへは送信していない。
