# 後半走破の開始点60: 全未解決課題の棚卸しと戻値観測

## 到達状態

開始時mainは `cc668e34d7ca014daf9f8944767476d56c56fafc`、treeは `08b4161457909e8575fa365abbcb5ed176bf3ef1`。全328blobと公式submodule pin `f3283f727488ad98fe575ea6a5ac981e4a188e49` を照合した。

同じcloud環境の新しいcheckoutで全120課題/167例を再実行し、60完全課題、84正答例、83HOLD、誤格子0、資源失敗0。全120の実行記録が従来の固定60地点と完全一致し、全67回帰script/1091testが通過した。旧指標 `wrong_attempted_tasks=7` は正答を含む部分回答7課題であり、誤格子7件を意味しない。

この追加は観測標本であり、solver能力の改善を主張しない。既存67台帳と二つの観測研究の原本は変更していない。

## 全60課題のteacher-only棚卸し

重複しない20課題ずつの3群に分け、train input/outputだけを観測した。各課題の記録は指定10項目を保ち、対象集合60件・部分回答7件・未回答83例の網羅を独立監査した。

分類は「次に必要な作業」の教師根拠付き仮分類であり、query正答の確認ではない。

- 既存primitiveの組合せ: 9
- 新しい入力view: 13
- 新しい関係表現: 17
- 新しい作用: 3
- 現行表現では原因未確定: 18
- 既存familyだけで閉じる/範囲拡張だけで閉じると確認済み: 0

`未解決60観測.json` が正本。`teacher-only三分割観測.tar.gz` は各群の原観測、教師限定診断コード、JSON、画像を無損失で保存する。`三分割観測manifest.json` に58原ファイルのbyte数とSHA256を記録した。

## 全120課題の別観測replay

solverを変更せず、候補器の返却値を透明wrapperで記録した。各課題はfresh subprocess、CPU10秒/512MiB/wall60秒、並列3。wrapperが値を変えていないことは、全120のsolver結果がfresh基準と全文一致したことで確認した。

- 候補呼出8503件
- `None` を返した候補生成7980件
- 最終query HOLD83件
- 入力変更・例外・資源失敗0
- v2は完全diagnosticと候補格子hash、最終solver結果を保存（raw約7.15MB、gzip約660KB）
- 別凍結のv3で候補格子本体523件とNone7980件を追加保存。全8503旧call記録・全120solver結果がv2と完全一致し、各格子hashも照合

失敗索引8063件はrawの行番号・JSON Pointer・展開後SHA256に結び、理由を推測で補完していない。呼出数をHDSの支持数へ読み替えない。v3は候補器が返した格子とdiagnosticの完全保存であり、候補器内部で返却されなかった全仮説や過去の失われた診断を復元したという意味ではない。

部分回答7課題の追加観測では、並進軸同率、障害横断、元の基部との衝突、HDS方向未確定、区切役割の非一意、最大保持軸同率、支持floor役割の非一意が返された。これはguardの実測であり、それを弱めれば正答するという証拠ではない。

## 凍結と情報分離

runtimeへ渡す課題はtrainとtest inputだけ。test正解と課題IDは親scorerのみに置く。replayにはPythonの監査可能なopenについて、正規化したevaluation原本/solutionsへのアクセスを拒否するhookを追加した。OS全体のファイル隔離や過去を含む完全未見を保証するものではない。

公式source評価は公開データ上の開発でありhidden汎化評価ではない。固定source由来challengesのSHA256は `bd9a3bdd8d176764412108eb3a1a6cb8b792a9c6fe2567532c186b2e3e4bd3bb`。既存ZIPマニフェストとのbyte差異および旧作業の偶発的challenge露出/filename走査の留保は取り消さない。workspace巻戻りで失われた未公開過去証拠も復元済みとは扱わない。

同一instance保持の利用可能出力FAIL、別境界の識別不能性によるHOLD伝播、native保存exit137が2回という既存観測は、[保持研究](../../同一学習機械保持/README.md)および[既存台帳](../../../学習台帳/README.md)を参照する。今回のfresh課題solverの60/84保持と混同しない。Learning Machine vNextは実装していない。

## 再現

開始点commitを取得し公式submoduleを固定pinへ置く。`全120基準評価.json.gz` と `既存84格子比較.json.gz` はgzip展開後の原JSON。candidate trace、失敗索引はJSONL。失敗索引は原v2 traceを参照する。v3は同じcall記録にcandidate格子を加えた別原本として保存し、旧trace/freezeは変更していない。tar内のファイルはmanifestと個別SHA256を照合できる。

`候補観測replay_v3.py --root <開始点repo> --baseline <展開した全120基準評価.json> --output <新規directory>` で追加replayを実行できる。観測群内の一部診断scriptは実行時の絶対workspace pathを原文のまま保存している。別環境での実行にはroot/sourceの対応付けが必要であり、移植後のscriptを原実行済みcodeと混同しない。`manifest.json` は公開package各ファイルの完全bytesを検証する。
