# CodexからのKaggle実行・提出

## 接続

対象大会は`arc-prize-2026-arc-agi-2`、接続アカウントは`tecchannn`。
Kaggle公式CLIのOAuth認証を使用し、認証情報はユーザーホームの`.kaggle/credentials.json`に保持する。
このrepositoryにはトークンを保存しない。

Codexは以下のコマンドをこのrepositoryのルートで実行できる。
認証の失効時は`python -m uv run --locked kaggle auth login`で再認証する。
APIトークンの表示コマンドや設定全体のログ出力は不要。

```powershell
$env:PYTHONUTF8 = "1"
python -m uv run --locked python -m 接続.Kaggle操作 接続確認
python -m uv run --locked python -m 接続.Kaggle操作 履歴
```

## 実行と提出の経路

```text
ローカルのコード・metadataを確認
→ 送信してKaggle実行を開始
→ Notebook名・版番号・コードhashを実行記録へ保存
→ COMPLETEを確認
→ 指定版の出力を取得・検証
→ ユーザーが提出を指示したら、その版を大会へ提出
→ 受付番号と提出履歴で採点結果を確認
```

「提出して」という指示では、対象Notebookと保存済み実行記録を特定して提出する。
実行記録の版番号を省略したり、暗黙に最新版へ置き換えたりしない。
Notebookのアップロードと大会提出は、それぞれ独立した操作である。

本提出の公式APIは`competition_submit_code`。
`submission.json`は指定Notebookの出力ファイル名であり、手元のJSONを通常のファイル提出へ送る方式ではない。
[Kaggle公式提出手順](https://github.com/Kaggle/kaggle-cli/blob/main/docs/tutorials.md)

## 動作確認用Notebook

`接続/Kaggle動作確認/`を非公開・CPU・インターネット無効で送信する。
公式配布6ファイルの読取りと環境報告だけを行い、`接続確認.json`を生成する。
解答ファイルを生成しないため、このNotebookは大会提出には使わない。

```powershell
python -m uv run --locked python -m 接続.Kaggle操作 送信 --folder 接続/Kaggle動作確認 --timeout 600
```

送信結果に表示された`実行記録`のパスを、以降の操作に渡す。
同じ送信を再実行すると新しいNotebookバージョンが作成される。

```powershell
# 送信結果の実行記録に合わせて設定する。以下は環境構築時の最終版の例。
$runRecord = "出力/Kaggle/arc2-codex-connection-check/v2/実行記録.json"
python -m uv run --locked python -m 接続.Kaggle操作 状態 --record $runRecord
python -m uv run --locked python -m 接続.Kaggle操作 出力 --record $runRecord --path 出力/Kaggle/動作確認出力
```

出力の保存先は空のフォルダを指定する。既存の取得物は上書きしない。
`状態`がRUNNING/QUEUEDなら、適切な間隔で再確認する。ERROR/CANCELLED等は成功として扱わない。

## 本番の準備

ソルバーを実装したら、送信用フォルダへ自己完結した`.py`または`.ipynb`と
`kernel-metadata.json`を置く。例:

```json
{
  "id": "tecchannn/arc2-codex-solver",
  "title": "ARC2 Codex Solver",
  "code_file": "solve.py",
  "language": "python",
  "kernel_type": "script",
  "is_private": true,
  "enable_gpu": false,
  "enable_tpu": false,
  "enable_internet": false,
  "dataset_sources": [],
  "competition_sources": ["arc-prize-2026-arc-agi-2"],
  "kernel_sources": [],
  "model_sources": []
}
```

Notebook形式の場合は`code_file`を`.ipynb`、`kernel_type`を`notebook`にする。
CLIは`code_file`本体を送信するため、同じローカルフォルダに置いた補助moduleやmodelが
自動でKaggleへ同梱されると仮定しない。依存資産はコードへ組み込むか、必要なKaggle Data/Modelを明示接続する。
インターネットなしで起動し、未知のtest入力すべてに対して
`/kaggle/working/submission.json`を生成できることが必要。
GPUを使う場合は実装に応じたmetadata/acceleratorと利用枠を別途確認する。

```powershell
# 完成したソルバーを置いたフォルダを指定
python -m uv run --locked python -m 接続.Kaggle操作 送信 --folder 出力/提出候補 --timeout 43200

# 送信結果の記録へ変更する
$runRecord = "出力/Kaggle/arc2-codex-solver/v1/実行記録.json"
python -m uv run --locked python -m 接続.Kaggle操作 状態 --record $runRecord
python -m uv run --locked python -m 接続.Kaggle操作 出力 --record $runRecord --path 出力/Kaggle/提出候補v1

# この操作で大会へ実際に提出する
python -m uv run --locked python -m 接続.Kaggle操作 提出 --record $runRecord --message "ARC2 solver v1"
python -m uv run --locked python -m 接続.Kaggle操作 履歴
```

提出操作はCOMPLETEと`submission.json`の存在を確認してから、保存済み版番号で送信する。
JSONの解答形式・正解率・時間内完了・hidden rerunへの対応はソルバー側で検証する。
提出受理は採点成功とは異なる。`提出記録-<受付番号>.json`を残し、履歴の同じ番号の結果を確認する。
通信障害で受付の有無が不明な場合は履歴を照合してから対応し、自動再提出しない。

## バージョンの扱い

API契約を実測したKaggle CLI 2.2.4・SDK 0.1.37を`pyproject.toml`で固定している。
このCLIのstatus/output wrapperは、解析した版番号をAPI要求へ渡さない。
SDKの`version_label="1"`も今回の実APIでは404となったため、版番号として使用しない。

- 状態・提出前検査は、APIの`current_version_number`を読取り前後で照合する。
  実行記録と現行版が異なる、または読取り中に版が変わった場合は処理を中断する。
  状態API自体が過去版を指定できるという保証ではない。
- 出力は公式KaggleHubと同じ`ApiDownloadKernelOutputRequest.version_number`で版を固定して取得する。
  [公式実装](https://github.com/Kaggle/kagglehub/blob/main/src/kagglehub/http_resolver.py)
- 大会提出には`kernel_version`を必ず渡す。

採点対象を確定するまでは、同じNotebookに別の版を送信しない運用を基本とする。
過去版の出力取得と、現行版に限る状態・提出前検査を区別する。
