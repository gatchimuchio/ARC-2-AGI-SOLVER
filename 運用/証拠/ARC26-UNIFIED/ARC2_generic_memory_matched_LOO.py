"""Compare current ARC2 HDS with the feature-neighbor family disabled.

Uses public training data only. Held-out outputs are inspected after both
runtime calls and are never passed to either solver invocation.
"""
from __future__ import annotations

from collections import Counter
from contextlib import redirect_stdout
import hashlib
import importlib
import io
import json
from pathlib import Path
import tempfile
import sys
import time
import zipfile


ROOT = Path(__file__).resolve().parents[3]
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BUNDLE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v14-v5-current-20261026/bundle.zip"


class NoFeatureNeighbor:
    """Baseline adapter that disables only the candidate under evaluation."""

    applicability_limit = -1.0

    def __init__(self, teachers):
        self.teachers = teachers

    def 最近距離(self, _grid):
        return float("inf")

    def 最近距離特徴量(self, _feature):
        return float("inf")

    def 適用範囲内(self, _grid):
        return False

    def 候補(self, _grid, _expected):
        return None, {"reason": "baseline_feature_neighbor_disabled"}

    def 記録(self):
        return {"disabled_for_matched_baseline": True}


def _prior_source_ids(challenge_ids: set[str]) -> set[str]:
    memory_root = ROOT / "記憶/事前記憶/v0.4"
    selected: set[str] = set()
    for shard in range(1, 5):
        doc = json.loads(
            (memory_root / f"1120題_HDS索引_{shard}.json").read_text(encoding="utf-8")
        )
        columns = doc["列"]
        for values in doc["records"]:
            row = dict(zip(columns, values, strict=True))
            if row["分割(0学習1評価)"] == 0 and row["機構確定"] == 1:
                task_id = row["課題ID"]
                if task_id not in challenge_ids:
                    selected.add(task_id)
    template = json.loads(
        (ROOT / "接続/ARC2/テンプレート充填教材.json").read_text(encoding="utf-8")
    )
    selected.update(item["課題ID"] for item in template["教材"])
    return selected


def _valid_nonidentity(grid, query, adapter) -> bool:
    return adapter.格子か(grid) and grid != query


def _submission_pair(result, query, teachers, adapter, simple, panel_model=None, panel_predict=None):
    rows = result.get("results", [])
    row = rows[0] if rows and isinstance(rows[0], dict) else {}
    candidate_pair = row.get("candidate_attempts")
    if (
        isinstance(candidate_pair, list)
        and len(candidate_pair) == 2
        and all(adapter.格子か(grid) for grid in candidate_pair)
        and candidate_pair[0] != candidate_pair[1]
    ):
        first, second = candidate_pair
    else:
        first = row.get("answer")
        if not adapter.格子か(first):
            first = query
        second = adapter._一意な別候補を選ぶ(
            row.get("candidate_predictions"), first
        )
        if panel_model is not None and panel_predict is not None:
            panel, _ = panel_predict(query, panel_model)
            if _valid_nonidentity(panel, query, adapter) and panel != first:
                records = row.get("candidate_predictions")
                if not isinstance(records, list):
                    records = []
                records = [*records, {"family": "repeated_panel_screen", "answer": panel}]
                second = adapter._一意な別候補を選ぶ(records, first)
        if not adapter.格子か(second) or second == first:
            second = simple.unique_candidate(teachers, query)
    return first, second if adapter.格子か(second) else query, row


def main(max_candidate_folds: int = 40, budget_seconds: float = 1200.0) -> int:
    bundle_bytes = BUNDLE.read_bytes()
    bundle_sha = hashlib.sha256(bundle_bytes).hexdigest()
    temporary_payload = tempfile.TemporaryDirectory(prefix="arc2-v14-loo-")
    payload_root = Path(temporary_payload.name)
    with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as archive:
        member_names = archive.namelist()
        bundle_manifest = json.loads(archive.read("__arc2_bundle_manifest__.json"))
        expected = {row["path"]: row for row in bundle_manifest["files"]}
        if set(member_names[1:]) != set(expected):
            raise ValueError("frozen bundle manifest does not match its members")
        for name in member_names[1:]:
            path = Path(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name:
                raise ValueError("unsafe frozen bundle member")
            content = archive.read(name)
            record = expected[name]
            if len(content) != record["size"] or hashlib.sha256(content).hexdigest() != record["sha256"]:
                raise ValueError("frozen bundle member checksum mismatch")
            target = payload_root.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    sys.path[:0] = [str(payload_root), str(payload_root / "HDS/学習系統/v0.4.2")]
    hds = importlib.import_module("接続.ARC2.HDS接続")
    feature = importlib.import_module("接続.ARC2.特徴近傍変換選択")
    simple = importlib.import_module("接続.ARC2.単純変換候補")
    adapter = importlib.import_module("接続.ARC2.Kaggle提出")
    panel = importlib.import_module("接続.ARC2.埋込見本一致候補")
    memory_path = payload_root / "接続/ARC2/事前記憶訓練例.json"
    memory_bytes = memory_path.read_bytes()
    generic_memory = hds.汎用事前記憶を読む()
    template = hds.事前教材を読む()
    challenge = json.loads(
        (ROOT / "入力/Kaggle/arc-agi_test_challenges.json").read_text(encoding="utf-8")
    )
    excluded_ids = _prior_source_ids(set(challenge))

    hashes_start = bundle_sha
    training_digest = hashlib.sha256()
    files = sorted(TRAINING.glob("*.json"))
    for path in files:
        training_digest.update(
            path.name.encode("utf-8") + b"\0" + hashlib.sha256(path.read_bytes()).digest()
        )
    before_exact = after_exact = before_pair = after_pair = 0
    baseline_fallbacks = candidate_fallbacks = accepted = 0
    candidate_folds = scanned_folds = gains = regressions = unchanged = 0
    gate_states: Counter[str] = Counter()
    started = time.perf_counter()
    original_feature = hds.FeatureNeighborTransform
    stopped = False

    for path in files:
        if path.stem in excluded_ids:
            continue
        task_data = json.loads(path.read_text(encoding="utf-8"))
        examples = task_data.get("train", [])
        if len(examples) < 3:
            continue
        for heldout_index, heldout in enumerate(examples):
            if time.perf_counter() - started >= budget_seconds or candidate_folds >= max_candidate_folds:
                stopped = True
                break
            teachers = [
                pair for index, pair in enumerate(examples) if index != heldout_index
            ]
            selector = original_feature(teachers)
            proposed, _ = selector.候補(heldout["input"], {})
            scanned_folds += 1
            if proposed is None:
                continue
            candidate_folds += 1
            task = {"train": teachers, "test": [{"input": heldout["input"]}]}

            hds.FeatureNeighborTransform = NoFeatureNeighbor
            try:
                with redirect_stdout(io.StringIO()):
                    baseline_raw = hds.課題を解く(
                        task,
                        template,
                        汎用事前教材=generic_memory,
                        候補収集=True,
                    )
            finally:
                hds.FeatureNeighborTransform = original_feature
            with redirect_stdout(io.StringIO()):
                current_raw = hds.課題を解く(
                    task,
                    template,
                    汎用事前教材=generic_memory,
                    候補収集=True,
                )

            panel_model, _ = panel.fit_candidate(teachers)
            before_first, before_second, _ = _submission_pair(
                baseline_raw,
                heldout["input"],
                teachers,
                adapter,
                simple,
                panel_model,
                panel.predict_candidate,
            )
            after_first, after_second, _ = _submission_pair(
                current_raw,
                heldout["input"],
                teachers,
                adapter,
                simple,
                panel_model,
                panel.predict_candidate,
            )
            target = heldout["output"]
            before_primary_ok = (
                _valid_nonidentity(before_first, heldout["input"], adapter)
                and before_first == target
            )
            after_primary_ok = (
                _valid_nonidentity(after_first, heldout["input"], adapter)
                and after_first == target
            )
            before_solved = before_primary_ok or (
                _valid_nonidentity(before_second, heldout["input"], adapter)
                and before_second == target
            )
            after_solved = after_primary_ok or (
                _valid_nonidentity(after_second, heldout["input"], adapter)
                and after_second == target
            )
            before_exact += int(before_primary_ok)
            after_exact += int(after_primary_ok)
            before_pair += int(before_solved)
            after_pair += int(after_solved)
            gains += int(after_solved and not before_solved)
            regressions += int(before_solved and not after_solved)
            unchanged += int(before_solved == after_solved)
            baseline_fallbacks += int(
                not _valid_nonidentity(before_first, heldout["input"], adapter)
            )
            candidate_fallbacks += int(
                not _valid_nonidentity(after_first, heldout["input"], adapter)
            )
            feature_record = next(
                (
                    item
                    for item in current_raw.get("families", [])
                    if item.get("境界") == "ARC特徴近傍変換選択"
                ),
                {},
            )
            accepted += int(
                bool(feature_record.get("採用可") and feature_record.get("同値採用"))
            )
            gate_states[feature_record.get("状態", "missing")] += 1
            if candidate_folds % 10 == 0:
                print(
                    json.dumps(
                        {
                            "candidate_folds": candidate_folds,
                            "scanned_folds": scanned_folds,
                            "baseline_pair_exact": before_pair,
                            "current_pair_exact": after_pair,
                            "regressions": regressions,
                        }
                    ),
                    flush=True,
                )
        if stopped:
            break

    hashes_end = hashlib.sha256(BUNDLE.read_bytes()).hexdigest()
    result = {
        "schema": "arc2-v5-generic-prior-matched-loo.v1",
        "data_source": "public ARC-AGI-2 training split and canonical HDS prior v0.4",
        "prior_memory_sha256": hashlib.sha256(memory_bytes).hexdigest(),
        "prior_source_tasks": generic_memory["source_task_count"],
        "prior_examples": generic_memory["example_count"],
        "prior_features": len(generic_memory["features"]),
        "leakage_guard": "exclude every prior source task and template source from held-out folds",
        "heldout_output_passed_to_solver": False,
        "fallback_counted_correct": False,
        "task_identifiers_or_grids_saved": False,
        "candidate_fold_limit": max_candidate_folds,
        "candidate_folds_evaluated": candidate_folds,
        "eligible_folds_scanned": scanned_folds,
        "complete": candidate_folds >= max_candidate_folds or not stopped,
        "baseline_primary_exact": before_exact,
        "current_primary_exact": after_exact,
        "primary_delta_exact": after_exact - before_exact,
        "baseline_pair_exact": before_pair,
        "current_pair_exact": after_pair,
        "paired_delta_exact": after_pair - before_pair,
        "paired_gains": gains,
        "paired_regressions": regressions,
        "paired_unchanged": unchanged,
        "baseline_fallbacks": baseline_fallbacks,
        "current_fallbacks": candidate_fallbacks,
        "hds_gate_accepted": accepted,
        "hds_gate_states": dict(gate_states),
        "frozen_bundle_sha256_start": hashes_start,
        "frozen_bundle_sha256_end": hashes_end,
        "frozen_bundle_unchanged": hashes_start == hashes_end,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "training_manifest_sha256": training_digest.hexdigest(),
    }
    output = ROOT / "出力/検証/ARC2-v5-v14-generic-prior-matched-loo-40fold-20261026.json"
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
