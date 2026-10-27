# C2-052 HDS per-cell local LOO pilot

観測: 2026-10-24 UTC。公開ARC2 training splitの先頭4適格課題、19 LOO foldsで完了。

## 条件

- C2-047と同じ中心色・半径1近傍色数・境界数を入力特徴に使用。
- 出力セル座標ごとに独立HDS engineを生成し、その座標に対応する教師例だけを学習。
- support=3、最大条件数=2。held-out出力はsolverへ渡さず、solver return後に採点。
- C2-045と同じ母集団フィルタを適用。pilot範囲のためbaseline全体一致は未判定。

## 結果

| 指標 | baseline | candidate | delta |
|---|---:|---:|---:|
| 完全回答あり | 0/19 | 0/19 | 0 |
| fallback | 19/19 | 19/19 | 0 |
| second exact | 0/19 | 0/19 | 0 |
| second wrong | 0/19 | 0/19 | 0 |
| union exact | 0/19 | 0/19 | 0 |

Candidate diagnostics: 55 per-cell engines, 54 queries, 204 teacher relations, 6 additional-observation requests, 6 cells without prediction, 1 conflicting prediction, 1 cell below support, 5 shape-precondition failures, 0 complete candidate grids.

Baseline runtime 119.869 s、candidate runtime 0.948 s、combined 120.847 s。`baseline_matches_c2_045=null` のため、このsubsetだけでC2-045全体のbaseline再現を主張しない。

## 判定

このpilotでは性能改善を確認できず、全件LOO・本番採用・提出へ進めない。Per-cell化は低コストだったが、出力を完成できなかった。次の限定仮説では、HDSが断定しないセルを無条件に埋めず、同じ座標の全教師例で入出力が一致した場合だけ、入力色を明示的なidentity予測として使う。candidateは全格子でexact採点し、HOLD/fallbackは正答に数えない。

Held-out出力のsolver流入なし、hidden/evaluation正解の読込なし、本番solver・提出変更なし。

## 証拠

- JSON: `運用/証拠/ARC26-UNIFIED/P5_HDS_per_cell_LOO_pilot.json`
- JSON SHA-256: `5bee1c16cfddf252db27a75da06f3bb5f4170c22c4bc8642a8489a0cc381baf3`
- Script: `運用/証拠/ARC26-UNIFIED/P5_HDS_per_cell_LOO.py`
- Plan: `運用/ARC26-UNIFIED/C2-052_HDS_per_cell_public_LOO.md`
