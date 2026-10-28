"""Input-only candidate: learn a two-panel occupancy-to-color mapping from train."""
from collections import Counter
import math


def _valid(grid):
    return (isinstance(grid, list) and 1 <= len(grid) <= 30
            and all(isinstance(row, list) and 1 <= len(row) <= 30
                    and all(type(v) is int and 0 <= v <= 9 for v in row) for row in grid)
            and len({len(row) for row in grid}) == 1)


def _split(grid, axis, separator):
    if not _valid(grid):
        return None
    height, width = len(grid), len(grid[0])
    length = width if axis == "horizontal" else height
    if length <= separator or (length - separator) % 2:
        return None
    n = (length - separator) // 2
    if separator:
        middle = [row[n] for row in grid] if axis == "horizontal" else grid[n]
        if len(set(middle)) != 1:
            return None
    if axis == "horizontal":
        left = [row[:n] for row in grid]
        right = [row[n + separator:] for row in grid]
    else:
        left = grid[:n]
        right = grid[n + separator:]
    frequencies = Counter(v for panel in (left, right) for row in panel for v in row)
    most = max(frequencies.values())
    backgrounds = [color for color, count in frequencies.items() if count == most]
    return (left, right, backgrounds[0]) if len(backgrounds) == 1 else None


def _predict(split, mapping):
    a, b, background = split
    return [[mapping[(a[r][c] != background, b[r][c] != background)]
             for c in range(len(a[0]))] for r in range(len(a))]


def _candidate_without_loo(train, test_input):
    if (not isinstance(train, list) or len(train) < 2 or not _valid(test_input)
            or any(not isinstance(pair, dict) or not _valid(pair.get("input"))
                   or not _valid(pair.get("output")) for pair in train)):
        return None
    distinct = {tuple(tuple(row) for row in pair["input"]) for pair in train}
    if len(distinct) < 2:
        return None
    viable = []
    for axis in ("horizontal", "vertical"):
        for separator in (0, 1):
            mapping = {}
            compatible = True
            splits = []
            for pair in train:
                split = _split(pair["input"], axis, separator)
                if split is None:
                    compatible = False
                    break
                a, b, background = split
                output = pair["output"]
                if len(output) != len(a) or len(output[0]) != len(a[0]):
                    compatible = False
                    break
                for r in range(len(a)):
                    for c in range(len(a[0])):
                        key = (a[r][c] != background, b[r][c] != background)
                        color = output[r][c]
                        if key in mapping and mapping[key] != color:
                            compatible = False
                            break
                        mapping[key] = color
                    if not compatible:
                        break
                splits.append(split)
                if not compatible:
                    break
            if not compatible or len(mapping) != 4 or len(set(mapping.values())) != 2:
                continue
            if any(_predict(split, mapping) != pair["output"] for split, pair in zip(splits, train)):
                continue
            viable.append((axis, separator, mapping))
    candidates = []
    for axis, separator, mapping in viable:
        split = _split(test_input, axis, separator)
        if split is None:
            return None
        answer = _predict(split, mapping)
        if _valid(answer) and answer not in candidates:
            candidates.append(answer)
    return candidates[0] if len(candidates) == 1 else None


def candidate_details(train, test_input):
    """Return an input-only candidate and train-only LOO observations."""
    prediction = _candidate_without_loo(train, test_input)
    details = {"source": "two_panel_occupancy_truth_table", "decision": "provisional_external_candidate",
               "loo_total": 0, "loo_correct": 0, "loo_conflicts": 0, "loo_unavailable": 0}
    if prediction is None:
        return None, details
    for index, held in enumerate(train):
        details["loo_total"] += 1
        remaining = train[:index] + train[index + 1:]
        loo_prediction = _candidate_without_loo(remaining, held["input"])
        if loo_prediction is None:
            details["loo_unavailable"] += 1
        elif loo_prediction == held["output"]:
            details["loo_correct"] += 1
        else:
            details["loo_conflicts"] += 1
    if details["loo_conflicts"]:
        details["decision"] = "rejected_loo_conflict"
        return None, details
    return prediction, details


def candidate(train, test_input):
    return candidate_details(train, test_input)[0]


def local_training_evidence(train, model, factory, *, clock, cutoff_monotonic):
    """Observe complete train fit and LOO without treating abstention as correct."""
    evidence = {"train_exact": False, "loo_applicable": False, "loo_total": 0,
                "loo_correct": 0, "loo_conflicts": 0, "loo_unavailable": 0,
                "reason": "training_evidence_missing"}
    if not isinstance(train, list) or not train:
        return evidence
    if (type(cutoff_monotonic) not in (int, float) or not -1e100 < cutoff_monotonic < 1e100
            or not math.isfinite(cutoff_monotonic)):
        evidence["reason"] = "deadline_unknown"
        return evidence
    for pair in train:
        if clock() >= cutoff_monotonic:
            evidence["reason"] = "deadline_expired"
            return evidence
        if (not isinstance(pair, dict) or not _valid(pair.get("input"))
                or not _valid(pair.get("output"))):
            evidence["reason"] = "invalid_training_pair"
            return evidence
        try:
            predicted, _ = model.候補(pair["input"], {})
        except Exception:
            evidence["reason"] = "local_validation_error"
            return evidence
        if predicted != pair["output"]:
            evidence["reason"] = "training_not_reproduced"
            return evidence
    evidence["train_exact"] = True
    if len(train) >= 2:
        evidence["loo_applicable"] = True
        for index, held in enumerate(train):
            if clock() >= cutoff_monotonic:
                evidence["train_exact"] = False
                evidence["reason"] = "deadline_expired"
                return evidence
            try:
                predicted, _ = factory(train[:index] + train[index + 1:]).候補(held["input"], {})
            except Exception:
                evidence["train_exact"] = False
                evidence["reason"] = "local_validation_error"
                return evidence
            evidence["loo_total"] += 1
            if predicted is None:
                evidence["loo_unavailable"] += 1
            elif predicted == held["output"]:
                evidence["loo_correct"] += 1
            else:
                evidence["loo_conflicts"] += 1
    evidence["reason"] = "training_reproduced_loo_recorded"
    return evidence


def provisional_action_gate(first, existing_second, proposed, *, train_exact, loo,
                            hds_basis, now_monotonic, cutoff_monotonic,
                            allow_one_shot_loo=False, allow_loo_conflicts=False):
    """Keep HDS truth decisions separate from a loss-aware second-attempt action."""
    result = {"authority": "arc2_domain_adapter", "objective": "pass_at_2_exact",
              "loss": "zero_if_either_attempt_is_exact_else_one", "accepted": False,
              "reason": "unverified", "hds_truth_approved": False, "confidence": None,
              "dominance": "first_attempt_preserved_if_output_finishes_before_deadline",
              "risk": "candidate_may_be_wrong_or_runtime_may_expire", "hds_basis": None,
              "remaining_seconds": None}
    if not _valid(first) or not _valid(proposed) or proposed == first:
        result["reason"] = "invalid_or_duplicate_candidate"
        return result
    if _valid(existing_second) and existing_second != first:
        result["reason"] = "existing_distinct_second_preserved"
        return result
    if train_exact is not True or not isinstance(loo, dict):
        result["reason"] = "training_evidence_missing"
        return result
    keys = ("loo_total", "loo_correct", "loo_conflicts", "loo_unavailable")
    if (any(type(loo.get(key)) is not int or loo[key] < 0 for key in keys)
            or (loo["loo_total"] < 2 and not (allow_one_shot_loo is True and loo["loo_total"] == 0))
            or loo["loo_correct"] + loo["loo_conflicts"] + loo["loo_unavailable"] != loo["loo_total"]
            or (loo["loo_conflicts"] != 0 and allow_loo_conflicts is not True)):
        result["reason"] = "loo_evidence_invalid_or_conflicting"
        return result
    basis_fields = {"status", "reason_count", "reason_labels", "quarantined", "answer_present", "equality_admitted"}
    known_reasons = {"PREDICTION_CONFLICT", "QUARANTINED_PRINCIPLE", "MISSING_OBSERVATION",
                     "INDISTINGUISHABLE", "UNKNOWN"}
    if (not isinstance(hds_basis, dict) or set(hds_basis) != basis_fields
            or hds_basis["status"] not in ("出力", "断定保留")
            or type(hds_basis["reason_count"]) is not int or hds_basis["reason_count"] < 0
            or not isinstance(hds_basis["reason_labels"], list)
            or len(hds_basis["reason_labels"]) != hds_basis["reason_count"]
            or any(type(label) is not str or label not in known_reasons for label in hds_basis["reason_labels"])
            or type(hds_basis["quarantined"]) is not int or hds_basis["quarantined"] < 0
            or type(hds_basis["answer_present"]) is not bool
            or type(hds_basis["equality_admitted"]) is not bool):
        result["reason"] = "hds_observation_unknown"
        return result
    result["hds_basis"] = dict(hds_basis)
    def finite_clock(value):
        return type(value) in (int, float) and -1e100 < value < 1e100 and math.isfinite(value)

    if not finite_clock(now_monotonic) or not finite_clock(cutoff_monotonic):
        result["reason"] = "deadline_unknown"
        return result
    remaining = cutoff_monotonic - now_monotonic
    result["remaining_seconds"] = remaining
    if remaining <= 0:
        result["reason"] = "deadline_expired"
        return result
    result["accepted"] = True
    result["reason"] = "distinct_second_preserves_first_under_any_exact_target"
    return result
