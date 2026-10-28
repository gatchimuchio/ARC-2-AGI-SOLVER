"""Input-only candidate: learn a two-panel occupancy-to-color mapping from train."""
from collections import Counter


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
