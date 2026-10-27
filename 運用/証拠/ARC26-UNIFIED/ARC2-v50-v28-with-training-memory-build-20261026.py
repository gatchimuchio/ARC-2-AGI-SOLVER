"""Build a local-only v28 solver overlay that restores training-only prior memory."""
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
PARENT = BUILDS / "v28-vote-ratio-second-20261026"
MEMORY_SOURCE = BUILDS / "v14-v5-current-20261026"
OUTPUT = BUILDS / "v50-v28-with-training-memory-20261026"
MANIFEST_NAME = "__arc2_bundle_manifest__.json"
HDS_PATH = "接続/ARC2/HDS接続.py"
ADAPTER_PATH = "接続/ARC2/Kaggle提出.py"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def archive_files(bundle: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        if not names or names[0] != MANIFEST_NAME:
            raise ValueError("parent bundle manifest is missing")
        manifest = json.loads(archive.read(MANIFEST_NAME))
        expected = {row["path"] for row in manifest["files"]}
        if set(names[1:]) != expected:
            raise ValueError("parent bundle file set differs from its manifest")
        return {name: archive.read(name) for name in names[1:]}


def method_map(source: str, class_name: str) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(source)
    cls = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return {
        node.name: node for node in cls.body
        if isinstance(node, ast.FunctionDef)
    }


def restore_neighbor_distance_methods(v14_source: str, v28_source: str) -> str:
    old_methods = method_map(v14_source, "FeatureNeighborTransform")
    current_methods = method_map(v28_source, "FeatureNeighborTransform")
    missing = [name for name in old_methods if name not in current_methods]
    if missing != ["最近距離", "最近距離特徴量"]:
        raise ValueError(f"unexpected feature-neighbor API difference: {missing}")

    old_lines = v14_source.splitlines(keepends=True)
    methods = []
    for name in missing:
        node = old_methods[name]
        methods.extend(old_lines[node.lineno - 1:node.end_lineno])
    current_lines = v28_source.splitlines(keepends=True)
    insert_at = current_methods["記録"].lineno - 1
    current_lines[insert_at:insert_at] = methods + ["\n"]
    result = "".join(current_lines)
    ast.parse(result)
    return result


def patch_adapter(v28_source: str) -> str:
    source_bytes = v28_source.encode("utf-8")
    lines = v28_source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line.encode("utf-8")))
    tree = ast.parse(v28_source)
    worker = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_worker"
    )
    preflight = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_preflight"
    )
    changes: list[tuple[int, int, bytes]] = []

    imports = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and "HDS" in node.module
    ]
    if len(imports) != 2:
        raise ValueError(f"expected worker and preflight HDS imports, got {len(imports)}")
    for node in imports:
        names = [alias.name for alias in node.names]
        if "汎用事前記憶を読む" not in names:
            names.append("汎用事前記憶を読む")
        line_start = offsets[node.lineno - 1]
        line_end = offsets[node.end_lineno]
        original_line = lines[node.lineno - 1]
        indent = original_line[:len(original_line) - len(original_line.lstrip())]
        newline = b"\r\n" if original_line.endswith("\r\n") else b"\n"
        replacement = (
            indent.encode("utf-8")
            + f"from {node.module} import {', '.join(names)}".encode("utf-8")
            + newline
        )
        changes.append((line_start, line_end, replacement))

    memory_assignments = []
    preflight_validations = []
    hds_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Name) and func.id == "事前教材を読む":
                if worker.lineno < node.lineno < worker.end_lineno:
                    memory_assignments.append(node)
                elif preflight.lineno < node.lineno < preflight.end_lineno:
                    preflight_validations.append(node)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "課題を解く"
            and worker.lineno < node.lineno < worker.end_lineno
        ):
            hds_calls.append(node)

    if len(memory_assignments) != 1 or len(preflight_validations) != 1 or len(hds_calls) != 2:
        raise ValueError(
            "unexpected adapter shape: "
            f"memory assignments={len(memory_assignments)}, "
            f"preflight validations={len(preflight_validations)}, HDS calls={len(hds_calls)}"
        )

    assignment = memory_assignments[0]
    assignment_line = lines[assignment.lineno - 1]
    indent = assignment_line[:len(assignment_line) - len(assignment_line.lstrip())]
    memory_line = indent + "汎用記憶 = 汎用事前記憶を読む()\n"
    changes.append((offsets[assignment.end_lineno], offsets[assignment.end_lineno], memory_line.encode("utf-8")))

    validation = preflight_validations[0]
    validation_line = lines[validation.lineno - 1]
    indent = validation_line[:len(validation_line) - len(validation_line.lstrip())]
    validation_text = indent + "汎用事前記憶を読む()\n"
    changes.append((offsets[validation.end_lineno], offsets[validation.end_lineno], validation_text.encode("utf-8")))

    for call in hds_calls:
        if any(keyword.arg == "汎用事前教材" for keyword in call.keywords):
            raise ValueError("parent adapter unexpectedly already uses generic prior memory")
        close = offsets[call.end_lineno - 1] + call.end_col_offset - 1
        if source_bytes[close:close + 1] != b")":
            raise ValueError("could not locate an HDS call's closing parenthesis")
        changes.append((close, close, ", 汎用事前教材=汎用記憶".encode("utf-8")))

    for start, end, replacement in sorted(changes, key=lambda row: row[0], reverse=True):
        source_bytes = source_bytes[:start] + replacement + source_bytes[end:]
    result = source_bytes.decode("utf-8")
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
    parent_files = archive_files(PARENT / "bundle.zip")
    v14_files = archive_files(MEMORY_SOURCE / "bundle.zip")
    feature_path = next(
        name for name in parent_files
        if "近傍" in name and "変換選択" in name
    )
    memory_path = next(
        name for name in v14_files if name.endswith("事前記憶訓練例.json")
    )
    parent_files[HDS_PATH] = v14_files[HDS_PATH]
    parent_files[feature_path] = restore_neighbor_distance_methods(
        v14_files[feature_path].decode("utf-8"), parent_files[feature_path].decode("utf-8")
    ).encode("utf-8")
    parent_files[ADAPTER_PATH] = patch_adapter(parent_files[ADAPTER_PATH].decode("utf-8")).encode("utf-8")
    parent_files[memory_path] = v14_files[memory_path]

    prior = json.loads(parent_files[memory_path].decode("utf-8"))
    if prior.get("schema") != "arc2-hds-generic-prior-training-v1" or prior.get("source_split") != "training":
        raise ValueError("prior memory is not the declared training-only schema")
    if len(prior.get("examples", [])) != 279 or prior.get("example_count") != 279:
        raise ValueError("unexpected generic prior memory example count")

    payload, rows = make_payload(parent_files)
    candidate_commit = parent_manifest["source_commit"] + "+v50-local-prior-memory"
    builder_path = ROOT / "道具/ARC2Kaggle提出bundle.py"
    spec = importlib.util.spec_from_file_location("arc2_local_bundle_builder", builder_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the project bundle renderer")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    launcher = builder._render_launcher(payload, candidate_commit)
    notebook = builder._render_notebook(launcher, sha(payload))
    metadata = json.loads((PARENT / "kernel-metadata.json").read_text(encoding="utf-8"))
    metadata["title"] = "ARC2 v50 local v28 plus training prior memory"

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
        "local_candidate_overlay": {
            "description": "v28 solver families with v14 training-only generic prior integration",
            "files": {
                HDS_PATH: sha(parent_files[HDS_PATH]),
                ADAPTER_PATH: sha(parent_files[ADAPTER_PATH]),
                feature_path: sha(parent_files[feature_path]),
                memory_path: sha(parent_files[memory_path]),
            },
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
