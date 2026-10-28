"""検証済みの凍結実行器へ二面候補を追加した実験stageを再現する。"""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile

from 道具.ARC2Kaggle提出bundle import TEMPLATE
from 道具.ARC2候補診断準備 import 作成 as 診断stage作成


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "接続/ARC2/二面真理値候補.py"
CANDIDATE_SHA = "819d9459ed6cb1a356532b98658e756038945b80d9996b6f7b51e881372a945f"
ORIGINAL_PAYLOAD_SHA = "06f7e19da4f1b6fc0059a4aef03833fd9074bc725204a3f9c5c1b33523e0fbee"


def _replace_definition(source: str, name: str, replacement: str) -> str:
    tree = ast.parse(source)
    nodes = [node for node in tree.body if (
        isinstance(node, ast.FunctionDef) and node.name == name or
        isinstance(node, ast.Assign) and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name)]
    if len(nodes) != 1:
        raise ValueError(f"対象定義が一意ではありません: {name}")
    node = nodes[0]
    lines = source.splitlines(keepends=True)
    return "".join(lines[:node.lineno - 1]) + replacement.rstrip("\n") + "\n" + "".join(lines[node.end_lineno:])


def _安全payload(source: str) -> tuple[str, dict]:
    tree = ast.parse(source)
    values = {node.targets[0].id: ast.literal_eval(node.value)
              for node in tree.body if isinstance(node, ast.Assign) and len(node.targets) == 1
              and isinstance(node.targets[0], ast.Name)
              and node.targets[0].id in ("PAYLOAD_B64", "PAYLOAD_SHA256")}
    raw = base64.b64decode(values["PAYLOAD_B64"], validate=True)
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_PAYLOAD_SHA or values["PAYLOAD_SHA256"] != ORIGINAL_PAYLOAD_SHA:
        raise ValueError("元payloadのhashが固定値と一致しません")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        manifest = json.loads(archive.read("__arc2_bundle_manifest__.json"))
        rows = manifest["files"]
        if len({row["path"] for row in rows}) != len(rows) or set(archive.namelist()) != {"__arc2_bundle_manifest__.json", *(row["path"] for row in rows)}:
            raise ValueError("元payloadのファイル集合が不正です")
        contents = {}
        for row in rows:
            data = archive.read(row["path"])
            if len(data) != row["size"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise ValueError("元payloadのメンバーhash不一致")
            contents[row["path"]] = data
    teachers = [name for name in contents if name.startswith("入力/公式ソース/ARC-AGI-2/data/training/") and name.endswith(".json")]
    if len(teachers) != 1:
        raise ValueError("固定教材の数が想定と一致しません")
    teacher = json.loads(contents[teachers[0]])
    if len(teacher.get("train", [])) != 2 or not any("output" in row for row in teacher.get("test", [])):
        raise ValueError("固定教材の内容が想定と一致しません")
    train_only = json.dumps({"train": teacher["train"]}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    contents[teachers[0]] = train_only
    updated = [{"path": row["path"], "size": len(contents[row["path"]]),
                "sha256": hashlib.sha256(contents[row["path"]]).hexdigest()} for row in rows]
    manifest_bytes = json.dumps({"format": "arc2-hds-kernel-bundle-v1", "files": updated},
                                ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in [("__arc2_bundle_manifest__.json", manifest_bytes), *sorted(contents.items())]:
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    data = output.getvalue()
    payload_sha = hashlib.sha256(data).hexdigest()
    encoded = base64.b64encode(data).decode("ascii")
    chunks = "\n".join(f'    "{encoded[i:i + 100]}"' for i in range(0, len(encoded), 100))
    source = _replace_definition(source, "PAYLOAD_B64", "PAYLOAD_B64 = (\n" + chunks + "\n)")
    source = _replace_definition(source, "PAYLOAD_SHA256", "PAYLOAD_SHA256 = " + repr(payload_sha))
    template_tree = ast.parse(TEMPLATE)
    function = next(node for node in template_tree.body if isinstance(node, ast.FunctionDef) and node.name == "payload_root")
    template_lines = TEMPLATE.splitlines(keepends=True)
    guard = "".join(template_lines[function.lineno - 1:function.end_lineno])
    source = _replace_definition(source, "payload_root", guard)
    marker = 'def main():\n    import importlib.util\n'
    if source.count(marker) != 1:
        raise ValueError("launcher main挿入箇所が一意ではありません")
    source = source.replace(marker, 'def main():\n    sys.dont_write_bytecode = True\n    import importlib.util\n', 1)
    compile(source, "solve.py", "exec")
    return source, {"original_payload_sha256": ORIGINAL_PAYLOAD_SHA, "payload_sha256": payload_sha,
                    "teacher_train_only_sha256": hashlib.sha256(train_only).hexdigest(),
                    "teacher_training_pairs": len(teacher["train"]), "teacher_test_removed": True,
                    "cache_member_revalidation": True}


def 作成(destination: Path, *, 安全化: bool = False):
    source = CANDIDATE.read_bytes()
    if hashlib.sha256(source).hexdigest() != CANDIDATE_SHA:
        raise ValueError("評価済み候補のhashと一致しません")
    manifest = 診断stage作成(destination)
    adapter = destination / "Kaggle提出.py"
    text = adapter.read_text(encoding="utf-8")
    anchor = '        from 接続.ARC2.単純変換候補 import unique_candidate\n'
    if text.count(anchor) != 1:
        raise ValueError("候補import箇所が一意ではありません")
    text = text.replace(anchor, anchor + '        from two_panel import candidate as two_panel_candidate\n', 1)
    anchor = '            公開行群.append(\n'
    if text.count(anchor) != 1:
        raise ValueError("候補採用箇所が一意ではありません")
    insertion = (
        '            if 位置 < len(課題["test"]) and (not 格子か(第二候補) or 第二候補 == 第一候補):\n'
        '                二面候補 = two_panel_candidate(課題["train"], 課題["test"][位置]["input"])\n'
        '                if 格子か(二面候補) and 二面候補 != 第一候補:\n'
        '                    第二候補 = 二面候補\n'
    )
    text = text.replace(anchor, insertion + anchor, 1)
    compile(text, str(adapter), "exec")
    adapter.write_text(text, encoding="utf-8", newline="\n")
    with (destination / "two_panel.py").open("xb") as file:
        file.write(source)
    manifest["diagnostic_sha256"]["Kaggle提出.py"] = hashlib.sha256(adapter.read_bytes()).hexdigest()
    manifest["candidate_sha256"] = CANDIDATE_SHA
    manifest["integration"] = "Use only as a distinct second attempt when no valid distinct second candidate already exists; leave first attempt and HDS acceptance unchanged."
    if 安全化:
        launcher = destination / "solve.py"
        updated, security = _安全payload(launcher.read_text(encoding="utf-8"))
        launcher.write_text(updated, encoding="utf-8", newline="\n")
        manifest["diagnostic_sha256"]["solve.py"] = hashlib.sha256(launcher.read_bytes()).hexdigest()
        manifest["security"] = security
    (destination / "diagnostic-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hardened", action="store_true", help="固定教材をtrain-only化し、payloadキャッシュを再検証する")
    args = parser.parse_args()
    print(json.dumps(作成(args.output, 安全化=args.hardened), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
