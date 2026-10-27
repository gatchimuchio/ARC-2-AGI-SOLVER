# 公開training隔離比較・観測追加試験（セル条件木）

この試験は `LocalCellContextCandidate` と実験用 `CellConditionalTree` の候補生成を比較し、それぞれの候補について実在するHDSの全教師再現・同値原理採用・照会を実行する。提出worker、提出attempt選択、既存全候補群、事前記憶、保存からのincremental学習は実行しない。したがって結果は隔離した生成器のbatch refitとHDS接続の証拠に限定し、公式score・full solver性能・HDS中核の学習能力向上とは呼ばない。

## 固定する条件

- 公開trainingのうちtrain数5以上、入力が全て異なる課題を対象とする。現在の入力では78課題。Aは3例以上なので、新生成器の最低2教師・2セルとHDS既定3支持の両方をbefore/afterで満たせる。10trainの1課題も除外しない。after support9は新生成器の既定max8を超えるため、抽出された場合はモデルのteacher_budget_exceeded/HOLDとして分母に残す。
- sorted task ID集合からseed `20261026` で20課題を選ぶ。各課題のU/Fのindexも同じ乱数列で選ぶ。IDは台帳用に親だけが保持し、workerへ渡さない。選択条件にoutputを使用しない。
- AはUとFを除く全train、beforeはA、afterはAにFを最後に追加する。同じ生成器・既定bounds・特徴座標・HDS既定支持数・query順 `[F.input,U.input]`・90秒process wall budgetを使用する。新生成器は常に既定33特徴の完全grammarを両phaseに使用し、CLIから変更できない。旧baselineは既存のexact 3x3 context方式のままで、33特徴木へ変更しない。
- 各arm/phaseは新規processで実行する。課題indexごとに旧→新/新→旧の実行順を交互にし、両armともbefore完了後にafterを実行する。
- Uの正解はどちらのworkerにも渡さない。Fの正解はafter supportだけに渡し、before predictionの結果を改変しない。親は4呼出しが終了してからU/Fの予測を採点する。
- workerで全JSON/JSONLファイルのopenを禁止し、事前記憶やpublic datasetの独自読込を防ぐ。唯一の例外はNumPy importが確認する `.venv/Lib/site-packages/numpy-2.3.5.dist-info/direct_url.json` の不存在probe。正規化したこの1パスが存在しない場合だけ通常のFileNotFoundErrorへ進め、内容は読まない。存在したらsource gate/guardで拒否する。不存在とprobe回数を記録する。外部正解表、ID/hash分岐、問題別モデルは使用しない。

## HDSが実行する範囲

生成器を現在supportだけでfitする。同じ機械に対して `HDS接続.候補機構を学習` を実行し、候補は入力だけから生成、比較用教師出力はHDS公開学習経路へ渡す。全教師再現と同値原理採用の両方が成立した場合だけ `出力格子(..., 同値必須=True)` を使用する。新生成器は同じ機能の `admit_to_hds` / `query_via_hds` APIを使用する。候補HOLDではHDS照会を実行せず、`hds_queried=false` を記録する。HDS出力と直接候補を別々に採点する。

HDSは候補=出力という関係を学習・承認する。セル条件木・入力色role／定数色leafの探索自体は実験生成器で行う。観測追加の効果が出ても、永続的なincremental更新やHDS中核が条件木を発見した証拠にはならない。afterのF正解はtraining fitであり、未知入力への改善判定にはUだけを用いる。

旧LocalCellContextCandidateはqueryと同じshapeの教師だけからexact 3x3 contextを集計し、未知・競合contextのセルは入力色を維持する。どこも変わらなければHOLDし、一部を変えた場合だけ完成格子を候補として返す。この候補をfull-cell推論の証明と呼ばず、changed_cells等の元diagnosticを記録する。学習状態は全supportから同方式のshape/context→出力色countを正規化して記録する。raw gridを含むquery cacheは学習状態から除き、entry数の増加だけを別記録する。新生成器が全trainから学んだcenter/copy leafによるidentityは、placeholder fallbackではなく生成予測として通常採点する。

## 証拠と採否

cohortを実行前に新規ファイルへ固定し、既存runは上書きしない。入力dataset、生成器、接続コード、HDSコード、harnessのSHAを記録し、終了時に再照合する。source変化があればrunの有効性を否定する。使用するHDSとhelperはcurrent worktreeであり、frozen v61 full solver評価ではない。各workerは照会の前後に実際に読まれた接続.ARC2／hds学習系統moduleのoriginとSHAをcurrent ROOT配下のfingerprintへ照合し、生成器の接続先が同じHDS moduleであることも確認する。Windowsではprocess wall timeoutだけを設定し、CPU/RAM hard limitは未設定と明示する。既定2m work budgetはfit探索だけの上限であり、full-train replay・query・importの総負荷上限とは呼ばない。これらは90秒worker wall timeoutで捕捉し、失敗を分母に残す。

U/F別に直接候補/HDS出力のbefore/current/delta・gain・regressionを出す。旧→新比較も各phaseの同じUで行う。new correct/old wrongと、仮に2候補を両方使った場合のunion正答数も出すが、生成器familyの補完性に限定し、full submission-policyの証拠とは呼ばない。HOLD、error、timeoutをrequested分母に残し、成功した課題だけに限定しない。input-copy fallbackは作成しないため、生成器が推論したidentityは通常の予測として採点する。予測格子はpipe上で親が採点した後削除し、出力ファイルにはSHAだけを残す。

typed tree/leaf state、旧baselineの正規化context count、HDS規則のboundary/relation/条件経路・支持数・反例数・対応表SHA、候補/HDS予測SHA、admission/HOLD理由、実行時間を記録する。raw教師格子をmodel stateへ混入した場合は証拠保存を拒否する。before/afterのstate変化やquery cache増加はそれ自体を性能改善と呼ばない。

改善の採用はこの隔離試験だけで決めない。重複実行、full solverへの最小接続、同条件回帰、時間・提出attempt不変性を別途確認する。今回の既定採否は `UNDECIDED_REQUIRES_REVIEW`。

## 実行

`test_public_harness.py` はdataflow/scoringだけの純粋testでsolverを起動しない。`public_harness.py --prepare-only --output <新規prefix>.jsonl` はcohort固定だけ。実評価はOwner/親agentのreview後に、同じ引数から `--prepare-only` を外し、別の新規prefixを指定する。実評価は `--expected-module-sha256 <reviewed SHA>` が必須。先行prepareの `--expected-cohort-sha256 <cohort SHA>` も渡し、source・課題・U/F・順序・時間条件を含むcohortの完全一致を実行前に照合する。
