# ARC2 P5 HDS候補生成経路 attribution LOO

- 観測: 2026-10-24T09:47:29Z; public ARC-AGI-2 training split only。267 eligible tasks、1191 folds、manifestは既存baselineと一致。
- 手法: 107の汎用candidate module familyを全1191 foldで観測。solverの候補採否・fallback動作は変更せず、task ID・格子を保存しない。
- module-fold結果: 合計127437回。候補なし127417回、teacherに完全一致して等値確認後に採用された候補20回。候補があるfoldは1/1191。候補出力20件は1 foldに集中し、distinct candidate/foldは最大1。
- previous→current: first answer 16/16 → 16/16 (delta +0); candidate fold 1 → 1 (delta +0); candidate vote 17 → 17 (delta +0); union exact 17 → 17 (delta +0). Metrics match baseline.
- 計測時間: baseline 1600.275s、instrumented run 1826.345s。instrumentation overheadが入るためalgorithm runtime比較には使わない。

## 判定

`候補生成coverage不足`は汎用的な観測上のボトルネック候補だが、この計数だけでは256 fallback taskごとのHOLD理由は特定できない。候補プールもexact数もbaselineと同じで改善はない。P5変更としては不採用、現行production SHAは据え置く。fallbackは正答扱いしない。評価正解は読まず、task IDとgridも保存していない。

- 生結果: `運用/証拠/ARC26-UNIFIED/P5_HDS_candidate_pipeline_attribution_LOO.json`
- 計数script: `運用/証拠/ARC26-UNIFIED/P5_HDS_candidate_pipeline_attribution_LOO.py`
- 集約JSON: `運用/証拠/ARC26-UNIFIED/P5_HDS_candidate_pipeline_attribution_summary_20261024.json`
