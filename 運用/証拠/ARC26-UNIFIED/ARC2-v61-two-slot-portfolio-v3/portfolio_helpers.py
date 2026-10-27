"""Full-current-train qualified portfolio using isolated, lazy fitted models."""
from collections import Counter as _portfolio_Counter
from copy import deepcopy as _portfolio_copy
from time import monotonic as _portfolio_clock


_PORTFOLIO_POLICY_ID = "arc2-v61-hold-two-slot-portfolio-v3-both-copy-composite"
_PORTFOLIO_PRIORITY = (
    "teacher_pair_consensus", "object_extraction", "object_outlier", "object_palette",
    "local_cell_context", "simple_unique_transform", "composite_geometry",
)


def _portfolio_ordered_subset(families):
    families = tuple(families)
    if not families or any(family not in _PORTFOLIO_PRIORITY for family in families):
        raise ValueError("portfolio subset has an unknown family or is empty")
    if len(set(families)) != len(families):
        raise ValueError("portfolio subset repeats a family")
    priorities = [_PORTFOLIO_PRIORITY.index(family) for family in families]
    if priorities != sorted(priorities):
        raise ValueError("portfolio subset differs from the fixed policy order")
    return families


def _portfolio_unpack(value):
    return value if isinstance(value, tuple) and len(value) == 2 else (value, {})


def _portfolio_qualification_is_valid(qualification, expected_total=None):
    if not isinstance(qualification, dict):
        return False
    exact, total = qualification.get("train_exact"), qualification.get("train_total")
    errors = qualification.get("validation_error_counts")
    return (
        qualification.get("qualified") is True
        and type(exact) is int and type(total) is int and total > 0 and exact == total
        and (expected_total is None or total == expected_total)
        and qualification.get("fit_error_type") is None
        and isinstance(errors, dict)
        and all(type(value) is int and value == 0 for value in errors.values())
    )


def _portfolio_model_predictor(model_type, teachers, method_name, with_empty_expected=False):
    """Construct a portfolio-only model; never receive a baseline model instance."""
    model = model_type(_portfolio_copy(teachers))
    method = getattr(model, method_name)
    if with_empty_expected:
        return lambda query: method(query, {})
    return lambda query: method(query)


def _portfolio_simple_predictor(teachers, fit_models, apply_model):
    """Fit the simple-model ensemble once, retaining the v61 unique-output policy."""
    models = fit_models(_portfolio_copy(teachers)) if len(teachers) >= 2 else []

    def predict(query):
        outputs = {}
        for model in models:
            grid = apply_model(model, query)
            if grid is not None:
                outputs.setdefault(tuple(tuple(row) for row in grid), grid)
        grid = _portfolio_copy(next(iter(outputs.values()))) if len(outputs) == 1 else None
        return grid, {"fitted_models": len(models), "distinct_predictions": len(outputs)}

    return predict


class _PortfolioTaskProviders:
    """One qualification per provider/task, using the same isolated fitted predictor."""

    def __init__(self, teachers, factories, valid_grid):
        factories = tuple(factories)
        _portfolio_ordered_subset(family for family, _, _ in factories)
        self._teachers = _portfolio_copy(teachers)
        self._factories = {family: (policy, factory) for family, policy, factory in factories}
        self._valid_grid = valid_grid
        self._states = {}

    def _qualify(self, family):
        if family in self._states:
            return self._states[family], False
        policy, factory = self._factories[family]
        state = {
            "predictor": None, "fit_seconds": 0.0, "validation_seconds": 0.0,
            "qualification": {
                "qualified": False, "train_exact": 0, "train_total": len(self._teachers),
                "fit_error_type": None, "validation_error_counts": {},
                "validation_invalid_grid_count": 0, "validation_mismatch_count": 0,
                "qualification_attempts": 1,
            },
        }
        self._states[family] = state  # Failed qualifications are cached as well.
        qualification = state["qualification"]
        started = _portfolio_clock()
        try:
            predictor = factory(_portfolio_copy(self._teachers))
            if not callable(predictor):
                raise TypeError("portfolio factory did not return a predictor")
            state["predictor"] = predictor
        except Exception as error:
            qualification["fit_error_type"] = type(error).__name__
        state["fit_seconds"] = _portfolio_clock() - started
        if state["predictor"] is None:
            return state, True

        validation_errors = _portfolio_Counter()
        started = _portfolio_clock()
        for teacher in self._teachers:
            try:
                # Predictor receives an input only. The target is used solely below.
                grid, _ = _portfolio_unpack(state["predictor"](_portfolio_copy(teacher["input"])))
                if not self._valid_grid(grid):
                    qualification["validation_invalid_grid_count"] += 1
                elif grid == teacher["output"]:
                    qualification["train_exact"] += 1
                else:
                    qualification["validation_mismatch_count"] += 1
            except Exception as error:
                validation_errors[type(error).__name__] += 1
        state["validation_seconds"] = _portfolio_clock() - started
        qualification["validation_error_counts"] = dict(sorted(validation_errors.items()))
        qualification["qualified"] = (
            qualification["train_total"] > 0
            and qualification["train_exact"] == qualification["train_total"]
            and qualification["fit_error_type"] is None and not validation_errors
        )
        return state, True

    def predict(self, family, query):
        state, qualification_attempted = self._qualify(family)
        qualification = state["qualification"]
        record = {
            "qualification": _portfolio_copy(qualification),
            "timing": {
                "qualification_attempted": qualification_attempted,
                "qualification_cached": not qualification_attempted,
                "fit_seconds": round(state["fit_seconds"], 6) if qualification_attempted else 0.0,
                "validation_seconds": round(state["validation_seconds"], 6) if qualification_attempted else 0.0,
                "query_seconds": 0.0,
            },
        }
        if not _portfolio_qualification_is_valid(qualification, len(self._teachers)):
            return None, record  # No test-query call is allowed for an unqualified provider.
        started = _portfolio_clock()
        try:
            grid, evidence = _portfolio_unpack(state["predictor"](_portfolio_copy(query)))
            if isinstance(evidence, dict):
                record["model_evidence"] = {
                    key: value for key, value in evidence.items()
                    if type(value) in (int, float, bool) and len(str(key)) <= 80
                }
        except Exception as error:
            grid = None
            record["query_error_type"] = type(error).__name__
        record["timing"]["query_seconds"] = round(_portfolio_clock() - started, 6)
        return grid, record

    def providers_for_query(self, query, families=None):
        families = _portfolio_ordered_subset(self._factories if families is None else families)
        if any(family not in self._factories for family in families):
            raise ValueError("portfolio subset was not configured for this task")
        return tuple(
            (family, self._factories[family][0], lambda family=family: self.predict(family, query))
            for family in families
        )


def _portfolio_select_attempt1(query, v61_second, providers, valid_grid):
    """Select only an all-current-train-qualified alternative to frozen attempt2."""
    started = _portfolio_clock()
    second_key = tuple(tuple(row) for row in v61_second)
    query_key = tuple(tuple(row) for row in query)
    providers = tuple(providers)
    families = _portfolio_ordered_subset(family for family, _, _ in providers)
    both_copy = second_key == query_key
    if both_copy and families != ("composite_geometry",):
        raise ValueError("both-copy scope permits only composite_geometry")
    groups = {} if both_copy else {second_key: {"grid": _portfolio_copy(v61_second), "sources": []}}
    source_records = []
    for family, support_policy, predict in providers:
        priority = _PORTFOLIO_PRIORITY.index(family)
        record = {"family": family, "priority": priority, "support_policy": support_policy}
        try:
            grid, evidence = _portfolio_unpack(predict())
        except Exception as error:
            grid, evidence = None, {"query_error_type": type(error).__name__}
        evidence = evidence if isinstance(evidence, dict) else {}
        qualification = evidence.get("qualification")
        record["qualification"] = _portfolio_copy(qualification)
        record["timing"] = _portfolio_copy(evidence.get("timing", {}))
        if evidence.get("query_error_type"):
            record["query_error_type"] = str(evidence["query_error_type"])
        if isinstance(evidence.get("model_evidence"), dict):
            record["model_evidence"] = evidence["model_evidence"]
        qualified = _portfolio_qualification_is_valid(qualification)
        record["qualified"] = qualified
        record["candidate_returned_valid"] = valid_grid(grid)
        record["generated"] = bool(qualified and record["candidate_returned_valid"])
        if record["generated"]:
            key = tuple(tuple(row) for row in grid)
            record["nonidentity"] = key != query_key
            record["distinct_from_v61_attempt2"] = key != second_key
            if key != query_key:
                group = groups.setdefault(key, {"grid": _portfolio_copy(grid), "sources": []})
                group["sources"].append({
                    "priority": priority, "family": family, "support_policy": support_policy,
                    "qualification": _portfolio_copy(qualification),
                })
        source_records.append(record)

    alternatives = []
    for key, group in groups.items():
        if key in (query_key, second_key) or not group["sources"]:
            continue
        best_source = min(group["sources"], key=lambda source: source["priority"])
        alternatives.append((best_source["priority"], key, best_source, group))
    alternatives.sort(key=lambda item: (item[0], item[1]))
    selected = alternatives[0] if alternatives else None
    timing = {
        field: round(sum(float(row.get("timing", {}).get(field, 0)) for row in source_records), 6)
        for field in ("fit_seconds", "validation_seconds", "query_seconds")
    }
    diagnostics = {
        "policy_id": _PORTFOLIO_POLICY_ID, "eligible": True,
        "eligibility_reason": "hds_primary_hold_both_input_copy" if both_copy else "hds_primary_hold_input_copy_attempt1_and_nonidentity_v61_attempt2",
        "eligibility_scope": "both_copy_composite_only" if both_copy else "noncopy_second_seven_provider",
        "requested_provider_families": list(families),
        "new_attempt1_training_requirement": "all_current_train_exact",
        "source_calls": len(source_records),
        "qualified_source_count": sum(bool(row.get("qualified")) for row in source_records),
        "valid_source_proposals": sum(bool(row.get("generated")) for row in source_records),
        "distinct_nonidentity_pool": len(groups),
        "distinct_alternatives_to_v61_attempt2": len(alternatives),
        "selected": selected is not None,
        "selected_family": selected[2]["family"] if selected else None,
        "selected_support_policy": selected[2]["support_policy"] if selected else None,
        "selected_qualification": _portfolio_copy(selected[2]["qualification"]) if selected else None,
        "selected_supporting_families": sorted({source["family"] for source in selected[3]["sources"]}) if selected else [],
        "sources": source_records, "timing": timing,
        "extra_seconds": round(_portfolio_clock() - started, 6),
        "targets_or_task_ids_received": False,
        "portfolio_models_separate_from_v61": True,
    }
    return (_portfolio_copy(selected[3]["grid"]) if selected else None), diagnostics


def _portfolio_audit_summary(hold_records):
    diagnostics = [row.get("portfolio") for row in hold_records if isinstance(row.get("portfolio"), dict)]
    generated, selected, errors, reasons = (_portfolio_Counter() for _ in range(4))
    qualification_attempts = qualified_provider_tasks = unqualified_provider_tasks = 0
    for item in diagnostics:
        reasons[str(item.get("eligibility_reason", "unknown"))] += 1
        if item.get("materialized") and isinstance(item.get("selected_family"), str):
            selected[item["selected_family"]] += 1
        for source in item.get("sources", []):
            if not isinstance(source, dict) or not isinstance(source.get("family"), str):
                continue
            family = source["family"]
            generated[family] += bool(source.get("generated"))
            if source.get("timing", {}).get("qualification_attempted"):
                qualification_attempts += 1
                qualified_provider_tasks += bool(source.get("qualified"))
                unqualified_provider_tasks += not bool(source.get("qualified"))
            qualification = source.get("qualification") or {}
            if source.get("timing", {}).get("qualification_attempted"):
                if qualification.get("fit_error_type"):
                    errors[family + ":fit:" + str(qualification["fit_error_type"])] += 1
                for error, count in qualification.get("validation_error_counts", {}).items():
                    errors[family + ":validation:" + error] += int(count)
            if source.get("query_error_type"):
                errors[family + ":query:" + str(source["query_error_type"])] += 1
    return {
        "policy_id": _PORTFOLIO_POLICY_ID,
        "new_attempt1_training_requirement": "all_current_train_exact",
        "priority": list(_PORTFOLIO_PRIORITY),
        "observed_hold_rows": len(diagnostics),
        "eligible_rows": sum(bool(item.get("eligible")) for item in diagnostics),
        "selected_rows": sum(bool(item.get("selected")) for item in diagnostics),
        "materialized_attempt1_rows": sum(bool(item.get("materialized")) for item in diagnostics),
        "input_copy_attempt1_fallback_rows": sum(bool(row.get("true_input_copy_fallback")) for row in hold_records),
        "hds_primary_hold_provenance_rows": sum(row.get("reason") == "solver_hold" for row in hold_records),
        "v61_attempt2_preservation_failures": sum(row.get("v61_attempt2_preserved") is False for row in hold_records),
        "materialized_without_full_train_qualification": sum(bool(item.get("materialized")) and not _portfolio_qualification_is_valid(item.get("selected_qualification")) for item in diagnostics),
        "qualification_attempts": qualification_attempts,
        "qualified_provider_tasks": qualified_provider_tasks,
        "unqualified_provider_tasks": unqualified_provider_tasks,
        "distinct_alternative_proposals_total": sum(int(item.get("distinct_alternatives_to_v61_attempt2", 0)) for item in diagnostics),
        "extra_seconds_total": round(sum(float(item.get("extra_seconds", 0)) for item in diagnostics), 6),
        "timing_totals": {field: round(sum(float(item.get("timing", {}).get(field, 0)) for item in diagnostics), 6) for field in ("fit_seconds", "validation_seconds", "query_seconds")},
        "generated_source_counts": dict(sorted(generated.items())),
        "selected_family_counts": dict(sorted(selected.items())),
        "source_error_counts": dict(sorted(errors.items())),
        "eligibility_reason_counts": dict(sorted(reasons.items())),
        "eligibility_scope_counts": dict(sorted(_portfolio_Counter(str(item.get("eligibility_scope", "outside_scope")) for item in diagnostics).items())),
        "fallback_counted_correct": False,
    }
