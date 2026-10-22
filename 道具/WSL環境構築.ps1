[CmdletBinding()]
param([string]$Distribution = 'Ubuntu-24.04')

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$linuxRoot = & wsl.exe --distribution $Distribution --exec wslpath -a -u $projectRoot
if ($LASTEXITCODE -ne 0 -or -not $linuxRoot) {
    throw 'The selected WSL distribution is unavailable.'
}
$linuxRoot = ($linuxRoot | Out-String).Trim()

# This script only manages the dedicated Linux directory, never Windows .venv.
# The shell body is fixed; the repository path is a positional argument.
$setup = @'
set -eu
repo=$1
base="$HOME/.local/share/arc2-wsl"
if [ "$(uname -m)" != x86_64 ]; then
    printf '%s\n' 'This runtime setup currently supports WSL x86_64 only.' >&2
    exit 1
fi
test -f "$repo/requirements-runtime.txt"
mkdir -p "$base/bin" "$base/downloads"
if [ -e "$base/bin/uv" ] || [ -L "$base/bin/uv" ]; then
    case "$("$base/bin/uv" --version)" in
        'uv 0.12.19 '*) ;;
        *) printf '%s\n' 'Existing ARC2 uv is not 0.12.19; it was not overwritten.' >&2; exit 1 ;;
    esac
else
    staging=$(mktemp -d "$base/downloads/bootstrap.XXXXXX")
    archive=uv-x86_64-unknown-linux-gnu.tar.gz
    release=https://github.com/astral-sh/uv/releases/download/0.12.19
    curl -fsSL --retry 2 --max-time 180 -o "$staging/$archive" "$release/$archive"
    curl -fsSL --retry 2 --max-time 60 -o "$staging/$archive.sha256" "$release/$archive.sha256"
    (cd "$staging" && sha256sum -c "$archive.sha256")
    tar -xzf "$staging/$archive" -C "$staging" uv-x86_64-unknown-linux-gnu/uv
    install -m 755 "$staging/uv-x86_64-unknown-linux-gnu/uv" "$base/bin/uv"
fi
"$base/bin/uv" --no-config python install --no-bin --install-dir "$base/python" 3.12.14
managed="$base/python/cpython-3.12.14-linux-x86_64-gnu/bin/python3.12"
if [ -L "$base/runtime" ]; then
    printf '%s\n' 'Existing ARC2 runtime is a symlink; its target was not modified.' >&2
    exit 1
fi
if [ -e "$base/runtime" ]; then
    test -f "$base/runtime/pyvenv.cfg" && test -x "$base/runtime/bin/python" || {
        printf '%s\n' 'Existing ARC2 runtime is not a virtual environment; it was not overwritten.' >&2
        exit 1
    }
    "$base/runtime/bin/python" -c 'import sys; assert sys.version_info[:3] == (3, 12, 14), "Existing ARC2 Python version differs; environment was not overwritten"'
else
    "$base/bin/uv" --no-config venv --python "$managed" "$base/runtime"
fi
"$base/bin/uv" --no-config pip install --python "$base/runtime/bin/python" -r "$repo/requirements-runtime.txt"
"$base/bin/uv" --no-config pip check --python "$base/runtime/bin/python"
env OPENBLAS_NUM_THREADS=1 "$base/runtime/bin/python" -B -c 'import json, platform, sys, numpy, scipy; print(json.dumps({"python": platform.python_version(), "executable": sys.executable, "numpy": numpy.__version__, "scipy": scipy.__version__}))'
'@

$setup | & wsl.exe --distribution $Distribution --exec sh -s -- $linuxRoot
exit $LASTEXITCODE
