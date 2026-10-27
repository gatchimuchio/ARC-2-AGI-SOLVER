# 凍結v61 全体締切制御・隔離レビュー版

状態は **ISOLATED / NOT ADOPTED**。本番・現行worker/HDS・実際のv61 Notebook/payload/提出記録/intentは変更していない。公開課題、HDS、Kaggle照会・提出・pushは実行していない。実プロセス試験は人工のJSON workerとsleepだけを使う。

## 凍結部分と差分

- 元worker `c20102c4e9a01e833ca8f9e2778b5306333c50c065d9aebe7cbeaf574e74418d` を `Kaggle提出.py` へ複製。変更は `_run_one` と `run_cli` の実行管理のみ。`_worker`、入力・提出検査、既存formatterとその他top-level ASTは元と同一。
- 元runner `d47dac81dbcb9cd9a151fa7461145b5ac708291dbb52af8a4099e20efbc4a791` を `solve.py` へ複製。`main` だけを変更し、payload準備前のmonotonic開始時刻を保持して隔離adapterを呼ぶ。payload抽出関数・埋込みpayloadは同一。
- `deadline_control.py` はstdlibだけのプロセス・queue・出力管理。新しい解法ではない。
- `outer_watchdog.py` と `deadline_notebook_template.ipynb` は新しい隔離外側watchdog。元の公式Notebookへは配線していない。templateはレビュー済みファイル群が `ARC2_DEADLINE_VARIANT_ROOT` に置かれている前提であり、Kaggle用の新bundleは作成していない。

## 時間と子プロセス

課題上限300秒・並列3を保持する。既定のrun budgetは42600秒、最終化reserve600秒、cleanup grace3秒、外側終了reserve10秒。外側は開始時の絶対monotonic締切を子runnerへ渡す。未来の開始時刻・非有限値・reserve不足は拒否する。preflightと課題待機・cleanupは残時間で短縮する。

全件をexecutorへ先行投入せず、inflightを最大3件とする。cutoff後は新規投入を止め、未開始を取消し、active processの終了・回収を行う。生きたworker threadが残る場合は `CleanupIncompleteRequiresOuterWatchdog` などで失敗し、`shutdown(wait=False)` だけを終了保証と扱わない。外側がrunnerを別process/sessionで所有するため、子のThreadPool interpreter終了joinが残っても外側から停止できる。

stdin/stdout/stderrは一時通常ファイルで渡し、PIPE EOF待ちを使わない。読み込みは既定16MiBまで。超過は `worker_output_limit` という明示的な運用失敗であり、正答・能力改善に読み替えない。通常の非zero終了でも有効JSONなら元 `_run_one` と同様にformatterへ渡す。

LinuxはPython 3.11以上を必須とする。外側runnerは専用session、内側workerはそのsession内の専用process group。課題終了時はleaderが先に終了していてもgroupへ終了要求を送る。外側は `/proc` で所有session内の非zombie groupを確認・終了する。実際のKaggle Linux imageでの実行は未検証。

Windowsは64bit HANDLE型を明示したJobObjectを使用する。割当失敗・TerminateJobObjectの失敗は親だけ回収して成功扱いせず、cleanup未確認としてfail closed。直接子の回収とtree終了要求のacknowledgementを分けて記録する。PopenからJob割当までのraceは解消していないため、Windowsの無条件tree保証は主張しない。

OSのprocess作成・filesystem処理自体が停止する場合までは制御できない。短時間の合成試験だけでNotebook全体の12時間保証を証明したとは扱わない。

## 完全な出力と保護

preflight失敗は失敗のままで、submission/audit/snapshotをseedしない。成功後、すべてのID・test順序・2attemptを満たす入力コピーを、未処理fallbackと明記して確保する。完了したworker結果だけを反映し、未処理は `global_deadline` / `outer_watchdog_deadline`。`scientific_correctness_evaluated=false`、`solved_count=null` を維持する。

`deadline_owned_snapshot.json` にsubmissionとauditの両方を一つのowned blobとして原子的に保存し、その後に公開2ファイルを導出する。公開途中でrunnerを停止した場合も、外側はrun token・preflight・challenge hash・submission hash・全ID形式を検証したblobから復旧する。

canonicalファイルは直前または今回の自分のpublication hashに一致する場合だけ復旧できる。初回の不在を許すのはprevious hashがNoneの場合だけ。既存submission/audit/snapshotは実行開始時に拒否し、外国tokenや予期しない外部変更は上書きしない。これは単一writer運用のownership検査であり、敵対的な同時writerに対するatomic CASや、disk crash耐久性の証明ではない。

正常終了時の `submission.json` は、十分な予算の合成比較で元版とbyte一致を検証する。auditは締切・ownership metadataが加わるため同一ではない。外側が期限でrunnerを停止しても、有効なowned snapshotがなければfail closed。snapshotがあることだけで終了したとせず、runner/treeの回収を確認してから外側を完了させる。

## 検証

```powershell
& '.venv/Scripts/python.exe' -m pytest -q '運用/証拠/ARC26-UNIFIED/ARC2-v61-global-deadline-isolated/test_deadline_control.py' '運用/証拠/ARC26-UNIFIED/ARC2-v61-global-deadline-isolated/test_outer_watchdog.py'
```

検証対象は、凍結AST、通常/非zero JSONのbyte一致、queued/active cutoff、親例外cleanup、preflight失敗、共有clock、既存出力・ownership、出力超過、子孫stdio、Job API失敗、外側のinterpreter join停止、公開途中のowned pair復旧、実際の新Notebook template配線。最終結果・SHAは `static-validation.json` に記録する。
