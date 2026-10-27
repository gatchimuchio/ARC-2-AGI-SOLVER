from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import zipfile


REPOSITORY = Path(__file__).resolve().parents[3]
SOURCE_ROOT = REPOSITORY / "運用/証拠/ARC26-UNIFIED/ARC2-v61-global-deadline-isolated"
BUILD_ROOT = REPOSITORY / "出力/Kaggle/arc2-v61-global-deadline-review-20261027-build"
KERNEL_ID = "tecchannn/arc2-v61-global-deadline-review-20261027"
COMPETITION = "arc-prize-2026-arc-agi-2"
MEMBERS = {
    "Kaggle提出.py": "dc90314d9fa18626c67b02177ddac9fd9ec2d1ef89bc3b5f76ae013861a15213",
    "deadline_control.py": "fd20d8b0609882b83217a7356a6175cd549c63a4c13ba7b9b852bc27a0a39f27",
    "outer_watchdog.py": "a26b1711cc77ad9797dcded9ad63427ea656ca27193fe7c5c2f24a1585473347",
    "solve.py": "740ebb543f6fbed996b12fff96cbb3b2892c964ece66d692e29445450ecac7af",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def notebook_source(bundle_b64: str, bundle_sha256: str) -> str:
    chunks = [bundle_b64[i : i + 100] for i in range(0, len(bundle_b64), 100)]
    chunk_lines = ",\n".join(f'    "{chunk}"' for chunk in chunks)
    members_json = json.dumps(MEMBERS, sort_keys=True)
    return f'''# Isolated ARC2 v61 deadline review; no official submission is made here.
import base64, hashlib, io, json, os, sys, zipfile
from pathlib import Path, PurePosixPath

BUNDLE_SHA256 = "{bundle_sha256}"
EXPECTED_MEMBERS = json.loads({members_json!r})
BUNDLE_PARTS = [
{chunk_lines}
]
bundle = base64.b64decode("".join(BUNDLE_PARTS), validate=True)
if hashlib.sha256(bundle).hexdigest() != BUNDLE_SHA256:
    raise RuntimeError("embedded runtime bundle hash mismatch")

variant_root = Path("/kaggle/working/arc2_deadline_variant")
variant_root.mkdir(parents=True, exist_ok=False)
with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
    if sorted(archive.namelist()) != sorted(EXPECTED_MEMBERS):
        raise RuntimeError("unexpected runtime bundle members")
    for name in archive.namelist():
        path = PurePosixPath(name)
        if path.is_absolute() or len(path.parts) != 1 or path.name in ("", ".", ".."):
            raise RuntimeError("unsafe runtime bundle member")
        data = archive.read(name)
        if hashlib.sha256(data).hexdigest() != EXPECTED_MEMBERS[name]:
            raise RuntimeError("runtime member hash mismatch: " + name)
        (variant_root / name).write_bytes(data)

sys.path.insert(0, str(variant_root))
from outer_watchdog import main
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
main(["--runner", str(variant_root / "solve.py"), "--output-dir", "/kaggle/working"])
'''


def main() -> None:
    if BUILD_ROOT.exists():
        raise FileExistsError(f"refusing to overwrite {BUILD_ROOT}")
    member_bytes: dict[str, bytes] = {}
    for name, expected in MEMBERS.items():
        source = SOURCE_ROOT / name
        data = source.read_bytes()
        actual = sha256(data)
        if actual != expected:
            raise ValueError(f"frozen source hash mismatch for {name}: {actual}")
        member_bytes[name] = data

    BUILD_ROOT.mkdir(parents=True)
    bundle_path = BUILD_ROOT / "runtime_bundle.zip"
    with zipfile.ZipFile(bundle_path, "w") as archive:
        for name in sorted(member_bytes):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, member_bytes[name])
    bundle = bundle_path.read_bytes()
    bundle_hash = sha256(bundle)
    b64 = base64.b64encode(bundle).decode("ascii")
    source = notebook_source(b64, bundle_hash)
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": source.splitlines(keepends=True),
            }
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            }
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    code_path = BUILD_ROOT / "main.ipynb"
    code_path.write_text(
        json.dumps(notebook, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    metadata = {
        "id": KERNEL_ID,
        "title": "ARC2 v61 Global Deadline Review",
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
    metadata_path = BUILD_ROOT / "kernel-metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest = {
        "schema": "arc2-v61-deadline-review-bundle-v1",
        "kernel": KERNEL_ID,
        "private": True,
        "internet": False,
        "competition": COMPETITION,
        "runtime_member_sha256": MEMBERS,
        "runtime_bundle_sha256": bundle_hash,
        "runtime_bundle_bytes": len(bundle),
        "code_sha256": sha256(code_path.read_bytes()),
        "metadata_sha256": sha256(metadata_path.read_bytes()),
        "run_budget_seconds": 42600,
        "kaggle_allowed_runtime_seconds": 43200,
        "official_competition_submission": False,
    }
    manifest_path = BUILD_ROOT / "build-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
