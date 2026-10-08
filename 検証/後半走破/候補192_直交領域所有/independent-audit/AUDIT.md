# 候補192 r2 独立再監査

判定: **PASS（明示priorとSciPy数値許容下の限定監査）**。
対象SHA256: 943acdb273c66b56f2103cb86038b523b32847594c34335f9ed781d0fe8e8a02。
親のr2再監査指示を受け、作業前に運用/ARC2_目的再固定_指示書.md全文を再読。
旧r1監査のBLOCKED記録と再現scriptはそのまま保存。query、README、pure-results、画像、公式答えは今回も未読。
正本と両kernelは変更していない。

## r1からの差分確認

1. regularizeは非relax MILPでgap/dual欠損・dual非有限・目的とdualの1e-6超乖離を拒否。
2. 非relaxで共有セルの整数性が1e-7未満に収まらない結果をnonintegral_milp_resultとして拒否。
3. unique_regionの第一MILP再試行後も整数性を防御的に再確認し、SearchIncompleteへ。
4. 除外MILP再試行後も同様に整数性を再確認。

それ以外の幾何prior・目的・共有セル制約・no-good・renderer・fit/model保持・候補一致規約に差分なし。
追加bound gateは保守的な数値不確定HOLDであり、第二最適領域を切り落とす探索制限を追加しない。

## 独立再現

旧r1で受理された実現可能凸結合のfault injectionをr2へ実行。
整数性gateだけを検査できるよう、fake結果にmip_dual_bound=funを加え、gap0/dual同値/残差0を満たした。
結果: accepted=False、SearchIncomplete、message={'status':'nonintegral_milp_result'}。
旧r1の不確定結果受理経路は閉鎖された。
これはfault injectionであり、実solverが不正結果を返すことを示すものではない。

## 独立oracleと教師

r1と同じ独立oracleをr2で再実行（kernel側のenergy/padding関数を使わない全列挙）。
全3×3入力512個×候補512領域 = 262,144候補energy。
唯一440／同点72の全512件が一致、エラー0、SearchIncomplete0。
この小規模検査では初回LP分数結果は0件であり、当該分岐は上のfault injectionで検査した。
教師fitの保持modelは[(0,1,7)]のみ、教師再予測3/3一致。

記録: oracle-results.json、teacher-results.json、fractional-probe-results.json、対応実行script。
数値許容付きsolverのstatus/下界契約を信頼する監査であり、正式有理最適性・唯一性証明ではない。
この判定は公式query正答やregression・正本採用を代替しない。
