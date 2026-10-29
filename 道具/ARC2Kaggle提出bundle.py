"""現行HDS接続をKaggleの単一オフラインkernel fileへ梱包する。"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile
import zlib


ROOT = Path(__file__).resolve().parents[1]
COMPETITION = "arc-prize-2026-arc-agi-2"
KERNEL = "tecchannn/arc2-codex-main-baseline-v1"
TEMPLATE = r'''#!/usr/bin/env python3
"""ARC2 Kaggle submission adapter; the bundled HDS source is checksum-verified."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tempfile
import zipfile

SOURCE_COMMIT = __SOURCE_COMMIT__
PAYLOAD_SHA256 = __PAYLOAD_SHA256__
PAYLOAD_B64 = (
__PAYLOAD_B64__
)


def payload_root():
    requested = os.environ.get("ARC2_PAYLOAD_ROOT")
    if requested:
        destination = Path(requested).resolve()
    elif Path("/kaggle/working").is_dir():
        destination = Path("/kaggle/working/arc2_payload").resolve()
    else:
        destination = (Path(tempfile.gettempdir()) / f"arc2_payload_{PAYLOAD_SHA256[:12]}").resolve()
    marker = destination / "__arc2_payload_sha256.txt"
    cached = marker.is_file() and marker.read_text(encoding="ascii").strip() == PAYLOAD_SHA256
    if not cached and destination.exists() and any(destination.iterdir()):
        raise RuntimeError("payload destination is non-empty and unverified")
    data = base64.b64decode(PAYLOAD_B64, validate=True)
    if hashlib.sha256(data).hexdigest() != PAYLOAD_SHA256:
        raise RuntimeError("HDS payload checksum mismatch")
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        manifest_name = "__arc2_bundle_manifest__.json"
        if not names or names[0] != manifest_name:
            raise RuntimeError("HDS payload manifest is missing")
        manifest = json.loads(archive.read(manifest_name))
        expected = {row["path"]: row for row in manifest["files"]}
        if len(set(names)) != len(names) or len(expected) != len(manifest["files"]) or set(names[1:]) != set(expected):
            raise RuntimeError("HDS payload file set mismatch")
        if cached:
            for path in destination.rglob("*"):
                relative_name = path.relative_to(destination).as_posix()
                if (relative_name not in expected and (path.is_file() or path.is_symlink())
                        and path.suffix.lower() in {".py", ".pyc", ".pyo", ".pyd", ".so", ".dll"}):
                    raise RuntimeError("HDS cached payload contains an unexpected executable")
        for name in names[1:]:
            relative = PurePosixPath(name)
            if relative.is_absolute() or ".." in relative.parts or "\\" in name:
                raise RuntimeError("unsafe path in HDS payload")
            target = destination.joinpath(*relative.parts)
            node = destination
            for part in relative.parts:
                node = node / part
                if node.is_symlink():
                    raise RuntimeError("HDS payload path contains a symlink")
            if cached:
                if not target.is_file():
                    raise RuntimeError("HDS cached payload member missing")
                content = target.read_bytes()
            else:
                content = archive.read(name)
            row = expected[name]
            if len(content) != row["size"] or hashlib.sha256(content).hexdigest() != row["sha256"]:
                raise RuntimeError("HDS payload member checksum mismatch")
            if not cached:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
    if not cached:
        marker.write_text(PAYLOAD_SHA256 + "\n", encoding="ascii")
    return destination


def main():
    sys.dont_write_bytecode = True
    root = payload_root()
    os.environ["ARC2_PAYLOAD_ROOT"] = str(root)
    os.environ["ARC2_SOURCE_COMMIT"] = SOURCE_COMMIT
    os.environ["ARC2_WORKER_LAUNCHER"] = str(Path(__file__).resolve())
    sys.path.insert(0, str(root))
    from 接続.ARC2.Kaggle提出 import run_cli

    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _runtime_files() -> list[tuple[str, Path]]:
    """Whitelist only solver modules and the declared public training material."""
    template_path = ROOT / "接続/ARC2/テンプレート充填教材.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    if template.get("分割") != "training":
        raise ValueError("事前教材の分割はtrainingでなければならない")
    references = template.get("教材")
    if not isinstance(references, list) or not references:
        raise ValueError("事前教材の参照一覧が空または不正")
    task_ids = set()
    for row in references:
        task_id = row.get("課題ID") if isinstance(row, dict) else None
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("事前教材の課題IDが不正")
        task_ids.add(task_id)

    selected: dict[str, Path] = {}
    # The recovered solver is allowed only through its audited input-only adapter:
    # solve_task receives cleaned train/test grids, and runtime fit metadata uses
    # the constant "runtime_task". ID and solution loaders stay in offline reports.
    for base in (
        ROOT / "HDS/学習系統/v0.4.2/hds学習系統",
        ROOT / "接続/ARC2",
    ):
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts or path.is_symlink():
                continue
            # The recovered v4 solver contains task-specific runtime branches.
            # Keep those local artifacts out of every generated Kaggle payload.
            if path.name.startswith("legacy_v4_"):
                continue
            relative = path.relative_to(ROOT).as_posix()
            # This proof-search candidate failed its preregistered pass@2
            # confirmation. Keep its source for research, but do not ship it.
            if relative in {
                "接続/ARC2/arc_proof_search.py",
                "接続/ARC2/汎用プログラム帰納候補.py",
            }:
                continue
            selected[relative] = path
    # The exact-rule generator is distributed under MIT-0. Keep its full
    # permission notice beside the source in the offline Kaggle payload.
    external_source = "接続/ARC2/第三者/NVARC/merge_agreement.py"
    if external_source in selected:
        license_path = ROOT / "接続/ARC2/第三者/NVARC/LICENSE"
        if license_path.is_symlink() or not license_path.is_file():
            raise FileNotFoundError("NVARC third-party license is missing")
        selected[license_path.relative_to(ROOT).as_posix()] = license_path
    # 未観測端対応教材がimportするルート直下の実装と、そのpeer演算依存。
    for name in ("missing_edge_bindings.py", "peer_edge.py"):
        path = ROOT / name
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError(f"runtime依存moduleがありません: {name}")
        selected[path.relative_to(ROOT).as_posix()] = path
    selected[template_path.relative_to(ROOT).as_posix()] = template_path
    training = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
    for task_id in sorted(task_ids):
        path = training / f"{task_id}.json"
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError(f"宣言済みtraining教材がありません: {task_id}")
        selected[path.relative_to(ROOT).as_posix()] = path

    paths = sorted(selected.items())
    for name, path in paths:
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts:
            raise ValueError(f"payload path is unsafe: {name}")
        if "evaluation" in pure.parts or "solutions" in pure.name.lower():
            raise ValueError(f"evaluation/solution data is excluded from the payload: {name}")
    return paths


def _make_payload(files: list[tuple[str, Path]]) -> tuple[bytes, list[dict[str, object]]]:
    manifest: list[dict[str, object]] = []
    contents: dict[str, bytes] = {}
    for name, path in files:
        data = path.read_bytes()
        pure = PurePosixPath(name)
        training_root = PurePosixPath("入力/公式ソース/ARC-AGI-2/data/training")
        if pure.parent == training_root and pure.suffix == ".json":
            material = json.loads(data.decode("utf-8"))
            if not isinstance(material, dict) or not isinstance(material.get("train"), list):
                raise ValueError("training教材のtrainが不正です")
            data = json.dumps({"train": material["train"]}, ensure_ascii=False,
                              sort_keys=True, separators=(",", ":")).encode("utf-8")
        contents[name] = data
        manifest.append(
            {"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        )
    manifest_bytes = json.dumps(
        {"format": "arc2-hds-kernel-bundle-v1", "files": manifest},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in [("__arc2_bundle_manifest__.json", manifest_bytes), *sorted(contents.items())]:
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return output.getvalue(), manifest


def _render_launcher(payload: bytes, source_commit: str) -> bytes:
    encoded = base64.b64encode(payload).decode("ascii")
    chunks = [f'    "{encoded[offset:offset + 100]}"' for offset in range(0, len(encoded), 100)]
    source = (
        TEMPLATE.replace("__SOURCE_COMMIT__", repr(source_commit))
        .replace("__PAYLOAD_SHA256__", repr(hashlib.sha256(payload).hexdigest()))
        .replace("__PAYLOAD_B64__", "\n".join(chunks))
    )
    return source.encode("utf-8")


def _render_notebook(launcher: bytes, payload_sha256: str) -> bytes:
    """大会条件に合わせ、runnerを内包する実行可能なNotebookを作る。"""
    runner_sha256 = hashlib.sha256(launcher).hexdigest()
    encoded = base64.b64encode(zlib.compress(launcher, level=9)).decode("ascii")
    chunks = [f'        "{encoded[offset:offset + 1000]}"' for offset in range(0, len(encoded), 1000)]
    source = "\n".join(
        [
            "import base64",
            "import hashlib",
            "import os",
            "from pathlib import Path",
            "import subprocess",
            "import sys",
            "import tempfile",
            "import zlib",
            "",
            f"RUNNER_SHA256 = {runner_sha256!r}",
            f"PAYLOAD_SHA256 = {payload_sha256!r}",
            "RUNNER_B64 = (",
            *chunks,
            ")",
            "runner = zlib.decompress(base64.b64decode(RUNNER_B64, validate=True))",
            "if hashlib.sha256(runner).hexdigest() != RUNNER_SHA256:",
            '    raise RuntimeError("Notebook runner checksum mismatch")',
            "temp_root = Path(tempfile.gettempdir())",
            'runner_path = temp_root / f"arc2_runner_{RUNNER_SHA256[:12]}.py"',
            "runner_path.write_bytes(runner)",
            'work_dir = Path("/kaggle/working")',
            'if not work_dir.is_dir():',
            '    work_dir = Path(os.environ.get("ARC2_OUTPUT_DIR", Path.cwd())).resolve()',
            'payload_root = temp_root / f"arc2_payload_{PAYLOAD_SHA256[:12]}"',
            "environment = {**os.environ, \"ARC2_PAYLOAD_ROOT\": str(payload_root)}",
            'arguments = [sys.executable, str(runner_path), "--output-dir", str(work_dir)]',
            'challenges = os.environ.get("ARC2_CHALLENGES")',
            "if challenges:",
            '    arguments.extend(["--challenges", challenges])',
            "subprocess.run(arguments, check=True, env=environment)",
            "",
        ]
    )
    cell_id = hashlib.sha256(
        b"arc2-kernel-main-cell-v1\0" + source.encode("utf-8")
    ).hexdigest()[:12]
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "id": cell_id,
                "metadata": {},
                "outputs": [],
                "source": [line + "\n" for line in source.splitlines()],
            }
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    return (json.dumps(notebook, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def stage_upload(source: Path, output: Path) -> dict[str, object]:
    """NotebookとmetadataだけのKaggle送信フォルダを作る。"""
    source = source.expanduser().resolve()
    output = output.expanduser()
    if not output.is_absolute():
        output = ROOT / output
    output = output.resolve()
    output_root = (ROOT / "出力").resolve()
    if not output.is_relative_to(output_root):
        raise ValueError("送信フォルダはrepositoryの出力/内に限る")
    if output.exists():
        raise FileExistsError(f"既存の送信フォルダを上書きしない: {output}")
    metadata_path = source / "kernel-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("kernel_type") != "notebook" or metadata.get("code_file") != "main.ipynb":
        raise ValueError("Kaggle送信物はmain.ipynbを使うNotebook型でなければならない")
    code = source / "main.ipynb"
    if not code.is_file():
        raise FileNotFoundError("Notebook sourceがありません")
    output.mkdir(parents=True)
    (output / "main.ipynb").write_bytes(code.read_bytes())
    (output / "kernel-metadata.json").write_bytes(metadata_path.read_bytes())
    return {
        "upload_directory": str(output),
        "files": ["main.ipynb", "kernel-metadata.json"],
        "code_sha256": hashlib.sha256(code.read_bytes()).hexdigest(),
        "metadata_sha256": hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
    }


def build(output: Path, *, allow_dirty: bool = False, kernel: str = KERNEL) -> dict[str, object]:
    output = output.expanduser()
    if not output.is_absolute():
        output = ROOT / output
    output = output.resolve()
    output_root = (ROOT / "出力").resolve()
    if not output.is_relative_to(output_root):
        raise ValueError("出力先はrepositoryの出力/内に限る")
    if output.exists():
        raise FileExistsError(f"既存の出力先を上書きしない: {output}")
    if not isinstance(kernel, str) or "/" not in kernel:
        raise ValueError("Kaggle kernel idはowner/slug形式が必要")

    status = _git("status", "--porcelain")
    if status and not allow_dirty:
        raise RuntimeError("cleanなcommitからbuildしてください。作業中は--allow-dirtyのみ許可")
    source_commit = _git("rev-parse", "HEAD") + ("+dirty" if status else "")
    submodule_commit = _git("-C", "入力/公式ソース/ARC-AGI-2", "rev-parse", "HEAD")
    files = _runtime_files()
    payload, manifest = _make_payload(files)
    launcher = _render_launcher(payload, source_commit)
    notebook = _render_notebook(launcher, hashlib.sha256(payload).hexdigest())
    metadata = {
        "id": kernel,
        "title": "ARC2 Codex Main Baseline v1",
        "code_file": "main.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": False,
        "enable_tpu": False,
        "enable_internet": False,
        "dataset_sources": [],
        "competition_sources": [COMPETITION],
        "kernel_sources": [],
        "model_sources": [],
    }
    audit = {
        "format": "arc2-kaggle-kernel-build-v1",
        "source_commit": source_commit,
        "hds_submodule_commit": submodule_commit,
        "kernel": kernel,
        "competition": COMPETITION,
        "internet": False,
        "source_files": len(manifest),
        "source_bytes": sum(int(row["size"]) for row in manifest),
        "payload_bytes": len(payload),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "launcher_bytes": len(launcher),
        "launcher_sha256": hashlib.sha256(launcher).hexdigest(),
        "notebook_bytes": len(notebook),
        "notebook_sha256": hashlib.sha256(notebook).hexdigest(),
        "files": manifest,
    }

    output.mkdir(parents=True)
    (output / "bundle.zip").write_bytes(payload)
    (output / "solve.py").write_bytes(launcher)
    (output / "main.ipynb").write_bytes(notebook)
    (output / "kernel-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "build-manifest.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {key: value for key, value in audit.items() if key != "files"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("出力/Kaggle/arc2-codex-main-baseline-v1"),
    )
    parser.add_argument("--stage-upload", type=Path, help="既存buildからNotebookのみを送信フォルダへ切り出す")
    parser.add_argument("--kernel", default=KERNEL)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    if args.stage_upload:
        result = stage_upload(args.stage_upload, args.output)
    else:
        result = build(args.output, allow_dirty=args.allow_dirty, kernel=args.kernel)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
