# 検証

検証は「実装した」と「成立した」を分離する。

証拠の強さ:

```text
E0 文書・構造・artifact存在
E1 syntax / static / unit
E2 local integrated / offline
E3 公式サンプル実行
E4 Kaggle normal run
E5 公式accepted score
```

上位claimを下位Evidenceで代用しない。公式サンプルの正解をMemoryへ事前格納した場合、その既知入力での成功とhiddenへの汎化を別々に記録する。

失敗、未確認、反例は隠さずHDSの次判断へ渡す。
