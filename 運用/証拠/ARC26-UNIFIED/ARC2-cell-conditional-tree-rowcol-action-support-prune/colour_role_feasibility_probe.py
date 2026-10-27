"""Own-input colour-role feasibility for the two pinned index7 support phases.

This is a diagnostic callback inside the frozen support-only guard/origin/DTO
worker. No new solver action, tree fit, HDS query or heldout data is used.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
PARENT_PATH = HERE.with_name("ARC2-cell-conditional-tree-rowcol-partition-prune") / "action_support_diagnosis.py"
PARENT_SHA256 = "80125444b5c9b4a378097fa3ddd6c0edb5faf9c7d9420894fe46d78f47595412"
PROOF_PATH = PARENT_PATH.parent / "fit_results/action-support-six-phases-20261027T0146Z.jsonl"
PROOF_SHA256 = "1382a7f68abd3bc901016e40c2f22eba2ba04fe3e2f7b8dffe2a1b796ee0bb80"


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_parent():
    if sha(PARENT_PATH.read_bytes()) != PARENT_SHA256:
        raise ValueError("frozen support-only machinery changed")
    spec = importlib.util.spec_from_file_location("arc2_colour_probe_parent", PARENT_PATH)
    parent = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = parent
    spec.loader.exec_module(parent)
    return parent


def fingerprint(parent):
    pins = {"script_sha256": sha(Path(__file__).read_bytes()), "parent_script_sha256": PARENT_SHA256,
            "previous_proof_sha256": PROOF_SHA256, "parent_fingerprint": parent.fingerprint(parent.load_base())}
    return {"sha256": sha(encoded(pins)), **pins}


def rank_profile(counts, target):
    """Frequency groups use dense ranks; tied colours never define unique roles."""
    if target not in counts:
        return {"state": "target_absent"}
    frequency = counts[target]
    frequencies = sorted(set(counts.values()))
    ties = sum(value == frequency for value in counts.values())
    return {"state": "unique" if ties == 1 else "tied", "tie_size": ties,
            "ascending_dense_rank": frequencies.index(frequency) + 1,
            "descending_dense_rank": len(frequencies) - frequencies.index(frequency),
            "ascending_position_start": 1 + sum(value < frequency for value in counts.values()),
            "ascending_position_end": sum(value <= frequency for value in counts.values()),
            "descending_position_start": 1 + sum(value > frequency for value in counts.values()),
            "descending_position_end": sum(value >= frequency for value in counts.values())}


def own_input_profiles(counts, target):
    maximum = max(counts.values())
    largest = [color for color, count in counts.items() if count == maximum]
    global_rank = rank_profile(counts, target)
    if len(largest) != 1:
        nonbackground = {"state": "background_not_unique"}
    elif target == largest[0]:
        nonbackground = {"state": "target_is_unique_background"}
    else:
        nonbackground = rank_profile({color: count for color, count in counts.items() if color != largest[0]}, target)
    return {"global": global_rank, "nonbackground": nonbackground}


def role_labels(profiles):
    return tuple(f"{scope}_{direction}_dense_rank_{profile[direction + '_dense_rank']}"
                 for scope, profile in profiles.items() if profile["state"] == "unique"
                 for direction in ("ascending", "descending"))


def probe_callback(original_condition):
    def probe(module, support, bounds):
        from 接続.ARC2.枠端積層幾何 import counts as input_counts
        baseline = original_condition(module, support, bounds)
        unique = {tuple(tuple(row) for row in pair["input"]): pair for pair in support}
        ordered = [unique[key] for key in sorted(unique)]
        rows, action_teachers = [], defaultdict(set)
        action_cells, role_cells, role_teachers = Counter(), Counter(), defaultdict(set)
        for teacher, pair in enumerate(ordered):
            counts = input_counts(pair["input"])
            targets = (value for row in pair["output"] for value in row)
            for (_features, roles), target in zip(module._input_cells(pair["input"]), targets, strict=True):
                actions = tuple(p for p in module.PROGRAMS if module._program_value(p, roles) == target)
                profiles = own_input_profiles(counts, target)
                labels = role_labels(profiles)
                rows.append((teacher, target in counts, actions, profiles, labels))
                for action in actions:
                    action_cells[action] += 1
                    action_teachers[action].add(teacher)
                for role in labels:
                    role_cells[role] += 1
                    role_teachers[role].add(teacher)
        eligible = {p for p in module.PROGRAMS if action_cells[p] >= bounds.minimum_cell_support
                    and len(action_teachers[p]) >= bounds.minimum_teacher_support}
        unsupported = [row for row in rows if not any(p in eligible for p in row[2])]
        if len(unsupported) != baseline["cells_without_any_support_eligible_matching_action"]:
            raise ValueError("unsupported-cell reconstruction differs from frozen proof")
        profiles_hist = {scope: Counter() for scope in ("global", "nonbackground")}
        rank_hist = {scope: Counter() for scope in ("global", "nonbackground")}
        per_teacher = Counter()
        for teacher, _present, _actions, profiles, _labels in unsupported:
            per_teacher[str(teacher)] += 1
            for scope, profile in profiles.items():
                profiles_hist[scope][profile["state"]] += 1
                if profile["state"] in ("unique", "tied"):
                    rank_hist[scope][f"asc{profile['ascending_dense_rank']}_desc{profile['descending_dense_rank']}_ties{profile['tie_size']}"] += 1
        supported_roles = {role for role in role_cells if role_cells[role] >= bounds.minimum_cell_support
                           and len(role_teachers[role]) >= bounds.minimum_teacher_support}
        return {"root_action_support_proof": baseline,
                "unsupported_cells": len(unsupported), "unsupported_cells_per_anonymous_teacher": dict(per_teacher),
                "target_present_anywhere_in_own_input": sum(row[1] for row in unsupported),
                "target_absent_from_own_input": sum(not row[1] for row in unsupported),
                "frequency_profile_states": {k: dict(v) for k, v in profiles_hist.items()},
                "dense_rank_and_tie_histograms": {k: dict(v) for k, v in rank_hist.items()},
                "unsupported_cells_with_a_unique_frequency_role": sum(bool(row[4]) for row in unsupported),
                "unsupported_cells_with_globally_support_feasible_unique_frequency_role": sum(any(role in supported_roles for role in row[4]) for row in unsupported),
                "diagnostic_rank_role_target_match_supports": [{"role": role, "matching_cells_all_current_support": role_cells[role],
                    "matching_distinct_teachers": len(role_teachers[role]), "global_leaf_support_floor_met": role in supported_roles}
                    for role in sorted(role_cells)],
                "existing_input_count_helper": "接続/ARC2/枠端積層幾何.py:24-26 counts(grid, background=None)",
                "existing_generic_unique_frequency_rank_action_found": False,
                "role_binding_is_a_new_grammar_hypothesis_not_current_capability": True,
                "no_fit_partition_generalization_or_score_claim": True}
    return probe


def worker(payload, expected_source):
    parent = load_parent()
    sources = fingerprint(parent)
    if sources["sha256"] != expected_source:
        raise ValueError("probe source changed")
    original = parent.action_support_condition
    parent.action_support_condition = probe_callback(original)
    result = parent.run_worker(payload, sources["parent_fingerprint"]["sha256"])
    if fingerprint(parent) != sources:
        raise ValueError("probe source changed during worker")
    result["reused_guard_diagnostic_sha256"] = PARENT_SHA256
    result["source_sha256"] = sources["sha256"]
    result["callback_source_sha256"] = sources["script_sha256"]
    return result


def run(args):
    parent = load_parent()
    sources = fingerprint(parent)
    if sources["script_sha256"] != args.expected_script_sha256:
        raise ValueError("probe script differs from review pin")
    base = parent.load_base()
    prepared = parent.prepare(base, sources["parent_fingerprint"])
    proof_bytes = PROOF_PATH.read_bytes()
    if sha(proof_bytes) != PROOF_SHA256:
        raise ValueError("root unsupported-cell evidence differs from pin")
    proof = {(r["cohort_index"], r["phase"]): r for r in (json.loads(v) for v in proof_bytes.splitlines() if v.strip())}
    cases = [case for case in prepared["cases"] if case["cohort_index"] == 7]
    if [case["phase"] for case in cases] != ["before", "after"]:
        raise ValueError("only the two fixed index7 phases are allowed")
    cohort = json.loads((base.OLD_ROOT / "public_results/study20-20261027T0005Z.cohort.json").read_bytes())
    data = base.TRAINING.read_bytes()
    if sha(data) != cohort["training_file_sha256"]:
        raise ValueError("training differs from fixed cohort")
    training = json.loads(data)
    row = next(row for row in cohort["rows"] if row["index"] == 7)
    output = args.output.resolve()
    summary_path = output.with_suffix(".summary.json")
    if not output.is_relative_to(HERE.resolve()) or output.exists() or summary_path.exists():
        raise ValueError("output must be new evidence in this experiment")
    output.parent.mkdir(parents=True, exist_ok=True)
    results = []
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    with output.open("x", encoding="utf-8") as stream:
        for case in cases:
            payload = base.make_payload(training, row, case["phase"], base.DEFAULT_BOUNDS)
            base.validate_payload(payload, "necessary_condition")
            if sha(encoded(payload)) != case["current_support_payload_sha256"]:
                raise ValueError("support differs from existing fixed phase")
            started = time.perf_counter()
            process = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", "--expected-source-sha256", sources["sha256"]],
                input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=parent.ROOT,
                env=env, timeout=90, check=False)
            if process.returncode:
                raise RuntimeError("guarded support-only worker failed")
            result = json.loads(process.stdout)
            if result.get("state") != "complete":
                raise ValueError("support-only worker incomplete")
            expected = proof[(7, case["phase"])]["action_support"]["condition"]["cells_without_any_support_eligible_matching_action"]
            if result["condition"]["unsupported_cells"] != expected:
                raise ValueError("probe changed the unsupported cell cohort")
            record = {"cohort_index": 7, "phase": case["phase"], "current_support_payload_sha256": case["current_support_payload_sha256"],
                      "probe": result, "wall_seconds": round(time.perf_counter() - started, 6)}
            results.append(record)
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
    unchanged = sources == fingerprint(parent)
    if not unchanged:
        raise ValueError("probe source changed")
    summary = {"state": "SUPPORT_COLOUR_ROLE_PROBE_COMPLETE", "completed_at": datetime.now(timezone.utc).isoformat(),
        "requested_phases": 2, "completed_phases": len(results), "sources": sources, "source_unchanged": unchanged,
        "output_sha256": sha(output.read_bytes()), "previous_proof_sha256": PROOF_SHA256,
        "fit_calls": 0, "external_query_calls": 0, "hds_calls": 0, "scoring_calls": 0,
        "unseen_pair_excluded_entirely": True, "new_action_implemented": False, "performance_or_score_claim": False}
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--expected-source-sha256")
    parser.add_argument("--expected-script-sha256")
    parser.add_argument("--output", type=Path, default=HERE / "fit_results/colour-role-support-only.jsonl")
    args = parser.parse_args()
    try:
        result = worker(json.load(sys.stdin), args.expected_source_sha256) if args.worker else run(args)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return 0
    except Exception as error:
        print(json.dumps({"state": "probe_error", "error_type": type(error).__name__}), file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
