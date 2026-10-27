"""Current actual Kaggle worker A2 -> A+F3 under unchanged ADAPTIVE2_TO3.

Reuses ARC2-P3-observation-update.py's worker/observer/dataflow pattern, but
retains failure denominators and actual attempt-level fallback provenance.
No production source, support floor, candidate policy or prior memory changes.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import random
import re
import subprocess
import sys
import time
import traceback
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TRAINING = ROOT / "入力/Kaggle/arc-agi_training_challenges.json"
HDS_PATH = ROOT / "接続/ARC2/HDS接続.py"
SUBMISSION_PATH = ROOT / "接続/ARC2/Kaggle提出.py"
REFERENCE_SCRIPT = HERE.parent / "ARC2-P3-observation-update.py"
REFERENCE_COHORT = HERE.parent / "ARC2-cell-conditional-tree-rowcol-support-prune-lowshot-min2/public_results/study20-20261027T0039Z.cohort.json"
TEMPLATE_MANIFEST = ROOT / "接続/ARC2/テンプレート充填教材.json"
EXPECTED = {"hds": "69ba1aa8f428a108624ae871672496f8b0bf2746b93f96f65d1a0f78d3c0d1fe",
            "submission": "43fd2c444cc1428bdfb3da3b228fca14b6ccb939c169401b1684c2b93b4092e4",
            "reference_script": "14fe5c0d0ef2dce2cae69343309b6a6f45e50262499b497e15c1e2e55ec64621",
            "reference_cohort": "3d12810ec92ef855802b6b559bcd7613a0a6868fdc469e09b58dd8fe794e6376"}
EMPTY_GENERIC = {"schema": "arc2-hds-generic-prior-training-v1", "source_split": "training",
                 "example_count": 0, "examples": [], "features": []}
PHASES = ("before", "after")
ROLES = ("feedback", "unseen")
SCOPE = "CURRENT_FULL_WORKER_ADAPTIVE2_TO3_BATCH_REFIT"
ABSENT_METADATA = (ROOT / ".venv/Lib/site-packages/numpy-2.3.5.dist-info/direct_url.json").resolve()
BLOCKED_JSON = []


class DataBoundaryViolation(RuntimeError):
    pass


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def valid_grid(value):
    return (isinstance(value, list) and 1 <= len(value) <= 30
            and all(isinstance(row, list) and 1 <= len(row) <= 30 and len(row) == len(value[0])
                    and all(type(color) is int and 0 <= color <= 9 for color in row) for row in value))


def contains_grid(value):
    if valid_grid(value):
        return True
    if isinstance(value, dict):
        return any(contains_grid(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_grid(item) for item in value)
    return False


def policy_audit():
    for name, path in (("hds", HDS_PATH), ("submission", SUBMISSION_PATH), ("reference_script", REFERENCE_SCRIPT)):
        if sha(path.read_bytes()) != EXPECTED[name]:
            raise ValueError("pinned current worker/HDS/reference source changed")
    hds_source, submission_source = HDS_PATH.read_text(encoding="utf-8"), SUBMISSION_PATH.read_text(encoding="utf-8")
    hds_tree, wrapper_tree = ast.parse(hds_source), ast.parse(submission_source)
    generic_name = "汎用事前記憶を読む"
    if (any(isinstance(node, ast.Name) and node.id == generic_name for node in ast.walk(hds_tree))
            or any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == generic_name for node in ast.walk(hds_tree))
            or generic_name in submission_source or "事前記憶訓練例.json" in hds_source
            or "汎用事前教材" in hds_source or "必要追加支持数" in hds_source):
        raise ValueError("generic prior is no longer the reviewed absent call path; STOP")
    worker_node = next(node for node in wrapper_tree.body if isinstance(node, ast.FunctionDef) and node.name == "_worker")
    imports = [alias.name for node in ast.walk(worker_node) if isinstance(node, ast.ImportFrom)
               and node.module == "接続.ARC2.HDS接続" for alias in node.names]
    if imports != ["課題を解く", "事前教材を読む"]:
        raise ValueError("current worker prior imports changed")
    assignments = {node.targets[0].id: node.value.value for node in wrapper_tree.body
                   if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                   and isinstance(node.value, ast.Constant)}
    return {"scope": SCOPE, "generic_prior": {"status": "ABSENT_CALL_PATH_PINNED_CURRENT_SOURCE",
            "valid_empty_reader_injected": True, "expected_reader_calls": 0, "expected_content_opens": 0,
            "not_v61_needed_extra_arithmetic": True},
            "adaptive_support": {"before_current_train": 2, "after_current_train": 3,
                                 "expected_outer_and_validator": [2, 3], "forced_or_mutated": False,
                                 "source": "current HDS接続.py:269-277"},
            "selector": "actual Kaggle提出._worker -> 結果を候補へ",
            "diagnostics_mode": "ARC2_AGGREGATE_DIAGNOSTICS=1, same as reference14fe5c",
            "nominal_adapter_task_seconds": assignments.get("課題時間上限秒"),
            "nominal_adapter_parallelism": assignments.get("並列数")}


def source_fingerprint():
    audit = policy_audit()
    if ABSENT_METADATA.exists():
        raise ValueError("reviewed package-metadata absence changed")
    paths = [Path(__file__), REFERENCE_SCRIPT]
    for folder in (ROOT / "接続/ARC2", ROOT / "HDS/学習系統/v0.4.2"):
        paths.extend(folder.rglob("*.py"))
    rows = [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path.read_bytes())}
            for path in sorted(set(path.resolve() for path in paths))]
    absent = {"path": ABSENT_METADATA.relative_to(ROOT).as_posix(), "state": "ABSENT"}
    return {"sha256": sha(encoded({"files": rows, "policy": audit, "metadata_probe": absent})),
            "files": rows, "file_count": len(rows), "policy": audit, "metadata_probe": absent}


def template_sources_parent():
    """Parent only: extract selected training pairs; raw source never enters worker."""
    manifest_bytes = TEMPLATE_MANIFEST.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("分割") != "training":
        raise ValueError("template prior must be public training")
    sources, files = [], [{"path": TEMPLATE_MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha(manifest_bytes)}]
    for item in manifest["教材"]:
        source_id = item["課題ID"]
        if not re.fullmatch("[0-9a-f]{8}", source_id):
            raise ValueError("invalid public template provenance")
        path = ROOT / "入力/公式ソース/ARC-AGI-2/data/training" / (source_id + ".json")
        raw = path.read_bytes()
        data = json.loads(raw)
        files.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha(raw)})
        for index in item["訓練例位置"]:
            pair = data["train"][index]
            sources.append({"source_task_id": source_id,
                            "pair": {"input": deepcopy(pair["input"]), "output": deepcopy(pair["output"])}})
    return sources, files


def filtered_prior(sources, task_id, all_four_inputs):
    forbidden = {sha(encoded(grid)) for grid in all_four_inputs}
    pairs, same_task, input_collision, seen = [], 0, 0, set()
    for source in sources:
        pair = source["pair"]
        if source["source_task_id"] == task_id:
            same_task += 1
        elif sha(encoded(pair["input"])) in forbidden:
            input_collision += 1
        elif sha(encoded(pair)) not in seen:
            pairs.append(deepcopy(pair))
            seen.add(sha(encoded(pair)))
    return pairs, {"same_source_task_removed": same_task, "all_four_input_collisions_removed": input_collision,
                   "retained_examples": len(pairs), "retained_io_sha256": sha(encoded(pairs)),
                   "same_prior_both_phases": True, "target_values_used_for_filter": False}


def freeze_cohort(training, tasks, seed):
    eligible = [task_id for task_id in sorted(training) if len(training[task_id]["train"]) == 4
                and all(valid_grid(pair.get("input")) for pair in training[task_id]["train"])
                and len({sha(encoded(pair["input"])) for pair in training[task_id]["train"]}) == 4]
    if len(eligible) < tasks:
        raise ValueError("not enough exact4 distinct-input tasks")
    rng = random.Random(seed)
    selected = rng.sample(eligible, tasks)
    rows = []
    for index, task_id in enumerate(selected):
        pairs = training[task_id]["train"]
        u, f = rng.sample(range(4), 2)
        rows.append({"index": index, "task_id": task_id, "support_indices": [i for i in range(4) if i not in (u, f)],
                     "feedback_index": f, "unseen_index": u, "query_roles": list(ROLES),
                     "query_input_sha256": [sha(encoded(pairs[i]["input"])) for i in (f, u)],
                     "before_support": 2, "after_support": 3})
    return {"schema": "arc2-full-worker-lowshot-adaptive-cohort-v1", "scope": SCOPE,
            "seed": seed, "eligible_task_count": len(eligible), "tasks_requested": tasks,
            "selection_uses_targets": False, "rows": rows}


def verify_reference(cohort):
    raw = REFERENCE_COHORT.read_bytes()
    if sha(raw) != EXPECTED["reference_cohort"]:
        raise ValueError("fixed-MIN2 reference cohort changed")
    previous = json.loads(raw)
    keys = ("index", "task_id", "support_indices", "feedback_index", "unseen_index", "query_roles",
            "query_input_sha256", "before_support", "after_support")
    identity = lambda item: [{key: row[key] for key in keys} for row in item["rows"]]
    if (identity(previous) != identity(cohort) or previous["seed"] != cohort["seed"]
            or previous["training_file_sha256"] != cohort["training_file_sha256"]):
        raise ValueError("actual-system study differs from requested fixed20/U/F/support/input bytes")
    return {"reference_fixed_min2_cohort_sha256": EXPECTED["reference_cohort"],
            "same_task_U_F_support_identity": True, "do_not_pool_fixed_min2_or_default_min3_scores": True}


def make_payload(training, row, phase, prior, source_sha256):
    pairs = training[row["task_id"]]["train"]
    indices = list(row["support_indices"])
    if phase == "after":
        indices.append(row["feedback_index"])
    elif phase != "before":
        raise ValueError("unknown phase")
    if row["unseen_index"] in indices:
        raise ValueError("unseen target entered runtime support")
    return {"phase": phase, "task": {"train": [deepcopy(pairs[i]) for i in indices],
            "test": [{"input": deepcopy(pairs[i]["input"])} for i in (row["feedback_index"], row["unseen_index"])]},
            "prior": deepcopy(prior), "generic_prior": deepcopy(EMPTY_GENERIC), "source_sha256": source_sha256}


def validate_payload(payload):
    if set(payload) != {"phase", "task", "prior", "generic_prior", "source_sha256"} or payload["phase"] not in PHASES:
        raise ValueError("worker accepts only task/support priors, phase and source proof")
    task = payload["task"]
    if set(task) != {"train", "test"} or len(task["train"]) != (2 if payload["phase"] == "before" else 3):
        raise ValueError("invalid A2/A+F3 phase")
    if not isinstance(payload["prior"], list) or len(payload["prior"]) > 2:
        raise ValueError("template prior must be the filtered canonical IO list")
    for pair in [*task["train"], *payload["prior"]]:
        if set(pair) != {"input", "output"} or not valid_grid(pair["input"]) or not valid_grid(pair["output"]):
            raise ValueError("only valid current-support/public-template IO pairs are allowed")
    if len({sha(encoded(pair["input"])) for pair in task["train"]}) != len(task["train"]):
        raise ValueError("current training inputs must be distinct")
    if len(task["test"]) != 2 or any(set(pair) != {"input"} or not valid_grid(pair["input"]) for pair in task["test"]):
        raise ValueError("query targets and identifiers are forbidden")
    if payload["generic_prior"] != EMPTY_GENERIC:
        raise ValueError("generic prior must be the reviewed VALID empty dictionary")
    forbidden = {sha(encoded(pair["input"])) for pair in [*task["train"], *task["test"]]}
    if any(sha(encoded(pair["input"])) in forbidden for pair in payload["prior"]):
        raise DataBoundaryViolation("parent-filtered prior collided with current support/query input")


def semantic_state(machine):
    # Same normalized observer as the 14fe5c reference; UUIDs/raw tables are not exported.
    rules = []
    for rule in machine._現行原理群():
        enum = lambda value: str(getattr(value, "value", value))
        rules.append({"boundary": rule.対象系境界, "relation": rule.関係型,
                      "conditions": rule.条件経路群, "result": rule.結果経路,
                      "state": enum(rule.状態), "adoption": enum(rule.採用状態),
                      "support_count": len(rule.根拠参照群), "counterexample_count": len(rule.反証参照群),
                      "excluded_counterexample_count": len(rule.除外反証参照群),
                      "mapping_sha256": sha(encoded([rule.対応表, rule.対応値表]))})
    rules.sort(key=encoded)
    return {"minimum_support": machine.最小支持数, "validator_minimum_support": machine.検証器.最小支持数,
            "experience_count": machine.台帳.件数("観測台帳"), "update_count": machine.台帳.件数("更新台帳"),
            "active_principle_count": len(machine._有効原理群()), "quarantined_principle_count": len(machine._係争中原理群()),
            "semantic_rule_sha256": sha(encoded(rules)), "semantic_rules": rules}


def count_diagnostics(value):
    result = {}
    for key, item in value.items():
        if key == "repeated_panel_candidate_fit" and isinstance(item, dict):
            result[key] = {name: item[name] for name in ("status", "failure", "teacher_count", "exact_teacher_count")
                           if name in item and type(item[name]) in (str, int, float, bool)}
        elif type(item) in (int, float, bool):
            result[key] = item
        elif isinstance(item, dict) and all(type(v) in (int, float, bool) for v in item.values()):
            result[key] = item
    return result


def family_stage(item):
    if item.get("training_all_reproduced") and item.get("equality_admitted"):
        return "full_accepted"
    if item.get("training_all_reproduced"):
        return "full_train_fit_without_equality"
    if item.get("status") == "教師反例により不採用":
        return "teacher_counterexample"
    if item.get("status") == "充足する候補なし":
        return "no_candidate"
    return "other_not_full_train_fit"


def pure_formatter():
    tree = ast.parse(SUBMISSION_PATH.read_text(encoding="utf-8"))
    names = {"格子か", "_保留理由ラベル群", "結果を候補へ"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in nodes} != names:
        raise ValueError("actual formatter functions missing")
    namespace = {"Any": Any, "deepcopy": deepcopy, "re": re}
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *nodes], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), "<actual-current-formatter-only>", "exec"), namespace)
    return namespace["結果を候補へ"]


def ensure_no_blocked_json():
    if BLOCKED_JSON:
        raise DataBoundaryViolation("an inner solver caught a forbidden JSON read; STOP")


def worker():
    payload = json.load(sys.stdin)
    validate_payload(payload)
    sources = source_fingerprint()
    if payload["source_sha256"] != sources["sha256"]:
        raise ValueError("source changed before worker")
    metadata_probes = []
    def guard(event, arguments):
        if event == "open" and isinstance(arguments[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(arguments[0]))
            if path.suffix.lower() in (".json", ".jsonl"):
                if path.resolve() == ABSENT_METADATA and not path.exists():
                    metadata_probes.append(ABSENT_METADATA.relative_to(ROOT).as_posix())
                    raise FileNotFoundError("reviewed absent import metadata")
                BLOCKED_JSON.append(path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name)
                raise RuntimeError("worker JSON dataset/prior file access forbidden")
    sys.addaudithook(guard)
    os.environ["ARC2_PAYLOAD_ROOT"] = str(ROOT)
    os.environ["ARC2_AGGREGATE_DIAGNOSTICS"] = "1"
    for path in (ROOT, ROOT / "HDS/学習系統/v0.4.2"):
        sys.path.insert(0, str(path))
    from 接続.ARC2 import HDS接続 as hds
    from 接続.ARC2 import Kaggle提出 as submission
    expected_files = {row["path"]: row["sha256"] for row in sources["files"]}
    def origins():
        checked = []
        for name, loaded in sorted(tuple(sys.modules.items())):
            if name == "接続.ARC2" or name.startswith("接続.ARC2."):
                required = (ROOT / "接続/ARC2").resolve()
            elif name == "hds学習系統" or name.startswith("hds学習系統."):
                required = (ROOT / "HDS/学習系統/v0.4.2").resolve()
            else:
                continue
            filename = getattr(loaded, "__file__", None)
            if filename is None:
                if not all(Path(path).resolve().is_relative_to(required) for path in getattr(loaded, "__path__", [])):
                    raise ValueError("namespace escaped current source tree")
                continue
            actual = Path(filename).resolve()
            if not actual.is_relative_to(required):
                raise ValueError("runtime escaped current source tree")
            relative = actual.relative_to(ROOT).as_posix()
            digest = sha(actual.read_bytes())
            if expected_files.get(relative) != digest:
                raise ValueError("imported runtime is outside source fingerprint")
            checked.append({"module": name, "path": relative, "sha256": digest})
        if Path(submission._worker.__code__.co_filename).resolve() != SUBMISSION_PATH.resolve():
            raise ValueError("actual current worker was not reused")
        return {"module_count": len(checked), "modules_sha256": sha(encoded(checked)),
                "all_current_origins_and_hashes_verified": True, "hds_sha256": EXPECTED["hds"],
                "worker_sha256": EXPECTED["submission"]}
    origins_before = origins()
    calls = {"template_reader": 0, "generic_reader": 0}
    def template_reader():
        calls["template_reader"] += 1
        return deepcopy(payload["prior"])
    def generic_reader():
        calls["generic_reader"] += 1
        return deepcopy(payload["generic_prior"])
    hds.事前教材を読む = template_reader
    hds.汎用事前記憶を読む = generic_reader  # Absent in pinned source; deliberately unused.
    base_type = hds.HDS学習実行系
    instances, initial_states, floors, families, raw_hds_rows, reported_minimum = [], [], [], [], [], []
    class ObservedHDS(base_type):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)  # Never force or mutate support settings.
            instances.append(self)
            initial_states.append(semantic_state(self))
            floors.append({"outer": self.最小支持数, "validator": self.検証器.最小支持数,
                           "constructor_minimum_support": kwargs.get("最小支持数")})
    hds.HDS学習実行系 = ObservedHDS
    original_solve = hds.課題を解く
    def observed_solve(*args, **kwargs):
        result = original_solve(*args, **kwargs)
        reported_minimum.append(result.get("minimum_support"))
        for item in result.get("families", []):
            family = {"boundary": item.get("境界"), "prior_observations": item.get("事前観測数", 0),
                             "current_observations": item.get("現在観測数", 0),
                             "training_all_reproduced": bool(item.get("採用可")),
                             "equality_admitted": bool(item.get("同値採用")), "status": item.get("状態"),
                             "quarantined": item.get("隔離数", 0)}
            family["admission_stage"] = family_stage(family)
            families.append(family)
        for row in result.get("results", []):
            pair = submission._完全候補対(row.get("candidate_attempts"))
            raw_hds_rows.append({"primary_valid": submission.格子か(row.get("answer")),
                                 "primary_is_none": row.get("answer") is None,
                                 "primary_sha256": sha(encoded(row.get("answer"))),
                                 "status": row.get("status"), "reasons": submission._保留理由ラベル群(row.get("reasons")),
                                 "candidate_pair_valid": pair is not None,
                                 "candidate_pair_sha256": sha(encoded(pair)) if pair is not None else None,
                                 "candidate_pair_attempt1_sha256": sha(encoded(pair[0])) if pair is not None else None,
                                 "candidate_pair_family": row.get("candidate_attempt_family"),
                                 "candidate_prediction_family_counts": dict(Counter(item.get("family") for item in row.get("candidate_predictions", [])
                                     if isinstance(item, dict) and isinstance(item.get("family"), str) and submission.格子か(item.get("answer"))))})
        return result
    hds.課題を解く = observed_solve
    task = payload["task"]
    immutable = sha(encoded(task))
    output = io.StringIO()
    started, cpu_started = time.perf_counter(), time.process_time()
    with redirect_stdout(output):
        code = submission._worker(task)
    ensure_no_blocked_json()
    try:
        raw = json.loads(output.getvalue())
    except json.JSONDecodeError:
        raw = {"error": "invalid_solver_output"}
    rows_valid = (isinstance(raw, dict) and isinstance(raw.get("results"), list)
                  and len(raw["results"]) == 2 and all(isinstance(row, dict) for row in raw["results"]))
    state = "complete" if code == 0 and rows_valid and not raw.get("error") else "solver_error"
    predictions, audit = submission.結果を候補へ("analysis", task, raw)
    expected_floor = 2 if payload["phase"] == "before" else 3
    if state == "complete" and (len(instances) != 1 or any(row["outer"] != expected_floor or row["validator"] != expected_floor
                                                         or row["constructor_minimum_support"] != expected_floor for row in floors)
                                or reported_minimum != [expected_floor]):
        raise ValueError("actual production adaptive central-machine policy differs from reviewed 2->3")
    if calls["generic_reader"] != 0 or (state == "complete" and calls["template_reader"] != 1):
        raise DataBoundaryViolation("reviewed prior-reader call path changed; STOP")
    if sha(encoded(task)) != immutable:
        raise ValueError("actual solver mutated input task")
    public_rows = raw.get("results", []) if isinstance(raw, dict) else []
    wrapper_meta = [{"public_answer_valid": submission.格子か(row.get("answer")),
                     "public_answer_sha256": sha(encoded(row.get("answer"))),
                     "public_status": row.get("status"), "public_reasons": submission._保留理由ラベル群(row.get("reasons"))}
                    for row in public_rows]
    for index, row in enumerate(wrapper_meta):
        original = raw_hds_rows[index] if index < len(raw_hds_rows) else {}
        row["raw_hds_primary_hold"] = not bool(original.get("primary_valid"))
        row["wrapper_promoted_candidate_pair_first"] = bool(
            not original.get("primary_valid") and original.get("candidate_pair_valid")
            and row["public_answer_sha256"] == original.get("candidate_pair_attempt1_sha256"))
    final_states = [semantic_state(machine) for machine in instances]
    for item in final_states:
        if item["minimum_support"] != expected_floor or item["validator_minimum_support"] != expected_floor:
            raise ValueError("actual adaptive support setting changed during solve")
    return {"state": state, "predictions": predictions, "hold_audit": audit,
            "blocked_json": list(BLOCKED_JSON), "boundary_violation": False,
            "solver_error_type": (raw.get("error") if isinstance(raw, dict) and isinstance(raw.get("error"), str)
                                  and re.fullmatch(r"[A-Za-z_]\w{0,79}", raw["error"]) else None),
            "scope": SCOPE, "hds_central_constructor_settings": floors,
            "hds_initial_states": initial_states, "hds_final_states": final_states,
            "hds_families": families, "raw_hds_rows": raw_hds_rows, "wrapper_rows": wrapper_meta,
            "raw_hds_primary_is_not_wrapper_promoted_pair": True,
            "reported_minimum_support": reported_minimum,
            "aggregate_diagnostics": count_diagnostics(raw.get("aggregate_diagnostics", {})) if isinstance(raw, dict) else {},
            "prior_readers": {**calls, "generic_status": "ABSENT_CALL_PATH", "generic_content_opens": 0,
                              "template_io_sha256": sha(encoded(payload["prior"]))},
            "runtime_origins_before": origins_before, "runtime_origins_after": origins(),
            "source_sha256": sources["sha256"], "solver_seconds": round(time.perf_counter() - started, 6),
            "process_cpu_seconds": round(time.process_time() - cpu_started, 6),
            "absent_import_metadata_probes": {"state": "ABSENT", "probe_count": len(metadata_probes), "content_reads": 0}}


def normalize_failure(task, state, formatter):
    predictions, audit = formatter("analysis", task, {"error": state})
    return {"state": state, "predictions": predictions, "hold_audit": audit,
            "failure_normalized_by_actual_formatter": True}


def valid_response(value):
    if not isinstance(value, dict) or value.get("state") != "complete":
        return False
    predictions, audit = value.get("predictions"), value.get("hold_audit")
    if (not isinstance(predictions, list) or len(predictions) != 2
            or any(not isinstance(pair, dict) or set(pair) != {"attempt_1", "attempt_2"}
                   or not all(valid_grid(grid) for grid in pair.values()) for pair in predictions)
            or not isinstance(audit, list)):
        return False
    indices = []
    for row in audit:
        if (not isinstance(row, dict) or type(row.get("test_index")) is not int
                or row["test_index"] not in (0, 1) or not isinstance(row.get("reason"), str)
                or ("solver_hold_reasons" in row and not isinstance(row["solver_hold_reasons"], list))):
            return False
        indices.append(row["test_index"])
    return len(indices) == len(set(indices))


def enforce_boundary(value):
    if value.get("boundary_violation") or value.get("blocked_json"):
        raise DataBoundaryViolation("worker data boundary violation; public study must stop")


def invoke(payload, timeout):
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    started = time.perf_counter()
    formatter = pure_formatter()
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker"],
                                input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout, cwd=ROOT, env=env, check=False)
        try:
            value = json.loads(result.stdout) if result.returncode == 0 else None
        except json.JSONDecodeError:
            value = None
        if not valid_response(value):
            metadata = deepcopy(value) if isinstance(value, dict) else {}
            for key in ("predictions", "hold_audit"):
                metadata.pop(key, None)
            state = metadata.get("state")
            if not isinstance(state, str) or state == "complete":
                state = "worker_error_or_invalid_output"
            value = {**metadata, **normalize_failure(payload["task"], state, formatter)}
            value["stderr_sha256"] = sha(result.stderr.encode("utf-8"))
    except subprocess.TimeoutExpired:
        value = normalize_failure(payload["task"], "timeout", formatter)
        value["timeout_seconds"] = timeout
    value["wall_seconds"] = round(time.perf_counter() - started, 6)
    return value


def score_attempts(pair, expected, query, audit):
    a, b = pair["attempt_1"], pair["attempt_2"]
    copy1, copy2 = audit is not None and a == query, audit is not None and b == query
    first = a == expected and not copy1
    second = b == expected and not copy2
    generated = not copy1 or not copy2
    return {"raw_pass1": a == expected, "raw_pass2": a == expected or b == expected,
            "nonfallback_pass1": first, "nonfallback_pass2": first or second,
            "second_incremental_exact": second and not first,
            "attempt1_input_copy_fallback": copy1, "attempt2_input_copy_fallback": copy2,
            "generated_attempt_available": generated, "distinct_attempts": a != b,
            "identity_target": expected == query, "prediction_sha256": sha(encoded(pair)),
            "attempt1_sha256": sha(encoded(a)), "attempt2_sha256": sha(encoded(b))}


def score_and_strip(result, expected, queries):
    safe = deepcopy(result)
    audit = {row["test_index"]: row for row in result.get("hold_audit", [])}
    scores = []
    for index, (target, query) in enumerate(zip(expected, queries, strict=True)):
        score = score_attempts(result["predictions"][index], target, query, audit.get(index))
        score.update(complete=result.get("state") == "complete", query_role=ROLES[index])
        scores.append(score)
    safe.pop("predictions", None)
    for row in safe.get("hold_audit", []):
        row.pop("task_id", None)
    if contains_grid(safe):
        raise ValueError("raw grid escaped prediction/diagnostic stripping")
    return {"scores": scores, "evidence": safe}


def summarize(records, requested):
    summary = {}
    for role_index, role in enumerate(ROLES):
        entry = {}
        for phase in PHASES:
            scores = [record[phase]["scores"][role_index] for record in records]
            entry[phase] = {"requested": requested, "complete": sum(score["complete"] for score in scores),
                **{name: sum(score[name] for score in scores) for name in
                   ("raw_pass1", "raw_pass2", "nonfallback_pass1", "nonfallback_pass2", "second_incremental_exact",
                    "attempt1_input_copy_fallback", "attempt2_input_copy_fallback", "distinct_attempts")},
                "nonfallback_wrong": sum(score["complete"] and score["generated_attempt_available"] and not score["nonfallback_pass2"] for score in scores),
                "hold_without_generated_attempt": sum(score["complete"] and not score["generated_attempt_available"] for score in scores),
                "error_or_timeout": sum(not score["complete"] for score in scores)}
        for metric in ("raw_pass1", "raw_pass2", "nonfallback_pass1", "nonfallback_pass2"):
            paired = [(record["before"]["scores"][role_index][metric], record["after"]["scores"][role_index][metric]) for record in records]
            entry[metric + "_delta"] = sum(int(b) - int(a) for a, b in paired)
            entry[metric + "_gains"] = sum(not a and b for a, b in paired)
            entry[metric + "_regressions"] = sum(a and not b for a, b in paired)
        summary[role] = entry
    summary["states"] = {phase: dict(Counter(record[phase]["evidence"]["state"] for record in records)) for phase in PHASES}
    summary["paired_complete"] = sum(record["before"]["evidence"]["state"] == record["after"]["evidence"]["state"] == "complete" for record in records)
    summary["all_requested_used_for_gains_and_regressions"] = True
    stages = {}
    for phase in PHASES:
        counts = {}
        for record in records:
            for item in record[phase]["evidence"].get("hds_families", []):
                family = counts.setdefault(item["boundary"], {"stages": Counter(), "statuses": Counter()})
                family["stages"][family_stage(item)] += 1
                family["statuses"][str(item.get("status"))] += 1
        stages[phase] = {name: {key: dict(value) for key, value in item.items()} for name, item in sorted(counts.items())}
    summary["per_family_admission_stage_counts"] = stages
    return summary


def parent_environment():
    versions = {}
    for name in ("numpy", "scipy", "kaggle"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    locks = {name: sha((ROOT / name).read_bytes()) if (ROOT / name).is_file() else None
             for name in ("pyproject.toml", "uv.lock")}
    return {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
            "package_versions": versions, "project_lock_sha256": locks}


def run(args):
    sources = source_fingerprint()
    environment = parent_environment()
    if args.expected_source_sha256 and args.expected_source_sha256 != sources["sha256"]:
        raise ValueError("source differs from review pin")
    if not args.prepare_only and not args.expected_source_sha256:
        raise ValueError("actual study requires reviewed --expected-source-sha256")
    training_bytes = TRAINING.read_bytes()
    training = json.loads(training_bytes)
    cohort = freeze_cohort(training, args.tasks, args.seed)
    cohort.update(training_file_sha256=sha(training_bytes), source_sha256=sources["sha256"],
                  timeout_seconds=args.timeout_seconds, environment=environment)
    cohort.update(verify_reference(cohort))
    prior_sources, prior_files = template_sources_parent()
    priors = {}
    for row in cohort["rows"]:
        prior, audit = filtered_prior(prior_sources, row["task_id"], [pair["input"] for pair in training[row["task_id"]]["train"]])
        priors[row["index"]] = prior
        row["parent_prior_filter"] = audit
    cohort["template_source_files_parent_only"] = prior_files
    cohort_bytes = encoded(cohort) + b"\n"
    if args.expected_cohort_sha256 and sha(cohort_bytes) != args.expected_cohort_sha256:
        raise ValueError("cohort differs from review pin")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    cohort_path, summary_path = output.with_suffix(".cohort.json"), output.with_suffix(".summary.json")
    if any(path.exists() for path in (output, cohort_path, summary_path)):
        raise FileExistsError("refuse to overwrite prior evidence")
    cohort_path.write_bytes(cohort_bytes)
    if args.prepare_only:
        return {"state": "prepared_no_solver_execution", "cohort_sha256": sha(cohort_bytes),
                "sources": sources, "environment": environment}
    records = []
    with output.open("x", encoding="utf-8") as stream:
        for row in cohort["rows"]:
            raw = {}
            for phase in PHASES:
                raw[phase] = invoke(make_payload(training, row, phase, priors[row["index"]], sources["sha256"]), args.timeout_seconds)
                try:
                    enforce_boundary(raw[phase])
                except DataBoundaryViolation:
                    safe_violation = {key: value for key, value in raw[phase].items() if key != "predictions"}
                    if contains_grid(safe_violation):
                        safe_violation = {"state": "boundary_violation", "blocked_json": raw[phase].get("blocked_json", [])}
                    stream.write(json.dumps({"record_type": "BOUNDARY_VIOLATION_STOP", "cohort_index": row["index"],
                                             "phase": phase, "evidence": safe_violation}, ensure_ascii=False) + "\n")
                    stream.flush()
                    raise
            pairs = training[row["task_id"]]["train"]
            expected = [pairs[i]["output"] for i in (row["feedback_index"], row["unseen_index"])]
            queries = [pairs[i]["input"] for i in (row["feedback_index"], row["unseen_index"])]
            record = {"cohort_index": row["index"], "task_id": row["task_id"], "scope": SCOPE,
                      **{phase: score_and_strip(raw[phase], expected, queries) for phase in PHASES}}
            records.append(record)
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            print(json.dumps({"completed_tasks": len(records), "requested": args.tasks,
                              "states": {phase: raw[phase]["state"] for phase in PHASES}}), flush=True)
    final_sources = source_fingerprint()
    prior_unchanged = all(sha((ROOT / item["path"]).read_bytes()) == item["sha256"] for item in prior_files)
    summary = {"state": "COMPLETE", "scope": SCOPE, "completed_at": datetime.now(timezone.utc).isoformat(),
               "requested_tasks": args.tasks, "requested_queries_per_phase": 2 * args.tasks,
               "cohort_sha256": sha(cohort_bytes), "output_sha256": sha(output.read_bytes()),
               "sources": sources, "source_unchanged": sources == final_sources, "parent_prior_sources_unchanged": prior_unchanged,
               "metrics": summarize(records, args.tasks), "feedback_after_is_training_fit": True,
               "causal_scope": "full current system response to F under unchanged adaptive2->3 code/policy; not pure HDS-core causality",
               "source_scope": "current local worker and actual formatter with filtered template prior; not frozen v61 Notebook",
               "do_not_pool_fixed_min2_or_default_min3": True, "official_score": None, "adoption": "UNDECIDED_REQUIRES_REVIEW",
               "resources": {"per_worker_wall_seconds": args.timeout_seconds, "cpu_ram_hard_limits": False,
                             "scheduling": "sequential fresh processes; Notebook three-way scheduling not exercised"},
               "raw_metric_note": "official-like any-attempt matches include input-copy fallback even on failed tasks; nonfallback metrics exclude it",
               "environment": environment, "environment_unchanged": environment == parent_environment()}
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--tasks", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20261027)
    parser.add_argument("--timeout-seconds", type=float, default=90)
    parser.add_argument("--expected-source-sha256")
    parser.add_argument("--expected-cohort-sha256")
    parser.add_argument("--output", type=Path, default=HERE / "public_results/study.jsonl")
    args = parser.parse_args()
    if args.worker:
        try:
            value = worker()
            print(json.dumps(value, ensure_ascii=False), flush=True)
            return 0
        except Exception as error:
            print(json.dumps({"state": "boundary_violation" if BLOCKED_JSON or isinstance(error, DataBoundaryViolation) else "harness_worker_error",
                              "boundary_violation": bool(BLOCKED_JSON) or isinstance(error, DataBoundaryViolation),
                              "error_type": type(error).__name__,
                              "frames": [{"file": Path(frame.filename).name, "line": frame.lineno, "function": frame.name}
                                         for frame in traceback.extract_tb(error.__traceback__)], "blocked_json": BLOCKED_JSON}), flush=True)
            return 0
    if args.tasks <= 0 or not 0 < args.timeout_seconds <= 90:
        parser.error("positive task count and worker timeout <=90 are required")
    print(json.dumps(run(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
