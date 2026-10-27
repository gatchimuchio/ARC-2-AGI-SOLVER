"""Matched local evaluation of frozen v61 and its two-slot portfolio overlay.

No execution occurs at import time. ``--preflight`` only reads archives;
``--prepare-only`` only extracts verified files under this experiment directory.
The normal mode runs solver workers and must be invoked explicitly by the Owner
workflow. Held-out targets and current-task identifiers never enter a worker.

Both workers replace the two prior readers: a parent-filtered template pair list
and an EMPTY VALID generic prior. The latter is a matched inactive-prior-removal
intervention, proven dormant here only because every task has >=3 support pairs.
It is not an unmodified-full-bundle evaluation for one/two-shot tasks.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import random
import re
import stat
import subprocess
import sys
import time
from typing import Any
import zipfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MANIFEST = "__arc2_bundle_manifest__.json"
WRAPPER = "接続/ARC2/Kaggle提出.py"
HDS = "接続/ARC2/HDS接続.py"
GENERIC = "接続/ARC2/事前記憶訓練例.json"
TEMPLATE = "接続/ARC2/テンプレート充填教材.json"
TRAINING = ROOT / "入力/Kaggle/arc-agi_training_challenges.json"
FROZEN = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v61-kaggle-staging-20261026"
EXPECTED = {
    "baseline": "06f7e19da4f1b6fc0059a4aef03833fd9074bc725204a3f9c5c1b33523e0fbee",
    "candidate": "629fff543c65b5b2847a19aab1ea644edbc84f9278445d8092e51c472246d2bf",
    "hds": "8cc1456edfab1b84478fcc1b8f82973481709d85a45532b5181d0e79655362a3",
}
EMPTY_GENERIC = {"schema": "arc2-hds-generic-prior-training-v1", "source_split": "training",
                 "example_count": 0, "examples": [], "features": []}


def encoded(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha(path.read_bytes())


def contains_grid(value: Any) -> bool:
    if isinstance(value, list):
        if value and all(isinstance(row, list) and row and all(type(x) is int for x in row) for row in value):
            return True
        return any(contains_grid(item) for item in value)
    return isinstance(value, dict) and any(contains_grid(item) for item in value.values())


def _archive(path: Path, expected: str) -> dict:
    raw = path.read_bytes()
    if sha(raw) != expected:
        raise ValueError(f"archive SHA mismatch: {path}")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate archive member")
        entries = {}
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename or ":" in info.filename:
                raise ValueError("unsafe archive path")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError("symlink archive member")
            entries[info.filename] = archive.read(info)
    manifest = json.loads(entries[MANIFEST])
    rows = manifest["files"]
    if set(entries) != {MANIFEST, *(row["path"] for row in rows)}:
        raise ValueError("archive and internal manifest member sets differ")
    for row in rows:
        value = entries[row["path"]]
        if len(value) != row["size"] or sha(value) != row["sha256"]:
            raise ValueError("internal member hash mismatch: " + row["path"])
    return {"path": path, "sha256": expected, "entries": entries, "manifest": manifest}


def preflight(candidate_dir: Path | None = None, expected_candidate_sha256: str | None = None) -> tuple[dict, dict]:
    """Read and validate payloads without importing any solver source."""
    candidate_dir = HERE if candidate_dir is None else candidate_dir
    if not candidate_dir.is_absolute():
        candidate_dir = HERE / candidate_dir
    candidate_dir = candidate_dir.resolve()
    if not candidate_dir.is_relative_to(HERE.parent.resolve()):
        raise ValueError("candidate build must stay in the sibling experiment artifact tree")
    if expected_candidate_sha256 is None:
        if candidate_dir != HERE:
            raise ValueError("a non-v1 candidate requires explicit --expected-candidate-sha256")
        expected_candidate_sha256 = EXPECTED["candidate"]
    if not re.fullmatch(r"[0-9a-f]{64}", expected_candidate_sha256):
        raise ValueError("expected candidate SHA must be 64 lowercase hex digits")
    build_manifest = json.loads((candidate_dir / "build-manifest.json").read_text(encoding="utf-8"))
    if build_manifest.get("candidate_payload_sha256") != expected_candidate_sha256:
        raise ValueError("candidate build manifest and explicitly pinned payload SHA differ")
    if build_manifest.get("parent_sha256", {}).get("bundle.zip") != EXPECTED["baseline"]:
        raise ValueError("candidate build has a different frozen parent")
    payloads = {
        "baseline": _archive(FROZEN / "bundle.zip", EXPECTED["baseline"]),
        "candidate": _archive(candidate_dir / "candidate/bundle.zip", expected_candidate_sha256),
    }
    a, b = payloads["baseline"]["entries"], payloads["candidate"]["entries"]
    if set(a) != set(b):
        raise ValueError("baseline/candidate archive member sets differ")
    changed = sorted(name for name in a if a[name] != b[name])
    runtime_changed = [name for name in changed if name != MANIFEST]
    if changed != sorted([MANIFEST, WRAPPER]) or runtime_changed != [WRAPPER]:
        raise ValueError("intervention changed unexpected archive members")
    if sha(a[HDS]) != EXPECTED["hds"] or a[HDS] != b[HDS]:
        raise ValueError("frozen HDS source mismatch")
    source = a[HDS].decode("utf-8")
    guards = [
        '必要支持数 = 2 if 二例 else 3',
        '必要追加支持数 = max(0, 必要支持数 - len(課題["train"]))',
        'if 必要追加支持数:',
        '近傍候補 = []',
        '記録群.append(候補機構を学習(機械, 課題, 教材, 境界, 候補器))',
    ]
    if not all(text in source for text in guards):
        raise ValueError("generic-prior dormancy proof context changed")
    info = {
        "archive_sha256": {arm: data["sha256"] for arm, data in payloads.items()},
        "archive_member_changes": changed,
        "runtime_member_changes": runtime_changed,
        "unchanged_runtime_members": len(a) - 2,
        "hds_source_sha256": EXPECTED["hds"],
        "generic_prior_file_sha256": sha(a[GENERIC]),
        "generic_prior_intervention": "empty valid dict in BOTH workers; original 279-pair file is never opened by a worker",
        "generic_prior_dormancy_proof": {
            "support_pairs_minimum": 3,
            "hds_minimum_support": 3,
            "additional_support": 0,
            "source_lines": "frozen HDS接続.py:297-301,548-556,575-576,611-613",
        },
        "candidate_directory": candidate_dir.relative_to(ROOT).as_posix(),
        "candidate_policy_id": build_manifest.get("policy_id"),
        "new_attempt1_training_requirement": build_manifest.get("new_attempt1_training_requirement"),
        "build_manifest_sha256": sha_file(candidate_dir / "build-manifest.json"),
        "protocol_sha256": sha_file(candidate_dir / "protocol.md"),
        "harness_sha256": sha_file(Path(__file__).resolve()),
    }
    wrapper_tree = ast.parse(a[WRAPPER].decode("utf-8"))
    info["payload_nominal_task_timeout_seconds"] = next(
        ast.literal_eval(node.value) for node in wrapper_tree.body
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "課題時間上限秒" for target in node.targets)
    )
    return payloads, info


def _verify_root(root: Path, entries: dict[str, bytes]) -> None:
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != set(entries):
        raise ValueError("extracted root contains missing/extra files: " + str(root))
    for name, data in entries.items():
        if (root / name).read_bytes() != data:
            raise ValueError("extracted member changed: " + name)


def prepare_roots(payloads: dict) -> dict[str, Path]:
    roots = {}
    parent = HERE / "evaluation_roots"
    parent.mkdir(exist_ok=True)
    for arm, data in payloads.items():
        destination = parent / f"{arm}-{data['sha256'][:12]}"
        if destination.is_symlink() or not destination.resolve().is_relative_to(parent.resolve()):
            raise ValueError("extracted root resolves outside the experiment")
        if not destination.exists():
            destination.mkdir()
            for name, value in data["entries"].items():
                target = (destination / name).resolve()
                if not target.is_relative_to(destination.resolve()):
                    raise ValueError("extraction escaped experiment root")
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(value)
        _verify_root(destination, data["entries"])
        roots[arm] = destination
    return roots


def pure_formatter(source: str) -> tuple[Any, Any]:
    """Compile only actual grid validation/reason/format functions, never a solver."""
    names = {"格子か", "_保留理由ラベル群", "結果を候補へ"}
    tree = ast.parse(source)
    selected_names = names | {"_portfolio_qualification_is_valid"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in selected_names]
    if not names.issubset({node.name for node in nodes}):
        raise ValueError("formatter functions missing")
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *nodes], type_ignores=[])
    namespace = {"deepcopy": deepcopy, "re": re, "Any": Any}
    exec(compile(ast.fix_missing_locations(module), "<frozen-formatter-only>", "exec"), namespace)
    return namespace["結果を候補へ"], namespace["格子か"]


def _template_sources(payload: dict) -> list[dict]:
    entries = payload["entries"]
    manifest = json.loads(entries[TEMPLATE])
    if manifest.get("分割") != "training":
        raise ValueError("template prior is not public training")
    result, seen = [], set()
    for item in manifest["教材"]:
        source_id = item["課題ID"]
        original = json.loads(entries[f"入力/公式ソース/ARC-AGI-2/data/training/{source_id}.json"])
        for index in item["訓練例位置"]:
            if (source_id, index) in seen:
                raise ValueError("duplicate template support")
            seen.add((source_id, index))
            pair = original["train"][index]
            result.append({"source_task_id": source_id, "pair": {"input": pair["input"], "output": pair["output"]}})
    return result


def template_for_task(sources: list[dict], task_id: str, queries: list) -> tuple[list, dict]:
    prior, removed_source, removed_input = [], 0, 0
    for source in sources:
        if source["source_task_id"] == task_id:
            removed_source += 1
        elif any(source["pair"]["input"] == query for query in queries):
            removed_input += 1
        else:
            prior.append(deepcopy(source["pair"]))
    return prior, {"examples": len(prior), "payload_sha256": sha(encoded(prior)),
                   "removed_same_source_task": removed_source, "removed_query_input_collision": removed_input}


def semantic_state(machine) -> dict:
    rules = []
    for rule in machine._現行原理群():
        rules.append({"boundary": rule.対象系境界, "relation": rule.関係型,
                      "conditions": rule.条件経路群, "result": rule.結果経路,
                      "state": str(getattr(rule.状態, "value", rule.状態)),
                      "adoption": str(getattr(rule.採用状態, "value", rule.採用状態)),
                      "support": len(rule.根拠参照群), "counterexamples": len(rule.反証参照群),
                      "mapping_sha256": sha(encoded([rule.対応表, rule.対応値表]))})
    rules.sort(key=encoded)
    return {"version": machine.状態.現在版, "experiences": machine.台帳.件数("観測台帳"),
            "updates": machine.台帳.件数("更新台帳"), "active": len(machine._有効原理群()),
            "quarantined": len(machine._係争中原理群()), "semantic_sha256": sha(encoded(rules))}


def _count_diagnostics(value: dict) -> dict:
    return {key: item for key, item in value.items()
            if key != "repeated_panel_candidate_fit" and
            (isinstance(item, (int, float, bool)) or
             isinstance(item, dict) and all(isinstance(x, (int, float, bool)) for x in item.values()))}


def worker(payload_root: Path) -> int:
    """One exact payload worker, with matched prior-loader injections only."""
    payload = json.load(sys.stdin)
    if set(payload) != {"task", "template_prior"}:
        raise ValueError("unexpected worker payload fields")
    task, prior = payload["task"], payload["template_prior"]
    if set(task) != {"train", "test"} or len(task["train"]) < 3:
        raise ValueError("evaluation requires >=3 current support pairs")
    if any(set(pair) != {"input"} for pair in task["test"]):
        raise ValueError("test target or identifier entered worker")
    if any(set(pair) != {"input", "output"} for pair in task["train"] + prior):
        raise ValueError("invalid public support pair")
    payload_root = payload_root.resolve()
    if not payload_root.is_relative_to((HERE / "evaluation_roots").resolve()):
        raise ValueError("payload root is outside this experiment")
    # Readers are patched below. Reject any unexpected payload JSON/data read,
    # including the dormant generic279 file and raw template file/test labels.
    blocked_reads = []
    def read_guard(event, arguments):
        if event == "open" and arguments and isinstance(arguments[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(arguments[0])).resolve()
            if path.is_relative_to(payload_root) and path.suffix.lower() == ".json":
                blocked_reads.append("payload_json")
                raise PermissionError("payload JSON readers must use matched parent prior injection")
    sys.addaudithook(read_guard)
    sys.dont_write_bytecode = True
    blocked_paths = {str(ROOT.resolve()), str((ROOT / "HDS/学習系統/v0.4.2").resolve())}
    sys.path[:] = [str(payload_root / "HDS/学習系統/v0.4.2"), str(payload_root),
                   *(path for path in sys.path if path and str(Path(path).resolve()) not in blocked_paths)]
    os.environ["ARC2_PAYLOAD_ROOT"] = str(payload_root)
    os.environ["ARC2_AGGREGATE_DIAGNOSTICS"] = "1"
    from 接続.ARC2 import HDS接続 as hds
    from 接続.ARC2 import Kaggle提出 as submission
    for module in (hds, submission):
        if not Path(module.__file__).resolve().is_relative_to(payload_root):
            raise ValueError("current-checkout module contamination")
    hds.事前教材を読む = lambda: deepcopy(prior)
    hds.汎用事前記憶を読む = lambda: deepcopy(EMPTY_GENERIC)
    base_type, instances = hds.HDS学習実行系, []
    class ObservedHDS(base_type):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            instances.append(self)
    hds.HDS学習実行系 = ObservedHDS
    before_task = sha(encoded(task))
    output = io.StringIO()
    started, cpu_started = time.perf_counter(), time.process_time()
    with redirect_stdout(output):
        code = submission._worker(task)
    raw_text = output.getvalue()
    raw = json.loads(raw_text)
    if code or raw.get("error"):
        print(json.dumps({"state": "solver_error", "error_type": raw.get("error"), "blocked_prior_read_attempts": len(blocked_reads)}))
        return 0
    predictions, hold = submission.結果を候補へ("analysis", task, raw)
    raw_rows = raw.get("results", [])
    if len(raw_rows) != len(task["test"]):
        print(json.dumps({"state": "result_count_mismatch"}))
        return 0
    metadata = [{"primary_is_none": row.get("answer") is None,
                 "primary_sha256": sha(encoded(row["answer"])) if submission.格子か(row.get("answer")) else None,
                 "status": row.get("status"), "reasons": row.get("reasons", [])}
                for row in raw_rows]
    origins_ok = all(not getattr(module, "__file__", None) or Path(module.__file__).resolve().is_relative_to(payload_root)
                     for name, module in list(sys.modules.items())
                     if name.startswith(("接続.ARC2", "hds学習系統")))
    result = {"state": "complete", "predictions": predictions,
              "hold_audit": [{k: v for k, v in row.items() if k != "task_id"} for row in hold],
              "raw_metadata": metadata, "hds_states": [semantic_state(machine) for machine in instances],
              "aggregate_diagnostics": _count_diagnostics(raw.get("aggregate_diagnostics", {})),
              "task_input_unchanged": before_task == sha(encoded(task)), "module_origins_verified": origins_ok,
              "blocked_prior_read_attempts": len(blocked_reads),
              "solver_seconds": round(time.perf_counter() - started, 6),
              "cpu_seconds": round(time.process_time() - cpu_started, 6)}
    if contains_grid({k: v for k, v in result.items() if k != "predictions"}):
        raise ValueError("raw grid escaped into diagnostics")
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0


def invoke(root: Path, task: dict, prior: list, timeout: float, formatter) -> dict:
    env = os.environ.copy()
    env.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    started = time.perf_counter()
    try:
        process = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", "--payload-root", str(root)],
                                 input=json.dumps({"task": task, "template_prior": prior}, ensure_ascii=False),
                                 capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=HERE,
                                 env=env, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        result = {"state": "timeout"}
    else:
        if process.returncode:
            result = {"state": "worker_exit", "return_code": process.returncode, "stderr_sha256": sha(process.stderr.encode())}
        else:
            try:
                result = json.loads(process.stdout)
            except json.JSONDecodeError:
                result = {"state": "invalid_worker_output"}
    result["wall_seconds"] = round(time.perf_counter() - started, 6)
    if result.get("state") != "complete":
        predictions, audit = formatter("analysis", task, {"error": result.get("state", "worker_error")})
        result.update(predictions=predictions, hold_audit=[{k: v for k, v in row.items() if k != "task_id"} for row in audit],
                      raw_metadata=[{} for _ in task["test"]], hds_states=None)
    return result


def score_attempts(pair: dict, expected: list, query: list, audit: dict | None) -> dict:
    a, b = pair["attempt_1"], pair["attempt_2"]
    source = audit.get("attempt1_source", "input_copy_fallback") if audit else "solver_prediction"
    copy1 = audit is not None and a == query and source != "external_portfolio"
    copy2 = audit is not None and b == query
    pass1 = a == expected and not copy1
    exact2 = b == expected and not copy2
    return {"raw_pass1": a == expected, "raw_pass2": a == expected or b == expected,
            "nonfallback_pass1": pass1, "nonfallback_pass2": pass1 or exact2,
            "second_incremental_exact": exact2 and not pass1,
            "identity_target": expected == query, "attempt1_source": source,
            "true_input_copy_attempt1": copy1, "input_copy_attempt2": copy2,
            "distinct_attempts": a != b, "prediction_sha256": sha(encoded(pair)),
            "attempt1_sha256": sha(encoded(a)), "attempt2_sha256": sha(encoded(b))}


def row_invariants(previous: dict, current: dict, query: list, eligible: bool, candidate_audit: dict | None) -> dict:
    second_equal = previous["attempt_2"] == current["attempt_2"]
    first_changed = previous["attempt_1"] != current["attempt_1"]
    materialized = bool(candidate_audit and candidate_audit.get("attempt1_source") == "external_portfolio")
    valid_materialization = (not materialized or eligible and current["attempt_1"] != query
                            and current["attempt_1"] != previous["attempt_2"] and second_equal)
    return {"attempt2_equal": second_equal, "attempt1_changed": first_changed,
            "outside_scope_unchanged": eligible or previous == current,
            "materialized": materialized, "materialization_valid": bool(valid_materialization),
            "changed_first_has_materialization_provenance": not first_changed or materialized}


def baseline_eligible(state: str, metadata: dict, audit: dict | None, pair: dict, query: list) -> bool:
    return bool(state == "complete" and metadata.get("primary_is_none") is True
                and audit is not None and audit.get("reason") == "solver_hold"
                and pair["attempt_1"] == query and pair["attempt_2"] != query)


def new_first_qualification(audit: dict | None, support_count: int) -> dict:
    """Require full-current-train evidence ONLY for the new materialized first slot.

    The approved frozen second slot is deliberately not requalified or excluded.
    This validates evidence consistency; it is not a generalization claim.
    """
    materialized = bool(audit and audit.get("attempt1_source") == "external_portfolio")
    if not materialized:
        return {"required": False, "valid": True}
    proof = (audit.get("portfolio") or {}).get("selected_qualification")
    required_keys = {"qualified", "train_exact", "train_total", "fit_error_type", "validation_error_counts"}
    present = isinstance(proof, dict) and required_keys <= set(proof)
    proof = proof if isinstance(proof, dict) else {}
    errors = proof.get("validation_error_counts")
    error_free = (proof.get("fit_error_type") is None and isinstance(errors, dict)
                  and all(type(value) is int and value == 0 for value in errors.values()))
    counts_match = (type(proof.get("train_exact")) is int and type(proof.get("train_total")) is int
                    and proof["train_exact"] == proof["train_total"] == support_count and support_count >= 3)
    valid = present and proof.get("qualified") is True and counts_match and error_free
    return {"required": True, "valid": bool(valid), "support_count": support_count,
            "qualified": proof.get("qualified"), "train_exact": proof.get("train_exact"),
            "train_total": proof.get("train_total"), "fit_error_type": proof.get("fit_error_type"),
            "validation_error_counts": errors}


def require_candidate_contract(static: dict) -> None:
    if static.get("new_attempt1_training_requirement") != "all_current_train_exact":
        raise ValueError("solver evaluation requires a candidate with all-current-train-qualified NEW attempt1; v1 remains static history")


def run(tasks_requested: int, seed: int, timeout: float, output: Path,
        candidate_dir: Path | None = None, expected_candidate_sha256: str | None = None) -> dict:
    payloads, static = preflight(candidate_dir, expected_candidate_sha256)
    require_candidate_contract(static)
    roots = prepare_roots(payloads)
    formatters = {arm: pure_formatter(data["entries"][WRAPPER].decode("utf-8"))[0] for arm, data in payloads.items()}
    data_raw = TRAINING.read_bytes()
    data = json.loads(data_raw)
    eligible_ids = sorted(task_id for task_id, task in data.items() if len(task.get("train", [])) >= 4
                          and len({sha(encoded(pair["input"])) for pair in task["train"]}) == len(task["train"]))
    rng = random.Random(seed)
    rng.shuffle(eligible_ids)
    cohort = []
    for task_id in eligible_ids[:tasks_requested]:
        count = len(data[task_id]["train"])
        heldout = sorted(rng.sample(range(count), 2 if count >= 5 else 1))
        cohort.append({"task_id": task_id, "heldout_indices": heldout,
                       "support_pairs": count - len(heldout), "test_inputs": len(heldout)})
    sources = _template_sources(payloads["baseline"])
    if not output.is_absolute():
        output = HERE / output
    output = output.resolve()
    if not output.is_relative_to(HERE.resolve()):
        raise ValueError("evaluation output must stay in this experiment directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    cohort_path, summary_path = output.with_suffix(".cohort.json"), output.with_suffix(".summary.json")
    if any(path.exists() for path in (output, cohort_path, summary_path)):
        raise FileExistsError(output)
    cohort_manifest = {"schema": "arc2-v61-portfolio-cohort-v1", "seed": seed,
                       "training_sha256": sha(data_raw), "eligible_tasks": len(eligible_ids),
                       "rule": "fixed-seed shuffle, unique inputs; holdout2 for >=5 pairs else1; query order is original index order",
                       "selection_uses_outputs": False, "cohort": cohort, "static_preflight": static}
    cohort_path.write_bytes(encoded(cohort_manifest) + b"\n")
    records, grid_records = [], []
    header = {"record_type": "header", "schema": "arc2-v61-portfolio-evaluation-v1",
              "started_at_utc": datetime.now(timezone.utc).isoformat(), "requested_tasks": len(cohort),
              "requested_grids": sum(item["test_inputs"] for item in cohort), "seed": seed,
              "cohort_manifest": str(cohort_path.relative_to(HERE)), "cohort_sha256": sha_file(cohort_path),
              "training_sha256": sha(data_raw), "static_preflight": static,
              "execution_order": "baseline/candidate for odd task index, candidate/baseline for even index",
              "environment": {"python": sys.version, "platform": platform.platform(), "cpu_count": os.cpu_count(),
                              "numpy": importlib.metadata.version("numpy"), "scipy": importlib.metadata.version("scipy")},
              "resource_limits": {"wall_seconds_per_task_worker": timeout, "cpu_limit": None, "ram_limit": None,
                                  "limitation": "Windows CPU/RAM are not isolated; both arms use same host and wall limit"},
              "targets_passed_to_worker": False, "task_id_passed_to_worker": False,
              "prior_scope": "matched inactive-generic-prior removal plus parent-only template source/input exclusion"}
    with output.open("xb") as stream:
        stream.write(encoded(header) + b"\n"); stream.flush()
        for index, item in enumerate(cohort, 1):
            original = data[item["task_id"]]["train"]
            positions = item["heldout_indices"]
            support = [pair for i, pair in enumerate(original) if i not in positions]
            queries = [original[i]["input"] for i in positions]
            task = {"train": support, "test": [{"input": query} for query in queries]}
            prior, prior_audit = template_for_task(sources, item["task_id"], queries)
            responses = {}
            order = ("baseline", "candidate") if index % 2 else ("candidate", "baseline")
            for arm in order:
                responses[arm] = invoke(roots[arm], task, prior, timeout, formatters[arm])
            paired_complete = all(responses[arm]["state"] == "complete" for arm in responses)
            audits = {arm: {row["test_index"]: row for row in response["hold_audit"]}
                      for arm, response in responses.items()}
            rows = []
            for test_index, position in enumerate(positions):
                # All policy/eligibility/proposal decisions have finished. Only now access the held-out target.
                expected = original[position]["output"]
                query = queries[test_index]
                previous = responses["baseline"]["predictions"][test_index]
                current = responses["candidate"]["predictions"][test_index]
                old_audit, new_audit = audits["baseline"].get(test_index), audits["candidate"].get(test_index)
                old_meta = responses["baseline"]["raw_metadata"][test_index]
                new_meta = responses["candidate"]["raw_metadata"][test_index]
                eligible = baseline_eligible(responses["baseline"]["state"], old_meta, old_audit, previous, query)
                before = score_attempts(previous, expected, query, old_audit)
                after = score_attempts(current, expected, query, new_audit)
                invariants = row_invariants(previous, current, query, eligible, new_audit)
                qualification = new_first_qualification(new_audit, len(support))
                row = {"task_index": index, "test_index": test_index, "baseline_eligible": bool(eligible),
                       "paired_complete": paired_complete, "baseline": before, "candidate": after,
                       "invariants": invariants, "hds_raw_row_preserved": old_meta == new_meta,
                       "new_attempt1_train_qualification": qualification,
                       "baseline_hold": old_audit, "candidate_hold": new_audit,
                       "raw_pass2_gain": after["raw_pass2"] and not before["raw_pass2"],
                       "raw_pass2_regression": before["raw_pass2"] and not after["raw_pass2"],
                       "identity_copy_regression": expected == query and before["raw_pass2"] and not after["raw_pass2"],
                       "nonfallback_pass2_gain": after["nonfallback_pass2"] and not before["nonfallback_pass2"],
                       "nonfallback_pass2_regression": before["nonfallback_pass2"] and not after["nonfallback_pass2"]}
                rows.append(row); grid_records.append(row)
            record = {"record_type": "task", "task_index": index, "support_pairs": len(support),
                      "query_count": len(queries), "prior": prior_audit, "execution_order": list(order),
                      "paired_complete": paired_complete,
                      "hds_states_equal": paired_complete and responses["baseline"]["hds_states"] == responses["candidate"]["hds_states"],
                      "arms": {arm: {key: value for key, value in response.items()
                                     if key not in ("predictions", "hold_audit", "raw_metadata")}
                               for arm, response in responses.items()}, "rows": rows}
            if contains_grid(record):
                raise ValueError("raw prediction/target grid would be persisted")
            records.append(record); stream.write(encoded(record) + b"\n"); stream.flush()
            print(f"task {index}/{len(cohort)}: baseline={responses['baseline']['state']}, candidate={responses['candidate']['state']}", flush=True)
    unchanged = True
    try:
        for arm, root in roots.items():
            _verify_root(root, payloads[arm]["entries"])
        unchanged = (sha_file(payloads["baseline"]["path"]) == payloads["baseline"]["sha256"] and
                     sha_file(payloads["candidate"]["path"]) == payloads["candidate"]["sha256"] and
                     sha_file(Path(__file__).resolve()) == static["harness_sha256"])
    except ValueError:
        unchanged = False
    def total(arm: str, key: str) -> int:
        return sum(bool(row[arm][key]) for row in grid_records)
    summary = {"schema": "arc2-v61-portfolio-evaluation-summary-v1", "completed_at_utc": datetime.now(timezone.utc).isoformat(),
               "records_path": str(output.relative_to(HERE)), "cohort_sha256": sha_file(cohort_path),
               "records_sha256": sha_file(output), "static_preflight": static,
               "requested_tasks": len(cohort), "requested_grids": header["requested_grids"],
               "processed_tasks": len(records), "scored_grids": len(grid_records),
               "completed_paired_tasks": sum(record["paired_complete"] for record in records),
               "states": {arm: dict(Counter(record["arms"][arm]["state"] for record in records)) for arm in ("baseline", "candidate")},
               "raw_official_like": {arm: {key: total(arm, key) for key in ("raw_pass1", "raw_pass2")} for arm in ("baseline", "candidate")},
               "scientific_nonfallback": {arm: {key: total(arm, key) for key in ("nonfallback_pass1", "nonfallback_pass2", "second_incremental_exact")} for arm in ("baseline", "candidate")},
               "raw_pass2_delta": total("candidate", "raw_pass2") - total("baseline", "raw_pass2"),
               "nonfallback_pass2_delta": total("candidate", "nonfallback_pass2") - total("baseline", "nonfallback_pass2"),
               "raw_gains": sum(row["raw_pass2_gain"] for row in grid_records),
               "raw_regressions": sum(row["raw_pass2_regression"] for row in grid_records),
               "identity_copy_regressions": sum(row["identity_copy_regression"] for row in grid_records),
               "nonfallback_regressions": sum(row["nonfallback_pass2_regression"] for row in grid_records),
               "nonfallback_gains": sum(row["nonfallback_pass2_gain"] for row in grid_records),
               "all_heldout_correct_tasks": {
                   arm: {metric: sum(all(row[arm][metric] for row in record["rows"]) for record in records)
                         for metric in ("raw_pass2", "nonfallback_pass2")}
                   for arm in ("baseline", "candidate")
               },
               "baseline_eligible_rows": sum(row["baseline_eligible"] for row in grid_records),
               "materialized_rows": sum(row["invariants"]["materialized"] for row in grid_records),
               "selected_family_counts": dict(Counter(
                   row["candidate_hold"]["portfolio"]["selected_family"] for row in grid_records
                   if row["invariants"]["materialized"] and row["candidate_hold"].get("portfolio", {}).get("selected_family")
               )),
               "attempt2_mismatches_all_rows_including_error_fallback": sum(not row["invariants"]["attempt2_equal"] for row in grid_records),
               "attempt2_mismatches_complete_pairs": sum(row["paired_complete"] and not row["invariants"]["attempt2_equal"] for row in grid_records),
               "outside_scope_changed_rows": sum(not row["invariants"]["outside_scope_unchanged"] for row in grid_records),
               "invalid_materializations": sum(not row["invariants"]["materialization_valid"] or not row["invariants"]["changed_first_has_materialization_provenance"] for row in grid_records),
               "new_attempt1_full_train_qualification_failures": sum(not row["new_attempt1_train_qualification"]["valid"] for row in grid_records),
               "hds_raw_row_mismatches": sum(not row["hds_raw_row_preserved"] for row in grid_records),
               "hds_state_mismatches_complete_tasks": sum(record["paired_complete"] and not record["hds_states_equal"] for record in records),
               "new_runtime_failure_tasks": sum(record["arms"]["baseline"]["state"] == "complete" and record["arms"]["candidate"]["state"] != "complete" for record in records),
               "input_or_module_invariant_failures": sum(record["arms"][arm].get("task_input_unchanged") is False or record["arms"][arm].get("module_origins_verified") is False for record in records for arm in ("baseline", "candidate")),
               "wall_seconds": {arm: round(sum(record["arms"][arm].get("wall_seconds", 0) for record in records), 6) for arm in ("baseline", "candidate")},
               "solver_seconds": {arm: round(sum(record["arms"][arm].get("solver_seconds", 0) for record in records), 6) for arm in ("baseline", "candidate")},
               "candidate_portfolio_extra_seconds": round(sum(float((row["candidate_hold"] or {}).get("portfolio", {}).get("extra_seconds", 0)) for row in grid_records), 6),
               "sources_unchanged_at_end": unchanged, "resource_limits": header["resource_limits"],
               "targets_passed_to_worker": False, "task_id_passed_to_worker": False,
               "official_submission": False, "adoption": "UNDECIDED; requires repeat, broader regression and all protocol gates"}
    summary_path.write_bytes(encoded(summary) + b"\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--payload-root", type=Path)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--candidate-dir", type=Path)
    parser.add_argument("--expected-candidate-sha256")
    parser.add_argument("--tasks", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20261026)
    parser.add_argument("--timeout-seconds", type=float, default=90)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.worker:
        try:
            return worker(args.payload_root)
        except Exception as error:
            print(json.dumps({"state": "harness_worker_error", "error_type": type(error).__name__}))
            return 0
    if args.preflight or args.prepare_only:
        payloads, report = preflight(args.candidate_dir, args.expected_candidate_sha256)
        if args.prepare_only:
            report["prepared_roots"] = {arm: str(path.relative_to(HERE)) for arm, path in prepare_roots(payloads).items()}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.tasks < 1 or args.timeout_seconds <= 0:
        parser.error("tasks and timeout must be positive")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or HERE / "evaluation_results" / f"matched-{stamp}.jsonl"
    run(args.tasks, args.seed, args.timeout_seconds, output, args.candidate_dir, args.expected_candidate_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
