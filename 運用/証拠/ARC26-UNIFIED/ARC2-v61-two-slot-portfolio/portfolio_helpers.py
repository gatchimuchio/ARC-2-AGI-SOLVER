"""Target-independent external proposal portfolio; embedded into the frozen wrapper.

This file contains no solver execution at import time. Providers must be the
existing v61 models fitted from the current task's public train pairs.
"""
from copy import deepcopy as _portfolio_copy
from time import monotonic as _portfolio_clock


_PORTFOLIO_POLICY_ID = "arc2-v61-hold-two-slot-portfolio-v1"
_PORTFOLIO_PRIORITY = (
    "teacher_pair_consensus",
    "object_extraction",
    "object_outlier",
    "object_palette",
    "local_cell_context",
    "simple_unique_transform",
    "composite_geometry",
)


def _portfolio_select_attempt1(query, v61_second, providers, valid_grid):
    """Choose an alternative to the preserved v61 attempt2, without targets or IDs."""
    started = _portfolio_clock()
    second_key = tuple(tuple(row) for row in v61_second)
    query_key = tuple(tuple(row) for row in query)
    groups = {
        second_key: {
            "grid": _portfolio_copy(v61_second),
            "sources": [(len(_PORTFOLIO_PRIORITY), "v61_attempt2", "preserved_baseline")],
        }
    }
    source_records = []
    for priority, (family, support_policy, predict) in enumerate(providers):
        if family != _PORTFOLIO_PRIORITY[priority]:
            raise ValueError("portfolio provider order differs from the frozen policy")
        record = {"family": family, "priority": priority, "support_policy": support_policy}
        try:
            value = predict()
            grid, evidence = value if isinstance(value, tuple) and len(value) == 2 else (value, {})
        except Exception as error:
            record.update({"generated": False, "error_type": type(error).__name__})
            source_records.append(record)
            continue
        generated = valid_grid(grid)
        record["generated"] = generated
        if isinstance(evidence, dict):
            record["support_counts"] = {
                key: evidence[key]
                for key in ("top_votes", "applicable_models", "support", "total", "independent_teacher_pairs")
                if type(evidence.get(key)) is int and evidence[key] >= 0
            }
        if generated:
            key = tuple(tuple(row) for row in grid)
            record["nonidentity"] = key != query_key
            record["distinct_from_v61_attempt2"] = key != second_key
            if key != query_key:
                group = groups.setdefault(key, {"grid": _portfolio_copy(grid), "sources": []})
                group["sources"].append((priority, family, support_policy))
        source_records.append(record)

    alternatives = [
        (min(group["sources"]), key, group)
        for key, group in groups.items()
        if key != query_key and key != second_key
    ]
    # Fixed family priority first, then lexicographic grid order for deterministic ties.
    # Grid content is used only to deduplicate proposals and break ties, never as an answer lookup.
    alternatives.sort(key=lambda item: (item[0][0], item[1]))
    selected = alternatives[0] if alternatives else None
    diagnostics = {
        "policy_id": _PORTFOLIO_POLICY_ID,
        "eligible": True,
        "eligibility_reason": "hds_primary_hold_input_copy_attempt1_and_nonidentity_v61_attempt2",
        "source_calls": len(source_records),
        "valid_source_proposals": sum(bool(row.get("generated")) for row in source_records),
        "distinct_nonidentity_pool": len(groups),
        "distinct_alternatives_to_v61_attempt2": len(alternatives),
        "selected": selected is not None,
        "selected_family": selected[0][1] if selected is not None else None,
        "selected_support_policy": selected[0][2] if selected is not None else None,
        "selected_supporting_families": sorted({item[1] for item in selected[2]["sources"]}) if selected is not None else [],
        "sources": source_records,
        "extra_seconds": round(_portfolio_clock() - started, 6),
        "targets_or_task_ids_received": False,
    }
    return (_portfolio_copy(selected[2]["grid"]) if selected is not None else None), diagnostics


def _portfolio_audit_summary(hold_records):
    diagnostics = [row.get("portfolio") for row in hold_records if isinstance(row.get("portfolio"), dict)]
    generated, selected, errors, reasons = Counter(), Counter(), Counter(), Counter()
    for item in diagnostics:
        reasons[str(item.get("eligibility_reason", "unknown"))] += 1
        if item.get("materialized") and isinstance(item.get("selected_family"), str):
            selected[item["selected_family"]] += 1
        for source in item.get("sources", []):
            if not isinstance(source, dict) or not isinstance(source.get("family"), str):
                continue
            generated[source["family"]] += bool(source.get("generated"))
            if source.get("error_type"):
                errors[source["family"] + ":" + str(source["error_type"])] += 1
    return {
        "policy_id": _PORTFOLIO_POLICY_ID,
        "priority": list(_PORTFOLIO_PRIORITY),
        "observed_hold_rows": len(diagnostics),
        "eligible_rows": sum(bool(item.get("eligible")) for item in diagnostics),
        "selected_rows": sum(bool(item.get("selected")) for item in diagnostics),
        "materialized_attempt1_rows": sum(bool(item.get("materialized")) for item in diagnostics),
        "input_copy_attempt1_fallback_rows": sum(bool(row.get("true_input_copy_fallback")) for row in hold_records),
        "hds_primary_hold_provenance_rows": sum(row.get("reason") == "solver_hold" for row in hold_records),
        "v61_attempt2_preservation_failures": sum(row.get("v61_attempt2_preserved") is False for row in hold_records),
        "distinct_alternative_proposals_total": sum(int(item.get("distinct_alternatives_to_v61_attempt2", 0)) for item in diagnostics),
        "extra_seconds_total": round(sum(float(item.get("extra_seconds", 0)) for item in diagnostics), 6),
        "generated_source_counts": dict(sorted(generated.items())),
        "selected_family_counts": dict(sorted(selected.items())),
        "source_error_counts": dict(sorted(errors.items())),
        "eligibility_reason_counts": dict(sorted(reasons.items())),
        "fallback_counted_correct": False,
    }
