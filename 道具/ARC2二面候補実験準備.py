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
CANDIDATE_SHA = "649846a6ba03232eb4853fa3ed25c39e4c915fae3975ef2f42eb4a0503f306ab"
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
    hds_path = "接続/ARC2/HDS接続.py"
    hds_source = contents[hds_path].decode("utf-8")
    anchor = '        結果群.append(結果)\n'
    if hds_source.count(anchor) != 1:
        raise ValueError("HDS実観測の記録箇所が一意ではありません")
    observation = (
        '        _hds_reasons = 基底結果.get("reasons")\n'
        '        _hds_reason_labels = {\n'
        '            "複数の有効暫定原理が異なる出力を予測したため断定保留": "PREDICTION_CONFLICT",\n'
        '            "原因未確定で隔離中の原理が存在する": "QUARANTINED_PRINCIPLE",\n'
        '            "現行暫定原理の適用に必要な観測が不足している": "MISSING_OBSERVATION",\n'
        '            "現観測だけでは複数の関係候補を識別できない": "INDISTINGUISHABLE",\n'
        '        }\n'
        '        結果["hds_basis"] = {\n'
        '            "status": 基底結果.get("status"),\n'
        '            "reason_count": len(_hds_reasons) if isinstance(_hds_reasons, list) else None,\n'
        '            "reason_labels": [_hds_reason_labels.get(x, "UNKNOWN") if isinstance(x, str) else "UNKNOWN" for x in _hds_reasons] if isinstance(_hds_reasons, list) else None,\n'
        '            "quarantined": 基底結果.get("quarantined"),\n'
        '            "answer_present": 基底結果.get("answer") is not None,\n'
        '            "equality_admitted": 基底結果.get("equality_admitted"),\n'
        '        }\n'
    )
    hds_source = hds_source.replace(anchor, observation + anchor, 1)
    compile(hds_source, hds_path, "exec")
    contents[hds_path] = hds_source.encode("utf-8")
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
                    "cache_member_revalidation": True, "hds_basis_observation_wired": True,
                    "hds_adapter_sha256": hashlib.sha256(contents[hds_path]).hexdigest()}


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
    text = text.replace(anchor, anchor + '        from two_panel import candidate_details as two_panel_candidate_details, provisional_action_gate, local_training_evidence\n', 1)
    anchor = '        公開行群 = []\n'
    if text.count(anchor) != 1:
        raise ValueError("候補証跡の初期化箇所が一意ではありません")
    text = text.replace(anchor, anchor + '        二面候補証跡 = []\n        局所候補証跡 = []\n        局所訓練検証 = None\n', 1)
    anchor = ('                局所近傍候補, _ = 局所近傍候補器.候補(\n'
              '                    課題["test"][位置]["input"], {}\n'
              '                )\n')
    if text.count(anchor) != 1:
        raise ValueError("局所候補の検証箇所が一意ではありません")
    text = text.replace(anchor, (
        '                try:\n'
        '                    局所近傍候補, _ = 局所近傍候補器.候補(課題["test"][位置]["input"], {})\n'
        '                except Exception:\n'
        '                    局所近傍候補 = None\n'
        '                    局所候補証跡.append({"test_index": 位置, "train_exact": False,\n'
        '                        "loo_applicable": False, "loo_total": 0, "loo_correct": 0,\n'
        '                        "loo_conflicts": 0, "loo_unavailable": 0, "reason": "local_inference_error",\n'
        '                        "generalization_risk": "unknown", "candidate_sha256": None, "selected": False, "gate": None})\n'), 1)
    anchor = '                第二候補 = 局所近傍候補\n'
    if text.count(anchor) != 1:
        raise ValueError("局所候補の選択箇所が一意ではありません")
    text = text.replace(anchor, (
        '                if 局所訓練検証 is None:\n'
        '                    try:\n'
        '                        局所締切 = float(os.environ.get("ARC2_PROVISIONAL_CUTOFF_MONOTONIC", ""))\n'
        '                    except (TypeError, ValueError):\n'
        '                        局所締切 = None\n'
        '                    局所訓練検証 = local_training_evidence(課題["train"], 局所近傍候補器,\n'
        '                        LocalCellContextCandidate, clock=time.monotonic, cutoff_monotonic=局所締切)\n'
        '                局所リスク = ("loo_conflict" if 局所訓練検証["loo_conflicts"] else\n'
        '                    "loo_unavailable" if not 局所訓練検証["loo_applicable"] or 局所訓練検証["loo_unavailable"] else "unverified_generalization")\n'
        '                局所hash = hashlib.sha256(json.dumps(局所近傍候補, separators=(",", ":")).encode("utf-8")).hexdigest()\n'
        '                局所証跡 = {"test_index": 位置, **局所訓練検証, "generalization_risk": 局所リスク,\n'
        '                    "candidate_sha256": 局所hash, "selected": False, "gate": None}\n'
        '                局所候補証跡.append(局所証跡)\n'
        '                if 局所訓練検証["train_exact"]:\n'
        '                    局所判定 = provisional_action_gate(第一候補, 第二候補, 局所近傍候補,\n'
        '                        train_exact=True, loo=局所訓練検証, hds_basis=行.get("hds_basis"),\n'
        '                        now_monotonic=time.monotonic(), cutoff_monotonic=局所締切,\n'
        '                        allow_one_shot_loo=len(課題["train"]) == 1, allow_loo_conflicts=True)\n'
        '                    局所証跡["gate"] = 局所判定\n'
        '                    if 局所判定["accepted"]:\n'
        '                        第二候補 = 局所近傍候補\n'
        '                        局所証跡["selected"] = True\n'), 1)
    anchor = '            公開行群.append(\n'
    if text.count(anchor) != 1:
        raise ValueError("候補採用箇所が一意ではありません")
    insertion = (
        '            if 位置 < len(課題["test"]) and (not 格子か(第二候補) or 第二候補 == 第一候補):\n'
        '                二面候補, 二面証跡 = two_panel_candidate_details(課題["train"], 課題["test"][位置]["input"])\n'
        '                if 格子か(二面候補) and 二面候補 != 第一候補:\n'
        '                    try:\n'
        '                        締切 = float(os.environ.get("ARC2_PROVISIONAL_CUTOFF_MONOTONIC", ""))\n'
        '                    except (TypeError, ValueError):\n'
        '                        締切 = None\n'
        '                    判定 = provisional_action_gate(第一候補, 第二候補, 二面候補, train_exact=True, loo=二面証跡,\n'
        '                        hds_basis=行.get("hds_basis"), now_monotonic=time.monotonic(), cutoff_monotonic=締切)\n'
        '                    二面証跡["gate"] = 判定\n'
        '                    if 判定["accepted"]:\n'
        '                        第二候補 = 二面候補\n'
        '                    else:\n'
        '                        二面証跡["decision"] = "rejected_gate"\n'
        '                    二面候補証跡.append({"test_index": 位置, **二面証跡})\n'
        '                elif 二面証跡["decision"] == "rejected_loo_conflict":\n'
        '                    二面証跡["gate"] = None\n'
        '                    二面候補証跡.append({"test_index": 位置, **二面証跡})\n'
    )
    text = text.replace(anchor, insertion + anchor, 1)
    anchor = '        公開結果 = {"results": 公開行群}\n'
    if text.count(anchor) != 1:
        raise ValueError("候補証跡の出力箇所が一意ではありません")
    text = text.replace(anchor, anchor + '        公開結果["candidate_provenance"] = 二面候補証跡\n'
                        '        公開結果["local_training_validation"] = 局所候補証跡\n', 1)
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
    anchor = 'class OwnedArtifact:\n'
    if control_text.count(anchor) != 1:
        raise ValueError("所有出力診断箇所が一意ではありません")
    control_text = control_text.replace(anchor, (
        'def _artifact_io_event(path, operation, error):\n'
        '    try:\n'
        '        names = {"submission.json", "submission_audit.json", "deadline_owned_snapshot.json"}\n'
        '        kinds = {"PermissionError", "FileNotFoundError", "FileExistsError", "OSError", "RuntimeError", "ValueError"}\n'
        '        kind = type(error).__name__ if type(error).__name__ in kinds else "Exception"\n'
        '        number = getattr(error, "errno", None)\n'
        '        windows = getattr(error, "winerror", None)\n'
        '        event = {"artifact": path.name if path.name in names else "other", "operation": operation,\n'
        '                 "exception_type": kind, "errno": number if type(number) is int else None,\n'
        '                 "winerror": windows if type(windows) is int else None}\n'
        '        print("ARC2_ARTIFACT_ERROR " + json.dumps(event, sort_keys=True), file=sys.stderr, flush=True)\n'
        '    except Exception:\n'
        '        pass\n\n\n' + anchor), 1)
    anchor = ('        try:\n'
              '            with temporary.open("xb") as stream:\n'
              '                stream.write(content)\n')
    if control_text.count(anchor) != 1:
        raise ValueError("所有出力の書込箇所が一意ではありません")
    control_text = control_text.replace(anchor, '        operation = "temporary_write"\n' + anchor, 1)
    anchor = '                os.link(temporary, self.path)\n'
    if control_text.count(anchor) != 1:
        raise ValueError("所有出力のlink箇所が一意ではありません")
    control_text = control_text.replace(anchor, '                operation = "link"\n' + anchor, 1)
    anchor = '                if not self.path.is_file() or hashlib.sha256(self.path.read_bytes()).hexdigest() != self.expected:\n'
    if control_text.count(anchor) != 1:
        raise ValueError("所有出力の照合箇所が一意ではありません")
    control_text = control_text.replace(anchor, '                operation = "ownership_check"\n' + anchor, 1)
    anchor = '                os.replace(temporary, self.path)\n'
    if control_text.count(anchor) != 1:
        raise ValueError("所有出力のreplace箇所が一意ではありません")
    control_text = control_text.replace(anchor, '                operation = "replace"\n' + anchor, 1)
    anchor = '        finally:\n            temporary.unlink(missing_ok=True)\n        return content\n'
    if control_text.count(anchor) != 1:
        raise ValueError("所有出力の後処理箇所が一意ではありません")
    control_text = control_text.replace(anchor, (
        '        except OSError as error:\n'
        '            _artifact_io_event(self.path, operation, error)\n'
        '            raise\n'
        '        finally:\n'
        '            had_primary = sys.exc_info()[0] is not None\n'
        '            try:\n'
        '                temporary.unlink(missing_ok=True)\n'
        '            except OSError as error:\n'
        '                _artifact_io_event(self.path, "cleanup", error)\n'
        '                if not had_primary:\n'
        '                    raise\n'
        '        return content\n'), 1)
    anchor = '    if aggregate_diagnostics:\n        env["ARC2_AGGREGATE_DIAGNOSTICS"] = "1"\n'
    if control_text.count(anchor) != 1:
        raise ValueError("暫定行動の期限伝達箇所が一意ではありません")
    control_text = control_text.replace(anchor,
        '    env["ARC2_PROVISIONAL_CUTOFF_MONOTONIC"] = str(min(budget.solve_cutoff, time.monotonic() + api["課題時間上限秒"]))\n' + anchor, 1)
    anchor = '    if process.error:\n        result = {"error": process.error}\n    else:\n'
    replacement = ('    if process.error:\n        result = {"error": process.error}\n'
                   '    elif process.returncode != 0:\n        result = {"error": "worker_exit"}\n    else:\n')
    if control_text.count(anchor) != 1:
        raise ValueError("worker終了状態の判定箇所が一意ではありません")
    control_text = control_text.replace(anchor, replacement, 1)
    anchor = '    diagnostics = result.get("aggregate_diagnostics", {}) if aggregate_diagnostics and isinstance(result, dict) else {}\n'
    if control_text.count(anchor) != 1:
        raise ValueError("候補証跡の受信箇所が一意ではありません")
    control_text = control_text.replace(anchor,
        '    if isinstance(result, dict) and "error" in result and set(result) != {"error"}:\n'
        '        result = {"error": "worker_reported_error"}\n' + anchor, 1)
    provenance = (
        '    diagnostics = dict(diagnostics) if isinstance(diagnostics, dict) else {}\n'
        '    decisions = result.get("candidate_provenance", []) if isinstance(result, dict) else []\n'
        '    local = result.get("local_training_validation", []) if isinstance(result, dict) else []\n'
        '    local_invalid = (not isinstance(local, list) or (isinstance(result, dict)\n'
        '        and "error" not in result and "local_training_validation" not in result))\n'
        '    local_fields = {"test_index", "train_exact", "loo_applicable", "loo_total", "loo_correct", "loo_conflicts", "loo_unavailable", "reason", "generalization_risk", "candidate_sha256", "selected", "gate"}\n'
        '    local_seen = set()\n'
        '    if isinstance(local, list):\n'
        '        for entry in local:\n'
        '            if (not isinstance(entry, dict) or set(entry) != local_fields\n'
        '                    or type(entry["test_index"]) is not int or not 0 <= entry["test_index"] < len(task["test"])\n'
        '                    or entry["test_index"] in local_seen or type(entry["train_exact"]) is not bool\n'
        '                    or type(entry["loo_applicable"]) is not bool or type(entry["selected"]) is not bool\n'
        '                    or (entry["selected"] and (not entry["train_exact"] or entry["gate"] is None))\n'
        '                    or entry["generalization_risk"] not in ("unknown", "loo_conflict", "loo_unavailable", "unverified_generalization")\n'
        '                    or (entry["reason"] != "local_inference_error" and entry["generalization_risk"] != (\n'
        '                        "loo_conflict" if entry["loo_conflicts"] else "loo_unavailable"\n'
        '                        if not entry["loo_applicable"] or entry["loo_unavailable"] else "unverified_generalization"))\n'
        '                    or (entry["candidate_sha256"] is not None and (type(entry["candidate_sha256"]) is not str\n'
        '                        or len(entry["candidate_sha256"]) != 64 or any(c not in "0123456789abcdef" for c in entry["candidate_sha256"])))\n'
        '                    or (entry["selected"] and entry["candidate_sha256"] is None)\n'
        '                    or any(type(entry[k]) is not int or entry[k] < 0 for k in ("loo_total", "loo_correct", "loo_conflicts", "loo_unavailable"))\n'
        '                    or entry["loo_correct"] + entry["loo_conflicts"] + entry["loo_unavailable"] != entry["loo_total"]\n'
        '                    or entry["reason"] not in ("training_evidence_missing", "deadline_unknown", "deadline_expired", "invalid_training_pair", "training_not_reproduced", "training_reproduced_loo_recorded", "local_validation_error", "local_inference_error")\n'
        '                    or (entry["train_exact"] and (entry["reason"] != "training_reproduced_loo_recorded"\n'
        '                        or entry["loo_applicable"] is not (len(task["train"]) >= 2)\n'
        '                        or entry["loo_total"] != (len(task["train"]) if entry["loo_applicable"] else 0)))):\n'
        '                local_invalid = True\n'
        '                break\n'
        '            local_seen.add(entry["test_index"])\n'
        '    fields = {"test_index", "source", "decision", "loo_total", "loo_correct", "loo_conflicts", "loo_unavailable", "gate"}\n'
        '    def valid_gate(gate, accepted):\n'
        '        fields = {"authority", "objective", "loss", "accepted", "reason", "hds_truth_approved", "confidence", "dominance", "risk", "hds_basis", "remaining_seconds"}\n'
        '        if (not isinstance(gate, dict) or set(gate) != fields or gate["authority"] != "arc2_domain_adapter"\n'
        '                or gate["objective"] != "pass_at_2_exact" or gate["loss"] != "zero_if_either_attempt_is_exact_else_one"\n'
        '                or gate["hds_truth_approved"] is not False or gate["confidence"] is not None or gate["accepted"] is not accepted\n'
        '                or gate["dominance"] != "first_attempt_preserved_if_output_finishes_before_deadline"\n'
        '                or gate["risk"] != "candidate_may_be_wrong_or_runtime_may_expire" or type(gate["reason"]) is not str):\n'
        '            return False\n'
        '        if not accepted:\n'
        '            return gate["reason"] in {"invalid_or_duplicate_candidate", "existing_distinct_second_preserved", "training_evidence_missing", "loo_evidence_invalid_or_conflicting", "hds_observation_unknown", "deadline_unknown", "deadline_expired"}\n'
        '        basis = gate["hds_basis"]\n'
        '        reasons = {"PREDICTION_CONFLICT", "QUARANTINED_PRINCIPLE", "MISSING_OBSERVATION", "INDISTINGUISHABLE", "UNKNOWN"}\n'
        '        remaining = gate["remaining_seconds"]\n'
        '        return (gate["reason"] == "distinct_second_preserves_first_under_any_exact_target"\n'
        '                and type(remaining) in (int, float) and 0 < remaining < 1e100 and math.isfinite(remaining)\n'
        '                and isinstance(basis, dict) and set(basis) == {"status", "reason_count", "reason_labels", "quarantined", "answer_present", "equality_admitted"}\n'
        '                and basis["status"] in ("出力", "断定保留") and type(basis["reason_count"]) is int and basis["reason_count"] >= 0\n'
        '                and isinstance(basis["reason_labels"], list) and len(basis["reason_labels"]) == basis["reason_count"]\n'
        '                and all(type(label) is str and label in reasons for label in basis["reason_labels"])\n'
        '                and type(basis["quarantined"]) is int and basis["quarantined"] >= 0\n'
        '                and type(basis["answer_present"]) is bool and type(basis["equality_admitted"]) is bool)\n'
        '    invalid_provenance = (local_invalid or not isinstance(decisions, list) or (isinstance(result, dict)\n'
        '        and "error" not in result and "candidate_provenance" not in result))\n'
        '    if invalid_provenance:\n'
        '        decisions = []\n'
        '    seen_indices = set()\n'
        '    for decision in decisions:\n'
        '        if (not isinstance(decision, dict) or set(decision) != fields\n'
        '                or type(decision["test_index"]) is not int or not 0 <= decision["test_index"] < len(task["test"])\n'
        '                or decision["test_index"] in seen_indices\n'
        '                or decision["source"] != "two_panel_occupancy_truth_table"\n'
        '                or decision["decision"] not in ("provisional_external_candidate", "rejected_loo_conflict", "rejected_gate")\n'
        '                or any(type(decision[k]) is not int or decision[k] < 0 for k in ("loo_total", "loo_correct", "loo_conflicts", "loo_unavailable"))\n'
        '                or decision["loo_total"] != len(task["train"])\n'
        '                or decision["loo_correct"] + decision["loo_conflicts"] + decision["loo_unavailable"] != decision["loo_total"]\n'
        '                or (decision["decision"] == "provisional_external_candidate" and decision["loo_conflicts"] != 0)\n'
        '                or (decision["decision"] == "rejected_loo_conflict" and (decision["loo_conflicts"] == 0 or decision["gate"] is not None))\n'
        '                or (decision["decision"] != "rejected_loo_conflict" and not valid_gate(\n'
        '                    decision["gate"], decision["decision"] == "provisional_external_candidate"))):\n'
        '            invalid_provenance = True\n'
        '            break\n'
        '        seen_indices.add(decision["test_index"])\n'
        '    if not local_invalid:\n'
        '        for entry in local:\n'
        '            if entry["gate"] is not None and not valid_gate(entry["gate"], entry["selected"]):\n'
        '                local_invalid = True\n'
        '                break\n'
        '    invalid_provenance = invalid_provenance or local_invalid\n'
        '    if invalid_provenance:\n'
        '        decisions = []\n'
    )
    control_text = control_text.replace(anchor, anchor + provenance, 1)
    anchor = '            result = json.loads(process.stdout)\n'
    if control_text.count(anchor) != 1:
        raise ValueError("worker JSON読込箇所が一意ではありません")
    control_text = control_text.replace(anchor,
        anchor + '            if not isinstance(result, dict):\n'
        '                raise ValueError("worker result must be an object")\n'
        '            json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")\n', 1)
    anchor = '        except (json.JSONDecodeError, TypeError):\n'
    if control_text.count(anchor) != 1:
        raise ValueError("worker JSON検査箇所が一意ではありません")
    control_text = control_text.replace(anchor, '        except (ValueError, TypeError, RecursionError):\n', 1)
    anchor = '    return (*api["結果を候補へ"](task_id, task, result), diagnostics)\n'
    if control_text.count(anchor) != 1:
        raise ValueError("候補証跡の提出照合箇所が一意ではありません")
    reconciliation = (
        '    if invalid_provenance:\n'
        '        result = {"error": "invalid_candidate_provenance"}\n'
        '    predictions, holds = api["結果を候補へ"](task_id, task, result)\n'
        '    rows = result.get("results") if isinstance(result, dict) else None\n'
        '    valid_rows = isinstance(rows, list) and len(rows) == len(task["test"])\n'
        '    for entry in local if not invalid_provenance else []:\n'
        '        if not entry["selected"]:\n'
        '            continue\n'
        '        index = entry["test_index"]\n'
        '        row = rows[index] if valid_rows else None\n'
        '        output = predictions[index] if isinstance(predictions, list) and index < len(predictions) else None\n'
        '        if (not isinstance(row, dict) or not isinstance(output, dict)\n'
        '                or output.get("attempt_2") != row.get("second_answer")\n'
        '                or output.get("attempt_1") == output.get("attempt_2")\n'
        '                or hashlib.sha256(json.dumps(output.get("attempt_2"), separators=(",", ":")).encode("utf-8")).hexdigest() != entry["candidate_sha256"]):\n'
        '            invalid_provenance = True\n'
        '            result = {"error": "invalid_candidate_provenance"}\n'
        '            predictions, holds = api["結果を候補へ"](task_id, task, result)\n'
        '            decisions = []\n'
        '            break\n'
        '    kept = []\n'
        '    dropped = [{"test_index": None, "reason": "invalid_provenance"}] if invalid_provenance else []\n'
        '    for decision in decisions:\n'
        '        index = decision["test_index"]\n'
        '        if not valid_rows:\n'
        '            dropped.append({"test_index": index, "reason": "invalid_worker_result"})\n'
        '            continue\n'
        '        if decision["decision"] == "provisional_external_candidate":\n'
        '            row = rows[index]\n'
        '            output = predictions[index] if index < len(predictions) else None\n'
        '            if (not isinstance(row, dict) or not isinstance(output, dict)\n'
        '                    or output.get("attempt_2") != row.get("second_answer")\n'
        '                    or output.get("attempt_1") == output.get("attempt_2")):\n'
        '                dropped.append({"test_index": index, "reason": "candidate_not_applied"})\n'
        '                continue\n'
        '        kept.append(decision)\n'
        '    diagnostics["candidate_provenance"] = kept\n'
        '    diagnostics["candidate_provenance_drops"] = dropped\n'
        '    diagnostics["local_training_validation"] = [] if invalid_provenance else local\n'
        '    return predictions, holds, diagnostics\n'
    )
    control_text = control_text.replace(anchor, reconciliation, 1)
    anchor = '        if args.aggregate_diagnostics:\n            scalar, families, distinct, requests = Counter(), Counter(), Counter(), Counter()\n'
    if control_text.count(anchor) != 1:
        raise ValueError("候補証跡の監査箇所が一意ではありません")
    addition = (
        '        audit["candidate_provenance"] = [\n'
        '            {"task_id": key, **entry} for key in tasks\n'
        '            for entry in records[key][2].get("candidate_provenance", [])\n'
        '        ]\n'
        '        audit["candidate_provenance_drops"] = [\n'
        '            {"task_id": key, **entry} for key in tasks\n'
        '            for entry in records[key][2].get("candidate_provenance_drops", [])\n'
        '        ]\n'
        '        audit["local_training_validation"] = [\n'
        '            {"task_id": key, **entry} for key in tasks\n'
        '            for entry in records[key][2].get("local_training_validation", [])\n'
        '        ]\n'
    )
    control_text = control_text.replace(anchor, addition + anchor, 1)
    compile(control_text, str(controller), "exec")
    controller.write_text(control_text, encoding="utf-8", newline="\n")
    outer = destination / "outer_watchdog.py"
    outer_text = outer.read_text(encoding="utf-8")
    anchor = '    if not process.cleanup_complete or control.active:\n'
    if outer_text.count(anchor) != 1:
        raise ValueError("外側watchdogの失敗診断箇所が一意ではありません")
    outer_text = outer_text.replace(anchor, (
        '    emitted = 0\n'
        '    for line in process.stderr.splitlines():\n'
        '        if not line.startswith("ARC2_ARTIFACT_ERROR ") or emitted >= 10:\n'
        '            continue\n'
        '        try:\n'
        '            event = json.loads(line[len("ARC2_ARTIFACT_ERROR "):])\n'
        '        except (ValueError, TypeError, RecursionError):\n'
        '            continue\n'
        '        if (not isinstance(event, dict) or set(event) != {"artifact", "operation", "exception_type", "errno", "winerror"}\n'
        '                or event["artifact"] not in ("submission.json", "submission_audit.json", "deadline_owned_snapshot.json", "other")\n'
        '                or event["operation"] not in ("temporary_write", "link", "ownership_check", "replace", "cleanup", "outer_controller")\n'
        '                or event["exception_type"] not in ("PermissionError", "FileNotFoundError", "FileExistsError", "OSError", "RuntimeError", "ValueError", "Exception")\n'
        '                or any(event[k] is not None and (type(event[k]) is not int or not -2147483648 <= event[k] <= 2147483647)\n'
        '                       for k in ("errno", "winerror"))):\n'
        '            continue\n'
        '        print("ARC2_ARTIFACT_ERROR " + json.dumps(event, sort_keys=True), file=sys.stderr, flush=True)\n'
        '        emitted += 1\n'
        '    if emitted and process.error == "global_deadline":\n'
        '        raise RuntimeError("inner artifact failure before deadline")\n' + anchor), 1)
    anchor = 'from deadline_control import OwnedSnapshot, ProcessControl, SNAPSHOT_NAME, artifact_bytes\n'
    if outer_text.count(anchor) != 1:
        raise ValueError("外側watchdogの診断import箇所が一意ではありません")
    outer_text = outer_text.replace(anchor, anchor.rstrip("\n") + ', _artifact_io_event\n', 1)
    anchor = 'if __name__ == "__main__":\n    raise SystemExit(main())\n'
    if outer_text.count(anchor) != 1:
        raise ValueError("外側watchdogの終了箇所が一意ではありません")
    outer_text = outer_text.replace(anchor, (
        'if __name__ == "__main__":\n'
        '    try:\n'
        '        raise SystemExit(main())\n'
        '    except Exception as error:\n'
        '        _artifact_io_event(Path("other"), "outer_controller", error)\n'
        '        raise SystemExit(1)\n'), 1)
    compile(outer_text, str(outer), "exec")
    outer.write_text(outer_text, encoding="utf-8", newline="\n")
    manifest["diagnostic_sha256"]["Kaggle提出.py"] = hashlib.sha256(adapter.read_bytes()).hexdigest()
    manifest["diagnostic_sha256"]["deadline_control.py"] = hashlib.sha256(controller.read_bytes()).hexdigest()
    manifest["diagnostic_sha256"]["outer_watchdog.py"] = hashlib.sha256(outer.read_bytes()).hexdigest()
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
