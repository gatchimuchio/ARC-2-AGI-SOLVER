# 提案153: 外角標識による矩形片の平行移動組立

## 目的・採否
提供された教師2組だけから、既存能力の適用・合成を先に照合し、最小の不足関係を純粋な候補として提示する。教師2/2完全一致、コンパクト検査30/30成功。独立入力検証・HDS採否・回帰・production統合は未実行であり、現時点の採用は未確定。

## 既存能力との照合
- 採用済み「標点組立教材」の mixed_c8、valid_grid、WorkBudget、BudgetIncomplete を再利用。
- 既存標点組立の全体parserは両教師で raw_role_not_unique。内部単点標識の回転組立を直接適用できない。
- 既存重畳組立は両教師で不一致（出力形9x10、4x9）。今回は面積保存・重なりなし。
- 既存二物体標識組立の色役割推定も成立しない。

## 新しい固定事前と教師適合
固定事前は明示的に次の一つ。入力内の同色3点が2x2のLを作り、残る角がある矩形片の外角を示す。その角と片を固定し、全矩形片を回転・反転せず平行移動して、外周が固定角と同色の一つの充填矩形を作る。標識を消し、元の片位置を消去する。

教師から色番号、個数、面積、位置、寸法、出力、lookup表を保存しない。教師適合は宣言済み単一programの完全再現を認証するだけ。色・背景・ホスト・向き・canvas因数は入力から毎回導出する。Stateはfrozen dataclassでprogram名だけを保持する。

## 全解保持
背景と標識の全構造役割を組立前に抽出する。全役割に対して、総面積の全canvas因数と、固定角がcanvas内に収まる全配置を列挙する。最初の未占有セルを埋める未配置矩形の全選択を分岐する。矩形は穴がないため、当該セルを含む次の片はそのセルを左上角としなければならず、この分岐は全合法平行移動tilingを網羅する。

枝除外は範囲・重なり・宣言済み外周色だけ。最初の成功、ranking、上位だけの採択はない。全完成配置を記録し、全格子が一致した場合だけ返す。構造役割の一つでも解なし・不一致なら全体HOLD。複数同値配置も削らず保持。資源枯渇は明示的 RESOURCE_INCOMPLETE / complete=false で、途中解を返さない。

## API・検証
- anchored_rectangle.py: fit(teachers) -> (State|None, record)
- anchored_rectangle.py: predict(state, grid, budget=100000) -> (grid|None, record)
- teachers-only.json: 提供教師
- teacher-evidence.json: 教師2組の完全一致証拠
- compact-evidence.json: 教師証拠、30検査、既存能力照合
- test_compact.py: 再実行可能な局所検査

実行例:

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=candidate142-production-20261007:proposal153-existing-composition-20261007 python3 proposal153-existing-composition-20261007/test_compact.py

30検査はD4共変性、色置換、余白移動、独立構築の別palette四片、6通りの同値配置保持、6通りの不一致HOLD、不可能組立、標識欠落、資源不足、入力非変更、State不変、矛盾教師、無効入力を含む。

## 制限
- 提供教師と独立syntheticだけを使用。元query・target・scorer・除外historical sourcesにアクセスしていない。
- production登録、core、protected authority、base sourceの編集なし。
- 受理済みbaseの環境監査は現在の明示戦略に対する旧「戦略未選択」契約で失敗した。現在状態は変更せず、不一致を記録した。
- 新規git commit・pushは実行していない。
