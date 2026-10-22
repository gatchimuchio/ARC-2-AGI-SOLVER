# Runtime 起動契約（候補192r2）

既存Python 3.12.14に加え、`requirements-runtime.txt`のNumPy 2.3.5とSciPy 1.17.0を使用する。依存のインストール・更新は本検証では行っていない。ユーザー側の未検証環境で動作確認済みとはしない。

この候補の比較検証プロセスには `OPENBLAS_NUM_THREADS=1` のみを設定する。環境全体の恒久変更ではない。CPU10秒、address space512MiB、wall60秒の通常上限は不変。OMP/MKL等の追加thread設定は行わない。

起動例：

```sh
OPENBLAS_NUM_THREADS=1 python -B 検証/ARC2評価.py --runtime current < input-only.json
```

基底107と候補192は同じ上記条件で再検証する。従来の環境変数無設定の107実績とは区別し、同条件だったとは扱わない。無設定ではSciPy optimizeのimport中にCPU上限へ達した失敗を保持している。元のpure検証が単一OpenBLAS thread条件だったことを明示する。

新規familyの資源未完了は例外として伝播し、HOLDや成功へ読み替えない。HDS中核・通常gateは不変。

WindowsではWSL Ubuntu-24.04の専用環境を使用する。PowerShell 7から次を実行する：

```powershell
pwsh -NoProfile -File 道具/WSL環境構築.ps1
pwsh -NoProfile -File 道具/WSL評価.ps1 -InputPath input-only.json

# 公開120題の正規評価。既存出力は上書きしない。
pwsh -NoProfile -File 道具/WSL評価.ps1 -OutputPath 出力/WSL評価/current.json
```

`--runtime current`は評価器の既存CLIであり、入力は`train`とtestの`input`だけを含むJSON。
WSL用入口も同じ評価器を使い、単問ではLinuxの`timeout`でwall60秒を維持する。
CPU・address space制限は評価器自身が設定する。制約を無効化するWindows用fallbackは設けない。

WSL構築工具は公式uv 0.12.19をchecksum照合して配置し、managed Python 3.12.14と
`requirements-runtime.txt`の固定依存をLinuxユーザーホームに用意する。
Windowsの`.venv`は編集・Notebook・工具試験・Kaggle接続に使用する。
環境再現と過去の全問成績の再現は別々に検証し、資源失敗を成功へ読み替えない。

候補196r2: HiGHSの正式threads optionを1に固定する。SciPy1.17.0のmilpはこのoptionをHiGHSへそのまま転送するが公開supported_options集合外のためRuntimeWarningを出す。警告は隠さない。目的関数・制約・gap・許容・数値証明gateは不変。OpenBLAS1だけではHiGHS thread数を制御できず、初版196は512MiB VMS上限で失敗した。環境変数の追加や資源上限緩和は行わない。参照: https://ergo-code.github.io/HiGHS/dev/options/definitions/#threads
