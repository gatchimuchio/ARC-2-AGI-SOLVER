# Kaggle直接提出環境の構築結果

確認日: 2026-09-29

目的: CodexからKaggleの認証・Notebook送信・実行確認・出力取得・版指定提出・履歴確認を操作できるようにする。

## 成立した状態

- アカウント`tecchannn`のOAuth認証が成立。公式CLIのユーザーホーム認証ファイルを使用する。
- 対象大会`arc-prize-2026-arc-agi-2`のファイル一覧・本人の提出履歴を取得できる。
- 大会ZIPを取得・展開し、ZIPおよび6ファイルのサイズ・SHA256が既存マニフェストと完全一致した。
- 非公開・CPU・internet無効の動作確認Notebookのv1/v2がともにCOMPLETEとなった。
- v2公開後にv1を再取得してもv1の内容が保持され、v2とは異なることを確認した。
- 古いv1の記録を使う状態照会は終了code 1で拒否し、現行v2の状態照会は成功した。
- 実APIの状態・出力一覧を使用した提出前検査が、動作確認Notebookの`submission.json`欠落を検出した。
  この検査では提出APIを呼べない代替関数を置き、実際に呼ばれなかったことも確認した。

[動作確認Notebook](https://www.kaggle.com/code/tecchannn/arc2-codex-connection-check)

取得物と実行記録はGit対象外の`出力/Kaggle/arc2-codex-connection-check/v1/`および`v2/`に保存する。
両版でKaggle側の配布6ファイルも既存マニフェストと完全一致した。

## 検証

| 対象 | 結果 |
| --- | --- |
| pytest | 59 tests・10 subtests合格 |
| Ruff | 合格 |
| 既存リポジトリ監査 | 合格 |
| 開発環境確認 | 合格、大会配布6ファイル取得済み |
| uv依存確認 | 113 packagesの整合性合格、lock一致 |
| 秘密情報 | repository内のKaggle APIトークン形式の一致なし |
| 提出履歴 | 開始時と終了時で同じ5件。今回の新規大会提出なし |

Kaggleの実測環境はLinux、Python 3.12.13、NumPy 2.0.2、PyTorch 2.10.0+cpu、
pandas 2.3.3、Transformers 5.0.0。これは今回のCPUセッションの観測であり、GPU環境や将来のNotebook環境を保証しない。

## 実APIとの適合

送信応答の`ref`は`/code/owner/slug`形式だったため、対象を正規化してmetadataのidと一致確認する。
初回の記録保存停止後は自動再送せず、リモートの版・コード・設定を読み取り照合して実行記録を復旧した。
v2の記録は観測済み送信応答を修正後の処理へ再入力して復旧し、その際の追加送信は行っていない。

statusの`version_label="1"`は実APIで404となったため、現行版番号の前後一致によって観測対象を限定する。
出力取得は`ApiDownloadKernelOutputRequest.version_number`を使用する。
本提出は公式`competition_submit_code`の`kernel_version`を必須指定する。
詳細は[`接続/Kaggle提出.md`](../接続/Kaggle提出.md)を参照。

## 採否・範囲

前: ローカル開発環境とCLIのみ。Kaggle認証・配布データ取得は未完了。
後: 認証、配布データ取得、非公開Notebook送信・実行・版別出力取得が実測で成立。
提出操作は公式API引数と拒否条件をローカル試験し、実APIで提出前検査まで確認した。
採否: 直接提出の操作環境としてADMIT。

大会への新規提出・採点受理・GPU実行・ソルバー精度は今回未検証。
動作確認Notebookは解答を生成しない。今後、完成したソルバーと提出対象版を指定して使用する。
Kaggleには確認用Notebookの2バージョンを保存した。repositoryの変更はローカル保存でcommit・pushは未実施。
Gitの取得元mainは`536ff316acc811fa64f851a28d4588ee21811f9a`。
