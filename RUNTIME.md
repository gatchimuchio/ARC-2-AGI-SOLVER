# Runtime 起動契約（候補192r2）

既存Python 3.12.14に加え、`requirements-runtime.txt`のNumPy 2.3.5とSciPy 1.17.0を使用する。依存のインストール・更新は本検証では行っていない。ユーザー側の未検証環境で動作確認済みとはしない。

この候補の比較検証プロセスには `OPENBLAS_NUM_THREADS=1` のみを設定する。環境全体の恒久変更ではない。CPU10秒、address space512MiB、wall60秒の通常上限は不変。OMP/MKL等の追加thread設定は行わない。

起動例：

```sh
OPENBLAS_NUM_THREADS=1 python -B 検証/ARC2評価.py --runtime current < input-only.json
```

基底107と候補192は同じ上記条件で再検証する。従来の環境変数無設定の107実績とは区別し、同条件だったとは扱わない。無設定ではSciPy optimizeのimport中にCPU上限へ達した失敗を保持している。元のpure検証が単一OpenBLAS thread条件だったことを明示する。

新規familyの資源未完了は例外として伝播し、HOLDや成功へ読み替えない。HDS中核・通常gateは不変。

PowerShellでは現プロセスとその子だけに設定する（`setx`による永続化は不要）：

```powershell
$previousOpenBlas = $env:OPENBLAS_NUM_THREADS
try {
    $env:OPENBLAS_NUM_THREADS = '1'
    Get-Content -Raw input-only.json | python -B 検証/ARC2評価.py --runtime current
} finally {
    $env:OPENBLAS_NUM_THREADS = $previousOpenBlas
}
```

上記`--runtime current`は評価器の既存CLIであり、入力は`train`とtestの`input`だけを含むJSON。POSIX側のコマンドは本環境で実行確認済み。PowerShell例は本環境にPowerShellがないため未実行。

候補196r2: HiGHSの正式threads optionを1に固定する。SciPy1.17.0のmilpはこのoptionをHiGHSへそのまま転送するが公開supported_options集合外のためRuntimeWarningを出す。警告は隠さない。目的関数・制約・gap・許容・数値証明gateは不変。OpenBLAS1だけではHiGHS thread数を制御できず、初版196は512MiB VMS上限で失敗した。環境変数の追加や資源上限緩和は行わない。参照: https://ergo-code.github.io/HiGHS/dev/options/definitions/#threads
