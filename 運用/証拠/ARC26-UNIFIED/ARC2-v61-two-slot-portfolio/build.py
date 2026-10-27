"""Build a local experimental payload from frozen v61; never run a solver or Kaggle."""
from __future__ import annotations

import ast
import base64
from datetime import datetime, timezone
import difflib
import hashlib
import io
import json
from pathlib import Path
import zipfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FROZEN = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v61-kaggle-staging-20261026"
MEMBER = "接続/ARC2/Kaggle提出.py"
MANIFEST_MEMBER = "__arc2_bundle_manifest__.json"
EXPECTED = {
    "bundle.zip": "06f7e19da4f1b6fc0059a4aef03833fd9074bc725204a3f9c5c1b33523e0fbee",
    "solve.py": "d47dac81dbcb9cd9a151fa7461145b5ac708291dbb52af8a4099e20efbc4a791",
    MEMBER: "c20102c4e9a01e833ca8f9e2778b5306333c50c065d9aebe7cbeaf574e74418d",
    "接続/ARC2/HDS接続.py": "8cc1456edfab1b84478fcc1b8f82973481709d85a45532b5181d0e79655362a3",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError("patch context is not unique: " + old[:100])
    return text.replace(old, new, 1)


def replace_function(source: str, name: str, replacement: str) -> str:
    nodes = [n for n in ast.parse(source).body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise ValueError("function is not unique: " + name)
    node = nodes[0]
    lines = source.splitlines(keepends=True)
    return "".join(lines[:node.lineno - 1]) + replacement.rstrip() + "\n" + "".join(lines[node.end_lineno:])


def render_launcher(source: str, payload: bytes) -> str:
    assignments = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ("PAYLOAD_B64", "PAYLOAD_SHA256", "SOURCE_COMMIT"):
                assignments[node.targets[0].id] = node
    if set(assignments) != {"PAYLOAD_B64", "PAYLOAD_SHA256", "SOURCE_COMMIT"}:
        raise ValueError("frozen launcher assignments missing")
    old_commit = ast.literal_eval(assignments["SOURCE_COMMIT"].value)
    encoded = base64.b64encode(payload).decode("ascii")
    new_values = {
        "SOURCE_COMMIT": "SOURCE_COMMIT = " + repr(old_commit + "+experimental-two-slot-portfolio-v1") + "\n",
        "PAYLOAD_SHA256": "PAYLOAD_SHA256 = " + repr(sha(payload)) + "\n",
        "PAYLOAD_B64": "PAYLOAD_B64 = (\n" + "".join("    " + repr(encoded[i:i + 100]) + "\n" for i in range(0, len(encoded), 100)) + ")\n",
    }
    lines = source.splitlines(keepends=True)
    for name, node in sorted(assignments.items(), key=lambda item: item[1].lineno, reverse=True):
        lines[node.lineno - 1:node.end_lineno] = [new_values[name]]
    result = "".join(lines)
    compile(result, "candidate/solve.py", "exec")
    return result


def normalized_launcher(source: str) -> str:
    result = source
    node = next(n for n in ast.parse(result).body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PAYLOAD_B64" for t in n.targets))
    lines = result.splitlines(keepends=True)
    lines[node.lineno - 1:node.end_lineno] = ["PAYLOAD_B64 = '<omitted; see payload SHA256>'\n"]
    return "".join(lines)


def main() -> None:
    if (HERE / "build-manifest.json").exists() or (HERE / "candidate").exists():
        raise FileExistsError("refuse to overwrite an experimental build")
    protected_paths = (ROOT / "AGENTS.md", ROOT / "制御/現在状態.json", ROOT / "接続/ARC2/HDS接続.py", ROOT / "接続/ARC2/Kaggle提出.py")
    protected_before = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in protected_paths}
    frozen_payload = (FROZEN / "bundle.zip").read_bytes()
    frozen_launcher = (FROZEN / "solve.py").read_bytes()
    if sha(frozen_payload) != EXPECTED["bundle.zip"] or sha(frozen_launcher) != EXPECTED["solve.py"]:
        raise ValueError("frozen v61 parent hash mismatch")
    with zipfile.ZipFile(io.BytesIO(frozen_payload)) as archive:
        manifest = json.loads(archive.read(MANIFEST_MEMBER))
        files = {row["path"]: archive.read(row["path"]) for row in manifest["files"]}
    for row in manifest["files"]:
        if len(files[row["path"]]) != row["size"] or sha(files[row["path"]]) != row["sha256"]:
            raise ValueError("frozen member manifest mismatch")
    for path in (MEMBER, "接続/ARC2/HDS接続.py"):
        if sha(files[path]) != EXPECTED[path]:
            raise ValueError("frozen source mismatch: " + path)

    original = files[MEMBER].decode("utf-8")
    helpers = (HERE / "portfolio_helpers.py").read_text(encoding="utf-8")
    formatter = (HERE / "formatter_overlay.py").read_text(encoding="utf-8")
    fragment = (HERE / "worker_fragment.pyfrag").read_text(encoding="utf-8")
    patched = replace_function(original, "結果を候補へ", formatter)
    patched = replace_once(patched, "def _worker(", helpers.rstrip() + "\n\n\ndef _worker(")
    patched = replace_once(patched, "            公開行群.append(\n", fragment.rstrip() + "\n            公開行群.append(\n")
    row_context = '                    "second_answer": 第二候補 if 位置 < len(課題["test"]) else None,\n'
    patched = replace_once(patched, row_context, row_context + '                    "hds_primary_hold": hds一次保留,\n                    "portfolio_attempt1": portfolio候補,\n                    "portfolio_diagnostics": portfolio診断,\n')
    audit_context = '        "fallback_count": len(保留群),\n'
    patched = replace_once(patched, audit_context, audit_context + '        "fallback_count_semantics": "legacy_primary_hold_or_worker_error_provenance",\n        "true_input_copy_fallback_count": sum(bool(row.get("true_input_copy_fallback")) for row in 保留群),\n        "portfolio_diagnostics": _portfolio_audit_summary(保留群),\n')
    compile(patched, MEMBER, "exec")
    compile(helpers, "portfolio_helpers.py", "exec")
    compile(formatter, "formatter_overlay.py", "exec")
    files[MEMBER] = patched.encode("utf-8")
    changed_members = [row["path"] for row in manifest["files"] if sha(files[row["path"]]) != row["sha256"]]
    if changed_members != [MEMBER]:
        raise ValueError("unexpected changed payload member set: " + repr(changed_members))
    rows = [{"path": path, "size": len(content), "sha256": sha(content)} for path, content in sorted(files.items())]
    new_manifest = {"format": manifest["format"], "files": rows}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, content in [(MANIFEST_MEMBER, (json.dumps(new_manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")), *sorted(files.items())]:
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    payload = buffer.getvalue()
    launcher = render_launcher(frozen_launcher.decode("utf-8"), payload)

    for folder in (HERE / "candidate/接続/ARC2", HERE / "frozen", HERE / "diffs"):
        folder.mkdir(parents=True, exist_ok=False)
    (HERE / "candidate/bundle.zip").write_bytes(payload)
    (HERE / "candidate/solve.py").write_text(launcher, encoding="utf-8", newline="\n")
    (HERE / "candidate" / MEMBER).write_bytes(files[MEMBER])
    (HERE / "frozen/Kaggle提出.py").write_text(original, encoding="utf-8", newline="\n")
    (HERE / "diffs/Kaggle提出.py.diff").write_text("".join(difflib.unified_diff(original.splitlines(keepends=True), patched.splitlines(keepends=True), fromfile="frozen-v61/接続/ARC2/Kaggle提出.py", tofile="portfolio/接続/ARC2/Kaggle提出.py")), encoding="utf-8", newline="\n")
    (HERE / "diffs/solve.py.normalized.diff").write_text("".join(difflib.unified_diff(normalized_launcher(frozen_launcher.decode("utf-8")).splitlines(keepends=True), normalized_launcher(launcher).splitlines(keepends=True), fromfile="frozen-v61/solve.py (base64 omitted)", tofile="portfolio/solve.py (base64 omitted)")), encoding="utf-8", newline="\n")
    protected_after = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in protected_paths}
    if protected_before != protected_after:
        raise ValueError("protected or active source changed during build")
    built_at = datetime.now(timezone.utc).isoformat()
    report = {
        "schema": "arc2-v61-two-slot-portfolio-build-v1",
        "built_at_utc": built_at,
        "scope": "local experimental artifact only; no solver, LOO, Kaggle, or official candidate mutation",
        "parent_directory": str(FROZEN.relative_to(ROOT)),
        "parent_sha256": EXPECTED,
        "changed_payload_members": changed_members,
        "unchanged_payload_member_count": len(files) - 1,
        "candidate_payload_sha256": sha(payload),
        "candidate_wrapper_sha256": sha(files[MEMBER]),
        "candidate_launcher_sha256": sha(launcher.encode("utf-8")),
        "builder_sha256": sha(Path(__file__).read_bytes()),
        "overlay_sha256": {name: sha((HERE / name).read_bytes()) for name in ("portfolio_helpers.py", "formatter_overlay.py", "worker_fragment.pyfrag", "protocol.md")},
        "protected_and_active_source_hashes_unchanged": protected_after,
        "policy_id": "arc2-v61-hold-two-slot-portfolio-v1",
        "priority": ["teacher_pair_consensus", "object_extraction", "object_outlier", "object_palette", "local_cell_context", "simple_unique_transform", "composite_geometry"],
        "syntax_compile": {"wrapper": True, "launcher": True, "helpers": True, "formatter": True},
        "solver_runs": 0,
        "evaluation_targets_read": False,
        "performance_improvement": "UNMEASURED",
    }
    (HERE / "build-manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
