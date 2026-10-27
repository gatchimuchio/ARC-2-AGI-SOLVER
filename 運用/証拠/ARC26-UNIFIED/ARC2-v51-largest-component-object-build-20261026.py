"""Build a local v50 bundle with a largest-connected-component background rule."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[3]
BUILDS = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1"
PARENT = BUILDS / "v50-v28-with-training-memory-20261026"
PROBE = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-largest-component-object-v51-probe-20261026.py"
OUTPUT = BUILDS / "v51-largest-component-background-20261026"
MANIFEST_NAME = "__arc2_bundle_manifest__.json"
OBJECT_PATH = "接続/ARC2/物体抽出候補.py"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_files(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if not names or names[0] != MANIFEST_NAME:
            raise ValueError("parent bundle manifest is missing")
        manifest = json.loads(archive.read(MANIFEST_NAME))
        expected = {row["path"] for row in manifest["files"]}
        if set(names[1:]) != expected:
            raise ValueError("parent bundle file set differs from its manifest")
        return {name: archive.read(name) for name in names[1:]}


def replace_background(parent_source: str, probe_source: str) -> str:
    parent_tree = ast.parse(parent_source)
    probe_tree = ast.parse(probe_source)
    current = next(
        node for node in parent_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_background"
    )
    candidate = next(
        node for node in probe_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_largest_component_background"
    )
    parent_lines = parent_source.splitlines(keepends=True)
    probe_lines = probe_source.splitlines(keepends=True)
    replacement = "".join(probe_lines[candidate.lineno - 1:candidate.end_lineno])
    replacement = replacement.replace(
        "def _largest_component_background(grid):",
        "def _background(grid: Grid) -> int:",
        1,
    )
    parent_lines[current.lineno - 1:current.end_lineno] = [replacement]
    result = "".join(parent_lines)
    ast.parse(result)
    return result


def make_payload(files: dict[str, bytes]) -> tuple[bytes, list[dict[str, object]]]:
    rows = [
        {"path": name, "size": len(data), "sha256": sha(data)}
        for name, data in sorted(files.items())
    ]
    manifest_bytes = json.dumps(
        {"format": "arc2-hds-kernel-bundle-v1", "files": rows},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in [(MANIFEST_NAME, manifest_bytes), *sorted(files.items())]:
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return output.getvalue(), rows


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    parent_manifest = json.loads((PARENT / "build-manifest.json").read_text(encoding="utf-8"))
    files = read_files(PARENT / "bundle.zip")
    original_object_sha = sha(files[OBJECT_PATH])
    files[OBJECT_PATH] = replace_background(
        files[OBJECT_PATH].decode("utf-8"), PROBE.read_text(encoding="utf-8")
    ).encode("utf-8")
    payload, rows = make_payload(files)
    candidate_commit = parent_manifest["source_commit"] + "+v51-largest-component-object"

    builder_path = ROOT / "道具/ARC2Kaggle提出bundle.py"
    spec = importlib.util.spec_from_file_location("arc2_local_bundle_builder", builder_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the project bundle renderer")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    launcher = builder._render_launcher(payload, candidate_commit)
    notebook = builder._render_notebook(launcher, sha(payload))
    metadata = json.loads((PARENT / "kernel-metadata.json").read_text(encoding="utf-8"))
    metadata["title"] = "ARC2 v51 local largest-component object candidate"

    manifest = dict(parent_manifest)
    manifest.update({
        "source_commit": candidate_commit,
        "source_files": len(rows),
        "source_bytes": sum(int(row["size"]) for row in rows),
        "payload_bytes": len(payload),
        "payload_sha256": sha(payload),
        "launcher_bytes": len(launcher),
        "launcher_sha256": sha(launcher),
        "notebook_bytes": len(notebook),
        "notebook_sha256": sha(notebook),
        "files": rows,
        "local_candidate_parent_build": PARENT.name,
        "local_candidate_parent_payload_sha256": parent_manifest["payload_sha256"],
        "local_candidate_build_script_sha256": sha(Path(__file__).read_bytes()),
        "local_candidate_probe_sha256": sha(PROBE.read_bytes()),
        "local_candidate_overlay": {
            "description": "largest 4-connected component selects object-extraction background",
            "object_module_parent_sha256": original_object_sha,
            "object_module_candidate_sha256": sha(files[OBJECT_PATH]),
            "training_prior_memory_sha256": next(
                row["sha256"] for row in rows if row["path"].endswith("事前記憶訓練例.json")
            ),
        },
    })

    OUTPUT.mkdir(parents=True)
    (OUTPUT / "bundle.zip").write_bytes(payload)
    (OUTPUT / "solve.py").write_bytes(launcher)
    (OUTPUT / "main.ipynb").write_bytes(notebook)
    (OUTPUT / "kernel-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUTPUT / "build-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: manifest[key] for key in (
        "source_commit", "source_files", "payload_bytes", "payload_sha256",
        "notebook_sha256", "local_candidate_parent_build", "local_candidate_overlay",
    )}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
