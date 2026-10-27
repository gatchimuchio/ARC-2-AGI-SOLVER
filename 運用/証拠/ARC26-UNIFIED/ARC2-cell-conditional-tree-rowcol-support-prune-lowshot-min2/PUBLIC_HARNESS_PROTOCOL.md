# 低shot隔離比較・観測追加試験（EXPLORATORY FIXED_MIN2）

凍結済み35特徴の非prune版0664と、支持数が不足する固定cell subsetの子孫探索だけを省くprune版5eb6を比較する。35特徴・21 action・bounds・HDSロジックは同じ。両arm・両phaseとも、HDSはコンストラクタ `HDS学習実行系(最小支持数=2)` で外側と内部検証器を同時設定し、実際の両floorを前後確認する。生成後の属性書換えは行わない。

これは独立した **EXPLORATORY FIXED_MIN2** 試験である。productionのadaptive 2→3、過去の既定min3試験とは異なる。scoreをpoolしたり、production改善・公式score・HDS中核改善として扱わない。production、旧module、旧harness、事前記憶、権限は変更しない。prototypeのnew_hds_machine既定3も変更しない。

## 固定する条件

- 公開trainingのうちtrainが正確に4例、入力が全て異なる課題を対象とする。入力・例数だけでeligibleを決め、seed `20261027` で20課題とU/Fを固定する。過去のtrain5以上のcohortとはdisjointであることを元cohort SHA付きで確認する。既知の正答率やU/F出力で課題を選ばない。
- 旧module SHA `0664c6ef1878f434c963125a767a65a35a4737aff9132a5091c05a5c316a5ac2` と新module SHAをsourceへ含める。課題IDは親の台帳用だけでworkerへ渡さない。
- AはU/Fを除く2教師、afterはAにFを最後に追加した3教師。両arm・両phaseの全35特徴・21 action・bounds・HDS floor2・query順 `[F.input,U.input]`・90秒process wallを固定する。CLIからgrammarやHDS floorを変更できない。
- 各arm/phaseは新規processで実行する。課題indexごとに旧→新/新→旧の実行順を交互にし、両armともbefore完了後にafterを実行する。
- Uの正解はどちらのworkerにも渡さない。Fの正解はafter supportだけに渡し、before predictionの結果を改変しない。親は4呼出しが終了してからU/Fの予測を採点する。
- workerで全JSON/JSONLファイルのopenを禁止し、事前記憶やpublic datasetの独自読込を防ぐ。唯一の例外はNumPy importが確認する `.venv/Lib/site-packages/numpy-2.3.5.dist-info/direct_url.json` の不存在probe。正規化したこの1パスが存在しない場合だけ通常のFileNotFoundErrorへ進め、内容は読まない。存在したらsource gate/guardで拒否する。不存在とprobe回数を記録する。外部正解表、ID/hash分岐、問題別モデルは使用しない。

## HDSが実行する範囲

生成器を現在supportだけでfitする。同じ機械に対して `HDS接続.候補機構を学習` を実行し、候補は入力だけから生成、比較用教師出力はHDS公開学習経路へ渡す。全教師再現と同値原理採用の両方が成立した場合だけ `出力格子(..., 同値必須=True)` を使用する。新生成器は同じ機能の `admit_to_hds` / `query_via_hds` APIを使用する。候補HOLDではHDS照会を実行せず、`hds_queried=false` を記録する。HDS出力と直接候補を別々に採点する。

HDSは候補=出力という関係を学習・承認する。セル条件木・入力色role／定数色leafの探索自体は実験生成器で行う。観測追加の効果が出ても、永続的なincremental更新やHDS中核が条件木を発見した証拠にはならない。afterのF正解はtraining fitであり、未知入力への改善判定にはUだけを用いる。

両armは同じ35特徴を使う。prune対象は既存leaf判定で2つのdistinct teacher IDまたは最低cell数を満たさない固定subsetだけ。子孫はそのsubsetを細分化するので支持を回復できず、ample budgetでの有効な最小forest・全tieを削らない。固定budgetでは無効枝の探索節約によってbudget-HOLDが変わる可能性があるが、それ自体を正答改善とは呼ばない。学習したcenter/copy leafによるidentityはplaceholderではなく生成予測として通常採点する。

## 証拠と採否

cohortを実行前に新規ファイルへ固定し、既存runは上書きしない。入力dataset、生成器、接続コード、HDSコード、harnessのSHAを記録し、終了時に再照合する。source変化があればrunの有効性を否定する。使用するHDSとhelperはcurrent worktreeであり、frozen v61 full solver評価ではない。各workerは照会の前後に実際に読まれた接続.ARC2／hds学習系統moduleのoriginとSHAをcurrent ROOT配下のfingerprintへ照合し、生成器の接続先が同じHDS moduleであることも確認する。Windowsではprocess wall timeoutだけを設定し、CPU/RAM hard limitは未設定と明示する。既定2m work budgetはfit探索だけの上限であり、full-train replay・query・importの総負荷上限とは呼ばない。これらは90秒worker wall timeoutで捕捉し、失敗を分母に残す。

U/F別に直接候補/HDS出力のbefore/current/delta・gain・regressionを出す。旧→新比較も各phaseの同じUで行う。new correct/old wrongと、仮に2候補を両方使った場合のunion正答数も出すが、生成器familyの補完性に限定し、full submission-policyの証拠とは呼ばない。HOLD、error、timeoutをrequested分母に残し、成功した課題だけに限定しない。input-copy fallbackは作成しないため、生成器が推論したidentityは通常の予測として採点する。予測格子はpipe上で親が採点した後削除し、出力ファイルにはSHAだけを残す。

両armのtyped tree/leaf state、HDS規則のboundary/relation/条件経路・支持数・反例数・対応表SHA、候補/HDS予測SHA、admission/HOLD理由、実行時間を記録する。U/F・phase別に直接候補/HDS出力のcorrect・wrong・HOLD・error/timeoutを分母内で区別する。raw教師格子をmodel stateへ混入した場合は証拠保存を拒否する。state変化だけを性能改善と呼ばない。

改善の採用はこの隔離試験だけで決めない。重複実行、full solverへの最小接続、同条件回帰、時間・提出attempt不変性を別途確認する。今回の既定採否は `UNDECIDED_REQUIRES_REVIEW`。

## 実行

`test_public_harness.py` はdataflow/scoringだけの純粋testでsolverを起動しない。`public_harness.py --prepare-only --output <新規prefix>.jsonl` はcohort固定だけ。実評価はOwner/親agentのreview後に、同じ引数から `--prepare-only` を外し、別の新規prefixを指定する。実評価は `--expected-module-sha256 <reviewed SHA>` が必須。先行prepareの `--expected-cohort-sha256 <cohort SHA>` も渡し、source・課題・U/F・順序・時間条件を含むcohortの完全一致を実行前に照合する。
