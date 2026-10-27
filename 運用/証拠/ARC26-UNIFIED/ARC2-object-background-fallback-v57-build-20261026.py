"""Build v57 from v51 with a training-guided fallback when primary object families lack consensus."""
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
PARENT = BUILDS / "v51-largest-component-background-20261026"
PROBE = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-object-background-fallback-v57-probe-20261026.py"
OUTPUT = BUILDS / "v57-object-background-training-fallback-20261026"
MANIFEST_NAME = "__arc2_bundle_manifest__.json"
OBJECT_PATH = "接続/ARC2/物体抽出候補.py"
ADAPTER_PATH = "接続/ARC2/Kaggle提出.py"


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


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    node = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    return "".join(source.splitlines(keepends=True)[node.lineno - 1:node.end_lineno])


def patch_object_module(parent_source: str, probe_source: str) -> str:
    _function_source(parent_source, "_background")
    helper_source = "\n" + _function_source(probe_source, "_mode_background") + "\n" + _function_source(
        probe_source, "_training_guided_background"
    ) + "\n"
    tree = ast.parse(parent_source)
    background = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_background"
    )
    lines = parent_source.splitlines(keepends=True)
    lines.insert(background.end_lineno, helper_source)
    source = "".join(lines)
    tree = ast.parse(source)
    cls = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ObjectExtractionCandidate"
    )
    candidate_method = next(
        node for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == "candidate"
    )
    fallback_method = '''    def training_guided_fallback_candidate(self, test_input: Grid) -> tuple[Grid | None, dict[str, int]]:
        """Return a unique two-family consensus under training-guided background."""
        global _background
        original_background = _background
        _background = _training_guided_background(self.teachers)
        try:
            model = ObjectExtractionCandidate(self.teachers)
            outputs: list[GridKey] = []
            for method in (model.candidate, model.outlier_candidate, model.palette_candidate):
                prediction, _ = method(test_input)
                if _valid_grid(prediction) and prediction != test_input:
                    outputs.append(_grid_key(prediction))
        finally:
            _background = original_background
        votes = Counter(outputs)
        if not votes:
            return None, {"top_votes": 0, "applicable_models": 3}
        top_votes = max(votes.values())
        winners = [key for key, count in votes.items() if count == top_votes]
        if top_votes < 2 or len(winners) != 1:
            return None, {"top_votes": top_votes, "applicable_models": 3}
        return [list(row) for row in winners[0]], {"top_votes": top_votes, "applicable_models": 3}

'''
    lines = source.splitlines(keepends=True)
    lines.insert(candidate_method.lineno - 1, fallback_method)
    result = "".join(lines)
    ast.parse(result)
    return result


def patch_adapter(parent_source: str) -> str:
    marker = "                if 物体枠未充足 and 物体候補群:\n                    選択種別, 第二候補, _ = max(\n"
    if parent_source.count(marker) != 1:
        raise ValueError("could not locate object candidate selection point")
    fallback = '''                if 物体枠未充足:
                    _primary_object_votes = Counter(
                        tuple(tuple(row) for row in candidate)
                        for _, candidate, _ in 物体候補群
                    )
                    if max(_primary_object_votes.values(), default=0) < 2:
                        _training_candidate, _training_record = 物体抽出候補器.training_guided_fallback_candidate(
                            課題["test"][位置]["input"]
                        )
                        if 格子か(_training_candidate) and _training_candidate != 第一候補:
                            物体候補群.append(("training_fallback", _training_candidate, _training_record))
'''
    result = parent_source.replace(marker, fallback + marker, 1)
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
    original_adapter_sha = sha(files[ADAPTER_PATH])
    probe_source = PROBE.read_text(encoding="utf-8")
    files[OBJECT_PATH] = patch_object_module(files[OBJECT_PATH].decode("utf-8"), probe_source).encode("utf-8")
    files[ADAPTER_PATH] = patch_adapter(files[ADAPTER_PATH].decode("utf-8")).encode("utf-8")
    payload, rows = make_payload(files)
    candidate_commit = parent_manifest["source_commit"] + "+v57-training-guided-object-fallback"

    builder_path = ROOT / "道具/ARC2Kaggle提出bundle.py"
    spec = importlib.util.spec_from_file_location("arc2_local_bundle_builder", builder_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the project bundle renderer")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    launcher = builder._render_launcher(payload, candidate_commit)
    notebook = builder._render_notebook(launcher, sha(payload))
    metadata = json.loads((PARENT / "kernel-metadata.json").read_text(encoding="utf-8"))
    metadata["title"] = "ARC2 v57 local object-background fallback candidate"

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
            "description": "largest-component primary; training-guided removed-color fallback when primary object methods lack a two-family consensus",
            "object_module_parent_sha256": original_object_sha,
            "object_module_candidate_sha256": sha(files[OBJECT_PATH]),
            "adapter_parent_sha256": original_adapter_sha,
            "adapter_candidate_sha256": sha(files[ADAPTER_PATH]),
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
