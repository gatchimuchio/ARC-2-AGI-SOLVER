# 現行full worker・低shot ADAPTIVE2_TO3

この試験は現在の `接続/ARC2/Kaggle提出.py` の実 `_worker` と実 `結果を候補へ` を使用する。旧P3観測追加script（SHA14fe5c）で検証したobserver・A→A+F dataflowを再利用し、独立classだけの試験を繰り返さない。生産コード、候補順、HDS設定、権限、事前記憶、Kaggleは変更しない。現行HDS69ba／worker43fdを使うlocal実験であり、frozen v61 Notebookとは異なる。

## 固定する条件

- 元trainが正確に4例で全inputが異なる189課題から、seed20261027で20課題を固定する。既存FIXED_MIN2低shot cohort SHA3d12810eと課題・U/F・support・入力順が完全一致することを親が確認する。scoreはFIXED_MIN2／既定min3試験へ合算しない。
- beforeはAの2教師、afterはAに観測したFを最後に加えた3教師。両phaseのqueryは同じ `[F.input,U.input]`。U正解はworkerへ渡さず、F正解はafterのtraining pairだけへ渡す。親は両workerが戻ってから採点する。
- 現行HDSの同じコード・policyが2つの異なる入力教師なら最小支持数2、それ以外なら3を選ぶ。constructorへの引数をobserverがそのまま渡し、外側と実内部検証器のfloorを記録する。設定を強制・生成後に変更しない。中心機械はbefore2→after3であり、一定floorの介入ではない。
- したがって変化は、追加Fに対する現行full systemの固定policy下の応答である。純粋なHDS中核の学習因果、保存したstateのincremental更新、production全体や公式scoreの改善とは呼ばない。
- fresh processをphaseごとに順次起動し、各90秒wall timeoutを使用する。Notebookの3並列scheduleとCPU/RAM hard limitは検証していない。

## 事前教材とdata境界

親だけがcanonical template manifestと指定public training pairを読む。現在課題と同じ出典、または現在課題4つ全てのinput（A/F/Uのinputを含む）と衝突するpriorを取り除き、同一の残存IO pairだけを両phaseに注入する。workerへsource task IDや未使用test正解を送らない。template readerは実workerが1回呼ぶ既存経路であり、同一prior SHAを記録する。

現行固定sourceには汎用事前記憶loader・引数・消費branchが存在しない。この観測を `ABSENT_CALL_PATH_PINNED_CURRENT_SOURCE` と記録し、frozen v61にあるneeded-extra算術とは混同しない。isolated workerにvalid empty generic dictionary readerを用意するが、呼出し0・JSON内容open0を必須とする。sourceやcall pathが変わったら停止する。

workerの全JSON/JSONL openを禁止する。唯一の例外は、正規化した `.venv/Lib/site-packages/numpy-2.3.5.dist-info/direct_url.json` が存在しない場合のimport probeで、OSのopen自体へ進まずFileNotFoundErrorを返す。ファイルが出現したら拒否する。内側のsolverが禁止read例外を捕捉しても、外側で記録を検出し `DataBoundaryViolation` とする。親は違反を保存して停止し、後続phase／課題を実行しない。これは通常の不正解やtimeoutとして隠さず、未完了runから能力指標を主張しない。

workerはstdinのtask/prior以外のdatasetを読まない。source fingerprintはPython sourceだけを読み、template元JSONのhashは親だけが確認する。実module originとSHAを実行前後に検査する。

## 実候補と採点

実workerが選んだattempt1/2だけを、実formatterのまま採点する。primary HOLDでも非identity attempt2が正答なら生成候補として数える。有効なidentity予測や、raw HDS HOLDからwrapperが昇格したcandidate pairを入力コピーとして一律除外しない。raw HDS rowのvalidity・status・pair hashとwrapper rowのvalidity・pair昇格を別に記録する。

formatterがHOLD／errorで挿入したinput copyは、rawのofficial-like any-attempt指標に残す一方、nonfallback指標からattemptごとに除く。duplicate2欄を独立した2試行の改善とは呼ばない。wrong・生成候補なしHOLD・error/timeoutとpass@1/2を区別する。Fのafter正答はtraining fitであり、未知への改善はUで判定する。

不正なworker response、solver error、timeoutは同じ実formatterから全queryのcopy fallbackを生成する。全20件を分母に残し、before正答→after timeoutもregressionに数える。paired-completeだけで改善を計算しない。raw指標はerror時のcopy一致も含むため、nonfallback partitionとは別軸で解釈する。

familyごとに、no candidate／teacher counterexample／full train fit without equality／full acceptedの返却stageと原status、prior/current観測数を記録・集計する。これは最終返却stageであり、途中で停止したfamilyの全未実行内部causeを観測したとの主張はしない。中心HDSの正規化rule/state、候補予測SHA、採用flags、時間を保存し、raw gridは親の採点後に除く。

## 実行条件

cohort/source/prior provenanceを実行前に固定し、既存artifactを上書きしない。親でPython実行系・NumPy/SciPy/Kaggle package version・pyproject.toml/uv.lock SHAを記録する。公開実runにはreview済みsource/cohort SHAを渡す。終了時の `source_unchanged`、`parent_prior_sources_unchanged`、`environment_unchanged` が全てTrueでなければ結果は無効。これらのTrueは採用PASSを意味しない。

`test_public_harness.py` は純粋なdataflow・実formatter・境界・分母試験。`synthetic_worker_smoke.py` は人工4pairによる2つの新規process確認で、公開評価ではない。`public_harness.py --prepare-only ...` はcohort固定のみ。親agentがreviewした後にのみ実20件を起動する。公式提出IDの数値score追跡を妨げず、このscriptからPOSTは行わない。
