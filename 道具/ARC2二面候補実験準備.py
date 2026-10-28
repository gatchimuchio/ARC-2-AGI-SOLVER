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
CANDIDATE_SHA = "9899c239411e4914a02dbdc1182fe1adcdd1b4215dab2d8b909149d4247bdb25"
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


def 作成(destination: Path, *, 安全化: bool = False, 記憶介入: bool = False):
    source = CANDIDATE.read_bytes()
    if hashlib.sha256(source).hexdigest() != CANDIDATE_SHA:
        raise ValueError("評価済み候補のhashと一致しません")
    manifest = 診断stage作成(destination, 記憶介入=記憶介入)
    adapter = destination / "Kaggle提出.py"
    text = adapter.read_text(encoding="utf-8")
    anchor = '        from 接続.ARC2.単純変換候補 import unique_candidate\n'
    if text.count(anchor) != 1:
        raise ValueError("候補import箇所が一意ではありません")
    text = text.replace(anchor, anchor + '        from two_panel import candidate_details as two_panel_candidate_details\n', 1)
    anchor = '        公開行群 = []\n'
    if text.count(anchor) != 1:
        raise ValueError("候補証跡の初期化箇所が一意ではありません")
    text = text.replace(anchor, anchor + '        二面候補証跡 = []\n', 1)
    anchor = '            公開行群.append(\n'
    if text.count(anchor) != 1:
        raise ValueError("候補採用箇所が一意ではありません")
    insertion = (
        '            if 位置 < len(課題["test"]) and (not 格子か(第二候補) or 第二候補 == 第一候補):\n'
        '                二面候補, 二面証跡 = two_panel_candidate_details(課題["train"], 課題["test"][位置]["input"])\n'
        '                if 格子か(二面候補) and 二面候補 != 第一候補:\n'
        '                    第二候補 = 二面候補\n'
        '                    二面候補証跡.append({"test_index": 位置, **二面証跡})\n'
        '                elif 二面証跡["decision"] == "rejected_loo_conflict":\n'
        '                    二面候補証跡.append({"test_index": 位置, **二面証跡})\n'
    )
    text = text.replace(anchor, insertion + anchor, 1)
    anchor = '        公開結果 = {"results": 公開行群}\n'
    if text.count(anchor) != 1:
        raise ValueError("候補証跡の出力箇所が一意ではありません")
    text = text.replace(anchor, anchor + '        公開結果["candidate_provenance"] = 二面候補証跡\n', 1)
    if 安全化:
        before = '            診断選択前 = deepcopy(行.get("candidate_predictions", []))\n'
        after = '            if 観測診断:\n                診断選択前 = deepcopy(行.get("candidate_predictions", []))\n'
        if text.count(before) != 1:
            raise ValueError("診断前候補の挿入箇所が一意ではありません")
        text = text.replace(before, after, 1)
        before = (
            '            公開行群[-1]["diagnostic_candidates"] = {\n'
            '                "preselection": 診断選択前,\n'
            '                "postselection": deepcopy(行.get("candidate_predictions", [])),\n'
            '                "candidate_attempts": deepcopy(行.get("candidate_attempts")),\n'
            '                "simple_candidate": deepcopy(行.get("simple_transform_candidate")),\n'
            '            }\n'
        )
        after = '            if 観測診断:\n' + ''.join('    ' + line for line in before.splitlines(keepends=True))
        if text.count(before) != 1:
            raise ValueError("診断出力箇所が一意ではありません")
        text = text.replace(before, after, 1)
    compile(text, str(adapter), "exec")
    adapter.write_text(text, encoding="utf-8", newline="\n")
    with (destination / "two_panel.py").open("xb") as file:
        file.write(source)
    controller = destination / "deadline_control.py"
    control_text = controller.read_text(encoding="utf-8")
    anchor = '    diagnostics = result.get("aggregate_diagnostics", {}) if aggregate_diagnostics and isinstance(result, dict) else {}\n'
    if control_text.count(anchor) != 1:
        raise ValueError("候補証跡の受信箇所が一意ではありません")
    provenance = (
        '    diagnostics = dict(diagnostics) if isinstance(diagnostics, dict) else {}\n'
        '    decisions = result.get("candidate_provenance", []) if isinstance(result, dict) else []\n'
        '    fields = {"test_index", "source", "decision", "loo_total", "loo_correct", "loo_conflicts", "loo_unavailable"}\n'
        '    if not isinstance(decisions, list):\n'
        '        raise ValueError("invalid candidate provenance")\n'
        '    for decision in decisions:\n'
        '        if (not isinstance(decision, dict) or set(decision) != fields\n'
        '                or type(decision["test_index"]) is not int or not 0 <= decision["test_index"] < len(task["test"])\n'
        '                or decision["source"] != "two_panel_occupancy_truth_table"\n'
        '                or decision["decision"] not in ("provisional_external_candidate", "rejected_loo_conflict")\n'
        '                or any(type(decision[k]) is not int or decision[k] < 0 for k in ("loo_total", "loo_correct", "loo_conflicts", "loo_unavailable"))\n'
        '                or decision["loo_correct"] + decision["loo_conflicts"] + decision["loo_unavailable"] != decision["loo_total"]\n'
        '                or (decision["decision"] == "provisional_external_candidate" and decision["loo_conflicts"] != 0)\n'
        '                or (decision["decision"] == "rejected_loo_conflict" and decision["loo_conflicts"] == 0)):\n'
        '            raise ValueError("invalid candidate provenance entry")\n'
        '    diagnostics["candidate_provenance"] = decisions\n'
    )
    control_text = control_text.replace(anchor, anchor + provenance, 1)
    anchor = '        if args.aggregate_diagnostics:\n            scalar, families, distinct, requests = Counter(), Counter(), Counter(), Counter()\n'
    if control_text.count(anchor) != 1:
        raise ValueError("候補証跡の監査箇所が一意ではありません")
    addition = (
        '        audit["candidate_provenance"] = [\n'
        '            {"task_id": key, **entry} for key in tasks\n'
        '            for entry in records[key][2].get("candidate_provenance", [])\n'
        '        ]\n'
    )
    control_text = control_text.replace(anchor, addition + anchor, 1)
    compile(control_text, str(controller), "exec")
    controller.write_text(control_text, encoding="utf-8", newline="\n")
    manifest["diagnostic_sha256"]["Kaggle提出.py"] = hashlib.sha256(adapter.read_bytes()).hexdigest()
    manifest["diagnostic_sha256"]["deadline_control.py"] = hashlib.sha256(controller.read_bytes()).hexdigest()
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
    parser.add_argument("--memory-intervention", action="store_true", help="汎用記憶あり／空の限定比較を可能にする")
    args = parser.parse_args()
    print(json.dumps(作成(args.output, 安全化=args.hardened, 記憶介入=args.memory_intervention), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
