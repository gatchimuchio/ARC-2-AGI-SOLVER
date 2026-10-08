# 候補192 r2: 数値整数性gate修正

基底107/150不変。旧提案 `../proposal192-outline-cleanup-20261008/` のsource/失敗/全候補を変更せず保持。教師/query入力の追加読取以外に公式解・採点は参照しない。

独立監査は、残差0・status0・mip_gap0でも非整数セルを返すfault injectionで、r1がMILP再試行後の非整数性を拒否せず丸め採用し得ると確認。実solverの誤作動再現とは区別。旧反例は旧dirの independent-audit/fractional-probe-results.json に保存。

r2は非relax結果の非整数性をregularizeでrejectし、unique_regionでも両MILP再試行後の整数性を防御確認する。不成立はSearchIncompleteへ伝播。MILPのgap/dual bound欠損・非有限値・目的とdualの乖離も拒否。LPの非整数解は下界としてだけ扱い、既存の厳密な目的差許容を満たす場合にのみ使用。問題のモデル、prior、色役割、描画、HDSは不変。

既存56検査PASS、独立3×3全512入力×512領域の440一意/72HOLD一致、数値fault injection15件PASS。教師とqueryの全5出力はr1と完全一致。CPU10秒/AS512MiB下のpure import＋全教師fit＋2queryは0.746 CPU秒、最大RSS72048KiB。native全経路は未実施。

priorと観測根拠は旧READMEを継承。凍結SHAと詳細はfreeze.json。差分はr2.patch。独立監査待ちで採用・公式評価は未実施。
