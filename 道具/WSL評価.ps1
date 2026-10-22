[CmdletBinding(DefaultParameterSetName = 'Evaluation')]
param(
    [ValidateSet('current', 'baseline')]
    [string]$Mode = 'current',

    [Parameter(Mandatory = $true, ParameterSetName = 'Runtime')]
    [string]$InputPath,

    [Parameter(ParameterSetName = 'Evaluation')]
    [string]$OutputPath,

    [string]$Distribution = 'Ubuntu-24.04'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot

function Convert-ToLinuxPath([string]$Path) {
    $converted = & wsl.exe --distribution $Distribution --exec wslpath -a -u $Path
    if ($LASTEXITCODE -ne 0 -or -not $converted) {
        throw 'WSL path conversion failed.'
    }
    return ($converted | Out-String).Trim()
}

function Resolve-ProjectPath([string]$Path) {
    if (-not [System.IO.Path]::IsPathRooted($Path)) {
        $Path = Join-Path $projectRoot $Path
    }
    return [System.IO.Path]::GetFullPath($Path)
}

$linuxHome = & wsl.exe --distribution $Distribution --exec printenv HOME
if ($LASTEXITCODE -ne 0 -or -not $linuxHome) {
    throw 'The selected WSL distribution is unavailable.'
}
$linuxPython = ($linuxHome | Out-String).Trim() + '/.local/share/arc2-wsl/runtime/bin/python'
& wsl.exe --distribution $Distribution --exec test -x $linuxPython
if ($LASTEXITCODE -ne 0) {
    throw 'ARC2 WSL runtime is missing. See RUNTIME.md for setup.'
}
$linuxRoot = Convert-ToLinuxPath $projectRoot
$evaluator = $linuxRoot + '/検証/ARC2評価.py'

if ($PSCmdlet.ParameterSetName -eq 'Runtime') {
    $inputFile = Resolve-ProjectPath $InputPath
    if (-not (Test-Path -LiteralPath $inputFile -PathType Leaf)) {
        throw 'InputPath must point to an existing input-only JSON file.'
    }
    $linuxInput = Convert-ToLinuxPath $inputFile
    # Positional shell arguments preserve paths without interpolating them as code.
    # The repository evaluator sets CPU/AS limits and validates the input schema.
    & wsl.exe --distribution $Distribution --cd $linuxRoot --exec sh -c 'exec timeout --signal=KILL 60s env OPENBLAS_NUM_THREADS=1 "$1" -B "$2" --runtime "$3" < "$4"' sh $linuxPython $evaluator $Mode $linuxInput
    exit $LASTEXITCODE
}

if (-not $OutputPath) {
    $OutputPath = '出力/WSL評価/' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json'
}
$outputFile = Resolve-ProjectPath $OutputPath
if (Test-Path -LiteralPath $outputFile) {
    throw 'OutputPath already exists. Choose a new path to preserve previous evidence.'
}
$null = [System.IO.Directory]::CreateDirectory((Split-Path -Parent $outputFile))
$linuxOutput = Convert-ToLinuxPath $outputFile
# OPENBLAS_NUM_THREADS only affects this Linux process and its children.
& wsl.exe --distribution $Distribution --cd $linuxRoot --exec env OPENBLAS_NUM_THREADS=1 $linuxPython -B $evaluator --mode $Mode --output $linuxOutput
exit $LASTEXITCODE
