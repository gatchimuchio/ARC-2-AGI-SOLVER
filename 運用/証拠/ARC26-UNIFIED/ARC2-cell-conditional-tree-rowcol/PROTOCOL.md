# 行列前景数を追加するセル条件木・隔離比較

旧 `ARC2-cell-conditional-tree/cell_conditional_tree.py` の凍結SHA `f1116b7c386baad86a958af5f936b598960e83a64a9644b548efbda3978a49c4` から別ディレクトリへ複製した。旧版・本番・凍結bundle・Kaggle・台帳は変更していない。公開fitはこの作成担当では実行していない。

変更は入力特徴2個だけである。既存33特徴の後ろに `row_foreground_count` と `column_foreground_count` を追加し、各セルの行・列全体の前景セル数をカテゴリとして与える。前景は入力の唯一の最大頻度色以外。最大頻度色が同率なら両特徴を `unknown` とする。絶対row/column番号、問題ID、hash、答案参照は追加しない。

計数は既存 `接続/ARC2/受動凡例転写核.py::colour_prefix/rectangle_count` を再利用する。矩形範囲は両端inclusive。カテゴリdomainは0〜30と `unknown`。schemaは `arc2-cell-conditional-tree-rowcol-v1` とし、旧schemaを黙って35特徴へ読み替えない。

21葉アクション、木探索、単純性費用、全最小仮説の一致、全現在trainの再現検証、支持条件、探索上限、HDS採用・問い合わせ経路は旧版のままである。AST監査で変更を許すのはschema/FEATURES、`_domain`、`_input_cells`、計数helperのimportと説明docstringだけ。その他の全top-level定義・全class本体が旧版と同一であることを試験した。

合成試験では、同じ旧33特徴を持つセル群が異なるtargetを必要とし、旧文法の全21葉アクションの共通部分が空になる条件を用いた。新35特徴版は全3教師を再現し、未見のサイズ・色配置にも行の前景数から計算した。実HDSの3教師同値採用、問い合わせ、反例拒否と、35特徴状態の保存・読込・domain検査も確認した。これは構成した合成例の実証であり、公開能力・公式スコア改善の証拠ではない。

```powershell
& '.venv/Scripts/python.exe' -m pytest -q '運用/証拠/ARC26-UNIFIED/ARC2-cell-conditional-tree-rowcol/test_cell_conditional_tree_rowcol.py'
```

結果: **5 passed in 5.58s**（chunk `042e52`）。

公開比較は別担当の新ハーネスが旧33特徴木と新35特徴木を比較する。既存の固定20課題・同じA/F/Uをそのまま使い、両時点の特徴文法は各armの既定値で固定する。旧LocalCellContextを比較対象に置き換えない。両module・HDS・helperのsource pin、直接候補/HDS経由、全分母・HOLD・timeout・退行、同条件previous/current/deltaを記録する。

行列前景数で必要条件の矛盾が消えても、支持条件・上限内のfitや未見の正答は保証されない。総runtime上限には引き続き90秒worker制限を使う。採用は未決定である。
