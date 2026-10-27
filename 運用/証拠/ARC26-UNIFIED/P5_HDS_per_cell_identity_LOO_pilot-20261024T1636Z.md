# C2-053 HDS per-cell supported-identity LOO pilot

観測: 2026-10-24 UTC。公開ARC2 training splitの先頭4適格課題、19 LOO foldsで完了。

## 条件と結果

- C2-052と同じper-cell HDS。未予測セルは、同じ座標の教師例3件以上が全て入出力同色の場合に限りidentity予測。
- baseline: 19 fallback、0 exact、0 wrong、0 union exact。
- candidate: 19 fallback、29 supported identity cells、0 complete candidate grid、0 second exact、0 second wrong、0 union exact。deltaは全指標0。
- HDS diagnostics: 132 cell engines、129 queries、489 teacher relations、14 identity fills after observation request、4 output conflicts、3 output quarantines、3 below-support cells、5 shape-precondition failures。
- baseline runtime 127.078 s、candidate runtime 2.307 s、combined 129.419 s。
- `baseline_matches_c2_045=null`。19fold subsetのbaseline一致だけではC2-045全体の再現を主張しない。

## 判定

identity予測を29セルまで生成したが、全セル格子を完成できず正答増は0。全件LOO・本番採用・提出へ進めない。HDSの出力競合・隔離が残り、教師例に一貫したidentityがあっても候補を返せない座標があるかは未計測。次の限定診断では、その重なりを集計し、追加のidentity適用が公開LOOで完全格子のexactを増やすかだけを確認する。

held-out出力はsolverへ渡していない。fallback/HOLDは正答に数えず、本番solver・提出の変更なし。

## 証拠

- JSON: `運用/証拠/ARC26-UNIFIED/P5_HDS_per_cell_identity_LOO_pilot.json`
- JSON SHA-256: `028bb6dd5de6ada8acf7ab16031e9c7d12eef716b6d331baedd13d0e20950a96`
- Script: `運用/証拠/ARC26-UNIFIED/P5_HDS_per_cell_identity_LOO.py`
- Plan: `運用/ARC26-UNIFIED/C2-053_HDS_per_cell_supported_identity_public_LOO.md`
